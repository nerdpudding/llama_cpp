# llama.cpp Docker Wrapper for Dual-GPU Desktop

Custom llama.cpp Docker build optimized for a dual-GPU desktop with asymmetric VRAM, targeting large MoE models that require precise GPU/CPU tensor placement.

## Table of Contents

- [Hardware](#hardware)
- [Why Not Ollama?](#why-not-ollama)
- [Target Models](#target-models)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Switching Models](#switching-models)
- [Benchmarks](#benchmarks)
- [Updating llama.cpp](#updating-llamacpp)
- [Documentation](#documentation)

---

## Hardware

| Component | Spec |
|-----------|------|
| GPU 0 | NVIDIA RTX 4090 (24 GB VRAM) — Ada Lovelace, sm_89 |
| GPU 1 | NVIDIA RTX 5070 Ti (16 GB VRAM) — Blackwell, sm_120 |
| CPU | AMD Ryzen 7 5800X3D (8C/16T) |
| RAM | 64 GB DDR4 |
| OS | Ubuntu 24.04 |
| Driver | 580.x (open kernel) |
| CUDA | 13.0 (required for sm_120 / Blackwell support) |

Total GPU VRAM: 40 GB across two GPUs with asymmetric split.

## Why Not Ollama?

Ollama doesn't support the features needed for this hardware and these models:

- **`-ot` tensor overrides:** Regex-based per-layer GPU/CPU placement is essential for running 60-80 GB MoE models across 40 GB of split VRAM. Ollama has no equivalent.
- **Hardware-specific build:** CUDA 13.0 with `sm_89;sm_120` targeting both Ada and Blackwell architectures. Ollama ships a generic binary.
- **Latest features:** DeltaNet kernels, `--fit` auto-VRAM, disaggregated prompt processing for MoE — features that arrive in llama.cpp master weeks before (if ever) in Ollama.

## Target Models

| Model | File Size | Speed | Context | Use Case |
|-------|-----------|-------|---------|----------|
| GLM-4.7 Flash Q4_K_M | 18 GB | ~140 t/s | 128K | Fast tasks, single GPU (Strategy A) |
| GLM-4.7 Flash Q8_0 | 30 GB | ~105 t/s | 128K | Higher quality, dual GPU (Strategy C) |
| GPT-OSS 120B F16 | 61 GB | ~22 t/s | 64K | Large MoE, partial CPU offload (Strategy D) |
| Qwen3-Coder-Next UD-Q6_K_XL | 64 GB | ~24 t/s | 256K | Coding baseline, best quality |
| Qwen3-Coder-Next UD-Q5_K_XL | 57 GB | ~30 t/s | 256K | Coding speed option |

## Repository Structure

```
.
├── README.md                      # This file
├── ROADMAP.md                     # Future plans and status
├── Dockerfile                     # Multi-stage build (CUDA 13.0, sm_89+sm_120)
├── docker-compose.yml             # Production compose file
├── docker-compose.example.yml     # Annotated template with usage instructions
├── .dockerignore
├── .gitignore
├── models.conf                    # Server configuration (all models)
├── start.sh                       # Model selector script (generates .env, launches dashboard)
├── dashboard.py                   # Terminal monitoring dashboard (curses TUI)
├── .env.example                   # Generic template with all variables documented
├── docs/
│   ├── gpu-strategy-guide.md              # GPU placement decision tree
│   ├── client-settings.md                 # Recommended client-side sampler settings per model
│   ├── bench-test-results.md              # Bench profile GPU optimization (VRAM, speeds, OOM tests)
│   ├── dgx-spark-comparison.md            # DGX Spark vs desktop comparison (WIP article)
│   └── lessons_learned.md                 # Mistakes and prevention rules
├── models/                        # GGUF files (gitignored)
│   ├── .gitkeep
│   ├── documentation/             # Model cards (README from HuggingFace)
│   ├── GLM-4.7-Flash/
│   ├── GPT-OSS-120b/
│   └── Qwen3-Coder-Next/
│       ├── Q6_K/
│       ├── UD-Q5_K_XL/
│       └── UD-Q6_K_XL/
├── benchmarks/
│   └── evalplus/                  # EvalPlus HumanEval+ coding benchmark runner
│       ├── benchmark.sh           # Main runner (orchestrates all steps)
│       ├── bench-client.conf      # Client-side config (system prompts per model)
│       ├── generate-report.py     # Results → comparison table
│       ├── reference-scores.json  # Published proprietary model scores
│       └── results/               # Benchmark outputs (gitignored)
│           └── REPORT.md          # Latest EvalPlus HumanEval+ results
├── archive/                       # Archived plans, old docs, superseded files
├── claude_plans/                  # Claude Code plan files
├── llama.cpp/                     # llama.cpp source (separate git repo, gitignored)
└── .claude/
    └── agents/                    # Claude Code specialized agents
        ├── gpu-optimizer.md
        ├── benchmark.md
        ├── builder.md
        ├── diagnose.md
        ├── model-manager.md
        ├── api-integration.md
        └── doc-keeper.md
```

## Prerequisites

- **Docker** with Docker Compose v2
- **NVIDIA Container Toolkit** installed and configured
- **NVIDIA driver** 580+ (open kernel module recommended for Blackwell)
- **CUDA 13.0** support (provided by the Docker image, not needed on host)
- Sufficient disk space for models (60-200+ GB depending on models)

## Installation

1. **Clone this repository:**
   ```bash
   git clone <repo-url> llama_cpp
   cd llama_cpp
   ```

2. **Clone llama.cpp source:**
   ```bash
   git clone https://github.com/ggml-org/llama.cpp.git
   ```

3. **Download models** into the appropriate subdirectory under `models/`:
   ```bash
   # Example: download from Hugging Face
   huggingface-cli download <repo> <file> --local-dir models/<model-dir>/
   ```

4. **Build the Docker image:**
   ```bash
   docker compose build
   ```

## Quick Start

1. Run the model selector:
   ```bash
   ./start.sh
   ```
   Pick a model from the menu — the script generates `.env`, starts the container, waits for the server to be ready, and opens a monitoring dashboard with server logs, GPU stats, and system stats.

2. Dashboard controls:
   - **`q`** — Stop the server and exit
   - **`r`** — Stop the server and return to the model menu
   - **`Up/Down/PgUp/PgDn`** — Scroll server logs

3. Access:
   - **Web UI:** http://localhost:8080
   - **API:** http://localhost:8080/v1/chat/completions

3. Test with curl:
   ```bash
   curl http://localhost:8080/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"messages": [{"role": "user", "content": "Hello!"}], "max_tokens": 100}'
   ```

## Switching Models

Use the interactive menu or pass a model ID directly:

```bash
./start.sh                  # Interactive menu + monitoring dashboard
./start.sh qwen3-coder      # Direct launch (stops running container first)
./start.sh --list            # List available models
./start.sh --no-dashboard   # Launch without dashboard (raw docker compose logs)
```

Available models (defined in `models.conf`):

| Section ID | Model | Speed | Context |
|------------|-------|-------|---------|
| `glm-flash-q4` | GLM-4.7 Flash Q4_K_M | Fast | 128K |
| `glm-flash` | GLM-4.7 Flash Q8_0 | Fast | 128K |
| `glm-flash-exp` | GLM-4.7 Flash Q8_0 (experimental) | Fast | 128K |
| `gpt-oss-120b` | GPT-OSS 120B F16 | ~20 t/s | 64K |
| `qwen3-coder-q5` | Qwen3-Coder-Next UD-Q5_K_XL (speed) | 25.8 t/s | 256K |
| `qwen3-coder` | Qwen3-Coder-Next UD-Q6_K_XL (baseline) | 21.4 t/s | 256K |
| `qwen3-coder-q6k` | Qwen3-Coder-Next Q6_K | ~21 t/s | 256K |

### Model-specific notes

**GPT-OSS 120B reasoning levels:** GPT-OSS supports configurable reasoning effort (low/medium/high) but controls it via a system prompt trigger (`"Reasoning: high"`), not a server flag. llama-server's `--system-prompt` flag is excluded from the server binary, so this cannot be set in `models.conf` or `EXTRA_ARGS`. Set it in the system prompt field of your client (web UI, API call, agentic framework). See the [model card](models/documentation/README_modelcard_gpt-oss-120b-GGUF.md) for details.

## Benchmarks

The project includes an [EvalPlus HumanEval+](benchmarks/evalplus/README.md) coding benchmark runner that tests all models against 164 Python problems and compares results with proprietary models (Claude, GPT, DeepSeek, etc.).

```bash
cd benchmarks/evalplus
source .venv/bin/activate       # One-time setup: uv venv && uv pip install evalplus
./benchmark.sh bench-glm-flash-q4       # Smoke test (one model)
./benchmark.sh --local                  # All local models
./benchmark.sh --all                    # All models (local + Claude)
```

Code generation runs on the host via the llama.cpp API; evaluation runs in a Docker sandbox for safety. Server config (model, GPU layers) comes from `models.conf`; client config (system prompts, reasoning levels) comes from `benchmarks/evalplus/bench-client.conf`. Claude Opus 4.6 can also be benchmarked using a custom Claude Code agent that solves each problem without code execution or internet access. See [benchmarks/evalplus/README.md](benchmarks/evalplus/README.md) for full setup and usage.

## Updating llama.cpp

```bash
cd llama.cpp
git pull origin master
cd ..
docker compose build --no-cache
```

The `llama.cpp/` directory is a separate git repository — it's gitignored from this wrapper project and updated independently.

## Documentation

- **[GPU Strategy Guide](docs/gpu-strategy-guide.md)** — GPU placement decision tree, strategies A-D, graph splits, and tuning guidance
- **[Client Settings](docs/client-settings.md)** — Recommended temperature, top_p, top_k, min_p, and system prompt settings per model for any client
- **[Bench Profile Test Results](docs/bench-test-results.md)** — GPU optimization data: VRAM usage, speeds, OOM failures, and layer split decisions
- **[EvalPlus Benchmark Results](benchmarks/evalplus/results/REPORT.md)** — Latest HumanEval+ scores for all models vs proprietary references
- **[EvalPlus Benchmark Runner](benchmarks/evalplus/README.md)** — HumanEval+ coding benchmark setup, usage, and comparison with proprietary models
- **[Lessons Learned](docs/lessons_learned.md)** — Common mistakes and prevention rules
- **[ROADMAP.md](ROADMAP.md)** — Current status and future plans
- **[docker-compose.example.yml](docker-compose.example.yml)** — Annotated compose template with full variable reference
