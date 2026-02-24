# claude-local — Claude Code with local llama-server

Run Claude Code against a local llama-server instead of the Anthropic API. This is
an experimental setup for testing local models — the normal Anthropic subscription
(`claude`) is not affected.

## Structure

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

## Prerequisites

- **Claude Code CLI** (`claude`) installed
- **bubblewrap** and **socat** for sandboxing: `sudo apt install bubblewrap socat`
- **llama-server** running on `localhost:8080` (use `./start.sh` from the project root)

## Installation

**Option A: Run the install script**

```bash
cd claude-local
./install.sh
```

This copies `home/` contents to `~/.claude-local/` and `bin/claude-local` to
`~/bin/`. If `~/bin` is not in PATH, the script will tell you how to add it.

Re-run `install.sh` after updating files in the repo to sync changes.

**Option B: Manual setup**

```bash
# Copy config files
cp -r home/ ~/.claude-local/

# Copy wrapper script to somewhere in your PATH
cp bin/claude-local ~/bin/claude-local
chmod +x ~/bin/claude-local
```

Alternatively, create a symlink instead of copying:

```bash
ln -s "$(pwd)/home" ~/.claude-local
ln -s "$(pwd)/bin/claude-local" ~/bin/claude-local
```

## Usage

1. Start a model with `./start.sh` (from the project root)
2. Run `claude-local` from any project directory
3. Optionally activate `/sandbox` for filesystem restriction

The wrapper sets `HOME` to `~/.claude-local/` so the local instance has its own
config space, completely separate from the normal `~/.claude/` directory. No OAuth
credentials are touched.

## What the wrapper does

| Variable | Value | Why |
|----------|-------|-----|
| `HOME` | `~/.claude-local` | Credential isolation from normal Claude Code |
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:8080` | Point to local llama-server |
| `ANTHROPIC_AUTH_TOKEN` | `llamacpp` | Bypass OAuth (any non-empty string works) |
| `ANTHROPIC_API_KEY` | `""` | Prevent API key lookup |
| `ANTHROPIC_MODEL` | `glm-flash-q4` | Default model name |
| `ANTHROPIC_SMALL_FAST_MODEL` | `glm-flash-q4` | Used for background requests |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | No telemetry/update checks |

## Updating

After changing files in this directory (e.g., updating CLAUDE.md or settings.json),
re-run `./install.sh` or manually copy the changed files to `~/.claude-local/`.
