# Plan: Sampler Settings + EvalPlus Coding Benchmark

## Context

The project has 7 model configs but no formal coding benchmarks and some models lack recommended sampler settings. This plan:
1. Updates `models.conf` with official sampler settings for all model families
2. Creates a `benchmarks/` directory with an EvalPlus-based benchmark runner that tests 6 models on HumanEval+ (164 Python problems) and produces comparable scores against proprietary models

**Why EvalPlus?** It works directly with llama.cpp's OpenAI-compatible API (`--backend openai --base-url http://localhost:8080/v1`), uses greedy decoding for reproducible leaderboard-comparable scores, and has a public leaderboard with Claude/GPT/Gemini scores for comparison. LiveCodeBench was considered but its OpenAI API support PR was closed — not viable without custom code.

**Models to benchmark (6):** glm-flash-q4, glm-flash, gpt-oss-120b, qwen3-coder-q5, qwen3-coder, qwen3-coder-q6k (skip glm-flash-exp)

---

## Step 1: Update sampler settings in `models.conf`

**File:** `/home/rvanpolen/vibe_claude_kilo_cli_exp/llama_cpp/models.conf`

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

**Note on benchmarks vs production:** These are production sampler settings. For benchmarks, EvalPlus sends `temperature=0` in the API request body (via `--greedy`), which overrides server-side defaults. No special benchmark server config needed.

---

## Step 2: Create benchmark directory structure

```
benchmarks/
├── run-benchmark.sh        # Orchestrator (main entry point)
├── generate-report.py      # Results → markdown comparison table
├── reference-scores.json   # Published proprietary model scores
├── requirements.txt        # evalplus
├── README.md               # Setup & usage docs
└── results/                # Output (gitignored)
    └── .gitkeep
```

Also update:
- `.gitignore` — add `benchmarks/results/` and `benchmarks/venv/`

---

## Step 3: Create `benchmarks/requirements.txt`

```
evalplus
```

Setup (documented in README, run once):
```bash
cd benchmarks && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

**Why venv, not Docker:** Docker complexity is already in llama-server. The benchmark client is just a Python script hitting localhost:8080. EvalPlus uses Docker internally for safe code execution during evaluation.

---

## Step 4: Create `benchmarks/run-benchmark.sh`

**Reuses patterns from:** `start.sh` (INI parser lines 28-55, `get()` helper, `generate_env()` lines 113-131, `wait_for_health()` lines 183-222)

### Usage
```bash
./benchmarks/run-benchmark.sh                        # All 6 models
./benchmarks/run-benchmark.sh qwen3-coder glm-flash  # Specific models
./benchmarks/run-benchmark.sh --list                  # List available models
./benchmarks/run-benchmark.sh --report                # Generate report from existing results
```

### Core logic (sequential per model)
```
for each model_id:
  1. Check model file exists
  2. Generate .env from models.conf (same as start.sh)
  3. docker compose up -d
  4. Wait for health (600s timeout, non-interactive)
  5. Run: evalplus.evaluate --model "$name" --dataset humaneval \
         --base-url http://localhost:8080/v1 --backend openai \
         --greedy --root benchmarks/results/$model_id
  6. docker compose down
  7. Log result summary
```

### Key design decisions
- **Use production models.conf settings as-is** — same layer splits, same VRAM. Benchmark what we actually run.
- **No context size override** — HumanEval prompts are short but changing ctx would invalidate -ot layer splits
- **`continue` on failure** — if a model fails to start, skip it and proceed to the next
- **600s health timeout** — large models (GPT-OSS 120B) need time to load ~61GB from disk
- **Log everything** — each run saves to `results/$model_id/evalplus.log`
- **Skip glm-flash-exp** — hardcoded exclusion list (or just don't pass it)
- **Venv activation** — script activates benchmarks/venv before calling evalplus

### Expected runtime
~1 hour per model for HumanEval+ (164 problems). 6 models = ~6 hours total. Best run overnight.

---

## Step 5: Create `benchmarks/reference-scores.json`

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

Scores marked `null` will be filled from the EvalPlus leaderboard at implementation time (it loads data dynamically, couldn't scrape). GLM-4.7-Flash has no published HumanEval score.

---

## Step 6: Create `benchmarks/generate-report.py`

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

## Step 7: Create `benchmarks/README.md`

Document:
- Prerequisites (Python 3.10+, Docker running)
- One-time setup (venv + pip install)
- Usage examples
- Expected runtime
- How to interpret results
- How to add MBPP+ later

---

## Step 8: Update project files

- `ROADMAP.md` — move "Formal benchmarks" to current/done, reference `benchmarks/`
- `.claude/agents/benchmark.md` — update to include EvalPlus benchmark context alongside existing Ollama comparison scope

---

## Verification

1. **Smoke test with fastest model:** Run glm-flash-q4 + HumanEval+ first (~30 min)
   ```bash
   ./benchmarks/run-benchmark.sh glm-flash-q4
   ```
2. **Check results exist:** `ls benchmarks/results/glm-flash-q4/`
3. **Generate report:** `./benchmarks/run-benchmark.sh --report`
4. **Sanity check:** Scores should be within ~5-10pp of published FP16 scores. If way off, likely a prompt template issue.
5. **Full run:** Once smoke test passes, run all 6 models overnight

---

## Files to create/modify

| File | Action |
|------|--------|
| `models.conf` | Edit: add sampler settings |
| `.gitignore` | Edit: add benchmark paths |
| `ROADMAP.md` | Edit: update status |
| `.claude/agents/benchmark.md` | Edit: add EvalPlus context |
| `benchmarks/run-benchmark.sh` | Create |
| `benchmarks/generate-report.py` | Create |
| `benchmarks/reference-scores.json` | Create |
| `benchmarks/requirements.txt` | Create |
| `benchmarks/README.md` | Create |
| `benchmarks/results/.gitkeep` | Create |
