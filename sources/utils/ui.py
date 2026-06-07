import sys
import os
import time
import threading
import platform
import shutil

# ANSI color codes (Windows 10+ supports them, older Windows will fallback)
if platform.system() == "Windows":
    # Enable ANSI support for Windows 10+
    os.system("")  # This enables ANSI escape sequences
RESET = "\033[0m"
BOLD = "\033[1m"
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
    """Attempt to set console width to the specified number of characters."""
    system = platform.system()
    try:
        if system == "Windows":
            # Use mode command to set columns and rows (rows optional)
            os.system(f"mode con cols={width} lines=30")
        else:
            # For macOS/Linux: use stty or escape sequence
            # Option 1: stty (works on most Unix terminals)
            os.system(f"stty cols {width}")
            # Option 2: fallback escape sequence for xterm-like terminals
            # (works in many terminal emulators)
            sys.stdout.write(f"\x1b[8;30;{width}t")
            sys.stdout.flush()
    except Exception:
        pass  # Silently fail if unsupported

def clear_screen():
    if os.name == 'nt':
        os.system('cls')
        return
    if shutil.which('clear'):
        os.system('clear')

def print_banner():
    """Print the LinkCatty logo with colors."""
    logo = f"""
=============================================================

{CYAN}{BOLD}    ██     ▄▄ ▄▄  ▄▄ ▄▄ ▄▄ ▄█████  ▄▄▄ ▄▄▄▄▄▄ ▄▄▄▄▄▄ ▄▄ ▄▄ 
    ██     ██ ███▄██ ██▄█▀ ██     ██▀██  ██     ██   ▀███▀ 
    ██████ ██ ██ ▀██ ██ ██ ▀█████ ██▀██  ██     ██     █{RESET}

============================================================="""
    print(logo)

def print_main_menu():
    print(f"{BOLD}{WHITE}                       🐈‍⬛ MAIN MENU{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 61}{RESET}")
    print(f"")
    print(f"{CYAN}{BOLD}1.{RESET}{BOLD} YouTube Downloader")
    print(f"{CYAN}{BOLD}2.{RESET}{BOLD} Spotify Downloader")
    print(f"{CYAN}{BOLD}3.{RESET}{BOLD} Other (coming soon)")
    print(f"{CYAN}{BOLD}4.{RESET}{BOLD} Settings")
    print(f"{CYAN}{BOLD}5.{RESET}{BOLD} Exit")
    print(f"")
    print(f"{BOLD}{CYAN}{'=' * 61}{RESET}")

def print_error(message, suggestion=None):
    """Print a formatted error message with optional suggestion."""
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
    """Pause after a screen message without letting Ctrl+C crash a submenu."""
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

def menu_choice(prompt, valid_choices, back_choices=None):
    """Read a single-key menu choice and validate it."""
    valid = {str(choice) for choice in valid_choices}
    back = set(back_choices or [])
    while True:
        print(prompt, end="", flush=True)
        choice = read_key()
        print(choice if choice not in ("\r", "\n", "\x03") else "")
        if choice == "\x03":
            return None
        if choice in valid or choice in back:
            return choice
        print_error(
            f"Invalid choice: {choice or '<empty>'}",
            f"Press one of: {', '.join(sorted(valid | back))}"
        )

def confirm(prompt, default=False):
    """Read a y/n answer as a single-key option."""
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        print(prompt + suffix, end="", flush=True)
        choice = read_key().lower()
        print(choice if choice not in ("\r", "\n", "\x03") else "")
        if choice == "\x03":
            return False
        if choice in ("\r", "\n", ""):
            return default
        if choice in ("y", "n"):
            return choice == "y"
        print_error("Invalid answer", "Press y or n")

def start_spinner(text="Processing"):
    """Start an animated spinner in a separate thread."""
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
    """Display a colored progress bar."""
    percent = current / total
    filled = int(length * percent)
    bar = f"{GREEN}{'█' * filled}{RESET}{'░' * (length - filled)}"
    sys.stdout.write(f"\r{prefix} |{bar}| {percent:.1%} {suffix}")
    sys.stdout.flush()
