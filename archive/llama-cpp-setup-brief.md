# llama.cpp Docker Setup & Benchmark Brief

> **Purpose**: Reference document for a coding assistant to build an optimized Docker-based llama.cpp setup on the specific hardware below, and run structured benchmarks against the existing Ollama setup.
>
> **Project structure**: The llama.cpp source is cloned in the `llama.cpp/` subdirectory. All project files (Dockerfile, compose, scripts) live in the project root alongside it.

---

## Table of Contents

1. [Current Setup](#1-current-setup)
2. [Goal](#2-goal)
3. [Docker Strategy](#3-docker-strategy)
4. [Technical Findings & Build Requirements](#4-technical-findings--build-requirements)
5. [Task for the Coding Assistant](#5-task-for-the-coding-assistant)

---

## 1. Current Setup

### Hardware

| Component | Spec | Notes |
|-----------|------|-------|
| **CPU** | AMD Ryzen 7 5800X3D | 8 cores / 16 threads |
| **RAM** | 64 GB DDR4 | ~12-14 GB used by Ubuntu at idle |
| **GPU 0** | NVIDIA RTX 4090 (24 GB VRAM) | Ada Lovelace, compute capability **8.9** (sm_89). Full 24 GB available. |
| **GPU 1** | NVIDIA RTX 5070 Ti (16 GB VRAM) | Blackwell, compute capability **12.0** (sm_120). ~4 GB used by desktop. |
| **OS** | Ubuntu 24.04 LTS | |
| **NVIDIA Driver** | 580.126.16 (`nvidia-driver-580-open`, open kernel module) | All nvidia packages on apt hold |
| **CUDA** | 13.0 (driver-level), toolkit 12.6 on host | |
| **Docker** | Installed with `nvidia-container-toolkit` 1.18.2 | GPU passthrough works |

### Current Ollama Setup

```bash
docker run -d \
  --network ollama-network \
  --gpus device=all \
  -v ollama:/root/.ollama \
  -p 11434:11434 \
  --name ollama \
  -e OLLAMA_KV_CACHE_TYPE=q8_0 \
  -e OLLAMA_NUM_PARALLEL=1 \
  ollama/ollama
```

**What this delivers:** 32B models (Q4/Q8) with 128k-170k context. Single-user. KV cache q8_0. Ollama auto-distributes layers across both GPUs.

**Limitations:** No control over GPU split. Conservative heuristics. Bundled llama.cpp version is weeks/months behind upstream. No access to `--fit`, `--override-tensor`, or new split modes.

---

## 2. Goal

Run llama.cpp directly (in Docker) alongside Ollama and compare:

- **Inference speed**: tokens/sec for prompt processing and generation
- **Memory efficiency**: VRAM usage at identical context length and model
- **GPU distribution**: how llama.cpp allocates work across both GPUs vs Ollama

**Use case**: Single-user chat, one session. Secondary: agentic workflows (sequential, not parallel). No need for multi-user serving or vLLM.

**Benchmark plan**: Same GGUF model, same prompt, same context length → measure tokens/sec and VRAM for both. Test at 4k, 32k, 128k context.

---

## 3. Docker Strategy

### Model Storage: Bind Mount to User-Managed Directory

**Critical**: Models live in `models/` inside the project repo, bind-mounted into the container. Not in a Docker volume, not in HuggingFace cache, not in the container. GGUF files are git-ignored.

```
llama_cpp/models/
├── model-a-Q8_0.gguf
└── model-b-Q4_K_M.gguf
```

Mount: `-v ./models:/models:ro`

For Ollama comparison: Ollama manages its own models via `ollama pull` in a Docker volume. For benchmarking, use the same model name/size in both — download a GGUF for llama.cpp into `models/`, and pull the equivalent via `ollama pull` on the Ollama side.

### PyTorch Is NOT Required

llama.cpp is pure C/C++ with direct CUDA. No PyTorch, no Python.

---

## 4. Technical Findings & Build Requirements

### 4.1 CUDA Architectures

Must compile for both GPUs:

| GPU | Architecture | Compute Capability | sm flag |
|-----|-------------|-------------------|---------|
| RTX 4090 | Ada Lovelace | 8.9 | `sm_89` |
| RTX 5070 Ti | Blackwell | 12.0 | `sm_120` |

```
-DCMAKE_CUDA_ARCHITECTURES="89;120"
```

sm_120 requires CUDA toolkit **12.8+** in the build environment. We use `nvidia/cuda:13.0.0-devel-ubuntu24.04` to match the host driver (580.x = CUDA 13.0).

**Resolved**: mxfp4 kernels on sm_120 (GitHub [#18447](https://github.com/ggml-org/llama.cpp/issues/18447)) — fixed in our checkout. CMakeLists.txt auto-converts `120` to `120a`.

**Build notes**:
- `-DBUILD_SHARED_LIBS=OFF` — static build, single binary, no shared libs to manage
- `-DCMAKE_EXE_LINKER_FLAGS="-L/usr/local/cuda/lib64/stubs"` — needed because `libcuda.so` is not present in the devel image (only stubs)

### 4.2 llama-server Flags

**Essential:**

| Flag | Value | Purpose |
|------|-------|---------|
| `-m /models/name.gguf` | model path | Bind-mounted from host |
| `-c 131072` | context length | Match Ollama config |
| `-ngl 99` | all layers to GPU | 99 = max |
| `--flash-attn` | on | Always |
| `-ctk q8_0` | KV cache key quant | Match Ollama |
| `-ctv q8_0` | KV cache value quant | Match Ollama |
| `--host 0.0.0.0` | listen all | For Docker |
| `--port 8080` | server port | |

**New (not in Ollama):**

| Flag | Purpose |
|------|---------|
| `--fit` | Auto memory allocation across GPUs. **ON by default.** Replaces manual `--tensor-split`. |
| `--fit-target` | VRAM headroom per GPU. Tune for 5070 Ti desktop usage. |
| `-ts 0.65,0.35` | Manual split. Only if `--fit` isn't optimal. |
| `-sm layer/row` | Split mode: `layer` (sequential, default), `row` (parallel). |
| `-mg 0` | Main GPU for KV cache in row mode. |
| `-ot` | Per-tensor override. Advanced, regex-based. |

### 4.3 Split Modes to Test

**`-sm layer`** (default, same as Ollama): Sequential layer distribution. Stable. GPUs partially idle.

**`-sm row`**: Weight matrices split; both GPUs compute simultaneously. May or may not help with asymmetric GPUs (4090 vs 5070 Ti). Worth testing.

**`-sm tensor`** (PR [#19378](https://github.com/ggml-org/llama.cpp/pull/19378)): Backend-agnostic tensor parallelism. Check if merged at build time.

**`-sm graph`** (ik_llama.cpp fork only): 3-4x speedup reported. Not mainline. Optional/advanced.

### 4.4 Benchmark Method

Test each backend separately (not simultaneously — they share the same GPUs).

1. Start llama.cpp with a model, send a test prompt, note tokens/sec and VRAM
2. Stop llama.cpp
3. Start Ollama with the same model, send the same prompt, note tokens/sec and VRAM
4. Compare results

Both expose OpenAI-compatible APIs (`POST /v1/chat/completions`). The JSON response includes timing info (tokens/sec). VRAM via `nvidia-smi`.

Keep settings identical: same model, same context size, same KV cache type, same prompt, same max_tokens and temperature.

---

## 5. Task for the Coding Assistant

### Deliverables

1. **Dockerfile** — Multi-stage build. `nvidia/cuda:13.0.0-devel-ubuntu24.04` for compile, `13.0.0-runtime` for final. Static build (`-DBUILD_SHARED_LIBS=OFF`). Copies from local `llama.cpp/` subdir. Compiles for sm_89 + sm_120. Final image: just `llama-server` binary + CUDA runtime.

2. **docker-compose.yml** — GPU access (all GPUs), bind mount `./models:/models:ro`, port 8080. All settings via env vars (MODEL, CTX_SIZE, SPLIT_MODE, etc.).

3. **USAGE.md** — How to build, download models, start, configure, monitor VRAM, stop.

4. **USAGE.md section 7** — Step-by-step instructions for manually comparing llama.cpp vs Ollama (same model, same prompt, same settings, one at a time).

### Project Layout

```
~/vibe_claude_kilo_cli_exp/llama_cpp/     ← project root
├── .claude/
│   └── agents/
│       ├── build.md
│       ├── benchmark.md
│       └── diagnose.md
├── llama.cpp/                             ← cloned llama.cpp repo (subdir)
│   └── ... (their source)
├── llama-cpp-setup-brief.md               ← this file
├── Dockerfile
├── docker-compose.yml
├── USAGE.md
└── models/                                ← GGUF files (git-ignored)
    ├── model-a.gguf
    └── model-b.gguf
```

### NOT Needed

- PyTorch, Python ML frameworks
- vLLM, multi-user serving
- NCCL (unless testing `-sm graph`)
- Models baked into Docker image
- Web UI

### References

- llama.cpp: https://github.com/ggml-org/llama.cpp
- Build docs: https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md
- Auto-fit: https://github.com/ggml-org/llama.cpp/discussions/18049
- Tensor parallelism PR: https://github.com/ggml-org/llama.cpp/pull/19378
- sm_120 issues: https://github.com/ggml-org/llama.cpp/issues/18447
- Multi-GPU split: https://github.com/ggml-org/llama.cpp/discussions/7678
