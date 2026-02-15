#!/usr/bin/env python3
"""Custom code generation via local OpenAI-compatible API with system prompt.

Used instead of evalplus.codegen when a model needs a system prompt
(e.g., GPT-OSS reasoning level). Produces the same JSONL format.

Usage:
    python codegen-custom.py \
        --model-name "GPT-OSS 120B F16 (benchmark)" \
        --system-prompt "Reasoning: low" \
        --output-dir results/bench-gpt-oss-120b/
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).parent
PROMPTS_FILE = SCRIPT_DIR / "humaneval_prompts.json"
BASE_URL = "http://localhost:8080/v1/chat/completions"


def generate_solution(prompt_text: str, system_prompt: str, model_name: str) -> str:
    """Call local API for a single problem and return the response."""
    messages = [{"role": "user", "content": prompt_text}]
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    payload = json.dumps({
        "model": model_name,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 4096,
    }).encode()

    req = Request(BASE_URL, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())

    return data["choices"][0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser(description="Custom codegen with system prompt")
    parser.add_argument("--model-name", required=True, help="Model name for API calls")
    parser.add_argument("--system-prompt", default="", help="System prompt to prepend")
    parser.add_argument("--output-dir", required=True, help="Output directory (results/<model-id>/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) / "humaneval"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.model_name}_temp_0.0.jsonl"

    # Load prompts
    if not PROMPTS_FILE.exists():
        print(f"ERROR: {PROMPTS_FILE} not found")
        print("Run: .venv/bin/python extract-prompts.py")
        sys.exit(1)

    with open(PROMPTS_FILE) as f:
        prompts = json.load(f)

    print(f"Model:         {args.model_name}")
    print(f"System prompt: {args.system_prompt or '(none)'}")
    print(f"Problems:      {len(prompts)}")
    print(f"Output:        {output_file}")
    print()

    with open(output_file, "w") as out:
        for i, problem in enumerate(prompts):
            task_id = problem["task_id"]
            prompt_text = problem["prompt"]

            print(f"[{i+1}/{len(prompts)}] {task_id} ... ", end="", flush=True)

            try:
                response = generate_solution(prompt_text, args.system_prompt, args.model_name)

                entry = {"task_id": task_id, "solution": response}
                out.write(json.dumps(entry) + "\n")
                out.flush()

                print(f"OK ({len(response)} chars)")

            except URLError as e:
                print(f"ERROR: {e}")
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


if __name__ == "__main__":
    main()
