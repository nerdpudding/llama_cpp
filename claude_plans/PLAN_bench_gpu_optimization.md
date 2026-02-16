# Plan: Benchmark GPU Layer Optimization

**Status: BENCH PROFILES COMPLETE — production profile optimization remaining**

## Goal

Optimize bench profiles in `models.conf` for reduced context (16K → 10K).
Less KV cache = more VRAM = more layers on GPU = faster benchmark inference.

## Context from data

**Actual token usage in benchmarks (prompt + response):**

| Model | Max response | ~Max tokens | + prompt | Total |
|-------|-------------|-------------|----------|-------|
| GLM Q8 (incl. `<think>`) | 28,787 chars | ~7,200 | ~500 | ~7,700 |
| GPT-OSS (no reasoning level) | 7,837 chars | ~2,000 | ~500 | ~2,500 |
| GPT-OSS (Reasoning: high) | ~11,200 chars | ~2,800 | ~500 | ~3,300 |
| Qwen3 UD-Q6 | 6,051 chars | ~1,500 | ~500 | ~2,000 |

**Worst case overall:** GLM Q8 at HumanEval/10 = ~8,391 tokens (prompt + thinking + response).

**Target CTX_SIZE:** 10240 (was 16384)

**Why not 8K:** GLM Q8's worst case exceeds 8192. 10K gives safe margin for all
models including future additions.

## Pre-implementation: manual GPT-OSS test — DONE

Tested GPT-OSS with `Reasoning: high` via web UI. Both worst-case prompts stayed
well under 10K tokens (~1,200 and ~2,800 tokens respectively). Confirmed 10K is safe.

VRAM at 16K bench profile (before optimization):
- RTX 4090: 92%
- RTX 5070 Ti: 94%

## Changes made to models.conf

### Reasoning: why smaller batch sizes help

HumanEval prompts are ~400 tokens max. The `-b` (batch) and `-ub` (micro-batch)
flags control prompt processing chunk size. Larger values allocate bigger compute
buffers in VRAM — useful for long prompts but wasteful for short ones.

- Production profiles use `-b 2048 -ub 2048` (Qwen3) or `-b 4096 -ub 4096` (GPT-OSS)
  because prompts can be very long in interactive use.
- Benchmark profiles only need `-b 512 -ub 512` since HumanEval prompts are tiny.
  This saves several GB of compute buffer VRAM per GPU, which can be reallocated
  to model weight layers.

### Per-model changes

#### GLM Flash Q4 and Q8

- **CTX_SIZE:** 16384 → 10240
- **No other changes.** Both use `FIT=on`, which auto-calculates optimal layer
  placement. GLM is a dense model that fits entirely on GPU at these sizes.
- Q4 (~8 GB weights) easily fits on RTX 4090 alone.
- Q8 (~16 GB weights) fits on 4090 alone with ~8 GB headroom for KV + buffers.

#### GPT-OSS 120B (MoE, 36 layers)

- **CTX_SIZE:** 16384 → 10240
- **Batch size:** `-b 4096 -ub 4096` → `-b 512 -ub 512`
- **Layer split:** 12 CUDA0 + 4 CUDA1 → 12 CUDA0 + 5 CUDA1 (+1 layer on CUDA1)

**Reasoning:**
- Production at 64K: compute buffer on 5070 Ti is ~3.2 GB with `-ub 4096`.
- At 10K with `-ub 512`: compute buffer drops ~2.5 GB (to ~0.7 GB).
- Each GPT-OSS layer is ~1.7 GB. The freed ~2.5 GB is enough for 1 extra layer.
- CUDA0 stays at 12 layers (4090 was already at 96% in production, limited headroom).
- CUDA1 gains 1 layer: regex changes from `1[2-5]` (4 layers) to `1[2-6]` (5 layers).
- Total on GPU: 17/36 (was 16/36).

#### Qwen3-Coder-Next UD-Q5_K_XL (MoE, 48 layers)

- **CTX_SIZE:** 16384 → 10240
- **Batch size:** `-b 2048 -ub 2048` → `-b 512 -ub 512`
- **Layer split:** 15 CUDA0 + 7 CUDA1 → 18 CUDA0 + 8 CUDA1 (+4 layers total)

**Reasoning:**
- Qwen3 has DeltaNet on 75% of layers — only 12/48 layers have KV cache.
- At 256K production: KV = ~3,264 MiB. At 10K: ~128 MiB. Saves ~3,136 MiB.
- Combined with `-ub 512` (saves compute buffer), total ~4-5 GB freed per GPU.
- Each Qwen3 Q5 layer is ~1.2 GB.
- CUDA0: 15 → 18 layers (+3). Regex: `[0-9]|1[0-4]` → `[0-9]|1[0-7]`.
- CUDA1: 7 → 8 layers (+1). Regex: `1[5-9]|2[0-1]` → `1[8-9]|2[0-5]`.
- Total on GPU: 26/48 (was 22/48).

#### Qwen3-Coder-Next UD-Q6_K_XL and Q6_K (MoE, 48 layers)

- **CTX_SIZE:** 16384 → 10240
- **Batch size:** `-b 2048 -ub 2048` → `-b 512 -ub 512`
- **Layer split:** 13 CUDA0 + 6 CUDA1 → 16 CUDA0 + 7 CUDA1 (+4 layers total)

**Reasoning:**
- Same DeltaNet KV savings as Q5 variant.
- Each Qwen3 Q6 layer is ~1.3 GB (slightly larger than Q5).
- CUDA0: 13 → 16 layers (+3). Regex: `[0-9]|1[0-2]` → `[0-9]|1[0-5]`.
- CUDA1: 6 → 7 layers (+1). Regex: `1[3-8]` → `1[6-9]|2[0-2]`.
- Total on GPU: 23/48 (was 19/48).
- Both UD-Q6_K_XL and standard Q6_K use the same split (similar model sizes).

### Summary table

| Model | Production layers | Bench layers (old) | Bench layers (new) | Change |
|-------|------------------|-------------------|-------------------|--------|
| GLM Q4/Q8 | all (FIT=on) | all (FIT=on) | all (FIT=on) | — |
| GPT-OSS 120B | 16/36 | 16/36 | 17/36 | +1 |
| Qwen3 Q5 | 22/48 | 22/48 | 26/48 | +4 |
| Qwen3 Q6/Q6K | 19/48 | 19/48 | 23/48 | +4 |

### No sampler args in bench profiles

Benchmark profiles intentionally omit temperature/top-p/min-p sampler arguments.
evalplus sends `temperature=0` via API (greedy decoding), which overrides any
server-side defaults. Adding redundant sampler args would just add noise.

## Completed steps

### 1. OOM testing — DONE

All optimized bench profiles tested via `./start.sh`:
- [x] `bench-glm-flash-q4` — passed
- [x] `bench-glm-flash-q8` — passed
- [x] `bench-gpt-oss-120b` — passed
- [x] `bench-qwen3-coder-ud-q5` — passed
- [x] `bench-qwen3-coder-ud-q6` — passed
- [x] `bench-qwen3-coder-q6k` — passed

Actual tested splits documented in `docs/bench-test-results.md`.

### 2. Bench profiles in start.sh — DONE

start.sh reads all sections from models.conf, bench profiles are selectable.

### 3. Full benchmark run — DONE

Full EvalPlus HumanEval+ benchmark completed 2026-02-15. Results in
`benchmarks/evalplus/results/REPORT.md`. All 5 local models + 2 Claude
configurations benchmarked.

## Order of execution

1. ~~Manual GPT-OSS test → confirm 10K is safe~~ — DONE
2. ~~Update models.conf bench profiles~~ — DONE
3. ~~OOM test per model via start.sh~~ — DONE
4. ~~Add bench profiles to start.sh menu~~ — DONE
5. ~~Full benchmark run with optimized profiles~~ — DONE (see REPORT.md)
6. ~~Compare speeds and update documentation~~ — DONE

## Remaining: Production profile optimization

Bench profiles are fully optimized and benchmarked. Production profiles still
need review and optimization for the following models:

- [ ] GLM-4.7 Flash Q4_K_M — review if current FIT=on is optimal
- [ ] GLM-4.7 Flash Q8_0 — review layer split, may benefit from explicit -ot
- [ ] Qwen3-Coder-Next UD-Q5_K_XL — check if current 15+7 split can be improved
- [ ] Qwen3-Coder-Next UD-Q6_K_XL — check if current 13+6 split can be improved
- [ ] Qwen3-Coder-Next Q6_K — check if current split can be improved

**Exception:** GPT-OSS 120B production profile is already optimized (12+4=16/36,
64K context). No changes needed.
