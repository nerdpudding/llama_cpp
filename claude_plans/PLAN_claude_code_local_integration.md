# Plan: Claude Code ↔ Local llama.cpp Integration

## Goal

Enable Claude Code to use the local llama-server (llama.cpp) as an alternative
backend, so we can experiment with local models alongside the normal Anthropic
subscription/API. The user should be able to easily switch between:

1. **Anthropic subscription** (default, as-is today)
2. **Anthropic API** (pay-per-use, already works)
3. **Local llama.cpp** (experimental, new)

## Key Discovery: Native Anthropic Messages API in llama.cpp

llama.cpp now has **native Anthropic Messages API support** (PR #17570). This
means llama-server exposes:

- `POST /v1/messages` — chat completions with streaming (Anthropic format)
- `POST /v1/messages/count_tokens` — token counting

This eliminates the need for LiteLLM or other translation proxies. Claude Code
speaks Anthropic API → llama-server now speaks Anthropic API natively.

**Supported features:**
- Full Messages API with streaming
- Token counting
- Tool/function calling (requires `--jinja` flag)
- Vision (with multimodal models)
- Extended thinking (with reasoning models)
- Proper Anthropic SSE event types

## Known Issues & Risks

These are documented problems when running Claude Code against local backends:

### 1. Hardcoded Haiku calls
Claude Code sends background requests (title generation, tool filtering) to
`claude-haiku-4-5-20251001` regardless of your `--model` setting. The local
server only has one model loaded, so these requests either fail or get routed
to the loaded model anyway.

**Impact:** May cause errors or unexpected behavior.
**Mitigation:** The Anthropic Messages API in llama.cpp should handle any model
name and route to the loaded model. Need to verify this.

### 2. Concurrent requests
Claude Code fires multiple parallel requests (title, tool preflight, actual
prompt). A single-slot (`-np 1`) llama-server can only handle one request at a
time — others queue up.

**Approach:** Start with `-np 1` (current config) and see if it works. If Claude
Code hangs or crashes, try `-np 2`. Extra slots only cost additional KV-cache
VRAM (model weights are shared). With FIT auto, if the extra KV-cache doesn't
fit on GPU it spills to CPU RAM — slower but functional. Worst case it OOMs at
startup (immediately visible, no silent failure).

### 3. Large system prompt
Claude Code injects a ~16K token system prompt defining its behavior. This is
non-negotiable — it's how Claude Code works. This means:
- Context usage starts high before the user says anything
- Smaller context sizes may run out quickly
- Our models with 128K-262K context should handle this fine

### 4. Model capability gaps
Local models won't match Claude Opus 4.6 for complex agentic coding. This is
expected — the goal is experimentation, not replacement. Some Claude Code
features (adaptive reasoning, prompt caching) won't work locally.

### 5. ~~`--jinja` flag required~~ (already done)
Tool calling (which Claude Code uses heavily) requires the `--jinja` flag on
llama-server. **All our profiles already have `--jinja` in EXTRA_ARGS.** No
change needed.

## Implementation Plan

### Phase 1: Verify & Prepare

**1a. Check llama.cpp version** ✓
- Build `ed4837891` includes Anthropic Messages API
- Routes confirmed in `server.cpp:181-182`: `POST /v1/messages` and `POST /v1/messages/count_tokens`
- No rebuild needed

**~~1b. Add `--jinja` flag~~** — already present on all profiles, nothing to do.

**1b. Parallel slots** — start with `-np 1` (current config). Only increase if
Claude Code has issues with concurrent requests. No preemptive changes.

### Phase 2: Basic Connection Test

**2a. Start llama-server with a model**
- Use `./start.sh glm-flash-q4` (or whichever model)
- Verify the server is running on port 8080

**2b. Test Anthropic Messages API directly** ✓
- Tested with GLM Flash Q4. Returns valid Anthropic format response.
- Thinking blocks included (GLM is a reasoning model).
- Model name in response: `GLM-4.7-Flash-Q4_K_M.gguf`

**2c. Test token counting endpoint** ✓
- Returns `{"input_tokens": 11}` for a simple message. Works.

### Phase 3: Connect Claude Code

**3a. Launch a separate Claude Code instance pointed at local server** ✓

Launch script (`test/run.sh`):
```bash
#!/bin/bash
export HOME=/home/rvanpolen/vibe_claude_kilo_cli_exp/llama_cpp/test
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080
export ANTHROPIC_AUTH_TOKEN=llamacpp
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL=glm-flash-q4
export ANTHROPIC_SMALL_FAST_MODEL=glm-flash-q4
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
exec claude --model glm-flash-q4
```

Key details:
- `ANTHROPIC_AUTH_TOKEN=llamacpp` — bypasses OAuth login (Ollama-style approach)
- `ANTHROPIC_API_KEY=""` — empty, so Claude Code doesn't try Anthropic auth
- `HOME=test/` — sandboxed to avoid OAuth conflict with main Claude Code session
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` — keeps it fully local
- `ANTHROPIC_SMALL_FAST_MODEL` — routes background tasks to same local model

**3b. Test results** ✓
- Chat: works (responds in Dutch when prompted in Dutch)
- Tool use: works (Glob search, Read files)
- Auth: no conflict when sandboxed with separate HOME
- Bash commands: not yet tested
- `-np 1`: no issues observed so far (single slot)
- **BLOCKER: Isolation insufficient.** HOME override does not fully sandbox
  Claude Code — it traverses parent directories and picks up project-level
  config (AI_INSTRUCTIONS.md, .claude/). A local model is less capable than
  Opus and more likely to make mistakes. Uncontrolled access to project files
  and config is too risky.

**Cleanup done:** test artifacts removed, global and project config verified intact.

### Phase 4: Proper Sandboxing (TODO — replaces old Phase 4)

Before the local Claude Code instance can be used for real work, proper
isolation is needed. Options to investigate:

1. **Claude Code `/sandbox` command** — built-in OS-level sandboxing using
   bubblewrap (Linux). Restricts filesystem writes to working directory only,
   network to approved hosts only. Requires `bubblewrap` + `socat` packages.
2. **Docker sandboxing** — run Claude Code itself inside a Docker container
   with controlled volume mounts. Full isolation from host filesystem.
3. **Combination** — Docker for hard isolation + `/sandbox` inside.

Requirements for any solution:
- Cannot write outside a designated work directory
- Cannot access or modify project config (.claude/, AI_INSTRUCTIONS.md, etc.)
- Can reach localhost:8080 (llama-server API) but nothing else
- Cannot interfere with the main Claude Code session (OAuth, settings)

### Phase 5: Convenience Setup (after sandboxing is solved)

Deferred — wrapper scripts and aliases only make sense once sandboxing works.

### Phase 6: Documentation

- Document the working setup and sandboxing approach
- Update ROADMAP.md to reflect progress on API integration

## What We're NOT Doing (yet)

- **Replacing Anthropic subscription** — this is experimental, not a replacement
- **Claude Code Router / middleware proxy** — try direct connection first, add
  complexity only if needed
- **Multi-model routing** — e.g. "use local for simple, Claude for complex" —
  future work
- **Continue.dev / aider / OpenClaw integration** — separate future tasks
- **Automated switching** — e.g. agent decides which backend to use — future

## Decisions Made

1. **Test model:** GLM Flash Q4 first (fastest, most VRAM headroom).
2. **Parallel slots:** Start with `-np 1` (current config). Increase only if needed.
3. **Profiles:** Use existing profiles as-is. Separate cc-* profiles only if needed.

## Files Changed

| File | Change |
|------|--------|
| `models.conf` | Possibly add cc-* profiles (only if needed) |
| `claude-local.sh` (new) | Convenience script for launching Claude Code locally |
| `docs/claude-code-integration.md` (new) | Setup guide and findings |
| `ROADMAP.md` | Update API integration status |
| `todo_23_feb.md` | Add tasks |

## Sources

- [Anthropic Messages API in llama.cpp](https://huggingface.co/blog/ggml-org/anthropic-messages-api-in-llamacpp) — native support, no proxy needed
- [Why Claude Code Fails with Local LLM Inference](https://explore.n1n.ai/blog/why-claude-code-fails-local-llm-inference-2026-02-19) — known issues (Haiku calls, token counting, concurrency)
- [Offline Agentic coding with llama-server](https://github.com/ggml-org/llama.cpp/discussions/14758) — practical setup with `--jinja`, parallel slots
- [Claude Code LLM Gateway docs](https://code.claude.com/docs/en/llm-gateway) — official gateway configuration
- [Using Claude Code with Ollama](https://www.datacamp.com/tutorial/using-claude-code-with-ollama-local-models) — similar setup with Ollama
- [Unsloth: Local LLMs with Claude Code](https://unsloth.ai/docs/basics/claude-code) — environment variable reference
