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
        "audio_quality": "320k",
        "video_quality": "best",
        "auto_retry": True,
        "max_retries": 3,
        "quiet_mode": True,

        # parallel downloads + retry passes
        "parallel_downloads": 3,
        "max_retry_passes": 3,
        "retry_delay_seconds": 8,

        # metadata sidecars (one file per video)
        "save_metadata": True,
        "save_thumbnail": True,
        "save_description": False,

        # embed metadata directly into the media file
        "embed_metadata": True,
        "embed_thumbnail": False,
    },
    "spotify": {
        "client_id": "",
        "client_secret": "",
        "audio_format": "mp3",
        "audio_quality": "320k",
        "auto_retry": True,
        "max_retries": 3,
        "quiet_mode": True,

        # multi-pass retry + pacing
        "threads": 2,
        "max_retry_passes": 4,
        "retry_delay_seconds": 8,

        # parallel batching (speed)
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
    """Return the current LinkCatty version as a plain string."""
    try:
        if VERSION_FILE.exists():
            value = VERSION_FILE.read_text(encoding="utf-8-sig").strip()
            if value:
                return value
    except Exception:
        pass
    return "dev"

def load_config():
    config = deepcopy(DEFAULT_CONFIG)

    if not CONFIG_FILE.exists():
        # First run: write the defaults to disk so users have a real
        # settings.json to edit.
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

def reset_to_defaults():
    """Overwrite settings.json with a fresh copy of DEFAULT_CONFIG,
    but keep any user-set Spotify API credentials.

    Returns the new config dict so the caller can swap it into the
    running session without restarting.
    """
    fresh = deepcopy(DEFAULT_CONFIG)

    # Preserve credentials if the user already had them.
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                old = json.load(f)
            old_spotify = old.get("spotify", {})
            if old_spotify.get("client_id"):
                fresh["spotify"]["client_id"] = old_spotify["client_id"]
            if old_spotify.get("client_secret"):
                fresh["spotify"]["client_secret"] = old_spotify["client_secret"]
        except Exception:
            pass

    save_config(fresh)
    fresh['ffmpeg_path'] = get_ffmpeg_path()
    return fresh