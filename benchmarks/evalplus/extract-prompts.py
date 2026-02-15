#!/usr/bin/env python3
"""Extract HumanEval prompts to JSON for Claude benchmark agent.

Produces a single JSON file that the Claude agent reads to solve each problem.
Run from the benchmarks/evalplus/ directory (needs the .venv with evalplus installed).

Usage:
    .venv/bin/python extract-prompts.py
"""

import json
from pathlib import Path

from evalplus.data import get_human_eval_plus


def main():
    problems = get_human_eval_plus()

    prompts = []
    for task_id, data in problems.items():
        prompts.append({
            "task_id": task_id,
            "prompt": data["prompt"],
            "entry_point": data["entry_point"],
        })

    out_path = Path("humaneval_prompts.json")
    with open(out_path, "w") as f:
        json.dump(prompts, f, indent=2)

    print(f"Extracted {len(prompts)} problems to {out_path}")


if __name__ == "__main__":
    main()
