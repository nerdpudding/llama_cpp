#!/usr/bin/env python3
"""Terminal monitoring dashboard for llama.cpp Docker wrapper.

Single-process curses TUI with GPU monitoring, system stats, server logs,
and keyboard controls. Uses only Python stdlib — no pip installs needed.

Called by start.sh after starting the container:
    python3 dashboard.py --compose-file docker-compose.yml --model-name "Model Name"

Exit codes:
    0 = stop & exit
    2 = stop & return to menu
"""

import argparse
import curses
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections import deque

MIN_WIDTH = 60
MIN_HEIGHT = 20
LOG_BUFFER_SIZE = 2000

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


class Dashboard:
    def __init__(self, compose_file, model_name):
        self.compose_file = compose_file
        self.model_name = model_name
        self.exit_code = 0
        self.running = True

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

        try:
            curses.wrapper(self._ui_main)
        except KeyboardInterrupt:
            self.exit_code = 0
        finally:
            self.running = False
            if self._log_proc:
                try:
                    self._log_proc.terminate()
                except OSError:
                    pass

        return self.exit_code

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
                if not self._handle_key(key, height):
                    break

            if height < MIN_HEIGHT or width < MIN_WIDTH:
                self._draw_too_small(stdscr, height, width)
            else:
                self._draw(stdscr, height, width)

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
        """Handle keypress. Returns False to exit the main loop."""
        if key in (ord('q'), ord('Q')):
            self.exit_code = 0
            self.running = False
            return False
        elif key in (ord('r'), ord('R')):
            self.exit_code = 2
            self.running = False
            return False
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

    def _scroll_up(self, n):
        self.auto_follow = False
        self.scroll_pos = max(0, self.scroll_pos - n)

    def _scroll_down(self, n):
        with self.lock:
            total = len(self.log_lines)
        self.scroll_pos += n
        # Re-enable auto-follow if scrolled past end (checked during draw)

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
            # Filled portion
            bar_f = "#" * min(filled, avail)
            win.addnstr(y, x, bar_f, avail,
                        curses.color_pair(color_pair) | curses.A_BOLD)
            # Empty portion
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
        mid_h = max(5, height - log_h - ctrl_h - 2)  # -2 for separator lines
        mid_split = width // 2

        # Logs (top)
        self._draw_logs_panel(stdscr, 0, 0, log_h, width)
        # Horizontal separator
        self._draw_hline(stdscr, log_h, width)
        # GPU (middle-left) and System (middle-right)
        self._draw_gpu_panel(stdscr, log_h + 1, 0, mid_h, mid_split)
        self._draw_vline(stdscr, log_h + 1, mid_split, mid_h)
        self._draw_sys_panel(stdscr, log_h + 1, mid_split + 1, mid_h,
                             width - mid_split - 1)
        # Horizontal separator
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

        with self.lock:
            lines = list(self.log_lines)
        total = len(lines)
        view_h = height - 1  # minus header

        if self.auto_follow:
            start = max(0, total - view_h)
            self.scroll_pos = start
        else:
            start = max(0, min(self.scroll_pos, max(0, total - view_h)))
            self.scroll_pos = start
            # Re-enable auto-follow when scrolled to bottom
            if total > 0 and start >= total - view_h:
                self.auto_follow = True

        # Scroll position indicator
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
                # Strip docker compose service prefix ("llama-server  | ...")
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
        self._safe_addstr(stdscr, row, x + 1, "Model: ", curses.A_BOLD)
        self._safe_addstr(stdscr, row, x + 8, self.model_name)
        row += 1

        if row < y + height:
            api_url = "http://localhost:8080"
            self._safe_addstr(stdscr, row, x + 1, "API: ", curses.A_BOLD)
            self._safe_addstr(stdscr, row, x + 6,
                              f"{api_url}/v1/chat/completions")
            web_x = max(46, width // 2)
            self._safe_addstr(stdscr, row, web_x, "Web: ", curses.A_BOLD)
            self._safe_addstr(stdscr, row, web_x + 5, api_url)
            row += 2

        if row < y + height:
            self._safe_addstr(stdscr, row, x + 1, "[q]",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, x + 5, "Stop & exit")
            self._safe_addstr(stdscr, row, x + 20, "[r]",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, x + 24, "Stop & return to menu")
            scroll_x = max(49, width // 2)
            self._safe_addstr(stdscr, row, scroll_x, "[",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, scroll_x + 1, "Up/Dn PgUp/Dn",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, scroll_x + 15, "]",
                              curses.color_pair(C_YELLOW) | curses.A_BOLD)
            self._safe_addstr(stdscr, row, scroll_x + 17, "Scroll logs")

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
    args = parser.parse_args()

    dashboard = Dashboard(args.compose_file, args.model_name)
    sys.exit(dashboard.run())


if __name__ == "__main__":
    main()
