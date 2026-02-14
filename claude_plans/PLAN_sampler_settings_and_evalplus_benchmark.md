# Plan: Sampler Settings + EvalPlus Coding Benchmark

## Context

The project has 7 model configs but no formal coding benchmarks and some models lack recommended sampler settings. This plan:
1. Updates `models.conf` with official sampler settings for production profiles
2. Adds **benchmark profiles** to `models.conf` — separate sections with reduced context (16K) optimized for EvalPlus runs
3. Creates a `benchmarks/evalplus/` directory with a benchmark runner that tests 6 models on HumanEval+ (164 Python problems) and produces comparable scores against proprietary models

**Why EvalPlus?** It works directly with llama.cpp's OpenAI-compatible API (`--backend openai --base-url http://localhost:8080/v1`), uses greedy decoding for reproducible leaderboard-comparable scores, and has a public leaderboard with Claude/GPT/Gemini scores for comparison. LiveCodeBench was considered but its OpenAI API support PR was closed — not viable without custom code.

**Models to benchmark (6):** glm-flash-q4, glm-flash, gpt-oss-120b, qwen3-coder-q5, qwen3-coder, qwen3-coder-q6k (skip glm-flash-exp)

**Context size for benchmarks:** EvalPlus uses max_new_tokens=768 (`provider/base.py:13`). Prompts are ~20 + ~500 tokens max. Total per request ≈ 1,300 tokens. 16K context (16384) is 12x headroom — guaranteed safe.

---

## Step 1: Update production sampler settings in `models.conf`

**File:** `models.conf`

Based on official model card recommendations and Unsloth docs:

### Qwen3-Coder-Next (3 sections: lines 89, 99, 110)
- Change `--min-p 0` to `--min-p 0.01` in EXTRA_ARGS
- Rationale: Unsloth explicitly recommends min_p=0.01 for llama.cpp (default 0.05 is too aggressive, 0 disables it entirely)
- Everything else stays the same (temp 1.0, top_p 0.95, top_k 40 already correct)

### GLM-4.7-Flash (2 sections: glm-flash-q4, glm-flash — skip glm-flash-exp)
- Add `--temp 1.0 --top-p 0.95 --min-p 0.01` to EXTRA_ARGS
- Source: Z.ai model card + Unsloth guide
- Before: `EXTRA_ARGS=--jinja -np 1`
- After: `EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01`

### GPT-OSS 120B (1 section)
- Add `--temp 1.0 --top-p 1.0` to EXTRA_ARGS (before the -ot regex)
- Source: OpenAI recommends temp=1.0, top_p=1.0
- Before: `EXTRA_ARGS=--jinja -np 1 -b 4096 -ub 4096 -ot ...`
- After: `EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 1.0 -b 4096 -ub 4096 -ot ...`

---

## Step 2: Add benchmark profiles to `models.conf`

Add new sections with a `bench-` prefix. These are identical to production profiles except:
- `CTX_SIZE=16384` (instead of 65K-256K) — saves VRAM, faster loading
- No sampler settings needed (EvalPlus overrides via API with temperature=0)
- Same MODEL, N_GPU_LAYERS, FIT, -ot layer splits as production

Example:
```ini
# --- Benchmark profiles (EvalPlus HumanEval+) ---
# Reduced context (16K) — same model/layer config as production.
# EvalPlus sends temperature=0 via API, overriding server defaults.

[bench-qwen3-coder]
NAME=Qwen3-Coder-Next UD-Q6_K_XL (benchmark)
MODEL=Qwen3-Coder-Next/UD-Q6_K_XL/Qwen3-Coder-Next-UD-Q6_K_XL-00001-of-00003.gguf
CTX_SIZE=16384
N_GPU_LAYERS=99
FIT=off
EXTRA_ARGS=--jinja -np 1 -b 2048 -ub 2048 --no-context-shift -ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU
```

6 benchmark sections total (one per model being tested).

The `run-benchmark.sh` script only selects `bench-*` profiles, so they don't clutter the normal `start.sh` menu.

---

## Step 3: Create benchmark directory structure

```
benchmarks/
└── evalplus/
    ├── run-benchmark.sh        # Orchestrator (main entry point)
    ├── generate-report.py      # Results → markdown comparison table
    ├── reference-scores.json   # Published proprietary model scores
    ├── README.md               # Setup & usage docs
    └── results/                # Output (gitignored)
        └── .gitkeep
```

Also update:
- `.gitignore` — add `benchmarks/evalplus/results/`

**EvalPlus source reference** stays at `benchmarks/evalplus-src/` (already cloned). Add to `.gitignore` as well.

---

## Step 4: Set up Python environment with uv

```bash
cd benchmarks/evalplus
uv venv
source .venv/bin/activate
uv pip install evalplus
```

Add `benchmarks/evalplus/.venv/` to `.gitignore`.

**Why uv:** Faster and lighter than conda for pure Python packages. EvalPlus has no compiled CUDA dependencies — standard pip packages only. uv handles dependency resolution well.

---

## Step 5: Create `benchmarks/evalplus/run-benchmark.sh`

**Reuses patterns from:** `start.sh` (INI parser lines 28-55, `get()` helper, `generate_env()` lines 113-131, `wait_for_health()` lines 183-222)

### Usage
```bash
./benchmarks/evalplus/run-benchmark.sh                        # All bench-* models
./benchmarks/evalplus/run-benchmark.sh bench-qwen3-coder      # Specific model
./benchmarks/evalplus/run-benchmark.sh --list                  # List benchmark profiles
./benchmarks/evalplus/run-benchmark.sh --report                # Generate comparison report
```

### Core logic (sequential per model, two-phase)

EvalPlus runs in two phases for safety: generation on the host, evaluation in Docker sandbox.

```
for each bench-* model_id:
  1. Check model file exists
  2. Generate .env from models.conf (same logic as start.sh)
  3. docker compose up -d
  4. Wait for health (600s timeout, non-interactive)
  5. PHASE 1 — Code generation (host, via uv .venv):
     evalplus.codegen --model "$name" --dataset humaneval \
         --base-url http://localhost:8080/v1 --backend openai \
         --greedy --root benchmarks/evalplus/results/$model_id
  6. docker compose down
  7. PHASE 2 — Code evaluation (Docker sandbox):
     docker run --rm -v $(pwd)/benchmarks/evalplus/results/$model_id:/app \
         ganler/evalplus:latest \
         evalplus.evaluate --dataset humaneval --samples /app/humaneval/*.jsonl
  8. Log result summary
```

### Key design decisions
- **Docker sandbox for code execution** — generated code runs inside `ganler/evalplus:latest`, not on the host. Safer since it executes arbitrary AI-generated Python.
- **Benchmark profiles only** — script filters for `bench-*` sections from models.conf
- **16K context** — verified safe: EvalPlus max total ≈ 1,300 tokens per request
- **Same -ot layer splits** — layer placement unaffected by context reduction, KV cache is separate
- **`continue` on failure** — if a model fails to start, skip it and proceed to the next
- **600s health timeout** — large models (GPT-OSS 120B) need time to load ~61GB from disk
- **Log everything** — each run saves to `results/$model_id/evalplus.log`
- **uv venv activation** — script activates `.venv` before calling evalplus (generation phase only)

### Expected runtime
~1 hour per model for HumanEval+ (164 problems). 6 models = ~6 hours total. Best run overnight.

---

## Step 6: Create `benchmarks/evalplus/reference-scores.json`

Published pass@1 scores for comparison (from model cards + EvalPlus leaderboard):

```json
{
  "metadata": {
    "source": "Model cards + EvalPlus leaderboard",
    "last_updated": "2026-02-14",
    "notes": "pass@1, greedy decoding"
  },
  "models": {
    "Qwen3-Coder-Next (FP16)": { "humaneval_plus": 94.1 },
    "GPT-OSS 120B (official)": { "humaneval_plus": 88.3 },
    "Claude Sonnet 4": { "humaneval_plus": null },
    "GPT-4o": { "humaneval_plus": null }
  }
}
```

Scores marked `null` will be filled from the EvalPlus leaderboard at implementation time. GLM-4.7-Flash has no published HumanEval score.

---

## Step 7: Create `benchmarks/evalplus/generate-report.py`

Small Python script that:
1. Reads `results/*/eval_results.json` (EvalPlus output)
2. Reads `reference-scores.json`
3. Outputs markdown table to `results/REPORT.md` and stdout

Output format:
```markdown
# Benchmark Results — 2026-02-14

## Local HumanEval+ Results (pass@1, greedy)
| Model                          | Quant      | HumanEval+ | vs FP16 ref |
|--------------------------------|------------|------------|-------------|
| Qwen3-Coder-Next UD-Q6_K_XL   | UD-Q6_K_XL | xx.x%      | -x.xpp      |
| ...                            | ...        | ...        | ...         |

## Comparison with Published Scores
| Model                          | HumanEval+ | Source             |
|--------------------------------|------------|--------------------|
| Qwen3-Coder-Next (FP16)       | 94.1%      | Model card         |
| Claude Sonnet 4                | xx.x%      | EvalPlus leaderboard |
| Local: qwen3-coder UD-Q6_K_XL | **xx.x%**  | **Local benchmark**  |
| ...                            | ...        | ...                |
```

---

## Step 8: Create `benchmarks/evalplus/README.md`

Document:
- Prerequisites (Python 3.10+, uv, Docker running)
- One-time setup (uv venv + uv pip install)
- Usage examples
- Expected runtime
- How to interpret results
- How to add MBPP+ later

---

## Step 9: Update project files

- `ROADMAP.md` — move "Formal benchmarks" to current/done, reference `benchmarks/`
- `.claude/agents/benchmark.md` — update to include EvalPlus benchmark context alongside existing Ollama comparison scope

---

## Verification

1. **Smoke test with fastest model:** Run bench-glm-flash-q4 + HumanEval+ first (~30 min)
   ```bash
   ./benchmarks/evalplus/run-benchmark.sh bench-glm-flash-q4
   ```
2. **Check results exist:** `ls benchmarks/evalplus/results/bench-glm-flash-q4/`
3. **Generate report:** `./benchmarks/evalplus/run-benchmark.sh --report`
4. **Sanity check:** Scores should be within ~5-10pp of published FP16 scores. If way off, likely a prompt template issue.
5. **Full run:** Once smoke test passes, run all 6 models overnight

---

## Findings

### GLM-4.7 Flash: empty solutions (2026-02-14)

The smoke test with `bench-glm-flash-q4` completed the full pipeline (codegen + Docker sandbox evaluation) but scored only **4.3% pass@1** — 7 out of 164 problems. Investigation revealed all solutions were empty strings.

**Root cause:** GLM-4.7 Flash is a reasoning model. It returns its chain-of-thought in the `reasoning_content` field and the actual answer in the `content` field of the API response. Two problems:

1. **EvalPlus reads only `message.content`**, not `reasoning_content` — so it sees an empty answer.
2. **The 768 max_tokens budget is consumed entirely by reasoning** (`finish_reason: length`), so the model never produces an actual answer in `content`.

Verified with a direct API call — the model generates a full correct solution inside `reasoning_content` but `content` is empty.

**Affects:** Both GLM Flash profiles (bench-glm-flash-q4 and bench-glm-flash). Does NOT affect Qwen3-Coder-Next (explicitly non-thinking model per model card: "This model supports only non-thinking mode") or GPT-OSS 120B (reasoning effort is configurable via system prompt, not a separate field).

**Possible fixes (to investigate later):**
- Increase max_tokens significantly so the model has budget left after reasoning for the actual answer
- Disable thinking mode if llama.cpp supports it for GLM (e.g. omit `--reasoning-parser`)
- Patch evalplus to concatenate `reasoning_content` + `content`, or extract code from the reasoning field
- Use a non-reasoning GLM variant if available

**Status:** Parked. Proceeding with Qwen3 and GPT-OSS benchmarks first.

---

## Files to create/modify

| File | Action |
|------|--------|
| `models.conf` | Edit: add production sampler settings + 6 benchmark profiles |
| `.gitignore` | Edit: add benchmark paths |
| `ROADMAP.md` | Edit: update status |
| `.claude/agents/benchmark.md` | Edit: add EvalPlus context |
| `benchmarks/evalplus/run-benchmark.sh` | Create |
| `benchmarks/evalplus/generate-report.py` | Create |
| `benchmarks/evalplus/reference-scores.json` | Create |
| `benchmarks/evalplus/README.md` | Create |
| `benchmarks/evalplus/results/.gitkeep` | Create |
