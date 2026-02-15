#!/usr/bin/env python3
"""
generate-report.py — Generate markdown comparison report from EvalPlus results.

Reads eval_results.json files from the results directory and combines them
with reference scores from reference-scores.json to produce a comparison table.

Usage:
    python generate-report.py --results-dir results --reference reference-scores.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# Map section IDs to readable display names
DISPLAY_NAMES = {
    "bench-glm-flash-q4": "GLM-4.7 Flash Q4_K_M",
    "bench-glm-flash-q8": "GLM-4.7 Flash Q8_0",
    "bench-gpt-oss-120b": "GPT-OSS 120B F16",
    "bench-qwen3-coder-ud-q5": "Qwen3-Coder-Next UD-Q5_K_XL",
    "bench-qwen3-coder-ud-q6": "Qwen3-Coder-Next UD-Q6_K_XL",
    "bench-opus4.6-thinking": "Claude Opus 4.6 (thinking)",
    "bench-opus4.6": "Claude Opus 4.6",
}

# Map section IDs to reference model keys for delta calculation
REFERENCE_MAP = {
    "bench-qwen3-coder-ud-q5": "Qwen3-Coder-Next (FP16, official)",
    "bench-qwen3-coder-ud-q6": "Qwen3-Coder-Next (FP16, official)",
    "bench-gpt-oss-120b": "GPT-OSS 120B (official)",
    "bench-glm-flash-q4": "GLM-4.7 (full, not Flash)",
    "bench-glm-flash-q8": "GLM-4.7 (full, not Flash)",
    "bench-opus4.6-thinking": "Claude Opus 4.5",
    "bench-opus4.6": "Claude Opus 4.5",
}


def find_eval_results(results_dir: str) -> dict:
    """Find all eval_results.json files in the results directory."""
    results = {}
    results_path = Path(results_dir)

    if not results_path.exists():
        return results

    for model_dir in sorted(results_path.iterdir()):
        if not model_dir.is_dir() or model_dir.name.startswith(".") or model_dir.name.startswith("archive"):
            continue

        for f in model_dir.rglob("*eval_results.json"):
            results[model_dir.name] = f
            break

    return results


def parse_eval_results(filepath: Path) -> dict:
    """Extract pass@1 scores from an EvalPlus eval_results.json file."""
    with open(filepath) as f:
        data = json.load(f)

    scores = {}

    # Format 1: pass_at_k summary (older evalplus versions)
    pass_at_k = data.get("pass_at_k", {})
    if pass_at_k:
        base = pass_at_k.get("base", {})
        if "pass@1" in base:
            scores["humaneval_base"] = round(base["pass@1"] * 100, 1)
        plus = pass_at_k.get("plus", {})
        if "pass@1" in plus:
            scores["humaneval_plus"] = round(plus["pass@1"] * 100, 1)

    # Format 2: per-problem eval results (newer evalplus versions)
    if not scores and "eval" in data:
        eval_data = data["eval"]
        total = len(eval_data)
        if total > 0:
            base_pass = sum(1 for v in eval_data.values() if v[0].get("base_status") == "pass")
            plus_pass = sum(1 for v in eval_data.values() if v[0].get("plus_status") == "pass")
            scores["humaneval_base"] = round(base_pass / total * 100, 1)
            scores["humaneval_plus"] = round(plus_pass / total * 100, 1)

    return scores


def load_reference_scores(filepath: str) -> dict:
    """Load reference scores from JSON file."""
    if not os.path.exists(filepath):
        return {}

    with open(filepath) as f:
        data = json.load(f)

    return data.get("models", {})


def calc_delta(local_scores, model_id, reference, score_key):
    """Calculate delta vs reference score. Tries humaneval_plus first, falls back to humaneval."""
    ref_key = REFERENCE_MAP.get(model_id)
    if not ref_key or ref_key not in reference:
        return None

    local = local_scores.get(score_key)
    if local is None:
        return None

    ref_data = reference[ref_key]
    # Try matching score type first, then fall back
    if score_key == "humaneval_plus":
        ref_score = ref_data.get("humaneval_plus") or ref_data.get("humaneval")
    else:
        ref_score = ref_data.get("humaneval")

    if ref_score is None:
        return None

    return local - ref_score


def generate_report(results_dir: str, reference_file: str) -> str:
    """Generate the full markdown report."""
    eval_files = find_eval_results(results_dir)
    reference = load_reference_scores(reference_file)

    lines = []
    lines.append(f"# EvalPlus HumanEval+ Benchmark Results")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    if not eval_files:
        lines.append("No results found. Run benchmarks first:")
        lines.append("```")
        lines.append("./benchmark.sh --local")
        lines.append("```")
        return "\n".join(lines)

    # Parse all local scores and sort by HumanEval+ descending
    local_scores = {}
    for model_id, filepath in eval_files.items():
        scores = parse_eval_results(filepath)
        if scores:
            local_scores[model_id] = scores

    sorted_local = sorted(
        local_scores.items(),
        key=lambda x: x[1].get("humaneval_plus", 0),
        reverse=True,
    )

    # --- Local results table ---
    lines.append("## Local Results (pass@1, greedy decoding, temperature=0)")
    lines.append("")
    lines.append("| # | Model | HumanEval | HumanEval+ | vs FP16 ref |")
    lines.append("|---|-------|-----------|------------|-------------|")

    for rank, (model_id, scores) in enumerate(sorted_local, 1):
        name = DISPLAY_NAMES.get(model_id, model_id)
        if "glm" in model_id.lower():
            name += " *"
        base = scores.get("humaneval_base")
        plus = scores.get("humaneval_plus")

        base_str = f"{base:.1f}%" if base is not None else "—"
        plus_str = f"{plus:.1f}%" if plus is not None else "—"

        delta = calc_delta(scores, model_id, reference, "humaneval_base")
        delta_str = f"{delta:+.1f}pp" if delta is not None else "—"

        lines.append(f"| {rank} | {name} | {base_str} | {plus_str} | {delta_str} |")

    lines.append("")

    # --- HumanEval ranking (most models have this) ---
    lines.append("## HumanEval Ranking (pass@1)")
    lines.append("")
    lines.append("| # | Model | HumanEval | Source |")
    lines.append("|---|-------|-----------|--------|")

    he_scores = []
    for name, data in reference.items():
        he = data.get("humaneval")
        source = data.get("source", "")
        if he is not None:
            he_scores.append((he, name, source, False))
    for model_id, scores in local_scores.items():
        he = scores.get("humaneval_base")
        name = DISPLAY_NAMES.get(model_id, model_id)
        if he is not None:
            he_scores.append((he, name, "Local benchmark", True))

    he_scores.sort(key=lambda x: x[0], reverse=True)
    for rank, (he, name, source, is_local) in enumerate(he_scores, 1):
        if is_local:
            lines.append(f"| {rank} | **{name}** | **{he:.1f}%** | **{source}** |")
        else:
            lines.append(f"| {rank} | {name} | {he:.1f}% | {source} |")

    lines.append("")

    # --- HumanEval+ ranking (stricter, fewer models have published scores) ---
    lines.append("## HumanEval+ Ranking (pass@1, stricter)")
    lines.append("")
    lines.append("| # | Model | HumanEval+ | Source |")
    lines.append("|---|-------|------------|--------|")

    hp_scores = []
    for name, data in reference.items():
        hp = data.get("humaneval_plus")
        source = data.get("source", "")
        if hp is not None:
            hp_scores.append((hp, name, source, False))
    for model_id, scores in local_scores.items():
        hp = scores.get("humaneval_plus")
        name = DISPLAY_NAMES.get(model_id, model_id)
        if hp is not None:
            hp_scores.append((hp, name, "Local benchmark", True))

    hp_scores.sort(key=lambda x: x[0], reverse=True)
    for rank, (hp, name, source, is_local) in enumerate(hp_scores, 1):
        if is_local:
            lines.append(f"| {rank} | **{name}** | **{hp:.1f}%** | **{source}** |")
        else:
            lines.append(f"| {rank} | {name} | {hp:.1f}% | {source} |")

    lines.append("")

    # --- Notes ---
    lines.append("## Notes")
    lines.append("")
    lines.append("- All local results use greedy decoding (temperature=0, max_tokens=4096)")
    lines.append("- **HumanEval+** uses 80x more tests than standard HumanEval (stricter, scores are typically 3-8% lower)")
    lines.append("- Local benchmarks produce both HumanEval and HumanEval+ scores")
    lines.append("- \"vs FP16 ref\" shows difference in HumanEval base score vs the closest official published score")
    lines.append("- Many reference models only have HumanEval (not HumanEval+) published — direct comparison on HumanEval+ is limited")
    lines.append("- Local scores may differ from published due to quantization, prompt template, and max_tokens differences")
    lines.append("- GLM-4.7 Flash is a reasoning model — benchmarked with `--reasoning-format none` to include thinking in output. Scores may be less reliable: the model spends tokens on chain-of-thought reasoning before producing code, and the code extractor must parse it from mixed reasoning+code output. The Q4 > Q8 score inversion is likely caused by this")

    # Add Claude note if any opus results exist
    has_opus = any("opus" in mid for mid in local_scores)
    if has_opus:
        lines.append("- Claude Opus 4.6 was tested via Claude Code (Max subscription) using a custom agent that solves each problem from the prompt alone — no code execution, no internet, no tools. \"vs FP16 ref\" compares against the published Opus 4.5 score (no Opus 4.6 reference available yet)")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate EvalPlus benchmark report")
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Directory containing benchmark results (default: results)",
    )
    parser.add_argument(
        "--reference",
        default="reference-scores.json",
        help="Reference scores JSON file (default: reference-scores.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (default: results/REPORT.md)",
    )
    args = parser.parse_args()

    report = generate_report(args.results_dir, args.reference)

    # Print to stdout
    print(report)

    # Save to file
    output_path = args.output or os.path.join(args.results_dir, "REPORT.md")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    print(f"\nReport saved to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
