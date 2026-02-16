# Production Profile Optimization — Advice and Test Plan

**Created:** 2026-02-16
**Status:** READY FOR TESTING
**Author:** gpu-optimizer agent

## Overview

This document analyzes the 4 production profiles that are candidates for optimization,
proposes aggressive and moderate improvements for each, and provides empty result
sections for the user to fill in after testing.

**Scope:** GLM-4.7 Flash (Q4, Q8, Q8-exp) and Qwen3-Coder-Next UD-Q5_K_XL.
GPT-OSS 120B is excluded — the existing plan already notes it as optimized
(11+3=14/36 at 128K, -b 2048).

**Method:** Compare bench profile VRAM data (10K context, -b 512) against production
requirements (128K/256K context, -b 2048) to estimate how many layers can fit on GPU.

### Hardware reference

| Device | Total VRAM | Usable VRAM | Role |
|--------|-----------|-------------|------|
| CUDA0 (RTX 4090) | 24,576 MiB | ~24,000 MiB | Primary compute, nothing else running |
| CUDA1 (RTX 5070 Ti) | 16,384 MiB | ~12,800 MiB | Secondary, display/OS takes ~3,500 MiB |
| CPU | 64 GB DDR4 | ~60 GB | Slowest, large capacity |

---

## 1. GLM-4.7 Flash Q4_K_M

### Current production profile (`[glm-flash-q4]`)

```
CTX_SIZE=131072
N_GPU_LAYERS=99
FIT=on
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01
```

### Architecture

- MoE: 30B-A3B, 47 layers (1 dense lead + 46 MoE)
- 64 experts per layer, 4 active + 1 shared
- MLA (Multi-head Latent Attention): n_head_kv=1, V derived from K (no separate V cache)
- File size: 18 GB (Q4_K_M)
- Per-layer weight: ~382 MiB (~18 GB / 47 layers)
- Source: model card + GGUF metadata (lessons_learned.md)

### Analysis

**Bench profile data (10K context, Strategy A — all on 4090):**
- Model buffer: 17,285 MiB on CUDA0
- Total CUDA0: 18,361 MiB (74% of 24.6 GB) = ~6,200 MiB headroom
- Graph splits: 2 (optimal)
- Speed: ~140 t/s

**VRAM estimate at 128K production:**
- Model weights: ~17,285 MiB (unchanged)
- KV cache at 128K (MLA with q8_0): ~3,500 MiB (extrapolated from 3.1 GiB at 112K)
- Compute buffer (default batch, ~2048): ~1,500-2,000 MiB (larger than bench's ~500 MiB)
- CUDA overhead: ~500 MiB
- **Total estimate: ~22,785-23,285 MiB on CUDA0 alone**

**Key insight:** At 128K, Q4 likely still fits on the 4090 alone (~23 GB of ~24 GB).
The current `FIT=on` approach auto-distributes across both GPUs unnecessarily.
This was already identified as a problem in the bench profile (see models.conf comment
about "old broken config"). The same issue likely applies to production.

Using explicit `--split-mode none --main-gpu 0` (Strategy A) would keep everything on
the 4090, avoiding inter-GPU transfers and minimizing graph splits (2 instead of
potentially 20+). This should match or improve the ~140 t/s bench speed proportionally.

**Risk:** at full 128K context with a long prompt being processed, the compute buffer
may spike. The default batch size without explicit `-b` is 2048, which at 128K context
may allocate a larger compute buffer than estimated. If OOM occurs, reducing to
`-b 1024 -ub 1024` should recover ~500-800 MiB.

### Suggestion A (Aggressive): Single GPU, full context

Force everything onto the 4090. No batch size reduction. Target ~95%+ utilization.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01 --split-mode none --main-gpu 0
```

**Expected:** ~23 GB on CUDA0 (95%), CUDA1 idle. 2 graph splits. Speed close to bench.
If the compute buffer at 128K is larger than estimated, this may OOM.

### Suggestion B (Moderate): Single GPU with batch limit

Same as aggressive but cap the batch size to control compute buffer VRAM.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01 -b 1024 -ub 1024 --split-mode none --main-gpu 0
```

**Expected:** ~22.5 GB on CUDA0 (92%), CUDA1 idle. 2 graph splits. Speed similar to
aggressive — batch size reduction has negligible impact on token generation speed (only
affects prompt ingestion of very long prompts slightly).

### Test results

#### Suggestion A — Aggressive (single GPU, no batch limit)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

#### Suggestion B — Moderate (single GPU, -b 1024)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

---

## 2. GLM-4.7 Flash Q8_0 (and Q8_0 experimental)

### Current production profile (`[glm-flash]` and `[glm-flash-exp]`)

```
CTX_SIZE=131072
N_GPU_LAYERS=99
FIT=on
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01
```

The experimental variant (`[glm-flash-exp]`) uses a different model file but the same
settings (minus sampler args). Both are 30 GB Q8_0 files. Optimization applies to both.

### Architecture

Same as Q4 above, but Q8_0 quantization:
- File size: 30 GB
- Per-layer weight: ~628 MiB (~30 GB / 47 layers, measured in bench testing)
- All 47 layers fit on combined GPU VRAM at bench (10K): 35 CUDA0 + 12 CUDA1

### Analysis

**Bench profile data (10K context, -b 512, Strategy C — both GPUs, no exps=CPU):**
- Split: 35 CUDA0 + 12 CUDA1 = 47/47 (all layers on GPU)
- CUDA0: 93% (~22.9 GB), CUDA1: 65% (~10.6 GB)
- Graph splits: 33
- Speed: ~105 t/s
- Total GPU memory: ~33.5 GB for model + KV + compute at 10K

**VRAM scaling from 10K to 128K:**
- KV cache increase: MLA with q8_0 at 128K ~3,500 MiB vs ~275 MiB at 10K = +3,225 MiB
- Compute buffer increase (no explicit -b in production = default 2048 vs bench 512):
  ~1,500-2,500 MiB additional
- Total additional VRAM needed: ~4,725-5,725 MiB across both GPUs

**Available headroom at bench:**
- CUDA0: ~24,000 - 22,900 = 1,100 MiB headroom
- CUDA1: ~12,800 - 10,600 = 2,200 MiB headroom
- Total headroom: ~3,300 MiB

**Problem:** The additional ~4.7-5.7 GB needed for production exceeds the ~3.3 GB
headroom at bench. This means NOT all 47 layers can fit on GPU at 128K. Some layers
need to either go to CPU or the context must be reduced.

**FIT=on current behavior:** FIT likely auto-distributes fewer layers, potentially
keeping all on GPU but reducing context, or splitting suboptimally across GPUs. Without
explicit `-ot`, FIT does not know to prioritize CUDA0 or keep experts on the faster GPU.

**Strategy options:**
1. Keep all 47 layers on GPU with `-b 1024` to reduce compute buffer: saves ~1-2 GB,
   might barely fit but risky (~95%+ on CUDA0).
2. Offload a few layers to CPU: e.g., 33+12=45 layers on GPU, 2 on CPU. Since GLM is
   MoE, we could use `exps=CPU` for the overflow layers.
3. Keep all on GPU with reduced batch size. Since MLA makes KV cache compact, this
   model might fit even at 128K if we control compute buffers.

**Estimated per-GPU breakdown at 128K with all 47 layers (Strategy C, -b 1024):**
- CUDA0 (35 layers): ~22,000 MiB model + ~2,400 MiB KV/compute/overhead = ~24,400 MiB
  (exceeds 24,000 MiB usable — likely OOM)
- The KV cache distribution depends on FIT/split behavior. With -ot, KV follows the
  layers, so 35/47 of KV on CUDA0.

**Revised estimate with fewer CUDA0 layers:**
- Per-layer weight: 628 MiB. Removing 2 layers from CUDA0 saves ~1,256 MiB.
- 33 CUDA0 + 12 CUDA1 = 45/47 layers, 2 layers on CPU.
  - CUDA0: 33 * 628 = 20,724 MiB model + ~2,100 MiB KV/compute/overhead = ~22,824 MiB (93%)
  - CUDA1: 12 * 628 = 7,536 MiB model + ~1,400 MiB KV/compute/overhead = ~8,936 MiB (70%)

- 33 CUDA0 + 14 CUDA1 = 47/47 layers, none on CPU.
  - CUDA0: 33 * 628 = 20,724 MiB + ~2,100 MiB = ~22,824 MiB (93%)
  - CUDA1: 14 * 628 = 8,792 MiB + ~1,400 MiB = ~10,192 MiB (80%)
  - This might work! Moving 2 layers from CUDA0 to CUDA1 keeps everything on GPU.

**Best approach:** Explicit `-ot` placement (Strategy C) with a split that accounts for
the larger KV + compute at 128K. The bench sweet spot was 35+12 at 10K. For 128K, we
need to shift ~2-4 layers from CUDA0 to CUDA1 to make room for KV/compute growth.

**Graph split consideration:** The bench tests showed 35+12 = 33 splits and 37+10 = 53
splits. Changing the split point by 2 layers can dramatically affect graph splits for
this MoE model. We need to test a few split points.

### Suggestion A (Aggressive): 33+14=47/47, all on GPU, -b 1024

All layers on GPU. Shift 2 layers from CUDA0 to CUDA1 vs bench. Reduce batch to control
compute buffer.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01 -b 1024 -ub 1024 -ot blk\.([0-9]|[12][0-9]|3[0-2])\.=CUDA0,blk\.(3[3-9]|4[0-6])\.=CUDA1
```

**Regex breakdown:**
- `blk\.([0-9]|[12][0-9]|3[0-2])\.=CUDA0` = layers 0-32 (33 layers) on 4090
- `blk\.(3[3-9]|4[0-6])\.=CUDA1` = layers 33-46 (14 layers) on 5070 Ti

**Expected:** CUDA0 ~93% (~22.8 GB), CUDA1 ~80% (~10.2 GB). All experts on GPU.
Graph splits unknown — test required. Speed potentially close to bench ~105 t/s
if splits are favorable.

**Risk:** CUDA0 may be tight. KV cache distribution at 128K could push it over.
If OOM, reduce CUDA0 by 1 (32+15) or increase CUDA1 range.

### Suggestion B (Moderate): 31+14=45/47, 2 layers CPU, -b 1024

Safer: 2 fewer layers on CUDA0 than aggressive, with those 2 overflowing to CPU.
Uses `exps=CPU` for the 2 CPU layers — attention stays on GPU via -ngl 99.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01 -b 1024 -ub 1024 -ot blk\.([0-9]|[12][0-9]|30)\.=CUDA0,blk\.(3[1-9]|4[0-4])\.=CUDA1,exps=CPU
```

**Regex breakdown:**
- `blk\.([0-9]|[12][0-9]|30)\.=CUDA0` = layers 0-30 (31 layers) on 4090
- `blk\.(3[1-9]|4[0-4])\.=CUDA1` = layers 31-44 (14 layers) on 5070 Ti
- `exps=CPU` = layers 45-46 expert weights on CPU (attention still on GPU)

**Expected:** CUDA0 ~84% (~20.5 GB), CUDA1 ~80% (~10.2 GB). Comfortable headroom.
The 2 CPU layers will have minimal impact — experts on CPU for only 2/47 layers means
~4% of expert evaluations go through PCIe. Speed loss vs all-GPU: ~2-5%.

**Alternative to test:** If suggestion A works, try 33+14 without -b limit:

```
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 0.95 --min-p 0.01 -ot blk\.([0-9]|[12][0-9]|3[0-2])\.=CUDA0,blk\.(3[3-9]|4[0-6])\.=CUDA1
```

### Test results

#### Suggestion A — Aggressive (33+14, all GPU, -b 1024)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

#### Suggestion B — Moderate (31+14, 2 CPU layers, -b 1024)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

#### Optional: Suggestion A without batch limit (33+14, all GPU, default batch)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

---

## 3. GPT-OSS 120B F16

### Current production profile (`[gpt-oss-120b]`)

```
CTX_SIZE=131072
N_GPU_LAYERS=99
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 1.0 -b 2048 -ub 2048 -ot blk\.([0-9]|10)\.=CUDA0,blk\.(1[1-3])\.=CUDA1,exps=CPU
```

Split: 11 CUDA0 + 3 CUDA1 = 14/36 layers on GPU.

### Architecture

- MoE: 116.8B total, 5.1B active per token
- 36 layers (18 standard + 18 SWA — sliding window attention)
- 128 experts per layer, 4 active
- MXFP4 native, stored as F16: 61 GB file
- Per-layer weight: ~1.7 GB
- Source: model card (models/documentation/README_modelcard_gpt-oss-120b-GGUF.md)

### Analysis

**Bench profile data (10K, -b 512, Strategy D — GPU + CPU offload):**
- Split: 13 CUDA0 + 5 CUDA1 = 18/36
- CUDA0: 96%, CUDA1: 83%
- Speed: ~22 t/s
- 13+6 OOMed on CUDA1 (15.4/16.3 GB after load)

**VRAM scaling from 10K to 128K:**
- KV cache increase: significant for GPT-OSS (full KV, not MLA)
- Compute buffer increase: -b 2048 vs -b 512
- Production already works at 11+3=14/36. Bench adds 4 more layers (+2 CUDA0, +2 CUDA1).

**Existing plan verdict:** "GPT-OSS 120B production profile is already optimized.
No changes needed." This is because:
- At 128K with -b 2048, the KV cache is very large (~8-10 GB for 36 layers full attention)
- CUDA0 at bench was already 96% with only 13 layers
- Production has 11 layers — 2 fewer, matching the KV/compute growth
- CUDA1 at bench was 83% with 5 layers; production has 3 layers

**Can we squeeze 1 more layer?** The gap from bench (13+5=18) to production (11+3=14) is
4 layers. The KV growth from 10K to 128K is ~12.8x. For a model with full KV on all 36
layers, this is substantial. Let's estimate:

- KV cache at 10K (q8_0, 36 layers): rough estimate ~640 MiB
- KV cache at 128K: ~8,192 MiB (~8 GB)
- Difference: ~7,552 MiB
- Compute buffer -b 2048 vs -b 512: ~1,500-2,000 MiB more
- Total additional: ~9-10 GB distributed across both GPUs

At bench, total GPU usage was ~23.6 + 13.3 = ~36.9 GB for 18 layers.
At production, removing 4 layers saves ~6.8 GB, and the extra ~9-10 GB for KV/compute
brings the total back to ~40 GB, distributed as ~23 GB CUDA0 + ~12 GB CUDA1.

**Trying 12+3=15/36 (one more on CUDA0):**
- One extra layer on CUDA0 = +1.7 GB
- CUDA0 would go from ~23 GB to ~24.7 GB — this exceeds 24 GB usable. OOM likely.

**Trying 11+4=15/36 (one more on CUDA1):**
- One extra layer on CUDA1 = +1.7 GB
- CUDA1 at production is likely ~10-11 GB. Adding 1.7 GB = ~12-13 GB.
- CUDA1 usable is ~12.8 GB. This is borderline.

**Conclusion:** This model is genuinely at its limit. The existing profile is well-tuned.
However, reducing batch size to -b 1024 might free enough for +1 layer on CUDA1.

### Suggestion A (Aggressive): 11+4=15/36, -b 1024

One more layer on CUDA1, batch size halved to free compute buffer space.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 1.0 -b 1024 -ub 1024 -ot blk\.([0-9]|10)\.=CUDA0,blk\.(1[1-4])\.=CUDA1,exps=CPU
```

**Regex change:** `blk\.(1[1-3])\.` -> `blk\.(1[1-4])\.` (adds layer 14 to CUDA1)

**Expected:** CUDA1 ~95% (~12.2 GB). Risky — may OOM during inference at high context.
-b 1024 saves ~500-1,000 MiB of compute buffer on CUDA1, which should be enough for
the extra layer (~1.7 GB minus the savings).

### Suggestion B (Moderate): 11+3=14/36, -b 1024 (keep layers, reduce batch)

Keep the same layer split but reduce batch size. This saves VRAM headroom and may
slightly speed up inference by reducing memory pressure.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 --temp 1.0 --top-p 1.0 -b 1024 -ub 1024 -ot blk\.([0-9]|10)\.=CUDA0,blk\.(1[1-3])\.=CUDA1,exps=CPU
```

**Expected:** Same layers, more headroom. Useful as a baseline to measure what
-b 1024 does vs the current -b 2048. If VRAM savings are significant, that
data helps decide whether suggestion A is feasible.

### Test results

#### Suggestion A — Aggressive (11+4, -b 1024)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

#### Suggestion B — Moderate (11+3, -b 1024, same layers)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

---

## 4. Qwen3-Coder-Next UD-Q5_K_XL

### Current production profile (`[qwen3-coder-q5]`)

```
CTX_SIZE=262144
N_GPU_LAYERS=99
FIT=off
EXTRA_ARGS=--jinja -np 1 -b 2048 -ub 2048 --no-context-shift --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0.01 -ot blk\.([0-9]|1[0-4])\.=CUDA0,blk\.(1[5-9]|2[0-1])\.=CUDA1,exps=CPU
```

Split: 15 CUDA0 + 7 CUDA1 = 22/48 layers on GPU. Reported speed: 25.8 t/s.

### Architecture

- MoE: 80B total, 3B active, 48 layers
- 512 experts per layer, 10 active + 1 shared
- Hybrid: 75% Gated DeltaNet (linear attention, NO KV cache) + 25% Gated Attention
- Layout: 12 * (3 * (DeltaNet->MoE) -> 1 * (Attention->MoE)) = 36 DeltaNet + 12 Attention
- Only 12/48 layers have KV cache (layers 3,7,11,15,19,23,27,31,35,39,43,47)
- Hidden dim: 2048, attention: 16 Q heads, 2 KV heads, head dim 256
- File size: ~54 GB total (5.7 MiB + 47 GB + 6.7 GB across 3 shards)
- Per-layer weight: ~1.1 GB (experts + attention + routing)
- Source: model card (Qwen3-Coder-Next)

### Analysis

**Bench profile data (10K, -b 512, Strategy D):**
- Split: 19 CUDA0 + 9 CUDA1 = 28/48
- CUDA0: 93% (~22.3 GB), CUDA1: 89% (~14.2 GB)
- Graph splits: 136
- Speed: ~30 t/s

**VRAM scaling from 10K to 256K:**
- KV cache at 256K (q8_0, only 12 layers, 2 KV heads, head dim 256):
  - Per attention layer: 2 * 2 * 256 * 256K * 1 byte (q8_0) = ~262 MiB
  - 12 layers: ~3,146 MiB (~3.1 GB)
- KV cache at 10K: ~128 MiB
- KV increase: ~3,018 MiB
- Compute buffer (b 2048 vs b 512): ~1,500-2,500 MiB per GPU
- Total additional per GPU: varies by layer distribution, but ~2-3 GB per GPU

**Bench headroom:**
- CUDA0: 24,000 - 22,300 = ~1,700 MiB
- CUDA1: 12,800 - 14,200 = NEGATIVE (-1,400 MiB)

Wait — CUDA1 at 89% of 16,384 MiB = ~14,582 MiB. But usable is ~12,800 MiB.
This means CUDA1 was using ~14.6 GB, which is possible because nvidia-smi reports
total VRAM usage (including OS), not just the model's share. The 89% figure is
from bench-test-results which reports percentage of total 16 GB, not usable.

Let me recalculate with total VRAM:
- CUDA0: 93% of 24,576 = 22,856 MiB. Headroom to 24,000 = ~1,144 MiB
- CUDA1: 89% of 16,384 = 14,582 MiB. Headroom to 16,384 = ~1,802 MiB total,
  but ~3,500 MiB is OS/display, so real headroom = ~1,802 MiB

**From bench (28 layers) to production (22 layers): 6 fewer layers = ~6.6 GB freed.**
**Additional VRAM for 256K: ~3 GB KV + ~3-5 GB compute buffers = ~6-8 GB.**

The numbers roughly balance: 6 fewer layers free ~6.6 GB, and 256K context consumes
~6-8 GB. The production split is well-tuned.

**Can we add 1-2 more layers?** The bench profile went from 22 (production) to 28
(bench), gaining 6 layers by going from 256K to 10K and -b 2048 to -b 512.
If we reduce production batch size from 2048 to 1024, we save ~1-2 GB per GPU.
That is enough for roughly 1 additional layer per GPU (~1.1 GB each).

**Trying 16+8=24/48 (vs current 15+7=22/48):**
- +1 layer CUDA0 = +1.1 GB. CUDA0 already tight at production.
- +1 layer CUDA1 = +1.1 GB. CUDA1 already tight.
- Needs -b 1024 to free the room.

**Trying 17+8=25/48 with -b 1024:**
- +2 CUDA0, +1 CUDA1 vs current.
- CUDA0 adds ~2.2 GB of weights, saves ~1-2 GB from -b 1024. Net: +0.2 to +1.2 GB. Risky.

### Suggestion A (Aggressive): 17+8=25/48, -b 1024

Push 2 more layers onto CUDA0 and 1 more onto CUDA1 vs current production.
Reduce batch size to compensate.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 -b 1024 -ub 1024 --no-context-shift --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0.01 -ot blk\.([0-9]|1[0-6])\.=CUDA0,blk\.(1[7-9]|2[0-4])\.=CUDA1,exps=CPU
```

**Regex breakdown:**
- `blk\.([0-9]|1[0-6])\.=CUDA0` = layers 0-16 (17 layers) on 4090
- `blk\.(1[7-9]|2[0-4])\.=CUDA1` = layers 17-24 (8 layers) on 5070 Ti
- `exps=CPU` = remaining layers 25-47 expert weights on CPU

**Expected:** CUDA0 ~95%, CUDA1 ~93%. 3 more layers on GPU means 3 fewer layers doing
PCIe round-trips for expert weights. Speed increase: ~1-2 t/s over current 25.8 t/s.

**Risk:** CUDA0 may OOM at full 256K context with a very long prompt. The compute buffer
for 256K context is large even at -b 1024.

### Suggestion B (Moderate): 16+8=24/48, -b 1024

Push 1 more layer onto each GPU. More conservative than aggressive.

```
FIT=off
EXTRA_ARGS=--jinja -np 1 -b 1024 -ub 1024 --no-context-shift --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0.01 -ot blk\.([0-9]|1[0-5])\.=CUDA0,blk\.(1[6-9]|2[0-3])\.=CUDA1,exps=CPU
```

**Regex breakdown:**
- `blk\.([0-9]|1[0-5])\.=CUDA0` = layers 0-15 (16 layers) on 4090
- `blk\.(1[6-9]|2[0-3])\.=CUDA1` = layers 16-23 (8 layers) on 5070 Ti
- `exps=CPU` = remaining layers 24-47 expert weights on CPU

**Expected:** CUDA0 ~90%, CUDA1 ~90%. 2 more layers on GPU. Safer margin for
256K context spikes.

### Test results

#### Suggestion A — Aggressive (17+8=25/48, -b 1024)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

#### Suggestion B — Moderate (16+8=24/48, -b 1024)

| Metric | Value |
|--------|-------|
| CUDA0 VRAM (MiB / %) | |
| CUDA1 VRAM (MiB / %) | |
| Graph splits (bs=1) | |
| Speed (t/s) | |
| OOM? | |
| Notes | |

---

## Testing procedure

For each suggestion:

1. **Start the server** with the suggested EXTRA_ARGS by creating a temporary profile in
   models.conf or editing the existing one (comment out the original first).

2. **Check startup logs** for:
   - `load_tensors: CUDA0 model buffer size = X MiB` (model weights per GPU)
   - `load_tensors: CUDA1 model buffer size = X MiB`
   - `load_tensors: CPU model buffer size = X MiB`
   - `sched_reserve: graph splits = N` (lower is better)
   - Any OOM errors during loading

3. **Check nvidia-smi** after startup for VRAM usage per GPU.

4. **Send a test prompt** (something that generates 50+ tokens) and measure speed (t/s)
   from the server output or dashboard.

5. **Test with a long prompt** (paste a large document, ~2K+ tokens) to exercise the
   batch processing and verify no OOM at higher compute buffer usage.

6. **Record results** in the tables above.

### Priority order

Test in this order (most impactful first):

1. **GLM Q4 — Suggestion B** (moderate, safest change, likely big improvement from
   FIT=on to single GPU)
2. **GLM Q4 — Suggestion A** (if B works, try without batch limit)
3. **GLM Q8 — Suggestion A** (aggressive, tests if all 47 layers fit at 128K)
4. **GLM Q8 — Suggestion B** (fallback if A fails)
5. **Qwen3 Q5 — Suggestion B** (moderate, +2 layers)
6. **Qwen3 Q5 — Suggestion A** (aggressive, +3 layers)
7. **GPT-OSS — Suggestion B** (baseline, measures -b 1024 impact)
8. **GPT-OSS — Suggestion A** (aggressive, +1 layer)

### Expected outcomes

| Model | Current speed | Expected speed (best case) | Improvement |
|-------|-------------|--------------------------|-------------|
| GLM Q4 | unknown (FIT=on) | ~130+ t/s (single GPU, fewer splits) | Significant |
| GLM Q8 | unknown (FIT=on) | ~95-105 t/s (explicit split) | Moderate-to-significant |
| GPT-OSS | ~18-20 t/s | ~19-21 t/s (+1 layer) | Marginal |
| Qwen3 Q5 | 25.8 t/s | ~27-28 t/s (+2-3 layers) | Small |

The biggest win is likely GLM Q4, where switching from FIT=on (auto-distribute across
2 GPUs) to Strategy A (single 4090) eliminates inter-GPU transfers entirely.

---

## Decision criteria

After testing, apply these rules to pick the final profile:

1. **No OOM on startup** — the profile must load reliably.
2. **No OOM during inference** — test with a moderately long prompt (1K+ tokens).
3. **Among stable profiles, pick the fastest.** Speed is the primary metric.
4. **If aggressive and moderate are equally stable, pick aggressive** (more GPU layers).
5. **If aggressive OOMs intermittently, pick moderate** (stability over speed).
6. **Document the final choice** in models.conf with comments explaining why.
