# Roadmap

## Current Status

Three models are configured and tested with Docker on a dual-GPU desktop (RTX 4090 + RTX 5070 Ti):

- **Qwen3-Coder-Next UD-Q6_K_XL** — 21.4 t/s, 256K context, baseline for coding tasks
- **Qwen3-Coder-Next UD-Q5_K_XL** — 25.8 t/s, 256K context, speed alternative
- **GPT-OSS 120B** — ~20 t/s, 64K context, large MoE with CPU expert offloading
- **GLM-4.7 Flash Q8_0** — fits entirely in VRAM, 128K context

All models use optimized `-ot` regex configurations for per-layer GPU/CPU tensor placement. Tested configurations are documented in `docs/` with memory breakdowns, VRAM utilization, and performance data.

## Next Up

### Formal benchmarks
- Run LiveCodeBench, HumanEval, or similar coding-specific benchmarks across all configured models
- Compare against proprietary models (Opus 4.6, GPT-5.3 Codex) to understand which tasks are suitable for local inference
- Document results as a score reference for future model upgrades

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

### Automated benchmark suite
- Scripted tests with result logging
- Automated VRAM utilization tracking
- Regression testing when updating llama.cpp

## Considered & Deferred

### DGX Spark
Evaluated for GPT-OSS 120B: ~2x speed improvement (38-41 t/s vs ~20 t/s) driven by 273 GB/s unified memory bandwidth. Not justified at $3,000-4,000 given the desktop's adequate performance for interactive use. See `archive/dgx-spark-benchmarks.md` for detailed comparison.
