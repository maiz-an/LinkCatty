import contextlib
import unicodedata
import re
import sys
import os
import time
import threading
import platform
import shutil

# ANSI color codes (Windows 10+ supports them, older Windows will fallback)
if platform.system() == "Windows":
    os.system("")  # Enables ANSI escape sequences
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

_spinner_running = False
_spinner_text = ""


def set_console_width(width=62):
    system = platform.system()
    try:
        if system == "Windows":
            os.system(f"mode con cols={width} lines=30")
        else:
            os.system(f"stty cols {width}")
            sys.stdout.write(f"\x1b[8;30;{width}t")
            sys.stdout.flush()
    except Exception:
        pass


def clear_screen():
    if os.name == 'nt':
        os.system('cls')
        return
    if shutil.which('clear'):
        os.system('clear')


def _resolve_version(version=None):
    if version is not None:
        return version
    try:
        from .config import get_version
        return get_version()
    except Exception:
        return None


def print_banner():
    tagline = "- a Maiz's one -".center(61)
    logo = f"""
=============================================================

{CYAN}{BOLD}    ██     ▄▄ ▄▄  ▄▄ ▄▄ ▄▄ ▄█████  ▄▄▄ ▄▄▄▄▄▄ ▄▄▄▄▄▄ ▄▄ ▄▄ 
    ██     ██ ███▄██ ██▄█▀ ██     ██▀██  ██     ██   ▀███▀ 
    ██████ ██ ██ ▀██ ██ ██ ▀█████ ██▀██  ██     ██     █{RESET}

{DIM}{tagline}{RESET}

============================================================="""
    print(logo)


def print_version():
    resolved = _resolve_version()
    if resolved:
        tag = resolved if resolved.lower().startswith("v") else f"v{resolved}"
        print(f"{DIM}{tag.center(61)}{RESET}")


def print_main_menu():
    print(f"{BOLD}{WHITE}{center_text('🎯 MAIN MENU')}{RESET}")
    print_version()
    print("=" * 61)
    print(f"")
    print(f"{CYAN}{BOLD}1.{RESET} YouTube Downloader")
    print(f"{CYAN}{BOLD}2.{RESET} Spotify Downloader")
    print(f"{CYAN}{BOLD}3.{RESET} Other Downloaders")
    print(f"{CYAN}{BOLD}4.{RESET} Settings")
    print(f"{CYAN}{BOLD}0.{RESET} Exit")
    print(f"")
    print(f"{'=' * 61}{RESET}")


def print_error(message, suggestion=None):
    print(f"\n{RED}{BOLD}❌ ERROR:{RESET} {message}")
    if suggestion:
        print(f"{YELLOW}💡 {suggestion}{RESET}")


def print_success(message):
    print(f"\n{GREEN}{BOLD}✅ {message}{RESET}")


def print_info(message):
    print(f"{CYAN}ℹ️  {message}{RESET}")


def print_warning(message):
    print(f"{YELLOW}⚠️  {message}{RESET}")


def pause(message="\nPress Enter to continue..."):
    try:
        input(message)
    except (KeyboardInterrupt, EOFError):
        print()


def read_key():
    """Read one keypress when possible; fall back to Enter-based input."""
    try:
        if os.name == "nt":
            import msvcrt
            while True:
                char = msvcrt.getwch()
                if char in ("\x00", "\xe0"):
                    return char + msvcrt.getwch()
                return char

        import termios
        import tty
        if not sys.stdin.isatty():
            value = input().strip()
            return value[:1]
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except (ImportError, OSError, EOFError):
        value = input().strip()
        return value[:1]
    except KeyboardInterrupt:
        return "\x03"


def menu_choice(prompt, valid_choices, back_choices=None, allow_empty=False):
    """Read a single-key menu choice and validate it.

    Returns
    -------
    str
        The chosen key when it is in `valid_choices` or `back_choices`.
    ""
        If `allow_empty=True` and the user pressed Enter alone — callers
        use this as "keep current value / skip this step".
    None
        If the user pressed Ctrl+C.
    """
    valid = {str(choice) for choice in valid_choices}
    back = set(back_choices or [])
    while True:
        print(prompt, end="", flush=True)
        choice = read_key()

        # Enter (bare) ------------------------------------------------
        if choice in ("\r", "\n"):
            print()
            if allow_empty:
                return ""
            continue

        # Ctrl+C ------------------------------------------------------
        if choice == "\x03":
            print()
            return None

        print(choice)
        if choice in valid or choice in back:
            return choice

        hint = f"Press one of: {', '.join(sorted(valid | back))}"
        if allow_empty:
            hint += "  (Enter = keep current, 0 = cancel)"
        print_error(f"Invalid choice: {choice}", hint)


def confirm(prompt, default=False):
    """Read a y/n answer as a single-key option."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        print(prompt + suffix, end="", flush=True)
        choice = read_key().lower()
        if choice in ("\r", "\n"):
            print()
            return default
        if choice == "\x03":
            print()
            return False
        print(choice)
        if choice in ("y", "n", "0"):        # 0 = cancel, like everywhere else
            return choice == "y"
        print_error("Invalid answer", "Press y or n (0 to cancel)")


def start_spinner(text="Processing"):
    global _spinner_running, _spinner_text
    _spinner_running = True
    _spinner_text = text

    def _spin():
        chars = "⣾⣽⣻⢿⡿⣟⣯⣷"
        idx = 0
        while _spinner_running:
            sys.stdout.write(f"\r{_spinner_text} {CYAN}{chars[idx]}{RESET}")
            sys.stdout.flush()
            time.sleep(0.1)
            idx = (idx + 1) % len(chars)
        sys.stdout.write("\r" + " " * (len(_spinner_text) + 2) + "\r")
        sys.stdout.flush()

    threading.Thread(target=_spin, daemon=True).start()


def stop_spinner():
    global _spinner_running
    _spinner_running = False
    time.sleep(0.2)


def progress_bar(current, total, prefix="", suffix="", length=40):
    percent = current / total
    filled = int(length * percent)
    bar = f"{GREEN}{'█' * filled}{RESET}{'░' * (length - filled)}"
    sys.stdout.write(f"\r{prefix} |{bar}| {percent:.1%} {suffix}")
    sys.stdout.flush()


class SilentLogger:
    """yt-dlp logger that swallows all output (we print our own messages)."""

    def debug(self, msg):
        pass

    info = warning = error = debug


_URL = re.compile(r"https?://\S+")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def explain_error(exc, config=None):
    """Return (message, hint) for display: no extractor tags or URLs.

    Pass `config` so the hint can tell whether a proxy is already set.
    """
    text = strip_ansi(str(exc)).strip()
    text = text.split("; please report")[0]
    text = re.sub(r"^ERROR:\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*\S+:\s*", "", text)
    text = _URL.sub("", text)
    text = re.sub(r"\s*See\s+first for more details\.?", "", text)
    text = re.sub(r"\s*\(caused by .*$", "", text).strip()
    from .config import get_proxy, is_block_error, proxy_endpoint
    proxy = get_proxy(config) if config else ""
    has_proxy = bool(proxy)
    low = text.lower()
    if has_proxy:
        host, port = proxy_endpoint(proxy)
        if f"{host} port {port}".lower() in low:
            hint = (
                "Start your proxy or VPN app, or fix the address:\n"
                "   Main menu > 4. Settings > 7. Network proxy"
            )
            if (host, port) == ("127.0.0.1", 1080):
                hint += "\n   (127.0.0.1:1080 was only an example address.)"
            return (f"Nothing is running at your proxy address ({host}:{port}).", hint)
    if "proxyerror" in low or "tunnel failed" in low:
        return (
            "Could not connect through your proxy.",
            "Check the proxy address:\n"
            "   Main menu > 4. Settings > 7. Network proxy\n"
            "   and make sure your proxy or VPN app is running.",
        )
    if is_block_error(text):
        if has_proxy:
            return (
                "Still blocked, even through your proxy.",
                "Try a different proxy or VPN server:\n"
                "   Main menu > 4. Settings > 7. Network proxy",
            )
        return (
            "Could not connect - blocked by your network.",
            "Turn on your VPN, or use a proxy:\n"
            "   1. Main menu > 4. Settings > 7. Network proxy\n"
            "   2. Enter your proxy address, e.g.\n"
            "      socks5://127.0.0.1:1080\n"
            "   It is only used when a direct connection is blocked.",
        )
    return text, "Check the URL and your internet connection."


def offer_retry_after_block(exc):
    """After a blocked-connection error, let the user turn on a VPN and retry.

    Returns True when the caller should try again. Other errors never prompt.
    """
    from .config import is_block_error
    if not is_block_error(strip_ansi(str(exc))):
        return False
    return ask_retry_vpn()


def strip_ansi(text):
    return _ANSI.sub("", text)


def ask_retry_vpn():
    """Ask the user to turn on a VPN (or fix the proxy) and retry."""
    try:
        answer = input("\nTurn on your VPN (or fix the proxy), then press "
                       "Enter to retry, or 0 to cancel: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    return answer != "0"


# ─────────────────────────────────────────────────────────────────────
#  Formatting helpers
# ─────────────────────────────────────────────────────────────────────

def format_bytes(num):
    try:
        num = float(num)
    except (TypeError, ValueError):
        return "?"
    units = ("B", "KB", "MB", "GB", "TB")
    idx = 0
    while num >= 1024 and idx < len(units) - 1:
        num /= 1024
        idx += 1
    return f"{int(num)}B" if idx == 0 else f"{num:.1f}{units[idx]}"


def format_eta(seconds):
    secs = int(max(seconds, 0))
    minutes, secs = divmod(secs, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def format_duration(seconds):
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_count(num):
    if not num:
        return "Unknown"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


# ─────────────────────────────────────────────────────────────────────
#  LinkCatty UI kit - shared by every downloader
#
#    section_header    banner + centered section title
#    show_menu         numbered sub-menu
#    ask_url           the URL prompt
#    card              minimal info card            ┌ │ └
#    result_card       end-of-run summary card
#    plan_line         one dim line: what is about to happen
#    item_line         one ✔ / ✖ line for DownloadProgress.say()
#    DownloadProgress  ONE live, width-aware progress bar
#
#  Restyle here and every downloader changes with it.
# ─────────────────────────────────────────────────────────────────────

WIDTH = 61


def display_width(text):
    """Columns a string takes in the console (emoji/CJK count as 2)."""
    width = 0
    for ch in strip_ansi(str(text)):
        if unicodedata.combining(ch) or ch in ("‍", "︎", "️"):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def fit(text, width):
    """Shorten to `width` columns, adding … when something was cut."""
    text = " ".join(str(text).split())
    if display_width(text) <= width:
        return text
    out = ""
    for ch in text:
        if display_width(out + ch) > width - 1:
            break
        out += ch
    return out.rstrip() + "…"


_PATH_START = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]|~)")


def fit_tail(text, width):
    """Shorten from the left, keeping the END (what matters in a file path)."""
    text = str(text)
    if display_width(text) <= width:
        return text
    out = ""
    for ch in reversed(text):
        if display_width(ch + out) > width - 1:
            break
        out = ch + out
    return "…" + out


def center_text(text, width=WIDTH):
    return " " * max(0, (width - display_width(text)) // 2) + text


def section_header(title):
    """Clear the screen and draw: banner, centered title, rule."""
    clear_screen()
    print_banner()
    print(f"{BOLD}{center_text(title)}{RESET}")
    print_version()
    print("=" * WIDTH)


def show_menu(title, options, prompt="Select", back="Back to main menu"):
    """Full-screen numbered menu where 0 (or an empty Enter) goes back.

    Returns the chosen key, "0" for back, or None on Ctrl+C.
    """
    section_header(title)
    print()
    for number, text in enumerate(options, 1):
        print(f"{CYAN}{BOLD}{number}.{RESET} {text}")
    print(f"{CYAN}{BOLD}0.{RESET} {back}")
    print()
    print("=" * WIDTH)
    keys = "0" + "".join(str(n) for n in range(1, len(options) + 1))
    choice = menu_choice(f"{prompt} (0-{len(options)}): ", keys, allow_empty=True)
    return "0" if choice == "" else choice


def ask_url(what):
    """URL prompt. Blank or 0 means go back (returns "")."""
    value = input(f"\n🎯 Enter {what} URL (0 or blank to go back): ").strip()
    return "" if value == "0" else value


def _print_card(head, accent, rows, details=None, footer=None):
    def clean(items):
        return [(str(label), str(value)) for label, value in items
                if value not in (None, "")]
    rows, footer = clean(rows), clean(footer or [])
    label_w = max([len(label) for label, _ in rows + footer] + [6])

    def show(items):
        for label, value in items:
            room = WIDTH - (2 + 2 + label_w + 2)
            shown = fit_tail(value, room) if _PATH_START.match(value) else fit(value, room)
            print(f"  {DIM}│{RESET} {DIM}{label.ljust(label_w)}{RESET}  {shown}")

    print()
    print(f"  {DIM}┌{RESET} {accent}{BOLD}{head}{RESET}")
    show(rows)
    for line in details or []:
        print(f"  {DIM}│{RESET}   {DIM}•{RESET} {fit(line, WIDTH - 8)}")
    show(footer)
    print(f"  {DIM}└{RESET}")
    print()


def card(title, rows, icon="", details=None):
    """Info card: a title, aligned label/value rows, optional bullet lines."""
    _print_card(f"{icon} {title}".strip(), CYAN, rows, details)


_STATUS_STYLE = {"ok": ("✔", GREEN), "warn": ("⚠", YELLOW), "fail": ("✖", RED)}


def result_card(status, headline, rows, details=None, footer=None):
    """End-of-run card. status: 'ok' | 'warn' | 'fail'.

    rows first, then `details` as bullets (e.g. failure causes), then `footer`
    rows (e.g. the report path).
    """
    icon, color = _STATUS_STYLE[status]
    _print_card(f"{icon} {headline}", color, rows, details, footer)


def plan_line(*parts):
    """One dim line summarising what is about to run."""
    text = " · ".join(str(p) for p in parts if p)
    if text:
        print(f"  {DIM}{fit(text, WIDTH - 2)}{RESET}")


def item_line(ok, index, count, title, detail=""):
    """A per-item line, meant for DownloadProgress.say()."""
    mark = f"{GREEN}✔{RESET}" if ok else f"{RED}✖{RESET}"
    prefix = f"{index}/{count}"
    room = WIDTH - 4 - len(prefix) - 2 - (display_width(detail) + 2 if detail else 0)
    tail = f"  {DIM}{detail}{RESET}" if detail else ""
    return f"  {mark} {DIM}{prefix}{RESET}  {fit(title, max(room, 12))}{tail}"


def note_line(text, icon="↻"):
    """A dim one-liner (retry / cooldown notices), meant for .say()."""
    return f"  {DIM}{icon} {fit(text, WIDTH - 6)}{RESET}"


class DownloadProgress:
    """One live progress line for a whole run.

    Two ways to feed it:
      * yt-dlp hooks   -> pass .hook / .pp_hook as progress_hooks / postprocessor_hooks
      * counting files -> pass count_fn (e.g. Spotify: files on disk)
    The line adapts to the console width so it never wraps.
    Use .say() to print above the bar and .paused() around prompts.
    """

    def __init__(self, label, total_items=1, unit="videos", count_fn=None):
        self.label = label
        self.total_items = max(int(total_items), 1)
        self.unit = unit
        self.done_items = 0
        self.final_path = None
        self._count_fn = count_fn
        self._icon = "⬇"
        self._run_done = 0
        self._start = time.time()
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._last_len = 0
        self._paused = False
        self._saved_label = None
        self._reset_item()

    @property
    def elapsed(self):
        return time.time() - self._start

    def _reset_item(self):
        self._base_done = 0
        self._base_total = 0
        self._stream = None
        self._stream_done = 0
        self._stream_total = None
        self._speed = None
        self._eta = None
        self._frac = 0.0
        self._expected_total = None
        self._streams = 0
        self._finished_streams = 0

    def start(self):
        self._render()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
        self._render()
        with self._lock:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def set_label(self, label):
        with self._lock:
            self.label = label

    def say(self, message):
        with self._lock:
            sys.stdout.write("\r" + " " * self._last_len + "\r")
            sys.stdout.flush()
            print(message)
            self._last_len = 0

    @contextlib.contextmanager
    def paused(self):
        with self._lock:
            sys.stdout.write("\r" + " " * self._last_len + "\r")
            sys.stdout.flush()
            self._last_len = 0
            self._paused = True
        try:
            yield
        finally:
            with self._lock:
                self._paused = False
            self._render()

    def item_done(self):
        with self._lock:
            self.done_items = min(self.done_items + 1, self.total_items)
            self._run_done += 1
            self._reset_item()

    def item_reset(self):
        with self._lock:
            self._reset_item()

    def hook(self, data):
        """yt-dlp progress hook."""
        status = data.get("status")
        if status not in ("downloading", "finished"):
            return
        with self._lock:
            name = data.get("filename") or data.get("tmpfilename")
            formats = (data.get("info_dict") or {}).get("requested_formats") or []
            if formats and not self._streams:
                self._streams = len(formats)
                sizes = [f.get("filesize") or f.get("filesize_approx") or 0 for f in formats]
                if all(sizes):
                    self._expected_total = sum(sizes)
            if name != self._stream:
                if self._stream is not None:
                    self._base_done += self._stream_done
                    self._base_total += self._stream_total or self._stream_done
                    self._finished_streams += 1
                self._stream = name
                self._stream_done = 0
                self._stream_total = None
            done = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            if status == "finished":
                total = total or done
                done = total
                self.final_path = data.get("filename") or self.final_path
            self._stream_done = done
            self._stream_total = total
            self._speed = data.get("speed")
            self._eta = data.get("eta")
            denominator = self._base_total + (total or 0)
            if self._expected_total:
                seen = self._base_done + done
                frac = seen / max(self._expected_total, seen)
            elif self._streams > 1 and total:
                frac = (self._finished_streams + done / total) / self._streams
            elif denominator > 0:
                frac = (self._base_done + done) / denominator
            elif data.get("fragment_count"):
                frac = (data.get("fragment_index") or 0) / data["fragment_count"]
            else:
                frac = 0.0
            # 100% is reserved for item_done(): another stream may still follow
            self._frac = max(self._frac, min(frac, 0.99))

    def pp_hook(self, data):
        """yt-dlp postprocessor hook (merging, audio conversion...)."""
        name = str(data.get("postprocessor") or "").lower()
        with self._lock:
            if data.get("status") == "started":
                if self._saved_label is None:
                    self._saved_label = (self.label, self._icon)
                self.label = "Merging" if "merg" in name else "Processing"
                self._icon = "🔧"
            elif data.get("status") == "finished":
                path = (data.get("info_dict") or {}).get("filepath")
                if path:
                    self.final_path = path
                if self._saved_label is not None:
                    self.label, self._icon = self._saved_label
                    self._saved_label = None

    def _loop(self):
        while not self._stop.wait(0.5):
            self._render()

    @staticmethod
    def _columns():
        cols = shutil.get_terminal_size((100, 24)).columns
        return max(30, min(cols, 100) - 2)

    def _render(self):
        with self._lock:
            if self._paused:
                return
            parts = {}
            if self._count_fn:
                try:
                    done = int(self._count_fn())
                except Exception:
                    done = self.done_items
                self.done_items = min(done, self.total_items)
                frac = self.done_items / self.total_items
                parts["size"] = f"{self.done_items}/{self.total_items} {self.unit}"
                remaining = self.total_items - self.done_items
                if self.done_items > 0 and remaining > 0:
                    rate = self.done_items / max(self.elapsed, 0.001)
                    if rate > 0:
                        parts["eta"] = format_eta(remaining / rate)
            else:
                frac = min((self.done_items + self._frac) / self.total_items, 1.0)
                if self.total_items > 1:
                    parts["size"] = f"{self.done_items}/{self.total_items} {self.unit}"
                else:
                    done = self._base_done + self._stream_done
                    total = self._expected_total or (
                        self._base_total + (self._stream_total or 0))
                    if total:
                        parts["size"] = f"{format_bytes(done)}/{format_bytes(total)}"
                    elif done:
                        parts["size"] = format_bytes(done)
                if self._speed:
                    parts["speed"] = f"{format_bytes(self._speed)}/s"
                eta = self._estimate_eta()
                if eta is not None:
                    parts["eta"] = format_eta(eta)

            line = self._compose(max(0.0, min(frac, 1.0)), parts)
            visible = display_width(line)
            pad = max(0, self._last_len - visible)
            sys.stdout.write("\r" + line + (" " * pad))
            sys.stdout.flush()
            self._last_len = visible

    def _compose(self, frac, parts):
        head = f"  {self._icon} {self.label}  "
        pct = f"  {frac * 100:3.0f}%"
        cols = self._columns()
        order = ("size", "speed", "eta")
        keep = [name for name in order if name in parts]
        for drop in ("speed", "size"):
            tail = "  " + " · ".join(parts[n] for n in keep) if keep else ""
            if cols - display_width(head) - len(pct) - display_width(tail) >= 14:
                break
            if drop in keep:
                keep.remove(drop)
        tail = "  " + " · ".join(parts[n] for n in keep) if keep else ""
        bar_w = cols - display_width(head) - len(pct) - display_width(tail)
        bar_w = max(6, min(bar_w, 36))
        filled = int(bar_w * frac)
        bar = f"{CYAN}{'━' * filled}{RESET}{DIM}{'─' * (bar_w - filled)}{RESET}"
        return f"{head}{bar}{BOLD}{pct}{RESET}{DIM}{tail}{RESET}"

    def _estimate_eta(self):
        if self.total_items == 1:
            return self._eta
        progressed = self._run_done + self._frac
        if progressed <= 0:
            return None
        remaining = self.total_items - self.done_items - self._frac
        return self.elapsed / progressed * max(remaining, 0)
