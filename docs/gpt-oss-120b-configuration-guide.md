# GPT-OSS 120B on Desktop: Configuration Guide & Findings

## Table of Contents

- [Hardware Setup](#hardware-setup)
- [The Model: What "F16" Actually Means](#the-model-what-f16-actually-means)
- [Architecture: Why MoE Makes This Possible](#architecture-why-moe-makes-this-possible)
- [Working Configuration](#working-configuration)
  - [What Each Parameter Does](#what-each-parameter-does)
  - [Docker Compose Configuration](#docker-compose-configuration)
- [Memory Breakdown](#memory-breakdown-final-config)
- [Performance Results](#performance-results)
- [What We Tried That Failed](#what-we-tried-that-failed)
- [Remaining Headroom & Optimization Ideas](#remaining-headroom--optimization-ideas)
- [DGX Spark Comparison](#dgx-spark-comparison)

---

## Hardware Setup

- **GPU 0:** NVIDIA GeForce RTX 4090 (24 GB VRAM) — Ada Lovelace, PCIe slot 0A:00
- **GPU 1:** NVIDIA GeForce RTX 5070 Ti (16 GB VRAM) — Blackwell, PCIe slot 0B:00 (display attached)
- **CPU:** AMD Ryzen 7 5800X3D (8 cores / 16 threads)
- **RAM:** 64 GB DDR4
- **OS:** Ubuntu 24, Docker with NVIDIA Container Toolkit

## The Model: What "F16" Actually Means

The file `gpt-oss-120b-F16.gguf` (60.87 GiB, 4.48 BPW) is NOT a true FP16 model. The "F16" label in GGUF naming means "no post-training quantization applied." The actual weight precision is:

- **Expert weights (bulk of model):** Native MXFP4 — this is what the model was *trained* in, not a lossy quantization
- **Attention layers and embeddings:** BF16
- **Total parameters:** 116.83B (128 experts per layer, 4 active per token, ~5.1B active per forward pass)

A true FP16 120B model would be ~240 GB. The 61 GB file size confirms the MXFP4 native precision. This means you get full training quality at a fraction of the memory cost — the key innovation that makes running 120B on consumer hardware feasible.

The 5070 Ti has native FP4 tensor cores (Blackwell architecture) and can process these weights at full speed. The 4090 (Ada) dequantizes MXFP4 on-the-fly, which is still fast but not hardware-native.

## Architecture: Why MoE Makes This Possible

GPT-OSS 120B is a Mixture of Experts model. Each of its 36 layers contains 128 experts, but only 4 are activated per token. This means:

- **Total model size:** ~61 GB on disk
- **Active parameters per token:** ~5.1B (comparable to a small model)
- **Memory access per token:** Only the router + 4 selected experts per layer need to be read

The critical optimization insight: expert weights are the bulk of the model but only a small fraction are used per token. This makes them ideal candidates for CPU offloading — they can sit in slower system RAM because only 4 of 128 need to be read each time.

The model also uses **sliding window attention (SWA)** on half its layers (18 of 36). SWA layers have a fixed tiny KV cache regardless of context length, which dramatically reduces memory needed for long contexts.

## Working Configuration

For a ready-to-use config, see `.env.gpt-oss-120b` in the project root. The key parameters:

```bash
MODEL=GPT-OSS-120b/gpt-oss-120b-F16.gguf \
CTX_SIZE=65536 \
FIT=off \
N_GPU_LAYERS=99 \
EXTRA_ARGS="--jinja -np 1 -b 4096 -ub 4096 \
  -ot blk\.([0-9]|1[01])\.=CUDA0,blk\.(1[2-5])\.=CUDA1,exps=CPU" \
docker compose up
```

### What Each Parameter Does

**`N_GPU_LAYERS=99`** — Tells llama.cpp to offload all 36 layers to GPU. Without the `-ot` override, this would OOM immediately. Combined with `-ot`, it ensures all attention layers stay on GPU while experts get selectively placed.

**`FIT=off`** — Disables llama.cpp's automatic memory fitting. Essential when using `-ot` overrides, because auto-fit doesn't account for the expert/attention split correctly and will either refuse to load or miscalculate.

**`-ot blk\.([0-9]|1[01])\.=CUDA0,blk\.(1[2-5])\.=CUDA1,exps=CPU`** — This is the key command. It uses regex-based tensor overrides to control exactly where each part of the model goes:

- `blk\.([0-9]|1[01])\.=CUDA0` → Layers 0-11 (all tensors including experts) → RTX 4090
- `blk\.(1[2-5])\.=CUDA1` → Layers 12-15 (all tensors including experts) → RTX 5070 Ti
- `exps=CPU` → All remaining expert weights → system RAM

The first two rules take priority over `exps=CPU`. So layers 0-15 keep their experts on GPU, while layers 16-35 have their experts offloaded to CPU. Attention for ALL 36 layers stays on GPU (via `-ngl 99`).

**`--jinja`** — Required for GPT-OSS. The model's chat template (handling system prompts, reasoning channels, tool calls) is written in Jinja format.

**`-np 1`** — One parallel slot. Each slot allocates its own KV cache, so 1 slot = 1x cache instead of the default 4x.

**`-b 4096 -ub 4096`** — Batch and micro-batch size for prompt processing. Per the official MoE offloading guide, larger batches enable "disaggregated prompt processing" where the GPU handles all prompt tokens in one shot by temporarily copying CPU weights to GPU. This significantly speeds up prompt ingestion for MoE models.

**`CTX_SIZE=65536`** — 64K token context window. Viable because of SWA reducing KV cache cost and q8_0 KV cache quantization (set in docker-compose.yml).

### Docker Compose Configuration

The docker-compose.yml sets additional defaults:
- `--flash-attn on` — Flash attention for memory-efficient attention computation
- `--cache-type-k q8_0 --cache-type-v q8_0` — Quantized KV cache (roughly halves KV memory vs FP16)
- `--split-mode layer` — Layer-based multi-GPU splitting
- `--main-gpu 0` — RTX 4090 as primary GPU

## Memory Breakdown (Final Config)

| Component | Location | Size |
|-----------|----------|------|
| Model weights (CPU experts) | System RAM (mmap) | 62,221 MiB |
| Model weights (layers 0-11 + embeddings + output) | CUDA0 (4090) | 20,456 MiB |
| Model weights (layers 12-15) | CUDA1 (5070 Ti) | 8,410 MiB |
| KV cache non-SWA (18 layers, 64k context) | CUDA0 + CUDA1 | 1,224 MiB |
| KV cache SWA (18 layers, fixed) | CUDA0 + CUDA1 | 81 MiB |
| Compute buffer | CUDA0 | 1,811 MiB |
| Compute buffer | CUDA1 | 3,187 MiB |
| Compute buffer | CPU | 1,182 MiB |

**Final VRAM usage:**
- RTX 4090: 23,602 / 24,564 MiB (96%)
- RTX 5070 Ti: 14,507 / 16,303 MiB (89%)

## Performance Results

| Config | Context | Layers on GPU | Token Gen Speed |
|--------|---------|---------------|-----------------|
| 10 layers CUDA0, 5 layers CUDA1, 4k ctx | 4,096 | 15 / 36 | 20.79 t/s |
| 12 layers CUDA0, 4 layers CUDA1, 64k ctx | 65,536 | 16 / 36 | 20.11 t/s |

The speed barely changed despite 16x more context — token generation speed for MoE is dominated by expert weight transfer from CPU, not KV cache size. The 64k config has 16 layers on GPU vs 15 in the 4k config (layers 10-11 added to CUDA0, layer 16 dropped from CUDA1), which explains the tiny speed decrease.

Longer test: 4,629 tokens generated in 230.15 seconds = 20.11 t/s sustained. Output was faster than reading speed — fully usable for interactive chat.

## What We Tried That Failed

1. **Auto-fit (`FIT=on`):** Calculated it needed 62 GB across GPUs, only had 37 GB. Refused to reduce layers, crash-looped.

2. **`--n-cpu-moe` with `--tensor-split`:** These two features interact poorly. `--tensor-split` assigns layers first, then `--n-cpu-moe` moves experts after — resulting in unpredictable GPU distribution where the smaller 5070 Ti got more load than the larger 4090.

3. **`-ot` with escaped regex through Docker:** Shell escaping of regex patterns like `blk\.\([0-9]\|1[0-9]\)` was unreliable through Docker environment variables. The backslash-escaped group syntax didn't work as expected.

4. **5 layers on CUDA1 with 64k context and -ub 4096:** The compute buffer for disaggregated prompt processing at ub=4096 needed 3.2 GB on CUDA1, which combined with 5 layers of model weights exceeded 16 GB. Reducing to 4 layers freed enough room.

## Remaining Headroom & Optimization Ideas

**CUDA1 has ~1.8 GB free.** The 5070 Ti could potentially fit another partial layer if compute buffer requirements were reduced (e.g., `-ub 2048` instead of 4096). Trade-off: slightly slower prompt processing for one more layer of experts on GPU.

**CPU thread count:** Currently using 8 threads. The 5800X3D has 16 threads — increasing `-t 16` might improve CPU expert processing speed, though HTTP server threads compete for the same cores.

**`--no-mmap`:** Could improve token generation consistency by loading all weights into RAM upfront rather than relying on page faults. Risk: 62 GB of CPU-mapped weights + OS overhead might exceed 64 GB physical RAM and cause swapping. Not recommended without more RAM.

**Context could go to 128k** by dropping 2 layers from GPU (back to the original 10+5 config). KV cache at 128k would be ~2.4 GB total (thanks to SWA + q8_0). Speed would remain around 20 t/s since the bottleneck is CPU expert bandwidth, not KV cache.

**`q4_0` KV cache** instead of q8_0 would halve KV memory, allowing either more context or more GPU layers. Quality impact for this model is not well documented.

## DGX Spark Comparison

| Metric | Desktop (4090 + 5070 Ti) | DGX Spark |
|--------|--------------------------|-----------|
| GPT-OSS 120B speed | ~20 t/s | 38-41 t/s (estimated) |
| Max context (practical) | 64k (128k possible) | 128k easily |
| VRAM/unified memory | 40 GB split across 2 GPUs | 128 GB unified |
| Expert placement | 16/36 layers GPU, 20 on CPU | All on unified memory |
| Bottleneck | CPU RAM bandwidth (~50 GB/s) | Memory bandwidth (~273 GB/s) |
| Price | Already owned | ~$3,000-4,000 |

The Spark's advantage on this model is ~2x speed, driven entirely by memory bandwidth — no PCIe bottleneck and no CPU-GPU transfers. The Spark handles 128k context without any configuration gymnastics.

However, for models that fit entirely in 40 GB VRAM (up to ~30B dense or ~60B MoE at Q4), the desktop is 2-3x *faster* than Spark due to higher GPU compute throughput. The Spark only wins when models exceed desktop VRAM.

**Bottom line:** If GPT-OSS 120B at 20 t/s with 64k context meets your needs, the desktop setup is remarkably capable for a model this size. The Spark's value proposition is primarily for training/fine-tuning (128 GB unified memory for LoRA on 24-70B models) and for consistently running models in the 70-120B range without the configuration complexity shown here.
