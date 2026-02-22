# TODO 22 February

## Completed

### Check llama.cpp for upstream updates
- [x] Check current local llama.cpp version/commit — `b48e80f67` (b8022, 13 Feb)
- [x] Check latest upstream commits — 93 new commits to `ed4837891`
- [x] Review what changed — relevant: qwen3next graph opt, CUDA graph improvements, GPT-OSS Jinja fix
- [x] Updated, rebuilt, tested — CUDA illegal memory access regression on qwen3next models with `-ot` multi-GPU splits
- [x] Reverted to `b48e80f67`, rebuilt, tested — works correctly
- [x] Filed upstream issue: https://github.com/ggml-org/llama.cpp/issues/19816
- [x] Bench profile `bench-qwen3-next-ud-q5` verified working on reverted build (~29.5 t/s)

## In progress

### Run Qwen3-Next benchmark
- [x] Run EvalPlus HumanEval+ benchmark for `bench-qwen3-next-ud-q5`
- [x] Review results — 98.2% HumanEval, 93.9% HumanEval+ (surprisingly high for a general model)
- [x] Merge into `benchmarks/evalplus/results/REPORT.md` (automatic via generate-report.py)
- [x] Update README.md benchmark table with Qwen3-Next scores

### Roadmap items (decide later)
- [ ] Pick roadmap items to work on after benchmark is done

## Blocked

### llama.cpp upstream update
- **DO NOT UPDATE** until https://github.com/ggml-org/llama.cpp/issues/19816 is resolved
- Full details and workaround: `docs/known_issue_llama_cpp_cuda_graphs_2026-02-22.md`
