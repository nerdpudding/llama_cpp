# Plan: Streamlined "Add New Model" workflow

## Context

The project has four production models with optimized GPU profiles, benchmarks, and comprehensive docs. Five candidate models are already in `models/documentation/CANDIDATES/`. Currently, adding a new model requires manual coordination across many files. This plan creates a clear, repeatable workflow that the user and AI agents can follow together to quickly integrate any new GGUF model.

## The workflow (what we're documenting/setting up)

### Prerequisites (user does this manually)

1. **Find model on HuggingFace** — must be GGUF (for GPU/CPU offloading). Unsloth quants preferred for MoE (better router precision) but not required.
2. **Download model card** — save the HuggingFace README as `README_<modelname>.md` in `models/documentation/CANDIDATES/`.
3. **Start a new Claude Code session** and ask: "I want to evaluate candidate model X for integration."

### Phase 1: Evaluate (AI + user, uses model-manager agent)

AI reads the candidate model card and investigates:
- What kind of model? (Dense vs MoE, params, layers, experts, architecture)
- What quantized options exist on HuggingFace? How large are they?
- What are the model's specialties/use cases?
- Does it fit on the hardware? (RTX 4090 24GB + RTX 5070 Ti 16GB + 64GB RAM)
- Which quant is the best fit? (balance quality vs VRAM vs speed)

**AI must ask the user:**
- Which quant to use (after presenting options with sizes and trade-offs)
- Or the user can simply tell the AI which quant they've already decided on

### Phase 2: Download & organize (user does download, AI guides)

AI tells the user:
- Exact download command (`huggingface-cli download ...`)
- Where to place files: `models/<ModelName>/<QuantName>/` following existing hierarchy
- For multi-part GGUF: all parts must be in the same directory

User downloads and confirms files are in place.

### Phase 3: Create production profile (AI, uses gpu-optimizer agent)

The gpu-optimizer agent:
1. Reads the model card from `models/documentation/`
2. Reads `docs/gpu-strategy-guide.md` for strategy decision tree
3. Reads `docs/lessons_learned.md` for known pitfalls
4. Studies existing optimized profiles in `models.conf` as reference
5. Calculates VRAM budget (model weights + KV cache at target context + compute buffers)
6. Selects strategy (A/B/C/D) and generates `-ot` regex
7. Adds production profile to `models.conf` with:
   - NAME, DESCRIPTION, SPEED (estimated, marked as "~estimated")
   - MODEL path, CTX_SIZE, N_GPU_LAYERS, FIT=off
   - EXTRA_ARGS with sampler settings from model card
   - Comments: architecture source, strategy rationale, "NOT YET TESTED"

### Phase 4: Find sampler settings (AI)

AI researches recommended sampler settings:
- Check model card for official recommendations
- Check Unsloth docs if applicable
- Determine: temperature, top_p, top_k, min_p, repeat_penalty
- Determine: any special system prompt requirements (like GPT-OSS reasoning levels)
- Set these in EXTRA_ARGS in the production profile
- Add a new section to `docs/client-settings.md` with the settings + explanation

### Phase 5: Test (user + AI)

1. User runs `./start.sh <new-profile-id>` to test
2. User shares the server startup log with AI
3. AI (or gpu-optimizer agent) analyzes:
   - Did it load successfully? Any OOM?
   - VRAM usage per GPU — room for optimization?
   - Actual speed (t/s) — update SPEED field
   - Graph splits — acceptable?
4. Iterate if needed: adjust layer split, batch sizes, etc.
5. Remove "NOT YET TESTED" comment, add actual measured values

### Phase 6: Create bench profile (optional, AI uses gpu-optimizer + benchmark agents)

If benchmarking is desired:

**gpu-optimizer** creates a bench profile in `models.conf`:
- Section ID: `[bench-<model-id>]`
- CTX_SIZE=10240 (HumanEval worst case ~8.4K)
- -b 512 -ub 512 (small prompts)
- More GPU layers than production (less KV cache = more room for weights)
- `--reasoning-format none` if it's a thinking model (so chain-of-thought goes into content field for evalplus)
- No sampler args (evalplus sends temperature=0)

**Update benchmark pipeline files:**
- `benchmarks/evalplus/bench-client.conf` — add section if model needs a system prompt
- `benchmarks/evalplus/generate-report.py` — add to `DISPLAY_NAMES` dict and `REFERENCE_MAP` dict (if official scores exist in `reference-scores.json`)
- `benchmarks/evalplus/README.md` — add to profiles table

Note: `benchmark.sh` auto-discovers `bench-*` profiles from `models.conf` — no code changes needed there.

### Phase 7: Run benchmark (optional, user + benchmark agent)

```bash
cd benchmarks/evalplus
source .venv/bin/activate
./benchmark.sh bench-<model-id>
```

Results auto-generated in `results/REPORT.md`.

### Phase 8: Update documentation (AI, uses doc-keeper agent)

doc-keeper verifies and updates all cross-references:
- `README.md` — Target Models table, Switching Models table, Repository Structure
- `AI_INSTRUCTIONS.md` — project hierarchy
- `ROADMAP.md` — Current Status
- `docs/client-settings.md` — capability table, sampler table, per-model section
- `docs/gpu-strategy-guide.md` — model reference table (if applicable)
- `.claude/agents/model-manager.md` — directory structure
- `.claude/agents/gpu-optimizer.md` — model reference table
- `benchmarks/evalplus/README.md` — if bench profile added

## Agent roles summary

| Phase | Agent | Role |
|-------|-------|------|
| 1. Evaluate | model-manager | Analyze model card, advise on quant, guide download |
| 3. Profile | gpu-optimizer | Calculate VRAM, select strategy, generate `-ot` config |
| 4. Samplers | (main conversation) | Research and document sampler settings |
| 5. Test | gpu-optimizer | Analyze logs, optimize placement |
| 6. Bench profile | gpu-optimizer + benchmark | Create bench config, update pipeline files |
| 7. Benchmark | benchmark | Run EvalPlus, generate report |
| 8. Docs | doc-keeper | Cross-reference audit, update all docs |

## What to implement now

### 1. Update todo_16_feb.md — expand Session 2

Replace the current Session 2 block with a more detailed checklist that references this workflow.

### 2. Update agent instructions (if needed)

Review whether agents need updates to support this workflow:

- **model-manager** (`/.claude/agents/model-manager.md`) — add explicit "new model evaluation" workflow steps; currently focused on download/organize but should also cover the evaluation phase (reading candidate cards, comparing quants, advising the user)
- **gpu-optimizer** (`/.claude/agents/gpu-optimizer.md`) — already well-equipped; may need a note about creating profiles marked "NOT YET TESTED"
- **benchmark** (`/.claude/agents/benchmark.md`) — needs review; check if it documents the full file checklist for adding a new bench profile (models.conf, bench-client.conf, generate-report.py, README.md)

### 3. Later: test the workflow with a candidate

After the workflow is documented and agents updated, test it with one of the existing candidates. User picks which one. This is a separate session — not part of this implementation.

## Files to modify

1. `todo_16_feb.md` — expand Session 2 with detailed checklist
2. `.claude/agents/model-manager.md` — add evaluation workflow
3. `.claude/agents/gpu-optimizer.md` — minor: add "untested profile" convention
4. `.claude/agents/benchmark.md` — update with current pipeline file checklist

## Verification

1. Read updated agents and verify they reference the correct files and workflows
2. Run doc-keeper to check consistency
3. Later (separate session): test the full workflow with a candidate model
