# Roadmap

## Current Status

Five models are active in `models.conf` and selectable via `./start.sh` on a dual-GPU desktop (RTX 4090 + RTX 5070 Ti), plus one pending:

- **GLM-4.7 Flash Q4_K_M** — ~147 t/s, 128K context, fast general tasks, reasoning, tool calling (MoE)
- **GLM-4.7 Flash Q8_0** — ~112 t/s, 128K context, higher quality reasoning and tool calling (MoE)
- **GLM-4.7 Flash Q8_0 (experimental)** — ~112 t/s, 128K context, experimental config (MoE)
- **Qwen3.5-35B-A3B UD-Q6_K_XL** — ~120 t/s, 262K context, thinking model, coding, agentic tasks (MoE, DeltaNet)
- **Qwen3.5-122B-A10B UD-Q4_K_XL** — ~18 t/s, 262K context, quality king, deep reasoning, coding (MoE, DeltaNet, 10B active)
- **Qwen3.5-27B UD-Q8_K_XL** — pending (CUDA crash on first inference — illegal memory access on device 0, needs investigation)

Three models retired 2026-02-26: GPT-OSS 120B, Qwen3-Coder-Next, Qwen3-Next-80B-A3B — replaced by the Qwen3.5 family after benchmark comparison. See the Done section below and `models.conf` for details.

GPU placement uses `--fit` with `--n-gpu-layers auto` — FIT automatically distributes layers and expert tensors across CUDA0, CUDA1, and CPU RAM. See `docs/gpu-strategy-guide.md` for details and `docs/bench-test-results.md` for historical performance data. Latest EvalPlus HumanEval+ scores are in `benchmarks/evalplus/results/REPORT.md`.

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
- Initial run: 5 local models + 2 Claude configurations benchmarked (2026-02-15)
- Extended run with Qwen3.5 models (2026-02-26): added Qwen3.5-122B-A10B and Qwen3.5-35B-A3B
- Optimized bench profiles in `models.conf` (bench-*) with 10K context and maximized GPU layers
- Top local result: Qwen3.5-122B-A10B UD-Q4_K_XL at 97.6% HumanEval / 94.5% HumanEval+ (#2 behind Claude Opus 4.6)
- Qwen3.5-35B-A3B: 95.1% / 90.9% — ties Qwen3-Coder-Next at 4x the speed
- Claude Opus 4.6: 98.2% / 95.1% (non-thinking) and 99.4% / 93.9% (thinking)
- Full results: `benchmarks/evalplus/results/REPORT.md`
- See `benchmarks/evalplus/README.md` for setup and usage

### Model lineup refresh (2026-02-26)
- Added Qwen3.5-35B-A3B UD-Q6_K_XL (~120 t/s) and Qwen3.5-122B-A10B UD-Q4_K_XL (~18 t/s) after benchmark comparison
- Added Qwen3.5-27B UD-Q8_K_XL (pending — CUDA crash on first inference, under investigation)
- Retired GPT-OSS 120B: outclassed by Qwen3.5-122B (94.5% vs 87.2% HumanEval+) with similar speed
- Retired Qwen3-Coder-Next: matched by Qwen3.5-35B (90.9% HumanEval+ each) at ~4x the speed (~120 vs ~33 t/s)
- Retired Qwen3-Next-80B-A3B: superseded by Qwen3.5-122B (94.5% vs 93.9% HumanEval+) with better architecture
- Retired model profiles commented out in `models.conf` (not deleted — reactivate if needed)
- Benchmark data and REPORT.md scores preserved for retired models

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

### Claude Code ↔ local llama.cpp integration (2026-02-23 — 2026-02-24)
- **Phase 1-3:** Anthropic Messages API verified, Claude Code connected to local GLM Flash Q4, chat + tool use confirmed
- **Phase 4:** `claude-local` wrapper with `CLAUDE_CONFIG_DIR` isolation, bubblewrap sandbox tested (bash restricted, Write/Edit tools not sandboxed — Claude Code limitation), VS Code IDE integration working via symlink workaround
- **Phase 5:** Pre-flight health check in wrapper, management API model switching works mid-session (context preserved), recommended workflow documented
- **Phase 6:** Architecture document (`docs/architecture.md`), README updated, documentation consolidated
- Setup: `claude-local/README.md` | Decision: `docs/decisions/2026-02-24_claude-code-local-setup.md`

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
- Investigate sandbox localhost whitelist — currently sandbox blocks all bash network access including localhost, which prevents management API calls (`POST /switch`) from within a sandboxed session. Check if bubblewrap or Claude Code's sandbox config supports whitelisting specific ports or addresses.

### Automatic model switching in claude-local
- Enable claude-local to automatically switch the locally loaded llama.cpp model based on the task at hand. For example: switch to Qwen3-Coder for code generation, GPT-OSS for deep reasoning — all within the same claude-local session, using the llama.cpp management API (`POST /switch` on port 8081).
- Currently model switching works manually (dashboard `m` key, or bash curl to the management API). The goal is to automate this via a skill or agent that decides which local model fits the current task and triggers the switch.
- Requires deeper understanding of how Claude Code handles model routing internally, and how to gracefully handle the ~15-30s server downtime during a model switch.
- Foundation already proven: management API works from within claude-local, session survives the switch, conversation context is preserved for the new model.

### Revisit `-ts` (tensor split) for asymmetric GPU placement
- FIT auto distributes based on available VRAM per device but doesn't account for GPU speed differences. On asymmetric setups (RTX 4090 + RTX 5070 Ti), this leads to suboptimal placement — e.g., the 27B dense bench profile at 10K context splits ~13 GB / 8 GB across CUDA0/CUDA1 instead of maximizing the faster 4090.
- ggerganov recommended `-ts` (tensor split) in issue #19816 as the official way to control GPU distribution ratios. Previous testing of `-ts` showed poor results, but that test was done with the `N_GPU_LAYERS=99` hardcoded config error still active — so `-ts` never got a fair test.
- Worth re-testing now that the config is fixed (`N_GPU_LAYERS=auto`), specifically for:
  - Dense model bench profiles where Strategy A (single GPU) is borderline
  - Production profiles where FIT's automatic split is suboptimal for the faster GPU
  - Comparison: FIT auto vs `-ts 3,1` (75/25 split matching VRAM ratio) vs Strategy A

### Extended benchmarks
- Add benchmarks for tasks beyond coding (reasoning, instruction following, tool calling)
- Regression testing when updating llama.cpp
