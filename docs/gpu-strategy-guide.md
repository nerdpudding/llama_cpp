# GPU Placement Strategy Guide

Reference for deciding how to distribute model layers across GPUs and CPU.
Applies to all models in this project (GLM, GPT-OSS, Qwen3, and future additions).

## Hardware

- **GPU 0 (CUDA0):** RTX 4090 — 24 GB VRAM, fastest compute
- **GPU 1 (CUDA1):** RTX 5070 Ti — 16 GB VRAM (~12.5 GB usable after OS/display overhead)
- **CPU:** 64 GB DDR4 — slowest, but plenty of capacity

**Priority order:** CUDA0 (fastest) → CUDA1 → CPU (slowest). Always fill the
fastest device first.

## Decision tree

### Step 1: Verify model architecture

**Before any GPU decisions, read the model card.** Check:
- Dense or MoE?
- If MoE: how many experts? How many active per token? Shared experts?
- Total parameters vs active parameters per token
- Number of layers
- Any special architecture features (SWA, DeltaNet, hybrid dense/MoE)

Model cards are stored in `models/documentation/`. If missing, check the
Hugging Face page or GGUF metadata (use the metadata extraction script or
llama.cpp's `--verbose` output).

**Never assume architecture from model size or name.** A "30B" model can be
MoE with only 3B active (GLM-4.7-Flash). A "120B" model can run on consumer
GPUs because of MoE (GPT-OSS).

### Step 2: Estimate total VRAM needed

Calculate the full model footprint:
- **Model weights:** check the GGUF file size (subtract ~200 MiB for metadata/embeddings)
- **KV cache:** depends on context size, number of KV layers, and cache quantization (q8_0)
- **Compute buffers:** depends on `-b`/`-ub` settings and context size. Larger
  batch sizes allocate more VRAM. Use 512 for benchmarks (small prompts), larger
  for production.
- **CUDA overhead:** ~500 MiB per active GPU for driver/context

### Step 3: Apply the right strategy

```
Does the entire model fit on GPU 0 (RTX 4090)?
├── YES → Strategy A: Single GPU
│         All weights on GPU, no CPU offloading needed.
│         --split-mode none --main-gpu 0, FIT=off
│
└── NO → Does it fit on GPU 0 + GPU 1 combined?
         ├── YES, and it's dense → Strategy B: Tensor Split
         │   Use --tensor-split to distribute proportionally.
         │   Maximize GPU 0's share. FIT=off.
         │
         ├── YES, and it's MoE → Strategy C: Selective GPU split
         │   Use -ot to place layers on specific GPUs.
         │   Keep ALL attention on GPU. Experts stay on GPU for
         │   the layers that fit. FIT=off.
         │
         └── NO → Strategy D: GPU + CPU offloading (MoE models)
                  Use -ot with exps=CPU. Attention layers on GPU
                  (CUDA0 first, overflow to CUDA1). Expert weights
                  for layers that don't fit on GPU go to CPU.
                  FIT=off.
```

## Strategy details

### Strategy A: Single GPU (model fits on CUDA0)

Used when the full model (all weights + KV + compute) fits within the RTX 4090's
24 GB. This is the fastest option — no inter-device transfers.

```
FIT=off
EXTRA_ARGS=... --split-mode none --main-gpu 0
```

- `--split-mode none` prevents llama.cpp from distributing across GPUs
- `--main-gpu 0` ensures everything goes to the 4090
- Note: `--split-mode none` in EXTRA_ARGS overrides the docker-compose default
  `--split-mode layer` (EXTRA_ARGS is appended last, last flag wins)

**When to use:** Dense or MoE models where total VRAM footprint < ~23 GB
(leaving ~1.5 GB headroom on 4090).

**Example:** GLM-4.7-Flash Q4_K_M at 10K context (~17.5 GB total).

### Strategy B: Tensor Split (dense model, multi-GPU)

For dense models that don't fit on a single GPU. Use `--tensor-split` to
control the proportion on each GPU.

```
FIT=off
EXTRA_ARGS=... --tensor-split RATIO0,RATIO1
```

- `--tensor-split 3,1` = 75% on CUDA0, 25% on CUDA1
- Adjust ratio based on VRAM headroom after testing
- `--split-mode layer` (docker default) is correct here

**When to use:** Dense models > 23 GB that have no expert/attention distinction.

### Strategy C: Selective GPU split (MoE, fits on GPUs)

For MoE models where all layers (including experts) fit across both GPUs.
Use `-ot` regex to control which layers go where.

```
FIT=off
EXTRA_ARGS=... -ot blk\.([0-9]|1[0-9]|2[0-9])\.=CUDA0,blk\.(3[0-9])\.=CUDA1
```

No `exps=CPU` needed — all experts stay on GPU since they fit. GPU is always
faster than CPU for expert computation when the weights are already in VRAM.

**When to use:** MoE models where total weights fit in combined GPU VRAM
(24 + 12.5 ≈ 36.5 GB usable).

### Strategy D: GPU + CPU offloading (MoE, exceeds GPU VRAM)

For large MoE models that exceed total GPU VRAM. Use `-ot` with `exps=CPU`
to offload expert weights to system RAM.

```
FIT=off
EXTRA_ARGS=... -ot blk\.RANGE0\.=CUDA0,blk\.RANGE1\.=CUDA1,exps=CPU
```

**How `-ot` priority works:** Rules are evaluated left to right. The first
matching rule wins. So `blk\.([0-9])\.=CUDA0` takes priority over `exps=CPU`
for layers 0-9. This means:

- Layers matching CUDA0/CUDA1 rules: ALL tensors (attention + experts) on GPU
- Remaining layers: experts → CPU, attention → GPU (via `-ngl 99`)

This is the right trade-off because:
- Attention is used **every token** → keep on fastest device
- Experts are used **partially per token** (e.g., 4/64 = 6%) → CPU is acceptable
- CPU has plenty of capacity (64 GB) and the per-token expert computation is small

**When to use:** GPT-OSS 120B, Qwen3-Coder-Next, and any MoE model > 36.5 GB.

## Key principles

1. **Always verify architecture first.** Read the model card. Don't assume
   dense vs MoE from model name or file size.

2. **If it fits on GPU, keep it on GPU.** Expert weights in VRAM are accessed
   at ~1 TB/s. On CPU they require PCIe transfer (~32 GB/s). VRAM is only
   "wasted" if keeping experts there forces attention layers off GPU.

3. **Fill CUDA0 first, then CUDA1, then CPU.** The 4090 is the fastest device.
   Maximize its utilization before using the 5070 Ti.

4. **exps=CPU is a trade-off, not a default.** Only offload experts when GPU
   VRAM is insufficient. When experts fit on GPU, they run faster there.

5. **FIT=off for any manual placement.** FIT auto-distributes across all GPUs
   and doesn't account for expert/attention priorities correctly.

6. **Benchmark vs production have different VRAM budgets.** Benchmarks use
   smaller context (10K vs 128K-256K) and smaller batch sizes (512 vs 2048-4096).
   This frees significant VRAM, allowing more layers on GPU or even single-GPU
   operation for smaller models.

## Model quick reference

| Model | Type | Total params | Active/token | Experts | Layers | File sizes |
|-------|------|-------------|-------------|---------|--------|------------|
| GLM-4.7-Flash | MoE | 30B | 3B (A3B) | 64 per layer, 4 active + 1 shared | 47 (1 dense + 46 MoE) | Q4: 18 GB, Q8: 30 GB |
| GPT-OSS 120B | MoE | 116.8B | 5.1B | 128 per layer, 4 active | 36 (18 SWA) | F16: 61 GB |
| Qwen3-Coder-Next | MoE | 80B | 3B | 512 per layer, 10 active | 48 (75% DeltaNet) | Q5: 57 GB, Q6: 64 GB |

## Batch size strategy

`-b` (batch) and `-ub` (micro-batch) control prompt processing chunk size.
Larger values allocate bigger compute buffers in VRAM.

| Context | Use case | Recommended -b/-ub | Reason |
|---------|----------|-------------------|--------|
| Benchmark (10K) | HumanEval prompts (~400 tokens) | 512 | Tiny prompts, saves VRAM for more layers |
| Production (64K-256K) | Interactive chat, long prompts | 2048-4096 | Faster prompt ingestion for long inputs |

Savings from smaller batch: typically 2-4 GB per GPU in compute buffer VRAM.
At 10K context, this can free enough room for 1-4 additional layers on GPU.
