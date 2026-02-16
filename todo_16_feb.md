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

Plan: `archive/2026-02-16_add_model_flow.md` (completed)

### Step 1: Set up "add model" workflow
- [x] Create `/add-model` skill (`.claude/skills/add-model/SKILL.md`)
- [x] Update model-manager agent with candidate evaluation workflow
- [x] Update gpu-optimizer agent with untested profile + bench profile conventions
- [x] Update benchmark agent with new bench profile file checklist

### Step 2: Test workflow with Qwen3-Next-80B-A3B — DONE (16 feb)
- [x] Evaluate candidate model card (Phase 1)
- [x] Download model and organize files (Phase 2)
- [x] Create production profile — gpu-optimizer, tested 28 t/s (Phase 3)
- [x] Find and document sampler settings — temp 0.7, top_p 0.8, top_k 20 (Phase 4)
- [x] Test and optimize — CUDA0 94%, CUDA1 88%, 130 graph splits (Phase 5)
- [x] Create bench profile — bench-qwen3-next-ud-q5, 19+9=28/48 split (Phase 6)
- [ ] Run benchmark — bench profile ready, not yet executed (Phase 7)
- [x] Update all documentation — doc-keeper audit passed (Phase 8)
- [x] Renamed qwen3-coder-q5 → qwen3-coder-ud-q5 for naming consistency
