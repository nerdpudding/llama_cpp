# Plan: Python curses Dashboard for start.sh

## Context

After selecting a model, `start.sh` currently runs `exec docker compose up` which shows raw server logs until Ctrl+C. Problems:
- No GPU/system monitoring while the model runs
- Ctrl+C stops the container but doesn't `docker compose down` (can cause issues on next launch)
- No way to return to the menu without restarting the script

## Why Python curses instead of tmux

The first attempt used tmux to create a multi-pane layout. This failed because:

- **Quoting hell:** tmux runs pane commands via `sh -c`, creating a bash → tmux → sh → bash chain. Passing arguments (especially model names with spaces and parentheses) through this chain requires multiple escaping layers that are fragile and hard to debug.
- **Pane coordination:** Each tmux pane is a separate process. Communicating actions (quit/menu/detach) between panes requires temp files and IPC — fragile.
- **Layout control:** tmux pane splits are percentage-based with counter-intuitive numbering after splits. Getting a full-width control bar below side-by-side panels requires a specific split order that's easy to get wrong.
- **Extra dependency:** Requires the user to install tmux.

Python with `curses` (stdlib) solves all of these:

| Problem | tmux | Python curses |
|---------|------|---------------|
| Argument passing | Multi-layer shell escaping | Regular function arguments |
| Process coordination | Temp files between processes | Single process, shared state |
| Layout control | Fragile split percentages | Direct pixel-level window control |
| Terminal rendering | Limited to tmux's pane model | Full control: colors, bars, Unicode |
| Dependencies | tmux (apt install) | Python 3 (already on every Ubuntu) |
| Error handling | Silent failures, falls back to shell | Exceptions, traceback, clean error messages |
| Keyboard input | tmux key tables + pane focus | Direct `getch()` in the main loop |

The dashboard is a single Python script (`dashboard.py`) that `start.sh` calls after starting the container. One process, one file, full control.

---

## What the user sees

Same layout as the original plan — nothing changes from the user's perspective:

```
┌─────────────────────────────────────────────────────────────┐
│ === Server Logs ===                                         │
│                                                             │
│ Starting llama-server with: --model /models/Qwen3-Coder... │
│ model loaded successfully                                   │
│ all slots are idle                                          │
│ request: POST /v1/chat/completions ...                      │
│ (live, scrollable)                                  ~55%    │
├──────────────────────────────┬──────────────────────────────┤
│ === GPU Monitor ===          │ === System ===               │
│                              │                              │
│ GPU 0: NVIDIA RTX 4090      │   CPU:  34%                  │
│   VRAM: 22140/24564 MiB     │   Load: 4.21 2.15 1.82      │
│   ████████████████████░ 90%  │                              │
│   Util: 78%  Power: 312W    │   RAM:  31204/64234 MiB      │
│   Temp: 67°C                │   ██████████░░░░░░░░░░ 49%   │
│                              │   Swap: 0/8192 MiB           │
│ GPU 1: NVIDIA RTX 5070 Ti   │                              │
│   VRAM: 14200/16303 MiB     │ Container:                   │
│   ██████████████████░░ 87%  │   CPU: 245%  MEM: 5.2 GiB   │
│   Util: 65%  Power: 218W    │                              │
│   Temp: 72°C                │                              │
├──────────────────────────────┴──────────────────────────────┤
│  Model: Qwen3-Coder-Next UD-Q6_K_XL (baseline)             │
│  API: http://localhost:8080    Web: http://localhost:8080    │
│                                                             │
│  [q] Stop & exit    [r] Stop & return to menu               │
└─────────────────────────────────────────────────────────────┘
```

Key points:
- Color-coded VRAM bars (green < 70%, yellow 70-90%, red > 90%)
- GPU/system stats refresh every 2 seconds
- Server logs stream live, with scrollback buffer
- `q` stops the container and exits, `r` stops and returns to the menu
- Terminal resize is handled automatically (`curses.KEY_RESIZE`)

---

## Step 1: Create `dashboard.py`

A single Python file using only stdlib modules (`curses`, `subprocess`, `threading`, `time`, `signal`, `json`, `os`). No pip installs.

### Architecture

```
Main thread (curses)
├── Draws all 4 panels each tick (~500ms)
├── Handles keyboard input (non-blocking getch)
└── Manages terminal resize events

Log collector thread
├── Runs: docker compose logs -f --tail=200
├── Reads stdout line by line
└── Appends to a shared deque (last ~500 lines)

Data collector thread (every 2s)
├── GPU: nvidia-smi --query-gpu=... --format=csv
├── CPU: reads /proc/stat (1s delta)
├── RAM/Swap: reads /proc/meminfo
└── Container: docker stats --no-stream
```

Three threads, one shared data structure, no temp files, no IPC.

### Panel rendering

Each panel is a curses `window` (or `subwin`) positioned absolutely based on terminal dimensions:

- **Logs panel** (top, 55% height): Ring buffer of log lines. Scroll position tracked. Up/Down/PgUp/PgDn to scroll. Auto-follows when at bottom.
- **GPU panel** (middle-left, 35% height, 50% width): Formatted nvidia-smi output with colored progress bars using curses color pairs.
- **System panel** (middle-right, 35% height, 50% width): CPU, load, RAM, swap, container stats.
- **Control bar** (bottom, ~10% height): Model name, URLs, keybindings. Static content.

### Keyboard handling

`curses.halfdelay(5)` makes `getch()` return after 500ms if no key is pressed — this drives the render loop without busy-waiting.

| Key | Action |
|-----|--------|
| `q` | Set exit flag → cleanup → return exit code 0 to start.sh |
| `r` | Set exit flag → cleanup → return exit code 2 to start.sh |
| `Up/Down/PgUp/PgDn` | Scroll server logs |
| `Home/End` | Jump to top/bottom of logs |

### Signal handling

`SIGINT`, `SIGTERM`, `SIGHUP` → clean exit (same as pressing `q`).

### Arguments

```bash
python3 dashboard.py \
    --compose-file /path/to/docker-compose.yml \
    --model-name "Qwen3-Coder-Next UD-Q6_K_XL (baseline)"
```

Clean argument passing — no shell escaping needed.

---

## Step 2: Modify start.sh launch flow

Replace `exec docker compose up` with:

1. `docker compose up -d` (detached)
2. Health poll with spinner (same as before, stays in bash)
3. `python3 "$SCRIPT_DIR/dashboard.py" --compose-file ... --model-name ...`
4. Check exit code: 0 = stop & exit, 2 = stop & return to menu
5. `docker compose down` (always, unless container already stopped)

Add a main loop so `r` returns to the model menu.

Add `--no-dashboard` flag that falls back to `exec docker compose up`.

Add cleanup trap for `docker compose down` on unexpected exit.

---

## Step 3: Update README.md

- Prerequisites: add Python 3 (mention it's already on Ubuntu)
- Quick Start: mention dashboard appears after model selection
- Switching Models: document `q`/`r` keys and `--no-dashboard` flag

---

## Step 4: Update docker-compose.example.yml header

Mention the dashboard in usage comments.

---

## Critical files

| File | Action |
|------|--------|
| `dashboard.py` | **New file**: Python curses TUI (~300-400 lines) |
| `start.sh` | Moderate changes: detached launch, health poll, call dashboard.py, main loop, cleanup trap |
| `README.md` | Update Quick Start and Switching Models sections |
| `docker-compose.example.yml` | Update header comments |
| `docker-compose.yml` | Already done (healthcheck) |
| `Dockerfile` | Already done (curl) |

---

## Verification

1. `./start.sh` → pick model → verify dashboard appears with all 4 panels
2. Press `q` → verify container stops, script exits
3. `./start.sh` → pick model → press `r` → verify menu reappears → pick different model → press `q`
4. `./start.sh --no-dashboard` → verify old raw log behavior
5. `./start.sh --list` → verify still works
6. Resize terminal while dashboard is running → verify layout adapts
7. Close terminal while dashboard is running → verify `docker ps` shows container stopped
8. GPU panel: verify VRAM percentages match `nvidia-smi` output
9. System panel: verify RAM matches `free -h` output
10. Scroll logs with arrow keys and PgUp/PgDn
