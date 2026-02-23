# GPU Placement Strategy Guide

Reference for distributing model layers across GPUs and CPU.

> **Status update (2026-02-23):** The recommended approach changed from explicit `-ot` layer assignments to `--fit` with `--n-gpu-layers auto`. FIT automatically distributes layers across CUDA0, CUDA1, and CPU — including MoE expert offload. The old `-ot` approach is documented below for reference but is no longer used in `models.conf`. See [issue #19816](https://github.com/ggml-org/llama.cpp/issues/19816) for the discovery that motivated this change and `docs/lessons_learned.md` lesson #7 for the root cause (hardcoded `N_GPU_LAYERS=99` prevented FIT from working).

## Why this matters

Large language models often don't fit on a single GPU. Getting them to run well
involves three steps, in this order:

1. **Make it fit.** Not every model fits on one GPU. You may need to split across
   multiple GPUs, offload parts to CPU, or choose a smaller quantization. These
   are trade-offs — understand what you're giving up.

2. **Make it fit your needs.** Context window size has a big impact on VRAM usage.
   For benchmarking (short prompts), 10K context is plenty and frees VRAM for more
   model layers on GPU. For chat or assistant use, you want as much context as
   possible (64K-256K). Match the configuration to the actual use case.

3. **Optimize for speed.** Once it fits, tune the layer distribution for maximum
   performance. This depends on whether the model is dense or MoE, and for MoE
   models it can get complex (see [graph splits](#graph-splits)). This guide and
   the `gpu-optimizer` agent help find the best balance for each case.

## Table of contents

- [Hardware](#hardware)
- [Decision tree](#decision-tree)
- [Strategies](#strategies)
  - [A: Single GPU (current)](#strategy-a-single-gpu-current)
  - [FIT: Automatic multi-GPU placement (current)](#strategy-fit-automatic-multi-gpu-placement-current)
  - [B, C, D: Manual placement (historical)](#strategy-b-tensor-split--strategy-c--d-manual--ot-placement-historical)
- [Multi-GPU performance](#multi-gpu-performance)
  - [How layer-split execution works](#how-layer-split-execution-works)
  - [Graph splits](#graph-splits)
  - [Tuning a multi-GPU split](#tuning-a-multi-gpu-split)
- [Reference](#reference)
  - [Model table](#model-table)
  - [Batch size and VRAM](#batch-size-and-vram)

## Hardware

| Device | VRAM | Role |
|--------|------|------|
| CUDA0 — RTX 4090 | 24 GB | Primary compute, fastest. Nothing else runs here. |
| CUDA1 — RTX 5070 Ti | 16 GB (~12.5 usable) | Secondary. Runs display/OS. |
| CPU | 64 GB DDR4 | Slowest. Large capacity for expert offload. |

**Priority:** Always fill CUDA0 first → CUDA1 → CPU.

## Decision tree

### Step 1: Verify architecture

**Read the model card** in `models/documentation/` before any GPU decisions. Check:
- Dense or MoE? If MoE: expert count, active per token, shared experts.
- Total vs active parameters. Number of layers.
- Special features (SWA, DeltaNet, hybrid).

Never assume architecture from model name or file size.

### Step 2: Estimate VRAM

Check actual file size (`ls -lh`), then add:
- **Model weights:** file size minus ~200 MiB (metadata/embeddings)
- **KV cache:** depends on context, KV layer count, cache type (q8_0)
- **Compute buffers:** depends on `-b`/`-ub` and context size
- **CUDA overhead:** ~500 MiB per active GPU

### Step 3: Pick a strategy

```
Does the model fit on CUDA0 alone?
├── YES → Strategy A (single GPU, fastest)
│         EXTRA_ARGS: --split-mode none --main-gpu 0
│
└── NO → Use FIT auto (current standard approach)
         FIT automatically distributes across CUDA0 + CUDA1 + CPU.
         No -ot, no N_GPU_LAYERS=99, no FIT=off needed.
```

The core principle: **keep everything on GPU when possible.** GPU memory bandwidth
(~1 TB/s) is 30x faster than PCIe to CPU (~32 GB/s). Only offload to CPU when
GPU VRAM is genuinely insufficient. FIT applies this principle automatically.

## Strategies

**Current approach (2026-02-23 onward): use `--fit` for all profiles.** FIT is
on by default in docker-compose.yml and handles GPU/CPU distribution automatically.
`--n-gpu-layers auto` (also default) lets FIT decide how many layers go to GPU.

The old `-ot` explicit placement approach required `FIT=off` and `N_GPU_LAYERS=99`.
It was replaced after discovering that `N_GPU_LAYERS=99` prevents FIT from working
(see issue #19816). The old strategies (C and D) are documented below for reference
and historical context, but are not used in current `models.conf` profiles.

### Strategy A: Single GPU (current)

All weights on the 4090. No inter-device transfers, no graph split overhead.
FIT is on (default), but `--split-mode none` prevents distribution to CUDA1.

```
EXTRA_ARGS=... --split-mode none --main-gpu 0
```

`--split-mode none` in EXTRA_ARGS overrides the docker-compose default
`--split-mode layer` (last flag wins).

**When:** total VRAM footprint < ~23 GB.
**Example:** GLM-4.7-Flash Q4_K_M at 10K context (~17.5 GB).

### Strategy FIT: Automatic multi-GPU placement (current)

FIT distributes layers across CUDA0, CUDA1, and CPU based on available VRAM.
For MoE models where total weights exceed GPU VRAM, FIT automatically offloads
expert tensors to CPU while keeping attention layers on GPU.

```
# No special flags needed — FIT=on and --n-gpu-layers auto are defaults
EXTRA_ARGS=... --jinja -np 1 <sampler flags>
```

**When:** any model that needs more than one device (dense or MoE).
**Result (Qwen3-Next 262K):** 32.9 t/s, 55 graph splits, CUDA0 ~20 GB,
CUDA1 ~8 GB, CPU ~53 GB experts. Outperforms the old manual `-ot` approach
(26.5 t/s, 136 graph splits) for the same model.

### Strategy B: Tensor split / Strategy C & D: Manual -ot placement (historical)

These approaches are documented below for reference only. They required `FIT=off`
and explicit `-ot` regex rules. They are no longer used because FIT auto produces
equal or better results without the complexity and without the N_GPU_LAYERS=99 bug.

**Strategy B — Dense model across both GPUs:**
```
# Historical — not used in current profiles
EXTRA_ARGS=... --tensor-split 3,1    # 75% CUDA0, 25% CUDA1
```

**Strategy C — MoE model across both GPUs (all experts on GPU):**
```
# Historical — not used in current profiles
EXTRA_ARGS=... -ot blk\.RANGE0\.=CUDA0,blk\.RANGE1\.=CUDA1
```

**Strategy D — MoE model with CPU expert offload:**
```
# Historical — not used in current profiles
EXTRA_ARGS=... -ot blk\.RANGE0\.=CUDA0,blk\.RANGE1\.=CUDA1,exps=CPU
```

**How `-ot` priority works (for reference):** rules are evaluated left to right,
first match wins. Layers matching CUDA0/CUDA1 rules kept ALL tensors (attention
+ experts) on GPU. For remaining layers, `exps=CPU` offloaded expert weights
while `-ngl 99` kept attention on GPU.

Why experts specifically? Experts are used partially per token (e.g., 4/64 = 6%
for GLM). Attention is used every token. So when you must offload something,
experts cost the least performance. FIT applies the same logic automatically.

## Multi-GPU performance

### How layer-split execution works

Layer-split mode is **sequential, not parallel**: CUDA0 computes its layers →
transfers the result to CUDA1 → CUDA1 computes its layers.

```
total_time = CUDA0_time + transfer_time + CUDA1_time
```

This means more layers on the faster GPU genuinely helps — the 4090 processes
each layer faster, so giving it more work reduces total time.

### Graph splits

A graph split is a contiguous chunk of computation that runs on one device.
The scheduler creates a new split every time it encounters an operation on a
different device. Each split boundary costs time (data copy + synchronization).

**Check `sched_reserve: graph splits = N` in startup logs.** Lower is better.

**Dense models** are predictable: a 2-GPU split creates ~2-3 graph splits total.
Moving the split point doesn't change the count.

**MoE models** are unpredictable: each layer has complex operations (attention →
router → expert dispatch → compute → combine → shared experts). Moving the GPU
boundary by even 1-2 layers can significantly change the split count because the
scheduler maps operations to backends differently depending on where the cut falls.
There is no formula for this — you have to test and check the logs.

#### Measured example: GLM-4.7-Flash Q8 (Strategy C)

| Split (CUDA0 + CUDA1) | Graph splits | Speed | Result |
|------------------------|-------------|-------|--------|
| 35 + 12 | 33 | ~105 t/s | Sweet spot |
| 37 + 10 | 53 | ~102 t/s | Slower — 20 extra splits outweigh faster GPU benefit |

### Tuning a multi-GPU split

**Note:** With `--fit` (current default), the split is handled automatically.
The guidance below applies if you are tuning a manual `-ot` split for historical
reference, or researching how FIT behaves.

**Goal:** fewest graph splits + most layers on fastest GPU.

These two goals can conflict (as the example shows), so:

1. Start with a reasonable split based on VRAM math
2. Test and note the graph split count from startup logs
3. Try ±1-2 layers, compare graph splits and speed
4. Pick the split with the **lowest graph split count** that fits
5. Among equal split counts, prefer more layers on the faster GPU

For MoE models, certain split points produce cleaner boundaries than others.
This depends on the specific model architecture and is not predictable in advance.
FIT with auto placement produced 55 graph splits on Qwen3-Next vs 136 with the
manual `-ot` configuration — a significant improvement.

## Reference

### Model table

| Model | Type | Params | Active/token | Experts | Layers | Files |
|-------|------|--------|-------------|---------|--------|-------|
| GLM-4.7-Flash | MoE | 30B | 3B | 64/layer, 4+1 shared | 47 (1 dense + 46 MoE) | Q4: 18 GB, Q8: 30 GB |
| GPT-OSS 120B | MoE | 116.8B | 5.1B | 128/layer, 4 active | 36 (18 SWA) | F16: 61 GB |
| Qwen3-Coder-Next | MoE | 80B | 3B | 512/layer, 10 active + 1 shared | 48 (75% DeltaNet) | Q5: 57 GB, Q6: 64 GB |
| Qwen3-Next-80B-A3B | MoE | 80B | 3B | 512/layer, 10 active + 1 shared | 48 (75% DeltaNet) | Q5: 53 GB |

### Batch size and VRAM

`-b` (batch) and `-ub` (micro-batch) are independent parameters:

- **`-b` (logical batch):** How many tokens are scheduled per prompt processing
  step. Affects prompt ingestion speed. Has minimal direct VRAM impact.
- **`-ub` (micro-batch / physical batch):** How many tokens the GPU computes at
  once within a batch. **This determines the compute buffer size in VRAM.**

These can be set independently. `-b 2048 -ub 512` gives fast prompt processing
(2048 tokens per step) with a small compute buffer (sized for 512 tokens).

**Defaults (llama.cpp server and Ollama):**
- `-b 2048` (llama.cpp server default; Ollama uses 512-1024)
- `-ub 512` (universal default in both llama.cpp and Ollama)

**Rule of thumb:** Always use `-ub 512`. There is no meaningful performance
penalty — the same work is done in more micro-batches, but the speed difference
is negligible for interactive use. The VRAM savings are significant:

| `-ub` value | Compute buffer (typical) | VRAM vs `-ub 512` |
|-------------|-------------------------|-------------------|
| 512 | ~448 MiB | baseline |
| 1024 | ~897 MiB | +449 MiB wasted |
| 2048 | ~1,500-2,400 MiB | +1,000-2,000 MiB wasted |

Measured on GLM-4.7-Flash Q8_0. Exact sizes vary by model hidden dimension.

**Production recommendation:** `-b 2048 -ub 512` for all profiles. Omitting
`-ub` is fine since 512 is already the default, but explicit is clearer.

**Benchmark recommendation:** `-b 512 -ub 512` — HumanEval prompts are ~400
tokens, so the full prompt fits in one batch. No need for a larger `-b`.

**When to increase `-b`:** Only if you routinely paste very large documents
(50K+ tokens) in a single message and the prompt ingestion wait is noticeable.
Going from `-b 2048` to `-b 4096` processes prompts in fewer chunks. The VRAM
impact of `-b` alone is minimal — it only controls scheduling, not GPU buffers.

**Not like embedding chunking:** In RAG/embedding pipelines, document chunks are
processed independently, so you need overlap to preserve context at boundaries.
Prompt batching in llama.cpp is different — chunks are processed sequentially
into the same KV cache. After chunk 1 is processed, its full attention state is
stored. Chunk 2 attends to all previous tokens via the KV cache. No information
is lost at chunk boundaries, no overlap is needed. `-b` is purely a performance
knob — the end result is identical regardless of chunk size.

**Common mistake:** Setting `-b X -ub X` (same value for both). This wastes
VRAM on a larger compute buffer without any benefit. The only reason to increase
`-ub` above 512 is if profiling shows a measurable prompt processing bottleneck,
which is rare in practice.
