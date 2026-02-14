# llama.cpp Deep-Dive: Flags, Trade-offs & Qwen3-Coder-Next Strategy

## Table of Contents

- [Executive Summary](#executive-summary)
- [Quick Start: Qwen3-Coder-Next on Your Hardware](#quick-start)
  - [Recommended Quants](#recommended-quants)
  - [Golden Rule: Fill GPUs First](#golden-rule)
  - [Tuning Method](#tuning-method)
  - [-ot Regex Lookup Table](#ot-regex-lookup-table)
  - [Strategies & Test Results](#strategies--test-results)
  - [KV Cache Precision: q8_0 Is the Sweet Spot](#kv-cache-precision)
  - [Flags Reference](#flags-reference)
- [Part 1: GPT-OSS Docker Setup — Flags Explained](#part-1-gpt-oss-docker-setup--flags-explained)
- [Part 2: Flags You Haven't Used Yet but Are Relevant](#part-2-flags-you-havent-used-yet-but-are-relevant)
- [Part 3: Qwen3-Coder-Next vs GPT-OSS — Architecture Differences](#part-3-qwen3-coder-next-vs-gpt-oss--architecture-differences)
- [Part 4: Docker Setup Adjustments](#part-4-docker-setup-adjustments)
- [Part 5: Notes & Known Issues](#part-5-notes--known-issues)
- [Next Steps](#next-steps)

---

## Executive Summary

### Hardware

RTX 4090 (24 GB) + RTX 5070 Ti (16 GB) + 64 GB DDR4 RAM + AMD 5800X3D.

### Model

Qwen3-Coder-Next 80B MoE (512 experts, 10 active, ~3B active params/token). 75% DeltaNet (linear attention, no KV cache) + 25% standard attention. This makes 256K context feasible — only 12/48 layers have KV cache.

### Recommended Configuration

**Primary: UD-Q6_K_XL + 256K context + q8_0 KV cache**

For a ready-to-use config, see `[qwen3-coder]` in `models.conf`, or run `./start.sh qwen3-coder`.

```bash
MODEL=Qwen3-Coder-Next/UD-Q6_K_XL/Qwen3-Coder-Next-UD-Q6_K_XL-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU" \
docker compose up
```

**21.4 t/s** | 19/48 layers on GPU | 256K context | Best quality of all tested configurations.

**Alternative: UD-Q5_K_XL** — same command but different model, 15+7 layers, **25.8 t/s** (+21% faster). Use when speed is more important than maximum accuracy. See `[qwen3-coder-q5]` in `models.conf` for a ready-to-use config, or run `./start.sh qwen3-coder-q5`.

### Key Findings

1. **Unsloth Dynamic (UD) quants are strictly better than standard quants** for MoE models. UD gives higher precision to expert router tensors, leading to better expert selection, less self-correction, and more efficient context usage.
2. **Q4 quants are unusable for agentic coding** — 5x more tokens due to endless rewriting.
3. **KV cache: q8_0 is functionally lossless, q4_0 causes self-correction, f16 is wasted VRAM.**
4. **256K context costs ~4 GPU layers vs 64K** due to larger compute buffers and KV cache, but the speed impact is acceptable (~9-17% depending on quant).
5. **Compute buffer scales with context** — this was the biggest surprise when scaling from 64K to 256K. Budget ~5.4 GB CUDA0 and ~3.8 GB CUDA1 in fixed overhead.

---

## Quick Start: Qwen3-Coder-Next on Your Hardware {#quick-start}

### Recommended Quants {#recommended-quants}

| Quant | Type | Size | BPW | Status | Recommendation |
|-------|------|------|-----|--------|----------------|
| Q4_K_M | Standard 4-bit | ~44 GB | 4.83 | Tested, UNUSABLE | Do not download |
| Q5_K_M | Standard 5-bit | 52.9 GB | 5.70 | Tested, works | Delete (UD is better) |
| **UD-Q5_K_XL** | Unsloth Dynamic 5-bit | 56.8 GB | ~5.9 | **Tested, speed option** | Keep |
| Q6_K | Standard 6-bit | 65.5 GB | 6.57 | Tested, works | Delete (UD is better) |
| **UD-Q6_K_XL** | Unsloth Dynamic 6-bit | 63.9 GiB | 6.89 | **Tested, BASELINE** | Keep |

**Conclusion:** Only **UD-Q6_K_XL** (primary) and **UD-Q5_K_XL** (faster option) are needed. All other quants can be removed.

**Unsloth Dynamic (UD):** not every tensor is equally important. UD gives sensitive tensors (expert router, attention) higher precision and less important tensors lower precision. **XL** = even more tensors at higher precision. Smarter than uniform quantization — better quality at comparable size. For MoE models with 512 experts, router precision is crucial — UD makes the difference here.

### Golden Rule: ALWAYS Fill Both GPUs First {#golden-rule}

```
Step 1: Fill GPU0 (4090) — target: at least 23 GB of 24.5 GB used
Step 2: Fill GPU1 (5070 Ti) — target: at least 13 GB of 13.3 GB used
Step 3: Only then overflow to CPU
```

**Why:** GPU memory = ~1 TB/s. DDR4 RAM = ~50 GB/s. That's a 20x difference. Every GB of experts on CPU instead of GPU directly costs speed.

### Tuning Method: Start AGGRESSIVE, Scale Back on OOM {#tuning-method}

Start with as many layers on GPU as possible. OOM? Move one layer back to CPU. Repeat. This is the fastest way to find the optimal config.

### `-ot` Regex Lookup Table {#ot-regex-lookup-table}

The `-ot` flag uses regex to assign layers to GPUs. Below you can look up exactly which regex you need — no regex knowledge required.

**CUDA0 (4090) — choose the number of layers:**

| Layers | Which | Regex for CUDA0 |
|--------|-------|-----------------|
| 11 | 0-10 | `blk\.([0-9]\|10)\.=CUDA0` |
| 12 | 0-11 | `blk\.([0-9]\|1[0-1])\.=CUDA0` |
| **13** | **0-12** | **`blk\.([0-9]\|1[0-2])\.=CUDA0`** — UD-Q6_K_XL baseline |
| 14 | 0-13 | `blk\.([0-9]\|1[0-3])\.=CUDA0` |
| **15** | **0-14** | **`blk\.([0-9]\|1[0-4])\.=CUDA0`** — UD-Q5_K_XL baseline |
| 16 | 0-15 | `blk\.([0-9]\|1[0-5])\.=CUDA0` |
| 17 | 0-16 | `blk\.([0-9]\|1[0-6])\.=CUDA0` |
| 18 | 0-17 | `blk\.([0-9]\|1[0-7])\.=CUDA0` |
| 19 | 0-18 | `blk\.([0-9]\|1[0-8])\.=CUDA0` |
| 20 | 0-19 | `blk\.([0-9]\|1[0-9])\.=CUDA0` |

**CUDA1 (5070 Ti) — choose the number of layers (start where CUDA0 stops):**

| Layers | If CUDA0=13 (start 13) | Regex for CUDA1 |
|--------|------------------------|-----------------|
| 5 | 13-17 | `blk\.(1[3-7])\.=CUDA1` |
| **6** | **13-18** | **`blk\.(1[3-8])\.=CUDA1`** — UD-Q6_K_XL baseline |
| 7 | 13-19 | `blk\.(1[3-9])\.=CUDA1` |

| Layers | If CUDA0=15 (start 15) | Regex for CUDA1 |
|--------|------------------------|-----------------|
| 6 | 15-20 | `blk\.(1[5-9]\|20)\.=CUDA1` |
| **7** | **15-21** | **`blk\.(1[5-9]\|2[0-1])\.=CUDA1`** — UD-Q5_K_XL baseline |
| 8 | 15-22 | `blk\.(1[5-9]\|2[0-2])\.=CUDA1` |

| Layers | If CUDA0=18 (start 18) | Regex for CUDA1 |
|--------|------------------------|-----------------|
| 6 | 18-23 | `blk\.(1[8-9]\|2[0-3])\.=CUDA1` |
| 7 | 18-24 | `blk\.(1[8-9]\|2[0-4])\.=CUDA1` |
| 8 | 18-25 | `blk\.(1[8-9]\|2[0-5])\.=CUDA1` |

**Combining:** paste the two parts together with a comma + `exps=CPU` at the end:
```
-ot <CUDA0 regex>,<CUDA1 regex>,exps=CPU
```

**Example (13 on CUDA0, 6 on CUDA1 — UD-Q6_K_XL baseline):**
```
-ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU
```
Layers 0-12 → 4090, layers 13-18 → 5070 Ti, layers 19-47 experts → CPU.

### Strategies & Test Results {#strategies--test-results}

**VRAM Budget (measured at 256K context):**

| | CUDA0 (4090) | CUDA1 (5070 Ti) |
|---|---|---|
| Total available | 23,671 MiB | 12,761 MiB |
| Compute buffer (256K) | ~3,216 MiB | ~2,673 MiB |
| KV cache (q8_0, 256K) | 2,176 MiB | 1,088 MiB |
| RS buffer | 50 MiB | 25 MiB |
| **Fixed overhead total** | **~5,442 MiB** | **~3,786 MiB** |
| **Available for model weights** | **~18,229 MiB** | **~8,975 MiB** |

**Note:** Compute buffer scales with context size — at 64K it's ~2 GB, at 256K ~3.2 GB per GPU. This was the main reason 256K allows fewer GPU layers than 64K.

**KV cache scaling (only 12/48 layers have KV — DeltaNet has no KV):**

| Context | q8_0 KV total | q4_0 KV total |
|---------|---------------|---------------|
| 64K | 816 MiB | 408 MiB |
| 128K | 1,632 MiB | 816 MiB |
| 256K | 3,264 MiB | 1,632 MiB |

---

### Goal: highest accuracy → highest context → acceptable speed

---

**Strategy 1: Q5_K_M + 64K q8_0 — "first working config" (superseded)**

```bash
MODEL=Qwen3-Coder-Next-Q5_K_M-00001-of-00003.gguf \
CTX_SIZE=65536 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-7])\.=CUDA0,blk\.(1[8-9]|2[0-5])\.=CUDA1,exps=CPU" \
docker compose up
```

**Distribution:** 18 layers CUDA0, 8 layers CUDA1 = 26/48 on GPU.

**TESTED — results:**

| Metric | Value |
|--------|-------|
| CUDA0 (4090) VRAM | 23,489 / 24,564 MiB (**95.6%**) |
| CUDA1 (5070 Ti) VRAM | 14,869 / 16,303 MiB (**91.2%**) |
| Token generation speed | **27.4 t/s** (626 tokens in 22.8s) |
| RAM usage (idle) | 7.4 GB / 62.7 GB |
| Code quality | Correct, clean, no self-correction |

**Status:** Superseded. UD-Q5_K_XL and UD-Q6_K_XL are better in everything except raw speed.

---

**Strategy 2: Q5_K_M + 256K q8_0 — "context scaling test" (superseded)**

Same model as strategy 1, but with 256K context. Proved that 256K is feasible.
Compute buffer scales with context (64K: ~2 GB → 256K: ~3.2 GB per GPU).

```bash
MODEL=Qwen3-Coder-Next-Q5_K_M-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-4])\.=CUDA0,blk\.(1[5-9]|2[0-1])\.=CUDA1,exps=CPU" \
docker compose up
```

**Distribution:** 15 CUDA0 + 7 CUDA1 = 22/48 on GPU.

**TESTED — results:**

| Metric | Value | vs Strategy 1 (64K) |
|--------|-------|---------------------|
| CUDA0 VRAM | 23,108 / 24,564 MiB (**94.1%**) | was 95.6% |
| CUDA1 VRAM | 15,520 / 16,303 MiB (**95.2%**) | was 91.2% |
| Token generation speed | **24.9 t/s** | was 27.4 t/s (-9%) |
| Output tokens | **2,628** (self-correction!) | was 626 |
| Context | **262,144 (256K)** | was 64K |
| GPU layers | 22/48 | was 26/48 (-4 layers) |

**Observation:** Output showed self-correction behavior (3x rewritten). This is sampling variance at temp 1.0, worsened by uniform quantization on router tensors.

**Failed attempts:** 17+8 OOM (CUDA0), 16+8 OOM (CUDA1).

**Status:** Superseded by strategy 3 (UD-Q5_K_XL eliminates self-correction).

---

**Strategy 3: UD-Q5_K_XL + 256K q8_0 — "speed alternative" FASTER OPTION**

Unsloth Dynamic distribution: router and attention at higher precision, experts at lower precision.
Result: significantly better output quality than standard Q5_K_M at identical VRAM footprint.

```bash
MODEL=Qwen3-Coder-Next/UD-Q5_K_XL/Qwen3-Coder-Next-UD-Q5_K_XL-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-4])\.=CUDA0,blk\.(1[5-9]|2[0-1])\.=CUDA1,exps=CPU" \
docker compose up
```

**Distribution:** 15 CUDA0 + 7 CUDA1 = 22/48 on GPU.

**TESTED — results:**

| Metric | Value | vs Strategy 2 (Q5_K_M 256K) |
|--------|-------|------------------------------|
| CUDA0 model weights | 17,176 MiB | -8 MiB |
| CUDA1 model weights | 8,192 MiB | -250 MiB (UD saves on GPU!) |
| Token generation speed | **25.8 t/s** (821 tokens in 31.9s) | +4% |
| Self-correction | **None** | vs 3x rewritten |
| Output quality | Clean, 1x correct | vs hesitation behavior |

**Why UD performs better:** UD allocates higher precision to router tensors (which determine which 10/512 experts are active per token). Better router precision → better expert selection → less hesitation → fewer self-correction loops.

---

**Strategy 4: Q6_K + 256K q8_0 — "higher accuracy, uniform quant" (superseded)**

Higher model precision (6-bit uniform). Slightly slower due to fewer GPU layers, but output quality
comparable to UD-Q5_K_XL.

```bash
MODEL=Qwen3-Coder-Next/Q6_K/Qwen3-Coder-Next-Q6_K-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-1])\.=CUDA0,blk\.(1[2-7])\.=CUDA1,exps=CPU" \
docker compose up
```

**Distribution:** 12 CUDA0 + 6 CUDA1 = 18/48 on GPU.

**TESTED — results:**

| Metric | Value | vs Strategy 3 (UD-Q5_K_XL) |
|--------|-------|------------------------------|
| Token generation speed | **21.7 t/s** | was 25.8 t/s (-16%) |
| Output tokens | 691 | vs 821 |
| Self-correction | None | None |
| Output quality | Clean, slightly more elegant code | Clean |
| GPU layers | 18/48 | was 22/48 (-4 layers) |

**Failed attempt:** 13+6 OOM on CUDA0 (compute buffer didn't fit).

**Status:** Superseded by strategy 5 (UD-Q6_K_XL = same precision, better router, more layers).

---

**Strategy 5: UD-Q6_K_XL + 256K q8_0 — "best available quality" BASELINE**

63.87 GiB effective (6.89 BPW). Unsloth Dynamic Q6 with XL bit allocation.
Metadata bug (reported ~Feb 11, 2026) is **fixed** in the Feb 13 reupload.

For a ready-to-use config, see `[qwen3-coder]` in `models.conf`, or run `./start.sh qwen3-coder`.

```bash
MODEL=Qwen3-Coder-Next/UD-Q6_K_XL/Qwen3-Coder-Next-UD-Q6_K_XL-00001-of-00003.gguf \
CTX_SIZE=262144 \
FIT=off \
N_GPU_LAYERS=99 \
SPLIT_MODE=layer \
EXTRA_ARGS="--jinja -np 1 -b 2048 -ub 2048 --no-context-shift \
  --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 \
  -ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU" \
docker compose up
```

**Distribution:** 13 CUDA0 + 6 CUDA1 = 19/48 on GPU.

**TESTED — results:**

| Metric | Value | vs Strategy 4 (Q6_K) | vs Strategy 3 (UD-Q5_K_XL) |
|--------|-------|----------------------|------------------------------|
| CUDA0 model weights | 17,361 MiB | +1,414 MiB | +185 MiB |
| CUDA1 model weights | 8,835 MiB | +327 MiB | +643 MiB |
| CUDA0 VRAM total | 23,525 / 24,564 MiB (**95.8%**) | was 89.0% | — |
| CUDA1 VRAM total | 15,287 / 16,303 MiB (**93.8%**) | was 95.0% | — |
| Token generation speed | **21.4 t/s** (871 tokens in 40.8s) | -1% | -17% |
| Self-correction | None | None | None |
| Output quality | Clean, well-documented | Clean | Clean |
| GPU layers | 19/48 | +1 | -3 |
| RAM usage | ~5.7 GB | ~6.5 GB | ~7.1 GB |

**First attempt (11+5 = 16/48):** Worked, but had ~3,300 MiB free on CUDA0. 13+6 utilizes VRAM better.

---

### Overview of All Strategies

| Strategy | Quant | Context | KV | GPU layers | Speed | Quality | Status |
|----------|-------|---------|-----|------------|-------|---------|--------|
| 1 | Q5_K_M | 64K | q8_0 | 26/48 | 27.4 t/s | Good | Superseded |
| 2 | Q5_K_M | 256K | q8_0 | 22/48 | 24.9 t/s | Self-correction | Superseded |
| **3** | **UD-Q5_K_XL** | **256K** | **q8_0** | **22/48** | **25.8 t/s** | **Clean** | **Speed option** |
| 4 | Q6_K | 256K | q8_0 | 18/48 | 21.7 t/s | Clean | Superseded |
| **5** | **UD-Q6_K_XL** | **256K** | **q8_0** | **19/48** | **21.4 t/s** | **Clean** | **Baseline** |
| 5b | UD-Q6_K_XL | 256K | q4_0 | 20/48 | ~21 t/s | Self-correction | Not usable |
| — | Q4_K_M | 64K | q8_0 | 30/48 | 31.0 t/s | 5x rewritten | Not usable |

---

### KV Cache Precision: q8_0 Is the Sweet Spot {#kv-cache-precision}

KV cache is **working memory** (runtime attention scores), not learned knowledge. Quantizing it is different from model weight quantization.

| KV type | Supported | VRAM (256K) | Quality | Recommendation |
|---------|-----------|-------------|---------|----------------|
| **f16** | Yes | 6,528 MiB | Reference | **Don't use** — costs ~5 extra layers, gain is immeasurable |
| **q8_0** | Yes | 3,264 MiB | Functionally lossless | **Always use this** |
| q5_0 | Yes | ~2,448 MiB | Minimal loss | Middle ground (not tested) |
| **q4_0** | Yes | 1,632 MiB | Self-correction | **Not usable for agentic coding** |

**Why f16 KV is wasted VRAM:** q8_0 maintains 256 discrete levels per value. KV cache contains attention scores that are inherently noisy from softmax rounding. The difference between 256 levels (q8_0) and 65,536 levels (f16) disappears in that noise. The consensus in the llama.cpp community is that q8_0 KV is functionally lossless compared to f16.

**Why q4_0 KV doesn't work:** Tested with UD-Q6_K_XL (strategy 5b). 14+6 layers (20/48, 1 more than strategy 5). Output showed **severe self-correction behavior** — cut short halfway due to pointless rewrites. q4_0 has only 16 discrete levels — too few for reliable attention recall over long context. It gains 1 extra GPU layer but loses usability.

**q6 KV does not exist** — llama.cpp only supports q8_0, q5_0, and q4_0 for KV cache. q6_K is a weight-only quantization format.

---

### Q4_K_M Test Archive — NOT RECOMMENDED

Q4_K_M was tested and is **not suitable for agentic coding**. Results are kept here as reference.

**Configuration:** 20 layers CUDA0, 10 layers CUDA1 = 30/48 on GPU, 64K q8_0 context.

| Metric | Q5_K_M (strategy 1) | Q4_K_M |
|--------|----------------------|--------|
| Speed | 27.4 t/s | 31.0 t/s (+13%) |
| CUDA0 VRAM | 95.6% | 90.7% |
| CUDA1 VRAM | 91.2% | 96.0% |
| Tokens for same prompt | 626 | 3096 (**5x more**) |
| Output quality | One correct function | 5 rewrites, "Wait, there's an issue..." |
| Agentic coding usable? | Yes | No |

**Analysis:** Q4 quantization degrades the expert router precision. With 512 experts and only 10 active per token, the router is the most sensitive component — the model selects wrong experts, hesitates, and rewrites endlessly. For agentic coding this fills the context window 5x faster with noise.

---

**For all strategies:**
- **OOM → reduce layers first (1 at a time), then context (256K → 192K → 128K)**
- **VRAM headroom → look up in the table, add 1-2 layers**
- Goal: both GPUs at 90%+ VRAM (`nvidia-smi`)

### Flags That Should ALWAYS Be On {#flags-reference}

| Flag | In one sentence |
|------|-----------------|
| `--jinja` | Without this, the chat template and tool calling won't work |
| `--flash-attn on` | Free memory savings, no downside |
| `-np 1` | More slots = more KV cache memory used, unnecessary for single-user |
| `--no-context-shift` | Prevents code from silently disappearing from your context |
| `-ngl 99` | All layers to GPU, experts are selectively sent back by `-ot` |
| `FIT=off` | Auto-fit doesn't understand expert/attention split with `-ot` |

### Flags to Experiment With

| Flag | What it controls | Start with | Direction |
|------|-----------------|-----------|----------|
| `-b` / `-ub` | Batch size for prompt processing | 2048 | Increase if VRAM available = faster prompts |
| `-ot` | Precise tensor placement per layer | See strategies | Tune via trial & error on VRAM |
| `--cache-type-k/v` | KV cache precision | q8_0 | Don't reduce — q4_0 causes self-correction |
| `-sm` | Multi-GPU split | layer | Also test `row` (Qwen recommends it, but may conflict with `-ot`) |
| `--temp` | Sampling temperature | 1.0 (Qwen recommendation) | 0.6-0.8 for more deterministic coding |

### Note: Multi-part GGUF

All large quants are split into **3 files**. Always point MODEL to the first file (`-00001-of-0000X.gguf`), llama.cpp loads the rest automatically from the same directory.

---

## Part 1: GPT-OSS Docker Setup — Flags Explained {#part-1-gpt-oss-docker-setup--flags-explained}

Working config (see also `[gpt-oss-120b]` in `models.conf`):
```bash
MODEL=GPT-OSS-120b/gpt-oss-120b-F16.gguf \
CTX_SIZE=65536 \
FIT=off \
N_GPU_LAYERS=99 \
EXTRA_ARGS="--jinja -np 1 -b 4096 -ub 4096 \
  -ot blk\.([0-9]|1[01])\.=CUDA0,blk\.(1[2-5])\.=CUDA1,exps=CPU"
```

Plus docker-compose defaults: `--flash-attn on`, `--cache-type-k q8_0`, `--cache-type-v q8_0`, `--split-mode layer`, `--main-gpu 0`

| Flag | What it does | Trade-off |
|------|-------------|-----------|
| `--flash-attn on` | Computes attention without full NxN matrix. Halves attention memory. | No downside. Always on. |
| `--cache-type-k/v q8_0` | KV cache from FP16 to Q8. Halves KV cache memory. | Functionally lossless. Don't reduce further. |
| `-ngl 99` | All 36 layers to GPU. `-ot` sends some tensors back to CPU. | Without `-ot` = OOM. With `-ot` = all attention on GPU, experts selectively on CPU. |
| `--split-mode layer` | Layers sequentially across GPUs: 0-N on GPU0, N+1-M on GPU1. | Simple, effective for asymmetric GPUs. |
| `--main-gpu 0` | 4090 as primary GPU. | More VRAM, more compute. |
| `-ot` | Regex-based tensor placement per device. | Most control, but tricky with Docker shell escaping. |
| `--jinja` | Jinja chat template from model metadata. | Essential for GPT-OSS and Qwen3-Coder-Next. |
| `-np 1` | One parallel slot = one KV cache. | Single-user: 1 is correct. |
| `-b 4096 -ub 4096` | Batch size for prompt processing. Triggers disaggregated prompt processing. | Faster prompts, but more temporary VRAM (~3.2 GB compute buffer on CUDA1). |
| `--fit off` | Disables auto-fit. | Required with `-ot`. |

---

## Part 2: Flags You Haven't Used Yet but Are Relevant {#part-2-flags-you-havent-used-yet-but-are-relevant}

### MoE-Specific Flags

| Flag | What it does | When |
|------|-------------|------|
| `--cpu-moe` | All expert weights to CPU. | Simplest option, but leaves VRAM unused. Use `-ot` instead. |
| `--n-cpu-moe N` | Experts of N layers to CPU (counts from highest layer). | Easier than `-ot`, less control over GPU distribution. |
| `--no-op-offload` | Disables disaggregated prompt processing. | Sometimes faster for token gen if you already have enough experts on GPU. |

### Context & Memory

| Flag | What it does | Trade-off |
|------|-------------|-----------|
| `--ctx-size 0` | Max context from model metadata. | Can OOM if model claims more than fits. |
| `--no-context-shift` | Stop when full instead of shifting out oldest tokens. | Safer for coding. |
| `--cache-type-k/v q4_0` | Aggressive KV quantization. | Causes self-correction — don't use for agentic coding. |
| `--cache-type-k/v q5_0` | Middle ground. | Not tested, possibly usable as a compromise. |

### Sampling (Qwen3-Coder-Next)

Official: `temperature=1.0, top_p=0.95, top_k=40, min_p=0`. Optional: `--presence-penalty 0.0-2.0` against repetition. For agentic coding: consider `--temp 0.6-0.8` for more deterministic output.

### Performance Tuning

| Flag | What it does | Trade-off |
|------|-------------|-----------|
| `-t N` | CPU threads (5800X3D = 8C/16T). | More = faster expert processing, steals from HTTP server. |
| `--prio 2` | High process priority. | Helps with CPU-bound expert processing. |
| `-sm row` | Each layer across both GPUs. | Qwen recommends this, but may conflict with per-GPU `-ot`. |
| `--no-mmap` | Load everything into RAM upfront. | More consistent, risky with 64 GB RAM + 50+ GB model. |

---

## Part 3: Qwen3-Coder-Next vs GPT-OSS — Architecture Differences {#part-3-qwen3-coder-next-vs-gpt-oss--architecture-differences}

| Aspect | GPT-OSS-120B | Qwen3-Coder-Next |
|--------|--------------|------------------|
| Total params | 116.8B | 80B |
| Active params/token | ~5.1B (4/128 experts) | ~3B (10/512 experts) |
| Layers | 36 | 48 |
| Attention | Standard + SWA (50/50) | 75% DeltaNet (linear) + 25% standard |
| Experts per layer | 128, 4 active | 512, 10 active + 1 shared |
| KV cache | SWA layers = tiny KV | DeltaNet layers = no KV |
| Base precision | MXFP4 (native FP4) | BF16 (then GGUF quantized) |

**What this means:**
- Fewer active params → faster inference per token
- 75% DeltaNet → drastically less KV cache → more context per GB
- 512 experts/layer → expert weights ~85-90% of model → crucial to keep as many on GPU as possible
- 48 layers → more granularity in `-ot` layer distribution

---

## Part 4: Docker Setup Adjustments {#part-4-docker-setup-adjustments}

### To add to docker-compose.yml:

```yaml
- CPU_MOE=${CPU_MOE:-}
- N_CPU_MOE=${N_CPU_MOE:-}
- NO_CONTEXT_SHIFT=${NO_CONTEXT_SHIFT:-1}
```

### To add to Dockerfile CMD:

```bash
if [ "${CPU_MOE}" = "1" ]; then ARGS="${ARGS} --cpu-moe"; fi;
if [ -n "${N_CPU_MOE}" ]; then ARGS="${ARGS} --n-cpu-moe ${N_CPU_MOE}"; fi;
if [ "${NO_CONTEXT_SHIFT}" = "1" ]; then ARGS="${ARGS} --no-context-shift"; fi;
```

---

## Part 5: Notes & Known Issues {#part-5-notes--known-issues}

### llama.cpp Support Status
- `qwen3next` architecture recently added (PR #16095) — performance not yet fully optimized
- DeltaNet kernels are new — expect improvements
- **Rebuild Docker image with latest llama.cpp master** before you start
- Unsloth Feb 4 bugfix for looping/bad output — download recent GGUFs
- **UD-Q6_K_XL metadata bug (reported Feb 11)** — fixed in Feb 13, 2026 reupload. Confirmed working.

### Official Qwen Reference Command
```bash
./llama-cli \
  -m Qwen3-Coder-Next-Q5_K_M-00001-of-00003.gguf \
  --jinja -ngl 99 -fa on -sm row \
  --temp 1.0 --top-k 40 --top-p 0.95 --min-p 0 \
  -c 40960 -n 32768 --no-context-shift
```

### YaRN for Context Beyond 256K
```
--rope-scaling yarn --yarn-orig-ctx 262144
```
Validated up to 131K. Not needed for now (256K is native context length).

---

## Next Steps {#next-steps}

### 1. API Integration with Claude Code / CLI Tooling

The local Qwen3-Coder-Next runs as an OpenAI-compatible API (llama-server on port 8080). The next step is integration with development tooling:

- **Claude Code** or other CLI assistants configured to use the local API as backend
- **VS Code integration** testing for code completion and agentic workflows
- **Use case delineation:** determining when the local setup is worthwhile vs. the Anthropic Max subscription (Opus 4.6 / Sonnet). The proprietary models are significantly stronger — the local setup is interesting for privacy-sensitive tasks, offline use, unlimited token volume, and as an experimentation platform.

### 2. Formal Benchmarks

Current tests are qualitative (one prompt, visual assessment). For an objective comparison:

- **LiveCodeBench** (or similar coding-specific benchmark) on the three usable configs: UD-Q5_K_XL, Q6_K, UD-Q6_K_XL
- **Comparison with proprietary models** (Opus 4.6, GPT-5.3 Codex, etc.) to understand where the local model stands — not to compete, but to understand which tasks are and aren't suitable
- **Temperature sweep** (0.6 / 0.8 / 1.0) to find the optimal sampling point for agentic coding vs. creative tasks
- Document results as a score reference for future model upgrades
