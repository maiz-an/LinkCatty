import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
HISTORY_FILE = BASE_DIR / "download_history.json"

def log_download(source, title, artist=None, mode="", status="Success", error=""):
    """Log a download attempt."""
    try:
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "title": title,
            "artist": artist or "",
            "mode": mode,
            "status": status,
            "error": error
        }
        history = []
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        history.append(entry)
        # Keep last 200 entries
        if len(history) > 200:
            history = history[-200:]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def show_history():
    """Display download history."""
    if not HISTORY_FILE.exists():
        print("\n❌ No download history found.")
        return
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        if not history:
            print("\n❌ No download history found.")
            return
        print("\n" + "═" * 90)
        print("                            📊 DOWNLOAD HISTORY")
        print("═" * 90)
        print(f"{'Date/Time':<20} {'Source':<10} {'Status':<10} {'Title'}")
        print("-" * 90)
        for entry in reversed(history[-20:]):
            title = entry.get('title', 'Unknown')
            if len(title) > 50:
                title = title[:47] + "..."
            print(f"{entry['timestamp']:<20} {entry['source']:<10} {entry['status']:<10} {title}")
        print("═" * 90)
        input("\nPress Enter to continue...")
    except Exception as e:
        print(f"❌ Error reading history: {e}")

def clear_history():
    """Delete history file."""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()