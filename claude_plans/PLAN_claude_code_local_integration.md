# Plan: Claude Code + Local llama.cpp Integration

## Goal

Enable Claude Code to use the local llama-server (llama.cpp) as an alternative
backend for experimentation with local models. The normal Anthropic subscription
remains the primary setup and must not be affected. The result is two separate
commands:

- `claude` — normal (OAuth, Anthropic, Opus 4.6)
- `claude-local` — experimental (local llama-server, sandboxed)

**Decision document:** `docs/decisions/2026-02-24_claude-code-local-setup.md`

## Key Discovery: Native Anthropic Messages API in llama.cpp

llama.cpp has **native Anthropic Messages API support** (PR #17570). llama-server
exposes:

- `POST /v1/messages` — chat completions with streaming (Anthropic format)
- `POST /v1/messages/count_tokens` — token counting

No proxy or translation layer needed. Claude Code speaks Anthropic API, llama-server
now speaks Anthropic API natively.

**Supported features:**
- Full Messages API with streaming
- Token counting
- Tool/function calling (requires `--jinja` flag — already on all profiles)
- Vision (with multimodal models)
- Extended thinking (with reasoning models)
- Proper Anthropic SSE event types

## Known Issues & Risks

### 1. Hardcoded Haiku calls
Claude Code sends background requests (title generation, tool filtering) to
`claude-haiku-4-5-20251001` regardless of the `--model` setting. The local server
only has one model loaded, so these requests get routed to whatever is loaded.

**Mitigation:** `ANTHROPIC_SMALL_FAST_MODEL` is set to the same local model. The
Anthropic Messages API in llama.cpp handles any model name and routes to the loaded
model. Tested and working.

### 2. Concurrent requests
Claude Code fires multiple parallel requests (title, tool preflight, actual prompt).
A single-slot (`-np 1`) llama-server handles one at a time — others queue up.

**Status:** Tested with `-np 1`, no issues observed so far. If problems arise,
`-np 2` can be tried (extra KV-cache VRAM, shared model weights).

### 3. Large system prompt
Claude Code injects a ~16K token system prompt. Context usage starts high before
any user input. The available models with 128K-262K context handle this without
issues.

### 4. Model capability gaps
Local models do not match Opus for complex agentic coding. This is expected — the
goal is experimentation, not replacement. Some Claude Code features (adaptive
reasoning, prompt caching) do not work locally.

## Implementation Plan

### Phase 1: Verify & Prepare --- DONE

- Build `ed4837891` includes Anthropic Messages API
- Routes confirmed in `server.cpp:181-182`
- `--jinja` already on all profiles
- Parallel slots: `-np 1` sufficient so far

### Phase 2: Basic Connection Test --- DONE

- Anthropic Messages API tested with curl on GLM Flash Q4
- Returns valid Anthropic format (with thinking blocks for reasoning models)
- Token counting returns `{"input_tokens": N}`

### Phase 3: Connect Claude Code --- DONE

- Chat works (responds in Dutch when prompted in Dutch)
- Tool use works (Glob, Read)
- Auth bypass: `ANTHROPIC_AUTH_TOKEN=llamacpp` + `ANTHROPIC_API_KEY=""`
- No credential conflict when using separate HOME
- Launch script: `test/run.sh`

### Phase 4: Dual-Instance Setup + Sandboxing --- CURRENT

The decision is **Option A + B combined**: separate HOME for credential isolation,
plus bubblewrap sandbox for filesystem/privilege restriction.

**Why two layers:**
- **Option A (separate HOME)** solves credential conflict — the local instance gets
  its own `~/.claude-local/` with a separate settings.json, so the OAuth credentials
  in `~/.claude/` are never touched.
- **Option B (bubblewrap sandbox)** solves filesystem restriction — the local
  instance can only write within the project workspace, cannot use sudo (blocked at
  kernel level via `PR_SET_NO_NEW_PRIVS`), and has localhost access for the
  llama-server API.

Neither layer alone is sufficient: Option A alone leaves the filesystem wide open,
Option B alone does not separate credentials.

#### Step 4.1: Install bubblewrap and socat

```bash
sudo apt install bubblewrap socat
```

**Why:** Bubblewrap provides OS-level sandboxing via Linux kernel namespaces.
Socat bridges network sockets into the sandbox (used by Claude Code's `/sandbox`
for proxy-based network filtering). Both are required for Claude Code's built-in
`/sandbox` command to work.

**Who:** User action (requires sudo).

#### Step 4.2: Create local Claude Code home directory

Create `~/.claude-local/` with a minimal `settings.json`:

```json
{
  "$schema": "https://json-schema.org/claude-code-settings.json",
  "permissions": {
    "defaultMode": "plan"
  }
}
```

**Why:** This gives the local instance its own configuration space, separate from
`~/.claude/`. The `plan` default mode ensures all actions require approval — extra
important with less capable local models. No CLAUDE.md is needed here (the
project-level config is sufficient, and global preferences do not apply to the
experimental instance).

**Who:** Can be done together (Claude Code creates the directory and file).

#### Step 4.3: Create `claude-local` wrapper script

Replace `test/run.sh` with a proper wrapper script (location TBD — either project
root or `~/bin/`):

```bash
#!/bin/bash
# Claude Code with local llama-server backend
# Requires: llama-server running on localhost:8080
#           bubblewrap + socat installed (for /sandbox)

export HOME="$HOME/.claude-local"
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080
export ANTHROPIC_AUTH_TOKEN=llamacpp
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL=glm-flash-q4
export ANTHROPIC_SMALL_FAST_MODEL=glm-flash-q4
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# Pass through any arguments (e.g. --model qwen3-coder-ud-q5)
exec claude "$@"
```

**Why:** A single entry point that sets all required environment variables. The
script uses `exec` so it replaces the shell process (clean PID, proper signal
handling). Arguments are passed through so `--model` and other flags still work.

**Who:** Can be done together (Claude Code creates the script).

**Note:** The HOME path is constructed from the original HOME before overriding it,
so it resolves to `/home/rvanpolen/.claude-local` regardless of where the script
is run from.

#### Step 4.4: Test basic functionality

Start the local session and verify:

1. The session starts without OAuth login prompts
2. It connects to the local llama-server
3. Chat works (simple question/answer)
4. Tool use works (Glob, Read, Write within workspace)
5. No credential conflict with the normal Claude Code installation

**Who:** User action — start the session, run manual tests, verify behavior.

#### Step 4.5: Activate and test sandbox

In the local Claude Code session, type `/sandbox`. Then verify:

1. **Workspace access:** Can read and write files within the project directory
2. **Outside workspace:** Cannot write to `~/`, other project directories, or
   system paths
3. **Sudo:** Blocked at kernel level (PR_SET_NO_NEW_PRIVS prevents setuid
   escalation even though the password requirement already stops it in practice)
4. **Localhost:** llama-server API on port 8080 is reachable from the sandbox
5. **VS Code IDE:** Diagnostics and other IDE features work (MCP communicates
   via localhost, which remains available in the sandbox)
6. **Permission prompts:** Bash commands still require explicit approval (the
   sandbox auto-allows sandboxed commands, but un-sandboxable commands fall back
   to prompts)

**Who:** User action — activate sandbox, run manual tests, verify each point.

**Open question:** Is there a way to auto-enable `/sandbox` at startup (via
settings.json or environment variable)? If so, the wrapper script should include it.
If not, it needs to be typed manually each session. This needs to be investigated.

### Phase 5: Convenience and Polish

#### Step 5.1: Finalize wrapper script

Based on Phase 4 test results, finalize the wrapper script:
- Add model selection support (e.g. `claude-local --model qwen3-coder-ud-q5`)
- Add a pre-flight check: is llama-server running? If not, show a helpful message.
- Decide on script location (`~/bin/`, project root, or symlink)

#### Step 5.2: Verify management API integration

Test that the management API model switching (`POST /switch` on port 8081) works
from within a local Claude Code session. This allows switching the active model
without restarting the Claude Code session.

#### Step 5.3: Document recommended workflow

Write a short guide: when to use `claude` vs `claude-local`, what to expect from
local models, how to switch models, and safety considerations.

### Phase 6: Documentation

#### Step 6.1: Architecture document (`docs/architecture.md`)

Create a high-level architecture document (C4-style) that explains how all parts
of the project fit together. This is the "big picture" document that answers: what
is this, how does it work, why is it designed this way?

**Level 1 — Context:** What the system is and what it connects to.
- The wrapper project, the user, llama.cpp, Docker, Claude Code, Anthropic API,
  VS Code, local models (GGUF files)

**Level 2 — Containers:** The main runtime components and how they communicate.
- Docker container (llama-server) on port 8080
- Dashboard (curses TUI) + management API on port 8081
- `start.sh` (model selector, .env generator, orchestrator)
- Claude Code — normal (OAuth → Anthropic) vs local (`claude-local` → localhost)
- Bubblewrap sandbox (what it restricts, what it allows)

**Level 3 — Components:** Key internal pieces.
- `models.conf` (model profiles, GPU placement, sampler defaults)
- `dashboard.py` (log streaming, GPU monitoring, model picker, management API)
- Wrapper scripts (`start.sh`, `claude-local`)
- Per-project config (`.claude/agents/`, `AI_INSTRUCTIONS.md`)

Include simple ASCII or text-based diagrams showing the data flow:
- User → `start.sh` → Docker → llama-server → API (port 8080)
- User → `claude` → Anthropic API (cloud)
- User → `claude-local` → sandbox → llama-server API (localhost:8080)
- Dashboard → Docker logs + nvidia-smi + management API

**Why this matters:** The project has grown from a simple Docker wrapper to
something with multiple entry points, two Claude Code modes, a management API,
sandboxing, and model switching. Without an architecture overview, it is hard for
anyone (including a future version of this AI) to understand how the pieces connect.
It is also the right place to explain why certain choices were made (wrapper vs
forking llama.cpp, FIT auto vs manual GPU placement, bubblewrap vs Docker
sandboxing, etc.).

#### Step 6.2: README structure for user-facing documentation

The README currently has a Quick Start section focused on `start.sh`. With the
Claude Code local integration, the README needs a clearer structure that guides
different types of readers. Proposed structure:

```
README.md
├── What is this? (intro — already exists, may need minor update)
├── Hardware (already exists)
├── Quick Start
│   ├── 1. Requirements (what needs to be installed before anything works)
│   ├── 2. Build & Install (clone, download models, docker compose build)
│   ├── 3. Run a Model (start.sh, dashboard, web UI, API)
│   └── 4. Use with Claude Code (claude-local — what it is, how to set up,
│          what it can do, safety/sandbox, link to detailed guide)
├── Models (already exists)
├── Benchmarks (already exists)
├── Adding New Models (already exists)
├── Configuration (already exists)
├── Architecture (link to docs/architecture.md)
├── Documentation (links to all docs/ files)
├── Repository Structure (already exists)
└── Updating llama.cpp (already exists)
```

The "Use with Claude Code" section in Quick Start should be concise (install
bubblewrap, run `claude-local`, activate sandbox — done). For the full explanation
(why it works this way, what the sandbox does, limitations, model switching, etc.)
link to a detailed guide in `docs/`.

**Not now:** The README rewrite does not need to happen in this sprint. But the
structure should be kept in mind so that Phase 4-5 work produces content that fits
into this layout without needing a full rewrite later.

#### Step 6.3: Update project documentation

- Update ROADMAP.md with completion status
- Update README "What's next" section
- Run doc-keeper agent for consistency check

#### Step 6.4: Archive

- Move this plan to `archive/` with date prefix when complete
- Archive `todo_24_feb.md` when done

## What is NOT in Scope

- **Replacing the Anthropic subscription** — this is experimental, not a replacement
- **Claude Code Router / middleware proxy** — direct connection works, no proxy needed
- **Multi-model routing** (e.g. "use local for simple, Claude for complex") — future
- **Continue.dev / aider / OpenClaw integration** — separate future tasks
- **Automated backend switching** (agent decides which backend) — future

## Decisions Made

1. **Sandboxing approach:** Option A + B combined (separate HOME + bubblewrap)
2. **Test model:** GLM Flash Q4 (fastest, ~147 t/s, most VRAM headroom)
3. **Parallel slots:** `-np 1` (current config), increase only if needed
4. **Profiles:** Use existing profiles as-is, no separate cc-* profiles needed

## Sources

- [Anthropic Messages API in llama.cpp](https://huggingface.co/blog/ggml-org/anthropic-messages-api-in-llamacpp)
- [Why Claude Code Fails with Local LLM Inference](https://explore.n1n.ai/blog/why-claude-code-fails-local-llm-inference-2026-02-19)
- [Offline Agentic coding with llama-server](https://github.com/ggml-org/llama.cpp/discussions/14758)
- [Claude Code LLM Gateway docs](https://code.claude.com/docs/en/llm-gateway)
- [Claude Code Sandboxing docs](https://code.claude.com/docs/en/sandboxing)
- [Anthropic Engineering: Making Claude Code More Secure](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [Sandbox Runtime (GitHub)](https://github.com/anthropic-experimental/sandbox-runtime)
