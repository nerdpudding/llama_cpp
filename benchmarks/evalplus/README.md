# EvalPlus Coding Benchmark

Runs [HumanEval+](https://github.com/evalplus/evalplus) (164 Python coding problems, 80x more tests than original HumanEval) against models served by the llama.cpp Docker wrapper.

Results are comparable to the [EvalPlus leaderboard](https://evalplus.github.io/leaderboard.html) — same benchmark, same greedy decoding, same pass@1 metric.

## How it works

1. **Code generation** — EvalPlus sends 164 coding prompts to the llama.cpp OpenAI-compatible API (`localhost:8080/v1`). The model generates Python code for each problem.
2. **Evaluation** — Generated code runs inside a Docker sandbox (`ganler/evalplus`) against unit tests. Each problem is scored pass/fail based on whether all tests pass.
3. **Scoring** — pass@1 = percentage of problems solved correctly on the first attempt.

## Prerequisites

- Docker running (for both llama-server and evalplus sandbox)
- [uv](https://docs.astral.sh/uv/) installed
- Model files downloaded (same as regular usage)

## One-time setup

```bash
cd benchmarks/evalplus
uv venv
source .venv/bin/activate
uv pip install evalplus
```

## Usage

```bash
# Run all 6 benchmark profiles
./run-benchmark.sh

# Run specific model(s)
./run-benchmark.sh bench-glm-flash-q4
./run-benchmark.sh bench-qwen3-coder bench-gpt-oss-120b

# List available benchmark profiles
./run-benchmark.sh --list

# Generate report from existing results (no benchmarking)
./run-benchmark.sh --report
```

## Benchmark profiles

Benchmark profiles are defined in `models.conf` with a `bench-` prefix. They use the same model files and GPU layer splits as production, but with reduced context (16K instead of 64K-256K) since HumanEval+ problems need <1,300 tokens max.

## Expected runtime

~1 hour per model for HumanEval+ (164 problems). 6 models = ~6 hours total. Best run overnight.

## Output

Results are saved per model in `results/<model-id>/`. After a run, a comparison report is generated at `results/REPORT.md`.

## Adding MBPP+ later

EvalPlus also supports MBPP+ (378 problems). To add it, change `--dataset humaneval` to `--dataset mbpp` in `run-benchmark.sh` or add a `--dataset` flag.
