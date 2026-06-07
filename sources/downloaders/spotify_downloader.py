import os
import shutil
import subprocess
import re
import json
import urllib.request
import urllib.parse
from pathlib import Path

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    print_warning,
    BOLD,
    CYAN,
    GREEN,
    YELLOW,
    RESET,
    clear_screen,
    confirm,
    menu_choice,
    pause,
    print_banner,
    print_error,
    print_info,
    print_success,
    start_spinner,
    stop_spinner,
)

# ─────────────────────────────────────────────────────────────────────
#  spotdl imports  (metadata only – no official Spotify API ever)
# ─────────────────────────────────────────────────────────────────────
try:
    from spotdl.utils.spotify import SpotifyClient
    from spotdl.types.playlist import Playlist as SpotPlaylist
    from spotdl.types.album   import Album    as SpotAlbum
    _SPOTDL_AVAILABLE = True
except ImportError:
    SpotifyClient = None
    SpotPlaylist  = None
    SpotAlbum     = None
    _SPOTDL_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────
#  Deno – install once per process, never again
# ─────────────────────────────────────────────────────────────────────
_DENO_READY = False


def _ensure_deno(spotdl_path: str) -> None:
    global _DENO_READY
    if _DENO_READY:
        return
    if shutil.which("deno"):
        _DENO_READY = True
        return
    print_info("Deno not found – installing automatically (one-time setup)…")
    try:
        proc = subprocess.Popen(
            [spotdl_path, "--download-deno"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        proc.communicate(input="y\n", timeout=90)
        if shutil.which("deno"):
            print_success("Deno installed successfully.")
        else:
            print_warning("Deno may not have installed correctly. Some downloads could fail.")
    except Exception as exc:
        print_warning(f"Could not install Deno automatically: {exc}")
    _DENO_READY = True  # never retry regardless of outcome


# ─────────────────────────────────────────────────────────────────────
#  SpotifyClient – FREE MODE ONLY  (SpotipyFree / no credentials)
#
#  WHY: the official Spotify Web API (client_id + client_secret) now
#  requires a premium developer subscription even for read-only calls.
#  spotdl ships a free, unofficial client (SpotipyFree) that works for
#  every user with zero credentials.  We always use that for metadata.
#  The user's credentials (if any) are passed to the spotdl *CLI* only
#  so spotdl can resolve playlist/album track lists during download.
# ─────────────────────────────────────────────────────────────────────
_FREE_CLIENT = None   # module-level singleton


def _get_free_client():
    """
    Return a SpotipyFree client, initialised once per process.
    Always uses free/unofficial mode – credentials are intentionally
    never passed here.
    """
    global _FREE_CLIENT
    if _FREE_CLIENT is not None:
        return _FREE_CLIENT

    if SpotifyClient is None:
        return None

    # Reset class singleton so we can (re-)init cleanly
    if SpotifyClient._instance is not None:
        # Already initialised elsewhere – just use it
        try:
            _FREE_CLIENT = SpotifyClient()
            return _FREE_CLIENT
        except Exception:
            pass

    try:
        _FREE_CLIENT = SpotifyClient.init(
            client_id="",
            client_secret="",
            use_official_api=False,   # ← always free / SpotipyFree
        )
    except Exception:
        try:
            _FREE_CLIENT = SpotifyClient()
        except Exception:
            _FREE_CLIENT = None

    return _FREE_CLIENT


# ─────────────────────────────────────────────────────────────────────
#  Display helpers
# ─────────────────────────────────────────────────────────────────────

def _display_track_info(info: dict) -> None:
    print("\n" + "─" * 61)
    print("🎵 TRACK INFORMATION")
    print("─" * 61)
    print(f"🎶 Title  : {info.get('title') or 'Unknown'}")
    print(f"🎤 Artist : {info.get('artist') or 'Unknown'}")
    if info.get("album"):
        print(f"💿 Album  : {info['album']}")
    print("─" * 61)


def _display_album_info(info: dict) -> None:
    print("\n" + "─" * 61)
    print("💿 ALBUM INFORMATION")
    print("─" * 61)
    print(f"💿 Album       : {info.get('name') or 'Unknown'}")
    if info.get("artist"):
        print(f"🎤 Artist      : {info['artist']}")
    tc = info.get("track_count")
    print(f"🎬 Total Tracks: {tc if tc is not None else 'Unknown'}")
    print("─" * 61)


def _display_playlist_info(info: dict) -> None:
    print("\n" + "─" * 61)
    print("📂 PLAYLIST INFORMATION")
    print("─" * 61)
    print(f"📋 Playlist    : {info.get('name') or 'Unknown'}")
    if info.get("author"):
        print(f"👤 Author      : {info['author']}")
    tc = info.get("track_count")
    print(f"🎬 Total Tracks: {tc if tc is not None else 'Unknown'}")
    print("─" * 61)


def _display_download_result(item_type: str, name: str | None,
                              out_folder: str, downloaded: int) -> None:
    print("\n" + "─" * 61)
    print("✅ DOWNLOAD COMPLETE")
    print("─" * 61)
    if name:
        label = {"track": "🎶 Track", "album": "💿 Album", "playlist": "📋 Playlist"}[item_type]
        print(f"{label}    : {name}")
    print(f"📁 Saved to  : {out_folder}")
    print(f"🎵 Files     : {downloaded} audio file(s)")
    print("─" * 61)


# ─────────────────────────────────────────────────────────────────────
#  SpotifyDownloader
# ─────────────────────────────────────────────────────────────────────

class SpotifyDownloader:
    def __init__(self, config):
        self.config        = config
        self.spotify_config = config["spotify"]
        self.download_dir  = Path(config["download_dir"])
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.spotdl_path = shutil.which("spotdl")
        if not self.spotdl_path:
            raise RuntimeError(
                "spotdl is not installed or not in PATH.\n"
                "  → Run: pip install spotdl"
            )

        # Credentials are only ever forwarded to the spotdl CLI, never used
        # to initialise the metadata client (which is always free mode).
        self.client_id     = self.spotify_config.get("client_id", "").strip()
        self.client_secret = self.spotify_config.get("client_secret", "").strip()

        # Free client for metadata (no credentials, no premium required)
        self._client = _get_free_client()

        # Ensure Deno is available (one-time install)
        _ensure_deno(self.spotdl_path)

    # ── metadata ──────────────────────────────────────────────────────

    def _get_playlist_meta(self, url: str) -> dict:
        meta = {"name": None, "author": None, "track_count": None}
        if SpotPlaylist is not None and self._client is not None:
            try:
                pl_meta, songs    = SpotPlaylist.get_metadata(url)
                meta["name"]        = pl_meta.get("name")
                meta["author"]      = pl_meta.get("author_name")
                meta["track_count"] = len(songs)
                return meta
            except Exception:
                pass
        meta["name"] = _oembed_title(url)   # last-resort fallback
        return meta

    def _get_album_meta(self, url: str) -> dict:
        meta = {"name": None, "artist": None, "track_count": None}
        if SpotAlbum is not None and self._client is not None:
            try:
                al_meta, songs    = SpotAlbum.get_metadata(url)
                meta["name"]        = al_meta.get("name")
                meta["artist"]      = al_meta.get("artist")
                meta["track_count"] = len(songs)
                return meta
            except Exception:
                pass
        title = _oembed_title(url)
        if title:
            meta["name"] = re.sub(r"\s*[-–|].*$", "", title).strip()
        return meta

    def _get_track_meta(self, url: str) -> dict:
        meta = {"title": None, "artist": None, "album": None}
        if self._client is not None:
            try:
                track_id = url.split("/track/")[-1].split("?")[0]
                tr = self._client.track(track_id)
                meta["title"]  = tr.get("name")
                artists = tr.get("artists", [])
                if artists:
                    a = artists[0]
                    meta["artist"] = a.get("name") if isinstance(a, dict) else str(a)
                alb = tr.get("album")
                if isinstance(alb, dict):
                    meta["album"] = alb.get("name")
                return meta
            except Exception:
                pass
        title = _oembed_title(url)
        if title:
            parts = title.split(" - ", 1)
            meta["title"]  = parts[0].strip()
            meta["artist"] = parts[1].strip() if len(parts) > 1 else None
        return meta

    # ── core download ─────────────────────────────────────────────────

    def _spotdl_download(self, url: str, item_type: str,
                          meta_name: str | None = None) -> tuple:
        """
        Run spotdl CLI and return (success, out_folder, file_count).

        Metadata is fetched via the free client above.
        The CLI handles its own Spotify token internally (also free).
        Credentials are passed to the CLI only if the user explicitly
        configured them (optional speed/reliability improvement).
        """
        quality  = self.spotify_config.get("audio_quality", "320k").replace("k", "")
        base_dir = str(self.download_dir)

        if item_type in ("album", "playlist"):
            folder_name = _safe_name(meta_name) if meta_name else f"{{{item_type}}}"
            out_dir  = os.path.join(base_dir, folder_name)
            template = os.path.join(out_dir, "{title} - {artists}.{ext}")
        else:
            out_dir  = base_dir
            template = os.path.join(out_dir, "{title} - {artists}.{ext}")

        cmd = ["spotdl", url, "--output", template, "--bitrate", f"{quality}k"]
        # Only pass credentials to CLI if user configured them
        if self.client_id and self.client_secret:
            cmd += ["--client-id", self.client_id, "--client-secret", self.client_secret]

        print_info(f"Output folder : {out_dir}")
        print()

        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, bufsize=1,
        ) as proc:
            for line in proc.stdout:
                print(line, end="")
            proc.wait()

        actual = _find_output_folder(self.download_dir, meta_name)
        count  = _count_audio_files(actual)
        return count > 0, actual, count

    # ── public entry-points ───────────────────────────────────────────

    def download_single_track(self, url: str) -> None:
        meta = self._get_track_meta(url)
        _display_track_info(meta)
        if not confirm("Proceed with download?"):
            return
        success, out_folder, n = self._spotdl_download(url, "track")
        if success:
            _display_download_result("track", meta.get("title"), out_folder, n)
            log_download("Spotify", url, artist=meta.get("artist", "spotdl"),
                         mode="Single", status="Success")
        else:
            print_error("Download failed – no audio file was created.")
            log_download("Spotify", url, artist="spotdl", mode="Single", status="Failed")

    def download_album(self, url: str) -> None:
        meta = self._get_album_meta(url)
        _display_album_info(meta)
        if not confirm("Download all tracks?"):
            return
        success, out_folder, n = self._spotdl_download(url, "album", meta_name=meta["name"])
        if success:
            _display_download_result("album", meta["name"], out_folder, n)
            log_download("Spotify", url, artist="spotdl", mode="Album", status="Success")
        else:
            print_error("Album download failed – no tracks were saved.")
            log_download("Spotify", url, artist="spotdl", mode="Album", status="Failed")

    def download_playlist(self, url: str) -> None:
        meta = self._get_playlist_meta(url)
        _display_playlist_info(meta)
        if not confirm("Download all tracks?"):
            return
        success, out_folder, n = self._spotdl_download(url, "playlist", meta_name=meta["name"])
        if success:
            _display_download_result("playlist", meta["name"], out_folder, n)
            log_download("Spotify", url, artist="spotdl", mode="Playlist", status="Success")
        else:
            print_error("Playlist download failed – no tracks were saved.")
            log_download("Spotify", url, artist="spotdl", mode="Playlist", status="Failed")


# ─────────────────────────────────────────────────────────────────────
#  Standalone helpers
# ─────────────────────────────────────────────────────────────────────

def _oembed_title(url: str) -> str | None:
    """Last-resort title via Spotify oEmbed (no credentials needed)."""
    try:
        api = "https://open.spotify.com/oembed?url=" + urllib.parse.quote(url, safe="")
        req = urllib.request.Request(
            api,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()).get("title", "").strip() or None
    except Exception:
        return None


def _safe_name(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r'[\\/*?:"<>|]', "", name).strip() or None


def _find_output_folder(download_dir: Path, meta_name: str | None) -> str:
    base = str(download_dir)
    safe = _safe_name(meta_name)
    if safe:
        candidate = os.path.join(base, safe)
        if os.path.isdir(candidate):
            return candidate
    try:
        subdirs = [
            os.path.join(base, d)
            for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d))
        ]
        if subdirs:
            return max(subdirs, key=os.path.getmtime)
    except Exception:
        pass
    return base


def _count_audio_files(folder: str) -> int:
    exts = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav"}
    count = 0
    for root, _, files in os.walk(folder):
        for f in files:
            if Path(f).suffix.lower() in exts:
                count += 1
    return count


def extract_spotify_id(url: str, item_type: str) -> str | None:
    m = re.search(rf"{item_type}/([a-zA-Z0-9]+)", url)
    return m.group(1) if m else None


def is_spotify_url(url: str, item_type: str) -> bool:
    return bool(re.match(r"^https?://", url)) and f"spotify.com/{item_type}/" in url


# ─────────────────────────────────────────────────────────────────────
#  Workflow runners
# ─────────────────────────────────────────────────────────────────────

def create_downloader(config):
    try:
        return SpotifyDownloader(config)
    except Exception as err:
        print_error(str(err))
        return None


def run_spotify_workflow(config, choice: str) -> None:
    downloader = create_downloader(config)
    if downloader is None:
        pause()
        return

    item_type = {"1": "track", "2": "album", "3": "playlist"}[choice]
    while True:
        url = input(f"\n🎯 Enter Spotify {item_type} URL (blank to go back): ").strip()
        if not url:
            return
        if not is_spotify_url(url, item_type):
            print_error(
                f"Invalid Spotify {item_type} URL",
                f"Use a link containing spotify.com/{item_type}/.",
            )
            continue

        if choice == "1":
            downloader.download_single_track(url)
        elif choice == "2":
            downloader.download_album(url)
        elif choice == "3":
            downloader.download_playlist(url)

        if not confirm(f"\nProcess another Spotify {item_type}?"):
            return


def run(config) -> None:
    while True:
        clear_screen()
        print_banner()
        print(f"{BOLD}                   🎵 Spotify Downloader")
        print("=" * 61)
        print()
        print(f"{CYAN}{BOLD}1.{RESET} Download single track")
        print(f"{CYAN}{BOLD}2.{RESET} Download album")
        print(f"{CYAN}{BOLD}3.{RESET} Download playlist")
        print(f"{CYAN}{BOLD}4.{RESET} Back to main menu")
        print()
        print("=" * 61)
        choice = menu_choice("Select (1-4): ", "1234")
        if choice in (None, "4"):
            return
        try:
            run_spotify_workflow(config, choice)
        except Exception as err:
            stop_spinner()
            print_error(
                f"Spotify workflow error: {err}",
                "You remain in the Spotify Downloader.",
            )
            pause()