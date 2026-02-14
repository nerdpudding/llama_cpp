# DGX Spark Benchmark & Purchase Decision Report

**Date:** February 13, 2026  
**Purpose:** Should I buy a DGX Spark (~€3500-4000) to complement my current desktop?  
**Hardware:** Desktop = RTX 4090 (24GB) + RTX 5070 Ti (16GB) = 40GB combined VRAM  
**Scope:** Only models and workloads I actually use. Every benchmark is sourced. Gaps are marked.

---

## Table of Contents

0. [Executive Summary](#0-executive-summary)
1. [My Current Desktop: Verified Baseline](#1-my-current-desktop-verified-baseline)
   - 1.1 [Test setup and methodology](#11-test-setup-and-methodology)
   - 1.2 [GLM-4.7-Flash results: all tests](#12-glm-47-flash-results-all-tests)
   - 1.3 [Key findings from my own tests](#13-key-findings-from-my-own-tests)
   - 1.4 [Current desktop limits](#14-current-desktop-limits)
2. [DGX Spark Verified Benchmarks](#2-dgx-spark-verified-benchmarks)
   - 2.1 [Source classification](#21-source-classification)
   - 2.2 [MoE models on Spark](#22-moe-models-on-spark)
   - 2.3 [Dense models on Spark](#23-dense-models-on-spark)
   - 2.4 [Training on Spark](#24-training-on-spark)
   - 2.5 [Diffusion on Spark](#25-diffusion-on-spark)
3. [Head-to-Head: Desktop vs Spark](#3-head-to-head-desktop-vs-spark)
   - 3.1 [Models that fit on desktop (≤40GB)](#31-models-that-fit-on-desktop-40gb)
   - 3.2 [Models that overflow to CPU on desktop](#32-models-that-overflow-to-cpu-on-desktop)
   - 3.3 [Models impossible on desktop](#33-models-impossible-on-desktop)
   - 3.4 [Training workloads](#34-training-workloads)
4. [Qwen3-Coder-Next 80B: Special Case](#4-qwen3-coder-next-80b-special-case)
5. [Conclusions & Recommendation](#5-conclusions--recommendation)
6. [What's Missing (Data Gaps)](#6-whats-missing-data-gaps)
7. [Source URLs](#7-source-urls)

---

## 0. Executive Summary

**The question:** Is a DGX Spark worth €3500-4000 alongside my current RTX 4090 + RTX 5070 Ti desktop?

**The short answer:** Yes, but only as a complementary device for specific workloads — not as a replacement for inference on models that already fit on the desktop.

**What the data shows:**

1. **For models that fit on my desktop (≤30B MoE at ≤202k context):** Desktop wins decisively. I measured 109-133 t/s on GLM-4.7-Flash. Spark benchmarks for comparable MoE models show 40-46 t/s. Desktop is 2.5-3x faster. No reason to use Spark here.

2. **For models that overflow to CPU on desktop:** This is where it gets interesting. My Ollama test at 112k context with Q8_0 dropped to 31.67 t/s because 4 layers got offloaded to CPU. llama.cpp still managed 108 t/s at that same context because it uses less KV cache. But push context further (256k) or use larger models, and even llama.cpp will hit the 40GB wall. On Spark, everything stays in unified memory — no cliff edge. Expected: ~40-46 t/s for 30B MoE models at any context length up to 256k.

3. **For models impossible on desktop:** GPT-OSS 120B (MoE, ~65GB) gets 38-41 t/s on Spark. Qwen3-Coder-Next 80B Q4 (~56GB at 256k) likely ~40-50 t/s (estimated, no benchmark exists). 70B dense models like Llama 70B get only 4.4 t/s on Spark — unusable. The Spark only solves "doesn't fit" for MoE architectures.

4. **For training:** This is the Spark's strongest case. QLoRA for 30B+ models requires more VRAM than the desktop's 24GB single-GPU limit. Spark's 128GB unified memory enables 70B QLoRA (confirmed by NVIDIA at 5,079 tokens/s training throughput). Flux/LTX-2 LoRA training without quantization tricks. Train LoRAs on Spark → run inference on desktop at full speed.

5. **Runtime matters enormously on Spark:** TRT-LLM with FP4/MXFP4 is significantly faster than llama.cpp on Spark hardware. The 273 GB/s bandwidth bottleneck hurts llama.cpp for dense models, but MoE models with few active parameters sidestep it. Ollama on Spark is fine for MoE but terrible for dense.

**Recommended use pattern (if purchased):**

- **Desktop:** All inference for models ≤30B. Gaming/VR. Quick iteration.
- **Spark:** Training LoRAs/QLoRAs for 24-70B models. Running 80-120B MoE models that don't fit on desktop. Long-context (256k) inference where desktop would need CPU offload. Diffusion model training (Flux, LTX-2, WAN 2.2) at full precision without VRAM tricks.

**The honest gaps:** No Spark benchmark exists for Mistral models, Qwen3-Coder-Next, or GLM-4.7-Flash. The Ollama benchmarks are from October 2025 (4 months old). No training speed comparison Spark vs desktop exists for diffusion workloads.

---

## 1. My Current Desktop: Verified Baseline

Source: My own TEST_PLAN.md — tests I ran myself on my hardware.

### 1.1 Test setup and methodology

- **Hardware:** AMD 5800X3D, 64GB RAM, RTX 4090 (24GB) + RTX 5070 Ti (16GB)
- **Model:** GLM-4.7-Flash — 29.94B parameters, 47 layers, 64 experts (MoE + MLA architecture, same as DeepSeek-V2)
- **Quantizations tested:** Q8_0 (~31GB) and Q4_K_M (~19GB)
- **Backends:** Ollama (Docker) and llama.cpp (Docker, recent source build)
- **Settings:** Both backends with q8_0 KV cache, flash attention, same prompt (49 tokens), temperature=1
- **Method:** curl to native API, clean start each time (docker restart, no cached models)

### 1.2 GLM-4.7-Flash results: all tests

#### Unfair comparison first: Q8_0 at 112k context (Ollama overflows to CPU)

| Metric | Ollama | llama.cpp |
|--------|--------|-----------|
| Context length | 112k | 112k |
| Decode speed | **31.67 t/s** | **108.83 t/s** |
| GPU layers | **44/48** (4 on CPU!) | **48/48** (all GPU) |
| VRAM total | 39.2 GiB | 38.5 GiB |
| KV cache total | ~5.9 GiB | ~3.1 GiB |
| Model on CPU | 2.0 GiB | 321 MiB |
| KV cache on CPU | 379 MiB | 0 |
| Total response time | ~109 sec | ~32.2 sec |

**Why this happened:** Ollama's KV cache is ~2x larger (5.9 vs 3.1 GiB) because its MLA implementation stores K and V separately (head_count_kv=20) while llama.cpp compresses via true MLA (n_head_kv=1, V derived from K). This ~3 GiB difference pushes Ollama over the 40GB VRAM limit, forcing 4 layers + some KV cache to CPU. Result: 3.4x slower.

#### Controlled comparison: Q8_0 at 64k context (both 100% GPU)

| Metric | Ollama | llama.cpp |
|--------|--------|-----------|
| Context length | 64k | 64k |
| Decode speed | **100.33 t/s** | **109.03 t/s** |
| GPU layers | 48/48 | 48/48 |
| VRAM total | 37.5 GiB | 36.4 GiB |
| KV cache total | ~3.3 GiB | ~1.8 GiB |
| Prompt processing | 935 t/s | 224 t/s |
| Total response time | ~44.8 sec | ~31.9 sec |

#### Controlled comparison: Q4_K_M at 202k context (both 100% GPU)

| Metric | Ollama | llama.cpp |
|--------|--------|-----------|
| Context length | 202k | 202k |
| Decode speed | **121.91 t/s** | **132.72 t/s** |
| GPU layers | 48/48 | 48/48 |
| VRAM total | 33.7 GiB | 29.0 GiB |
| KV cache total | ~10.3 GiB | ~5.6 GiB |
| Prompt processing | 1053 t/s | 194 t/s |
| Total response time | ~73.8 sec | ~29.8 sec |

#### Summary table

| Test | Ollama | llama.cpp | Difference |
|------|--------|-----------|------------|
| Q8_0 64k decode | 100.33 t/s | 109.03 t/s | llama.cpp +9% |
| Q4_K_M 202k decode | 121.91 t/s | 132.72 t/s | llama.cpp +9% |
| Q8_0 112k decode | 31.67 t/s | 108.83 t/s | **llama.cpp +3.4x** (Ollama CPU offload) |
| Q8_0 64k prompt | 935 t/s | 224 t/s | Ollama +4.2x |
| Q4_K_M 202k prompt | 1053 t/s | 194 t/s | Ollama +5.4x |

### 1.3 Key findings from my own tests

**llama.cpp is the better backend for my hardware.** The 9% decode speed advantage is nice, but the real win is the 2x smaller KV cache through proper MLA implementation. This means:

- Q8_0 at 112k: llama.cpp fits on GPU (109 t/s), Ollama doesn't (32 t/s)
- Q4_K_M at 202k: both fit, but llama.cpp uses 4.7 GiB less VRAM — headroom for longer context or larger models

**Prompt processing is faster on Ollama** (4-5x), but with 49-token prompts the absolute difference is <0.3 seconds. For longer prompts this gap could matter more, but I haven't tested that.

### 1.4 Current desktop limits

Based on my tests and VRAM math:

| What I can do | Status |
|---------------|--------|
| GLM-4.7-Flash Q8_0 up to ~112k context (llama.cpp) | ✅ 109 t/s |
| GLM-4.7-Flash Q4_K_M up to ~202k context | ✅ 122-133 t/s |
| Any 30B MoE model Q4-Q8 with moderate context | ✅ Works well |
| Diffusion inference (Flux, LTX-2, WAN 2.2) | ✅ Already running (24GB single GPU) |
| Small LoRA training (≤8-12B LLMs) | ✅ Fits in 24GB |
| Flux/LTX-2 LoRA with quantization tricks | ⚠️ Tight, requires FP8/quantized optimizers |

| What I cannot do | Why |
|------------------|-----|
| Q8_0 at 256k context | KV cache + model > 40GB, even llama.cpp can't fit |
| 70B+ dense models at usable speed | Model alone >35GB at Q4, leaves no room for KV cache at useful context |
| GPT-OSS 120B | ~65GB MXFP4, doesn't fit on 40GB |
| Qwen3-Coder-Next 80B Q4 at 256k | ~56GB total, doesn't fit |
| QLoRA for 24B+ LLMs | Requires >24GB single-GPU VRAM |
| 70B QLoRA | Requires ~48-80GB depending on method |
| Full-precision diffusion training (large models) | Optimizer states + gradients + model > 24GB |
| TRT-LLM / vLLM | Requires single contiguous GPU memory, mixed GPUs not supported |

**The 40GB VRAM wall:** My two GPUs give 40GB combined, but only via GGUF layer splitting in llama.cpp. For everything else (training, TRT-LLM, vLLM, ComfyUI diffusion), I'm limited to the 4090's 24GB as a single block.

---

## 2. DGX Spark Verified Benchmarks

### 2.1 Source classification

**Tier 1 — Primary sources (project owners / manufacturer)**

| ID | Source | URL | Date | Method |
|----|--------|-----|------|--------|
| [A] | ggerganov (llama.cpp maintainer) | https://github.com/ggml-org/llama.cpp/discussions/16578 | Oct 14, 2025 → Feb 5, 2026 | llama-bench, documented flags |
| [B] | Ollama official blog | https://ollama.com/blog/nvidia-spark-performance | Oct 2025 | 10 runs/model, caching disabled |
| [C] | NVIDIA tech blog (training) | https://developer.nvidia.com/blog/how-nvidia-dgx-sparks-performance-enables-intensive-ai-tasks/ | Oct 24, 2025 | NVIDIA's own numbers |
| [D] | LMSYS / SGLang team | https://lmsys.org/blog/2025-10-13-nvidia-dgx-spark/ | Oct 13, 2025 | SGLang + Ollama |
| [E] | NVIDIA Spark Playbooks | https://github.com/NVIDIA/dgx-spark-playbooks | Ongoing | Benchmark scripts + setup |
| [F] | NVIDIA Jan 2026 update | https://developer.nvidia.com/blog/new-software-and-model-optimizations-supercharge-nvidia-dgx-spark/ | Jan 2026 | Software improvements |
| [H] | NVIDIA Flux LoRA playbook | https://build.nvidia.com/spark/flux-finetuning | Launch | Step-by-step guide |

**Tier 2 — Professional reviews**

| ID | Source | URL | Date |
|----|--------|-----|------|
| [G] | Hardware-Corner.net (Allan Witt) | https://www.hardware-corner.net/qwen3-coder-next-hardware-requirements/ | ~Feb 9, 2026 |
| [I] | StorageReview | https://www.storagereview.com/review/nvidia-dgx-spark-review | Nov 2025 |
| [J] | Hardware-Corner.net (Spark comparison) | https://www.hardware-corner.net/ (GPT-OSS 120B comparison table) | Oct 2025 |

**Tier 3 — Community (reference only, not used as benchmark numbers)**

| Source | URL | Why not Tier 1 |
|--------|-----|----------------|
| NVIDIA Dev Forum (Qwen3-Coder-Next) | https://forums.developer.nvidia.com/t/how-to-run-qwen3-coder-next-on-spark/359571 | No methodology, no llama-bench output |
| llama.cpp issue #19480 | https://github.com/ggml-org/llama.cpp/issues/19480 | Bug report, not benchmark |

**Caveat on all Tier 1 sources:** The Ollama and LMSYS benchmarks are from October 2025. ggerganov updated Feb 5, 2026 (build b7946). Software has improved since October — these numbers are likely a floor, not a ceiling. But I can't quantify how much improvement because no structured re-benchmark has been published.

### 2.2 MoE models on Spark

These are the relevant numbers because MoE models sidestep the 273 GB/s bandwidth bottleneck — only active parameters are read per token.

| Model | Params (total/active) | Quant | Runtime | Decode t/s | Source |
|-------|----------------------|-------|---------|-----------|--------|
| GPT-OSS 120B | 120B / ~5.1B active | MXFP4 | llama.cpp | **38.55** | [A] ggerganov |
| GPT-OSS 120B | 120B / ~5.1B active | MXFP4 | Ollama | **41.1** | [B] Ollama blog |
| GPT-OSS 120B | 120B / ~5.1B active | MXFP4 | SGLang | **~49.7** decode | [D] LMSYS |
| GPT-OSS 20B | 20B / ~1B active | MXFP4 | Ollama | **49.7** | [B] Ollama blog |
| GPT-OSS 20B | 20B / ~1B active | MXFP4 | SGLang | **~58** | [D] LMSYS |
| Qwen3-Coder 30B-A3B | 30B / ~3B active | Q8_0 | llama-bench | **44.26** (depth 0) | [A] user eugr, same method |
| Qwen3-Coder 30B-A3B | 30B / ~3B active | Q8_0 | llama-bench | **39.46** (depth 4096) | [A] user eugr |
| Qwen3-Coder 30B-A3B | 30B / ~3B active | FP8 | Ollama | **46.5** | [B] Ollama blog |

**Pattern:** MoE models with ~3-5B active parameters consistently get **38-50 t/s** on Spark across all runtimes. SGLang tends to be fastest, llama.cpp slightly behind, Ollama comparable.

**Context depth penalty:** Qwen3-Coder 30B-A3B drops from 44.26 → 39.46 t/s between depth 0 and depth 4096. That's about 11% slower. At 256k context the penalty will be larger, but no benchmark for that exists.

### 2.3 Dense models on Spark

This is where the 273 GB/s bandwidth wall hits hard. Formula: `273 GB/s ÷ model_size_in_memory ≈ theoretical max t/s`, actual is 50-60% of theoretical.

| Model | Params | Quant | Runtime | Decode t/s | Source |
|-------|--------|-------|---------|-----------|--------|
| Llama 3.1 70B | 70B dense | Q4_K_M | Ollama | **4.42** | [B] Ollama blog |
| Llama 3.1 70B | 70B dense | FP8 | SGLang | **2.7** | [D] LMSYS |
| Qwen3 32B | 32B dense | Q4_K_M | Ollama | **9.41** | [B] Ollama blog |
| Gemma3 27B | 27B dense | Q4_K_M | Ollama | **10.83** | [B] Ollama blog |
| DeepSeek-R1 14B | 14B dense | Q4_K_M | Ollama | **19.99** | [B] Ollama blog |
| Llama 3.2 8B | 8B dense | Q4_K_M | Ollama | **38.0** | [B] Ollama blog |

**The bottom line for dense models:** 70B dense at 4.4 t/s is not usable for anything interactive. 32B dense at 9.4 t/s is borderline. The Spark is not a viable platform for large dense model inference.

**Mistral models:** NO BENCHMARK EXISTS on Spark for any Mistral model. Based on bandwidth math, Mistral Small 24B at Q4 (~12GB) would get roughly 12-14 t/s. StorageReview [I] tested via vLLM: 5.3 t/s BF16, 8.8 t/s FP8. These are estimates/different runtime, not apples-to-apples.

### 2.4 Training on Spark

From NVIDIA tech blog [C]:

| Workload | Method | Training throughput | Note |
|----------|--------|---------------------|------|
| Llama 3.2 3B | Full fine-tune | 82,739 t/s | Confirmed working |
| Llama 3.1 8B | LoRA | 53,658 t/s | Confirmed working |
| Llama 3.3 70B | QLoRA | 5,079 t/s | **Confirmed working** |

**Training throughput** = `(batch_size × steps × sequence_length) / total_time`. This is NOT inference speed.

From NVIDIA Jan 2026 blog [F]:
- Distributed fine-tuning across two Sparks (FSDP + LoRA) for LLMs up to 70B: confirmed
- No training time benchmarks published for comparison with desktop GPUs

**What this means:** 128GB unified memory enables training workloads that are physically impossible on 24GB single-GPU VRAM. The training throughput numbers are reasonable but there's nothing to compare them against on desktop hardware for the same models — nobody publishes 70B QLoRA benchmarks on a 4090 because it doesn't fit.

### 2.5 Diffusion on Spark

| Claim | Source | Verified? |
|-------|--------|-----------|
| Flux.1-dev 12B Dreambooth LoRA works | [H] NVIDIA playbook | **Yes** — step-by-step guide exists |
| Flux.1 12B FP4 inference: 1K image / 2.6 sec | [C] NVIDIA blog | **Yes** — NVIDIA's number |
| FLUX 2 (90GB) full precision on Spark | [F] NVIDIA Jan 2026 | **Claimed** — no independent test |
| LTX-2 with NVFP8-optimized weights | [F] NVIDIA Jan 2026 | **Claimed** — no independent test |
| ComfyUI officially supported | [E] NVIDIA playbook | **Yes** — setup guide exists |
| ai-toolkit (ostris) Spark install instructions | https://github.com/ostris/ai-toolkit | **Yes** — in README |

**NOT confirmed:** Training speed comparisons Spark vs 4090. WAN 2.2 on Spark (not mentioned anywhere). Actual LoRA training times for Flux.

---

## 3. Head-to-Head: Desktop vs Spark

This is the section that matters for the purchase decision.

### 3.1 Models that fit on desktop (≤40GB)

**Example: GLM-4.7-Flash 30B MoE (my primary model)**

| Scenario | Desktop (llama.cpp) | Spark (estimated from Qwen3-Coder 30B-A3B benchmark*) |
|----------|---------------------|-------------------------------------------------------|
| Q8_0, 64k context | **109 t/s** | ~44 t/s* |
| Q4_K_M, 202k context | **133 t/s** | ~40 t/s* |
| Q8_0, 112k context | **109 t/s** | ~40 t/s* |

*No GLM-4.7-Flash benchmark exists on Spark. Estimate based on Qwen3-Coder 30B-A3B (similar size MoE, ~3B active params) getting 44 t/s at depth 0 and 39 t/s at depth 4096 on Spark [A]. Both are 30B MoE models with ~3B active parameters, so performance should be in the same ballpark.

**Verdict: Desktop wins 2.5-3x.** No reason to run these models on Spark.

### 3.2 Models that overflow to CPU on desktop

This is the crossover zone — where Spark might be faster than a desktop that's forced to CPU offload.

**Example: GLM-4.7-Flash Q8_0 at 112k context on Ollama**

| | Desktop (Ollama) | Desktop (llama.cpp) | Spark (estimated) |
|--|-----------------|--------------------|--------------------|
| Speed | **31.67 t/s** (CPU offload) | **108.83 t/s** (fits on GPU) | ~40-44 t/s* |
| Why | 4 layers on CPU, KV cache too large | Smaller KV cache, fits | All in unified memory |

**Key insight:** llama.cpp's efficient MLA implementation saves me here — it still fits at 112k where Ollama doesn't. But push to 256k context with Q8_0, and even llama.cpp won't fit. At that point:

**Example: GLM-4.7-Flash Q8_0 at 256k context (hypothetical)**

| | Desktop (llama.cpp) | Spark (estimated) |
|--|--------------------|--------------------|
| Memory needed | ~31GB model + ~6-7GB KV cache = ~38GB... might barely fit but would be at the absolute edge | ~38GB of 128GB = comfortable |
| Speed if it fits | ~100+ t/s | ~35-40 t/s |
| Speed if CPU offload | ~30-40 t/s (similar to Ollama 112k test) | N/A — it fits |

**Verdict:** For this specific model, llama.cpp's KV cache efficiency means my desktop can push further than expected before hitting the wall. Spark only wins if I push past what even llama.cpp can fit. The crossover point is somewhere around 200-256k context for Q8_0, or if I switch to Ollama as backend.

**Important nuance:** This analysis only holds for llama.cpp + GGUF. For any other runtime (vLLM, TRT-LLM, ComfyUI), I'm limited to 24GB single-GPU on desktop. Spark's 128GB unified memory works with all runtimes.

### 3.3 Models impossible on desktop

| Model | Why impossible on desktop | Spark performance | Usable? |
|-------|--------------------------|-------------------|---------|
| GPT-OSS 120B (MoE, ~65GB MXFP4) | Doesn't fit in 40GB | **38-41 t/s** (llama.cpp/Ollama) [A][B] | **Yes** — above 30 t/s minimum for interactive use |
| GPT-OSS 120B | | **~50 t/s** (SGLang) [D] | **Yes** — good with optimized runtime |
| Qwen3-Coder-Next 80B Q4 at 256k (~56GB) | Doesn't fit in 40GB | **No benchmark exists** (estimated ~40-50 t/s based on architecture*) | Probably yes — see Section 4 |
| Llama 70B dense Q4 (~35GB + KV) | Marginal fit, no useful context | **4.42 t/s** [B] | **No** — completely unusable |
| Llama 70B dense FP8 | Doesn't fit | **2.7 t/s** [D] | **No** — even worse |
| Any dense model >32B | KV cache pushes past 40GB | **<10 t/s** (from dense benchmarks) | **No** for interactive use |

*Qwen3-Coder-Next estimate: 3B active params, similar to Qwen3-Coder 30B-A3B which gets 44 t/s. The larger total parameter count means more memory for expert storage, but active compute per token is similar. See Section 4 for details.

**The pattern:** Spark unlocks MoE models that don't fit on desktop at 38-50 t/s. It does NOT unlock dense models in any useful way — 70B dense at 4.4 t/s is not interactive.

**What about n-cpu-moe on desktop?** From ggerganov's gpt-oss guide [A]: "You can get about 30 t/s at zero context on a 5090 with --n-cpu-moe 21." This technique offloads MoE expert layers to CPU while keeping attention on GPU. On my 4090 with 24GB, I'd need more layers on CPU, probably getting 15-25 t/s for GPT-OSS 120B (estimated — I haven't tested this). Spark's 38-41 t/s would be faster, and without the complexity of tuning n-cpu-moe settings.

### 3.4 Training workloads

| Workload | Desktop (4090 24GB) | Spark (128GB) |
|----------|---------------------|---------------|
| 8B LLM LoRA | ✅ Works | ✅ Works |
| 24-30B LLM QLoRA | ❌ Doesn't fit | ✅ Should work (no benchmark, but memory is sufficient) |
| 70B LLM QLoRA | ❌ Doesn't fit | ✅ **Confirmed:** 5,079 t/s training throughput [C] |
| Flux.1 Dreambooth LoRA | ⚠️ Tight, needs FP8/tricks | ✅ **Confirmed:** official playbook [H] |
| FLUX 2 (90GB) anything | ❌ Doesn't fit | ✅ Claimed at full precision [F] |
| LTX-2 LoRA | ⚠️ Possible with tricks | ✅ NVFP8-optimized weights available [F] |
| WAN 2.2 training | ⚠️ Possible at small scale | **Unknown** — not mentioned in any source |

**The complementary use case:** Train a 30B QLoRA on Spark → export merged model → run inference on desktop at 100+ t/s. This workflow is impossible today because the 24GB VRAM wall prevents training models larger than ~12B effectively.

---

## 4. Qwen3-Coder-Next 80B: Special Case

Released February 3, 2026 — 10 days ago. **NO RELIABLE BENCHMARK on Spark exists.**

### What we know about the model

From Qwen official (https://github.com/QwenLM/Qwen3-Coder, https://huggingface.co/Qwen/Qwen3-Coder-Next):

- 80B total / 3B active per token (512 experts, 10 active + 1 shared)
- Hybrid attention: Gated DeltaNet (linear) + Gated Attention → small KV cache
- 256K native context, extendable to 1M with YaRN
- SWE-Bench Verified: 70.6% (comparable to DeepSeek-V3.2)
- Apache 2.0 license

### Memory fit on Spark

From Unsloth GGUF sizes + Hardware-Corner.net [G] KV cache measurements on RTX PRO 6000:

| Quant | Model size | KV cache at 256K | Total estimated | Fits 128GB? | Fits my desktop (40GB)? |
|-------|-----------|-----------------|-----------------|-------------|------------------------|
| Q4_K_M | 48.5 GB | ~7 GB | ~56 GB | ✅ Yes (72GB free) | ❌ No |
| Q5_K_M | 56.8 GB | ~7 GB | ~64 GB | ✅ Yes (64GB free) | ❌ No |
| Q8_0 | 84.8 GB | ~14 GB | ~99 GB | ✅ Yes (29GB free) | ❌ No |

KV cache is small (~7GB at 256K for Q4) because the hybrid DeltaNet architecture uses linear attention for most layers — only 12 of 48 layers use traditional attention with KV cache [G].

### Speed estimate (not a benchmark)

Since active params ≈ 3B (same as Qwen3-Coder 30B-A3B), and Qwen3-Coder 30B-A3B gets 44 t/s on Spark [A]:

- **Estimated: ~40-50 t/s** for Qwen3-Coder-Next on Spark
- Slightly less than Qwen3-Coder 30B because more total expert weights to load from memory, even though active params are similar
- Forum post claims ~43 t/s FP8 — plausible but unverified (Tier 3 source)

**This is an educated guess, not a benchmark.** The only way to know is to run llama-bench on Spark when the model is added to ggerganov's benchmark set.

### llama.cpp support status

From llama.cpp issue #19480: CPU inference for Qwen3-Next architecture is ~5x slower than expected, indicating MoE optimizations are still incomplete. CUDA path may be better optimized. Monitor this issue for updates.

---

## 5. Conclusions & Recommendation

### What the data actually supports

**Conclusion 1: Spark is NOT a replacement for desktop inference.**
- Evidence: My desktop gets 109-133 t/s on 30B MoE models. Spark benchmarks show 38-50 t/s for comparable models. Desktop is 2.5-3x faster when models fit.
- Confidence: HIGH — based on my own measurements + Tier 1 Spark benchmarks.

**Conclusion 2: Spark IS useful for MoE models that don't fit on desktop.**
- Evidence: GPT-OSS 120B gets 38-41 t/s on Spark [A][B]. It doesn't run on my desktop at all. Qwen3-Coder-Next Q4 at 256k (~56GB) also doesn't fit on desktop but fits easily on Spark.
- Confidence: HIGH for GPT-OSS (Tier 1 data). MEDIUM for Qwen3-Coder-Next (no Spark benchmark, but memory fit is certain and speed estimate is reasonable).

**Conclusion 3: Spark does NOT solve large dense model inference.**
- Evidence: Llama 70B gets 4.42 t/s on Spark [B]. 70B FP8 gets 2.7 t/s [D]. This is not interactive.
- Confidence: HIGH — multiple Tier 1 sources confirm this. The 273 GB/s bandwidth is the hard physical limit.
- Exception: TRT-LLM with FP4 reportedly gets better results for 70B (one review claims ~5.2 t/s with TRT-LLM vs 3.8 t/s llama.cpp), but even 5 t/s is not usable for my purposes.

**Conclusion 4: Spark's strongest case is training.**
- Evidence: 70B QLoRA confirmed working at 5,079 t/s training throughput [C]. 128GB enables training workloads physically impossible on 24GB. Flux LoRA playbook exists [H].
- Confidence: HIGH for "it works." LOW for "how does it compare to desktop" — no comparative benchmarks exist.
- The complementary workflow: Train on Spark → infer on desktop is enabled by this purchase and impossible without it (for models >12B).

**Conclusion 5: Runtime choice matters enormously on Spark.**
- Evidence: GPT-OSS 120B gets ~39 t/s on llama.cpp vs ~50 t/s on SGLang [A][D]. Dense models might benefit from TRT-LLM FP4 path.
- Implication: If buying Spark, plan to learn TRT-LLM and SGLang. Don't expect Ollama or bare llama.cpp to give optimal results on this hardware.

**Conclusion 6: The Ollama-specific CPU offload problem on desktop is mostly solved by llama.cpp.**
- Evidence: My own test — Ollama drops to 32 t/s at 112k Q8_0, llama.cpp stays at 109 t/s at the same settings. This is because llama.cpp's MLA implementation uses ~2x less KV cache.
- Implication: Switching to llama.cpp already extends my desktop's effective range significantly. Some scenarios where I thought "Spark would be faster than CPU-offloaded desktop" are actually "llama.cpp on desktop is still faster because it doesn't need to offload."

### Recommendation

**Buy the Spark (or ASUS Ascent GX10 for ~€1000 less) IF:**

1. You want to train LoRAs/QLoRAs for models larger than 12B — this is impossible on your current hardware and is the single strongest justification
2. You want to run 80-120B MoE models (Qwen3-Coder-Next, GPT-OSS 120B) at 38-50 t/s — these don't fit on desktop
3. You want a dedicated always-on training/inference box that doesn't tie up your gaming/VR desktop
4. You accept that you'll need to invest time learning TRT-LLM/SGLang to get the most out of it

**Don't buy it IF:**

1. Your primary goal is faster inference on models that already fit on your desktop — Spark will be slower, not faster
2. You mainly want large dense models (70B Llama, etc.) — Spark can't run these at usable speeds either
3. Budget is the constraint — €3500-4000 is a lot for a device whose primary value is training and a narrow class of very large MoE models

**The complementary workflow I'd recommend:**

```
Desktop (RTX 4090 + 5070 Ti)          Spark (128GB)
─────────────────────────              ─────────────
• Inference ≤30B models (100+ t/s)     • Train 24-70B QLoRAs
• Gaming / VR / sim racing             • Train diffusion LoRAs (full precision)
• Quick iteration, hot-swap models     • Run 80-120B MoE inference (40-50 t/s)
• Flux/LTX/WAN inference               • Long-context (256k) inference
• Run YOUR trained LoRAs fast          • Generate the LoRAs that desktop runs
```

---

## 6. What's Missing (Data Gaps)

| Gap | Impact on decision | When it might be filled |
|-----|-------------------|------------------------|
| Qwen3-Coder-Next on Spark (llama-bench) | HIGH — this is a key target model | When ggerganov adds it to discussion #16578 |
| GLM-4.7-Flash on Spark | MEDIUM — I have a comparable model (Qwen3-Coder 30B) as proxy | Probably never unless I test it myself |
| Any Mistral model on Spark | MEDIUM — Mistral models are dense, so expect 10-15 t/s for 24B | Nobody has tested this |
| Training speed Spark vs 4090 (same workload) | HIGH — the training case is the strongest argument but has no comparative data | Would need identical workloads run on both |
| WAN 2.2 on Spark | LOW — if Flux works, WAN 2.2 likely works too | Unknown |
| Ollama/llama.cpp improvements since Oct 2025 | MEDIUM — Oct benchmarks are the floor | When someone re-runs standardized benchmarks |
| Spark at 256k context (any model) | HIGH — long context is a key Spark use case but no benchmark tests this | Monitor ggerganov's benchmark updates |
| TRT-LLM performance for MoE models on Spark | MEDIUM — could be significantly faster than llama.cpp | NVIDIA playbooks may have this |

---

## 7. Source URLs

### Tier 1 — Primary sources
- [A] https://github.com/ggml-org/llama.cpp/discussions/16578
- [B] https://ollama.com/blog/nvidia-spark-performance
- [C] https://developer.nvidia.com/blog/how-nvidia-dgx-sparks-performance-enables-intensive-ai-tasks/
- [D] https://lmsys.org/blog/2025-10-13-nvidia-dgx-spark/
- [E] https://github.com/NVIDIA/dgx-spark-playbooks
- [F] https://developer.nvidia.com/blog/new-software-and-model-optimizations-supercharge-nvidia-dgx-spark/
- [H] https://build.nvidia.com/spark/flux-finetuning

### Tier 2 — Professional reviews
- [G] https://www.hardware-corner.net/qwen3-coder-next-hardware-requirements/
- [I] https://www.storagereview.com/review/nvidia-dgx-spark-review
- [J] https://www.hardware-corner.net/ (GPT-OSS comparison table)

### Tier 3 — Community
- https://forums.developer.nvidia.com/t/how-to-run-qwen3-coder-next-on-spark/359571
- https://github.com/ggml-org/llama.cpp/issues/19480

### Model references
- Qwen3-Coder-Next: https://huggingface.co/Qwen/Qwen3-Coder-Next
- Qwen3-Coder-Next GGUF: https://huggingface.co/unsloth/Qwen3-Coder-Next-GGUF
- Qwen3-Coder GitHub: https://github.com/QwenLM/Qwen3-Coder
- ai-toolkit (Flux LoRA): https://github.com/ostris/ai-toolkit

### My own data
- TEST_PLAN.md — GLM-4.7-Flash benchmarks on RTX 4090 + RTX 5070 Ti
