# Client Settings Reference

Quick reference for recommended client-side settings per model. Use these when configuring any client (web UI, API calls, agentic frameworks, IDE integrations).

**Why this matters:** The server (`models.conf`) sets default sampling parameters, but most clients override them. If your client sends `temperature=0.7` while the server default is `1.0`, the client wins. Always set these explicitly in your client to get the intended behavior.

## Model capabilities

| Model | Best for | Thinking | Tool calling | Speed |
|-------|----------|----------|-------------|-------|
| GLM-4.7 Flash | General tasks, reasoning, tool calling | Yes (`<think>` blocks) | Yes (native) | 112-147 t/s |
| GPT-OSS 120B | Deep reasoning, knowledge, structured output | Yes (configurable low/med/high) | Yes (native) | ~22 t/s |
| Qwen3-Coder-Next | Coding agents, agentic tasks | No | Yes (native) | ~33 t/s |
| Qwen3-Next-80B-A3B | General reasoning, knowledge, agentic, ultra-long context | No | Yes (native) | ~33 t/s |

## Sampler settings at a glance

| Setting | GLM (general) | GLM (coding/tools) | GPT-OSS (all) | Qwen3-Coder (all) | Qwen3-Next (all) |
|---------|--------------|-------------------|---------------|-------------------|------------------|
| temperature | 1.0 | 0.7 | 1.0 | 1.0 | 0.7 |
| top_p | 0.95 | 1.0 | 1.0 | 0.95 | 0.8 |
| top_k | — | — | 0 (disabled) | 40 | 20 |
| min_p | 0.01 | 0.01 | — | 0.01 | — |
| system prompt | — | — | "Reasoning: low/med/high" | — | — |

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

## For benchmarks (EvalPlus)

Benchmarks use **greedy decoding** (`temperature=0`) sent by the evalplus client, which overrides all server-side sampler defaults. Server-side bench profiles intentionally omit sampler args for this reason. The only client-side benchmark config is in `benchmarks/evalplus/bench-client.conf` (GPT-OSS reasoning level).
