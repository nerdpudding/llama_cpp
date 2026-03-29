# Client Settings Reference

Quick reference for recommended client-side settings per model. Use these when configuring any client (web UI, API calls, agentic frameworks, IDE integrations).

**Why this matters:** The server (`models.conf`) sets default sampling parameters, but most clients override them. If your client sends `temperature=0.7` while the server default is `1.0`, the client wins. Always set these explicitly in your client to get the intended behavior.

## Model capabilities

Active models:

| Model | Best for | Thinking | Tool calling | Speed |
|-------|----------|----------|-------------|-------|
| GLM-4.7 Flash | General tasks, reasoning, tool calling | Yes (`<think>` blocks) | Yes (native) | 112-147 t/s |
| Qwen3.5-35B-A3B | Reasoning, coding, multilingual, agentic | Yes (`<think>` blocks, default) | Yes (native) | ~120 t/s |
| Qwen3.5-35B-A3B CL-Distill Q6 | Reasoning, coding, agentic — faster CL-distilled variant | Yes (`<think>` blocks, default) | Yes (native) | ~162 t/s |
| Qwen3.5-35B-A3B CL-Distill Q8 | Highest quality 35B — CL-distilled Q8 variant | Yes (`<think>` blocks, default) | Yes (native) | ~80 t/s |
| Qwen3.5-122B-A10B | Deep reasoning, agentic, terminal/tool use | Yes (`<think>` blocks, default) | Yes (native) | ~18 t/s |
| Qwen3.5-27B | Quality coding, reasoning (dense, all 27B active) | Yes (`<think>` blocks, default) | Yes (native) | ~31 t/s (Q6) |
| Mistral Small 4 119B | Reasoning, multilingual (11 languages), tool use | Yes (per-request `reasoning_effort` = "none" / "high") | Yes (native) | ~TBD t/s (Q3_K_XL) |

Retired models (2026-02-26) — settings preserved below for reference:

| Model | Best for | Thinking | Tool calling | Speed |
|-------|----------|----------|-------------|-------|
| GPT-OSS 120B | Deep reasoning, knowledge, structured output | Yes (configurable low/med/high) | Yes (native) | ~22 t/s |
| Qwen3-Coder-Next | Coding agents, agentic tasks | No | Yes (native) | ~33 t/s |
| Qwen3-Next-80B-A3B | General reasoning, knowledge, agentic, ultra-long context | No | Yes (native) | ~33 t/s |

## Sampler settings at a glance

Qwen3.5 settings apply to **all Qwen3.5 models** (35B-A3B UD, 35B-A3B CL-Distill Q6/Q8, 27B, 122B-A10B) — same family, same recommendations.

Active models:

| Setting | GLM (general) | GLM (coding) | Qwen3.5 all (thinking) | Qwen3.5 all (coding) | Mistral Small 4 |
|---------|--------------|-------------|------------------------|----------------------|-----------------|
| temperature | 1.0 | 0.7 | 1.0 | 0.6 | 0.1 |
| top_p | 0.95 | 1.0 | 0.95 | 0.95 | 1.0 |
| top_k | — | — | 20 | 20 | — |
| min_p | 0.01 | 0.01 | 0.0 | 0.0 | 0.0 |
| presence_penalty | — | — | 1.5 (client-side) | 0.0 | — |
| system prompt | — | — | — | — | — |

Retired models (2026-02-26) — preserved for reference:

| Setting | GPT-OSS | Qwen3-Coder | Qwen3-Next |
|---------|---------|-------------|------------|
| temperature | 1.0 | 1.0 | 0.7 |
| top_p | 1.0 | 0.95 | 0.8 |
| top_k | 0 (disabled) | 40 | 20 |
| min_p | — | 0.01 | — |
| system prompt | "Reasoning: low/med/high" | — | — |

---

## GLM-4.7 Flash

Source: [Z.ai recommended parameters](https://unsloth.ai/docs/models/glm-4.7-flash), model card

| Setting | General chat | Coding / Tool-calling |
|---------|-------------|----------------------|
| temperature | 1.0 | 0.7 |
| top_p | 0.95 | 1.0 |
| min_p | 0.01 | 0.01 |
| top_k | — (not specified) | — (not specified) |
| repeat_penalty | 1.0 (disabled) | 1.0 (disabled) |

**Important notes:**
- **Always disable repeat_penalty** (set to 1.0). Non-default values cause degraded output.
- **Set min_p to 0.01.** llama.cpp defaults to 0.05, which is suboptimal for this model.
- GLM is a **reasoning model** — it produces `<think>...</think>` blocks before the answer. For benchmarks, use `--reasoning-format none` server-side to include thinking in output. For interactive use, the thinking is normally hidden by the chat template.
- No system prompt needed for standard use.

**Server defaults (models.conf):** `--temp 1.0 --top-p 0.95 --min-p 0.01` — matches the "general chat" column. Clients used for coding should override to `temp 0.7, top_p 1.0`.

## GPT-OSS 120B

Source: [OpenAI official](https://huggingface.co/openai/gpt-oss-120b/discussions/21), model card

| Setting | All use cases |
|---------|--------------|
| temperature | 1.0 |
| top_p | 1.0 |
| top_k | disabled (do not set, or set to 0) |
| min_p | — (not specified) |
| repeat_penalty | — (not specified) |

**Important notes:**
- **Disable top_k explicitly.** Some clients (including Hugging Face Transformers) default to `top_k=50` if unset. The official torch implementation and OpenAI explicitly recommend disabling it.
- **Reasoning levels** are controlled via the system prompt, not sampling parameters. This **cannot** be set server-side — llama-server's `--system-prompt` flag is excluded from the binary. You must set it in your client (web UI system prompt field, API `system` message, or agentic framework config).
  - `Reasoning: low` — minimal chain-of-thought, fewer tokens used for reasoning. Best for simple factual questions, quick translations, or tasks where speed matters more than depth.
  - `Reasoning: medium` — **this is the default** when no system prompt is set. Balanced reasoning effort. Good for most general use.
  - `Reasoning: high` — extensive chain-of-thought, uses significantly more tokens for internal reasoning before answering. Best for complex analysis, multi-step problems, math, or tasks where answer quality is critical.
  - **Trade-off:** higher reasoning = more tokens consumed (slower, more compute) but potentially better answers. Lower reasoning = faster and cheaper but may miss nuance on hard problems.
  - Set as the first line of (or as the entire) system prompt. Example: `Reasoning: high`
- GPT-OSS uses the [harmony response format](https://github.com/openai/harmony). The chat template in the GGUF handles this automatically — no manual formatting needed in clients that use the `/v1/chat/completions` API.

**Server defaults (models.conf):** `--temp 1.0 --top-p 1.0` — matches official recommendation. Clients should not need to override sampling, but should set the reasoning level system prompt.

## Qwen3-Coder-Next

Source: [Qwen model card "Best Practices"](https://huggingface.co/Qwen/Qwen3-Coder-Next), [Unsloth guide](https://unsloth.ai/docs/models/qwen3-coder-next)

| Setting | Recommended (all use cases) |
|---------|----------------------------|
| temperature | 1.0 |
| top_p | 0.95 |
| top_k | 40 |
| min_p | 0.01 |
| repeat_penalty | — (not specified) |

**Important notes:**
- **This model is non-thinking only.** It does not produce `<think></think>` blocks. Setting `enable_thinking=False` is not required.
- **Set min_p to 0.01.** Same as GLM — llama.cpp defaults to 0.05. The Unsloth guide recommends 0.01 for llama.cpp.
- **Do not use Q4 quantization for agentic coding.** Q4 degrades router precision in this 512-expert MoE model, causing 5x token waste from endless self-correction. Use UD-Q5_K_XL only.
- **KV cache must be q8_0.** Lower KV cache precision (q4_0) causes self-correction behavior. This is a server-side setting, not client-side, but important to be aware of.
- Qwen officially recommends these same parameters for all use cases. No separate coding vs. chat profiles.
- No special system prompt needed, but system prompts are supported.

**Server defaults (models.conf):** `--temp 1.0 --top-p 0.95 --top-k 40 --min-p 0.01` — matches official recommendation exactly. Clients should not need to override.

## Qwen3-Next-80B-A3B

Source: [Qwen model card "Best Practices"](https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct), [Unsloth GGUF](https://huggingface.co/unsloth/Qwen3-Next-80B-A3B-Instruct-GGUF)

| Setting | Recommended (all use cases) |
|---------|----------------------------|
| temperature | 0.7 |
| top_p | 0.8 |
| top_k | 20 |
| min_p | — (not specified) |
| repeat_penalty | — (not specified, use `presence_penalty` 0-2 if repetition occurs) |

**Important notes:**
- **This model is non-thinking only.** It does not produce `<think></think>` blocks. No `--reasoning-format` flag needed.
- **Architecture identical to Qwen3-Coder-Next** — same 80B-A3B MoE, same hybrid DeltaNet + Gated Attention, same 48 layers, same 512 experts (10 active + 1 shared). Different training focus: general-purpose vs coding.
- **Different samplers than Qwen3-Coder-Next.** The model card recommends lower temperature (0.7 vs 1.0) and different top_p/top_k. Follow the model card recommendations.
- **262K native context** with ultra-long context performance (tested up to 1M with YaRN). No system prompt needed for standard use.
- Same UD quant and KV cache considerations as Qwen3-Coder-Next apply.

**Server defaults (models.conf):** `--temp 0.7 --top-p 0.8 --top-k 20` — matches official recommendation. Clients should not need to override.

## Qwen3.5 Family (35B-A3B UD, 35B-A3B CL-Distill Q6/Q8, 27B, 122B-A10B)

Source: [Qwen3.5 model card "Best Practices"](https://huggingface.co/Qwen/Qwen3.5-35B-A3B), [Unsloth guide](https://docs.unsloth.ai/models/qwen3.5)

**All Qwen3.5 models share the same sampler recommendations.** Four profiles depending on mode and task:

| Setting | Thinking general | Thinking coding | Instruct general | Instruct reasoning |
|---------|-----------------|-----------------|------------------|--------------------|
| temperature | 1.0 | 0.6 | 0.7 | 1.0 |
| top_p | 0.95 | 0.95 | 0.8 | 1.0 |
| top_k | 20 | 20 | 20 | 40 |
| min_p | 0.0 | 0.0 | 0.0 | 0.0 |
| presence_penalty | 1.5 | 0.0 | 1.5 | 2.0 |
| repetition_penalty | 1.0 (disabled) | 1.0 (disabled) | 1.0 (disabled) | 1.0 (disabled) |

**Important notes:**
- **Qwen3.5 is a thinking model.** It generates `<think>...</think>` blocks by default. This is the recommended mode — thinking produces the best results.
- **No soft switch.** Unlike Qwen3, the `/think` and `/nothink` tags are NOT supported. Thinking mode is controlled via the chat template parameter `enable_thinking` (true/false). This is a hard switch per session/request, not per-message.
- **min_p must be 0.0.** The model card explicitly sets min_p=0.0 across all profiles. llama.cpp defaults to 0.05 — override with `--min-p 0` server-side.
- **presence_penalty=1.5 is strongly recommended** for general use to prevent repetition. This must be set client-side (it's an API parameter, not a standard llama-server CLI flag). Set it in the client's API request or system configuration.
- **For coding, use temp=0.6 with presence_penalty=0.0.** Anti-repetition hurts code generation where repeating patterns (loops, similar function signatures) is correct behavior.
- **Minimum context: 128K tokens** recommended by the model card to preserve thinking capabilities. Default and recommended: 262K.
- **Recommended output length:** 32,768 tokens for most queries, 81,920 for complex math/programming benchmarks.
- Same DeltaNet hybrid architecture as Qwen3-Next — `--no-context-shift` required.

**Server defaults (models.conf):** `--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0` — matches the "thinking general" profile. Clients used for coding should override to `temp 0.6` and set `presence_penalty 0.0`. For general use, set `presence_penalty 1.5` client-side.

## Mistral Small 4 119B UD-Q3_K_XL

Source: [Mistral Small 4 model card](https://huggingface.co/mistralai/Mistral-Small-4B-Instruct-2503), [Mistral API docs](https://docs.mistral.ai)

| Setting | All use cases |
|---------|--------------|
| temperature | 0.1 |
| top_p | 1.0 |
| top_k | — (not a Mistral API parameter) |
| min_p | 0.0 |
| presence_penalty | — (0.0 default, set client-side per request if needed) |

**Important notes:**
- **Mistral uses much lower temperature than other model families.** The model card uses `temperature=0.1` in every code example (instruction, tool calling, vision, reasoning). The Mistral API docs recommend adjusting either temperature or top_p, not both — with temp=0.1 already low, keep top_p at 1.0 (full vocabulary coverage).
- **top_k is not a Mistral API parameter.** Do not set it. llama.cpp's default (40) has no practical effect when top_p=1.0 and temp is very low.
- **min_p must be 0.0.** The Mistral API does not expose min_p — it is not part of their sampling pipeline. llama.cpp defaults to 0.05; override with `--min-p 0` server-side (already set in models.conf).
- **Reasoning mode is per-request, not a server flag.** Set `reasoning_effort` in the API request body: `"none"` for fast responses, `"high"` for deep reasoning with `[THINK]/[/THINK]` blocks. This is a client-side parameter — configure it in your client or API call.
- **Vision projector is available** (`mmproj-BF16.gguf`, 827 MB) but currently disabled — caused crash loop on startup. Do not enable without further investigation.
- **Prompt processing is slow** (~18.4 t/s) due to CPU expert offload over PCIe. Long-context performance degrades further — ~4.7 t/s observed at 13K+ token KV cache fill.
- **llama.cpp support:** PR #20649 merged. Requires `--jinja` for chat template. CUDA Flash Attention kernel for MLA (HKS=320, HVS=256) was not yet in the merged PR — may use a slower fallback attention path.
- Architecture: mistral4 (deepseek2-based with MLA attention). MLA compresses the KV cache — V cache = 0 MiB. NOT DeltaNet, so `--no-context-shift` is not needed.
- Multilingual: 11 languages. Apache 2.0 license.

**Server defaults (models.conf):** `--temp 0.1 --top-p 1.0 --min-p 0` — matches official model card defaults. Clients should not need to override sampling parameters.

## For benchmarks (EvalPlus)

Benchmarks use **greedy decoding** (`temperature=0`) sent by the evalplus client, which overrides all server-side sampler defaults. Server-side bench profiles intentionally omit sampler args for this reason. The only client-side benchmark config is in `benchmarks/evalplus/bench-client.conf` (GPT-OSS reasoning level).
