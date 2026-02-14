# Plan: Project Organization & Documentation

## Context

This project wraps llama.cpp with a custom Docker build optimized for a dual-GPU desktop (RTX 4090 + RTX 5070 Ti). The project has outgrown its initial structure: model files are now in subdirectories, two key guides have outdated paths, there's no README, no git repo, and the docker-compose.example is an unused duplicate. This plan brings everything into a clean, documented state.

---

## Step 1: Rename model directory with space

The directory `models/GLM 4.7 Flash/` contains a space that breaks the Dockerfile CMD (line 80: `exec llama-server ${ARGS}` — unquoted expansion causes word splitting).

**Action:** Rename `models/GLM 4.7 Flash/` to `models/GLM-4.7-Flash/`

Current contents after user cleanup:
- `GLM-4.7-Flash-Q4_K_M.gguf`
- `GLM-4.7-Flash-Q8_0.gguf`
- `other/GLM-4.7-Flash-experimental.Q8_0.gguf`

---

## Step 2: Create `docs/` with English guides

Both documents will have a clear Table of Contents at the top and consistent markdown formatting.

### 2a: `docs/gpt-oss-120b-configuration-guide.md`

**Source:** `gpt-oss-120b-desktop-guide_WORKING.md` (already English)

Changes:
- Add TOC at the top
- Fix model path: `MODEL=GPT-OSS-120b/gpt-oss-120b-F16.gguf`
- Clean up informal "wait, actually" phrasing (line ~101 area)
- Add cross-reference to `.env.gpt-oss-120b` for ready-to-use config
- Keep all sections: Hardware, Model explanation, Architecture, Working Config, Memory Breakdown, Performance, Failed Attempts, Headroom, DGX Spark Comparison

### 2b: `docs/llama-cpp-flags-and-qwen3-strategy.md`

**Source:** `llama-cpp-flags-en-qwen-strategie.md` (Dutch, 575 lines)

Changes:
- Add TOC at the top
- Full translation to English (prose sections; code blocks/tables/regex stay as-is)
- Fix all model paths to subdirectory structure:
  - `MODEL=Qwen3-Coder-Next/UD-Q6_K_XL/Qwen3-Coder-Next-UD-Q6_K_XL-00001-of-00003.gguf`
  - `MODEL=Qwen3-Coder-Next/UD-Q5_K_XL/Qwen3-Coder-Next-UD-Q5_K_XL-00001-of-00003.gguf`
  - `MODEL=Qwen3-Coder-Next/Q6_K/Qwen3-Coder-Next-Q6_K-00001-of-00003.gguf` (non-UD variant)
  - `MODEL=GPT-OSS-120b/gpt-oss-120b-F16.gguf`
- Add cross-reference to `.env.qwen3-coder` and `.env.qwen3-coder-q6k`
- Preserve all `-ot` regex lookup tables, strategy test results, KV cache data, architecture comparison

### 2c: Archive originals

- `mv gpt-oss-120b-desktop-guide_WORKING.md archive/`
- `mv llama-cpp-flags-en-qwen-strategie.md archive/`

---

## Step 3: Create per-model `.env` files and improve example

### 3a: `docker-compose.example.yml`

Replace `docker-compose.example` (currently identical to docker-compose.yml) with a well-commented template explaining the `.env` file workflow:
- How to copy a model config: `cp .env.qwen3-coder .env && docker compose up`
- How to switch models
- List of available `.env.*` files with descriptions
- API/Web UI access URLs
- Full variable reference table in comments

### 3b: `.env.glm-flash`

```
MODEL=GLM-4.7-Flash/GLM-4.7-Flash-Q8_0.gguf
CTX_SIZE=131072
N_GPU_LAYERS=99
FIT=on
EXTRA_ARGS=--jinja -np 1
```

Comments: model fits entirely in VRAM, also mention Q4_K_M and experimental variants.

### 3c: `.env.gpt-oss-120b`

```
MODEL=GPT-OSS-120b/gpt-oss-120b-F16.gguf
CTX_SIZE=65536
N_GPU_LAYERS=99
FIT=off
EXTRA_ARGS=--jinja -np 1 -b 4096 -ub 4096 -ot blk\.([0-9]|1[01])\.=CUDA0,blk\.(1[2-5])\.=CUDA1,exps=CPU
```

Comments: ~20 t/s at 64K context, memory breakdown, link to guide.

### 3d: `.env.qwen3-coder` (UD-Q6_K_XL baseline)

```
MODEL=Qwen3-Coder-Next/UD-Q6_K_XL/Qwen3-Coder-Next-UD-Q6_K_XL-00001-of-00003.gguf
CTX_SIZE=262144
N_GPU_LAYERS=99
FIT=off
EXTRA_ARGS=--jinja -np 1 -b 2048 -ub 2048 --no-context-shift --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 -ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU
```

Comments: 21.4 t/s baseline, 256K context, also mention UD-Q5_K_XL speed alternative.

### 3e: `.env.qwen3-coder-q6k` (Q6_K non-UD variant)

```
MODEL=Qwen3-Coder-Next/Q6_K/Qwen3-Coder-Next-Q6_K-00001-of-00003.gguf
CTX_SIZE=262144
N_GPU_LAYERS=99
FIT=off
EXTRA_ARGS=--jinja -np 1 -b 2048 -ub 2048 --no-context-shift --temp 1.0 --top-p 0.95 --top-k 40 --min-p 0 -ot blk\.([0-9]|1[0-2])\.=CUDA0,blk\.(1[3-8])\.=CUDA1,exps=CPU
```

Comments: standard Q6_K quantization (non-UD), note that -ot regex may need adjustment based on testing (similar size to UD-Q6_K_XL, so same layer split is a reasonable starting point).

### 3f: `.env.example`

Create a generic `.env.example` file (best practice) with all variables documented and sensible defaults, so users understand the full variable set. This is the template; the model-specific `.env.*` files are the ready-to-use configs.

### 3g: Delete `docker-compose.example`

Replaced by `docker-compose.example.yml`.

---

## Step 4: Update and expand Claude agents

### Update existing agents

All three agents reference `llama-cpp-setup-brief.md` (now in archive). Update:

- `.claude/agents/benchmark.md` (line 10-11): Reference `README.md` and `docs/`
- `.claude/agents/builder.md` (line 10): Reference `README.md` and `docs/`; update "Files you own" to replace `USAGE.md` with `docker-compose.example.yml`
- `.claude/agents/diagnose.md` (line 10): Reference `README.md` and `docs/`

### Create new agents

- **`.claude/agents/model-manager.md`** — Helps download models (e.g. from Hugging Face), organize them in the correct subdirectory, verify file integrity, list available models and their sizes, suggest quantization trade-offs for the hardware
- **`.claude/agents/api-integration.md`** — Helps set up and test API integration: configure Claude Code or other tools to use the local llama-server endpoint (`localhost:8080/v1/`), test chat completions, troubleshoot connectivity, set up OpenAI-compatible client configs

---

## Step 5: Create `README.md`

Project README with TOC, covering:
- **Project overview:** Custom llama.cpp Docker build for specific hardware
- **Hardware table:** RTX 4090 + RTX 5070 Ti, AMD 5800X3D, 64GB DDR4
- **Why not Ollama:** `-ot` regex, hardware-specific build, latest features
- **Target models table:** GLM Flash, GPT-OSS 120B, Qwen3-Coder-Next with speed/use case
- **Repository structure:** tree diagram showing all key files and folders
- **Prerequisites:** Docker, NVIDIA Container Toolkit, driver version, CUDA 13.0
- **Installation/Setup:** Clone this repo, clone llama.cpp, download models, build Docker image
- **Quick start / Usage:** Copy .env, docker compose up, access Web UI/API
- **Switching models:** docker compose down, copy different .env, up
- **Updating llama.cpp:** cd llama.cpp && git pull, rebuild
- **Documentation links:** Pointers to `docs/` guides and `ROADMAP.md`

Roadmap content goes in separate file (see Step 6).

---

## Step 6: Create `ROADMAP.md`

Separate roadmap document with:

- **Current status:** What's working now (3 models configured, Docker build, tested configs)
- **Next up:**
  - Formal benchmarks (LiveCodeBench, HumanEval, or similar) across all 3 models
  - Temperature/sampling parameter sweeps for coding tasks
  - VRAM optimization experiments (different KV cache types, batch sizes)
- **Future:**
  - API integration with Claude Code (use local model as coding assistant)
  - API integration with other tools (Continue.dev, aider, etc.)
  - Test `--model-store` for multi-model hot-swap when available in llama.cpp
  - Explore row split mode for asymmetric GPU workloads
  - Automated benchmark suite (scripted tests with result logging)
- **Considered & deferred:**
  - DGX Spark purchase (see `archive/dgx-spark-benchmarks.md`)

---

## Step 7: Git setup

### 7a: Update `.gitignore`

Current file has `models/*.gguf` which does NOT match files in subdirectories. Full replacement:

```gitignore
# GGUF model files (large binaries)
**/*.gguf

# Active environment config (user copies from .env.* templates)
.env

# llama.cpp source (has its own git repo, pulled independently)
llama.cpp/
```

Note: `.env.*` template files (`.env.glm-flash`, `.env.gpt-oss-120b`, etc.) are NOT ignored — they are tracked as project configuration. Only the active `.env` is ignored.

### 7b: Initialize repo and commit

```bash
git init
git add .
git commit -m "Initial commit: llama.cpp Docker wrapper for dual-GPU desktop"
```

**Tracked:** Dockerfile, docker-compose.yml, docker-compose.example.yml, .env.*, .env.example, docs/, archive/, models/.gitkeep, README.md, ROADMAP.md, .claude/, .gitignore, .dockerignore, claude_plans/

**NOT tracked:** llama.cpp/ (gitignored), **/*.gguf (gitignored), .env (gitignored)

**Updating llama.cpp later:** `cd llama.cpp && git pull` — independent of wrapper repo.

**Pushing to GitHub:** `git remote add origin <url> && git push -u origin main`

---

## Execution Order

1. Rename `models/GLM 4.7 Flash/` → `models/GLM-4.7-Flash/`
2. Create `docs/` directory
3. Create `docs/gpt-oss-120b-configuration-guide.md` (with TOC)
4. Create `docs/llama-cpp-flags-and-qwen3-strategy.md` (with TOC, full English translation)
5. Move originals to `archive/`
6. Create `docker-compose.example.yml`
7. Create `.env.example`, `.env.glm-flash`, `.env.gpt-oss-120b`, `.env.qwen3-coder`, `.env.qwen3-coder-q6k`
8. Delete `docker-compose.example`
9. Update `.claude/agents/benchmark.md`, `builder.md`, `diagnose.md`
10. Create `.claude/agents/model-manager.md`, `.claude/agents/api-integration.md`
11. Create `README.md` (with TOC, repo structure, install/usage)
12. Create `ROADMAP.md`
13. Update `.gitignore`
14. `git init` + initial commit

---

## Critical Files

| File | Action |
|------|--------|
| `gpt-oss-120b-desktop-guide_WORKING.md` | Read → clean up → write to `docs/` → archive |
| `llama-cpp-flags-en-qwen-strategie.md` | Read → translate → write to `docs/` → archive |
| `docker-compose.yml` | Read (reference for .env vars) — do not modify |
| `docker-compose.example` | Delete (replaced by .yml version) |
| `Dockerfile` | Read-only (verify MODEL path handling) — do not modify |
| `.gitignore` | Rewrite with correct patterns |
| `.claude/agents/*.md` | Update references, add 2 new agents |

---

## Verification

1. **Docs:** Read both files in `docs/`, confirm all model paths match actual `models/` subdirectories
2. **Env files:** `cp .env.glm-flash .env && docker compose config` — verify env vars resolve correctly
3. **Git:** `git status` after commit — verify llama.cpp/ and *.gguf ignored, all project files tracked, .env.* files tracked but .env ignored
4. **Agents:** Confirm all agent references point to existing files
5. **Structure:** `ls -R` to verify final directory layout matches README tree diagram
