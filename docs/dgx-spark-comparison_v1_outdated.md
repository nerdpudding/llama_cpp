# DGX Spark: When Is It Worth It?

I already have a dual-GPU desktop (RTX 4090 + RTX 5070 Ti) that lets me do some genuinely cool things with AI locally — running language models, generating images and video, doing speech recognition, and more. As a developer, I find it both challenging and fun to push consumer hardware and see what's possible. But as my needs evolve toward larger models, multi-model pipelines, and fine-tuning, I'm increasingly hitting the limits of what 40 GB of VRAM and 64 GB of DDR4 system memory can do. The natural next step is more capable hardware — but "more capable" is expensive, and even with unlimited budget, buying something without knowing whether it actually fits the workflow would be a waste.

So I set out to answer a specific question: would a DGX Spark be a worthwhile addition to (or replacement for) my current setup? This document compares my desktop against the Spark and other devices (Jetson Thor, Mac Mini M4 Pro) using a mix of self-run benchmarks and data from [this YouTube video](https://youtu.be/PhJnZnQuuT0), to figure out when the Spark justifies its price — and when it doesn't.

## Executive summary

**When the Spark is worth it:**
- Running large models (>40 GB) that don't fit in GPU VRAM — the Spark's 128 GB unified memory eliminates the crippling overflow to slow system RAM that makes desktop inference unusable or painfully slow
- Large MoE models like GPT-OSS 120B: 52.8 t/s on the Spark vs 19.7 t/s on the desktop (2.7x faster). Not just usable — genuinely fast
- Multi-model workflows (LLM + image generation + vision + speech) that together exceed 40 GB
- Fine-tuning models larger than ~7B, where gradients and optimizer states push memory far beyond GPU VRAM
- Always-on, quiet operation at 150-240W total instead of 700W+ for a desktop under load
- Serving multiple users from a single device

**When it's not worth it:**
- Models that fit on a single GPU — the RTX 4090 at ~1 TB/s bandwidth is 4x faster than the Spark's 273 GB/s. For anything under ~24 GB, the desktop wins easily
- Pure compute tasks (image/video generation, gaming) where TFLOPS and bandwidth matter more than memory capacity
- If the use cases above are occasional rather than central to the workflow — €4,500 is a lot for something used once a week

**The honest answer:** the Spark fills real gaps where the desktop struggles, but those gaps have to matter enough to justify the cost. For someone regularly working with large models, multi-model pipelines, or fine-tuning, it's a strong investment. For someone mostly running models that fit on a GPU, it's expensive overkill.

## Table of Contents

- [Executive summary](#executive-summary)
- [Background concepts](#background-concepts)
  - [Dense vs Sparse (MoE) models](#dense-vs-sparse-moe-models)
  - [Unified memory vs dedicated VRAM](#unified-memory-vs-dedicated-vram)
  - [Two types of inference speed](#two-types-of-inference-speed)
  - [Compute performance (TFLOPS)](#compute-performance-tflops)
  - [Precision formats: trained as, stored as, computed with](#precision-formats-trained-as-stored-as-computed-with)
- [Devices compared](#devices-compared)
- [Benchmark tests](#benchmark-tests)
  - [Test methodology](#test-methodology)
  - [Test 1: Small MoE — Ministral-3 8B](#test-1-small-moe--ministral-3-8b)
  - [Test 2: Large dense — Llama 3.3 70B](#test-2-large-dense--llama-33-70b)
  - [Test 3: Large MoE FP4 — GPT-OSS 120B](#test-3-large-moe-fp4--gpt-oss-120b)
  - [Results summary](#results-summary)
- [What the benchmarks don't cover](#what-the-benchmarks-dont-cover)
- [Concurrent users and multi-model workflows](#concurrent-users-and-multi-model-workflows)
- [Training and fine-tuning](#training-and-fine-tuning)
- [The hardware alternatives](#the-hardware-alternatives)
- [Decision tree: what do you actually want?](#decision-tree-what-do-you-actually-want)
- [Conclusions](#conclusions)

---

## Background concepts

### Dense vs Sparse (MoE) models

**Dense models** (e.g., Llama 3.3 70B) activate ALL parameters for every token. If a model has 70 billion parameters, all 70B are used for every single word it generates. This means enough memory to hold the entire model and enough bandwidth to read it all for each token.

**Sparse / MoE models** (Mixture of Experts, e.g., GPT-OSS 120B, Ministral-3) have a large total parameter count but only activate a small fraction per token. GPT-OSS 120B has 116.8B total parameters but only ~5.1B are active per token.

How MoE works: the model contains many specialized sub-networks called **experts** — each one good at different kinds of patterns. A small **router** network decides which experts to activate for each token. The router and a few shared layers (attention, embeddings) are always active, but the vast majority of the model (the experts) sits idle for any given token. Only the handful of selected experts do actual work.

**Why this matters for memory:**

| | Dense | Sparse (MoE) |
|---|---|---|
| Memory to load | All parameters | All parameters (same or more) |
| Compute per token | All parameters | Only active experts (much less) |
| Speed when fully in memory | Bandwidth-limited | Very fast (less data to read per token) |
| Speed with partial CPU offload | Terrible (must read everything from slow memory) | Manageable — see below |
| Quality | Consistent | Can vary — depends on router quality and expert selection |

**Why MoE handles CPU offload better:** In a dense model, every parameter is needed for every token — if half the model is on slow CPU memory, the GPU stalls waiting for data on every single token. There's no avoiding it. In an MoE model, only the expert weights need to be accessible (and only the active ones per token). The router and shared layers — which are small — can stay on fast GPU memory permanently. The expert weights that don't fit can be placed on CPU, and for any given token only a few of them need to be fetched. This doesn't make CPU offload *fast*, but it makes it functional rather than catastrophic. The desktop's 19.7 t/s on GPT-OSS 120B (test 3) vs 1.29 t/s on Llama 70B (test 2) demonstrates this dramatically — same hardware, similar model sizes, but MoE architecture makes CPU offload 15x more tolerable.

Is it always faster when everything fits on VRAM? Yes. GPU memory is always better — the MoE advantage is specifically about making the *best of a bad situation* when the model doesn't fully fit. If the Spark's 128 GB unified memory holds the entire model, there's no offload penalty at all, which is why it reaches 52.8 t/s on GPT-OSS 120B.

### Unified memory vs dedicated VRAM

**Dedicated VRAM** (like the RTX 4090's 24 GB GDDR6X) is memory physically on the GPU. It's extremely fast (~1 TB/s on the 4090) but limited in size. When a model doesn't fit, the overflow goes to system RAM (DDR4/DDR5) over PCIe, which is dramatically slower (~50 GB/s for DDR4).

**Unified memory** (like the DGX Spark's 128 GB LPDDR5X) is shared between CPU and GPU with a single memory pool. There's no "overflow" to slow memory — everything is equally accessible at the same speed (273 GB/s). The downside: 273 GB/s is slower than dedicated VRAM (~1 TB/s), so when a model fits entirely on a discrete GPU, the GPU wins.

**Rule of thumb:**
- Model fits on GPU VRAM → dedicated GPU wins (fastest possible)
- Model doesn't fit on GPU VRAM → unified memory wins (no slow overflow penalty)
- The bigger the overflow to CPU RAM, the bigger the unified memory advantage

### Two types of inference speed

There are two distinct speed metrics in LLM inference, and they are bottlenecked by different things:

**Prompt eval rate** (prompt processing) is how fast the model reads and processes the input — the system prompt, conversation history, and user message. This happens before any output appears. It's computation-heavy and benefits from parallelism (processing many tokens at once in batches).

- *When it's noticeable:* Long system prompts, large documents pasted into chat, long conversation history. A slow prompt eval rate means a long pause before the first word appears (time-to-first-token).
- *When it isn't:* Short prompts, quick questions. At 44 t/s with a 100-token prompt, the wait is 2.3 seconds. At 977 t/s, it's 0.1 seconds. Both feel instant.

**Eval rate** (token generation) is how fast the model generates new tokens — the actual response. This is the speed visible as the text streams in. It's limited by memory bandwidth because the model must read weights for each token.

- *When it's noticeable:* Always. This is the typing speed of the response.

**What speed "feels like" is subjective.** Below ~5 t/s feels painfully slow for most people. In my experience, around 15-20 t/s is where chat becomes comfortable — roughly the speed of reading the words as they appear. Between 30 and 100 t/s feels fluid and responsive. Above 100 t/s the text appears nearly instantly.

But this is personal preference and depends on the task. For interactive chat, the streaming speed matters because you're watching it arrive in real time. For batch code generation, API calls, or background tasks, what matters is total completion time — the speed is invisible. Someone used to fast responses might find 20 t/s sluggish; someone else might find it perfectly fine. There's also something to be said for a pace that lets you read along as it generates — extremely fast output can actually be harder to follow in a chat context.

**For training:** Neither metric directly applies. Training processes tokens in large batches in both directions (forward and backward pass). Training speed depends on raw compute (TFLOPS), memory capacity (must hold model + gradients + optimizer states), and memory bandwidth (reading weights and gradients). Dedicated GPUs with large VRAM (A100, H100) dominate training because they have both high bandwidth and large capacity.

### Compute performance (TFLOPS)

Raw compute power — measured in TFLOPS (trillion floating-point operations per second) — matters for different workloads than memory bandwidth does.

| Device | FP32 | FP16 Tensor | FP8 Tensor (sparse) | FP4 Tensor (sparse) | Notes |
|--------|------|-------------|---------------------|---------------------|-------|
| RTX 4090 | 82.6 | 165 | 660 | — | No native FP4. Ada Lovelace, 4th gen Tensor Cores |
| RTX 5090 | 104.8 | 209 | 838 | ~3,352 | Blackwell, 5th gen Tensor Cores |
| DGX Spark GB10 | — | — | — | ~1,000 | Marketed as "1 PFLOP AI performance" |
| Jetson Thor | — | — | — | ~2,070 | Blackwell, 96 Tensor Cores |

**A note on the Spark's numbers:** NVIDIA markets the DGX Spark as "1 PFLOP" (1,000 TFLOPS) of AI performance. This is the peak FP4 sparse figure — the highest possible number at the lowest precision with structured sparsity optimizations. FP32, FP16, and FP8 figures for the Spark's GB10 chip are not widely published, but they would be substantially lower (as with any GPU, lower precision = higher throughput). For comparison, the RTX 5090's ~3,352 TFLOPS FP4 sparse figure is over 3x the Spark's — consumer GPUs can have more raw compute power than the Spark for workloads that fit in their memory.

**When compute matters:**
- **Training and fine-tuning:** Training is compute-bound. More TFLOPS = faster training. The RTX 4090 and 5090 have significantly more raw FLOPS than the Spark, making them actually better for training *when the model fits in VRAM*. The Spark's advantage for training is memory capacity (128 GB), not compute speed.
- **Batch inference / many concurrent users:** Processing many requests in parallel benefits from both compute and memory. More TFLOPS helps with throughput.
- **Image/video generation (diffusion models):** Highly compute-intensive. The RTX 4090's 82.6 TFLOPS FP32 and 660 TFLOPS FP8 Tensor make it excellent for this. The Spark can run these workloads too but with lower raw throughput.

**When compute doesn't matter much:**
- **Single-user LLM inference (what these benchmarks measure):** Token generation for one user is memory-bandwidth-limited, not compute-limited. The GPU spends most of its time reading model weights from memory, not doing math. This is why the 4090 with ~1 TB/s bandwidth dominates small models despite having "only" 82.6 TFLOPS — it can feed data to the GPU fast enough. The Spark's 1,000 TFLOPS of FP4 compute is largely idle during single-user inference because the 273 GB/s bandwidth can't keep the compute units fed.

### Precision formats: trained as, stored as, computed with

**What "floating point" precision means:** Numbers in a computer are stored with limited precision. FP16 uses 16 bits per number, FP8 uses 8 bits, FP4 uses 4 bits. Fewer bits means: less storage space (a model in FP4 is ~4x smaller than FP16), faster to move through memory (less data to read), but less numerical precision (the numbers are rougher approximations). The tradeoff is quality vs efficiency — fewer bits means faster and smaller, but the model's outputs become slightly less precise. Modern quantization techniques (Q4_K_M, Q6_K, etc.) are surprisingly good at preserving quality even at 4-6 bits per weight.

There are three different things that can each use different precision:

1. **Trained as** — the precision used during training (when the model was created). GPT-OSS 120B was trained using FP4 (MXFP4) natively. Most other models are trained in FP16 or BF16.
2. **Stored as** — the precision of the weights in the model file. A model trained in FP16 can be *quantized* (compressed) to Q4, Q5, Q6, Q8 etc. for smaller file size. GPT-OSS 120B is stored as F16 in the GGUF file, but the original weights are FP4 — the F16 file just preserves the FP4 values at higher precision for compatibility.
3. **Computed with** — the precision the GPU actually uses when doing the math during inference. This depends on what the *hardware* supports.

**The key distinction:** whether a GPU has native FP4 *compute* support is a completely separate question from whether a model's weights are in FP4.

- **RTX 4090 (Ada Lovelace):** Has FP8 Tensor Cores but **no native FP4 compute**. It can still *run* a model with FP4 weights — the inference runtime (llama.cpp) loads the FP4 values and converts them to a format the GPU can compute with (FP16 or FP8). This works fine, but the GPU does extra conversion work and can't take full advantage of the smaller data size for computation.
- **RTX 5090 / DGX Spark / Jetson Thor (Blackwell):** Have **native FP4 Tensor Cores**. They can directly compute with FP4 data without conversion. This is more efficient — fewer bytes to move, faster math, less power.

**In simple terms:** Think of it like a document written in French. Anyone can read it if they first translate it to English (that's the 4090 running FP4 — it works, but there's overhead). A native French speaker reads it directly without translation (that's Blackwell running FP4 — faster, more efficient). The document is the same; the difference is in the reader's capability.

This also means that as more models are released in FP4 or lower precision formats, Blackwell hardware (Spark, 5090, Jetson Thor) will have an increasing advantage over older architectures like Ada Lovelace — not just in memory capacity, but in computational efficiency per watt.

---

## Devices compared

| Device | CPU | GPU/Accelerator | Memory | Bandwidth | Power supply | Price range |
|--------|-----|-----------------|--------|-----------|-------------|-------------|
| **My desktop** | AMD Ryzen 7 5800X3D (8C/16T) | RTX 4090 (24 GB) + RTX 5070 Ti (16 GB)* | 40 GB VRAM + 64 GB DDR4 | ~1 TB/s (4090), ~896 GB/s (5070 Ti), ~50 GB/s (DDR4) | 1200W PSU | ~$3,500-4,000 (GPUs + system) |
| DGX Spark | 20-core ARM (10x Cortex-X925 + 10x Cortex-A725) | Blackwell GB10 (6,144 CUDA cores) | 128 GB unified LPDDR5X | 273 GB/s | 240W external | ~$3,000 (~€4,000-4,500 in EU) |
| Jetson Thor | 14-core ARM Neoverse V3AE @ 2.6 GHz | Blackwell (2,560 CUDA cores, 96 Tensor cores) | 128 GB unified LPDDR5X | 273 GB/s | 40-130W configurable | ~$3,500 (dev kit) |
| Mac Mini M4 Pro | 14-core Apple Silicon (10P+4E) | 20-core Apple GPU (integrated) | 64 GB unified LPDDR5X | 273 GB/s | 96W adapter | ~$2,000 |

*\*The RTX 4090 (Ada Lovelace, sm_89) and RTX 5070 Ti (Blackwell, sm_120) are different GPU architectures. Their VRAM cannot be pooled into a single 40 GB address space — each GPU has its own separate memory. To use both GPUs together, the model must be split into layers and specific layers assigned to each GPU (layer offloading). This works in llama.cpp (via `-ot` regex rules for per-layer placement) and ollama (which wraps llama.cpp), but requires manual configuration and testing to find optimal splits. It adds complexity, inter-GPU transfer overhead, and limits flexibility compared to a single large memory pool. See `docs/gpu-strategy-guide.md` for details on how this works in practice.*

**Mac Mini note:** The Mac Mini M4 Pro with 64 GB is included because it appeared in the source video. Mac Minis with more memory (M4 Max with 128 GB) exist and would perform better on the larger models. However, the Apple ecosystem has limitations for AI development beyond inference: no CUDA support (many AI tools and training frameworks depend on it), limited to macOS (no native Ubuntu/Linux), and the higher-memory configurations ($3,000-4,000+) approach Spark pricing. For running ollama and similar inference tools, Macs work well. For training, CUDA-dependent workflows, or the broader Linux AI ecosystem, they're more restrictive.

**About the DGX Spark's compute capability:** The Spark uses NVIDIA's Blackwell architecture with full CUDA support, meaning it runs the same software stack (CUDA, TensorRT, PyTorch with CUDA backend) as desktop GPUs. This is a significant advantage over Apple Silicon for development — code written for CUDA on a desktop works on the Spark without modification. The Spark's compute throughput (1,000 TFLOPS FP4) is lower than the RTX 5090's (~3,352 TFLOPS FP4), but its 128 GB unified memory means it can run workloads that no consumer GPU can fit in VRAM.

OEM variants of the DGX Spark exist from ASUS, HP, Lenovo and others. Most are priced similarly or make compromises (smaller SSD, less storage). The base NVIDIA unit ships with 4 TB SSD.

### Data sources

- **DGX Spark, Jetson Thor, Mac Mini:** Results from [this YouTube video](https://youtu.be/PhJnZnQuuT0). Power measured at the wall (whole device).
- **My desktop:** Tested locally on 2026-02-15. Power measured via nvidia-smi (GPU only — the full PC draws significantly more when including CPU, motherboard, fans, SSD, etc.).

---

## Benchmark tests

All tests used the same prompt and measure single-user inference only (not concurrent).

### Test methodology

**Test prompt (used for all tests):**

> Design a weekend trip itinerary for two people visiting Tokyo for the first time. Include where to stay, what to see each day, where to eat, and estimated budget in yen.

Requires reasoning about logistics, recommendations, and budgeting. Produces ~400-2800 tokens depending on model, enough for stable speed measurement.

**Key metrics:**
- **Eval rate** (token generation) — the speed at which new tokens (the answer) are generated. Limited by memory bandwidth. This is what determines how fast the response streams in.
- **Prompt eval rate** (prompt processing) — the speed at which the input prompt is processed before generation starts. Computation-heavy. Determines time-to-first-token.

**Inference software:**

All tests — both the desktop and the devices from the video — used **ollama** for inference, except for the GPT-OSS 120B test on the desktop which used **llama.cpp** directly.

Ollama is essentially a wrapper around llama.cpp that simplifies model management. llama.cpp offers more fine-grained control — crucially, it supports mixed multi-GPU tensor placement via `-ot` regex rules, which is essential for the asymmetric dual-GPU setup (24 GB + 16 GB). Ollama doesn't expose this level of control.

Other inference runtimes exist that could produce different results: **TensorRT-LLM** (NVIDIA's optimized runtime, often faster but more complex to set up), **SGLang**, **vLLM** (both optimized for multi-user serving with features like continuous batching), and others. These are not included in this comparison, but could influence absolute numbers. Since both sides of this comparison used the same runtime (ollama/llama.cpp), the relative performance differences between devices are a fair indication of the hardware gap. Absolute numbers could differ with other runtimes, but the ratios (e.g., "Spark is 2.7x faster") would remain similar because the bottleneck is hardware (memory bandwidth, compute), not software.

### Test 1: Small MoE — Ministral-3 8B

Sparse MoE model, `ministral-3:8b-instruct-2512-q4_K_M`, 6 GB file size. Fits entirely on a single GPU.

| Device | VRAM/RAM | Power | Eval rate | Prompt eval rate |
|--------|----------|-------|-----------|-----------------|
| **My desktop (RTX 4090 only)** | **9,270 MiB** | **366W (GPU)** | **147.07 t/s** | **7,927.71 t/s** |
| Mac Mini M4 Pro | ? | 140W (wall) | 39.76 t/s | 353.25 t/s |
| DGX Spark | 7,086 MiB | 70W (wall) | 34.97 t/s | 2,406.82 t/s |
| Jetson Thor | ? | 90W (wall) | 30.82 t/s | 1,037.67 t/s |

**Desktop wins by a landslide.** A small model that fits entirely on the RTX 4090 runs at ~1 TB/s bandwidth — 4.2x faster eval rate than the Spark and 3.3x faster prompt eval. This is where dedicated VRAM shines: when the model fits, nothing beats a high-end discrete GPU.

Desktop tested with: ollama, model fully on RTX 4090.

### Test 2: Large dense — Llama 3.3 70B

Dense model, `llama3.3:70b-instruct-q4_K_M`, 43 GB file size. Does NOT fit on GPU alone — the desktop requires CPU offload. The Spark, Jetson, and Mac Mini load it entirely in unified memory.

| Device | VRAM/RAM | Power | Eval rate | Prompt eval rate |
|--------|----------|-------|-----------|-----------------|
| Mac Mini M4 Pro | 56.87 GB | 75W (wall) | 5.43 t/s | 34.00 t/s |
| Jetson Thor | ? | 100W (wall) | 4.61 t/s | 104.00 t/s |
| DGX Spark | 42,318 MiB | 150W (wall) | 4.46 t/s | 283.00 t/s |
| **My desktop (4090+5070Ti+CPU)** | **19,849+10,555 MiB** | **137W (GPU only)** | **1.29 t/s** | **19.48 t/s** |

**Desktop is unusable.** At 1.29 t/s a 500-token response takes over 6 minutes. Not viable for interactive chat, and not practical for most other tasks either. The bottleneck is DDR4 system RAM (~50 GB/s): because this is a dense model, every token needs all 70B parameters, and the parameters that don't fit on GPU must come from slow system memory.

The Spark at 4.46 t/s and Mac Mini at 5.43 t/s are significantly faster (3.5-4.2x) thanks to unified memory keeping the entire model accessible at 273 GB/s. But to be realistic: 4-5 t/s is still slow. It's not pleasant for interactive chat. It is functional for tasks where waiting is acceptable — batch processing, one-off questions, background generation — but it's not fast. The desktop at 1.29 t/s isn't functional at all. The Spark turns "impossible" into "slow but usable," not "impossible" into "good."

Desktop tested with: ollama, KV cache q8_0, 40/81 layers on GPU, 32K context.

### Test 3: Large MoE FP4 — GPT-OSS 120B

Sparse MoE model, ~61 GB file size, native FP4 weights. 116.8B total parameters but only ~5.1B active per token.

On the DGX Spark and Jetson Thor, this model fits entirely in their 128 GB unified memory — no offloading needed, everything runs at 273 GB/s. On the desktop, the model exceeds the 40 GB combined GPU VRAM, so the expert weights are offloaded to CPU RAM (DDR4, ~50 GB/s). The core layers (router, attention, embeddings) stay on GPU for fast processing, while inactive expert weights shuttle between CPU and GPU over PCIe for each token.

| Device | VRAM/RAM | Power | Eval rate | Prompt eval rate |
|--------|----------|-------|-----------|-----------------|
| DGX Spark | ? | ? | 52.77 t/s | 977.00 t/s |
| Jetson Thor | ? | ? | 34.97 t/s | 464.00 t/s |
| **My desktop (4090+5070Ti+CPU)** | **22,709+12,179 MiB** | **162W (GPU only)** | **19.70 t/s** | **44.30 t/s** |
| Mac Mini M4 Pro | — | — | Not possible | (64 GB max RAM) |

**This is where the Spark genuinely wins.** The Spark at 52.77 t/s is 2.7x faster than the desktop's 19.70 t/s. Unlike test 2, this isn't just turning "broken" into "barely usable" — the desktop already manages an acceptable 19.7 t/s for chat. The Spark takes that to genuinely fast (52.8 t/s). That's a meaningful quality-of-life difference: responses come 2.7x faster, longer conversations feel more fluid, and the prompt eval gap (977 vs 44 t/s, 22x faster) means dramatically shorter time-to-first-token on long prompts.

Why doesn't the desktop lose as badly here as in test 2? MoE architecture. Only the inactive expert weights need to come from slow CPU memory. The attention layers, router, and currently-active experts stay on GPU where bandwidth is high. With a dense model like Llama 70B, ALL parameters must pass through the slow memory path for every token. MoE models are fundamentally better suited to split-memory setups (see the [background section on MoE](#dense-vs-sparse-moe-models) for why).

Desktop tested with: llama.cpp, 128K context, 11+3=14/36 GPU layers, -b 2048, exps=CPU.

### Results summary

#### Eval rate (token generation, t/s)

| Model type | My desktop | DGX Spark | Jetson Thor | Mac Mini | Desktop vs Spark |
|------------|-----------|-----------|-------------|----------|-----------------|
| Small MoE (8B, fits on GPU) | **147.07** | 34.97 | 30.82 | 39.76 | **4.2x faster** |
| Large dense (70B, CPU offload) | 1.29 | 4.46 | 4.61 | **5.43** | **3.5x slower** |
| Large MoE FP4 (120B, CPU offload) | 19.70 | **52.77** | 34.97 | — | **2.7x slower** |

#### Prompt eval rate (prompt processing, t/s)

| Model type | My desktop | DGX Spark | Jetson Thor | Mac Mini | Desktop vs Spark |
|------------|-----------|-----------|-------------|----------|-----------------|
| Small MoE (8B, fits on GPU) | **7,927.71** | 2,406.82 | 1,037.67 | 353.25 | **3.3x faster** |
| Large dense (70B, CPU offload) | 19.48 | **283.00** | 104.00 | 34.00 | **14.5x slower** |
| Large MoE FP4 (120B, CPU offload) | 44.30 | **977.00** | 464.00 | — | **22x slower** |

---

## What the benchmarks don't cover

The tests above only cover LLM text inference. Real-world AI development involves many other workloads that could change the picture:

- **Image generation** (diffusion model workflows) — these benefit heavily from VRAM and GPU compute. A 4090 is excellent here, but complex workflows with multiple models (base model + control networks + upscaler + adapters) can easily exceed 24 GB.
- **Video generation** — extremely VRAM-hungry. Even short clips can need 20-40+ GB. Currently a struggle on the desktop.
- **Audio generation and music** — moderate memory needs but adds up when running alongside other models.
- **Speech-to-text / text-to-speech** — smaller models individually, but they accumulate in a pipeline.
- **Object recognition and computer vision** — typically smaller models but constant VRAM usage when running as a service.

Each of these individually might fit on a GPU. The challenge is running them **together** — an agentic workflow that orchestrates an LLM, an image generator, a speech recognizer, and a vision model simultaneously can quickly exhaust 24-40 GB of VRAM. The Spark's 128 GB unified memory pool could be a real advantage there, even if each individual model runs slower than on a 4090.

These workloads are not included in the benchmarks, but they can definitely influence the value proposition. The data presented here focuses on what was actually measured; the full picture is broader.

---

## Concurrent users and multi-model workflows

This is one of the Spark's less obvious but potentially most compelling advantages.

### Single-user vs multi-user serving

All the benchmark tests above measure single-user, single-model inference. That's the simplest case. In practice, the picture changes with multiple users or models:

**Memory per user:** Each active user session needs its own KV cache (the model's "working memory" for the conversation context). For a large model with 128K context, this can be several GB per user. The model weights are shared — they're loaded once — but KV cache scales with the number of active sessions.

**On the desktop (40 GB VRAM):** One large model already fills the GPUs. A second user either queues behind the first (each request processed sequentially, doubling latency) or a second, smaller model must be loaded. Loading/unloading models is slow (30-120 seconds for large models). There's no practical way to serve 3-4 users simultaneously with a large model.

**On the Spark (128 GB unified):** The model weights load once. With remaining memory, multiple KV caches can coexist. For a 60 GB model, that leaves ~60 GB for KV caches, system overhead, and potentially additional models. Serving 3-4 users from a single model is feasible.

### Does speed degrade with multiple users?

Yes — bandwidth is shared. The 273 GB/s is split across all active requests. Two simultaneous users would each get roughly half the per-user throughput. So the Spark's 52.8 t/s on GPT-OSS 120B would drop to roughly ~25 t/s per user with two concurrent users — still very usable.

On the desktop, the situation is worse: with requests queued sequentially, the second user simply waits for the first to finish. There's no parallelism benefit.

Inference servers like **vLLM** and **SGLang** are specifically designed for multi-user serving — they use techniques like continuous batching (processing tokens from multiple requests together to better utilize compute) and PagedAttention (efficiently managing KV cache memory). These could improve multi-user throughput on the Spark compared to a basic ollama setup. They're not tested here, but they're worth exploring for anyone who needs to serve multiple users.

### Multi-model coexistence

Running multiple models simultaneously (e.g., an LLM for chat + a vision model for image analysis + a speech model for voice input) requires enough memory for all models at once. On the desktop, this typically means loading/unloading models as needed (slow) or being limited to small models. On the Spark, several medium-sized models can stay resident simultaneously, enabling responsive agentic workflows that switch between models without the loading penalty.

---

## Training and fine-tuning

Training a model requires storing not just the model weights, but also:
- **Gradients** — same size as the weights
- **Optimizer states** — 2-3x the weights for Adam (momentum + variance)

A 7B model in FP32 needs ~28 GB for weights alone. Add gradients (~28 GB) and optimizer states (~56 GB) and the total is ~112 GB — far beyond what 40 GB of VRAM can hold. Even with LoRA (which trains only a small fraction of parameters), larger base models still need to be loaded in full.

| Training scenario | Desktop (24 GB 4090) | DGX Spark (128 GB) |
|------------------|---------------------|-------------------|
| LoRA fine-tune 7B model | Works (fits in VRAM) | Works |
| LoRA fine-tune 13B model | Tight, needs tricks (4-bit base) | Comfortable |
| Full fine-tune 7B model | Not possible (>100 GB needed) | Possible |
| Full fine-tune 13B+ model | Not possible | Tight but feasible with QLoRA |

The alternative on a desktop is cloud computing (AWS, RunPod, Lambda Labs), which works but has its own downsides: cost per hour adds up, setup overhead for each session, data leaves the machine (privacy/security), and availability depends on demand.

---

## The hardware alternatives

The DGX Spark is not the only option. But every alternative has significant trade-offs.

### Option 1: Add an RTX 5090 (~€3,200+, trending higher)

The RTX 5090 has 32 GB GDDR7 at ~1.8 TB/s — even faster than the 4090. Adding it to the desktop would give ~56 GB total VRAM (5090 + 4090) or ~48 GB (5090 + 5070 Ti). That's a meaningful upgrade.

**But:** The 5090 is extremely hard to get at MSRP (~€2,100). Real street prices in Europe are €3,200+ as of early 2026, with analysts predicting €3,800-5,000 later in 2026 due to GDDR7 shortages and AI-driven demand. A 70B dense model at Q4 is 43 GB — it barely fits on 48 GB and leaves no room for KV cache. Multi-model workflows still overflow to CPU. A large PSU is needed (the 5090 alone draws 575W), plus good airflow and a case that fits it. At €3,200+ for a single GPU, the cost approaches Spark territory but with 3x less memory.

### Option 2: Used professional GPUs (A6000/48 GB, A100/80 GB)

More VRAM per card, but significantly more expensive than expected:
- **A6000 (48 GB):** Hard to find as used purchase; mostly available as cloud rental (~€0.30-2.50/hr). Slower than a 4090 for inference (Ampere, not Ada). Older CUDA architecture.
- **A100 (80 GB):** ~€9,000-16,000 used (not the bargain it might seem — HBM2e memory retains value and AI demand keeps prices high). Great for training and inference, but needs a workstation motherboard, ECC RAM, proper cooling. The "rest of system" cost adds €1,000-3,000+.
- **Trust:** Used pro GPUs from data centers may have been run hard 24/7. No warranty. Hard to verify condition.
- **Architecture:** Older CUDA compute capability (Ampere) means newer features (FP4 Tensor cores, Blackwell optimizations) aren't available.

### Option 3: Cloud computing

No upfront cost, pay per hour. Good for occasional training jobs or testing.

**But:** Costs accumulate quickly with regular use. An A100 on RunPod is ~€2/hour — 100 hours of fine-tuning/experimentation already costs as much as a Spark. Plus: data leaves the machine, sessions need setup, availability isn't guaranteed, and there's latency for interactive use.

### Option 4: DGX Spark (~€4,000-4,500 in EU)

All-in-one device. 128 GB unified memory, 240W total, near-silent, Blackwell architecture.

**But:** It's expensive for an individual. That's a significant investment that could instead be a 5090 + a year of cloud credits. The 273 GB/s unified bandwidth is slower than dedicated VRAM for models that fit on a GPU. And for pure GPU-compute tasks that need raw FLOPS, a desktop GPU is better.

OEM variants (ASUS, HP, Lenovo) exist but are similarly priced or make compromises (smaller SSD, different thermals).

### Comparison at a glance

| Factor | Add RTX 5090 | Used A6000/A100 | Cloud | DGX Spark |
|--------|-------------|-----------------|-------|-----------|
| Cost | €3,200+ (rising) | €9,000-16,000 (A100 80GB) | €2/hr+ | €4,000-4,500 |
| Total memory | 48-56 GB VRAM | 48-80 GB VRAM | 40-80 GB (rental) | 128 GB unified |
| Bandwidth | ~1.8 TB/s (5090) | ~2 TB/s (A100) | Varies | 273 GB/s |
| Power | +575W GPU alone | +250-400W GPU | N/A | 240W total system |
| Training headroom | Limited (LoRA ≤13B) | Good (if 80 GB) | Good | Good (128 GB) |
| Multi-model workflows | Still tight | Better | Flexible | Best (128 GB pool) |
| Privacy/offline | Yes | Yes | No | Yes |
| Other system costs | PSU upgrade, cooling | Workstation board, ECC RAM | None | None (all-in-one) |
| Noise | Significant | Significant | N/A | Near-silent |
| Risk | None (new) | Used hardware risk | Vendor lock-in | None (new) |

---

## Decision tree: what do you actually want?

```
What's the primary goal?
│
├── Run small/medium LLMs that fit on one GPU (<24 GB)?
│   └── KEEP THE CURRENT DESKTOP. Nothing to buy.
│       Fast (~100-150 t/s), cheapest option, already owned.
│
├── Run large LLMs (>40 GB) interactively?
│   ├── Dense models (Llama 70B, Qwen 72B)?
│   │   └── SPARK or MAC MINI — but manage expectations
│   │       4-5 t/s is usable but slow. Desktop is unusable (<2 t/s).
│   │       Mac Mini is cheaper if 64 GB is enough.
│   │
│   └── MoE models (GPT-OSS 120B, Qwen3-Coder)?
│       ├── ~20 t/s is acceptable?
│       │   └── KEEP THE CURRENT DESKTOP. It works.
│       │
│       └── Want ~50 t/s (genuinely fast)?
│           └── SPARK wins convincingly here.
│
├── Run multi-model workflows (LLM + image gen + vision + STT/TTS)?
│   ├── Models fit in combined GPU VRAM?
│   │   └── DESKTOP is fine — dedicated VRAM is fastest.
│   │
│   └── Total memory exceeds ~40 GB?
│       └── SPARK (128 GB shared pool, no overflow penalty)
│           Or RTX 5090 as compromise (48-56 GB, faster but still a ceiling).
│
├── Fine-tune or train models?
│   ├── Small models (≤7B) with LoRA?
│   │   └── DESKTOP GPU works fine (fits in 24 GB VRAM).
│   │
│   ├── Medium models (7-13B) or aggressive LoRA?
│   │   └── SPARK or CLOUD — desktop VRAM is too tight.
│   │       Spark for regular use, cloud for occasional jobs.
│   │
│   └── Large models (>13B) or full fine-tuning?
│       └── CLOUD or SPARK — nothing else is practical at consumer prices.
│           Spark for privacy and regular use. Cloud for one-off jobs.
│
├── Serve multiple users from one machine?
│   └── SPARK (128 GB holds model + multiple KV caches)
│       Desktop can only serve one user at a time with large models.
│
├── Want low power / always-on / quiet operation?
│   └── SPARK or MAC MINI
│       240W / 96W total vs 700-1000W desktop.
│
├── On a budget but need more VRAM?
│   └── RTX 5090 is the best GPU-only upgrade (32 GB, ~1.8 TB/s)
│       Still limited to ~48-56 GB total. Ceilings remain
│       with the biggest models or multi-model workflows.
│       But much cheaper than a Spark for a significant improvement.
│
└── Want the "ideal" solution regardless of cost?
    └── A pro GPU with 80-96 GB VRAM (H100, Blackwell Pro, etc.)
        Fastest AND enough memory — but they cost
        €15,000-30,000+, need a workstation, and draw 400-700W.
        At that point a Spark at €4,500 looks like a bargain.
```

---

## Conclusions

1. **Models that fit on GPU VRAM: desktop wins easily.** The RTX 4090's ~1 TB/s bandwidth is unbeatable. For LLMs under ~24 GB and single-model workflows, there's no reason to spend money on anything else.

2. **Large dense models: everything is slow.** The desktop at 1.29 t/s is unusable. The Spark at 4.46 t/s is 3.5x faster, which matters, but 4-5 t/s is still not a great experience. None of these devices make a 70B dense model feel fast. The Spark turns "impossible" into "slow but functional." Whether that's worth €4,500 depends on how often that's needed.

3. **Large MoE models: the Spark's strongest argument.** The desktop manages a usable 19.7 t/s, but the Spark delivers 52.8 t/s. That's the difference between "acceptable" and "genuinely fast." This is where the Spark clearly and convincingly wins for inference.

4. **Prompt processing is the biggest gap.** When CPU offload is involved, the desktop's prompt eval rate drops to 14-22x slower than the Spark. This means noticeably longer pauses before the first token on long prompts or large contexts.

5. **Power efficiency favors the Spark.** 150W at the wall (whole device) vs 137W for just GPUs on the desktop (the whole PC is much more). For always-on inference or in an office, the Spark is far more practical.

6. **The real question is what the use case demands.** The Spark isn't a universally better machine — it's slower than a 4090 for anything that fits on a GPU. It serves a specific niche: large models, multi-model workflows, training/fine-tuning, concurrent users, and energy-efficient always-on operation. A capable desktop already handles many workloads well. The Spark fills the gaps where a desktop struggles — but those gaps may or may not justify €4,500 depending on how central they are to the workflow.

7. **The data here is a starting point, not the full picture.** The benchmarks cover LLM inference only. Image/video generation, agentic multi-model workflows, training workloads, and always-on serving scenarios are not measured here but could significantly strengthen (or weaken) the case for a Spark. Hopefully the background concepts and analysis in this document help frame the decision even for workloads not directly benchmarked. The collected data suggests the Spark is most valuable when memory capacity matters more than raw speed — and that's exactly what larger, more ambitious AI workloads tend to need.
