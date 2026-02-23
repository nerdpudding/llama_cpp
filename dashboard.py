#!/usr/bin/env python3
"""Terminal monitoring dashboard for llama.cpp Docker wrapper.

Single-process curses TUI with GPU monitoring, system stats, server logs,
model switching, and a management API. Uses only Python stdlib.

Called by start.sh after starting the container:
    python3 dashboard.py --compose-file docker-compose.yml \
        --model-name "Model Name" --models-conf models.conf \
        --current-profile glm-flash-q4

Keyboard controls:
    q = stop container & exit
    r = stop container & return to start.sh menu
    m = model picker (switch models)
    Up/Down/PgUp/PgDn = scroll logs

Management API (port 8081):
    GET  /models  — list available model profiles
    GET  /status  — current model and server state
    POST /switch  — switch model: {"model": "profile-id"}

Exit codes:
    0 = stop & exit
    2 = stop & return to menu
"""

import argparse
import curses
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

MIN_WIDTH = 60
MIN_HEIGHT = 20
LOG_BUFFER_SIZE = 2000
API_PORT = 8081

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

# Color pair IDs
C_HEADER = 1
C_GREEN = 2
C_YELLOW = 3
C_RED = 4
C_BLUE = 5
C_DIM = 6


def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    return ANSI_RE.sub('', text)


def ctx_label(ctx):
    """Format context size for display."""
    if ctx >= 1024:
        return f"{ctx // 1024}K ctx"
    return f"{ctx} ctx"


# =============================================================================
# models.conf parser
# =============================================================================

class ModelProfile:
    """A model profile parsed from models.conf."""
    __slots__ = ('id', 'name', 'description', 'speed', 'model', 'ctx_size',
                 'n_gpu_layers', 'fit', 'fit_target', 'extra_args', 'is_bench')

    def __init__(self, profile_id):
        self.id = profile_id
        self.name = ""
        self.description = ""
        self.speed = ""
        self.model = ""
        self.ctx_size = ""
        self.n_gpu_layers = ""
        self.fit = ""
        self.fit_target = ""
        self.extra_args = ""
        self.is_bench = profile_id.startswith("bench-")


def parse_models_conf(path):
    """Parse models.conf and return list of ModelProfile."""
    profiles = []
    current = None

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Section header
            m = re.match(r'^\[([a-zA-Z0-9_-]+)\]$', line)
            if m:
                current = ModelProfile(m.group(1))
                profiles.append(current)
                continue

            # Key=Value
            if current and '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                if key == 'NAME':
                    current.name = value
                elif key == 'DESCRIPTION':
                    current.description = value
                elif key == 'SPEED':
                    current.speed = value
                elif key == 'MODEL':
                    current.model = value
                elif key == 'CTX_SIZE':
                    current.ctx_size = value
                elif key == 'N_GPU_LAYERS':
                    current.n_gpu_layers = value
                elif key == 'FIT':
                    current.fit = value
                elif key == 'FIT_TARGET':
                    current.fit_target = value
                elif key == 'EXTRA_ARGS':
                    current.extra_args = value

    return profiles


# =============================================================================
# Management API
# =============================================================================

class APIHandler(BaseHTTPRequestHandler):
    """HTTP handler for the management API."""
    # Reference to the Dashboard instance, set before server starts
    dashboard = None

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/models':
            self._handle_models()
        elif self.path == '/status':
            self._handle_status()
        else:
            self._send_json({'error': 'not found'}, 404)

    def do_POST(self):
        if self.path == '/switch':
            self._handle_switch()
        else:
            self._send_json({'error': 'not found'}, 404)

    def _handle_models(self):
        db = self.dashboard
        models = []
        for p in db.profiles:
            models.append({
                'id': p.id,
                'name': p.name,
                'speed': p.speed,
                'ctx_size': p.ctx_size,
                'is_bench': p.is_bench,
                'active': p.id == db.current_profile_id,
            })
        self._send_json({'models': models})

    def _handle_status(self):
        db = self.dashboard
        self._send_json({
            'model': db.current_profile_id or None,
            'model_name': db.model_name,
            'state': db.server_state,
            'status': db.status_message,
        })

    def _handle_switch(self):
        db = self.dashboard
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except (json.JSONDecodeError, ValueError):
            self._send_json({'error': 'invalid JSON'}, 400)
            return

        profile_id = body.get('model', '')
        if not profile_id:
            self._send_json({'error': 'missing "model" field'}, 400)
            return

        # Find profile
        profile = None
        for p in db.profiles:
            if p.id == profile_id:
                profile = p
                break
        if not profile:
            self._send_json({'error': f'unknown model: {profile_id}'}, 404)
            return

        # Start switch
        done_event = threading.Event()
        success = db.switch_model(profile_id, done_event=done_event)
        if not success:
            self._send_json({
                'error': 'switch already in progress',
                'state': db.server_state,
            }, 409)
            return

        # Wait for completion (with timeout)
        done_event.wait(timeout=300)
        self._send_json({
            'success': db.server_state == 'running',
            'model': db.current_profile_id,
            'model_name': db.model_name,
            'state': db.server_state,
        })


# =============================================================================
# Dashboard
# =============================================================================

class Dashboard:
    def __init__(self, compose_file, model_name, models_conf=None,
                 current_profile=None):
        self.compose_file = compose_file
        self.model_name = model_name
        self.exit_code = 0
        self.running = True

        # Project paths (derived from compose file location)
        self.project_dir = os.path.dirname(os.path.abspath(compose_file))
        self.env_file = os.path.join(self.project_dir, '.env')
        self.models_dir = os.path.join(self.project_dir, 'models')

        # Model profiles
        self.profiles = []
        self.prod_profiles = []
        self.bench_profiles = []
        self.current_profile_id = current_profile

        if models_conf and os.path.exists(models_conf):
            self.profiles = parse_models_conf(models_conf)
            self.prod_profiles = [p for p in self.profiles if not p.is_bench]
            self.bench_profiles = [p for p in self.profiles if p.is_bench]

        # Server state: idle, starting, running, stopping
        self.server_state = "running" if model_name else "idle"
        self.status_message = ""
        self._switch_lock = threading.Lock()

        # Picker state
        self.show_picker = False
        self.picker_page = "main"  # "main" or "bench"
        self.picker_sel = 0  # highlighted index in current picker list

        # Shared data (protected by lock)
        self.lock = threading.Lock()
        self.log_lines = deque(maxlen=LOG_BUFFER_SIZE)
        self.gpu_data = []
        self.cpu_percent = 0
        self.load_avg = ""
        self.mem_total = 0
        self.mem_used = 0
        self.swap_total = 0
        self.swap_used = 0
        self.container_cpu = ""
        self.container_mem = ""

        # Log scroll state
        self.auto_follow = True
        self.scroll_pos = 0

        # CPU delta tracking
        self._prev_cpu = None

        # Subprocess handle for log streaming
        self._log_proc = None

    def run(self):
        """Start threads and curses UI. Returns exit code."""
        log_t = threading.Thread(target=self._collect_logs, daemon=True)
        data_t = threading.Thread(target=self._collect_data, daemon=True)
        log_t.start()
        data_t.start()

        # Start API server if models are configured
        if self.profiles:
            api_t = threading.Thread(target=self._run_api_server, daemon=True)
            api_t.start()

        try:
            curses.wrapper(self._ui_main)
        except KeyboardInterrupt:
            self.exit_code = 0
        finally:
            self.running = False
            self._stop_log_collection()

        return self.exit_code

    # ── API Server ────────────────────────────────────────────────────────

    def _run_api_server(self):
        """Run management API HTTP server in background thread."""
        APIHandler.dashboard = self
        try:
            server = HTTPServer(('127.0.0.1', API_PORT), APIHandler)
            server.timeout = 1
            while self.running:
                server.handle_request()
        except OSError:
            with self.lock:
                self.log_lines.append(
                    f"(management API failed to start on port {API_PORT})")

    # ── Model Switching ───────────────────────────────────────────────────

    def switch_model(self, profile_id, done_event=None):
        """Switch to a different model profile. Thread-safe.

        Returns True if switch was initiated, False if already switching.
        If done_event is provided, it will be set when the switch completes.
        """
        if not self._switch_lock.acquire(blocking=False):
            return False

        t = threading.Thread(
            target=self._do_switch,
            args=(profile_id, done_event),
            daemon=True
        )
        t.start()
        return True

    def _do_switch(self, profile_id, done_event=None):
        """Perform the actual model switch. Runs in a background thread."""
        try:
            profile = None
            for p in self.profiles:
                if p.id == profile_id:
                    profile = p
                    break
            if not profile:
                self.status_message = f"Unknown profile: {profile_id}"
                return

            # Check model file exists
            if profile.model:
                model_path = os.path.join(self.models_dir, profile.model)
                # For multi-part models, check the first file
                if not os.path.exists(model_path):
                    self.status_message = f"Model not found: {profile.model}"
                    self.server_state = "idle"
                    return

            # Stop current container (if running)
            if self.server_state in ("running", "starting"):
                self.server_state = "stopping"
                self.status_message = "Stopping current model..."
                self._stop_log_collection()

                with self.lock:
                    self.log_lines.append(
                        f"--- Switching to {profile.name} ---")

                subprocess.run(
                    ["docker", "compose", "-f", self.compose_file, "down"],
                    capture_output=True, timeout=60
                )

            # Generate new .env
            self._generate_env(profile)

            # Start new container
            self.server_state = "starting"
            self.model_name = profile.name
            self.current_profile_id = profile.id
            self.status_message = f"Starting {profile.name}..."

            subprocess.run(
                ["docker", "compose", "-f", self.compose_file, "up", "-d"],
                capture_output=True, timeout=60
            )

            # Restart log collection
            self._start_log_collection()

            # Wait for health
            self.status_message = f"Loading {profile.name}..."
            healthy = self._wait_for_health(timeout=300)

            if healthy:
                self.server_state = "running"
                self.status_message = ""
            else:
                self.server_state = "idle"
                self.status_message = "Server failed to become healthy"

        except subprocess.TimeoutExpired:
            self.server_state = "idle"
            self.status_message = "Timeout during switch"
        except Exception as e:
            self.server_state = "idle"
            self.status_message = f"Switch failed: {e}"
        finally:
            self._switch_lock.release()
            if done_event:
                done_event.set()

    def _generate_env(self, profile):
        """Generate .env file for a model profile."""
        with open(self.env_file, 'w') as f:
            f.write(f"# Generated by dashboard.py — {profile.name}\n")
            f.write(f"# Section: [{profile.id}] from models.conf\n\n")
            if profile.model:
                f.write(f"MODEL={profile.model}\n")
            if profile.ctx_size:
                f.write(f"CTX_SIZE={profile.ctx_size}\n")
            if profile.n_gpu_layers:
                f.write(f"N_GPU_LAYERS={profile.n_gpu_layers}\n")
            if profile.fit:
                f.write(f"FIT={profile.fit}\n")
            if profile.fit_target:
                f.write(f"FIT_TARGET={profile.fit_target}\n")
            if profile.extra_args:
                f.write(f"EXTRA_ARGS={profile.extra_args}\n")

    def _wait_for_health(self, timeout=300):
        """Poll /health endpoint until server is ready."""
        url = "http://localhost:8080/health"
        elapsed = 0
        while elapsed < timeout and self.running:
            try:
                req = urllib.request.urlopen(url, timeout=3)
                if req.status == 200:
                    return True
            except Exception:
                pass
            time.sleep(2)
            elapsed += 2
        return False

    def _stop_log_collection(self):
        """Terminate the current log collection process."""
        if self._log_proc:
            try:
                self._log_proc.terminate()
                self._log_proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self._log_proc.kill()
                except OSError:
                    pass
            self._log_proc = None

    def _start_log_collection(self):
        """Start a new log collection thread."""
        self._stop_log_collection()
        t = threading.Thread(target=self._collect_logs, daemon=True)
        t.start()

    # ── Curses UI ──────────────────────────────────────────────────────────

    def _ui_main(self, stdscr):
        curses.curs_set(0)
        curses.use_default_colors()
        self._init_colors()
        stdscr.timeout(500)

        while self.running:
            height, width = stdscr.getmaxyx()

            key = self._get_key(stdscr)
            if key is not None:
                if self.show_picker:
                    self._handle_picker_key(key)
                elif not self._handle_key(key, height):
                    break

            if height < MIN_HEIGHT or width < MIN_WIDTH:
                self._draw_too_small(stdscr, height, width)
            else:
                self._draw(stdscr, height, width)
                if self.show_picker:
                    self._draw_picker(stdscr, height, width)

            try:
                stdscr.refresh()
            except curses.error:
                pass

    def _init_colors(self):
        if not curses.has_colors():
            return
        curses.init_pair(C_HEADER, curses.COLOR_CYAN, -1)
        curses.init_pair(C_GREEN, curses.COLOR_GREEN, -1)
        curses.init_pair(C_YELLOW, curses.COLOR_YELLOW, -1)
        curses.init_pair(C_RED, curses.COLOR_RED, -1)
        curses.init_pair(C_BLUE, curses.COLOR_BLUE, -1)
        curses.init_pair(C_DIM, curses.COLOR_WHITE, -1)

    def _get_key(self, stdscr):
        try:
            key = stdscr.getch()
            return key if key != -1 else None
        except curses.error:
            return None

    def _handle_key(self, key, height):
        """Handle keypress in normal mode. Returns False to exit."""
        if key in (ord('q'), ord('Q')):
            self.exit_code = 0
            self.running = False
            return False
        elif key in (ord('r'), ord('R')):
            self.exit_code = 2
            self.running = False
            return False
        elif key in (ord('m'), ord('M')):
            if self.profiles and self.server_state in ('running', 'idle'):
                self.show_picker = True
                self.picker_page = "main"
                self.picker_sel = 0
        elif key == curses.KEY_UP:
            self._scroll_up(1)
        elif key == curses.KEY_DOWN:
            self._scroll_down(1)
        elif key == curses.KEY_PPAGE:
            self._scroll_up(max(1, height // 3))
        elif key == curses.KEY_NPAGE:
            self._scroll_down(max(1, height // 3))
        elif key == curses.KEY_HOME:
            self.scroll_pos = 0
            self.auto_follow = False
        elif key == curses.KEY_END:
            self.auto_follow = True
        return True

    def _handle_picker_key(self, key):
        """Handle keypress in model picker mode."""
        if key == 27:  # Esc
            self.show_picker = False
            return

        profiles = (self.prod_profiles if self.picker_page == "main"
                    else self.bench_profiles)

        # Arrow keys and Enter for navigation
        if key == curses.KEY_UP:
            self.picker_sel = max(0, self.picker_sel - 1)
            return
        elif key == curses.KEY_DOWN:
            self.picker_sel = min(len(profiles) - 1, self.picker_sel + 1)
            return
        elif key in (10, 13, curses.KEY_ENTER):  # Enter
            if 0 <= self.picker_sel < len(profiles):
                profile = profiles[self.picker_sel]
                self.show_picker = False
                if profile.id != self.current_profile_id:
                    self.switch_model(profile.id)
            return

        if self.picker_page == "main":
            if key in (ord('b'), ord('B')) and self.bench_profiles:
                self.picker_page = "bench"
                self.picker_sel = 0
                return

            # Number keys for production models
            if ord('1') <= key <= ord('9'):
                idx = key - ord('1')
                if idx < len(self.prod_profiles):
                    profile = self.prod_profiles[idx]
                    self.show_picker = False
                    if profile.id != self.current_profile_id:
                        self.switch_model(profile.id)

        elif self.picker_page == "bench":
            if key in (ord('r'), ord('R')):
                self.picker_page = "main"
                self.picker_sel = 0
                return

            # Number keys for bench profiles
            if ord('1') <= key <= ord('9'):
                idx = key - ord('1')
                if idx < len(self.bench_profiles):
                    profile = self.bench_profiles[idx]
                    self.show_picker = False
                    if profile.id != self.current_profile_id:
                        self.switch_model(profile.id)

    def _scroll_up(self, n):
        self.auto_follow = False
        self.scroll_pos = max(0, self.scroll_pos - n)

    def _scroll_down(self, n):
        with self.lock:
            total = len(self.log_lines)
        self.scroll_pos += n

    # ── Drawing ────────────────────────────────────────────────────────────

    def _safe_addstr(self, win, y, x, text, attr=0):
        """Write text to window, silently ignoring out-of-bounds errors."""
        try:
            max_y, max_x = win.getmaxyx()
            if y < 0 or y >= max_y or x < 0 or x >= max_x:
                return
            win.addnstr(y, x, str(text), max_x - x, attr)
        except curses.error:
            pass

    def _draw_bar(self, win, y, x, width, percent, color_pair):
        """Draw a colored progress bar without the percentage label."""
        if width <= 0:
            return
        filled = max(0, min(width, int(percent * width / 100)))
        empty = width - filled
        try:
            max_y, max_x = win.getmaxyx()
            if y >= max_y or x >= max_x:
                return
            avail = max_x - x
            if avail <= 0:
                return
            bar_f = "#" * min(filled, avail)
            win.addnstr(y, x, bar_f, avail,
                        curses.color_pair(color_pair) | curses.A_BOLD)
            if filled < avail:
                bar_e = "-" * min(empty, avail - filled)
                win.addnstr(bar_e, avail - filled, curses.A_DIM)
        except curses.error:
            pass

    def _vram_color(self, percent):
        if percent >= 90:
            return C_RED
        elif percent >= 70:
            return C_YELLOW
        return C_GREEN

    def _draw_too_small(self, stdscr, height, width):
        stdscr.erase()
        msg = f"Terminal too small ({width}x{height}). Need {MIN_WIDTH}x{MIN_HEIGHT}."
        y = height // 2
        x = max(0, (width - len(msg)) // 2)
        self._safe_addstr(stdscr, y, x, msg)

    def _draw(self, stdscr, height, width):
        stdscr.erase()

        # Panel sizes
        log_h = max(5, int(height * 0.55))
        ctrl_h = max(4, min(7, int(height * 0.12)))
        mid_h = max(5, height - log_h - ctrl_h - 2)
        mid_split = width // 2

        # Logs (top)
        self._draw_logs_panel(stdscr, 0, 0, log_h, width)
        self._draw_hline(stdscr, log_h, width)
        # GPU (middle-left) and System (middle-right)
        self._draw_gpu_panel(stdscr, log_h + 1, 0, mid_h, mid_split)
        self._draw_vline(stdscr, log_h + 1, mid_split, mid_h)
        self._draw_sys_panel(stdscr, log_h + 1, mid_split + 1, mid_h,
                             width - mid_split - 1)
        self._draw_hline(stdscr, log_h + 1 + mid_h, width)
        # Control bar (bottom)
        self._draw_ctrl_panel(stdscr, log_h + 2 + mid_h, 0, ctrl_h, width)

    def _draw_hline(self, stdscr, y, width):
        try:
            stdscr.hline(y, 0, curses.ACS_HLINE, width)
        except curses.error:
            pass

    def _draw_vline(self, stdscr, y, x, height):
        try:
            stdscr.vline(y, x, curses.ACS_VLINE, height)
        except curses.error:
            pass

    # ── Log Panel ──────────────────────────────────────────────────────────

    def _draw_logs_panel(self, stdscr, y, x, height, width):
        header = " === Server Logs === "
        self._safe_addstr(stdscr, y, x, header,
                          curses.color_pair(C_HEADER) | curses.A_BOLD)

        # Status message (right-aligned in header)
        if self.status_message:
            if self.server_state in ('starting', 'stopping'):
                status_color = C_YELLOW
            else:
                status_color = C_RED
            status_text = f" {self.status_message} "
            status_x = width - len(status_text) - 1
            if status_x > len(header):
                self._safe_addstr(stdscr, y, status_x, status_text,
                                  curses.color_pair(status_color) | curses.A_BOLD)

        with self.lock:
            lines = list(self.log_lines)
        total = len(lines)
        view_h = height - 1

        if self.auto_follow:
            start = max(0, total - view_h)
            self.scroll_pos = start
        else:
            start = max(0, min(self.scroll_pos, max(0, total - view_h)))
            self.scroll_pos = start
            if total > 0 and start >= total - view_h:
                self.auto_follow = True

        if not self.auto_follow and total > view_h:
            end_line = min(start + view_h, total)
            hint = f" [{start + 1}-{end_line}/{total}] "
            hint_x = width - len(hint) - 1
            if hint_x > len(header):
                self._safe_addstr(stdscr, y, hint_x, hint, curses.A_DIM)

        for i in range(view_h):
            idx = start + i
            row = y + 1 + i
            if idx < total:
                line = strip_ansi(lines[idx])
                if '|' in line[:40]:
                    line = line.split('|', 1)[1].lstrip()
                self._safe_addstr(stdscr, row, x, line[:width])

    # ── GPU Panel ──────────────────────────────────────────────────────────

    def _draw_gpu_panel(self, stdscr, y, x, height, width):
        self._safe_addstr(stdscr, y, x + 1, " === GPU Monitor === ",
                          curses.color_pair(C_HEADER) | curses.A_BOLD)

        with self.lock:
            gpus = list(self.gpu_data)

        if not gpus:
            self._safe_addstr(stdscr, y + 2, x + 2,
                              "Waiting for GPU data...", curses.A_DIM)
            return

        row = y + 2
        for gpu in gpus:
            if row >= y + height - 1:
                break

            mem_pct = 0
            if gpu['mem_total'] > 0:
                mem_pct = int(gpu['mem_used'] * 100 / gpu['mem_total'])

            self._safe_addstr(stdscr, row, x + 2,
                              f"GPU {gpu['index']}: {gpu['name']}",
                              curses.A_BOLD)
            row += 1

            if row < y + height:
                self._safe_addstr(stdscr, row, x + 4,
                                  f"VRAM: {gpu['mem_used']}/{gpu['mem_total']} MiB")
                row += 1

            if row < y + height:
                bar_w = min(20, width - 10)
                self._draw_bar(stdscr, row, x + 4, bar_w, mem_pct,
                               self._vram_color(mem_pct))
                self._safe_addstr(stdscr, row, x + 4 + bar_w + 1,
                                  f"{mem_pct}%")
                row += 1

            if row < y + height:
                self._safe_addstr(
                    stdscr, row, x + 4,
                    f"Util: {gpu['util']}%  Power: {gpu['power_draw']}W/{gpu['power_limit']}W")
                row += 1

            if row < y + height:
                self._safe_addstr(stdscr, row, x + 4,
                                  f"Temp: {gpu['temp']}\u00b0C")
                row += 1

            row += 1  # blank line between GPUs

    # ── System Panel ───────────────────────────────────────────────────────

    def _draw_sys_panel(self, stdscr, y, x, height, width):
        self._safe_addstr(stdscr, y, x + 1, " === System === ",
                          curses.color_pair(C_HEADER) | curses.A_BOLD)

        with self.lock:
            cpu_pct = self.cpu_percent
            load = self.load_avg
            mem_t = self.mem_total
            mem_u = self.mem_used
            swap_t = self.swap_total
            swap_u = self.swap_used
            ccpu = self.container_cpu
            cmem = self.container_mem

        row = y + 2

        self._safe_addstr(stdscr, row, x + 2, f"CPU:  {cpu_pct}%")
        row += 1
        self._safe_addstr(stdscr, row, x + 2, f"Load: {load}")
        row += 2

        # RAM
        mem_pct = int(mem_u * 100 / mem_t) if mem_t > 0 else 0
        self._safe_addstr(stdscr, row, x + 2, f"RAM:  {mem_u}/{mem_t} MiB")
        row += 1

        if row < y + height:
            bar_w = min(20, width - 6)
            self._draw_bar(stdscr, row, x + 2, bar_w, mem_pct, C_BLUE)
            self._safe_addstr(stdscr, row, x + 2 + bar_w + 1, f"{mem_pct}%")
            row += 1

        # Swap
        if row < y + height:
            self._safe_addstr(stdscr, row, x + 2,
                              f"Swap: {swap_u}/{swap_t} MiB")
            row += 2

        # Container stats
        if row < y + height:
            self._safe_addstr(stdscr, row, x + 2, "Container:", curses.A_BOLD)
            row += 1
        if row < y + height:
            if ccpu or cmem:
                self._safe_addstr(stdscr, row, x + 4,
                                  f"CPU: {ccpu}  MEM: {cmem}")
            else:
                self._safe_addstr(stdscr, row, x + 4,
                                  "(not running)", curses.A_DIM)

    # ── Control Bar ────────────────────────────────────────────────────────

    def _draw_ctrl_panel(self, stdscr, y, x, height, width):
        row = y

        # Model name + state
        self._safe_addstr(stdscr, row, x + 1, "Model: ", curses.A_BOLD)
        self._safe_addstr(stdscr, row, x + 8, self.model_name)

        state_str = ""
        state_color = C_DIM
        if self.server_state == "running":
            state_str = " [running]"
            state_color = C_GREEN
        elif self.server_state == "starting":
            state_str = " [starting...]"
            state_color = C_YELLOW
        elif self.server_state == "stopping":
            state_str = " [stopping...]"
            state_color = C_YELLOW
        elif self.server_state == "idle":
            state_str = " [idle]"
            state_color = C_DIM

        model_end = x + 8 + len(self.model_name)
        self._safe_addstr(stdscr, row, model_end, state_str,
                          curses.color_pair(state_color))
        row += 1

        if row < y + height:
            self._safe_addstr(stdscr, row, x + 1, "Web: ", curses.A_BOLD)
            self._safe_addstr(stdscr, row, x + 6, "http://localhost:8080")
            row += 1
        if row < y + height:
            self._safe_addstr(stdscr, row, x + 1, "API: ", curses.A_BOLD)
            self._safe_addstr(stdscr, row, x + 6,
                              "http://localhost:8080/v1/chat/completions")
            mgmt_x = max(52, width // 2)
            self._safe_addstr(stdscr, row, mgmt_x, "Mgmt: ", curses.A_BOLD)
            self._safe_addstr(stdscr, row, mgmt_x + 6,
                              f"http://localhost:{API_PORT}")
            row += 2

        if row < y + height:
            self._safe_addstr(stdscr, row, x + 1, "[q]",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, x + 5, "Exit")
            self._safe_addstr(stdscr, row, x + 12, "[r]",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, x + 16, "Menu")
            if self.profiles:
                self._safe_addstr(stdscr, row, x + 23, "[m]",
                                  curses.color_pair(C_YELLOW) | curses.A_BOLD)
                self._safe_addstr(stdscr, row, x + 27, "Switch model")
            scroll_x = max(43, width // 2)
            self._safe_addstr(stdscr, row, scroll_x, "[",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, scroll_x + 1, "Up/Dn PgUp/Dn",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, scroll_x + 15, "]",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, scroll_x + 17, "Scroll")

    # ── Model Picker Overlay ──────────────────────────────────────────────

    def _draw_picker(self, stdscr, height, width):
        """Draw model picker overlay centered on screen."""
        if self.picker_page == "bench":
            profiles = self.bench_profiles
            title = "Benchmark Profiles"
            footer_hint = "Up/Dn Enter  [1-9]  [r] Back  [Esc] Cancel"
        else:
            profiles = self.prod_profiles
            title = "Switch Model"
            if self.bench_profiles:
                footer_hint = "Up/Dn Enter  [1-9]  [b] Benchmarks  [Esc] Cancel"
            else:
                footer_hint = "Up/Dn Enter  [1-9]  [Esc] Cancel"

        if not profiles:
            return

        # Calculate widest line for overlay width
        max_line_len = max(len(title), len(footer_hint))
        for i, p in enumerate(profiles):
            line_len = len(f"  {i+1}) {p.name}")
            if p.speed:
                line_len += len(f"  {p.speed}")
            if p.ctx_size:
                try:
                    line_len += len(f"  {ctx_label(int(p.ctx_size))}")
                except ValueError:
                    pass
            if p.id == self.current_profile_id:
                line_len += 3  # " *"
            max_line_len = max(max_line_len, line_len)

        # Overlay dimensions
        overlay_w = min(max_line_len + 6, width - 4)
        n_items = len(profiles)
        has_bench_link = (self.picker_page == "main" and self.bench_profiles)
        # rows: border(1) + title(1) + blank(1) + items(N) + [bench_link(2)] + blank(1) + footer(1) + border(1)
        overlay_h = n_items + 6 + (2 if has_bench_link else 0)
        overlay_h = min(overlay_h, height - 2)

        overlay_y = max(0, (height - overlay_h) // 2)
        overlay_x = max(0, (width - overlay_w) // 2)

        # Clear overlay area
        for row in range(overlay_h):
            y = overlay_y + row
            if y >= height:
                break
            self._safe_addstr(stdscr, y, overlay_x, " " * overlay_w)

        # Draw box border
        try:
            stdscr.addch(overlay_y, overlay_x, curses.ACS_ULCORNER)
            stdscr.hline(overlay_y, overlay_x + 1, curses.ACS_HLINE,
                         overlay_w - 2)
            stdscr.addch(overlay_y, overlay_x + overlay_w - 1,
                         curses.ACS_URCORNER)

            bottom_y = overlay_y + overlay_h - 1
            if bottom_y < height:
                stdscr.addch(bottom_y, overlay_x, curses.ACS_LLCORNER)
                stdscr.hline(bottom_y, overlay_x + 1, curses.ACS_HLINE,
                             overlay_w - 2)
                stdscr.addch(bottom_y, overlay_x + overlay_w - 1,
                             curses.ACS_LRCORNER)

            for row in range(1, overlay_h - 1):
                y = overlay_y + row
                if y >= height:
                    break
                stdscr.addch(y, overlay_x, curses.ACS_VLINE)
                end_x = overlay_x + overlay_w - 1
                if end_x < width:
                    stdscr.addch(y, end_x, curses.ACS_VLINE)
        except curses.error:
            pass

        # Title
        self._safe_addstr(stdscr, overlay_y + 1, overlay_x + 3, title,
                          curses.color_pair(C_HEADER) | curses.A_BOLD)

        # Model list
        row = overlay_y + 3
        for i, p in enumerate(profiles):
            if row >= overlay_y + overlay_h - 2:
                break

            ctx = ""
            if p.ctx_size:
                try:
                    ctx = ctx_label(int(p.ctx_size))
                except ValueError:
                    ctx = p.ctx_size

            is_current = (p.id == self.current_profile_id)
            is_selected = (i == self.picker_sel)

            # Highlight bar for selected item
            if is_selected:
                self._safe_addstr(stdscr, row, overlay_x + 2,
                                  " " * (overlay_w - 4), curses.A_REVERSE)

            # Number
            num_attr = curses.A_REVERSE if is_selected else (
                curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, overlay_x + 3, f"{i+1})", num_attr)

            # Name
            if is_selected:
                name_attr = curses.A_REVERSE | curses.A_BOLD
            elif is_current:
                name_attr = curses.A_BOLD
            else:
                name_attr = 0
            self._safe_addstr(stdscr, row, overlay_x + 6, p.name, name_attr)

            # Speed + context (right side)
            extra = ""
            if p.speed:
                extra += f"  {p.speed}"
            if ctx:
                extra += f"  {ctx}"
            if is_current:
                extra += "  *"

            extra_x = overlay_x + 6 + len(p.name)
            if is_selected:
                self._safe_addstr(stdscr, row, extra_x, extra, curses.A_REVERSE)
            elif is_current:
                self._safe_addstr(stdscr, row, extra_x, extra,
                                  curses.color_pair(C_GREEN))
            else:
                self._safe_addstr(stdscr, row, extra_x, extra, curses.A_DIM)

            row += 1

        # Bench submenu link (main page only)
        if has_bench_link:
            row += 1
            if row < overlay_y + overlay_h - 2:
                self._safe_addstr(stdscr, row, overlay_x + 3, "b)",
                                  curses.color_pair(C_YELLOW) | curses.A_BOLD)
                self._safe_addstr(stdscr, row, overlay_x + 6,
                                  f"Benchmarks ({len(self.bench_profiles)})",
                                  curses.A_DIM)

        # Footer
        footer_y = overlay_y + overlay_h - 2
        if footer_y < height:
            self._safe_addstr(stdscr, footer_y, overlay_x + 3, footer_hint,
                              curses.A_DIM)

    # ── Data Collection Threads ────────────────────────────────────────────

    def _collect_logs(self):
        """Thread: stream docker compose logs."""
        try:
            proc = subprocess.Popen(
                ["docker", "compose", "-f", self.compose_file,
                 "logs", "-f", "--tail=200"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._log_proc = proc
            for line in proc.stdout:
                if not self.running:
                    break
                with self.lock:
                    self.log_lines.append(line.rstrip('\n'))
            proc.wait()
        except Exception as e:
            with self.lock:
                self.log_lines.append(f"(log collection error: {e})")

    def _collect_data(self):
        """Thread: poll GPU, CPU, memory, container stats every ~2s."""
        while self.running:
            self._poll_gpu()
            self._poll_cpu()
            self._poll_memory()
            self._poll_container()
            # Sleep in small chunks for responsive exit
            for _ in range(20):
                if not self.running:
                    return
                time.sleep(0.1)

    def _poll_gpu(self):
        try:
            r = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=index,name,memory.used,memory.total,"
                 "utilization.gpu,power.draw,power.limit,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return
            gpus = []
            for line in r.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 8:
                    gpus.append({
                        'index': parts[0],
                        'name': parts[1],
                        'mem_used': int(float(parts[2])),
                        'mem_total': int(float(parts[3])),
                        'util': int(float(parts[4])),
                        'power_draw': int(float(parts[5])),
                        'power_limit': int(float(parts[6])),
                        'temp': int(float(parts[7])),
                    })
            with self.lock:
                self.gpu_data = gpus
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

    def _poll_cpu(self):
        try:
            with open('/proc/stat') as f:
                parts = f.readline().split()
            current = (int(parts[1]), int(parts[2]),
                       int(parts[3]), int(parts[4]))

            if self._prev_cpu is not None:
                pu, pn, ps, pi = self._prev_cpu
                cu, cn, cs, ci = current
                active = (cu + cn + cs) - (pu + pn + ps)
                total = active + (ci - pi)
                pct = int(active * 100 / total) if total > 0 else 0

                with open('/proc/loadavg') as f:
                    la = f.read().split()

                with self.lock:
                    self.cpu_percent = pct
                    self.load_avg = f"{la[0]} {la[1]} {la[2]}"

            self._prev_cpu = current
        except (OSError, IndexError, ValueError, ZeroDivisionError):
            pass

    def _poll_memory(self):
        try:
            info = {}
            with open('/proc/meminfo') as f:
                for line in f:
                    parts = line.split()
                    info[parts[0].rstrip(':')] = int(parts[1])

            mt = info.get('MemTotal', 0) // 1024
            ma = info.get('MemAvailable', 0) // 1024
            st = info.get('SwapTotal', 0) // 1024
            sf = info.get('SwapFree', 0) // 1024

            with self.lock:
                self.mem_total = mt
                self.mem_used = mt - ma
                self.swap_total = st
                self.swap_used = st - sf
        except (OSError, IndexError, ValueError):
            pass

    def _poll_container(self):
        try:
            r = subprocess.run(
                ["docker", "stats", "--no-stream",
                 "--format", "{{.CPUPerc}}|{{.MemUsage}}",
                 "llama-server"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split('|')
                with self.lock:
                    self.container_cpu = parts[0].strip() if parts else ""
                    self.container_mem = (parts[1].strip()
                                          if len(parts) > 1 else "")
            else:
                with self.lock:
                    self.container_cpu = ""
                    self.container_mem = ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            with self.lock:
                self.container_cpu = ""
                self.container_mem = ""


def main():
    parser = argparse.ArgumentParser(
        description="Terminal monitoring dashboard for llama.cpp"
    )
    parser.add_argument("--compose-file", required=True,
                        help="Path to docker-compose.yml")
    parser.add_argument("--model-name", required=True,
                        help="Display name of the loaded model")
    parser.add_argument("--models-conf",
                        help="Path to models.conf for model switching")
    parser.add_argument("--current-profile",
                        help="ID of the currently loaded model profile")
    args = parser.parse_args()

    dashboard = Dashboard(
        compose_file=args.compose_file,
        model_name=args.model_name,
        models_conf=args.models_conf,
        current_profile=args.current_profile,
    )
    sys.exit(dashboard.run())


if __name__ == "__main__":
    main()
