# EvalPlus Coding Benchmark

Runs [HumanEval+](https://github.com/evalplus/evalplus) (164 Python coding problems, 80x more tests than original HumanEval) against models served by the llama.cpp Docker wrapper.

Results are comparable to the [EvalPlus leaderboard](https://evalplus.github.io/leaderboard.html) — same benchmark, same greedy decoding, same pass@1 metric.

## Quick reference

```bash
cd benchmarks/evalplus
./benchmark.sh --list                   # Show available benchmark profiles
./benchmark.sh bench-glm-flash-q4       # Run one model (smoke test)
./benchmark.sh --local                  # All local models (llama.cpp)
./benchmark.sh --all                    # All models (local + Claude)
./benchmark.sh --report                 # Regenerate report from existing results
```

## How it works

### Pipeline

Each model goes through 4 steps:

1. **Codegen** — Generate code for 164 problems (local models via llama.cpp API, Claude via `claude -p`)
2. **Post-process** — Extract clean Python code from raw output (strips `<think>` tags, markdown fences, explanatory text). Applied uniformly to ALL models. Original raw output backed up as `*.raw.jsonl`.
3. **Evaluate** — Run evalplus against the cleaned solutions
4. **Report** — Generate comparison table with local + proprietary model scores

### Scripts

| File | Purpose |
|------|---------|
| `benchmark.sh` | Main runner — orchestrates all steps |
| `codegen.sh` | Code generation for local models (server start, health check, evalplus codegen, server stop) |
| `postprocess-solutions.py` | Extracts clean Python code from raw model output (strips think tags, markdown fences, explanatory text) |
| `evaluate.sh` | Runs evalplus evaluation on post-processed solutions |
| `generate-report.py` | Generates markdown comparison report from eval results + reference scores |
| `codegen-custom.py` | Custom codegen with system prompt support (used when `bench-client.conf` specifies a system prompt for a model) |
| `run-claude-benchmark.py` | Claude codegen via `claude -p` (Claude Code non-interactive mode) |
| `bench-client.conf` | Client-side config per model (system prompts, reasoning levels). Separate from `models.conf` (server config). |
| `extract-prompts.py` | One-time utility to extract HumanEval prompts from evalplus into JSON (already done) |
| `humaneval_prompts.json` | The 164 HumanEval problem prompts — used by `codegen-custom.py` and `run-claude-benchmark.py` |
| `reference-scores.json` | Published scores for proprietary models (Claude, GPT, DeepSeek, etc.) — used by `generate-report.py` |

### Existing data handling

When results already exist for a model, the runner asks:

```
Results already exist for bench-glm-flash-q4.
  [d] Delete existing and run fresh
  [s] Skip this model
  [q] Quit
Choice [d/s/q]:
```

No manual `rm -rf` needed.

## Prerequisites

- Docker running (for llama-server and evalplus)
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

Verify:

```bash
source .venv/bin/activate
python -c "import evalplus; print('OK')"
```

## Usage

```bash
cd benchmarks/evalplus
source .venv/bin/activate
```

### Smoke test (recommended first run)

```bash
./benchmark.sh bench-glm-flash-q4
```

Runs GLM-4.7 Flash Q4_K_M (smallest model, fits in VRAM) through the complete pipeline. If it completes and produces results in `results/bench-glm-flash-q4/`, everything works.

### Full run (all local models)

```bash
./benchmark.sh --local
```

Runs all `bench-*` profiles from `models.conf` sequentially. Best started before leaving or overnight.

### Including Claude

```bash
./benchmark.sh --all                        # Local + Claude
./benchmark.sh bench-opus4.6-thinking       # Claude only (thinking mode)
```

Claude benchmarks use `claude -p` (Claude Code's non-interactive print mode). Requires Claude Code installed and a Max subscription.

### Report only

```bash
./benchmark.sh --report
```

Regenerates `results/REPORT.md` from existing evaluation results without re-running any models.

## Server vs client config

Configuration is split between two files:

- **`models.conf`** (project root) — **Server config.** Controls how `llama-server` starts: model file, context size, GPU layers, server flags. Used by `start.sh` and `benchmark.sh` to generate `.env`.
- **`bench-client.conf`** (this directory) — **Client config.** Settings sent by the benchmark client *to* the API: system prompts, reasoning levels, max tokens. The `[defaults]` section applies to all models; per-model sections can override.

### System prompts

When `bench-client.conf` specifies a `SYSTEM_PROMPT` for a model, `codegen-custom.py` is used instead of `evalplus.codegen` (because evalplus doesn't support system prompts). The system prompt is sent in the messages array of the API call.

### MAX_TOKENS

`MAX_TOKENS` in `[defaults]` controls the maximum response length for code generation. At startup, `benchmark.sh` automatically patches evalplus's `provider/base.py` with this value (evalplus hardcodes 768 by default and has no CLI flag). The same value is passed to `codegen-custom.py` via `--max-tokens`. If evalplus is reinstalled, the patch is re-applied on the next benchmark run.

### Example

```ini
[defaults]
MAX_TOKENS=4096

[bench-gpt-oss-120b]
SYSTEM_PROMPT=Reasoning: high
```

## Benchmark profiles

Profiles are defined in `models.conf` with a `bench-` prefix. They use the same model files and GPU layer splits as production, but with reduced context (16K) to save VRAM.

| Profile | Model | Notes |
|---------|-------|-------|
| `bench-glm-flash-q4` | GLM-4.7 Flash Q4_K_M | Smallest, fastest — good for smoke testing |
| `bench-glm-flash-q8` | GLM-4.7 Flash Q8_0 | Higher quality quant |
| `bench-gpt-oss-120b` | GPT-OSS 120B F16 | Large MoE, partial CPU offload |
| `bench-qwen3-coder-ud-q5` | Qwen3-Coder-Next UD-Q5_K_XL | Speed option |
| `bench-qwen3-coder-ud-q6` | Qwen3-Coder-Next UD-Q6_K_XL | Coding baseline |
| `bench-qwen3-coder-q6k` | Qwen3-Coder-Next Q6_K | Standard quant |
| `bench-opus4.6-thinking` | Claude Opus 4.6 | Extended thinking (via Claude Code) |
| `bench-opus4.6` | Claude Opus 4.6 | Without thinking (via Claude Code) |

View profiles: `./benchmark.sh --list`

## Output

```
results/
├── bench-glm-flash-q4/
│   ├── humaneval/
│   │   ├── <model>_temp_0.0.jsonl       # Cleaned solutions (164)
│   │   └── <model>_temp_0.0.raw.jsonl   # Original raw output (backup)
│   ├── codegen.log
│   └── evaluation.log
├── bench-qwen3-coder-ud-q6/
│   └── ...
└── REPORT.md                            # Comparison report (auto-generated)
```

## Troubleshooting

- **"Python venv not found"** — Run the one-time setup steps above.
- **"Container llama-server is already running"** — Stop it first: `docker compose -f ../../docker-compose.yml down`
- **Server fails to start** — Check that the model file exists. The script logs the last 30 lines from the container on failure.
- **Timeout waiting for health** — Large models (GPT-OSS 120B) can take several minutes to load. The default timeout is 10 minutes. If that's not enough, increase `HEALTH_TIMEOUT` in `codegen.sh`.
- **Evaluation produces unexpected results** — Check `evaluation.log` in the model's results directory.
- **Interrupted mid-run** — Safe to restart. The script stops the container on each model transition. Completed results are preserved. When re-running, you'll be asked whether to overwrite or skip existing results.

## Technical notes

- EvalPlus uses `--greedy` (temperature=0), which overrides server-side sampler settings via the API. The sampler defaults in `models.conf` are for production use, not benchmarks.
- The script reuses the same `docker-compose.yml` and `.env` mechanism as `start.sh`, so hardware-specific GPU splits are identical to production.
- Post-processing is applied uniformly to all models before evaluation. Models with clean output (e.g., Qwen3) pass through unchanged. Models with reasoning tags or markdown fences (e.g., GLM, GPT-OSS) get cleaned automatically.
- EvalPlus also supports MBPP+ (378 problems). To add it, change `--dataset humaneval` to `--dataset mbpp` in `codegen.sh`.
