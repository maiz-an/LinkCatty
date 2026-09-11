import json
from copy import deepcopy
from pathlib import Path
from .ffmpeg import get_ffmpeg_path

# Now inside sources/utils/
BASE_DIR = Path(__file__).parent.parent  # sources folder
CONFIG_FILE = BASE_DIR / "settings.json"
VERSION_FILE = BASE_DIR / "version.txt"

# Download folder stays in root (user's files)
ROOT_DIR = BASE_DIR.parent
DEFAULT_DOWNLOAD_DIR = str(ROOT_DIR / "downloads")

DEFAULT_CONFIG = {
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "youtube": {
        "audio_quality": "320k",       # for MP3 only
        "video_quality": "best",       # best, 2160p, 1440p, 1080p, 720p, 480p, 360p
        "auto_retry": True,
        "max_retries": 3,
        "quiet_mode": True,

        # ── parallel downloads + retry passes ─────────────────────────
        "parallel_downloads": 3,       # concurrent yt-dlp instances
        "max_retry_passes": 3,         # total attempts per playlist
        "retry_delay_seconds": 8,      # cooldown between retry passes

        # ── metadata sidecars (one file per video) ────────────────────
        "save_metadata": True,         # writes  <title>.info.json
        "save_thumbnail": True,        # writes  <title>.webp / .jpg
        "save_description": False,     # writes  <title>.description

        # ── embed metadata directly into the media file ───────────────
        "embed_metadata": True,        # ID3 / MP4 tags (title, artist, etc.)
        "embed_thumbnail": False,      # cover art inside the file
    },
    "spotify": {
        "client_id": "",
        "client_secret": "",
        "audio_format": "mp3",       # mp3, flac, m4a, opus, ogg, wav
        "audio_quality": "320k",
        "auto_retry": True,
        "max_retries": 3,
        "quiet_mode": True,

        # ── multi-pass retry + pacing ─────────────────────────────────
        "threads": 2,
        "max_retry_passes": 4,
        "retry_delay_seconds": 8,

        # ── parallel batching (speed) ─────────────────────────────────
        "parallel_batches": 3,
        "batch_size": 10,
        "batch_cooldown_min": 1,
        "batch_cooldown_max": 3,
        "blocked_cooldown_seconds": 45
    },
    "common": {
        "enable_logging": True,
        "history_limit": 100
    }
}

def get_version():
    """Return the current LinkCatty version as a plain string.

    Reads `sources/version.txt` (written by the installer / updater).
    Falls back to "dev" when the file is missing or empty so the UI
    still renders something sensible in a dev checkout.
    """
    try:
        if VERSION_FILE.exists():
            value = VERSION_FILE.read_text(encoding="utf-8").strip()
            if value:
                return value
    except Exception:
        pass
    return "dev"

def load_config():
    config = deepcopy(DEFAULT_CONFIG)

    if not CONFIG_FILE.exists():
        # First run: write the defaults to disk so users have a real
        # settings.json to edit. save_config() strips ffmpeg_path, so
        # we pass the clean copy, not the runtime one.
        try:
            save_config(config)
        except Exception as e:
            print(f"⚠️ Could not create default settings.json: {e}")
    else:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                if not isinstance(user_config, dict):
                    raise ValueError("settings.json must contain a JSON object")
                for section, values in user_config.items():
                    if section in config:
                        if isinstance(config[section], dict) and isinstance(values, dict):
                            config[section].update(values)
                        elif not isinstance(config[section], dict):
                            config[section] = values
                    else:
                        config[section] = values
        except Exception as e:
            print(f"⚠️ Could not read settings.json. Defaults loaded instead: {e}")

    config['ffmpeg_path'] = get_ffmpeg_path()
    return config

def save_config(config):
    to_save = {k: v for k, v in config.items() if k != 'ffmpeg_path'}
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Could not save config: {e}")