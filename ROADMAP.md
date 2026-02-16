# Roadmap

## Current Status

Five models are configured in `models.conf` and selectable via `./start.sh` on a dual-GPU desktop (RTX 4090 + RTX 5070 Ti):

- **GLM-4.7 Flash Q4_K_M** — ~140 t/s, 128K context, single GPU (Strategy A)
- **GLM-4.7 Flash Q8_0** — ~105 t/s, 128K context, dual GPU split (Strategy C)
- **GPT-OSS 120B F16** — ~21 t/s, 64K context, large MoE with CPU expert offloading (Strategy D)
- **Qwen3-Coder-Next UD-Q5_K_XL** — ~28 t/s, 256K context, coding speed option
- **Qwen3-Coder-Next UD-Q6_K_XL** — ~24 t/s, 256K context, coding baseline

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
- Plan: `claude_plans/PLAN_bench_gpu_optimization.md`

### Production profile optimization (2026-02-16)
- All production profiles optimized with explicit GPU layer placement and `-b 2048 -ub 512`
- Key discovery: `-ub` (micro-batch) determines compute buffer VRAM — switching to `-ub 512` freed 449-2000 MiB per GPU
- GLM Q4: Strategy A (single GPU), 142.66 t/s
- GLM Q8: Strategy C (33+14=47/47), 103.79 t/s
- GPT-OSS 120B: Strategy D (11+4=15/36), 20.72 t/s
- Qwen3 UD-Q5: Strategy D (17+8=25/48), 27.89 t/s (+8% from 25.8)
- Documented in `docs/gpu-strategy-guide.md` and `docs/lessons_learned.md`
- Plan: `claude_plans/PLAN_bench_gpu_optimization.md`

## Next Up

### Temperature/sampling parameter sweeps
- Test temperature 0.6 / 0.8 / 1.0 for agentic coding tasks
- Find the optimal sampling configuration for deterministic code generation vs. creative tasks
- Document impact on self-correction behavior

### VRAM optimization experiments
- Test different KV cache types (q5_0 as middle ground between q8_0 and q4_0)
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

## Candidate Models

Five models are being evaluated for potential addition to the project. Model cards are in `models/documentation/CANDIDATES/`.

- **Qwen3-Next-80B-A3B-Instruct** — 80B total / 3B active MoE with hybrid Gated DeltaNet + Gated Attention, ultra-long context (256K native, extensible to 1M), strong general reasoning and coding
- **Nemotron-3-Nano-30B-A3B** — 30B total / 3.5B active hybrid Mamba2-Transformer MoE, reasoning with tool calling, excels at math/coding/agentic tasks (SWE-bench 38.8%)
- **Devstral-Small-2-24B-Instruct** — 24B dense model specialized for agentic coding and software engineering (SWE-bench 68.0%, Terminal Bench 22.5%), supports vision
- **Ministral-3-14B-Instruct** — 14B (13.5B LM + 0.4B vision encoder), general-purpose instruct with vision, multilingual, edge-optimized
- **Ministral-3-14B-Reasoning** — Same architecture as 14B Instruct but post-trained for reasoning with `<think>` blocks, strong at math/STEM (AIME25 85.0%)

## Considered & Deferred

### DGX Spark
Evaluated for GPT-OSS 120B: ~2x speed improvement (38-41 t/s vs ~20 t/s) driven by 273 GB/s unified memory bandwidth. Not justified at $3,000-4,000 given the desktop's adequate performance for interactive use. See `archive/dgx-spark-benchmarks.md` for detailed comparison.
