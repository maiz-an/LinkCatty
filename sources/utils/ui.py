import sys
import os
import time
import threading
import platform

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

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Print the LinkCaty logo with colors."""
    logo = f"""
{CYAN}{BOLD}██     ▄▄ ▄▄  ▄▄ ▄▄ ▄▄ ▄█████  ▄▄▄ ▄▄▄▄▄▄ ▄▄▄▄▄▄ ▄▄ ▄▄ 
██     ██ ███▄██ ██▄█▀ ██     ██▀██  ██     ██   ▀███▀ 
██████ ██ ██ ▀██ ██ ██ ▀█████ ██▀██  ██     ██     █{RESET}
    """
    print(logo)
    print(f"{BOLD}{CYAN}╔{'═' * 50}╗{RESET}")
    print(f"{BOLD}{CYAN}║{' ' * 12}🚀 LinkCaty Universal Downloader{' ' * 12}║{RESET}")
    print(f"{BOLD}{CYAN}║{' ' * 14}YouTube · Spotify · More{' ' * 16}║{RESET}")
    print(f"{BOLD}{CYAN}╚{'═' * 50}╝{RESET}\n")

def print_main_menu():
    print(f"{BOLD}{YELLOW}{'═' * 55}{RESET}")
    print(f"{BOLD}{WHITE}            🎯 MAIN MENU{RESET}")
    print(f"{BOLD}{YELLOW}{'═' * 55}{RESET}")
    print(f"{GREEN}1.{RESET} 📹 YouTube Downloader")
    print(f"{GREEN}2.{RESET} 🎵 Spotify Downloader")
    print(f"{GREEN}3.{RESET} 🛠️  Other (coming soon)")
    print(f"{GREEN}4.{RESET} ⚙️  Settings")
    print(f"{GREEN}5.{RESET} ❌ Exit")
    print(f"{BOLD}{YELLOW}{'═' * 55}{RESET}")

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