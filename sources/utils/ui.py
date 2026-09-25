import contextlib
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


def print_banner(version=None):
    logo = f"""
=============================================================

{CYAN}{BOLD}    ██     ▄▄ ▄▄  ▄▄ ▄▄ ▄▄ ▄█████  ▄▄▄ ▄▄▄▄▄▄ ▄▄▄▄▄▄ ▄▄ ▄▄ 
    ██     ██ ███▄██ ██▄█▀ ██     ██▀██  ██     ██   ▀███▀ 
    ██████ ██ ██ ▀██ ██ ██ ▀█████ ██▀██  ██     ██     █{RESET}

============================================================="""
    print(logo)
    resolved = _resolve_version(version)
    if not resolved:
        return
    tag = resolved if resolved.lower().startswith("v") else f"v{resolved}"
    print(f"{DIM}{tag.center(61)}{RESET}")


def print_main_menu():
    print(f"{BOLD}{WHITE}                       🎯 MAIN MENU{RESET}")
    print(f"{'=' * 61}{RESET}")
    print(f"")
    print(f"{CYAN}{BOLD}1.{RESET} YouTube Downloader")
    print(f"{CYAN}{BOLD}2.{RESET} Spotify Downloader")
    print(f"{CYAN}{BOLD}3.{RESET} Other Downloaders")
    print(f"{CYAN}{BOLD}4.{RESET} Settings")
    print(f"{CYAN}{BOLD}5.{RESET} Exit")
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
        if choice in ("y", "n"):
            return choice == "y"
        print_error("Invalid answer", "Press y or n")


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
#  Single live progress bar fed by yt-dlp hooks (Spotify-style)
#
#  One bar for the whole run. Messages printed with .say() land ABOVE
#  the bar instead of stomping on it; .paused() lets prompts run cleanly.
# ─────────────────────────────────────────────────────────────────────

class DownloadProgress:
    BAR_WIDTH = 40

    def __init__(self, label, total_items=1):
        self.label = label
        self.total_items = max(int(total_items), 1)
        self.done_items = 0
        self._run_done = 0
        self._start = time.time()
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._last_len = 0
        self._paused = False
        self._saved_label = None
        self._reset_item()

    def _reset_item(self):
        self._base_done = 0
        self._base_total = 0
        self._stream = None
        self._stream_done = 0
        self._stream_total = None
        self._speed = None
        self._eta = None
        self._frac = 0.0

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
            if name != self._stream:
                if self._stream is not None:
                    self._base_done += self._stream_done
                    self._base_total += self._stream_total or self._stream_done
                self._stream = name
                self._stream_done = 0
                self._stream_total = None
            done = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            if status == "finished":
                total = total or done
                done = total
            self._stream_done = done
            self._stream_total = total
            self._speed = data.get("speed")
            self._eta = data.get("eta")
            denominator = self._base_total + (total or 0)
            if denominator > 0:
                frac = (self._base_done + done) / denominator
            elif data.get("fragment_count"):
                frac = (data.get("fragment_index") or 0) / data["fragment_count"]
            else:
                frac = 0.0
            self._frac = max(self._frac, min(frac, 1.0))

    def pp_hook(self, data):
        """yt-dlp postprocessor hook (merging etc.)."""
        name = str(data.get("postprocessor") or "").lower()
        with self._lock:
            if data.get("status") == "started":
                if self._saved_label is None:
                    self._saved_label = self.label
                self.label = "🔧 Merging" if "merg" in name else "🔧 Processing"
            elif data.get("status") == "finished" and self._saved_label is not None:
                self.label = self._saved_label
                self._saved_label = None

    def _loop(self):
        while not self._stop.wait(0.5):
            self._render()

    def _render(self):
        with self._lock:
            if self._paused:
                return
            multi = self.total_items > 1
            overall = (self.done_items + self._frac) / self.total_items
            overall = max(0.0, min(overall, 1.0))
            filled = int(self.BAR_WIDTH * overall)
            bar = "█" * filled + "░" * (self.BAR_WIDTH - filled)

            parts = []
            if multi:
                parts.append(f"{self.done_items}/{self.total_items} videos")
            else:
                done = self._base_done + self._stream_done
                total = self._base_total + (self._stream_total or 0)
                if total:
                    parts.append(f"{format_bytes(done)}/{format_bytes(total)}")
                elif done:
                    parts.append(format_bytes(done))
            if self._speed:
                parts.append(f"{format_bytes(self._speed)}/s")
            eta = self._estimate_eta(multi)
            if eta is not None:
                parts.append(f"ETA {format_eta(eta)}")

            line = f"{self.label} |{bar}| {overall * 100:5.1f}% " + " · ".join(parts)
            line = line.rstrip()
            pad = max(0, self._last_len - len(line))
            sys.stdout.write("\r" + line + (" " * pad))
            sys.stdout.flush()
            self._last_len = len(line)

    def _estimate_eta(self, multi):
        if not multi:
            return self._eta
        progressed = self._run_done + self._frac
        if progressed <= 0:
            return None
        elapsed = max(time.time() - self._start, 0.001)
        remaining = self.total_items - self.done_items - self._frac
        return elapsed / progressed * max(remaining, 0)
