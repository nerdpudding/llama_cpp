#!/usr/bin/env python3
"""
postprocess-solutions.py — Extract clean Python code from raw model output.

Applied uniformly to ALL models before evaluation for fair scoring.
Most solutions pass through unchanged; only those with markdown fences,
<think> tags, or explanatory text are cleaned.

Usage:
    python postprocess-solutions.py results/bench-glm-flash-q4/
    python postprocess-solutions.py results/bench-opus4.6-thinking/
"""

import json
import re
import shutil
import sys
from pathlib import Path


def extract_code(response: str) -> str:
    """Extract Python code from a model response.

    Handles:
    1. <think>...</think> blocks (GLM reasoning tags)
    2. Markdown code fences (```python ... ```) — takes the largest block
    3. Explanatory text before first import/from/def/class/@ line
    4. Clean code passes through unchanged
    """
    # Step 1: Strip <think>...</think> blocks
    cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

    # Step 2: Try to extract from markdown code blocks
    code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", cleaned, re.DOTALL)
    if code_blocks:
        return max(code_blocks, key=len).strip()

    # Step 3: Strip explanatory text before first Python construct
    lines = cleaned.split("\n")
    code_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (stripped.startswith("import ") or stripped.startswith("from ") or
                stripped.startswith("def ") or stripped.startswith("class ") or
                stripped.startswith("@")):
            code_start = i
            break

    if code_start is not None and code_start > 0:
        return "\n".join(lines[code_start:]).strip()

    # Step 4: Nothing to strip — return as-is
    return cleaned


def postprocess_file(jsonl_path: Path) -> tuple[int, int]:
    """Post-process a single JSONL file. Returns (total, modified) counts."""
    # Read all entries
    entries = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if not entries:
        return 0, 0

    # Process each entry
    modified = 0
    for entry in entries:
        original = entry.get("solution", "")
        cleaned = extract_code(original)
        if cleaned != original:
            entry["solution"] = cleaned
            modified += 1

    # Only write if something changed
    if modified > 0:
        # Backup original (only if no backup exists yet)
        backup_path = jsonl_path.with_suffix(".raw.jsonl")
        if not backup_path.exists():
            shutil.copy2(jsonl_path, backup_path)
            print(f"  Backup saved: {backup_path.name}")

        # Write cleaned entries
        with open(jsonl_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    return len(entries), modified


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <results-dir>")
        print(f"Example: {sys.argv[0]} results/bench-glm-flash-q4/")
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    humaneval_dir = results_dir / "humaneval"

    if not humaneval_dir.is_dir():
        print(f"No humaneval/ directory found in {results_dir}")
        sys.exit(1)

    # Find JSONL files (exclude backups and parts)
    jsonl_files = [
        f for f in humaneval_dir.glob("*.jsonl")
        if not f.name.endswith(".raw.jsonl") and "_part" not in f.name
    ]

    if not jsonl_files:
        print(f"No JSONL files found in {humaneval_dir}")
        sys.exit(1)

    total_solutions = 0
    total_modified = 0

    for jsonl_path in jsonl_files:
        count, modified = postprocess_file(jsonl_path)
        total_solutions += count
        total_modified += modified

    print(f"Post-processed {total_solutions} solutions, {total_modified} modified")


if __name__ == "__main__":
    main()
