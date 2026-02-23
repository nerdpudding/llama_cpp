# AI Instructions — llama.cpp Docker Wrapper

## Project overview

Custom llama.cpp Docker build for a dual-GPU desktop (RTX 4090 24GB + RTX 5070 Ti 16GB). Serves large MoE models via llama-server with precise GPU/CPU tensor placement using `-ot` regex overrides. Includes an EvalPlus HumanEval+ benchmark pipeline.

## Principles

- **SOLID, DRY, KISS** — always. No over-engineering, no premature abstractions.
- **One source of truth** — no duplicate information across files.
- **Never delete, always archive** — outdated content goes to `archive/`.
- **Modularity** — keep server config, client config, and scripts cleanly separated.
- **Keep everything up to date** — after any change, verify that READMEs, docs, agent instructions, and config files still reflect reality. Stale docs are worse than no docs.
- **Use agents when their role fits** — don't do manually what an agent is designed for. Check the agents table below before starting a task.
- **ALL code, docs, comments, plans, and commit messages MUST be in English** — always, no exceptions. The user often communicates in Dutch, but everything written to files must be English.

## Workflow

For non-trivial changes, follow this order:

1. **Plan** — create a plan in `claude_plans/` with a logical name
2. **Ask for approval** — present the plan to the user before implementing
3. **Implement** — follow the approved plan, use the best approach
4. **Test** — verify changes work (sometimes manual with user involvement)
5. **Iterate** — if tests reveal issues, fix and re-test
6. **Clean up** — archive completed plans, remove unused files (to archive), update docs and agent instructions if affected

## Project hierarchy

```
.
├── AI_INSTRUCTIONS.md                # THIS FILE — read first
├── README.md                         # Project overview and usage
├── ROADMAP.md                        # Future plans and status
├── models.conf                       # SERVER config (model, GPU layers, context, flags)
├── start.sh                          # Interactive model selector → .env → dashboard
├── dashboard.py                      # Terminal monitoring TUI (curses) — model picker (m key), switch_model(), management API port 8081
├── Dockerfile                        # Multi-stage build (CUDA 13.0, sm_89+sm_120)
├── docker-compose.yml                # Production compose file
├── docker-compose.example.yml        # Annotated template with usage instructions
├── .env.example                      # Generic template with all variables documented
├── docs/                             # Technical documentation
│   ├── gpu-strategy-guide.md           # ** GPU placement decision tree — read before configuring models **
│   ├── client-settings.md              # ** Recommended client-side sampler settings per model **
│   ├── bench-test-results.md           # Bench profile GPU optimization results (VRAM, speeds, OOM tests)
│   ├── dgx-spark-comparison.md         # DGX Spark vs desktop comparison (draft article)
│   └── lessons_learned.md              # Mistakes made and prevention rules
├── models/                           # GGUF model files (gitignored)
│   ├── documentation/                # Model cards from HuggingFace
│   │   ├── CANDIDATES/               # Model cards for potential future models
│   │   │   ├── README_Nemotron-3-Nano-30B-A3B-GGUF.md
│   │   │   ├── README_Devstral-Small-2-24B-Instruct-2512-GGUF.md
│   │   │   ├── README_Ministral-3-14B-Instruct-2512-GGUF.md
│   │   │   └── README_Ministral-3-14B-Reasoning-2512-GGUF.md
│   │   ├── README_modelcard_GLM-4.7-Flash.md
│   │   ├── README_modelcard_gpt-oss-120b-GGUF.md
│   │   ├── README_modelcard_qwen3_coder_next.md
│   │   └── README_Qwen3-Next-80B-A3B-Instruct-GGUF.md
│   ├── GLM-4.7-Flash/
│   ├── GPT-OSS-120b/
│   ├── Qwen3-Coder-Next/
│   │   └── UD-Q5_K_XL/
│   └── Qwen3-Next/
│       └── UD-Q5_K_XL/
├── benchmarks/
│   └── evalplus/                     # EvalPlus HumanEval+ benchmark pipeline
│       ├── README.md                 # ** Detailed benchmark docs — read this for benchmark work **
│       ├── benchmark.sh              # Main runner (codegen → postprocess → evaluate → report)
│       ├── codegen.sh                # Local model code generation (server lifecycle)
│       ├── codegen-custom.py         # Custom codegen with system prompt support
│       ├── postprocess-solutions.py  # Strips think tags, markdown, explanatory text
│       ├── evaluate.sh               # Runs evalplus evaluation
│       ├── generate-report.py        # Generates comparison report
│       ├── run-claude-benchmark.py   # Claude codegen via claude -p
│       ├── bench-client.conf         # CLIENT config for benchmarks (system prompts)
│       ├── extract-prompts.py        # One-time utility (already run)
│       ├── humaneval_prompts.json    # 164 HumanEval problem prompts
│       ├── reference-scores.json     # Published proprietary model scores
│       └── results/                  # Benchmark outputs (gitignored)
│           └── REPORT.md             # ** Latest EvalPlus HumanEval+ results — authoritative **
├── claude_plans/                     # Active plans (see Plan rules below)
├── archive/                          # Archived plans, old docs, superseded files
├── llama.cpp/                        # llama.cpp source (separate git repo, gitignored)
└── .claude/
    ├── agents/                       # Claude Code specialized agents
    │   ├── gpu-optimizer.md
    │   ├── benchmark.md
    │   ├── builder.md
    │   ├── diagnose.md
    │   ├── model-manager.md
    │   ├── api-integration.md
    │   └── doc-keeper.md
    └── skills/                       # Claude Code skills (reusable workflows)
        └── add-model/SKILL.md        # /add-model — 8-phase model onboarding workflow
```

## GPU strategy

Before making any GPU placement decisions (layer splits, FIT, -ot, --tensor-split):

1. **Read the model card** in `models/documentation/`. Verify dense vs MoE, expert count, active parameters.
2. **Check actual file sizes** with `ls -lh`. Never estimate from quantization names.
3. **Follow the decision tree** in `docs/gpu-strategy-guide.md`.
4. **Document reasoning** in models.conf comments, including architecture source.

Key principles:
- If the model fits entirely on GPU, keep everything on GPU. `exps=CPU` is a trade-off for when VRAM is insufficient, not a MoE default.
- Fill CUDA0 (4090, fastest) first, then CUDA1 (5070 Ti), then CPU.
- `FIT=off` for any manual placement. FIT auto-distributes and doesn't handle expert/attention priorities.

See also: `docs/lessons_learned.md` for common mistakes and prevention rules.

## Key config files

| File | Scope | Purpose |
|------|-------|---------|
| `models.conf` | Server | How llama-server starts: MODEL, CTX_SIZE, N_GPU_LAYERS, FIT, EXTRA_ARGS |
| `bench-client.conf` | Client (benchmarks) | What the benchmark client sends to the API: system prompts, reasoning levels |
| `.env` | Generated | Auto-generated from models.conf by start.sh / dashboard.py — never edit manually |

**Management API** (dashboard.py, port 8081): `GET /models` — list profiles; `GET /status` — current model and state; `POST /switch {"model": "profile-id"}` — switch model programmatically. The API blocks on POST /switch until the new model is healthy (max 300s). Only available when the dashboard is running.

**Separation of concerns:** `models.conf` = server startup config. Client-side settings (system prompts, reasoning levels) go in `bench-client.conf` for benchmarks or are set in the client UI/API for interactive use. Never mix them.

## Agents

Use agents when their role matches the task. Don't reinvent what an agent already handles. Agent files live in `.claude/agents/`.

| Agent | When to use |
|-------|-------------|
| `gpu-optimizer` | GPU placement, `-ot` regex, models.conf profiles, OOM diagnosis, layer splits |
| `model-manager` | Download/organize/verify models, quantization advice |
| `benchmark` | EvalPlus HumanEval+ benchmarks, performance comparison |
| `builder` | Docker image builds, llama.cpp updates, Dockerfile changes |
| `diagnose` | System status, GPU health, VRAM check, container troubleshooting |
| `api-integration` | OpenAI-compatible API setup, client configuration, connectivity testing |
| `doc-keeper` | Documentation audits, consistency checks, cross-reference verification, hierarchy maintenance |

After changes that affect an agent's domain, update that agent's instructions.

## Plan rules

Plans are stored in: **`claude_plans/`**

1. **Always save plans as files** — plans must be persistent, never just in conversation.
2. **Use logical names** — e.g. `PLAN_fair_postprocessing_benchmark.md`. If plan mode generates a random name, rename it immediately.
3. **No duplicates** — if a plan already exists for the same topic, update it instead of creating a new one.
4. **Archive when done** — completed plans move to `archive/` with a date prefix: `2026-02-15_fair_postprocessing_benchmark.md`.

## Archive rules

Everything goes to: **`archive/`**

- Completed plans (from `claude_plans/`)
- Superseded documentation
- Old scripts replaced by new ones
- Outdated daily schedules or todo files

Never delete files. Always archive.

## Git commits

- Write normal, descriptive commit messages.
- Never add "Co-Authored-By: Claude" or AI attribution.
- Only commit when explicitly asked.

## After compaction

When resuming after compaction, read in this order:
1. This file (`AI_INSTRUCTIONS.md`)
2. Current task tracker if one exists (e.g. `todo_15_feb.md`)
3. Active plans in `claude_plans/`
4. Then continue with the task
