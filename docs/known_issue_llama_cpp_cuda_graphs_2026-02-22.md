# Known Issue: Qwen3next Graph Rewrite Regression in llama.cpp

**Date discovered:** 2026-02-22
**Status:** Fix confirmed, waiting for merge into upstream master
**Upstream issue:** https://github.com/ggml-org/llama.cpp/issues/19816
**Pinned safe version:** `b48e80f67` (b8022, 2026-02-13)
**Current version:** `ed4837891` with local one-line patch (see fix section)

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

## Root cause — bisected

**Bisected on 2026-02-23.** The first bad commit is:

```
1725e316c — models : optimize qwen3next graph (#19375)
Author: Georgi Gerganov
Date:   Sat Feb 14 12:57:36 2026 +0200
```

This PR rewrites the qwen3next computation graph for performance (~30% speedup
on M2 Ultra). The rewrite changes how tensors are laid out — using `ggml_permute`
and `ggml_transpose` views instead of `ggml_cont` copies, and restructuring the
delta net chunking logic.

The commit right before it (`b7742cf` — "ggml : fix GGML_DEBUG with OpenMP")
works fine.

**Not a CUDA graphs issue.** Tested `ed4837891` (latest) with
`GGML_CUDA_DISABLE_GRAPHS=1` — same crash. The problem is in the graph rewrite
itself, not CUDA graph capture.

**Root cause identified by ggerganov:** `ggml_set_inplace` in the delta net
chunking loop modifies a tensor directly in memory. When that tensor is split
across multiple GPUs via `-ot`, the inplace write causes an illegal memory access.
Fix: replace with `ggml_set` (non-inplace copy).

**Previous analysis (superseded):** We initially suspected CUDA graph capture
(PRs #19645 and #19754), but both the bisect and the `GGML_CUDA_DISABLE_GRAPHS=1`
test ruled that out.

### History of this bug

This is the second time this pattern has occurred:

1. **PR #18593** (Jan 2026) — Disabled CUDA graphs for `n-cpu-moe` to fix
   issue #18580 (same illegal memory access crash)
2. **PR #18934** — Re-enabled CUDA graphs for `n-cpu-moe` (believed fixed)
3. **PR #19375** (Feb 2026) — Qwen3next graph rewrite reintroduced the crash
   for multi-GPU `-ot` configurations

## Fix

One-line change in `src/models/delta-net-base.cpp:262`:
```diff
- v = ggml_set_inplace(ctx0, v, o_ch, v->nb[1], v->nb[2], v->nb[3], chunk * v->nb[2]);
+ v = ggml_set(ctx0, v, o_ch, v->nb[1], v->nb[2], v->nb[3], chunk * v->nb[2]);
```

**Tested and confirmed working** on `ed4837891` with this patch applied.
Currently running this patched version locally.

## When the fix lands upstream

1. Check https://github.com/ggml-org/llama.cpp/issues/19816 for the merge
2. Pull the new version, remove local patch
3. Rebuild with `docker compose build --no-cache`
4. Test with a **long prompt** (100+ tokens) on a qwen3next model with
   `-ot` multi-GPU splits to verify
5. Archive this document to `archive/`
