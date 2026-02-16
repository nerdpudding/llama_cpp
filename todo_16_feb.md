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

### Use cases, menu improvements, UD-Q6 removal — DONE (16 feb)
- [x] Removed UD-Q6 (production + bench profiles) — UD-Q5 is faster and higher scoring
- [x] Added DESCRIPTION/SPEED fields to all production profiles in models.conf
- [x] Rewrote start.sh menu with descriptions, speeds, and bench submenu
- [x] Added capability + sampler quick-reference tables to client-settings.md
- [x] Added GPT-OSS reasoning level documentation (low/medium/high trade-offs)
- [x] Fixed GPT-OSS context from 64K to 128K in docs
- [x] Updated all cross-references (README, ROADMAP, AI_INSTRUCTIONS, evalplus, agents)
- [x] Archived plan → `archive/2026-02-16_model_usecases_menu_improvements.md`

## Session 2: Add new model (separate session)

Plan: `claude_plans/PLAN_add_model_flow.md`

### Step 1: Set up "add model" workflow
- [ ] Update model-manager agent with evaluation workflow
- [ ] Update gpu-optimizer agent with "untested profile" convention
- [ ] Update benchmark agent with current pipeline file checklist
- [ ] Update todo with Session 2 completion

### Step 2: Test the workflow with a candidate (user picks which one)
- [ ] Evaluate candidate model card
- [ ] Download model and organize files
- [ ] Create production profile (gpu-optimizer)
- [ ] Find and document sampler settings
- [ ] Test and optimize (user runs, shares logs)
- [ ] Create bench profile (optional)
- [ ] Run benchmark (optional)
- [ ] Update all documentation (doc-keeper)
