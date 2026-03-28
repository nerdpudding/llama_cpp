# Plan: llama.cpp upstream update (2026-03-28)

## Current state

- **llama.cpp version**: `723c71064` (2026-02-26, tag area ~b8050)
- **Upstream master**: `b0f0dd3e5` (2026-03-28)
- **Gap**: ~397 commits, 1 month
- **Docker image**: `llama_cpp-llama-server:latest` (2.65 GB, built from current source)
- **Local patches**: None active. The old `ggml_set_inplace` → `ggml_set` patch (delta-net-base.cpp) was on an earlier commit and is no longer present.
- **Active model profiles**: glm-flash-q4, glm-flash-q8, glm-flash-exp, qwen35-35b-q6, qwen35-122b-q4, qwen35-27b-q6 + bench variants
- **Config approach**: `--fit on` with `--n-gpu-layers auto`, `FIT_TARGET=128,1024`

## Goal

Update llama.cpp to latest upstream master safely, preserving current functionality and performance.

## Key changes in upstream (relevant to this project)

1. **Fused GDN CUDA kernel** (`d28961d8`) — new `GATED_DELTA_NET` op replaces chunked delta-net path for Qwen3.5 DeltaNet models. Significant speedup potential.
2. **CUDA performance**: native bf16 flash attention (`db9d8aa`), fewer synchronizations between tokens (`2cd20b7`), shared memory ssm_conv (`1e38a7a`)
3. **FIT fix**: gate_up tensor regex fix (`e852eb4`) — may improve layer distribution
4. **Qwen3.5 support**: model type detection updates, Qwen3Model architecture registration
5. **Server**: built-in tools backend, dynamic threads, reasoning content across turns, kill switch
6. **NVFP4**: new quantization format support (not immediately needed but good to have)

## Known risk: `ggml_set_inplace` bug (PR #19375)

The bug in `src/models/delta-net-base.cpp:261` is **still present upstream**. However, two layers protect against it:
- The new fused GDN path (default on for CUDA) bypasses the chunked path entirely
- The project uses `--fit` without `-ot`, so the multi-GPU tensor split crash cannot trigger

Risk level: **low**.

---

## Step 1: Create rollback point

Before touching anything, tag the current working state.

```bash
cd llama.cpp/
git tag local-working-2026-02-26
```

This gives a clean rollback target: `git checkout local-working-2026-02-26`.

## Step 2: Pull upstream

```bash
cd llama.cpp/
git pull origin master
```

No local changes to conflict with (verified: `git diff HEAD` is empty).

## Step 3: Rebuild Docker image

```bash
cd ..
docker compose build --no-cache
```

Watch for:
- sm_120 CUDA compilation errors (known historical issue #18447)
- New build dependencies (check if Dockerfile needs updates)
- Build warnings that might indicate problems

**If build fails**: check error, fix Dockerfile if needed. If it's an upstream regression, rollback to tag and report.

## Step 4: Test — smoke test (quick)

Start container with the smallest/fastest model first.

```bash
./start.sh glm-flash-q4
```

Verify:
- Container starts without errors
- Server reports healthy on port 8080
- FIT placement log looks correct (CUDA0 + CUDA1 usage)

Then send a short prompt:
```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Say hello"}],"max_tokens":50}' | jq .choices[0].message.content
```

## Step 5: Test — long prompt (critical)

This is the test that caught the last regression (lesson #6). Send a 200+ token prompt:

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Write a detailed Python function that implements a binary search tree with insert, delete, search, and in-order traversal methods. Include docstrings, type hints, and error handling. Then write unit tests for each method using pytest, covering edge cases like empty tree, single node, duplicate values, and deletion of nodes with two children."}],"max_tokens":1000}' | jq .choices[0].message.content
```

This must complete without CUDA errors.

## Step 6: Test — all model architectures

Test each architecture type (not every profile, but each distinct model):

| Model | Architecture | Test |
|-------|-------------|------|
| glm-flash-q4 | MoE (GLM, MLA) | Steps 4-5 |
| qwen35-35b-q6 | MoE (Qwen3.5, DeltaNet) | Short + long prompt |
| qwen35-122b-q4 | MoE (Qwen3.5, DeltaNet, large) | Short + long prompt |

The DeltaNet models are the most important — they exercise the new fused GDN path.

For each model:
1. Start via dashboard or `./start.sh <profile>`
2. Short prompt (does it load and respond?)
3. Long prompt 200+ tokens (does generation complete?)
4. Check for CUDA errors in container logs
5. Note token speed (compare to known baseline from ROADMAP.md)

**Expected baselines** (from ROADMAP.md):
- GLM Q4: ~147 t/s
- Qwen3.5-35B: ~120 t/s
- Qwen3.5-122B: ~18 t/s

Speed should be equal or better (fused GDN may improve DeltaNet speeds).

## Step 7: Test — verify fused GDN is active

Check container logs when starting a Qwen3.5 model. Look for:
- References to `GATED_DELTA_NET` or `fused_gdn` in initialization
- Absence of chunked delta-net fallback warnings
- Graph split count (should be similar or lower than current)

## Step 8: Verify Dockerfile compatibility

If step 3 succeeds, this is already confirmed. But double-check:
- No new runtime dependencies needed (check upstream Dockerfile changes)
- `--flash-attn on` flag still works
- `--fit` and `--fit-target` flags still work (no renames or removals)

```bash
docker compose exec llama-server llama-server --help 2>&1 | grep -E 'fit|flash-attn|cache-type'
```

## Fallback plan

### If build fails (step 3)
1. Check error message — likely a new dependency or CUDA compatibility issue
2. Try to fix Dockerfile (add dependency, adjust flags)
3. If unfixable: `cd llama.cpp && git checkout local-working-2026-02-26`
4. Rebuild with known-good version

### If tests fail (steps 4-7)
1. Check container logs for specific error
2. If CUDA crash: check if it's the old `set_inplace` bug hitting the chunked fallback
   - Verify: is fused GDN active? Check logs.
   - If fused GDN is off for some reason, try forcing it or apply the old one-line patch
3. If performance regression (>10% slower): check FIT placement, graph splits, VRAM usage
4. If specific model fails but others work: investigate that model type, check upstream issues
5. **Nuclear option**: rollback to tag
   ```bash
   cd llama.cpp && git checkout local-working-2026-02-26
   cd .. && docker compose build --no-cache
   ```
   This restores the exact previous state.

### If rollback is needed
The tag `local-working-2026-02-26` preserves the exact commit that is currently running in production. A rollback is always possible and returns to a known-good state.

---

## Success criteria

- [ ] Docker image builds successfully
- [ ] GLM Q4 passes smoke + long prompt test
- [ ] Qwen3.5-35B passes smoke + long prompt test
- [ ] Qwen3.5-122B passes smoke + long prompt test
- [ ] No CUDA errors in any container logs
- [ ] Token speeds are within 10% of baseline (or better)
- [ ] Fused GDN path confirmed active for DeltaNet models

## After success

- Update ROADMAP.md with new llama.cpp version
- Note any speed changes
- Archive this plan to `archive/2026-03-28_PLAN_llama_cpp_update.md`
