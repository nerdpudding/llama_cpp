# Lessons Learned

Mistakes made during configuration and optimization, root causes, and rules
to prevent them in the future. This document is a living reference — add new
entries as issues are discovered.

---

## 1. Assumed GLM-4.7-Flash was a dense model

**What happened:** GLM-4.7-Flash was configured and documented as a "dense,
compact model" throughout models.conf. GPU strategies were designed assuming
all parameters are active per token. This led to using `FIT=on` (which
auto-distributes but doesn't understand expert/attention priorities) and
`--tensor-split` (designed for dense models) instead of the correct MoE
approach with `-ot`.

**Root cause:** The model name and file size (~18 GB for Q4) "felt" small,
so it was assumed to be dense. The model card was never checked. It clearly
states: "GLM-4.7-Flash is a 30B-A3B MoE model."

**Actual architecture (from GGUF metadata):**
- 30B total parameters, 3B active per token (A3B)
- 47 layers (1 dense lead + 46 MoE)
- 64 experts per MoE layer, 4 active + 1 shared
- Expert FFN: 1536, Dense FFN: 10240
- GQA: 20 attention heads, 1 KV head

**Impact:** The model worked (it always loads and runs), but GPU placement
was suboptimal. With `FIT=on`, experts were spread across both GPUs
unnecessarily. With `--split-mode none`, it happened to work for Q4 because
the full model fits on the 4090, but this was not a reasoned decision.

**Prevention rule:** Always verify model architecture from the model card
(`models/documentation/`) before making any GPU placement decisions. Check
dense vs MoE, expert count, active parameters. Never infer architecture from
model name or file size. See `docs/gpu-strategy-guide.md` for the decision tree.

---

## 2. Applied "exps=CPU" as a universal MoE best practice

**What happened:** After discovering GLM is MoE, the immediate reaction was
"it's MoE, so we need `exps=CPU`" — the same approach used for GPT-OSS and
Qwen3. This was applied without checking whether the model actually exceeds
GPU VRAM.

**Root cause:** Pattern matching from other MoE models (GPT-OSS at 61 GB,
Qwen3 at 57-64 GB) where `exps=CPU` is genuinely necessary. The rule
"MoE = exps=CPU" was treated as universal when it's actually conditional.

**The correct rule:** `exps=CPU` is a trade-off, not a default. Expert weights
in VRAM are accessed at ~1 TB/s (GPU memory bandwidth). On CPU, they require
PCIe transfer at ~32 GB/s plus slower CPU compute. Keeping experts on GPU is
always faster **if they fit**. Only offload to CPU when GPU VRAM is insufficient
to hold the full model.

**Decision logic:**
- Model fits on GPU entirely → keep everything on GPU (fastest)
- Model doesn't fit → offload experts to CPU, keep attention on GPU
- The threshold is total VRAM available, not the model architecture

**Prevention rule:** After verifying architecture, calculate total VRAM needed.
Only add `exps=CPU` when the model exceeds available GPU VRAM. Document the
reasoning in models.conf comments.

---

## 3. Wrote incorrect documentation, then treated it as truth

**What happened:** models.conf contained comments like "Dense model, FIT=on
auto-optimizes" for GLM. Later, when optimizing bench profiles, these comments
were referenced as facts instead of being verified.

**Root cause:** The original comments were written based on assumptions (see #1).
Once written, they became "trusted documentation" that was referenced without
question. This created a self-reinforcing error: wrong assumption → wrong docs
→ wrong docs used as source → more wrong decisions.

**Impact:** Multiple rounds of incorrect optimization: first `FIT=on`, then
`--tensor-split`, then `exps=CPU` — each based on the previous wrong assumption.

**Prevention rule:**
- When writing documentation about model architecture, always verify against
  the model card or GGUF metadata first.
- When referencing existing documentation for decisions, verify the key facts
  independently — especially architecture claims.
- Include the source of architecture information in comments (e.g., "MoE per
  model card" not just "MoE").

---

## 4. Estimated model sizes without checking actual file sizes

**What happened:** GLM Q8 was estimated at "~16-17 GB" based on mental math.
The actual file is 30 GB. This led to confidently claiming "Q8 fits on 4090
alone" when it doesn't.

**Root cause:** The estimate was based on a vague assumption about Q8 being
"roughly double Q4 in parameter efficiency" without checking the actual GGUF
file. Q4_K_M averages ~4.5 bits/param, Q8_0 is 8 bits/param, so the ratio
is 8/4.5 ≈ 1.78x, not 2x. Applied to 18 GB Q4: 18 × 1.78 = 32 GB, close
to the actual 30 GB.

**Prevention rule:** Always check actual file sizes with `ls -lh` before
making VRAM calculations. Never estimate from quantization names alone. File
sizes for all models should be documented in models.conf comments or in the
model quick reference table in `docs/gpu-strategy-guide.md`.

---

## 5. Set `-ub` equal to `-b`, wasting VRAM on oversized compute buffers

**What happened:** Production profiles for GPT-OSS 120B used `-b 2048 -ub 2048`
and the gpu-optimizer agent recommended `-b 1024 -ub 1024` for GLM Q8. The GLM
Q8 aggressive profile (33+14=47/47) OOMed on CUDA0 by 372 MiB — the compute
buffer was 897 MiB with `-ub 1024`. With the default `-ub 512`, it would have
been ~448 MiB, and the profile would have fit.

**Root cause:** Treating `-b` and `-ub` as a single parameter. They control
different things:
- `-b` (logical batch) = how many tokens per prompt processing step → speed
- `-ub` (micro-batch) = GPU compute chunk size → **determines compute buffer VRAM**

Setting both to the same value wastes VRAM on a compute buffer sized for the
full batch when the GPU only needs a buffer sized for one micro-batch. The
default `-ub 512` is what both llama.cpp and Ollama use.

**Measured impact:**
- `-ub 512`: ~448 MiB compute buffer (GLM Q8)
- `-ub 1024`: ~897 MiB compute buffer (+449 MiB wasted)
- `-ub 2048`: ~1,500-2,400 MiB compute buffer (+1,000-2,000 MiB wasted)

**Prevention rule:** Always use `-ub 512` (or omit it to use the default).
Only set `-b` explicitly when you need to control prompt processing speed.
The correct production setting is `-b 2048 -ub 512` (or just `-b 2048`).
Never write `-b X -ub X` with the same value. See `docs/gpu-strategy-guide.md`
"Batch size and VRAM" for the full reference.

---

## General prevention rules

1. **Read the model card first.** Before any configuration work on a model,
   read `models/documentation/README_modelcard_*.md`. If it doesn't exist,
   download the card from the model's source.

2. **Verify, don't assume.** Check GGUF metadata, file sizes, and architecture
   independently. Don't trust existing comments without verification.

3. **Follow the decision tree.** Use `docs/gpu-strategy-guide.md` step by step.
   Don't skip steps or take shortcuts based on pattern matching from other models.

4. **Document the reasoning.** In models.conf comments, explain WHY a particular
   strategy was chosen, not just WHAT it is. Include the source of key facts.

5. **Test and measure.** After making changes, verify with actual load logs
   and `nvidia-smi`. Check that model buffers, KV cache, and compute buffers
   are on the expected devices.

6. **Test llama.cpp updates with real workloads before committing.** A
   successful build and a short prompt don't prove correctness. Always test
   with longer prompts (100+ tokens) on all model types and GPU configurations
   before declaring an update safe. See lesson #6 below.

---

## 6. Updated llama.cpp without testing multi-GPU inference with real prompts

**What happened:** Pulled 93 new commits from llama.cpp upstream, rebuilt,
tested with a 20-token prompt via curl — worked fine. Started the benchmark
(164 HumanEval problems) and it crashed immediately. Every request with 100+
tokens caused `CUDA error: an illegal memory access was encountered` on the
first generated token. Both Qwen3-Next and Qwen3-Coder-Next were affected.

**Root cause:** A regression in the new upstream code that breaks qwen3next
model inference with `-ot` multi-GPU tensor splits. Prompt processing
succeeds, but the first decode step crashes. Short prompts (<~100 tokens)
happen to work, which masked the issue during manual testing.

**Resolution:** Reverted to previous commit (`b48e80f67`, b8022, 2026-02-13),
rebuilt, verified all models work. Filed upstream:
https://github.com/ggml-org/llama.cpp/issues/19816.
Similar issue was previously reported as #18580 and fixed by PR #18593.

**Prevention rule:** When updating llama.cpp, always test with:
1. A short prompt (smoke test — does it load?)
2. A long prompt (100+ tokens — does inference actually work?)
3. All model architectures, especially MoE models with multi-GPU placement
4. Only then consider the update safe

---

## 7. Hardcoded N_GPU_LAYERS=99 prevented FIT from working

**What happened:** `docker-compose.yml` had `N_GPU_LAYERS` defaulting to `99`
and `Dockerfile` set `ENV N_GPU_LAYERS=99`. When testing `--fit on` without
`-ot` on Qwen3-Next (53 GB model, 40 GB total GPU VRAM), it OOM'd immediately.
The conclusion at the time was "FIT without `-ot exps=CPU` doesn't fit".

During investigation of issue #19816, pwilkin's suggestion to try `--fit` without
`-ot` was tested again — but with `N_GPU_LAYERS=auto`. FIT then worked correctly:
it placed layers on GPU as long as VRAM allowed, then offloaded experts to CPU.
Result: 32.9 t/s at 262K context, 55 graph splits.

**Root cause:** With `N_GPU_LAYERS=99`, llama.cpp interpreted the flag as "try to
put 99 layers on GPU" — overriding FIT's automatic capacity-aware placement logic.
FIT's offloading logic only activates when it is allowed to set the layer count
itself (`--n-gpu-layers auto`). With a hardcoded `99`, it tried to load all layers
on GPU before FIT could decide to offload, causing the OOM.

**Impact:**
- All previous FIT tests with MoE models were invalid — they all ran with `N_GPU_LAYERS=99`
- The comparison "FIT gives 21.7 t/s, `-ot` gives 28 t/s" was comparing FIT-broken
  (hardcoded 99 layers) against `-ot` (manual but correct). Fair comparison: FIT
  gives 32.9 t/s vs `-ot` 28 t/s (with patch).
- The old `-ot` approach was replaced in all profiles on 2026-02-23.

**Prevention rule:**
- Never hardcode `N_GPU_LAYERS` to a specific number in infrastructure files
  (Dockerfile, docker-compose.yml). Use `auto` as the default.
- When testing auto-placement features like FIT, verify that no other config
  variable is overriding the auto behavior.
- When a feature "doesn't work", check for env var overrides before concluding
  the feature is broken.
