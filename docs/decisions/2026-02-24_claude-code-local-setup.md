# Decision: Claude Code Local Setup — 24 February 2026

**Decision: Option A + B combined (shell alias with separate HOME + bubblewrap sandbox)**

---

## Current State

### What has been built

A local llama-server (llama.cpp in Docker) is running with 6 MoE models, automatic
GPU placement via `--fit`, a monitoring dashboard with model switching, and a
management API on port 8081 for programmatic model switching.

Since build `ed4837891`, llama.cpp natively supports the **Anthropic Messages API**
(`POST /v1/messages`). This means Claude Code can talk to it directly without a
proxy or translation layer.

### What has been tested (Phase 1-3)

- Anthropic Messages API works (curl test with GLM Flash Q4)
- Token counting endpoint works (`/v1/messages/count_tokens`)
- Claude Code connected to local server: **chat and tool use work** (Glob, Read)
- Auth bypass: `ANTHROPIC_AUTH_TOKEN=llamacpp` + `ANTHROPIC_API_KEY=""`
- Launch script: `test/run.sh` with environment variables

### The problem

The current launch script (`test/run.sh`) uses `HOME=/path/to/test` to isolate the
local Claude Code session from the normal installation. This prevents credential
conflicts, but there is no restriction on filesystem access. Reading and writing
files *within* the project workspace (code, `.claude/agents/`, `AI_INSTRUCTIONS.md`)
is desired — that is where the model needs to work. Bash command execution should
also be possible, but controlled: Claude Code asks permission for each command by
default, and with a less capable local model it is important to review those prompts
more critically rather than accepting everything automatically.

The real risk is in the reach *outside* the workspace. A local model makes more
mistakes than Opus and can unintentionally navigate outside the project — opening
other projects, modifying files in the home folder, or executing system commands
that were not intended. A hard boundary is needed for this, not solely dependent on
user discipline when approving prompts.

### Current installation (normal Claude Code)

- Claude Code v2.1.52 via apt (Debian package), installed on Ubuntu Desktop
- Logged in via **OAuth** (Max subscription)
- Global config in `~/.claude/` (settings, credentials, CLAUDE.md)
- Per-project config in `.claude/` folders (agents, skills)
- No sandboxing active (standard permission prompts)

---

## Goal

### Two ways to use Claude Code, side by side

1. **Normal (OAuth/Max subscription)** — for serious work, access to Opus 4.6
   and other Anthropic models. This is and remains the primary method.
2. **Local (llama-server)** — experimental, for testing local models as a Claude
   Code backend. Occasional use.

### Why?

- The Max subscription is and remains the strongest: better models, prompt caching,
  adaptive reasoning — features that do not work locally.
- Running locally is interesting for experimentation: how far can local models go
  as a coding agent? What can they handle? Are there tasks they are good enough for?
- And it is simply interesting to see how far the available hardware can go.

### Requirements

- The normal OAuth installation must **never** be affected by the local setup.
- The local version must:
  - Work within a project workspace (read/write files within the project)
  - Retain VS Code IDE integration (diagnostics, etc.)
  - Execute bash commands (but always ask first, never automatically)
  - Not be able to use `sudo` or other privilege escalation
  - Not write outside the workspace
  - Reach localhost (for the llama-server API on port 8080)
  - Preferably also have internet access (web search, curl) but not strictly required

---

## Question 1: Can OAuth and local coexist in the same Claude Code instance?

### Short answer: No, not really.

Claude Code uses **one authentication method per session**:
- **OAuth** (subscription login) — the current method
- **API key** (`ANTHROPIC_API_KEY`) — for pay-per-use or third-party backends
- **Auth token** (`ANTHROPIC_AUTH_TOKEN`) — for local backends (Ollama-style)

These are mutually exclusive. It is not possible to have both OAuth and a local
backend active in the same session. The `/model` command within Claude Code can
switch between Anthropic models (Opus, Sonnet, Haiku), but not to a completely
different backend.

### What is possible

**Two separate sessions** can run, each with its own authentication and backend.
This is the approach already tested in Phase 3. The question is: how to do this
cleanly?

---

## Question 2: How to run two Claude Code instances side by side?

Three options were evaluated, each with a different isolation level.

### Option A: Environment variables via shell alias

**How it works:** An alias or wrapper script that starts Claude Code with environment
variables overriding the backend, plus a separate HOME path so that OAuth credentials
do not conflict.

```bash
# In ~/.bashrc or ~/.zshrc
alias claude-local='HOME=/home/rvanpolen/.claude-local \
  ANTHROPIC_BASE_URL=http://127.0.0.1:8080 \
  ANTHROPIC_AUTH_TOKEN=llamacpp \
  ANTHROPIC_API_KEY="" \
  ANTHROPIC_MODEL=glm-flash-q4 \
  ANTHROPIC_SMALL_FAST_MODEL=glm-flash-q4 \
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
  claude'
```

Or as a wrapper script (as already existed in `test/run.sh`):

```bash
#!/bin/bash
export HOME=/home/rvanpolen/.claude-local
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080
export ANTHROPIC_AUTH_TOKEN=llamacpp
# ... etc
exec claude --model glm-flash-q4
```

**Advantages:**
- Simplest solution, zero extra software needed
- `claude` for normal, `claude-local` for local
- The local session has its own HOME, so no conflict with OAuth credentials

**Disadvantages:**
- **No restriction outside the workspace.** There is no hard boundary on the
  filesystem — the local model can navigate outside the project, open other
  projects, or modify files in the home folder.
- No hard block on `sudo` (though it fails in practice because the password is
  required and Claude Code does not know it). Destructive commands that do not
  require root are still possible.
- Fully dependent on permission prompts ("may I execute this?"). These provide
  protection, but require every prompt to be critically reviewed — with a less
  capable model this is especially important.

**Suitable for:** Quick testing, with active supervision of every action. Not
suitable for longer or more autonomous tasks.

---

### Option B: Bubblewrap sandbox (Claude Code's built-in `/sandbox`)

**What is bubblewrap?** A lightweight Linux sandboxing tool (originally developed
for Flatpak). It creates isolated environments via Linux kernel namespaces, without
requiring root. It is a single binary, no daemon, and starts in milliseconds.

**How does it work in Claude Code?** Type `/sandbox` in a Claude Code session.
If `bubblewrap` and `socat` are installed, Claude Code switches to sandbox mode:

- **Filesystem:** Read and write only in the current working directory. The rest of
  the system is available read-only (system binaries, libraries) or blocked
  (sensitive directories).
- **Network:** All external traffic goes through a filtering proxy on the host. An
  allowlist can be configured. Localhost is always reachable (so the llama-server
  API on port 8080 works).
- **Sudo block:** `PR_SET_NO_NEW_PRIVS` is set — setuid binaries (sudo, su) cannot
  escalate privileges, even if available in the sandbox.
- **Performance:** Adds less than 15ms latency per command.

**Installation (one-time):**
```bash
sudo apt install bubblewrap socat
```

**Combined with Option A:**
```bash
#!/bin/bash
export HOME=/home/rvanpolen/.claude-local
export ANTHROPIC_BASE_URL=http://127.0.0.1:8080
export ANTHROPIC_AUTH_TOKEN=llamacpp
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL=glm-flash-q4
export ANTHROPIC_SMALL_FAST_MODEL=glm-flash-q4
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
cd /path/to/project
exec claude --model glm-flash-q4
# Then type /sandbox in the Claude Code session
```

**Advantages:**
- Real OS-level isolation: no writing outside the workspace, no sudo
- Localhost reachable (llama-server works)
- VS Code integration works (communicates via localhost, not filesystem)
- Lightweight: no Docker daemon, no images, millisecond startup
- Claude Code's own tooling — well integrated, reduces permission prompts by 84%
  (sandboxed commands are automatically allowed)
- Optional: internet access via the proxy allowlist (for web search, curl)

**Disadvantages:**
- `/sandbox` is a command that must be typed **in the session** — it is not
  automatic at startup. Forgetting is possible. (There may be a setting to enable
  it by default, but that needs to be investigated.)
- The sandbox applies to bash commands, not to Claude Code's own file operations
  (Read/Write/Edit tools). Those are handled separately via permissions. In
  practice this is fine because those prompts are visible.
- Linux-only (not a problem here, but worth noting).

**Suitable for:** Most scenarios. Good balance between safety and usability.

---

### Option C: Docker container

**How it works:** Claude Code runs in a Docker container with controlled volume
mounts. The project is mounted as a volume (read-write), the rest of the host
system is unreachable.

```yaml
# docker-compose.claude-local.yml
services:
  claude-local:
    build: ./claude-local-docker
    volumes:
      - /path/to/project:/workspace
    environment:
      - ANTHROPIC_BASE_URL=http://host.docker.internal:8080
      - ANTHROPIC_AUTH_TOKEN=llamacpp
    network_mode: host  # or a restricted network
    stdin_open: true
    tty: true
```

**Advantages:**
- Strongest isolation: the container only sees what is mounted
- Full control over what is available (no sudo, no host files)
- Reproducible: Dockerfile describes the exact environment
- No parent-directory traversal possible — the project in `/workspace` has no
  parent with `.claude/` or `AI_INSTRUCTIONS.md` (unless explicitly mounted)

**Disadvantages:**
- **VS Code integration becomes difficult.** Claude Code's IDE integration works
  via localhost MCP — if Claude Code runs in a container, that communication needs
  to be bridged. Not impossible, but adds complexity.
- **More overhead:** Docker daemon, image builds, ~300ms startup per container.
- **Interactive terminal in Docker** is less smooth than native.
- **Claude Code is not designed to run in Docker.** There is no official Docker
  image. It works, but the setup is entirely self-maintained.
- **Double Docker:** A llama-server is already running in Docker. Now Claude Code
  also in Docker. These need to communicate (network bridging).

**Suitable for:** Scenarios where maximum isolation is required and the extra
complexity is acceptable. Less practical for daily experimental use.

---

## Comparison Table

| | Option A: Alias | Option B: Bubblewrap | Option C: Docker |
|---|---|---|---|
| **Installation** | Nothing extra | `apt install bubblewrap socat` | Build Docker image |
| **Filesystem isolation** | None | Workspace r/w, rest r/o or blocked | Only mounted volumes |
| **Sudo block** | No (password-gated) | Yes (kernel-level) | Yes (no sudo in container) |
| **Reach outside workspace** | Unrestricted | Blocked (r/o or denied) | Blocked (not mounted) |
| **Network** | Fully open | Localhost + proxy allowlist | Configurable |
| **VS Code integration** | Works | Works | Difficult (bridging needed) |
| **llama-server reachable** | Yes | Yes (localhost) | Yes (host.docker.internal) |
| **Startup overhead** | None | <15ms | ~300ms + image |
| **Complexity** | Low | Low-medium | High |
| **Suitable for** | Quick testing | Daily experimental use | Maximum isolation |

---

## Decision: Option A + B Combined

### Step 1: Separate config (Option A)

A separate HOME path for local Claude Code (`~/.claude-local/`) with its own
settings.json. A wrapper script or alias to choose:

- `claude` — normal (OAuth, Anthropic, as-is)
- `claude-local` — local (llama-server, experimental)

This keeps credentials and configuration separated. The normal setup is never
touched.

### Step 2: Add sandbox (Option B)

Install bubblewrap + socat, and activate the sandbox in the local session. This
provides:

- No writing outside the workspace
- No sudo
- Localhost reachable (llama-server)
- VS Code integration intact
- Optional internet via proxy

### Result

```
claude          -> OAuth -> Anthropic -> Opus 4.6 (no sandbox, full freedom)
claude-local    -> API -> localhost:8080 -> llama-server -> GLM/Qwen/GPT-OSS
                   (sandbox: workspace-only writes, no sudo, localhost ok)
```

Two commands, two worlds, no interference.

---

## Open Questions

1. **Is a sandbox on normal Claude Code (OAuth) also desirable?** Possible, but
   there is no issue currently — Opus is reliable and prompts are reviewed. A
   sandbox would make it safer but also more restrictive.

2. **Which model as default for the local version?** GLM Flash Q4 is the fastest
   (~147 t/s). But switching is possible via the management API.

3. **Is internet needed in the local sandbox?** Web search and curl are useful, but
   not strictly needed for local experimentation. The proxy allowlist can make this
   configurable.

4. **Should the local version be usable in any project, or only in specific test
   workspaces?** This determines whether a fixed working directory is configured or
   whether it stays flexible.

---

## Next Steps

1. Install bubblewrap and socat
2. Set up `~/.claude-local/` with its own settings.json
3. Create wrapper script (`claude-local`)
4. Test: start local session, activate sandbox, verify basic functionality
5. Verify VS Code integration from the sandboxed session
6. Document in the project
