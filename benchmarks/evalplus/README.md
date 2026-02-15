# EvalPlus Coding Benchmark

Runs [HumanEval+](https://github.com/evalplus/evalplus) (164 Python coding problems, 80x more tests than original HumanEval) against models served by the llama.cpp Docker wrapper.

Results are comparable to the [EvalPlus leaderboard](https://evalplus.github.io/leaderboard.html) — same benchmark, same greedy decoding, same pass@1 metric.

## Table of contents

- [Quick reference](#quick-reference)
- [How it works](#how-it-works)
- [Prerequisites](#prerequisites)
- [One-time setup](#one-time-setup)
- [Usage](#usage)
- [Benchmark profiles](#benchmark-profiles)
- [Output](#output)
- [Claude Opus 4.6 benchmark](#claude-opus-46-benchmark)
- [Troubleshooting](#troubleshooting)
- [Technical notes](#technical-notes)

## Quick reference

### Local models (llama.cpp)

```bash
cd benchmarks/evalplus
./run-benchmark.sh --list                    # Show available benchmark profiles
./run-benchmark.sh bench-glm-flash-q4        # Run one model (smoke test)
./run-benchmark.sh bench-qwen3-coder-ud-q6 bench-gpt-oss-120b   # Run specific models
./run-benchmark.sh                           # Run all bench-* profiles
./run-benchmark.sh --report                  # Regenerate report from existing results
```

### Claude Opus 4.6

Three steps: extract prompts → run agent → evaluate results.

```bash
# Step 1: Extract the 164 HumanEval prompts to a JSON file (one-time, already done)
cd benchmarks/evalplus
.venv/bin/python extract-prompts.py          # Creates humaneval_prompts.json

# Step 2: Start a NEW Claude Code session with the benchmark agent
#         (must be a clean session — not inside an existing conversation)
cd /home/rvanpolen/vibe_claude_kilo_cli_exp/llama_cpp
claude --agent humaneval-solver-thinking     # With extended thinking
# or:
claude --agent humaneval-solver              # Without extended thinking
#
# On first run you may be asked about thinking effort:
#   - For thinking variant: choose "high" (default)
#   - For non-thinking variant: choose "low"
#   (on subsequent runs it remembers your choice — change with Alt+T or /model)
#
# If Claude starts in plan mode (shows "plan mode on" at the bottom):
#   - Press Shift+Tab to cycle to normal mode (Default → Accept Edits → Plan → ...)
#   - The agent needs normal mode to write files
#
# Then type "start" — the agent reads the prompts, solves all 164 problems,
# and writes the solutions to results/bench-opus4.6-thinking/ (or bench-opus4.6/)

# Step 3: After the agent finishes, evaluate the solutions in Docker sandbox
cd benchmarks/evalplus
./evaluate-claude.sh bench-opus4.6-thinking  # Evaluate thinking variant
./evaluate-claude.sh bench-opus4.6           # Evaluate non-thinking variant
# This runs the same test suite as local models and updates REPORT.md
```

## How it works

1. **Code generation (host)** — EvalPlus sends 164 coding prompts to the llama.cpp OpenAI-compatible API (`localhost:8080/v1`). The model generates Python code for each problem. This runs on the host using the evalplus Python package.
2. **Evaluation (Docker sandbox)** — Generated code runs inside a Docker sandbox (`ganler/evalplus:latest`) against unit tests. This is isolated from the host for safety — the AI-generated code never executes on your machine directly.
3. **Scoring** — pass@1 = percentage of problems solved correctly on the first attempt.

The benchmark script handles everything automatically: starts each model via docker compose, waits for health, runs code generation, stops the model, evaluates in sandbox, and moves to the next model.

## Prerequisites

- Docker running (for both llama-server and evalplus sandbox)
- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Model files downloaded (same as regular usage)
- No running llama-server container (the script manages its own)

## One-time setup

```bash
cd benchmarks/evalplus
uv venv
source .venv/bin/activate
uv pip install evalplus
```

Verify it works:

```bash
source .venv/bin/activate
python -c "import evalplus; print('OK')"
```

## Usage

Always activate the venv first:

```bash
cd benchmarks/evalplus
source .venv/bin/activate
```

### Smoke test (recommended first run)

Before running all 6 models, test with the fastest/smallest model to verify the full pipeline works:

```bash
./run-benchmark.sh bench-glm-flash-q4
```

This runs GLM-4.7 Flash Q4_K_M (smallest model, fits in VRAM) through the complete cycle: start server → generate code → stop server → evaluate in sandbox → generate report.

Check the output for errors. If it completes and produces results in `results/bench-glm-flash-q4/`, the pipeline works.

### Full run (all models)

Once the smoke test passes, run all 6 benchmark profiles:

```bash
./run-benchmark.sh
```

This runs all `bench-*` profiles from `models.conf` sequentially — one model at a time, each going through the full generate → evaluate cycle. Best started before leaving or overnight.

### Re-running a model

Delete old results first, then run again:

```bash
rm -rf results/bench-glm-flash/
./run-benchmark.sh bench-glm-flash
```

Without deleting, evalplus skips code generation because results already exist.

## Benchmark profiles

Benchmark profiles are defined in `models.conf` with a `bench-` prefix. They use the same model files and GPU layer splits as production, but with reduced context (16K instead of 64K-256K) to save VRAM.

| Profile | Model | Notes |
|---------|-------|-------|
| `bench-glm-flash-q4` | GLM-4.7 Flash Q4_K_M | Smallest, fastest — good for smoke testing |
| `bench-glm-flash` | GLM-4.7 Flash Q8_0 | Higher quality quant |
| `bench-gpt-oss-120b` | GPT-OSS 120B F16 | Large MoE, partial CPU offload |
| `bench-qwen3-coder-ud-q5` | Qwen3-Coder-Next UD-Q5_K_XL | Speed option |
| `bench-qwen3-coder-ud-q6` | Qwen3-Coder-Next UD-Q6_K_XL | Coding baseline |
| `bench-qwen3-coder-q6k` | Qwen3-Coder-Next Q6_K | Standard quant |

To view or edit profiles: `./run-benchmark.sh --list` or edit `models.conf` directly.

## Output

Results are saved per model in `results/<model-id>/`:

```
results/
├── bench-glm-flash-q4/
│   ├── humaneval/
│   │   └── <samples>.jsonl     # Generated code (164 solutions)
│   ├── codegen.log             # Code generation output
│   └── evaluation.log          # Docker sandbox evaluation output
├── bench-qwen3-coder-ud-q6/
│   └── ...
├── REPORT.md                   # Comparison report (auto-generated)
└── NOTES_max_tokens.md         # Notes on discarded run 1 (max_tokens=768)
```

The comparison report (`REPORT.md`) includes local scores alongside published scores from proprietary models (Claude, GPT, DeepSeek, etc.) sourced from `reference-scores.json`.

## Claude Opus 4.6 benchmark

Claude Opus 4.6 can be benchmarked on the same HumanEval+ problems using a custom Claude Code agent. The agent reads each problem and writes a solution from knowledge alone — no code execution, no internet, no tools other than Read/Write.

### Prerequisites

- Claude Code with a Max subscription
- Prompts extracted: `.venv/bin/python extract-prompts.py` (creates `humaneval_prompts.json`)

### Running

Start a **clean** Claude Code session with the agent:

```bash
cd /home/rvanpolen/vibe_claude_kilo_cli_exp/llama_cpp
claude --agent humaneval-solver-thinking    # with extended thinking
# or
claude --agent humaneval-solver             # without extended thinking
```

Type `start` and wait for the agent to solve all 164 problems. Solutions are written to `results/bench-opus4.6-thinking/` or `results/bench-opus4.6/`.

### Evaluation

After the agent finishes, evaluate the solutions and regenerate the report:

```bash
cd benchmarks/evalplus
./evaluate-claude.sh bench-opus4.6-thinking
# or for both:
./evaluate-claude.sh
```

This runs the same Docker sandbox evaluation as the local models and updates REPORT.md.

### Notes

- The agent has only Read and Write tools — no Bash, no WebSearch, no code execution
- HumanEval is likely in Claude's training data (same applies to all frontier models with published scores)
- "vs FP16 ref" in the report compares against the published Opus 4.5 score (no Opus 4.6 reference available)
- If context runs out mid-session, the agent writes partial results with instructions on where to continue

## Troubleshooting

- **"Python venv not found"** — Run the one-time setup steps above.
- **"Container llama-server is already running"** — Stop it first: `docker compose -f ../../docker-compose.yml down`
- **Server fails to start** — Check that the model file exists. The script logs the last 30 lines from the container on failure.
- **Timeout waiting for health** — Large models (GPT-OSS 120B) can take several minutes to load. The default timeout is 10 minutes. If that's not enough, increase `HEALTH_TIMEOUT` in `run-benchmark.sh`.
- **Evaluation produces unexpected results** — Check `evaluation.log` in the model's results directory. The Docker sandbox needs to pull `ganler/evalplus:latest` on first run.
- **Interrupted mid-run** — Safe to restart. The script stops the container on each model transition. Completed results are preserved.

## Technical notes

- EvalPlus uses `--greedy` (temperature=0), which overrides server-side sampler settings via the API. The sampler defaults in `models.conf` are for production use, not benchmarks.
- The evalplus Docker sandbox (`ganler/evalplus`) has no network access — it only gets a volume mount with the generated code files.
- The script reuses the same `docker-compose.yml` and `.env` mechanism as `start.sh`, so hardware-specific GPU splits are identical to production.
- EvalPlus also supports MBPP+ (378 problems). To add it, change `--dataset humaneval` to `--dataset mbpp` in `run-benchmark.sh` or add a `--dataset` flag.
