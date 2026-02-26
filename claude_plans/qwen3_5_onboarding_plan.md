# Plan: Qwen3.5 Model Onboarding

## Context

Three Qwen3.5 candidates evaluated for onboarding. All share the same generation
(Gated DeltaNet hybrid architecture, 262K native context, `--no-context-shift`
required). The user is already downloading the recommended quants.

## Models and Recommended Quants

| Model | Type | Quant | Size | Strategy | Est. Speed | Replaces |
|-------|------|-------|------|----------|------------|----------|
| Qwen3.5-122B-A10B | MoE (10B active) | UD-Q4_K_XL | 68.4 GB | FIT + CPU offload | ~15-22 t/s | GPT-OSS 120B |
| Qwen3.5-35B-A3B | MoE (3B active) | UD-Q6_K_XL | 30.3 GB | FIT (both GPUs) | ~80-120 t/s | Qwen3-Next-80B-A3B |
| Qwen3.5-27B | Dense (27B active) | UD-Q8_K_XL | 32.4 GB | FIT (both GPUs) | ~20-30 t/s | Qwen3-Coder-Next |

## Architecture Details

**Qwen3.5-122B-A10B (MoE):** 122B total, 10B activated. 48 layers. 256 experts,
8 routed + 1 shared. Expert intermediate dim 1024. Hidden dim 3072. 12/48 KV layers.

**Qwen3.5-35B-A3B (MoE):** 35B total, 3B activated. 40 layers. 256 experts,
8 routed + 1 shared. Expert intermediate dim 512. Hidden dim 2048. 10/40 KV layers.

**Qwen3.5-27B (Dense):** 27B total, ALL active. 64 layers. FFN intermediate dim
17408. Hidden dim 4096. 16/64 KV layers.

## Quant Selection Reasoning

### 122B-A10B: UD-Q4_K_XL over MXFP4_MOE and UD-Q5_K_XL

**Why not MXFP4_MOE (68.3 GB)?** Same file size as UD-Q4 but uniform 4-bit
precision on all tensors. UD-Q4 applies higher precision to router/gate weights
which determine expert selection. Router quantization errors cascade — wrong
expert selected = wrong output. This effect was confirmed with Qwen3-Coder-Next
UD quants ("better expert selection and no self-correction behavior").

GPT-OSS 120B is natively MXFP4 — it was *trained* at that precision, so the
model learned to compensate. Qwen3.5-122B was trained at full precision and
then quantized. Post-training MXFP4 has no training compensation, so smart bit
allocation (UD) is strictly better at the same total size.

**Why not UD-Q5_K_XL (87 GB)?** Memory math: 87 GB model, ~36 GB on GPU,
~51 GB on CPU. With 64 GB RAM minus ~8 GB OS = ~56 GB available. Only ~5 GB
left for KV cache and compute buffers at 262K context. Too tight — risk of OOM
or forced context reduction. The Q4 at 68.4 GB leaves ~24 GB CPU headroom.

### 35B-A3B: UD-Q6_K_XL over UD-Q8_K_XL

30.3 GB hits the sweet spot — nearly identical to GLM Q8 (30 GB) which runs at
~112 t/s across both GPUs with FIT. Same 3B active as GLM. Could be the fastest
capable model in the lineup. Q8 at 42 GB forces CPU offload, significantly
slower. Start with Q6; Q8 is the fallback if quality is insufficient.

### 27B Dense: UD-Q8_K_XL over UD-Q6_K_XL

Dense model = every parameter active every token. Higher precision directly
translates to better output — no "wasted" bits on inactive experts like MoE.
32.4 GB fits across both GPUs with FIT (comparable to GLM Q8 territory).
Q6 at 23.1 GB is borderline for Strategy A at 10K but not at 262K production
context. Quality benefit of Q8 on dense outweighs the marginal speed gain of Q6.

## Benchmark Comparison (from model cards, FP16 reference scores)

| Benchmark | 122B-A10B | 27B (dense) | 35B-A3B | GPT-OSS-120B |
|-----------|-----------|-------------|---------|--------------|
| MMLU-Pro | **86.7** | 86.1 | 85.3 | 80.8 |
| SWE-bench Verified | 72.0 | **72.4** | 69.2 | 62.0 |
| Terminal Bench 2 | **49.4** | 41.6 | 40.5 | 18.7 |
| LiveCodeBench v6 | 78.9 | **80.7** | 74.6 | 82.7 |
| CodeForces | **2100** | 1899 | 2028 | 2157 |
| FullStackBench en | **62.6** | 60.1 | 58.1 | 58.9 |
| BFCL-V4 (agentic) | **72.2** | 68.5 | 67.3 | -- |

Notable: the 27B dense beats the 122B on SWE-bench (72.4 vs 72.0) and
LiveCodeBench (80.7 vs 78.9). All three significantly outperform GPT-OSS
on coding and agentic benchmarks.

## Onboarding Plan (per model, using `/add-model` skill)

Each model goes through the 8-phase `/add-model` workflow:

### Phase 1: Evaluate — DONE (this plan)
Architecture analyzed, quant selected, sizes verified.

### Phase 2: Download — DONE
Files on disk:
```
models/Qwen3.5/
├── Dense/
│   └── 27B-UD-Q8_K_XL/
│       └── Qwen3.5-27B-UD-Q8_K_XL.gguf                          (31 GiB)
└── MoE/
    ├── 122B/
    │   └── US_Q4_K_XL/
    │       ├── Qwen3.5-122B-A10B-UD-Q4_K_XL-00001-of-00003.gguf (metadata)
    │       ├── Qwen3.5-122B-A10B-UD-Q4_K_XL-00002-of-00003.gguf (47 GiB)
    │       └── Qwen3.5-122B-A10B-UD-Q4_K_XL-00003-of-00003.gguf (18 GiB)
    └── 35B/
        └── UD6_K_XL/
            └── Qwen3.5-35B-A3B-UD-Q6_K_XL.gguf                  (29 GiB)
```
MODEL paths for models.conf (relative to models/):
- `Qwen3.5/MoE/122B/US_Q4_K_XL/Qwen3.5-122B-A10B-UD-Q4_K_XL-00001-of-00003.gguf`
- `Qwen3.5/MoE/35B/UD6_K_XL/Qwen3.5-35B-A3B-UD-Q6_K_XL.gguf`
- `Qwen3.5/Dense/27B-UD-Q8_K_XL/Qwen3.5-27B-UD-Q8_K_XL.gguf`

### Phase 3: Create production profiles (gpu-optimizer agent)
For each model, create a `models.conf` entry following the decision tree:
- All three need `--no-context-shift` (DeltaNet)
- All three use `--jinja -np 1`
- 35B-A3B at 30.3 GB: test if Strategy A is viable at reduced context, otherwise FIT auto
- 27B at 32.4 GB: FIT auto
- 122B at 68.4 GB: FIT auto + CPU offload

### Phase 4: Find sampler settings (research)
Check Qwen3.5 model cards and Unsloth docs for recommended samplers.
All three models likely share the same recommended settings (same family).

### Phase 5: Test with full context (262K)
For each model:
1. Start with `./start.sh <profile-id>`
2. Verify it loads without OOM at 262K context
3. Check VRAM usage, graph splits, actual speed
4. Iterate if needed (adjust FIT_TARGET, context, etc.)
5. Update SPEED field in models.conf with measured values

### Phase 6: Create bench profiles
For each model, add `[bench-<id>]` profiles to models.conf:
- CTX_SIZE=10240
- `--reasoning-format none` if thinking model
- No sampler args (evalplus sends temperature=0)
- Update bench-client.conf, generate-report.py, benchmarks README

### Phase 7: Run EvalPlus benchmarks
Run HumanEval+ for all three new models:
```bash
cd benchmarks/evalplus
source .venv/bin/activate
./benchmark.sh bench-qwen35-122b
./benchmark.sh bench-qwen35-35b
./benchmark.sh bench-qwen35-27b
```
Then generate the full comparison report including all existing models.

### Phase 8: Update documentation
Move model cards from `models/documentation/CANDIDATES/` to `models/documentation/`.
Run doc-keeper to update all cross-references (README, AI_INSTRUCTIONS, gpu-strategy-guide, etc.).

## Post-Onboarding: Model Cleanup

After benchmarks are complete and results compared, decide which models to
retire to save disk space:

**Likely candidates for removal:**
- GPT-OSS 120B (61 GB) — if Qwen3.5-122B-A10B outperforms it across the board
- Qwen3-Next-80B-A3B (53 GB) — if Qwen3.5-35B-A3B matches or beats it
- Qwen3-Coder-Next UD-Q5 (57 GB) — if Qwen3.5-27B or 35B-A3B covers coding

**Likely keepers regardless:**
- GLM-4.7 Flash Q4/Q8 — different architecture, proven fast daily driver, good for comparison
- Whichever Qwen3.5 models prove best in benchmarks

Decision will be based on benchmark results + hands-on usage experience.
