import sys
import os
import time
import threading

_spinner_running = False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    banner = """
╔══════════════════════════════════════════════╗
║            🚀 LinkCaty Downloader 🚀         ║
║       YouTube · Spotify · More               ║
╚══════════════════════════════════════════════╝
    """
    print(banner)

def print_main_menu():
    print("\n" + "═" * 55)
    print("            🎯 MAIN MENU")
    print("═" * 55)
    print("1. 📹 YouTube Downloader")
    print("2. 🎵 Spotify Downloader")
    print("3. 🛠️  Other (coming soon)")
    print("4. ⚙️  Settings")
    print("5. ❌ Exit")
    print("═" * 55)

def start_spinner(text="⏳ Processing"):
    global _spinner_running
    _spinner_running = True
    def _spin():
        chars = "\\|/-"
        idx = 0
        while _spinner_running:
            sys.stdout.write(f"\r{text} {chars[idx]}")
            sys.stdout.flush()
            time.sleep(0.15)
            idx = (idx + 1) % len(chars)
    threading.Thread(target=_spin, daemon=True).start()

def stop_spinner():
    global _spinner_running
    _spinner_running = False
    time.sleep(0.2)
    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()