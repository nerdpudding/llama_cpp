# Architecture Overview

This document explains how the llama.cpp Docker wrapper project is structured,
how its components interact, and why certain design decisions were made. It follows
a simplified C4 model (Context, Containers, Components).

## Level 1 — Context

What the system is and what interacts with it.

```
                          ┌─────────────────────────────┐
                          │          User                │
                          │  (developer / experimenter)  │
                          └──────┬──────────┬────────────┘
                                 │          │
                    ┌────────────┘          └────────────┐
                    ▼                                    ▼
          ┌─────────────────┐                 ┌─────────────────┐
          │  claude (normal) │                 │  claude-local    │
          │  OAuth → Cloud   │                 │  → localhost     │
          └────────┬────────┘                 └────────┬────────┘
                   │                                   │
                   ▼                                   ▼
          ┌─────────────────┐                 ┌─────────────────┐
          │  Anthropic API   │                 │  llama-server    │
          │  (cloud)         │                 │  (local, Docker) │
          └─────────────────┘                 └─────────────────┘
```

**Two modes of operation:**
- `claude` — normal Claude Code with Anthropic subscription (OAuth, Opus, cloud)
- `claude-local` — experimental, connects to a local llama-server via the
  Anthropic Messages API (`/v1/messages`). Nothing leaves the machine.

These are completely independent. The local setup does not touch the normal
installation. Credential isolation is achieved via `CLAUDE_CONFIG_DIR`.

**External dependencies:**
- Docker (container runtime for llama-server)
- NVIDIA drivers + CUDA (GPU acceleration)
- GGUF model files (downloaded separately, stored in `models/`)
- Claude Code CLI (installed via native installer)
- bubblewrap + socat (sandbox for claude-local)
- VS Code (optional, IDE integration)

## Level 2 — Containers

The main runtime components and how they communicate.

```
┌──────────────────────────────────────────────────────────────────┐
│  Host Machine (Ubuntu, dual GPU: RTX 4090 + RTX 5070 Ti)        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  start.sh                                                  │  │
│  │  - Interactive model selector (menu)                       │  │
│  │  - Reads models.conf, generates .env                       │  │
│  │  - Starts Docker container + dashboard                     │  │
│  └──────┬─────────────────────────────────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌────────────────────┐     ┌──────────────────────────────┐    │
│  │  Docker Container   │     │  dashboard.py (curses TUI)   │    │
│  │                     │     │                              │    │
│  │  llama-server       │     │  - Server log streaming      │    │
│  │  - Anthropic API    │◄────│  - GPU monitoring (VRAM,     │    │
│  │    /v1/messages     │     │    utilization, temp, power) │    │
│  │  - OpenAI API       │     │  - Model picker (m key)      │    │
│  │    /v1/chat/...     │     │  - Management API :8081      │    │
│  │  - Health :8080     │     │    GET /models, /status      │    │
│  │                     │     │    POST /switch              │    │
│  │  Port 8080          │     │  Port 8081                   │    │
│  └────────────────────┘     └──────────────────────────────┘    │
│         ▲                            ▲                           │
│         │                            │                           │
│  ┌──────┴────────────────────────────┴───────────────────────┐  │
│  │  claude-local                                              │  │
│  │  - CLAUDE_CONFIG_DIR=~/.claude-local                       │  │
│  │  - ANTHROPIC_BASE_URL=http://127.0.0.1:8080                │  │
│  │  - Optional: bubblewrap sandbox (/sandbox)                 │  │
│  │  - Optional: VS Code IDE integration (/ide)                │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Communication paths

| From | To | Protocol | Port | Purpose |
|------|----|----------|------|---------|
| claude-local | llama-server | Anthropic Messages API | 8080 | Chat, tool use, thinking |
| claude-local | management API | HTTP REST | 8081 | Model switching (optional) |
| dashboard.py | Docker | Docker API | — | Container lifecycle, log streaming |
| dashboard.py | nvidia-smi | CLI | — | GPU monitoring |
| start.sh | Docker Compose | CLI | — | Container start/stop |
| start.sh | dashboard.py | Process spawn | — | Launches TUI after container health |
| External clients | llama-server | OpenAI / Anthropic API | 8080 | Any compatible client |

### Port summary

| Port | Service | Exposed to |
|------|---------|------------|
| 8080 | llama-server (inference API) | localhost |
| 8081 | Management API (dashboard.py) | localhost |

## Level 3 — Components

Key internal pieces and their responsibilities.

### Configuration

| File | Scope | What it controls |
|------|-------|-----------------|
| `models.conf` | Server | Model profiles: MODEL path, CTX_SIZE, FIT, EXTRA_ARGS. Each profile defines how llama-server starts. |
| `docker-compose.yml` | Server | Container config: GPU passthrough, port mapping, volume mounts, environment variables from `.env`. |
| `.env` | Server | Auto-generated from `models.conf` by `start.sh` or `dashboard.py`. Never edit manually. |
| `claude-local/bin/claude-local` | Client | Wrapper script: sets CLAUDE_CONFIG_DIR, API endpoint, auth bypass, model name. |
| `~/.claude-local/settings.json` | Client | Claude Code settings for the local instance (telemetry, timeouts, plans directory). |
| `~/.claude-local/CLAUDE.md` | Client | Global preferences for the local instance (writing style, communication rules, local model warning). |
| `.claude/settings.local.json` | Project | Auto-generated permission overrides (allow-listed bash commands). |
| `AI_INSTRUCTIONS.md` | Project | Project rules, hierarchy, agents, workflow — read first by any AI tool. |

### Scripts

| Script | Purpose |
|--------|---------|
| `start.sh` | Interactive model selector. Reads `models.conf`, presents menu, generates `.env`, starts Docker container, launches dashboard. |
| `dashboard.py` | Curses TUI: four panels (logs, GPU, system, controls). Hosts management API on port 8081. Handles model switching without leaving the TUI. |
| `claude-local/bin/claude-local` | Wrapper for Claude Code with local backend. Pre-flight health check, environment setup, launches `claude`. |
| `claude-local/install.sh` | Copies config files to `~/.claude-local/` and wrapper to `~/bin/`. Creates IDE symlink. |

### GPU strategy

The system uses `--fit` with `--n-gpu-layers auto` (FIT). FIT automatically
distributes model layers and MoE expert tensors across CUDA0 (RTX 4090, 24GB),
CUDA1 (RTX 5070 Ti, 16GB), and CPU RAM based on available VRAM. No manual layer
assignment is needed. See `docs/gpu-strategy-guide.md` for the full decision tree.

## Design Decisions

### Why a Docker wrapper (not a fork of llama.cpp)?

llama.cpp is updated frequently. A wrapper around the official build keeps the
upgrade path clean: pull new source, rebuild the Docker image, done. No merge
conflicts, no patch maintenance. The wrapper adds model profiles, GPU auto-placement,
monitoring, and a management API — none of which require changes to llama.cpp itself.

### Why CLAUDE_CONFIG_DIR (not HOME override)?

Initially the `claude-local` wrapper overrode `HOME` to `~/.claude-local/`.
This caused side effects: Claude Code looked for its own binary in the wrong
location, and CLAUDE.md was not read from the overridden HOME. `CLAUDE_CONFIG_DIR`
isolates only the Claude Code configuration directory without affecting anything
else.

### Why bubblewrap sandbox (not Docker for Claude Code)?

Docker would provide stronger isolation but breaks VS Code IDE integration (the
editor runs on the host, MCP communicates via localhost). Bubblewrap sandboxes
bash commands at the OS level while keeping localhost and VS Code accessible. The
trade-off: Claude Code's built-in tools (Write, Edit) are not sandboxed — only
bash commands are restricted. See `docs/decisions/2026-02-24_claude-code-local-setup.md`
for the full analysis.

### Why FIT auto (not manual -ot GPU placement)?

Manual GPU placement with `-ot` and hardcoded `N_GPU_LAYERS=99` prevented FIT
from working correctly (issue #19816). FIT auto handles MoE expert offload,
layer distribution, and VRAM fitting automatically — with better performance
and fewer graph splits. See `docs/gpu-strategy-guide.md` and
`docs/lessons_learned.md` for the history.

### Why separate instances (not a router)?

A proxy/router that routes some requests to Anthropic and others to local would
be more elegant, but adds complexity and a single point of failure. Two separate
commands (`claude` and `claude-local`) are simple, reliable, and make it obvious
which backend is being used. Automatic model switching within claude-local via
the management API is a planned future improvement.
