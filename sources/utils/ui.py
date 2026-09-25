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
    text = _ANSI.sub("", str(exc)).strip()
    text = text.split("; please report")[0]
    text = re.sub(r"^ERROR:\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*\S+:\s*", "", text)
    text = _URL.sub("", text)
    text = re.sub(r"\s*See\s+first for more details\.?", "", text).strip()
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
            "To use a proxy for blocked links:\n"
            "   1. Main menu > 4. Settings > 7. Network proxy\n"
            "   2. Enter your proxy address, e.g.\n"
            "      socks5://127.0.0.1:1080\n"
            "   It is only used when a direct connection is blocked.",
        )
    return text, "Check the URL and your internet connection."
