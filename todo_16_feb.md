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

### Production profile optimization
- [ ] Analyze benchmark results, choose models
- [ ] Optimize production profiles with gpu-optimizer agent (GLM Q4, GLM Q8, Qwen3 Q5, Qwen3 Q6, Qwen3 Q6K)
- [ ] GPT-OSS 120B production profile already optimized — skip
- [ ] Test and document

### Plans archived
- [x] Archived `PLAN_fair_postprocessing_benchmark.md` → `archive/` (done 15 feb)
- [x] Archived `PLAN_separation_of_concerns.md` → `archive/` (done 15 feb)

## Session 2: New model (separate session after Session 1)

- [ ] Add new model — create normal and bench profiles
- [ ] Test the new model
- [ ] Benchmark the new model
- [ ] Add results to REPORT.md
