# Plan: Model use cases, client-settings table, and menu improvements

**Status: COMPLETED (2026-02-16)**

## Context

After optimizing all production profiles, the user wants better model selection guidance. Currently, choosing the right model requires reading multiple docs. The goal: surface use-case info everywhere decisions are made — client-settings doc, README, and start.sh menu. Bench profiles also clutter the interactive menu and should be in a submenu.

Additionally, Qwen3 UD-Q6 is being removed entirely (UD-Q5 is faster AND scores higher). User will delete the GGUF files manually.

## Verified facts

- **repeat_penalty** defaults to 1.0 (disabled) in llama.cpp (`common/common.h:196`). No need to set explicitly.
- **GLM-4.7-Flash** has two sampler profiles: General chat (temp 1.0, top_p 0.95) and Tool-calling/Coding (temp 0.7, top_p 1.0). Source: model card.
- **GPT-OSS 120B** and **Qwen3-Coder-Next** each have a single sampler profile for all use cases.

## Changes

### 1. models.conf — Remove UD-Q6, add DESCRIPTION/SPEED fields

**Remove these sections:**
- `[qwen3-coder]` (line 135) — UD-Q6 production profile
- `[bench-qwen3-coder-ud-q6]` (line 272) — UD-Q6 bench profile

**Add fields to production profiles** (parsed by existing INI parser, no code change needed):

| Section | DESCRIPTION | SPEED |
|---------|-------------|-------|
| `glm-flash-q4` | Fast general tasks, reasoning, tool calling | ~140 t/s |
| `glm-flash-q8` | Higher quality reasoning and tool calling | ~105 t/s |
| `glm-flash-exp` | Experimental Q8 (same as glm-flash-q8) | ~105 t/s |
| `gpt-oss-120b` | Deep reasoning, knowledge, structured output | ~21 t/s |
| `qwen3-coder-q5` | Coding agents, agentic tasks | ~28 t/s |

Bench profiles: no DESCRIPTION or SPEED (not shown in main menu).

### 2. start.sh — Menu with descriptions and bench submenu

Rewrite `show_menu()` to separate production from bench profiles and display richer info:

```
llama.cpp Model Selector
========================

  1) GLM-4.7 Flash Q4_K_M                            ~140 t/s  128K ctx
     Fast general tasks, reasoning, tool calling

  2) GLM-4.7 Flash Q8_0                              ~105 t/s  128K ctx
     Higher quality reasoning and tool calling

  3) GLM-4.7 Flash Q8_0 (experimental)               ~105 t/s  128K ctx

  4) GPT-OSS 120B F16                                  ~21 t/s   64K ctx
     Deep reasoning, knowledge, structured output

  5) Qwen3-Coder-Next UD-Q5_K_XL                      ~28 t/s  256K ctx
     Coding agents, agentic tasks

  b) Benchmarks >
  q) Quit

Select model [1-5, b, q]:
```

Pressing `b` shows:

```
Benchmark Profiles (10K context, optimized GPU layers)
======================================================

  1) GLM-4.7 Flash Q4_K_M (benchmark)                          10K ctx
  2) GLM-4.7 Flash Q8_0 (benchmark)                            10K ctx
  3) GPT-OSS 120B (benchmark)                                  10K ctx
  4) Qwen3-Coder-Next UD-Q5 (benchmark)                        10K ctx

  r) Return to main menu
  q) Quit

Select benchmark [1-4, r, q]:
```

Implementation in start.sh:
- In `show_menu()`, split `SECTION_IDS` into `prod_ids` and `bench_ids` based on `bench-` prefix
- Display prod models with speed + context + description (if set)
- Add `b)` option; when chosen, call new `show_bench_menu()` function
- `show_bench_menu()` displays bench-only list, `r)` returns to main menu
- `list_models` (`--list`) also groups production/benchmark separately

### 3. client-settings.md — Quick reference tables at top

Add two tables right after the title, before the per-model sections:

**Table A: Model capabilities**

| Model | Best for | Thinking | Tool calling | Speed |
|-------|----------|----------|-------------|-------|
| GLM-4.7 Flash | General tasks, reasoning, tool calling | Yes (`<think>` blocks) | Yes (native) | 105-140 t/s |
| GPT-OSS 120B | Deep reasoning, knowledge, structured output | Yes (configurable low/med/high) | Yes (native) | ~21 t/s |
| Qwen3-Coder-Next | Coding agents, agentic tasks | No | Yes (native) | ~28 t/s |

**Table B: Sampler settings**

| Setting | GLM (general) | GLM (coding/tools) | GPT-OSS (all) | Qwen3-Coder (all) |
|---------|--------------|-------------------|---------------|-------------------|
| temperature | 1.0 | 0.7 | 1.0 | 1.0 |
| top_p | 0.95 | 1.0 | 1.0 | 0.95 |
| top_k | — | — | 0 (disabled) | 40 |
| min_p | 0.01 | 0.01 | — | 0.01 |
| system prompt | — | — | "Reasoning: low/med/high" | — |

Remove the existing "Quick comparison" table at the bottom (same data, now at top). Also remove UD-Q6 references from per-model sections and the name "(speed)" from Qwen3 section (it's now the only Qwen3 variant).

### 4. README.md — Update model tables

**Target Models table** — Remove UD-Q6, update Use Case column:

| Model | File Size | Speed | Context | Use Case |
|-------|-----------|-------|---------|----------|
| GLM-4.7 Flash Q4_K_M | 18 GB | ~140 t/s | 128K | Fast general tasks, reasoning, tool calling |
| GLM-4.7 Flash Q8_0 | 30 GB | ~105 t/s | 128K | Higher quality reasoning and tool calling |
| GPT-OSS 120B F16 | 61 GB | ~21 t/s | 64K | Deep reasoning, knowledge, structured output |
| Qwen3-Coder-Next UD-Q5_K_XL | 57 GB | ~28 t/s | 256K | Coding agents, agentic tasks |

**Switching Models table** — Remove `qwen3-coder` and `qwen3-coder-q6k`, add Best for column, rename Q5 from "(speed)" to just the name:

| Section ID | Model | Speed | Context | Best for |
|------------|-------|-------|---------|----------|
| `glm-flash-q4` | GLM-4.7 Flash Q4_K_M | ~140 t/s | 128K | Fast tasks, reasoning |
| `glm-flash-q8` | GLM-4.7 Flash Q8_0 | ~105 t/s | 128K | Quality reasoning, tools |
| `glm-flash-exp` | GLM-4.7 Flash Q8_0 (experimental) | ~105 t/s | 128K | Experimental |
| `gpt-oss-120b` | GPT-OSS 120B F16 | ~21 t/s | 64K | Deep reasoning, knowledge |
| `qwen3-coder-q5` | Qwen3-Coder-Next UD-Q5_K_XL | ~28 t/s | 256K | Coding agents |

### 5. Cleanup references

Remove UD-Q6 mentions from:
- `ROADMAP.md` (Current Status section lists UD-Q6)
- `benchmarks/evalplus/bench-client.conf` (if it has a UD-Q6 section — check)
- `benchmarks/evalplus/benchmark.sh` (if it references UD-Q6 profiles — check)

## Files to modify

1. `models.conf` — Remove 2 sections, add DESCRIPTION/SPEED to 5 sections
2. `start.sh` — Rewrite `show_menu()`, add `show_bench_menu()`, update `list_models()`
3. `docs/client-settings.md` — Add quick reference tables at top, remove bottom table
4. `README.md` — Update 2 tables, remove UD-Q6 rows
5. `ROADMAP.md` — Remove UD-Q6 from current status
6. Possibly: `benchmarks/evalplus/bench-client.conf`, `benchmarks/evalplus/benchmark.sh`

## Verification

1. `./start.sh` — Menu shows descriptions, speeds, no UD-Q6, bench submenu works
2. `./start.sh --list` — Shows grouped listing
3. `./start.sh glm-flash-q4` — Direct launch still works
4. `./start.sh qwen3-coder` — Should fail gracefully (section removed)
5. Press `b` in menu → bench submenu → `r` returns → select prod model → launches OK
6. doc-keeper agent verifies cross-references
