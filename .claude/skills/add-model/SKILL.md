---
name: add-model
description: "Streamlined workflow for evaluating and adding a new GGUF model to the project. Guides through 8 phases: evaluate, download, create profile, find samplers, test, create bench profile, run benchmark, and update documentation."
---

# Add New Model Workflow

You are orchestrating the addition of a new model to this llama.cpp Docker project. Follow the phases below in order. Use the specified agent at each phase. Do NOT skip phases unless explicitly told to.

**Arguments:** The user may provide a candidate name (matching a file in `models/documentation/CANDIDATES/`) or a HuggingFace model name.

## Before you start

1. Read `AI_INSTRUCTIONS.md` for project context
2. Read `docs/gpu-strategy-guide.md` for GPU placement strategies
3. Read `docs/lessons_learned.md` for known pitfalls
4. If a candidate name was given, read the model card from `models/documentation/CANDIDATES/`
5. Read `models.conf` to understand existing profile patterns

## Phase 1: Evaluate (model-manager agent)

Use the **model-manager** agent to analyze the candidate:

- What kind of model? (Dense vs MoE, params, layers, experts, architecture)
- What quantized options exist? How large are they?
- What are the model's specialties/use cases?
- Does it fit on the hardware? (RTX 4090 24GB + RTX 5070 Ti 16GB + 64GB RAM)
- Which quant is the best fit? (balance quality vs VRAM vs speed)

**You MUST ask the user** which quant to use after presenting options with sizes and trade-offs. The user may also tell you upfront which quant they want.

## Phase 2: Download & organize (user action)

Tell the user:
- The exact download command: `huggingface-cli download <repo> <file(s)> --local-dir models/<ModelName>/<QuantName>/`
- Where to place files following existing hierarchy (see `models/` structure)
- For multi-part GGUF: all parts must be in the same directory

**Wait for the user to confirm files are in place before continuing.**

## Phase 3: Create production profile (gpu-optimizer agent)

Use the **gpu-optimizer** agent to create the production profile in `models.conf`:

The agent will:
1. Read the model card
2. Follow `docs/gpu-strategy-guide.md` decision tree
3. Check `docs/lessons_learned.md` for pitfalls
4. Study existing optimized profiles in `models.conf` as reference
5. Calculate VRAM budget (model weights + KV cache at target context + compute buffers)
6. Select strategy: Strategy A (single GPU) or FIT auto (multi-GPU). Do NOT use `-ot` GPU assignments or set `N_GPU_LAYERS=99` / `FIT=off`.
7. Add production profile to `models.conf` with:
   - NAME, DESCRIPTION, SPEED (marked as `~estimated`)
   - MODEL path, CTX_SIZE
   - EXTRA_ARGS with `--jinja -np 1` and sampler/placement flags
     (add `--split-mode none --main-gpu 0` only for Strategy A)
   - Comments: architecture source, strategy rationale
   - Comment: `# NOT YET TESTED — run ./start.sh <id> and share startup logs`

## Phase 4: Find sampler settings (research in main conversation)

Research recommended sampler settings for this model:
- Check the model card for official recommendations
- Check Unsloth docs if applicable (UD quants)
- Determine: temperature, top_p, top_k, min_p, repeat_penalty
- Check if the model needs special system prompt handling (like GPT-OSS reasoning levels)
- Add sampler flags to EXTRA_ARGS in the production profile
- Add a new section to `docs/client-settings.md` with settings and explanation

## Phase 5: Test (user + gpu-optimizer agent)

1. Tell the user to run `./start.sh <new-profile-id>`
2. Ask the user to share the server startup log
3. Use the **gpu-optimizer** agent to analyze:
   - Did it load successfully? Any OOM?
   - VRAM usage per GPU — room for optimization?
   - Actual speed (t/s) — update SPEED field
   - Graph splits — acceptable?
4. Iterate if needed: adjust layer split, batch sizes, etc.
5. Remove `# NOT YET TESTED` comment, add actual measured values

## Phase 6: Create bench profile (optional, gpu-optimizer + benchmark agents)

Ask the user if they want a bench profile. If yes:

Use the **gpu-optimizer** agent to create a bench profile in `models.conf`:
- Section ID: `[bench-<model-id>]`
- CTX_SIZE=10240 (HumanEval worst case ~8.4K)
- `--reasoning-format none` if it's a thinking model (chain-of-thought must go into content field for evalplus)
- No sampler args (evalplus sends temperature=0)
- For Strategy A (single GPU): add `--split-mode none --main-gpu 0`
- For multi-GPU: no placement flags — FIT auto handles it (smaller context = FIT keeps more on GPU automatically)

Use the **benchmark** agent to update pipeline files:
- `benchmarks/evalplus/bench-client.conf` — add section if model needs a system prompt
- `benchmarks/evalplus/generate-report.py` — add to `DISPLAY_NAMES` dict and `REFERENCE_MAP` dict (if official scores exist)
- `benchmarks/evalplus/README.md` — add to profiles table

Note: `benchmark.sh` auto-discovers `bench-*` profiles from `models.conf` — no code changes needed there.

## Phase 7: Run benchmark (optional, user action)

If the user wants to benchmark:

```bash
cd benchmarks/evalplus
source .venv/bin/activate
./benchmark.sh bench-<model-id>
```

Results auto-generated in `results/REPORT.md`. Use the **benchmark** agent to help interpret results.

## Phase 8: Update documentation (doc-keeper agent)

**If the model card was in `models/documentation/CANDIDATES/`**, move it to `models/documentation/` now — the model has graduated from candidate to active.

Use the **doc-keeper** agent to verify and update all cross-references:

**Checklist of files to verify:**
- [ ] `README.md` — Models table, Candidate models table (remove if graduated), Repository Structure
- [ ] `AI_INSTRUCTIONS.md` — project hierarchy (model card location, new directories)
- [ ] `ROADMAP.md` — Current Status section
- [ ] `docs/client-settings.md` — capability table, sampler table, per-model section
- [ ] `docs/gpu-strategy-guide.md` — model reference table (if applicable)
- [ ] `.claude/agents/model-manager.md` — directory structure
- [ ] `.claude/agents/gpu-optimizer.md` — model reference table
- [ ] `benchmarks/evalplus/README.md` — if bench profile was added

## Phase summary

| Phase | Agent | What happens |
|-------|-------|-------------|
| 1. Evaluate | model-manager | Analyze model, advise on quant |
| 2. Download | (user) | User downloads and places files |
| 3. Profile | gpu-optimizer | Calculate VRAM, create models.conf entry |
| 4. Samplers | (main conversation) | Research and set sampler settings |
| 5. Test | gpu-optimizer | Analyze logs, iterate on placement |
| 6. Bench profile | gpu-optimizer + benchmark | Create bench config, update pipeline |
| 7. Benchmark | (user) + benchmark | Run EvalPlus, interpret results |
| 8. Docs | doc-keeper | Cross-reference audit, update all docs |
