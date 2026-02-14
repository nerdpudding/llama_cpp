# Plan: tmux Dashboard for start.sh

## Context

After selecting a model, `start.sh` currently runs `exec docker compose up` which shows raw server logs until Ctrl+C. Problems:
- No GPU/system monitoring while the model runs
- Ctrl+C stops the container but doesn't `docker compose down` (can cause issues on next launch)
- No way to return to the menu without restarting the script

This plan adds a unified terminal dashboard using tmux. The user never touches tmux directly — `start.sh` creates one cohesive screen with custom-formatted sections showing exactly what's needed.

---

## What the user sees

```
┌─────────────────────────────────────────────────────────────┐
│ === Server Logs ===                                         │
│                                                             │
│ Starting llama-server with: --model /models/Qwen3-Coder... │
│ model loaded successfully                                   │
│ all slots are idle                                          │
│ request: POST /v1/chat/completions ...                      │
│ (live, scrollable with mouse)                     ~55%      │
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
│   Util: 65%  Power: 218W    │                    ~30%      │
│   Temp: 72°C                │                              │
├──────────────────────────────┴──────────────────────────────┤
│  Model: Qwen3-Coder-Next UD-Q6_K_XL (baseline)             │
│  API: http://localhost:8080    Web: http://localhost:8080    │
│                                                             │
│  [q] Stop & exit    [r] Stop & return to menu    [d] Detach │
│                                                      ~15%   │
└─────────────────────────────────────────────────────────────┘
```

Key points:
- **Not** raw nvidia-smi / htop — custom formatted with colors and progress bars
- Color-coded VRAM (green < 70%, yellow 70-90%, red > 90%)
- GPU/system panes refresh every 2 seconds
- Server logs are scrollable (mouse scroll via tmux)
- Three control keys: `q` (stop & exit), `r` (stop & return to menu), `d` (detach, keep running)

---

## Step 1: Install tmux (user action, document in README)

tmux is the only new dependency. It creates the multi-pane layout within a single terminal — the user never interacts with tmux commands directly.

Add to README.md Prerequisites section:
```
- **tmux** (`sudo apt install tmux`) — used by `start.sh` for the monitoring dashboard
```

The script checks for tmux and gives a clear install instruction if missing.

---

## Step 2: Restructure start.sh launch flow

Replace the current ending (`exec docker compose up`) with:

1. `docker compose up -d` (detached — container runs in background)
2. Poll `http://localhost:8080/health` with a spinner until the server is ready (timeout 5min for large models)
3. Build tmux session with 4 panes (layout above)
4. Attach to tmux session (blocks until user acts)
5. On `q`: kill tmux → `docker compose down` → exit
6. On `r`: kill tmux → `docker compose down` → loop back to menu
7. On `d`: detach from tmux → print reattach instructions → exit (container keeps running)

**Self-sourcing pattern for panes:** Each tmux pane calls `start.sh --internal-pane <pane-type>`. This keeps everything in one file. The `--internal-pane` flag is intercepted early in the script before anything else runs.

**Cleanup trap:** `trap cleanup EXIT HUP TERM INT` ensures `docker compose down` runs even if the terminal is closed. The trap is removed on detach (intentional — user wants the container to keep running).

**`--no-dashboard` flag:** Falls back to the old `exec docker compose up` behavior for debugging or if tmux is unavailable.

---

## Step 3: Implement pane functions in start.sh

All pane functions are added to the same `start.sh` file:

**`pane_server_logs`** — Runs `docker compose logs -f --tail=200`. tmux provides scrollback.

**`pane_gpu_monitor`** — Loops every 2s, queries `nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu,power.draw,power.limit,temperature.gpu --format=csv,noheader,nounits`. Formats with ANSI colors and progress bars. Falls back gracefully if nvidia-smi is missing.

**`pane_system_monitor`** — Loops every 2s, reads CPU usage from `/proc/stat` (1s sample), load from `/proc/loadavg`, memory from `free -m`, and container stats from `docker stats --no-stream`. All custom formatted.

**`pane_control`** — Shows model name, API/Web URLs, keybindings. Runs `read -rsn1` loop. Writes action (`stop`/`menu`) to a temp file, then kills the tmux session.

---

## Step 4: Add healthcheck to docker-compose.yml

```yaml
healthcheck:
  test: ["CMD", "curl", "-sf", "http://localhost:8080/health"]
  interval: 10s
  timeout: 5s
  retries: 60
  start_period: 120s
```

This requires `curl` in the container. Add to Dockerfile runtime stage (line 36):
```
curl \
```

The healthcheck is complementary — `start.sh` polls from the host regardless, but the healthcheck gives Docker proper container state awareness.

---

## Step 5: Update README.md

- Prerequisites: add tmux
- Quick Start: mention the dashboard appears after model selection
- Switching Models: document `q`/`r`/`d` keys and `--no-dashboard` flag
- Add a brief "Dashboard" section explaining the panes

---

## Step 6: Update docker-compose.example.yml header

Mention the dashboard behavior in the usage comments.

---

## Critical files

| File | Action |
|------|--------|
| `start.sh` | Major rewrite: add pane functions, tmux setup, main loop, cleanup trap, `--internal-pane` intercept, `--no-dashboard` flag |
| `docker-compose.yml` | Add healthcheck block |
| `Dockerfile` | Add `curl` to runtime stage |
| `README.md` | Add tmux prerequisite, document dashboard keys |
| `docker-compose.example.yml` | Update header comments |

---

## Verification

1. `./start.sh` → pick model → verify 4-pane dashboard appears after loading spinner
2. Press `q` → verify container stops (`docker ps` shows nothing), script exits
3. `./start.sh` → pick model → press `r` → verify menu reappears → pick different model → press `q`
4. `./start.sh` → press `d` → verify "Re-attach" message → `tmux attach -t llama` → dashboard still live → press `q`
5. `./start.sh --no-dashboard` → verify old raw log behavior
6. `./start.sh --list` → verify works without tmux check
7. Close terminal while dashboard is running → verify `docker ps` shows container stopped
8. GPU pane: verify VRAM percentages match `nvidia-smi` output
9. System pane: verify RAM matches `free -h` output
10. `./start.sh qwen3-coder` → verify CLI shortcut still works, dashboard appears
