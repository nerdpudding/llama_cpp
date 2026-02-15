# GPU Placement Strategy Guide

Reference for distributing model layers across GPUs and CPU.

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
  - [A: Single GPU](#strategy-a-single-gpu)
  - [B: Tensor split (dense)](#strategy-b-tensor-split-dense)
  - [C: Selective GPU split (MoE)](#strategy-c-selective-gpu-split-moe)
  - [D: GPU + CPU offload (MoE)](#strategy-d-gpu--cpu-offload-moe)
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
│
└── NO → Does it fit on CUDA0 + CUDA1 combined?
         ├── YES, dense → Strategy B (tensor split)
         ├── YES, MoE  → Strategy C (selective GPU split)
         └── NO         → Strategy D (GPU + CPU offload)
```

The core principle: **keep everything on GPU when possible.** GPU memory bandwidth
(~1 TB/s) is 30x faster than PCIe to CPU (~32 GB/s). Only offload to CPU when
GPU VRAM is genuinely insufficient.

## Strategies

All strategies use `FIT=off`. FIT auto-distributes for fit, not for speed — it
ignores graph splits, bandwidth, and display overhead. Use explicit placement.

### Strategy A: Single GPU

All weights on the 4090. No inter-device transfers, no graph split overhead.

```
FIT=off
EXTRA_ARGS=... --split-mode none --main-gpu 0
```

`--split-mode none` in EXTRA_ARGS overrides the docker-compose default
`--split-mode layer` (last flag wins).

**When:** total VRAM footprint < ~23 GB.
**Example:** GLM-4.7-Flash Q4_K_M at 10K context (~17.5 GB).

### Strategy B: Tensor split (dense)

Dense model across both GPUs using proportional distribution.

```
FIT=off
EXTRA_ARGS=... --tensor-split 3,1
```

`--tensor-split 3,1` = 75% CUDA0, 25% CUDA1. Adjust ratio after testing.

**When:** dense model > 23 GB.

### Strategy C: Selective GPU split (MoE)

MoE model that fits across both GPUs. Use `-ot` regex to assign layers explicitly.
No `exps=CPU` — all experts stay on GPU.

```
FIT=off
EXTRA_ARGS=... -ot blk\.RANGE0\.=CUDA0,blk\.RANGE1\.=CUDA1
```

**When:** MoE model where total weights fit in combined GPU VRAM (~36.5 GB usable).
**Example:** GLM-4.7-Flash Q8_0 (30 GB, 47 layers → 35 on CUDA0, 12 on CUDA1).

### Strategy D: GPU + CPU offload (MoE)

MoE model exceeding total GPU VRAM. Attention stays on GPU, expert weights for
overflow layers go to CPU via `exps=CPU`.

```
FIT=off
EXTRA_ARGS=... -ot blk\.RANGE0\.=CUDA0,blk\.RANGE1\.=CUDA1,exps=CPU
```

**How `-ot` priority works:** rules are evaluated left to right, first match wins.
Layers matching CUDA0/CUDA1 rules keep ALL tensors (attention + experts) on GPU.
For remaining layers, `exps=CPU` offloads expert weights while `-ngl 99` keeps
attention on GPU.

Why experts specifically? Experts are used partially per token (e.g., 4/64 = 6%
for GLM). Attention is used every token. So when you must offload something,
experts cost the least performance.

**When:** GPT-OSS 120B, Qwen3-Coder-Next, any MoE model > 36.5 GB.

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

**Goal:** fewest graph splits + most layers on fastest GPU.

These two goals can conflict (as the example shows), so:

1. Start with a reasonable split based on VRAM math
2. Test and note the graph split count from startup logs
3. Try ±1-2 layers, compare graph splits and speed
4. Pick the split with the **lowest graph split count** that fits
5. Among equal split counts, prefer more layers on the faster GPU

For MoE models, certain split points produce cleaner boundaries than others.
This depends on the specific model architecture and is not predictable in advance.

## Reference

### Model table

| Model | Type | Params | Active/token | Experts | Layers | Files |
|-------|------|--------|-------------|---------|--------|-------|
| GLM-4.7-Flash | MoE | 30B | 3B | 64/layer, 4+1 shared | 47 (1 dense + 46 MoE) | Q4: 18 GB, Q8: 30 GB |
| GPT-OSS 120B | MoE | 116.8B | 5.1B | 128/layer, 4 active | 36 (18 SWA) | F16: 61 GB |
| Qwen3-Coder-Next | MoE | 80B | 3B | 512/layer, 10 active | 48 (75% DeltaNet) | Q5: 57 GB, Q6: 64 GB |

### Batch size and VRAM

`-b` (batch) and `-ub` (micro-batch) control prompt processing chunk size.
Larger values use more VRAM for compute buffers.

| Context | Use case | Recommended -b/-ub | Reason |
|---------|----------|-------------------|--------|
| Benchmark (10K) | HumanEval (~400 token prompts) | 512 | Saves VRAM for more GPU layers |
| Production (64K-256K) | Interactive, long prompts | 2048-4096 | Faster prompt ingestion |

Savings from smaller batch: typically 2-4 GB per GPU. At 10K context, this can
free enough room for 1-4 additional layers on GPU compared to production settings.
