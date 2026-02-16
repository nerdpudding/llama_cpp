# Roadmap

## Current Status

Five models are configured in `models.conf` and selectable via `./start.sh` on a dual-GPU desktop (RTX 4090 + RTX 5070 Ti):

- **GLM-4.7 Flash Q4_K_M** — ~140 t/s, 128K context, fast general tasks, reasoning, tool calling
- **GLM-4.7 Flash Q8_0** — ~105 t/s, 128K context, higher quality reasoning and tool calling
- **GPT-OSS 120B F16** — ~21 t/s, 128K context, deep reasoning, knowledge, structured output
- **Qwen3-Coder-Next UD-Q5_K_XL** — ~28 t/s, 256K context, coding agents, agentic tasks
- **Qwen3-Next-80B-A3B UD-Q5_K_XL** — ~28 t/s, 262K context, general-purpose reasoning, knowledge, agentic tasks, ultra-long context

All models are MoE. GPU placement uses optimized `-ot` regex configurations for per-layer tensor placement. See `docs/gpu-strategy-guide.md` for the decision tree and `docs/bench-test-results.md` for measured performance data. Latest EvalPlus HumanEval+ scores are in `benchmarks/evalplus/results/REPORT.md`.

**Monitoring dashboard:** `start.sh` now launches the container in the background, waits for server health, and opens a Python curses TUI (`dashboard.py`) with four panels: server logs (scrollable), per-GPU VRAM/utilization/power/temp monitoring, system stats (CPU/RAM/swap/container), and keyboard controls (`q` stop & exit, `r` stop & return to menu). Docker healthcheck is also configured for container-level health awareness. Use `--no-dashboard` for raw log output.

## Done

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

### Production profile optimization (2026-02-16)
- All production profiles optimized with explicit GPU layer placement and `-b 2048 -ub 512`
- Key discovery: `-ub` (micro-batch) determines compute buffer VRAM — switching to `-ub 512` freed 449-2000 MiB per GPU
- GLM Q4: Strategy A (single GPU), ~142.7 t/s
- GLM Q8: Strategy C (33+14=47/47), ~103.8 t/s
- GPT-OSS 120B: Strategy D (11+4=15/36), ~20.7 t/s
- Qwen3 UD-Q5: Strategy D (17+8=25/48), ~27.9 t/s (+8% from 25.8)
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
- Draft article in `docs/dgx-spark-comparison.md`, data archived in `archive/dgx-spark-benchmarks.md`

### Streamlined model onboarding (2026-02-16)
- `/add-model` skill with 8-phase guided workflow for evaluating and adding new GGUF models
- Uses specialized agents (model-manager, gpu-optimizer, benchmark, doc-keeper) at each phase
- Candidate models listed in README under "Adding New Models"

## Next Up

*(Nothing currently scheduled — see Future for planned work.)*

## Future

### API integration with external tools
- Configure Claude Code to use the local llama-server as an alternative backend
- Test integration with Continue.dev, aider, and other coding assistants
- Test integration with personal AI assistants like OpenClaw
- Set up OpenAI-compatible client configurations for various tools
- Define use cases: when local inference is worthwhile vs. cloud API
- Goal: agents can be configured to use local models alongside cloud APIs (e.g. Claude for complex tasks, local model for simpler ones)

### Model switching from API / agents
- Allow switching the active model via API call or agent action — stop the current server, load a different model, restart
- Enable workflows where an agent spins up a specific model for a task and shuts it down when done
- Investigate whether llama.cpp's `--model-store` (if/when available) could handle this without full restarts

### Extended benchmarks
- Add benchmarks for tasks beyond coding (reasoning, instruction following, tool calling)
- Regression testing when updating llama.cpp
