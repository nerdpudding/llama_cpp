# Plan: Central Model Config + Start Script

## Context

The project has 7 models on disk but only 4 `.env.*` config files. Switching models requires manually copying `.env` files. As more models get added, this approach doesn't scale — it's easy to forget which `.env` to use, configs are scattered across multiple files, and adding a new model means creating yet another file plus updating docs.

This plan replaces the per-model `.env.*` files with a single `models.conf` and a `start.sh` menu script that reads it, presents a selector, generates `.env`, and runs docker compose.

---

## Step 1: Create `models.conf`

Single INI-style config file with all 7 models. Format chosen over JSON (no comments, regex escaping issues) and YAML (needs yq). Pure bash parsing, zero dependencies.

Each `[section]` is a model. Required field: `NAME`, `MODEL`. All other fields optional (docker-compose.yml defaults apply when omitted).

**Models to include:**

| Section ID | Name | Model File | Status |
|-----------|------|------------|--------|
| `glm-flash-q4` | GLM-4.7 Flash Q4_K_M | `GLM-4.7-Flash/GLM-4.7-Flash-Q4_K_M.gguf` | New |
| `glm-flash` | GLM-4.7 Flash Q8_0 | `GLM-4.7-Flash/GLM-4.7-Flash-Q8_0.gguf` | From `.env.glm-flash` |
| `glm-flash-exp` | GLM-4.7 Flash Q8_0 (experimental) | `GLM-4.7-Flash/other/GLM-4.7-Flash-experimental.Q8_0.gguf` | New |
| `gpt-oss-120b` | GPT-OSS 120B F16 | `GPT-OSS-120b/gpt-oss-120b-F16.gguf` | From `.env.gpt-oss-120b` |
| `qwen3-coder-q5` | Qwen3-Coder-Next UD-Q5_K_XL (speed) | `Qwen3-Coder-Next/UD-Q5_K_XL/...` | New (config from docs strategy 3) |
| `qwen3-coder` | Qwen3-Coder-Next UD-Q6_K_XL (baseline) | `Qwen3-Coder-Next/UD-Q6_K_XL/...` | From `.env.qwen3-coder` |
| `qwen3-coder-q6k` | Qwen3-Coder-Next Q6_K | `Qwen3-Coder-Next/Q6_K/...` | From `.env.qwen3-coder-q6k` |

Performance notes, layer splits, and doc references preserved as comments per section.

---

## Step 2: Create `start.sh`

Bash script (~120 lines). Flow:

1. **Parse args**: `./start.sh [model-id]` — skips menu if ID given directly
2. **Check prerequisites**: docker running? container already up? (offer to stop if so)
3. **Show menu** (if no arg):
   ```
   llama.cpp Model Selector
   ========================

   1) GLM-4.7 Flash Q4_K_M                        128K ctx
   2) GLM-4.7 Flash Q8_0                           128K ctx
   3) GLM-4.7 Flash Q8_0 (experimental)            128K ctx
   4) GPT-OSS 120B F16                              64K ctx
   5) Qwen3-Coder-Next UD-Q5_K_XL (speed)         256K ctx
   6) Qwen3-Coder-Next UD-Q6_K_XL (baseline)      256K ctx
   7) Qwen3-Coder-Next Q6_K                        256K ctx

   q) Quit

   Select model [1-7]:
   ```
4. **Generate `.env`** from selected section in `models.conf`
5. **Start**: `exec docker compose up` (foreground, Ctrl+C to stop)

Key implementation details:
- INI parser using bash associative array (`declare -A`), no `eval`, no external tools
- Model file existence check before starting (clear error if missing)
- `exec` replaces bash process so Ctrl+C goes directly to docker compose
- CLI shortcut: `./start.sh qwen3-coder` for muscle memory

---

## Step 3: Archive `.env.*` files

Move to `archive/env-templates/`:
- `.env.glm-flash`
- `.env.gpt-oss-120b`
- `.env.qwen3-coder`
- `.env.qwen3-coder-q6k`

Keep `.env.example` in root — it documents ALL available docker-compose variables (including advanced ones like `SPLIT_MODE`, `TENSOR_SPLIT`, `FIT_TARGET` etc.) which is useful as a reference independent of `models.conf`.

---

## Step 4: Update documentation

**README.md:**
- Quick Start: `./start.sh` instead of `cp .env.* .env`
- Switching Models: show both menu and CLI shortcut
- Repository Structure: add `models.conf` and `start.sh`, remove `.env.*` model files
- Available configs table: reference `models.conf` section IDs

**docker-compose.example.yml:**
- Update header comments to mention `start.sh` as primary workflow

**docs/llama-cpp-flags-and-qwen3-strategy.md line 53:**
- References `.env.qwen3-coder-q5k` (never existed) — update to reference `models.conf [qwen3-coder-q5]`

---

## Step 5: Git commit

Stage: `models.conf`, `start.sh`, updated `README.md`, updated docs, archived `.env.*` files.

---

## Critical Files

| File | Action |
|------|--------|
| `models.conf` | Create (new) |
| `start.sh` | Create (new) |
| `.env.glm-flash` | Archive |
| `.env.gpt-oss-120b` | Archive |
| `.env.qwen3-coder` | Archive |
| `.env.qwen3-coder-q6k` | Archive |
| `.env.example` | Keep as-is |
| `README.md` | Update quick start, switching, structure |
| `docker-compose.example.yml` | Update header comments |
| `docs/llama-cpp-flags-and-qwen3-strategy.md` | Fix `.env.qwen3-coder-q5k` reference |
| `docker-compose.yml` | No changes |
| `Dockerfile` | No changes |

## Verification

1. `./start.sh` — verify menu shows all 7 models with correct names and context sizes
2. Select each model — verify generated `.env` matches the original `.env.*` content
3. `./start.sh qwen3-coder` — verify CLI shortcut works
4. `./start.sh nonexistent` — verify error message lists available models
5. Verify model file existence check works (point MODEL to a fake path)
6. `docker compose config` after `.env` generation — verify env vars resolve correctly
