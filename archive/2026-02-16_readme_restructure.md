# Plan: README.md Restructure

## Context

The README has grown organically and has some issues: duplicate model tables (Target Models + Switching Models), no quick-reference section, no benchmark results, no mention of the /add-model workflow or AI-assisted development practices. The user wants it to be the go-to reference for both using the project and understanding how to extend it.

## Current problems

1. **Duplicate model tables** — "Target Models" and "Switching Models" show the same data differently
2. **No quick-reference** — common operations (build, start, bench) are scattered
3. **No benchmark results** — the REPORT.md data is hidden in a subfolder
4. **No /add-model mention** — the onboarding workflow is undiscoverable
5. **No AI workflow section** — agents, skills, and development practices are undocumented
6. **DGX Spark research** — not mentioned anywhere
7. **ROADMAP** — only a link at the bottom, could be more prominent
8. **"Why Not Ollama?"** — takes up prime real estate near the top

## New structure

```
# llama.cpp Docker Wrapper for Dual-GPU Desktop

Intro paragraph (keep current, it's good)

## Table of Contents

## Hardware
(keep as-is, compact table)

## Quick Start
  ### Build & install
  (merge Prerequisites + Installation + Build into one concise section)
  ### Run a model
  (start.sh usage, dashboard controls, API endpoint — all in one place)

## Models
  (ONE table: section ID, model name, speed, context, best for)
  ### Sampler settings
  (compact table from client-settings.md, link to full doc)
  ### Model-specific notes
  (GPT-OSS reasoning levels — keep compact)

## Benchmarks (EvalPlus HumanEval+)
  (embed the Local Results table from REPORT.md)
  (caveat: coding-focused benchmark, 164 Python problems)
  ### Running benchmarks
  (the quick commands)
  → Full setup: benchmarks/evalplus/README.md

## Adding New Models
  (what /add-model does, 8 phases summary, what to expect)
  (candidate models list — move from ROADMAP to here)

## Configuration
  Key files table: models.conf, docker-compose.yml, bench-client.conf
  → Links to detailed docs

## AI-Assisted Development
  (compact section about working with Claude Code on this project)
  - AI_INSTRUCTIONS.md — project context for AI tools
  - Agents: gpu-optimizer, benchmark, model-manager, doc-keeper, etc.
  - Skills: /add-model
  - Workflow: plan → approve → implement → test → document → commit
  - claude_plans/ for plan files

## Roadmap & Research
  Brief current status (link to ROADMAP.md)
  DGX Spark comparison mention (link to docs/dgx-spark-comparison.md)

## Documentation
  (links to all detailed docs — keep as reference section)

## Repository Structure
  (move to end — it's reference material, not discovery)

## Why Custom llama.cpp?
  (rename "Why Not Ollama?" — more positive framing, move to end)
  (shorter version — the detailed reasons are less important than usage)

## Updating llama.cpp
  (keep at end, it's maintenance)
```

## Key decisions

1. **One model table, not two.** The "Switching Models" table is the more useful one (has section IDs). Remove "Target Models" table, keep only the one with section IDs.

2. **Benchmark results embedded.** Copy the "Local Results" table from REPORT.md directly into README. Add caveat that this is a coding benchmark (HumanEval+ = 164 Python problems). Keep it current by noting the date.

3. **"Why Not Ollama?" → "Why Custom llama.cpp?"** More positive framing. Move to bottom — returning users don't need to see this every time. New users scroll past the useful stuff first.

4. **Sampler settings inline.** The compact table from client-settings.md belongs in the README quick reference. Full details still in docs/client-settings.md.

5. **AI workflow section.** Short and practical: what files matter, what the workflow looks like, how agents help. Not a tutorial — a quick orientation.

6. **Candidates in "Adding New Models"** not in ROADMAP. They're actionable (use /add-model), not future plans.

## Files to modify

- `README.md` — full restructure
- `ROADMAP.md` — remove Candidate Models section (moved to README), update "Streamlined model onboarding" to note it's done

## Verification

- Read the final README top-to-bottom as a new user: can you build, run, and understand the project?
- Read it as a returning user: can you quickly find model IDs, sampler settings, benchmark results?
- Check all internal links still work
- Run doc-keeper after to verify cross-references
