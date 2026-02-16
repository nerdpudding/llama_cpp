# Plan: Documentation Consolidation & Cleanup — 16 Feb 2026

## Overview

Consolidate, organize, and update project documentation after yesterday's benchmarking work. Five tasks in sequence, each building on findings from the previous.

## Findings from initial read-through

### Files deleted since last AI_INSTRUCTIONS.md update
- `docs/gpt-oss-120b-configuration-guide.md` — deleted (git status confirms)
- `archive/env-templates/` — entire directory deleted (git status confirms)
- `todo_15_feb.md` — moved to `archive/todo_15_feb.md`

### Files present but not in any hierarchy
- `docs/dgx_testing.md` — DGX Spark comparison article (WIP)
- `benchmarks/evalplus/results/REPORT.md` — authoritative benchmark results

### Hierarchy errors in AI_INSTRUCTIONS.md
- Lists `docs/gpt-oss-120b-configuration-guide.md` — file no longer exists
- Lists `archive/env-templates/` — directory no longer exists
- Missing `docs/dgx_testing.md` (or its renamed version)
- Missing `benchmarks/evalplus/results/REPORT.md`

### README.md issues
- Lists `docs/gpt-oss-120b-configuration-guide.md` in repository structure and Documentation section — doesn't exist
- Missing `gpu-optimizer.md` from `.claude/agents/` listing
- Documentation section at bottom references deleted files
- Benchmark section could reference REPORT.md results
- Will need updating after docs/ changes (Task 4)

### ROADMAP.md issues
- References `docs/bench-test-results.md` — may need path update if renamed
- "Next Up" section has items that may be done or deprioritized after benchmarks
- EvalPlus results section in "Done" could reference actual scores from REPORT.md
- DGX Spark section references `archive/dgx-spark-benchmarks.md` — exists, correct

---

## Task 1: Update AI_INSTRUCTIONS.md hierarchy

**Scope:** ONLY the project hierarchy tree (lines ~30-85). No other changes.

**Changes needed:**
- Remove `docs/gpt-oss-120b-configuration-guide.md` (deleted)
- Remove `archive/env-templates/` (deleted)
- Rename `docs/dgx_testing.md` → `docs/dgx-spark-comparison.md` (rename the actual file too, matching the document title "DGX Spark: When Is It Worth It?")
- Add `benchmarks/evalplus/results/REPORT.md` to hierarchy
- After Task 4 decisions: update any docs/ entries that changed (archiving, renaming)

---

## Task 2: Read REPORT.md (reference only)

**Scope:** Already read. No changes needed. Key data points to keep in mind:

| Model | HumanEval | HumanEval+ |
|-------|-----------|------------|
| Claude Opus 4.6 | 98.2% | 95.1% |
| Claude Opus 4.6 (thinking) | 99.4% | 93.9% |
| Qwen3-Coder-Next UD-Q5_K_XL | 93.9% | 90.9% |
| Qwen3-Coder-Next UD-Q6_K_XL | 92.1% | 89.0% |
| GLM-4.7 Flash Q8_0 | 89.0% | 87.2% |
| GPT-OSS 120B F16 | 93.3% | 87.2% |
| GLM-4.7 Flash Q4_K_M | 87.8% | 83.5% |

These are the authoritative numbers. Any discrepancy in other docs should be corrected to match.

---

## Task 3: Update PLAN_bench_gpu_optimization.md

**Scope:** Update status markers to reflect reality.

**Already DONE (mark as complete):**
- All bench profile changes in models.conf
- All OOM testing (all 6 bench profiles)
- Adding bench profiles to start.sh menu
- Full benchmark run with optimized profiles (REPORT.md has the results)
- Speed comparison and documentation

**Still TODO (mark clearly):**
- Production profile optimization for:
  - GLM-4.7 Flash Q4_K_M
  - GLM-4.7 Flash Q8_0
  - Qwen3-Coder-Next UD-Q5_K_XL
  - Qwen3-Coder-Next UD-Q6_K_XL
  - Qwen3-Coder-Next Q6_K
- GPT-OSS 120B production profile is ALREADY optimized (exception)

**Note:** Production profile optimization is also on todo_16_feb.md already.

---

## Task 4: Organize docs/

### 4a. `bench-test-results.md` — KEEP, it serves a different purpose than REPORT.md

- REPORT.md = EvalPlus HumanEval+ pass@1 scores (code quality)
- bench-test-results.md = GPU optimization data (VRAM usage, t/s speeds, OOM failures, layer split decisions)
- These are complementary, not redundant
- Data in bench-test-results.md is current and matches final bench profiles
- Used by gpu-optimizer agent as reference
- **Action:** Keep as-is. No changes needed.

### 4b. `dgx_testing.md` — RENAME only (do not modify content)

- Current title: "DGX Spark: When Is It Worth It?"
- Contains accurate, detailed hardware comparison article (WIP)
- **Action:** Rename to `dgx-spark-comparison.md` to match content better
- Update references in AI_INSTRUCTIONS.md hierarchy

### 4c. `gpu-strategy-guide.md` — No errors found

- Model table data matches actual file sizes and architectures
- Strategy descriptions are accurate
- Graph split data matches bench-test-results.md
- **Action:** No changes needed.

### 4d. `lessons_learned.md` — Fine as-is

- 4 entries, all still relevant
- May add to later, but no changes now
- **Action:** No changes needed.

### 4e. `llama-cpp-flags-and-qwen3-strategy.md` — ARCHIVE

- Early exploration document (pre-benchmark, pre-optimized profiles)
- Most actionable content has been incorporated into:
  - `gpu-strategy-guide.md` (strategies, decision tree)
  - `bench-test-results.md` (actual measured performance)
  - `lessons_learned.md` (mistakes)
  - `models.conf` comments (configuration reasoning)
- Remaining unique data (VRAM budget breakdown at 256K, KV cache analysis) is useful reference but not actionable — the decisions have been made
- The "Next Steps" section references tasks that are now done (benchmarks, API integration planning)
- **Action:** Move to `archive/2026-02-16_llama-cpp-flags-and-qwen3-strategy.md`
- Update references in AI_INSTRUCTIONS.md, README.md

---

## Task 5: Update README.md and ROADMAP.md

### README.md changes needed:
- Remove `docs/gpt-oss-120b-configuration-guide.md` from repository structure
- Add `docs/dgx-spark-comparison.md` to repository structure
- Remove `docs/llama-cpp-flags-and-qwen3-strategy.md` (archived)
- Add `gpu-optimizer.md` to `.claude/agents/` listing
- Update Documentation section at bottom (remove deleted/archived file refs, add REPORT.md)
- Add latest benchmark scores summary to Benchmarks section or reference REPORT.md
- Add `benchmarks/evalplus/results/REPORT.md` to structure

### ROADMAP.md changes needed:
- Update "Current Status" speed numbers if any differ from bench-test-results.md
- Move completed items from "Next Up" to "Done" if applicable (bench profile optimization is done)
- Add note about EvalPlus results with scores or reference to REPORT.md
- Verify all document references are still valid
- Note that production profile optimization for non-GPT-OSS models is still planned

---

## Execution order

1. Task 4e first (archive the file, so hierarchy changes are final)
2. Task 4b (rename dgx_testing.md)
3. Task 1 (update AI_INSTRUCTIONS.md hierarchy — now all file moves are done)
4. Task 3 (update PLAN_bench_gpu_optimization.md)
5. Task 5 (update README.md and ROADMAP.md — last, since they reference everything else)

Tasks 2, 4a, 4c, 4d are read-only (already done during planning).
