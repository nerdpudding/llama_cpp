# Roadmap

## Current Status

Seven models are configured in `models.conf` and selectable via `./start.sh` on a dual-GPU desktop (RTX 4090 + RTX 5070 Ti):

- **GLM-4.7 Flash Q4_K_M / Q8_0 / experimental** — fits entirely in VRAM, 128K context
- **GPT-OSS 120B F16** — ~20 t/s, 64K context, large MoE with CPU expert offloading
- **Qwen3-Coder-Next UD-Q5_K_XL** — 25.8 t/s, 256K context, speed alternative
- **Qwen3-Coder-Next UD-Q6_K_XL** — 21.4 t/s, 256K context, baseline for coding tasks
- **Qwen3-Coder-Next Q6_K** — ~21 t/s, 256K context, standard quant alternative

MoE models use optimized `-ot` regex configurations for per-layer GPU/CPU tensor placement. Tested configurations are documented in `docs/` with memory breakdowns, VRAM utilization, and performance data.

**Monitoring dashboard:** `start.sh` now launches the container in the background, waits for server health, and opens a Python curses TUI (`dashboard.py`) with four panels: server logs (scrollable), per-GPU VRAM/utilization/power/temp monitoring, system stats (CPU/RAM/swap/container), and keyboard controls (`q` stop & exit, `r` stop & return to menu). Docker healthcheck is also configured for container-level health awareness. Use `--no-dashboard` for raw log output.

## Done

### Formal benchmarks (EvalPlus HumanEval+)
- EvalPlus benchmark runner in `benchmarks/evalplus/` — runs HumanEval+ (164 Python problems) against all models via the llama.cpp OpenAI API
- 6 benchmark profiles in `models.conf` (bench-*) with reduced 16K context
- Code generation on host, evaluation in Docker sandbox (`ganler/evalplus`) for safety
- Comparison report with published scores for proprietary models (Claude, GPT, DeepSeek, Codestral, etc.)
- Claude Opus 4.6 benchmark via custom Claude Code agent (Max subscription) — solves problems from prompts only, no code execution or internet. Agents in `.claude/agents/humaneval-solver*.md`, evaluation via `benchmarks/evalplus/evaluate-claude.sh`
- Production sampler settings updated per official model card recommendations
- See `benchmarks/evalplus/README.md` for setup and usage

## Next Up

### Temperature/sampling parameter sweeps
- Test temperature 0.6 / 0.8 / 1.0 for agentic coding tasks
- Find the optimal sampling configuration for deterministic code generation vs. creative tasks
- Document impact on self-correction behavior

### VRAM optimization experiments
- Test different KV cache types (q5_0 as middle ground between q8_0 and q4_0)
- Experiment with batch sizes (-b/-ub) for prompt processing speed vs. VRAM trade-off
- Test `--no-op-offload` for potential token generation speed improvement

## Future

### API integration
- Configure Claude Code to use the local llama-server as an alternative backend
- Test integration with Continue.dev, aider, and other coding assistants
- Set up OpenAI-compatible client configurations for various tools
- Define use cases: when local inference is worthwhile vs. cloud API

### Multi-model hot-swap
- Test `--model-store` for hot-swapping models without restarting the server (when available in llama.cpp)
- Evaluate memory management for keeping multiple models partially loaded

### Advanced GPU utilization
- Explore row split mode (`-sm row`) for asymmetric GPU workloads
- Test with future llama.cpp DeltaNet kernel optimizations
- Benchmark impact of `-t` thread count on CPU expert processing

### Extended benchmarks
- Add MBPP+ (378 problems) to the existing EvalPlus benchmark runner
- LiveCodeBench support (pending upstream OpenAI API integration)
- Automated VRAM utilization tracking during benchmarks
- Regression testing when updating llama.cpp

## Considered & Deferred

### DGX Spark
Evaluated for GPT-OSS 120B: ~2x speed improvement (38-41 t/s vs ~20 t/s) driven by 273 GB/s unified memory bandwidth. Not justified at $3,000-4,000 given the desktop's adequate performance for interactive use. See `archive/dgx-spark-benchmarks.md` for detailed comparison.
