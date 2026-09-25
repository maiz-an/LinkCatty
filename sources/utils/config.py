import json
import re
import socket
from copy import deepcopy
from urllib.parse import urlsplit
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
    },
    "network": {
        # Optional proxy for Other Downloaders, used only when a direct
        # connection is blocked. Example: socks5://127.0.0.1:1080
        "proxy": ""
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

# ---------------------------------------------------------------------
#  Network helpers (Other Downloaders): direct first, proxy only if blocked
# ---------------------------------------------------------------------
_BLOCK_PATTERN = re.compile(
    r"connection was reset|curl: \(35\)|\bssl|time(d )?out|connection refused|"
    r"connection aborted|remote end closed|name or service not known|"
    r"curl: \(7\)|failed to connect|could not connect to server",
    re.IGNORECASE,
)
_PROXY_PATTERN = re.compile(r"^(https?|socks4a?|socks5h?)://\S+$", re.IGNORECASE)


def is_block_error(exc):
    """True when an error looks like the connection itself was cut/blocked."""
    return bool(_BLOCK_PATTERN.search(str(exc)))


def get_proxy(config):
    return str((config.get("network") or {}).get("proxy") or "").strip()


def is_valid_proxy(value):
    return bool(_PROXY_PATTERN.match(value))


def proxy_endpoint(value):
    """Return (host, port) of a proxy URL, using the scheme's default port."""
    parts = urlsplit(value)
    default = {"http": 80, "https": 443}.get(parts.scheme.lower(), 1080)
    return parts.hostname or "", parts.port or default


def proxy_is_running(value, timeout=2.0):
    """True if something accepts TCP connections at the proxy address."""
    host, port = proxy_endpoint(value)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def mask_proxy(value):
    """Hide the password in scheme://user:pass@host:port for display."""
    return re.sub(r"(//[^:/@\s]+):[^@\s]*@", r"\1:***@", value)


def run_with_proxy_fallback(func, config, proxy=None):
    """Call func(proxy) and return (result, proxy_used).

    Starts with `proxy` (None = direct connection). If that fails with a
    connection-block error and a proxy is configured in Settings, retries
    once through it. Any other error, or a failure through the proxy,
    is raised unchanged.
    """
    configured = get_proxy(config)
    try:
        return func(proxy), proxy
    except Exception as exc:
        if configured and proxy != configured and is_block_error(exc):
            return func(configured), configured
        raise


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
    but keep any user-set Spotify API credentials and network proxy.

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
            old_proxy = (old.get("network") or {}).get("proxy")
            if old_proxy:
                fresh["network"]["proxy"] = old_proxy
        except Exception:
            pass

    save_config(fresh)
    fresh['ffmpeg_path'] = get_ffmpeg_path()
    return fresh