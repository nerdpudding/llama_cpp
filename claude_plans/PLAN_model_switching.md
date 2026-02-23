# Plan: Model Switching from Dashboard

## Problem

Currently, switching models requires exiting the dashboard (press `r`), which
stops the container, returns to the start.sh menu, selects a new model, restarts
the container, waits for health, and relaunches the dashboard. This is clunky —
the entire TUI disappears and reappears. The goal is Ollama-level simplicity:
press a key, pick a model, watch it load, use it.

## Current Architecture

```
start.sh
  ├── parse models.conf
  ├── show menu → user picks model
  ├── generate .env from selected profile
  ├── docker compose up -d
  ├── wait for /health
  └── launch dashboard.py (blocks)
        ├── _collect_logs thread (docker compose logs -f)
        ├── _collect_data thread (nvidia-smi, /proc/*, docker stats)
        └── _ui_main curses loop (q=exit, r=return to menu)
```

Key coupling points:
1. **start.sh owns the lifecycle** — it starts the container, launches the
   dashboard, and stops the container when the dashboard exits
2. **dashboard.py is passive** — it only monitors, it cannot control the
   container or change the model
3. **.env is generated once** by start.sh before `docker compose up` — there's
   no mechanism to regenerate it while the dashboard runs
4. **Log collection** uses `docker compose logs -f` — if the container restarts,
   the log stream may break or miss output

## Why not use llama-server's `/models/load` and `/models/unload`?

Each model has a unique server configuration in models.conf: different `-ot`
regex, context size, GPU layers, batch sizes, and flags. These are llama-server
**startup parameters**, not runtime-changeable settings. The `/models/load`
endpoint can swap the model file, but it cannot change `-ot`, `--ctx-size`,
`--n-gpu-layers`, or other flags.

**Conclusion:** model switching requires a container restart. This is not a
limitation we can work around — it's fundamental to how llama-server works.

## Approach: Dashboard-Driven Model Switching

Move the model switching logic into the dashboard. The dashboard stays running,
manages the container lifecycle, and shows loading progress.

### User experience

```
[Dashboard running with GLM Flash Q4 at 140 t/s]

User presses 'm'  →  Model picker overlay appears
                      (same models as start.sh menu)

User picks "2"    →  Dashboard shows "Switching to Qwen3-Coder-Next..."
                      Container stops (old logs stay visible)
                      .env regenerated for new profile
                      Container starts
                      Dashboard shows loading progress from logs
                      Health check passes → "Ready: Qwen3-Coder-Next UD-Q5_K_XL"

[Dashboard continues with new model, GPU stats update, new logs stream]
```

### Implementation Steps

#### Step 1: Give dashboard.py access to models.conf

The dashboard needs to know about available models and their configs.

- Add `--models-conf` argument to dashboard.py
- Reuse or port the INI parser from start.sh (simple, no dependencies)
- Store parsed profiles in the Dashboard class

#### Step 2: Add model picker overlay to dashboard

When user presses `m`:
- Draw a model list overlay on top of the current dashboard
- Show production models by number (1-N), bench profiles under `b` submenu
- Same info as start.sh: name, speed, context
- Number keys select a model, `Esc` cancels
- Keep the dashboard rendering underneath (GPU stats, system stats keep updating)
- Works the same whether a model is currently running or not — if nothing is
  running, it starts the selected model; if something is running, it switches

#### Step 3: Implement model switch in dashboard

When a model is selected from the picker:

1. Show status: "Stopping current model..."
2. Run `docker compose down` (subprocess, non-blocking to UI thread)
3. Regenerate `.env` from the selected profile (same logic as start.sh's
   `generate_env`)
4. Show status: "Starting {model name}..."
5. Run `docker compose up -d`
6. Reconnect log stream (restart `_collect_logs` thread)
7. Show status: "Loading model..." (with progress from logs if available)
8. Poll `/health` endpoint
9. Show status: "Ready: {model name}" → resume normal dashboard

Update `self.model_name` so the control bar shows the new model.

#### Step 4: Make log collection resilient to container restarts

Current `_collect_logs` runs `docker compose logs -f` once. If the container
restarts, the subprocess may exit or lose output.

- When a model switch happens, terminate the old log process
- Optionally: add a separator line "--- Switching to {model} ---"
- Start a new `docker compose logs -f` for the new container
- Keep old logs in the buffer (user can scroll back to see previous model's logs)

#### Step 5: Update start.sh to pass models.conf path

Add `--models-conf "$CONF"` to the dashboard launch command in start.sh.
No other changes to start.sh needed — it still handles initial startup.

#### Step 6: Add model switch API endpoint

A small HTTP server running alongside the dashboard on a separate port (e.g.
8081). This enables Claude Code agents, skills, and other tools to switch
models programmatically.

Endpoints:
- `GET  /models` — list available profiles (id, name, speed, status)
- `GET  /status` — current model, health, uptime
- `POST /switch` — switch to a profile: `{"model": "qwen3-coder-ud-q5"}`

Implementation:
- stdlib `http.server` in a daemon thread — no dependencies
- Calls the same `switch_model(profile_id)` method as the `m` key
- Returns JSON responses (easy for scripts and agents to parse)
- Switch response blocks until the new model is healthy (with timeout)

This is ~40 lines of code on top of the switch logic we already build in Step 3.

### Key Design Decisions

1. **Container restart, not hot-swap** — per-model GPU configs require it
2. **Dashboard stays running** — only the container restarts, the TUI persists
3. **Log buffer persists** — old model logs remain scrollable
4. **models.conf is the single source of truth** — dashboard reads the same
   config as start.sh, no duplication
5. **switch_model() is a method, not inline code** — used by both `m` key and API endpoint

### Files Changed

| File | Change |
|------|--------|
| `dashboard.py` | Add models.conf parser, model picker overlay, switch_model() method, resilient log collection, API endpoint |
| `start.sh` | Pass `--models-conf` to dashboard.py |

### Testing

**Dashboard switching:**
1. Start with `./start.sh` → pick any model → dashboard appears
2. Press `m` → model picker shows production models + bench submenu
3. Pick a different model → watch the switch happen in the dashboard
4. Verify: correct model loads (check logs), GPU placement matches profile
   (check nvidia-smi), speed is as expected (send test prompt)
5. Press `m` again → switch back → verify again
6. Press `Esc` in picker → cancels, returns to dashboard
7. Edge case: press `m` while model is still loading from a previous switch
8. Start dashboard with no model running → press `m` → pick model → starts

**API switching:**
9. `curl localhost:8081/models` → lists all profiles with current status
10. `curl localhost:8081/status` → shows current model info
11. `curl -X POST localhost:8081/switch -d '{"model":"glm-flash-q4"}'` → switches
12. Verify same model loads correctly as when switching via dashboard

### Not In Scope

- Claude Code agent/skill that uses the API to switch models (future session,
  but the API built here will be the foundation for it)
- Multiple concurrent models (VRAM doesn't allow it)
