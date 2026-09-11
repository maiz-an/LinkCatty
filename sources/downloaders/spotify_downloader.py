import os
import shutil
import subprocess
import re
import json
import time
import threading
import urllib.request
import urllib.parse
from datetime import datetime
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
    progress_bar,
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


def _deno_already_available() -> bool:
    """
    spotdl keeps its own private copy of Deno inside its app directory
    (NOT on the system PATH) when it self-installs via --download-deno.
    A plain `shutil.which("deno")` check only sees a system-wide/PATH
    install, so it misses spotdl's own copy — which meant this used to
    re-run `--download-deno` on every single launch. Ask spotdl itself
    where it thinks Deno is (it checks both locations) before falling
    back to a PATH-only check on older spotdl versions.
    """
    try:
        from spotdl.utils.deno import get_deno_path
        return get_deno_path() is not None
    except Exception:
        return bool(shutil.which("deno"))


def _ensure_deno(spotdl_path: str) -> None:
    global _DENO_READY
    if _DENO_READY:
        return
    if _deno_already_available():
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
        if _deno_already_available():
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

def _show_session_header(section_title: str) -> None:
    """Clear the leftover menu text and redraw just the banner + a
    section title, so the info panel below it isn't stacked underneath
    the numbered menu the user already picked from."""
    clear_screen()
    print_banner()
    print(f"{BOLD}                   {section_title}{RESET}")
    print("=" * 61)


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


def _display_download_result(item_type: str, name: str | None, out_folder: str,
                              downloaded: int, expected: int,
                              failed_report: str | None) -> None:
    print("\n" + "─" * 61)
    if failed_report is None:
        print("✅ DOWNLOAD COMPLETE — everything downloaded")
    else:
        print("⚠️  DOWNLOAD FINISHED WITH MISSING TRACKS")
    print("─" * 61)
    if name:
        label = {"track": "🎶 Track", "album": "💿 Album", "playlist": "📋 Playlist"}[item_type]
        print(f"{label}    : {name}")
    print(f"📁 Saved to  : {out_folder}")
    print(f"🎵 Files     : {downloaded}/{expected} audio file(s)")
    if failed_report is not None:
        missing = max(expected - downloaded, 0)
        print(f"❌ Missing   : {missing}")
        print(f"📝 Failed list saved to : {failed_report}")
    print("─" * 61)


# ─────────────────────────────────────────────────────────────────────
#  Progress bar (custom, spotdl-style, but stable/predictable)
#
#  We deliberately don't try to parse spotdl's own Rich TUI output –
#  it repaints in place with ANSI codes and its format isn't a stable
#  contract. Instead we redirect spotdl's raw output to a log file
#  (kept for debugging) and drive our own bar off something we fully
#  control: the number of audio files that actually landed on disk.
# ─────────────────────────────────────────────────────────────────────

def _progress_loop(out_dir: str, expected_total: int, stop_event: threading.Event,
                    label: str, interval: float = 1.0) -> None:
    start = time.time()
    expected_total = max(expected_total, 1)
    while not stop_event.is_set():
        count = _count_audio_files(out_dir)
        elapsed = max(time.time() - start, 0.001)
        rate = count / elapsed
        remaining = max(expected_total - count, 0)
        suffix = f"{count}/{expected_total} tracks"
        if rate > 0 and remaining > 0:
            eta = int(remaining / rate)
            suffix += f" · ETA {eta}s"
        progress_bar(count, expected_total, prefix=label, suffix=suffix)
        stop_event.wait(interval)
    count = _count_audio_files(out_dir)
    progress_bar(count, expected_total, prefix=label, suffix=f"{count}/{expected_total} tracks")
    print()  # move off the \r line once the pass is done


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

    # ── core download (with automatic retry passes) ────────────────────

    def _spotdl_download(self, url: str, item_type: str,
                          meta_name: str | None = None,
                          expected_total: int | None = None) -> tuple:
        """
        Run spotdl, then automatically re-run against only the tracks
        that are still missing, using spotdl's own --archive file so
        already-downloaded songs are always skipped. Repeats up to
        `max_retry_passes` times (config), with a cooldown between
        passes to ride out YouTube/Spotify rate limits.

        Returns (final_count, out_dir, expected_total, failed_report_path).
        failed_report_path is None when everything downloaded cleanly.
        """
        audio_format = self.spotify_config.get("audio_format", "mp3").lower()
        quality  = self.spotify_config.get("audio_quality", "320k").replace("k", "")
        # FLAC/WAV are lossless — a bitrate target doesn't apply to them.
        bitrate_arg = "disable" if audio_format in ("flac", "wav") else f"{quality}k"
        base_dir = str(self.download_dir)

        if item_type in ("album", "playlist"):
            folder_name = _safe_name(meta_name) if meta_name else f"{{{item_type}}}"
            out_dir  = os.path.join(base_dir, folder_name)
        else:
            out_dir  = base_dir
        template = os.path.join(out_dir, "{title} - {artists}.{ext}")
        os.makedirs(out_dir, exist_ok=True)

        expected_total = expected_total or 1

        archive_file = os.path.join(out_dir, ".spotdl_archive.spotdl")
        errors_file  = os.path.join(out_dir, ".spotdl_errors.txt")
        log_file     = os.path.join(out_dir, ".spotdl_log.txt")

        max_passes = int(self.spotify_config.get("max_retry_passes", 4))
        cooldown   = int(self.spotify_config.get("retry_delay_seconds", 15))
        base_threads = int(self.spotify_config.get("threads", 4))

        print_info(f"Output folder : {out_dir}")

        errors = []
        for attempt in range(1, max_passes + 1):
            # Ease off on later passes: fewer parallel threads + more
            # internal retries, since leftovers are usually the ones
            # that hit rate limits or transient network errors.
            threads = base_threads if attempt == 1 else max(1, base_threads // 2)
            max_retries = 5 if attempt == 1 else 8

            if os.path.exists(errors_file):
                os.remove(errors_file)  # capture only this pass's errors

            cmd = [
                "spotdl", url,
                "--output", template,
                "--format", audio_format,
                "--bitrate", bitrate_arg,
                "--threads", str(threads),
                "--max-retries", str(max_retries),
                "--archive", archive_file,
                "--save-errors", errors_file,
                "--overwrite", "skip",
            ]
            if self.client_id and self.client_secret:
                cmd += ["--client-id", self.client_id, "--client-secret", self.client_secret]

            label = f"⬇ Pass {attempt}/{max_passes}"
            print_info(f"{label} — downloading…" if attempt == 1 else
                       f"{label} — retrying {len(errors)} missing track(s)…")

            stop_event = threading.Event()
            progress_thread = threading.Thread(
                target=_progress_loop,
                args=(out_dir, expected_total, stop_event, label),
                daemon=True,
            )
            progress_thread.start()

            try:
                with open(log_file, "a", encoding="utf-8") as logf:
                    logf.write(f"\n\n===== Pass {attempt} — {datetime.now()} =====\n")
                    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, text=True)
                    proc.wait()
            finally:
                stop_event.set()
                progress_thread.join()

            count = _count_audio_files(out_dir)
            errors = _read_errors_file(errors_file)

            if count >= expected_total or not errors:
                break

            if attempt < max_passes:
                print_warning(
                    f"{len(errors)} track(s) missing after pass {attempt}. "
                    f"Cooling down {cooldown}s before retrying (rate-limit safe)…"
                )
                time.sleep(cooldown)

        final_count = _count_audio_files(out_dir)
        final_errors = _read_errors_file(errors_file)

        failed_report_path = None
        if final_errors or final_count < expected_total:
            failed_report_path = _write_failed_report(
                out_dir, meta_name, final_errors, expected_total, final_count
            )

        return final_count, out_dir, expected_total, failed_report_path

    # ── public entry-points ───────────────────────────────────────────

    def download_single_track(self, url: str) -> None:
        start_spinner("🎶 Fetching track info")
        meta = self._get_track_meta(url)
        stop_spinner()
        _show_session_header("🎵 Spotify Downloader — Track")
        _display_track_info(meta)
        if not confirm("Proceed with download?"):
            return
        count, out_folder, expected, failed_report = self._spotdl_download(
            url, "track", expected_total=1
        )
        _display_download_result("track", meta.get("title"), out_folder, count, expected, failed_report)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist=meta.get("artist", "spotdl"),
                     mode="Single", status=status)

    def download_album(self, url: str) -> None:
        start_spinner("💿 Fetching album info")
        meta = self._get_album_meta(url)
        stop_spinner()
        _show_session_header("💿 Spotify Downloader — Album")
        _display_album_info(meta)
        if not confirm("Download all tracks?"):
            return
        count, out_folder, expected, failed_report = self._spotdl_download(
            url, "album", meta_name=meta["name"], expected_total=meta.get("track_count")
        )
        _display_download_result("album", meta["name"], out_folder, count, expected, failed_report)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist="spotdl", mode="Album", status=status)

    def download_playlist(self, url: str) -> None:
        start_spinner("📂 Fetching playlist info")
        meta = self._get_playlist_meta(url)
        stop_spinner()
        _show_session_header("📂 Spotify Downloader — Playlist")
        _display_playlist_info(meta)
        if not confirm("Download all tracks?"):
            return
        count, out_folder, expected, failed_report = self._spotdl_download(
            url, "playlist", meta_name=meta["name"], expected_total=meta.get("track_count")
        )
        _display_download_result("playlist", meta["name"], out_folder, count, expected, failed_report)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist="spotdl", mode="Playlist", status=status)


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


def _count_audio_files(folder: str) -> int:
    exts = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav"}
    count = 0
    if not os.path.isdir(folder):
        return 0
    for root, _, files in os.walk(folder):
        for f in files:
            if Path(f).suffix.lower() in exts:
                count += 1
    return count


def _read_errors_file(path: str) -> list:
    """Read spotdl's --save-errors output, one reported issue per line."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []


def _write_failed_report(out_dir: str, meta_name: str | None, errors: list,
                          expected_total: int, final_count: int) -> str:
    """
    Write a plain-text report of everything that didn't make it, inside
    the download folder itself, so it's easy to find next to the audio
    files. Returns the report's absolute path.
    """
    report_path = os.path.join(out_dir, "failed_downloads.txt")
    missing = max(expected_total - final_count, 0)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("LinkCatty — failed / missing tracks report\n")
        f.write(f"Playlist or album : {meta_name or 'Unknown'}\n")
        f.write(f"Generated         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Expected tracks   : {expected_total}\n")
        f.write(f"Downloaded tracks : {final_count}\n")
        f.write(f"Missing tracks    : {missing}\n")
        f.write("-" * 60 + "\n")
        if errors:
            f.write("Reported issues (from spotdl):\n\n")
            for line in errors:
                f.write(line + "\n")
        else:
            f.write(
                "No specific error message was captured for the missing\n"
                "track(s) — only a count mismatch was detected. This\n"
                "usually means a track is region-locked, was removed from\n"
                "Spotify/YouTube, or has no usable match on YouTube Music.\n"
            )
        f.write("\n" + "-" * 60 + "\n")
        f.write(
            "Tip: re-run the same playlist/album download again later.\n"
            "LinkCatty keeps a hidden archive file (.spotdl_archive.spotdl)\n"
            "in this folder, so already-downloaded tracks are skipped and\n"
            "only the ones listed above are retried.\n"
        )
    return report_path


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