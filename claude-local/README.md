# claude-local — Claude Code with local llama-server

Run Claude Code against a local llama-server instead of the Anthropic API. This is
an experimental setup for testing local models — the normal Anthropic subscription
(`claude`) is not affected.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [First Launch (Onboarding)](#first-launch-onboarding)
- [Recommended Configuration](#recommended-configuration)
- [Usage](#usage)
- [Sandbox (Security)](#sandbox-security)
- [Important: What the Sandbox Does NOT Protect](#important-what-the-sandbox-does-not-protect)
- [How the Wrapper Works](#how-the-wrapper-works)
- [File Structure](#file-structure)
- [Known Issues](#known-issues)
- [Updating](#updating)

## Prerequisites

Before installing, make sure the following are available:

1. **Claude Code CLI** (`claude`) — install via the native installer (Ubuntu/Debian):
   ```bash
   curl -fsSL https://claude.ai/install.sh | sh
   ```
   After installation, run `claude` once to complete the OAuth login with an
   Anthropic subscription (Max or Teams). This sets up the normal `~/.claude/`
   directory. The local instance does not use these credentials but Claude Code
   itself needs to be installed first.
2. **bubblewrap** and **socat** — required for sandboxing:
   ```bash
   sudo apt install bubblewrap socat
   ```
3. **`~/bin` in PATH** — if not already set up:
   ```bash
   echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```
4. **A local inference server** with Anthropic Messages API support on
   `localhost:8080`. This setup assumes the llama.cpp Docker wrapper from this
   repository (start a model with `./start.sh`), but any server that exposes a
   compatible `/v1/messages` endpoint should work (e.g. Ollama with an Anthropic
   API adapter). The server must be running before starting `claude-local`.

## Installation

Run the install script:

```bash
cd claude-local
./install.sh
```

The script does the following:

| Step | What | Where | Why |
|------|------|-------|-----|
| 1 | Checks prerequisites | — | Verifies `claude`, `bwrap`, and `socat` are installed |
| 2 | Copies `home/CLAUDE.md` | `~/.claude-local/CLAUDE.md` | Global preferences for the local instance (writing style, communication rules, local model warning) |
| 3 | Copies `home/settings.json` | `~/.claude-local/settings.json` | Claude Code settings (telemetry off, timeouts, plans directory) |
| 4 | Copies `home/skills/project-setup/SKILL.md` | `~/.claude-local/skills/project-setup/SKILL.md` | `/project-setup` skill adapted for local paths |
| 5 | Creates IDE symlink | `~/.claude-local/ide/ → ~/.claude/ide/` | VS Code extension writes lock files to `~/.claude/ide/` (hardcoded). Without this symlink, VS Code integration breaks. See [issue #4739](https://github.com/anthropics/claude-code/issues/4739). |
| 6 | Copies `bin/claude-local` | `~/bin/claude-local` | Wrapper script — needs to be in PATH so `claude-local` works as a command from any directory |

### Why these files need to be copied

The wrapper sets `CLAUDE_CONFIG_DIR=~/.claude-local` so Claude Code reads its config
from there instead of `~/.claude/`. This keeps the local instance completely separate
from the normal Anthropic installation — no OAuth credentials are touched, no settings
are shared.

### Manual installation (alternative)

```bash
# Copy config files
mkdir -p ~/.claude-local/skills/project-setup
cp home/CLAUDE.md ~/.claude-local/CLAUDE.md
cp home/settings.json ~/.claude-local/settings.json
cp home/skills/project-setup/SKILL.md ~/.claude-local/skills/project-setup/SKILL.md

# Create IDE symlink for VS Code integration
mkdir -p ~/.claude/ide
ln -s ~/.claude/ide ~/.claude-local/ide

# Copy wrapper script to ~/bin (or another directory in PATH)
mkdir -p ~/bin
cp bin/claude-local ~/bin/claude-local
chmod +x ~/bin/claude-local
```

Or use symlinks instead of copies if preferred (changes in the repo then apply
immediately without re-running install):

```bash
ln -s "$(pwd)/home" ~/.claude-local
ln -s ~/.claude/ide ~/.claude-local/ide
mkdir -p ~/bin
ln -s "$(pwd)/bin/claude-local" ~/bin/claude-local
```

## First Launch (Onboarding)

The first time `claude-local` starts, Claude Code runs its onboarding wizard because
`~/.claude-local/` is a fresh config directory. This is normal and only happens once.

1. **Theme selection** — choose dark mode or another theme
2. **Diagnostic warnings** — a warning about `config install method is 'unknown'` may
   appear. This is cosmetic and has no effect on functionality. Ignore it.
3. **Ready** — after onboarding, the session is fully functional

## Recommended Configuration

After the first launch, open `/config` and adjust these settings:

| Setting | Recommended | Why |
|---------|-------------|-----|
| **Verbose output** | `true` | Shows thinking blocks and token usage — useful for seeing what the local model is doing |
| **Thinking mode** | `true` | Enables thinking/reasoning blocks (should already be on via settings.json) |
| **Auto-update channel** | `disabled` | Already disabled via `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` |

These settings are stored in `~/.claude-local/` and persist across sessions.

## Usage

1. **Start a model** — run `./start.sh` from the project root and pick a model
2. **Start claude-local** — from any project directory:
   ```bash
   claude-local
   ```
3. **Enable sandbox** — type `/sandbox` in the session and choose option 2
   ("Sandbox BashTool, with regular permissions")
4. **Work** — chat, read files, write code, use tools

The model name shown in the interface is `local-llama` regardless of which model
is actually loaded in llama-server. llama-server routes all requests to whatever
model is running — the name is only a label.

### VS Code integration

For VS Code integration (diffs shown in editor instead of terminal), start
`claude-local` from a **VS Code integrated terminal**. Then run `/ide` and select
Visual Studio Code.

## Sandbox (Security)

The sandbox (`/sandbox`) uses bubblewrap to restrict what **bash commands** can do.
Enable it after starting a session — especially important with local models that
are less capable than Claude Opus and may misinterpret instructions.

**How to enable:** Type `/sandbox` → select "Sandbox BashTool, with regular
permissions" → bash commands now run inside a bubblewrap container.

**Persistent:** The sandbox setting is saved — once enabled, it stays on for all
future sessions. It does not need to be re-enabled each time.

### What the sandbox protects

| Action | Result |
|--------|--------|
| Bash: write files outside project workspace | **Blocked** |
| Bash: `sudo` commands | **Blocked** |
| Bash: network access (curl, wget, etc.) | **Blocked** |
| Bash: commands within project workspace | **Allowed** (with permission prompt) |
| Claude Code → llama-server API communication | **Works** (not routed through bash) |
| VS Code IDE integration | **Works** |

## Important: What the Sandbox Does NOT Protect

**The sandbox only wraps bash commands.** Claude Code's built-in tools (Read, Write,
Edit, Glob) are **not sandboxed** — they can read and write files anywhere on the
system, including outside the project workspace.

This means:
- If the model decides to use the **Write tool** to write to `/tmp/test.txt` or
  `~/some-other-project/file.py`, the sandbox will **not block it**
- If the model uses **bash** `echo > /tmp/test.txt`, the sandbox **will block it**

**How to stay safe:**
- Always review what the model wants to do before approving
- Pay extra attention to Write/Edit tool actions — check the file path
- Local models are less capable than Opus and may misunderstand instructions
- When in doubt, deny the action and rephrase the instruction
- Use `/sandbox` mode 2 (regular permissions) so every bash command requires
  explicit approval

This is a limitation of Claude Code's sandbox design, not specific to the local
setup. The same applies to the normal `claude` command.

## How the Wrapper Works

The `claude-local` script sets environment variables and runs `claude`:

| Variable | Value | Why |
|----------|-------|-----|
| `CLAUDE_CONFIG_DIR` | `~/.claude-local` | Config isolation — reads settings, CLAUDE.md, and skills from here instead of `~/.claude/` |
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:8080` | Point to local llama-server |
| `ANTHROPIC_AUTH_TOKEN` | `llamacpp` | Bypass OAuth (any non-empty string works) |
| `ANTHROPIC_API_KEY` | `""` | Prevent API key lookup |
| `ANTHROPIC_MODEL` | `local-llama` | Generic model name (llama-server routes to whatever is loaded) |
| `ANTHROPIC_SMALL_FAST_MODEL` | `local-llama` | Used for background requests (same model) |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | No telemetry/update checks |

## File Structure

```
claude-local/
├── README.md              # This file
├── install.sh             # Copies files to ~/.claude-local/ and ~/bin/
├── bin/
│   └── claude-local       # Wrapper script (→ ~/bin/claude-local)
└── home/                  # Config files (→ ~/.claude-local/)
    ├── CLAUDE.md           # Global preferences for the local instance
    ├── settings.json       # Claude Code settings (telemetry, timeouts, etc.)
    └── skills/
        └── project-setup/
            └── SKILL.md    # /project-setup skill adapted for local instance
```

## Known Issues and Behavior

- **`CLAUDE_CONFIG_DIR` is not officially documented** by Anthropic. It works in
  practice but could change in future Claude Code versions.
- **VS Code IDE detection** requires the `ide/` symlink workaround (handled by the
  install script). See [issue #4739](https://github.com/anthropics/claude-code/issues/4739).
- **`config install method is 'unknown'` warning** appears in `/status` diagnostics.
  This is cosmetic — Claude Code does not find install metadata in the custom config
  directory. No effect on functionality.
- **Write/Edit tools not sandboxed** — Claude Code's built-in file tools bypass the
  bubblewrap sandbox. See the [security section](#important-what-the-sandbox-does-not-protect).
- **Sandbox is persistent** — once enabled via `/sandbox`, it stays on for all future
  sessions (stored in `~/.claude-local/`). This is desirable as a default, but be
  aware of the following consequences:
  - **Temporary stub files** appear in the working directory during a session (e.g.
    `.bashrc`, `.gitconfig`, `HEAD`, `.mcp.json`, `.vscode`, etc.) — these are
    read-only, 0-byte files created by bubblewrap as part of the sandboxed
    environment. They are automatically cleaned up when the session ends.
  - **`/project-setup` Phase 0 will not work** with sandbox active, because it tries
    to read/write files in `~/.claude-local/` which is outside the workspace. Disable
    sandbox first (`/sandbox` → "No Sandbox"), run the skill, then re-enable sandbox.
- **`/resume` may not work** — resuming a previous session has been observed to fail
  with a serialization error (`The "string" argument must be of type string...`).
  Not yet clear if this is caused by `CLAUDE_CONFIG_DIR`, running two Claude Code
  instances simultaneously, or the test-project being inside an existing repo.
  Needs further testing in an isolated setup.
- **Local model limitations with skills** — complex multi-step skills (like
  `/project-setup`) may produce errors or unexpected behavior with local models.
  Common issues include: Write tool parameter type errors, difficulty reading certain
  directories, and incorrect agent creation. These are model capability limitations,
  not configuration problems. Review each action carefully before approving.

## Updating

After changing files in this directory (e.g., updating CLAUDE.md or settings.json),
re-run `./install.sh` or manually copy the changed files to `~/.claude-local/`.
