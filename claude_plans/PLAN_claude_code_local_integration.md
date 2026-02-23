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

**1a. Check llama.cpp version**
- Verify our local llama.cpp build includes the Anthropic Messages API (PR #17570)
- If not, update llama.cpp and rebuild the Docker image
- Test: `curl http://localhost:8080/v1/messages` should respond (even with error)

**~~1b. Add `--jinja` flag~~** — already present on all profiles, nothing to do.

**1b. Parallel slots** — start with `-np 1` (current config). Only increase if
Claude Code has issues with concurrent requests. No preemptive changes.

### Phase 2: Basic Connection Test

**2a. Start llama-server with a model**
- Use `./start.sh glm-flash-q4` (or whichever model)
- Verify the server is running on port 8080

**2b. Test Anthropic Messages API directly**
```bash
curl http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: local" \
  -d '{
    "model": "glm-flash-q4",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello, what model are you?"}]
  }'
```

**2c. Test token counting endpoint**
```bash
curl http://localhost:8080/v1/messages/count_tokens \
  -H "Content-Type: application/json" \
  -H "x-api-key: local" \
  -d '{
    "model": "glm-flash-q4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Phase 3: Connect Claude Code

**3a. Launch a separate Claude Code instance pointed at local server**
```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:8080 \
ANTHROPIC_AUTH_TOKEN=local \
ANTHROPIC_API_KEY="" \
ANTHROPIC_MODEL=glm-flash-q4 \
claude
```

Note: `ANTHROPIC_API_KEY=""` prevents Claude Code from trying to authenticate
with Anthropic. `ANTHROPIC_AUTH_TOKEN` can be anything.

**3b. Test basic functionality**
- Does it start without errors?
- Can it respond to simple questions?
- Does tool use work (file reading, bash commands)?
- What happens with the Haiku background calls?
- How fast/responsive is it?

**3c. Document what works and what doesn't**
- Keep notes on errors, limitations, and workarounds
- This is the experimental phase — we expect issues

### Phase 4: Convenience Setup (if Phase 3 works)

**4a. Create shell aliases/scripts for easy switching**
```bash
# ~/.bashrc or similar
alias claude-local='ANTHROPIC_BASE_URL=http://127.0.0.1:8080 ANTHROPIC_AUTH_TOKEN=local ANTHROPIC_API_KEY="" claude'
alias claude-api='claude'  # default, uses subscription
```

Or a wrapper script:
```bash
#!/bin/bash
# claude-local.sh — start Claude Code with local llama.cpp backend
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080
export ANTHROPIC_AUTH_TOKEN=local
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL="${1:-glm-flash-q4}"
exec claude
```

**4b. Consider dedicated models.conf profiles**
If needed (VRAM constraints with `-np 2`, or reduced context for Claude Code
overhead), create `cc-*` profiles in models.conf:
```ini
[cc-glm-flash-q4]
DESCRIPTION=GLM Flash Q4 — Claude Code profile
MODEL=models/GLM-4.7-Flash/...
CTX_SIZE=32768          # Reduced from 128K — Claude Code eats ~16K for system prompt
EXTRA_ARGS=--jinja -np 2
```

**4c. Integration with management API**
The management API on port 8081 already supports model switching (`POST /switch`).
A Claude Code instance connected to the local server could potentially trigger
model switches. This is future work — note it but don't implement yet.

### Phase 5: Documentation

- Update `todo_23_feb.md` with progress
- Document findings in `docs/` (what works, what doesn't, recommended setup)
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
