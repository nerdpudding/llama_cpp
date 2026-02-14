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


def find_eval_results(results_dir: str) -> dict:
    """Find all eval_results.json files in the results directory."""
    results = {}
    results_path = Path(results_dir)

    if not results_path.exists():
        return results

    for model_dir in sorted(results_path.iterdir()):
        if not model_dir.is_dir() or model_dir.name.startswith("."):
            continue

        # EvalPlus saves results as eval_results.json or *.eval_results.json
        for f in model_dir.rglob("*eval_results.json"):
            results[model_dir.name] = f
            break  # Take the first match per model

    return results


def parse_eval_results(filepath: Path) -> dict:
    """Extract pass@1 scores from an EvalPlus eval_results.json file."""
    with open(filepath) as f:
        data = json.load(f)

    scores = {}
    pass_at_k = data.get("pass_at_k", {})

    # Base HumanEval tests
    base = pass_at_k.get("base", {})
    if "pass@1" in base:
        scores["humaneval_base"] = round(base["pass@1"] * 100, 1)

    # HumanEval+ (base + extra tests)
    plus = pass_at_k.get("plus", {})
    if "pass@1" in plus:
        scores["humaneval_plus"] = round(plus["pass@1"] * 100, 1)

    return scores


def load_reference_scores(filepath: str) -> dict:
    """Load reference scores from JSON file."""
    if not os.path.exists(filepath):
        return {}

    with open(filepath) as f:
        data = json.load(f)

    return data.get("models", {})


def generate_report(results_dir: str, reference_file: str) -> str:
    """Generate the full markdown report."""
    eval_files = find_eval_results(results_dir)
    reference = load_reference_scores(reference_file)

    lines = []
    lines.append(f"# EvalPlus Benchmark Results — {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    if not eval_files:
        lines.append("No results found. Run benchmarks first:")
        lines.append("```")
        lines.append("./run-benchmark.sh")
        lines.append("```")
        return "\n".join(lines)

    # --- Local results table ---
    lines.append("## Local HumanEval+ Results (pass@1, greedy)")
    lines.append("")
    lines.append("| Model | HumanEval (base) | HumanEval+ | vs FP16 ref |")
    lines.append("|-------|-----------------|------------|-------------|")

    local_scores = {}
    for model_id, filepath in eval_files.items():
        scores = parse_eval_results(filepath)
        local_scores[model_id] = scores

        base = scores.get("humaneval_base")
        plus = scores.get("humaneval_plus")

        base_str = f"{base:.1f}%" if base is not None else "—"
        plus_str = f"{plus:.1f}%" if plus is not None else "—"

        # Calculate delta vs reference
        delta_str = "—"
        if plus is not None:
            # Try to match model to a reference
            if "qwen3" in model_id.lower():
                ref = reference.get("Qwen3-Coder-Next (FP16, official)", {})
                ref_score = ref.get("humaneval_plus")
                if ref_score is not None:
                    delta = plus - ref_score
                    delta_str = f"{delta:+.1f}pp"
            elif "gpt-oss" in model_id.lower():
                ref = reference.get("GPT-OSS 120B (official)", {})
                ref_score = ref.get("humaneval_plus")
                if ref_score is not None:
                    delta = plus - ref_score
                    delta_str = f"{delta:+.1f}pp"
            elif "glm" in model_id.lower():
                ref = reference.get("GLM-4.7 Flash (official)", {})
                ref_score = ref.get("humaneval_plus")
                if ref_score is not None:
                    delta = plus - ref_score
                    delta_str = f"{delta:+.1f}pp"

        lines.append(f"| {model_id} | {base_str} | {plus_str} | {delta_str} |")

    lines.append("")

    # --- Comparison with published scores ---
    lines.append("## Comparison with Published Scores")
    lines.append("")
    lines.append("| Model | HumanEval+ | HumanEval | Source |")
    lines.append("|-------|------------|-----------|--------|")

    # Collect all scores into a sortable list
    # (sort_key, name, humaneval_plus, humaneval, source)
    all_scores = []

    # Add reference scores
    for name, data in reference.items():
        hp = data.get("humaneval_plus")
        he = data.get("humaneval")
        source = data.get("source", "")
        if hp is not None or he is not None:
            sort_key = hp if hp is not None else (he - 5 if he is not None else 0)
            all_scores.append((sort_key, name, hp, he, source))

    # Add local scores
    for model_id, scores in local_scores.items():
        hp = scores.get("humaneval_plus")
        he = scores.get("humaneval_base")
        if hp is not None or he is not None:
            sort_key = hp if hp is not None else 0
            all_scores.append((sort_key, f"**{model_id}**", hp, he, "**Local benchmark**"))

    # Sort by sort_key descending
    all_scores.sort(key=lambda x: x[0], reverse=True)

    for _, name, hp, he, source in all_scores:
        hp_str = f"{hp:.1f}%" if hp is not None else "—"
        he_str = f"{he:.1f}%" if he is not None else "—"
        lines.append(f"| {name} | {hp_str} | {he_str} | {source} |")

    lines.append("")

    # --- Notes ---
    lines.append("## Notes")
    lines.append("")
    lines.append("- All local results use greedy decoding (temperature=0)")
    lines.append("- **HumanEval+** uses 80x more tests than standard HumanEval (stricter, scores ~3-8% lower)")
    lines.append("- Local benchmarks produce HumanEval+ scores — compare to HumanEval+ column, not HumanEval")
    lines.append("- \"vs FP16 ref\" shows difference from full-precision published score")
    lines.append("- Local scores may differ from published due to quantization and prompt template differences")
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
