# Known Issue: Qwen3next Graph Rewrite Regression in llama.cpp

**Date discovered:** 2026-02-22
**Status:** Resolved — migrated to `--fit` with `--n-gpu-layers auto`. All `-ot` profiles removed.
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

## Alternative approaches tested (2026-02-23)

ggerganov suggested `-ts` (tensor-split) as the proper way to split GPU load,
and pwilkin suggested `--fit` without `-ot`. Both were tested at 262K context.
Initial tests used `N_GPU_LAYERS=99` (then-current docker-compose default):

| Config | N_GPU_LAYERS | Result | Speed | Notes |
|--------|-------------|--------|-------|-------|
| `-ot blk.0-18=CUDA0,blk.19-27=CUDA1,exps=CPU` | 99 | **Crash** | — | Original bug |
| `-ot blk.0-18=CUDA0,blk.19-27=CUDA1,exps=CPU` (with patch) | 99 | Works | ~29.5 t/s | 10K ctx bench |
| `-ot blk.0-16=CUDA0,blk.17-24=CUDA1,exps=CPU` (with patch) | 99 | Works | ~28 t/s | 262K ctx production |
| `-ot exps=CPU` with `--fit on` | 99 | Works | ~21.7 t/s | GPUs barely used (~1.6 GB total) |
| `-ts 21,10 -ot exps=CPU` | 99 | Works | ~19.8 t/s | Same problem: GPUs barely used |
| `--fit on` without `-ot` | 99 | **OOM** | — | 53 GB model > 40 GB total GPU |
| `--fit on` without `-ot` | **auto** | **Works** | **~32.9 t/s** | **FIT offloads experts to CPU automatically** |

**Revised conclusion (2026-02-23):** The initial OOM with `--fit on` without `-ot`
was caused by `N_GPU_LAYERS=99` overriding FIT's automatic layer count calculation.
With `N_GPU_LAYERS=99`, llama.cpp attempted to place all 99 layers on GPU, OOMing
before FIT could offload experts to CPU. Changing to `--n-gpu-layers auto` (which
lets FIT decide) resolved the issue.

With `--fit on` and `--n-gpu-layers auto`, Qwen3-Next at 262K achieves:
- 32.9 t/s (vs 26.5 t/s with manual `-ot`)
- 55 graph splits (vs 136 with manual `-ot`)
- CUDA0 ~20 GB, CUDA1 ~8 GB, CPU ~53 GB experts

This is significantly better than the manual `-ot` approach in both speed and
graph splits. All profiles were converted to FIT auto on 2026-02-23.

See commented-out test profiles in `models.conf` for exact configurations.

## Resolution

The `-ot` CUDA illegal memory access bug (PR #19375 regression) was addressed via
two parallel tracks:

1. **Local patch** (applied to `ed4837891`): replace `ggml_set_inplace` with
   `ggml_set` in `src/models/delta-net-base.cpp:262`. This fixes the crash for
   `-ot` configurations.

2. **Migration to FIT auto** (2026-02-23): removed all `-ot` GPU device assignments
   from `models.conf`, set `N_GPU_LAYERS=auto` in Dockerfile and docker-compose.yml.
   FIT auto produces better speed and fewer graph splits than the old `-ot` approach,
   and avoids the class of bugs that affect `-ot` multi-GPU configurations entirely.

The project now runs on track 2. The local patch is still in place for the current
build version (`ed4837891`) but is no longer load-bearing — FIT auto does not use
`-ot` tensor splits, so the PR #19375 crash path cannot be triggered.

## If reverting to -ot (not recommended)

If future work requires manual `-ot` placement:
1. Verify the upstream fix for PR #19375 has been merged, or keep the local patch
2. Set `N_GPU_LAYERS=99` in Dockerfile and docker-compose.yml
3. Add `-ot blk.X=CUDA0,blk.Y=CUDA1,exps=CPU` back to EXTRA_ARGS with `FIT=off`
4. Test with a **long prompt** (100+ tokens) on all affected models
5. This document provides the historical context
