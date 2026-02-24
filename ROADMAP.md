# Roadmap

## Current Status

Six models are configured in `models.conf` and selectable via `./start.sh` on a dual-GPU desktop (RTX 4090 + RTX 5070 Ti):

- **GLM-4.7 Flash Q4_K_M** — ~147 t/s, 128K context, fast general tasks, reasoning, tool calling
- **GLM-4.7 Flash Q8_0** — ~112 t/s, 128K context, higher quality reasoning and tool calling
- **GLM-4.7 Flash Q8_0 (experimental)** — ~112 t/s, 128K context, experimental config
- **GPT-OSS 120B F16** — ~22 t/s, 128K context, deep reasoning, knowledge, structured output
- **Qwen3-Coder-Next UD-Q5_K_XL** — ~33 t/s, 256K context, coding agents, agentic tasks
- **Qwen3-Next-80B-A3B UD-Q5_K_XL** — ~33 t/s, 256K context, general-purpose reasoning, knowledge, agentic tasks, ultra-long context

All models are MoE. GPU placement uses `--fit` with `--n-gpu-layers auto` — FIT automatically distributes layers and expert tensors across CUDA0, CUDA1, and CPU RAM. See `docs/gpu-strategy-guide.md` for details and `docs/bench-test-results.md` for historical performance data. Latest EvalPlus HumanEval+ scores are in `benchmarks/evalplus/results/REPORT.md`.

**Monitoring dashboard:** `start.sh` launches the container in the background, waits for server health, and opens a Python curses TUI (`dashboard.py`) with four panels: server logs (scrollable), per-GPU VRAM/utilization/power/temp monitoring, system stats (CPU/RAM/swap/container), and keyboard controls (`q` stop & exit, `r` stop & return to menu, `m` open model picker). The dashboard survives container restarts — model switching happens inside the TUI without returning to the shell. A management API runs on port 8081 (`GET /models`, `GET /status`, `POST /switch`) for programmatic model switching by agents and external tools. Use `--no-dashboard` for raw log output.

## Done

### Model switching from dashboard and management API (2026-02-23)
- Model picker overlay in dashboard (press `m`) — arrow keys + Enter to select, `Esc` to cancel
- `switch_model()` method: stops container, regenerates `.env` from selected profile, starts new container, reconnects log stream, polls health
- Dashboard survives container restarts — TUI stays running throughout the switch
- Log buffer persists: old model logs remain scrollable, separator line added between models
- Server state tracking: idle / starting / running / stopping, shown in control bar
- Management API on port 8081 (stdlib `http.server`, no dependencies):
  - `GET /models` — list all profiles with current active model marked
  - `GET /status` — current model, server state, status message
  - `POST /switch` — switch model by profile ID, blocks until healthy (or 300s timeout)
- `start.sh` passes `--models-conf` and `--current-profile` to dashboard.py
- Plan: `archive/2026-02-23_PLAN_model_switching.md`

### Formal benchmarks (EvalPlus HumanEval+)
- EvalPlus benchmark runner in `benchmarks/evalplus/` — runs HumanEval+ (164 Python problems) against all models via the llama.cpp OpenAI API
- 5 local models + 2 Claude configurations benchmarked (2026-02-15)
- Optimized bench profiles in `models.conf` (bench-*) with 10K context and maximized GPU layers
- Top local result: Qwen3-Coder-Next UD-Q5_K_XL at 93.9% HumanEval / 90.9% HumanEval+
- Claude Opus 4.6: 98.2% / 95.1% (non-thinking) and 99.4% / 93.9% (thinking)
- Full results: `benchmarks/evalplus/results/REPORT.md`
- See `benchmarks/evalplus/README.md` for setup and usage

### Bench profile GPU optimization
- All bench profiles optimized: reduced context (16K→10K), smaller batch sizes (-b 512 -ub 512), more GPU layers
- OOM tested all profiles, documented results in `docs/bench-test-results.md`

### Production profile optimization (2026-02-16, revised 2026-02-23)
- Key discovery (2026-02-16): `-ub` (micro-batch) determines compute buffer VRAM — switching to `-ub 512` freed 449-2000 MiB per GPU
- Initial approach: explicit `-ot` GPU layer placement with `FIT=off` and `N_GPU_LAYERS=99`
- Revised approach (2026-02-23): converted ALL profiles to `--fit` with `--n-gpu-layers auto` after discovering hardcoded `N_GPU_LAYERS=99` prevented FIT from working (issue #19816)
- FIT auto handles GPU/CPU distribution automatically, including MoE expert offload
- Qwen3-Next result: 32.9 t/s at 262K context with FIT (vs 26.5 t/s with manual -ot) and 55 graph splits (vs 136)
- Documented in `docs/gpu-strategy-guide.md` and `docs/lessons_learned.md`

### Documentation consolidation and model selection (2026-02-16)
- Consolidated project hierarchy, archived outdated docs, organized `docs/`
- Added `docs/client-settings.md` — sampler settings per model with official sources
- Added doc-keeper agent for documentation consistency audits
- Removed UD-Q6 (UD-Q5 is faster and higher scoring on all metrics)
- Rewrote `start.sh` menu with descriptions, speeds, and bench submenu
- Added capability and sampler quick-reference tables to client-settings.md
- GPT-OSS reasoning levels (low/medium/high) documented with trade-offs

### DGX Spark comparison article (concept)
- Researched DGX Spark vs desktop for GPT-OSS 120B inference
- Draft article in `docs/dgx-spark-comparison.md`

### Streamlined model onboarding (2026-02-16)
- `/add-model` skill with 8-phase guided workflow for evaluating and adding new GGUF models
- Uses specialized agents (model-manager, gpu-optimizer, benchmark, doc-keeper) at each phase
- Candidate models listed in README under "Adding New Models"

## In Progress

### Claude Code ↔ local llama.cpp integration (2026-02-23)
- Phases 1-3 done: Anthropic Messages API verified in build, tested with curl, Claude Code successfully connected to local GLM Flash Q4 (chat + tool use working)
- **Decision made:** Separate `claude-local` instance with its own HOME (credential isolation) + bubblewrap sandbox (filesystem/privilege restriction). See `docs/decisions/2026-02-24_claude-code-local-setup.md`
- Next: Phase 4 (install bubblewrap, create dual-instance setup, test sandbox), Phase 5 (convenience scripts, management API integration), Phase 6 (architecture.md, README restructure, documentation)
- Plan: `claude_plans/PLAN_claude_code_local_integration.md`

## Future

### API integration with other external tools
- Test integration with Continue.dev, aider, and other coding assistants
- Test integration with personal AI assistants like OpenClaw
- Set up OpenAI-compatible client configurations for various tools
- Define use cases: when local inference is worthwhile vs. cloud API
- Goal: agents can be configured to use local models alongside cloud APIs (e.g. Claude for complex tasks, local model for simpler ones)
- Foundation: management API (`POST /switch` on port 8081) is already built and tested

### claude-local convenience improvements
- Auto-start llama-server from `claude-local` wrapper: if the server is not running, open `start.sh` in a new terminal, let the user pick a model, wait for server health, then start Claude Code. Requires solving: repo path detection (wrapper can run from anywhere), terminal emulator detection (gnome-terminal, xterm, etc.).
- Investigate `/resume` issue — serialization error when resuming sessions with `CLAUDE_CONFIG_DIR`. Test in isolated setup (standalone project, no concurrent sessions) to narrow down the cause.

### Extended benchmarks
- Add benchmarks for tasks beyond coding (reasoning, instruction following, tool calling)
- Regression testing when updating llama.cpp
