# Known Issue: CUDA Graph Regression in llama.cpp

**Date discovered:** 2026-02-22
**Status:** Open — waiting for upstream fix
**Upstream issue:** https://github.com/ggml-org/llama.cpp/issues/19816
**Pinned safe version:** `b48e80f67` (b8022, 2026-02-13)

---

## Summary

Updating llama.cpp beyond commit `b48e80f67` causes CUDA illegal memory access
errors on MoE models using `-ot` multi-GPU tensor splits. Prompt processing
succeeds, but the first decode step crashes on prompts longer than ~100 tokens.
Short prompts work fine, which makes the bug easy to miss during smoke testing.

## Affected models

- Qwen3-Next (80B-A3B) — both UD-Q5_K_XL and UD-Q4_K_XL
- Qwen3-Coder-Next (80B-A3B) — UD-Q5_K_XL
- Likely any MoE model using `-ot` with `exps=CPU` and multi-GPU splits

## Error

```
/build/ggml/src/ggml-cuda/ggml-cuda.cu:97: CUDA error: an illegal memory access was encountered
```

Occurs after prompt processing completes, during the first token generation
step. The sampler initializes successfully, then the CUDA error fires.

## Root cause analysis

The regression is in the CUDA graph capture logic in `ggml/src/ggml-cuda/ggml-cuda.cu`.
Two PRs between our safe version and the broken tip are the likely culprits:

### PR #19645 — `cuda: enable CUDA graphs for MMID 1 <= BS <= 4`
- Changed `MUL_MAT_ID` to allow CUDA graphs for small batch sizes with
  quantized tensors
- Previously any `MUL_MAT_ID` with `ne[2] != 1` disabled CUDA graphs

### PR #19754 — `Improve CUDA graph capture`
- Complete rewrite of the CUDA graph activation logic
- Replaced the old "4 consecutive updates = permanently disable" safety mechanism
  with a warmup-based system
- Removed the `instance == nullptr` check from `ggml_cuda_graph_update_required`
- Removed batch-size-per-node-name compatibility checks that were previously
  blocking CUDA graphs for certain operations

The combination allows CUDA graphs to activate in MoE + multi-GPU scenarios
where they were previously blocked. MoE expert routing varies per token, meaning
memory access patterns are not stable between graph captures — exactly the
condition where CUDA graphs break.

### History of this bug

This is the second time this pattern has occurred:

1. **PR #18593** (Jan 2026) — Disabled CUDA graphs for `n-cpu-moe` to fix
   issue #18580 (same illegal memory access crash)
2. **PR #18934** — Re-enabled CUDA graphs for `n-cpu-moe` (believed fixed)
3. **PR #19645 + #19754** (Feb 2026) — Expanded CUDA graph coverage further,
   reintroducing the crash

## Workaround (if upstream doesn't fix it)

Add an environment variable to `docker-compose.yml` to disable CUDA graphs entirely:

```yaml
services:
  llama-server:
    environment:
      - GGML_CUDA_DISABLE_GRAPHS=1
```

This uses a built-in escape hatch in llama.cpp's `is_enabled()` function.
No code changes required. Trade-off: loses the performance benefit of CUDA
graphs for all models, not just MoE.

## What to do when checking on this issue

1. Check https://github.com/ggml-org/llama.cpp/issues/19816 for updates
2. If fixed, identify the fix commit and test by:
   - Pulling the new version
   - Rebuilding with `docker compose build --no-cache`
   - Testing with a **long prompt** (100+ tokens) on a qwen3next model with
     `-ot` multi-GPU splits — short prompts don't trigger the bug
   - Testing all MoE models, not just one
3. If not fixed but we need newer llama.cpp features, use the
   `GGML_CUDA_DISABLE_GRAPHS=1` workaround
4. Update this document and `lessons_learned.md` when resolved
