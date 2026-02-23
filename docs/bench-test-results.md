# Benchmark Profile Test Results

Tested 2026-02-15. All profiles use CTX_SIZE=10240, -b 512 -ub 512 (except GLM Q4
which uses default batch size), --cache-type-k q8_0 --cache-type-v q8_0.

> **Note:** UD-Q6_K_XL was removed from `models.conf` on 2026-02-16 after benchmarks
> showed UD-Q5_K_XL is both faster (30 vs 24 t/s) and higher scoring (93.9% vs 92.1%
> HumanEval). UD-Q6 data below is historical.

> **GPU placement note (2026-02-23):** All results below were measured with the old
> `-ot` explicit layer assignment approach (`FIT=off`, `N_GPU_LAYERS=99`). All bench
> profiles were converted to `--fit` with `--n-gpu-layers auto` on 2026-02-23, and
> `FIT_TARGET=128,1024` was set as the default in `docker-compose.yml` to tune
> per-device VRAM headroom for this asymmetric GPU setup (CUDA0 dedicated, CUDA1
> shares with display). Speeds and VRAM usage will differ under FIT auto with tuned
> FIT_TARGET. A re-benchmark is needed to update these figures — see
> `benchmarks/evalplus/results/REPORT.md` for current scores (benchmark scores are
> unaffected by GPU placement changes).

## Hardware

- CUDA0: RTX 4090 (24 GB) — nothing else running
- CUDA1: RTX 5070 Ti (16 GB, ~12.5 GB usable) — runs display/OS
- CPU: 64 GB DDR4

## Results

| Model | Quant | Strategy | Split | Speed | CUDA0 | CUDA1 | Graph splits (bs=1) |
|-------|-------|----------|-------|-------|-------|-------|---------------------|
| GLM-4.7-Flash | Q4_K_M | A (4090 only) | 47/47 | ~140 t/s | 74% | — | 2 |
| GLM-4.7-Flash | Q8_0 | C (both GPUs) | 35+12=47/47 | ~105 t/s | 93% | 65% | 33 |
| GPT-OSS 120B | F16 | D (GPU+CPU) | 13+5=18/36 | ~22 t/s | 96% | 83% | 68 |
| Qwen3-Coder-Next | UD-Q5_K_XL | D (GPU+CPU) | 19+9=28/48 | ~30 t/s | 93% | 89% | 136 |
| Qwen3-Coder-Next | UD-Q6_K_XL | D (GPU+CPU) | 16+8=24/48 | ~24 t/s | 93% | 96% | 132 |

## Optimization attempts that failed

| Model | Attempted split | Result | Reason |
|-------|----------------|--------|--------|
| GLM Q8 | 37+10 | ~102 t/s (slower) | Graph splits jumped 33→53, overhead outweighed faster GPU |
| GPT-OSS 120B | 13+6=19/36 | OOM on CUDA1 | 15.4/16.3 GB after load, no room for runtime allocations |
| Qwen3 UD-Q6 | 17+8=25/48 | OOM (load loop) | Layers too large (~1.33 GB each) for both GPUs at +1 |

## Key findings

1. **Strategy A is king.** When a model fits on 1 GPU: no splits, no transfers,
   maximum speed. GLM Q4 at 140 t/s vs Q8 at 105 t/s is partly quant size but
   also 2 splits vs 33.

2. **Graph splits matter more for GPU↔GPU (Strategy C) than GPU↔CPU (Strategy D).**
   GLM Q8 lost speed with more layers on the faster GPU because of extra splits.
   Qwen3 Q5 gained speed with more GPU layers despite more splits — because
   avoiding CPU is a bigger win than avoiding GPU↔GPU splits.

3. **+1 layer per GPU is the sweet spot when headroom allows.** Going from 18+8
   to 19+9 on Qwen3 Q5 improved speed (29→30 t/s). Going further risks OOM for
   marginal gains.

4. **CUDA1 (5070 Ti) is the limiting factor.** OOM always happened on CUDA1 first
   due to display/OS overhead eating ~3.5 GB. The 4090 consistently had more room.

5. **Rule of thumb:** if there's room for 2+ layers of headroom, add 1 per GPU.
   If only 1 layer of headroom, leave it — the gain is minimal or risks OOM.

## Comparison: bench vs production splits

These numbers help estimate production profile optimization. Production uses larger
context (64K-256K) and larger batch sizes (2048-4096), consuming more VRAM for KV
cache and compute buffers. So production splits will always have fewer GPU layers.

| Model | Bench split | Production split | Difference |
|-------|------------|-----------------|------------|
| GLM Q4 | 47/47 (all GPU) | all GPU | Same — fits either way |
| GLM Q8 | 35+12=47/47 | TBD (review needed) | — |
| GPT-OSS 120B | 13+5=18/36 | 12+4=16/36 | +2 layers at bench |
| Qwen3 UD-Q5 | 19+9=28/48 | 15+7=22/48 | +6 layers at bench |
| Qwen3 UD-Q6 | 16+8=24/48 | 13+6=19/48 | +5 layers at bench |
