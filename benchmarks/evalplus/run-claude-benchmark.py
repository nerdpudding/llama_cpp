#!/usr/bin/env python3
"""Run HumanEval benchmark using Claude Code CLI.

Each problem is solved in a separate stateless `claude -p` invocation,
identical to how evalplus calls local model APIs: one problem per request,
no context carryover between problems.

`claude -p` is Claude Code's non-interactive (print) mode. It sends a
prompt, prints the response, and exits. No interactive session, no UI.
It uses the same model and subscription as the interactive Claude Code.

Requirements:
    - Claude Code installed and authenticated (claude command available)
    - Claude Code Max subscription (for Opus model access)

Usage:
    # With extended thinking (high effort):
    python run-claude-benchmark.py --thinking

    # Without extended thinking (low effort):
    python run-claude-benchmark.py

    # Resume from a specific problem (e.g., after interruption):
    python run-claude-benchmark.py --thinking --start-from 42

    # Then evaluate:
    ./benchmark.sh bench-opus4.6-thinking
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROMPTS_FILE = SCRIPT_DIR / "humaneval_prompts.json"

SYSTEM_PROMPT = (
    "Complete the given Python function. "
    "Output ONLY valid Python code — nothing else. "
    "Include necessary imports, the function signature with its docstring, "
    "and your implementation. "
    "Do not wrap the code in markdown fences. "
    "Do not add any explanation, commentary, or text before or after the code."
)


def solve_problem(prompt_text: str, thinking: bool) -> str:
    """Call claude -p for a single problem and return the response."""
    cmd = [
        "claude", "-p",
        "--model", "opus",
        "--tools", "",
        "--no-session-persistence",
        "--system-prompt", SYSTEM_PROMPT,
    ]

    if thinking:
        cmd.extend(["--effort", "high"])
    else:
        cmd.extend(["--effort", "low"])

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)  # prevent nested session error

    result = subprocess.run(
        cmd,
        input=prompt_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,  # 5 min max per problem
    )

    if result.returncode != 0:
        print(f"  WARNING: claude exited with code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(f"  stderr: {result.stderr[:200]}", file=sys.stderr)

    return result.stdout.strip()


def extract_code(response: str) -> str:
    """Extract Python code from Claude's response.

    Handles common issues:
    - Markdown code fences (```python ... ```)
    - Explanatory text before the code
    - Multiple code blocks (takes the largest one)
    """
    # Try to extract from markdown code blocks first
    import re
    code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    if code_blocks:
        # Return the largest code block (most likely the full solution)
        return max(code_blocks, key=len).strip()

    # No code blocks — try to find where the Python code starts
    lines = response.split("\n")
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

    # Nothing to strip — return as-is
    return response.strip()


def main():
    parser = argparse.ArgumentParser(description="Run HumanEval benchmark via Claude Code CLI")
    parser.add_argument("--thinking", action="store_true",
                        help="Enable extended thinking (high effort)")
    parser.add_argument("--start-from", type=int, default=0,
                        help="Resume from problem index (0-based)")
    args = parser.parse_args()

    if args.thinking:
        bench_id = "bench-opus4.6-thinking"
        model_name = "Claude Opus 4.6 thinking"
    else:
        bench_id = "bench-opus4.6"
        model_name = "Claude Opus 4.6"

    results_dir = SCRIPT_DIR / "results" / bench_id / "humaneval"
    results_dir.mkdir(parents=True, exist_ok=True)
    output_file = results_dir / f"{model_name}_temp_0.0.jsonl"

    # Load prompts
    if not PROMPTS_FILE.exists():
        print(f"ERROR: {PROMPTS_FILE} not found")
        print("Run: .venv/bin/python extract-prompts.py")
        sys.exit(1)

    with open(PROMPTS_FILE) as f:
        prompts = json.load(f)

    print(f"Benchmark: {model_name}")
    print(f"Thinking:  {'high effort' if args.thinking else 'low effort'}")
    print(f"Problems:  {len(prompts)} (starting from {args.start_from})")
    print(f"Output:    {output_file}")
    print()

    # Load existing solutions if resuming
    existing = {}
    if args.start_from > 0 and output_file.exists():
        with open(output_file) as f:
            for line in f:
                entry = json.loads(line)
                existing[entry["task_id"]] = entry
        print(f"Loaded {len(existing)} existing solutions")

    mode = "a" if args.start_from > 0 else "w"
    with open(output_file, mode) as out:
        for i, problem in enumerate(prompts):
            if i < args.start_from:
                continue

            task_id = problem["task_id"]
            prompt_text = problem["prompt"]

            if task_id in existing:
                continue

            print(f"[{i+1}/{len(prompts)}] {task_id} ... ", end="", flush=True)

            try:
                response = solve_problem(prompt_text, args.thinking)
                solution = extract_code(response)

                # If the model didn't include the original prompt, prepend it
                if problem["entry_point"] not in solution:
                    solution = prompt_text + solution

                entry = {"task_id": task_id, "solution": solution}
                out.write(json.dumps(entry) + "\n")
                out.flush()

                print(f"OK ({len(solution)} chars)")

            except subprocess.TimeoutExpired:
                print("TIMEOUT")
                entry = {"task_id": task_id, "solution": prompt_text + "    pass\n"}
                out.write(json.dumps(entry) + "\n")
                out.flush()

            except Exception as e:
                print(f"ERROR: {e}")
                entry = {"task_id": task_id, "solution": prompt_text + "    pass\n"}
                out.write(json.dumps(entry) + "\n")
                out.flush()

    print()
    print(f"Done! Solutions written to {output_file}")
    print()
    print("Next step — evaluate:")
    print(f"  ./benchmark.sh {bench_id}")


if __name__ == "__main__":
    main()
