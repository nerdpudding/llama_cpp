# Docker Wrapper for llama.cpp

Custom llama.cpp Docker build optimized for a dual-GPU desktop with asymmetric VRAM, targeting large MoE models that require precise GPU/CPU tensor placement.

I use AI broadly — from running language models and generating images to speech recognition and agentic coding workflows (more on that in the [DGX Spark comparison article](docs/dgx-spark-comparison.md)). For local LLM inference I used [Ollama](https://ollama.com/) for a long time and it does a great job: easy model management, clean API, simple GPU offloading via GGUF. But as my projects moved toward larger models, agentic flows, and tighter hardware optimization, I kept running into limits. I wanted precise per-layer GPU/CPU placement across two GPUs with different VRAM sizes, access to the latest llama.cpp features as soon as they land, and control over build flags targeting my specific GPU architectures. Ollama's goal is simplicity — which it does well — but that means it doesn't expose these lower-level controls and sometimes lags behind on newer llama.cpp features.

So I went back to [llama.cpp](https://github.com/ggml-org/llama.cpp) — a high-performance C/C++ inference engine for running LLMs locally using quantized GGUF models. It supports CPU and GPU inference (CUDA, Metal, Vulkan), can split model layers across multiple GPUs and CPU RAM, and is the engine that Ollama itself is built on. It has come a long way since I last looked at it: it now includes its own web UI, an OpenAI-compatible API, and fine-grained multi-GPU control via per-layer tensor overrides. What it doesn't have is a convenient way to manage multiple model configurations, switch between them, or monitor what your hardware is doing while a model runs. That's what this wrapper adds:

- **Dockerized build** — compiles llama.cpp from source with hardware-specific CUDA flags, making the setup reproducible and isolated
- **Model selector** (`start.sh`) — interactive menu to pick a model, each with its own optimized GPU layer split, sampler defaults, and context size stored in `models.conf`
- **Monitoring dashboard** (`dashboard.py`) — curses TUI showing server logs, per-GPU VRAM/utilization/temperature, and system stats while a model runs
- **Benchmarking** — EvalPlus HumanEval+ runner to compare local models against each other and against proprietary references
- **Model onboarding** — `/add-model` skill with agent-assisted workflow for evaluating, configuring, and benchmarking new models (built for [Claude Code](https://claude.com/claude-code), but the approach could be adapted for other AI-assisted development tools)
- **Documentation** — GPU placement strategies, sampler settings per model, lessons learned, and hardware comparison research

llama.cpp itself provides the inference engine, web UI, and API. Everything else listed above is part of this wrapper. The goal is simple: get the most out of my hardware in terms of model quality, speed, and context length.

**What's next:** Since the API is OpenAI-compatible, this setup can serve as a local backend for coding assistants like Claude Code, Continue.dev, and aider, personal AI assistants like [OpenClaw](https://github.com/openclaw/openclaw), or any other tool that speaks the OpenAI API — using your own hardware instead of (or alongside) cloud APIs. That integration is the main next step. Beyond that: additional benchmarks for tasks beyond coding, and a way to switch models on the fly from API clients or agents without manually restarting the server. See the [Roadmap](ROADMAP.md) for details.

**Who is this for?** Anyone interested in llama.cpp, GPU utilization strategies for local inference, and also to some extent: how to use Claude Code agents and skills to develop and maintain a project like this. It's also a working reference for how different model architectures (MoE vs dense) need different GPU placement strategies, and includes documentation on those trade-offs. **However — this is not a plug-and-play installer.** The Docker build **compiles llama.cpp for specific GPU architectures** (sm_89 + sm_120), and **all model configurations are tuned and tested for my exact hardware**. You can absolutely adapt it to your own setup, but you'll need to **adjust GPU layers, tensor overrides, and possibly build flags**. The detailed docs are there to help with that.

## Table of Contents

- [Hardware](#hardware)
- [Quick Start](#quick-start)
- [Models](#models)
- [Benchmarks (EvalPlus HumanEval+)](#benchmarks-evalplus-humaneval)
- [Adding New Models](#adding-new-models)
- [Configuration](#configuration)
- [AI-Assisted Development](#ai-assisted-development)
- [Roadmap & Research](#roadmap--research)
- [Documentation](#documentation)
- [Repository Structure](#repository-structure)
- [Why Custom llama.cpp?](#why-custom-llamacpp)
- [Updating llama.cpp](#updating-llamacpp)

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

## Quick Start

### Build & install

```bash
git clone <repo-url> llama_cpp
cd llama_cpp
git clone https://github.com/ggml-org/llama.cpp.git
```

Download models into `models/<model-dir>/`:

```bash
huggingface-cli download <repo> <file> --local-dir models/<model-dir>/
```

Build the Docker image:

```bash
docker compose build
```

**Requirements:** Docker with Compose v2, NVIDIA Container Toolkit, NVIDIA driver 580+ (open kernel recommended for Blackwell), sufficient disk space for models (60-200+ GB).

### Run a model

```bash
./start.sh                  # Interactive menu + monitoring dashboard
./start.sh glm-flash-q4     # Direct launch (stops running container first)
./start.sh --list           # List available models
./start.sh --no-dashboard   # Launch without dashboard (raw docker compose logs)
```

The script shows an interactive model selector with speeds and context sizes:

![Model selector](docs/screenshots/custom_model_selector.jpeg)

It generates `.env`, starts the container, waits for the server to be ready, and opens a monitoring dashboard with server logs, GPU stats, and system stats:

![Monitoring dashboard](docs/screenshots/integrated_dashboard.jpeg)

**Dashboard controls:**
- **`q`** — Stop the server and exit
- **`r`** — Stop the server and return to the model menu
- **`Up/Down/PgUp/PgDn`** — Scroll server logs

**Access:**
- **Web UI:** http://localhost:8080 — llama.cpp's built-in chat interface
- **API:** http://localhost:8080/v1/chat/completions

![llama.cpp built-in web UI](docs/screenshots/llama_cpp_UI.jpeg)

**Test with curl:**

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "max_tokens": 100}'
```

## Models

All models are MoE (Mixture of Experts) and defined in `models.conf`. Use the section ID with `./start.sh` to launch.

| Section ID | Model | Speed | Context | Best for |
|------------|-------|-------|---------|----------|
| `glm-flash-q4` | GLM-4.7 Flash Q4_K_M | ~140 t/s | 128K | Fast tasks, reasoning |
| `glm-flash-q8` | GLM-4.7 Flash Q8_0 | ~105 t/s | 128K | Quality reasoning, tools |
| `glm-flash-exp` | GLM-4.7 Flash Q8_0 (experimental) | ~105 t/s | 128K | Experimental |
| `gpt-oss-120b` | GPT-OSS 120B F16 | ~21 t/s | 128K | Deep reasoning, knowledge |
| `qwen3-coder-ud-q5` | Qwen3-Coder-Next UD-Q5_K_XL | ~28 t/s | 256K | Coding agents |
| `qwen3-next-ud-q5` | Qwen3-Next-80B-A3B UD-Q5_K_XL | ~28 t/s | 262K | General reasoning, ultra-long context |

### Sampler settings

Recommended client-side settings per model. Most clients override server defaults, so set these explicitly.

| Setting | GLM (general) | GLM (coding) | GPT-OSS | Qwen3-Coder | Qwen3-Next |
|---------|--------------|-------------|---------|-------------|------------|
| temperature | 1.0 | 0.7 | 1.0 | 1.0 | 0.7 |
| top_p | 0.95 | 1.0 | 1.0 | 0.95 | 0.8 |
| top_k | — | — | 0 (disabled) | 40 | 20 |
| min_p | 0.01 | 0.01 | — | 0.01 | — |

Full details and rationale: [docs/client-settings.md](docs/client-settings.md)

### Model-specific notes

**GPT-OSS 120B reasoning levels:** GPT-OSS supports configurable reasoning effort via a system prompt trigger (`"Reasoning: low/medium/high"`). This cannot be set server-side — set it in the system prompt field of your client. `medium` is the default when no system prompt is set. See the [model card](models/documentation/README_modelcard_gpt-oss-120b-GGUF.md) for details.

## Benchmarks (EvalPlus HumanEval+)

Coding benchmark: 164 Python problems (HumanEval+), pass@1, greedy decoding. HumanEval+ uses 80x more tests than standard HumanEval.

### Local results (2026-02-15)

| # | Model | HumanEval | HumanEval+ | vs FP16 ref |
|---|-------|-----------|------------|-------------|
| 1 | Claude Opus 4.6 | 98.2% | 95.1% | +4.0pp |
| 2 | Claude Opus 4.6 (thinking) | 99.4% | 93.9% | +5.2pp |
| 3 | Qwen3-Coder-Next UD-Q5_K_XL | 93.9% | 90.9% | -0.2pp |
| 4 | Qwen3-Coder-Next UD-Q6_K_XL | 92.1% | 89.0% | -2.0pp |
| 5 | GLM-4.7 Flash Q8_0 * | 89.0% | 87.2% | +2.0pp |
| 6 | GPT-OSS 120B F16 | 93.3% | 87.2% | +5.0pp |
| 7 | GLM-4.7 Flash Q4_K_M * | 87.8% | 83.5% | +0.8pp |

Full results with proprietary model comparisons: [benchmarks/evalplus/results/REPORT.md](benchmarks/evalplus/results/REPORT.md)

### Running benchmarks

```bash
cd benchmarks/evalplus
source .venv/bin/activate       # One-time setup: uv venv && uv pip install evalplus
./benchmark.sh bench-glm-flash-q4       # Smoke test (one model)
./benchmark.sh --local                  # All local models
./benchmark.sh --all                    # All models (local + Claude)
```

Full setup and usage: [benchmarks/evalplus/README.md](benchmarks/evalplus/README.md)

## Adding New Models

The `/add-model` skill provides a guided 8-phase workflow for evaluating and adding new GGUF models. **This is built for [Claude Code](https://claude.com/claude-code)** and uses its agents and skills system, but the workflow pattern (evaluate → configure → test → benchmark → document) could be adapted for other AI-assisted development tools.

1. **Evaluate** — Analyze architecture, quant options, VRAM fit (model-manager agent)
2. **Download** — User downloads files to `models/<dir>/`
3. **Create profile** — Add production profile to `models.conf` (gpu-optimizer agent)
4. **Find samplers** — Research official sampler settings (model-manager agent)
5. **Test** — Verify the model loads, generates, and performs well
6. **Create bench profile** — Add benchmark profile to `models.conf`
7. **Run benchmark** — EvalPlus HumanEval+ evaluation (benchmark agent)
8. **Update docs** — Update README, client-settings, ROADMAP (doc-keeper agent)

Usage: run `/add-model <model-name>` in Claude Code.

### Candidate models

Models being evaluated for potential addition. Model cards are in `models/documentation/CANDIDATES/`.

| Model | Params | Architecture | Specialty |
|-------|--------|-------------|-----------|
| Nemotron-3-Nano-30B-A3B | 30B / 3.5B active | Hybrid Mamba2-Transformer MoE | Reasoning, tool calling, math/coding (SWE-bench 38.8%) |
| Devstral-Small-2-24B | 24B dense | Dense Transformer | Agentic coding (SWE-bench 68.0%, Terminal Bench 22.5%), vision |
| Ministral-3-14B-Instruct | 14B | Dense + vision encoder | General-purpose, multilingual, edge-optimized |
| Ministral-3-14B-Reasoning | 14B | Dense + vision encoder | Math/STEM reasoning (AIME25 85.0%) |

## Configuration

| File | Purpose |
|------|---------|
| `models.conf` | Server config: model paths, GPU layers, context size, sampler defaults, `-ot` tensor overrides |
| `docker-compose.yml` | Docker container config, GPU device mapping, volume mounts |
| `bench-client.conf` | Benchmark client config: system prompts, reasoning levels per model |
| `.env` | Auto-generated by `start.sh` from `models.conf` — never edit manually |

Annotated template with full variable reference: [docker-compose.example.yml](docker-compose.example.yml)

## AI-Assisted Development

This project is developed with [Claude Code](https://claude.com/claude-code) using specialized agents and workflows.

| Resource | Purpose |
|----------|---------|
| `AI_INSTRUCTIONS.md` | Project context and rules for AI tools |
| `.claude/agents/` | Specialized agents (gpu-optimizer, benchmark, model-manager, builder, diagnose, api-integration, doc-keeper) |
| `.claude/skills/add-model/` | `/add-model` — 8-phase model onboarding workflow |
| `claude_plans/` | Active plan files (archived to `archive/` when done) |

**Workflow:** plan → approve → implement → test → document → commit. Non-trivial changes start as a plan file, get user approval, then are implemented with the appropriate agents.

## Roadmap & Research

See [ROADMAP.md](ROADMAP.md) for current status, completed milestones, and future plans.

**Research:** [DGX Spark vs Desktop Comparison](docs/dgx-spark-comparison.md) — analysis of when NVIDIA's DGX Spark (128 GB unified memory, Grace Blackwell) is worth it compared to a dual-GPU desktop for local inference. Key finding: Spark is 2.7x faster for GPT-OSS 120B (52.8 vs 19.7 t/s) but the desktop wins for models that fit on a single GPU.

## Documentation

- **[GPU Strategy Guide](docs/gpu-strategy-guide.md)** — GPU placement decision tree, strategies A-D, graph splits, and tuning guidance
- **[Client Settings](docs/client-settings.md)** — Recommended temperature, top_p, top_k, min_p, and system prompt settings per model
- **[Bench Profile Test Results](docs/bench-test-results.md)** — GPU optimization data: VRAM usage, speeds, OOM failures, and layer split decisions
- **[EvalPlus Benchmark Results](benchmarks/evalplus/results/REPORT.md)** — Latest HumanEval+ scores for all models vs proprietary references
- **[EvalPlus Benchmark Runner](benchmarks/evalplus/README.md)** — HumanEval+ coding benchmark setup, usage, and comparison with proprietary models
- **[DGX Spark Comparison](docs/dgx-spark-comparison.md)** — DGX Spark vs desktop analysis for local LLM inference
- **[Lessons Learned](docs/lessons_learned.md)** — Common mistakes and prevention rules
- **[docker-compose.example.yml](docker-compose.example.yml)** — Annotated compose template with full variable reference

## Repository Structure

```
.
├── README.md                      # This file
├── AI_INSTRUCTIONS.md             # Project context for AI tools
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
│   ├── dgx-spark-comparison.md            # DGX Spark vs desktop comparison (draft article)
│   └── lessons_learned.md                 # Mistakes and prevention rules
├── models/                        # GGUF files (gitignored)
│   ├── .gitkeep
│   ├── documentation/             # Model cards (README from HuggingFace)
│   │   └── CANDIDATES/            # Model cards for potential future models
│   ├── GLM-4.7-Flash/
│   ├── GPT-OSS-120b/
│   ├── Qwen3-Coder-Next/
│   │   └── UD-Q5_K_XL/
│   └── Qwen3-Next/
│       └── UD-Q5_K_XL/
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
    ├── agents/                    # Claude Code specialized agents
    │   ├── gpu-optimizer.md
    │   ├── benchmark.md
    │   ├── builder.md
    │   ├── diagnose.md
    │   ├── model-manager.md
    │   ├── api-integration.md
    │   └── doc-keeper.md
    └── skills/                    # Claude Code skills (reusable workflows)
        └── add-model/SKILL.md    # /add-model — model onboarding workflow
```

## Why Custom llama.cpp?

Ollama doesn't support the features needed for this hardware and these models:

- **`-ot` tensor overrides** — Regex-based per-layer GPU/CPU placement is essential for running 60-80 GB MoE models across 40 GB of split VRAM. Ollama has no equivalent.
- **Hardware-specific build** — CUDA 13.0 with `sm_89;sm_120` targeting both Ada and Blackwell architectures. Ollama ships a generic binary.
- **Latest features** — DeltaNet kernels, `--fit` auto-VRAM, disaggregated prompt processing for MoE — features that arrive in llama.cpp master weeks before (if ever) in Ollama.

## Updating llama.cpp

```bash
cd llama.cpp
git pull origin master
cd ..
docker compose build --no-cache
```

The `llama.cpp/` directory is a separate git repository — it's gitignored from this wrapper project and updated independently.
