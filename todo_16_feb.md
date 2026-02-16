# TODO 16 February

## Session 1: Documentation consolidation & cleanup

Plan: `claude_plans/first_assignment_16_feb.md`

### Task 1: Update AI_INSTRUCTIONS.md hierarchy
- [x] Remove deleted files from hierarchy (gpt-oss config guide, env-templates/)
- [x] Add missing files (dgx-spark-comparison.md, REPORT.md)
- [x] Update after docs/ changes from Task 4

### Task 2: Read REPORT.md (reference only)
- [x] Read and noted — REPORT.md is the authoritative benchmark data

### Task 3: Update PLAN_bench_gpu_optimization.md
- [x] Mark all completed bench profile work as DONE
- [x] Clearly note remaining TODO: production profile optimization for GLM + Qwen3 models
- [x] Note GPT-OSS 120B production profile is already optimized (exception)

### Task 4: Organize docs/
- [x] 4a: bench-test-results.md — KEEP (complements REPORT.md, different data)
- [x] 4b: dgx_testing.md — RENAMED to dgx-spark-comparison.md
- [x] 4c: gpu-strategy-guide.md — reviewed, no errors found
- [x] 4d: lessons_learned.md — reviewed, fine as-is
- [x] 4e: llama-cpp-flags-and-qwen3-strategy.md — ARCHIVED to archive/

### Task 5: Update README.md and ROADMAP.md
- [x] Fix repository structure (remove deleted files, add new/renamed files)
- [x] Update Documentation section with current file references
- [x] Add benchmark results reference to REPORT.md
- [x] Update ROADMAP.md status and move completed items

## Carried over from 15 Feb

### Production profile optimization — DONE (16 feb)
- [x] Analyzed benchmark results, chose UD-Q5 over UD-Q6 (faster + higher score)
- [x] Optimized all production profiles with gpu-optimizer agent + manual testing
- [x] GPT-OSS 120B also optimized (-ub 512 freed room for +1 layer)
- [x] Tested and documented all results in advice_test_plan.md
- [x] Key discovery: -ub 512 saves 449-2000 MiB compute buffer vs -ub 1024/2048
- Results: GLM Q4 142.7 t/s, GLM Q8 103.8 t/s, GPT-OSS 20.7 t/s, Qwen3 Q5 27.9 t/s

### Plans archived
- [x] Archived `PLAN_fair_postprocessing_benchmark.md` → `archive/` (done 15 feb)
- [x] Archived `PLAN_separation_of_concerns.md` → `archive/` (done 15 feb)
- [x] Archived `PLAN_bench_gpu_optimization.md` → `archive/` (done 16 feb)
- [x] Archived `advice_test_plan.md` → `archive/` (done 16 feb)

## Session 2: New model (separate session after Session 1)

- [ ] Add new model — create normal and bench profiles
- [ ] Test the new model
- [ ] Benchmark the new model
- [ ] Add results to REPORT.md
