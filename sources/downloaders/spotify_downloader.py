import os
import sys
import shutil
import subprocess
import re
import json
import time
import random
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

    if SpotifyClient._instance is not None:
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
    clear_screen()
    print_banner()
    print(f"{BOLD}               {section_title}{RESET}")
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
                              failed_report: str | None,
                              error_breakdown: dict | None = None) -> None:
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
        if error_breakdown:
            print("   Breakdown  :")
            for label, count in error_breakdown.items():
                if count:
                    print(f"     • {label}: {count}")
        print(f"📝 Failed list saved to : {failed_report}")
    print("─" * 61)


# ─────────────────────────────────────────────────────────────────────
#  Error classification
# ─────────────────────────────────────────────────────────────────────

_ERROR_LABELS = {
    "blocked_or_rate_limited": "Blocked / rate-limited by provider",
    "no_match":                "No matching track found (search/lookup miss)",
    "network":                 "Network / timeout error",
    "unavailable":             "Video removed, private, or region-locked",
    "other":                   "Other / unclassified error",
}


def _classify_error(message: str) -> str:
    msg = (message or "").lower()
    if any(term in msg for term in (
        "blocked by youtube", "rate/request limit", "rate limit",
        "429", "too many requests",
    )):
        return "blocked_or_rate_limited"
    if "no results found" in msg or "lookuperror" in msg:
        return "no_match"
    if any(term in msg for term in (
        "timed out", "timeout", "connection", "network", "temporary failure",
        "max retries exceeded",
    )):
        return "network"
    if any(term in msg for term in (
        "unavailable", "private video", "video is no longer available",
        "removed", "copyright",
    )):
        return "unavailable"
    return "other"


# ─────────────────────────────────────────────────────────────────────
#  Adaptive retry-pass strategy
#
#  Pass 1 uses spotdl's normal, high-confidence settings (youtube-music
#  only, strict filtering). Each later pass widens the net a bit more
#  for whatever is STILL missing: more audio-provider fallbacks first
#  (youtube-music misses a lot of regional/film catalogue that a plain
#  YouTube or piped search finds fine), and only as a last resort
#  loosens spotdl's own result filtering.
#
#  FIX: valid spotdl providers are exactly:
#       youtube, youtube-music, soundcloud, bandcamp, piped
#       (the previous "slider-kz" entry was not a real provider).
#  FIX: added a 5th and 6th pass that lean on non-YouTube providers so
#       the "no match found" stragglers (old regional / film tracks)
#       actually get retried against a different catalogue.
# ─────────────────────────────────────────────────────────────────────

_PASS_STRATEGIES = [
    # (audio_providers,                                    dont_filter, thread_divisor, max_retries)
    (["youtube-music"],                                         False, 1,  5),
    (["youtube-music", "youtube"],                              False, 2,  6),
    (["youtube-music", "youtube", "soundcloud", "piped"],       False, 3,  8),
    (["youtube-music", "youtube", "soundcloud", "piped"],       True,  3,  8),
    (["soundcloud", "piped", "bandcamp", "youtube"],            True,  3,  8),
    (["soundcloud", "piped", "bandcamp"],                       True,  2, 10),
]


def _strategy_for_pass(pass_num: int, youtube_blocked: bool) -> tuple:
    idx = min(pass_num - 1, len(_PASS_STRATEGIES) - 1)
    providers, dont_filter, divisor, max_retries = _PASS_STRATEGIES[idx]
    if youtube_blocked:
        # YouTube (both youtube-music and youtube) is actively blocking
        # us — sending more requests just extends the block. Fall back
        # to providers that don't share that infrastructure.
        providers = [p for p in providers if p not in ("youtube-music", "youtube")]
        if not providers:
            providers = ["piped", "soundcloud", "bandcamp"]
    return providers, dont_filter, divisor, max_retries


# ─────────────────────────────────────────────────────────────────────
#  JSON track ledger
# ─────────────────────────────────────────────────────────────────────

def _ledger_path(out_dir: str) -> str:
    return os.path.join(out_dir, ".linkcatty_state.json")


def _load_ledger(out_dir: str) -> dict:
    path = _ledger_path(out_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_ledger(out_dir: str, ledger: dict) -> None:
    path = _ledger_path(out_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print_warning(f"Could not write track ledger: {exc}")


def _init_ledger_entry(url: str, title: str | None, artist: str | None) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "url": url,
        "title": title,
        "artist": artist,
        "status": "pending",       # pending | success | failed
        "attempts": 0,
        "error_type": None,
        "last_error": None,
        "providers_tried": [],
        "first_seen": now,
        "last_attempt": None,
    }


def _song_field(song, *names, default=None):
    for name in names:
        if isinstance(song, dict):
            if song.get(name):
                return song[name]
        else:
            val = getattr(song, name, None)
            if val:
                return val
    return default


def _song_url(song) -> str | None:
    return _song_field(song, "url")


def _song_title(song) -> str | None:
    return _song_field(song, "name", "title")


def _song_artist(song) -> str | None:
    artist = _song_field(song, "artist")
    if artist:
        return artist
    artists = _song_field(song, "artists")
    if artists:
        first = artists[0]
        return first if isinstance(first, str) else first.get("name")
    return None


# ─────────────────────────────────────────────────────────────────────
#  Single progress bar (FIX: one and only one bar for the whole run)
#
#  Runs in a daemon thread, repaints the same \r-line every 0.5 s and
#  computes a live ETA from files-on-disk vs. elapsed time. All print
#  calls made from the main thread go through .say() so they land
#  ABOVE the bar instead of stomping on it.
#
#  FIX: the start-time attribute is now called `_start_time` so it no
#  longer collides with the class method `start()`. Previously
#  `self.start = time.time()` shadowed the method with a float, so
#  `reporter.start()` raised "'float' object is not callable" right
#  after the "Output folder : ..." line.
# ─────────────────────────────────────────────────────────────────────

class _ProgressReporter:
    BAR_WIDTH = 40

    def __init__(self, out_dir: str, total: int, label: str):
        self.out_dir        = out_dir
        self.total          = max(int(total), 1)
        self.label          = label
        self._start_time    = time.time()
        self._stop          = threading.Event()
        self._thread        = None
        self._lock          = threading.Lock()
        self._last_line_len = 0

    # ── lifecycle ─────────────────────────────────────────────────
    def start(self):
        # Print the initial bar immediately so the user sees something
        # before the first subprocess even starts.
        self._render()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
        self._render()
        # move off the \r line once and for all
        with self._lock:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def set_label(self, label: str):
        with self._lock:
            self.label = label

    # ── printing helper ───────────────────────────────────────────
    def say(self, message: str):
        """Print a message above the bar without destroying it."""
        with self._lock:
            # clear the current bar line
            sys.stdout.write("\r" + " " * self._last_line_len + "\r")
            sys.stdout.flush()
            print(message)
            self._last_line_len = 0
        # next render tick (or an immediate render) will redraw

    # ── internals ─────────────────────────────────────────────────
    def _loop(self):
        while not self._stop.wait(0.5):
            self._render()

    def _render(self):
        count     = _count_audio_files(self.out_dir)
        elapsed   = max(time.time() - self._start_time, 0.001)
        remaining = max(self.total - count, 0)
        pct       = (count / self.total) * 100 if self.total else 0.0
        filled    = int(self.BAR_WIDTH * count / self.total) if self.total else 0
        filled    = max(0, min(self.BAR_WIDTH, filled))
        bar       = "█" * filled + "░" * (self.BAR_WIDTH - filled)

        eta_str = ""
        if count > 0 and remaining > 0:
            rate = count / elapsed
            if rate > 0:
                eta_str = f" · ETA {int(remaining / rate)}s"

        line = f"{self.label} |{bar}| {pct:5.1f}% {count}/{self.total} tracks{eta_str}"

        with self._lock:
            # \r + overwrite + pad with spaces if the line got shorter
            pad = max(0, self._last_line_len - len(line))
            sys.stdout.write("\r" + line + (" " * pad))
            sys.stdout.flush()
            self._last_line_len = len(line)


# ─────────────────────────────────────────────────────────────────────
#  Jittered sleep (avoids the "perfectly regular request pattern"
#  that's easiest for a provider to flag as a bot)
# ─────────────────────────────────────────────────────────────────────

def _jitter_sleep(low: float, high: float) -> None:
    if high <= 0:
        return
    low = max(0.0, min(low, high))
    time.sleep(random.uniform(low, high))


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

        # ── pacing / anti-rate-limit settings (all overridable in config) ──
        self.batch_size              = max(1, int(self.spotify_config.get("batch_size", 12)))
        self.batch_cooldown_min      = float(self.spotify_config.get("batch_cooldown_min", 10))
        self.batch_cooldown_max      = float(self.spotify_config.get("batch_cooldown_max", 15))
        self.pass_cooldown_seconds   = int(self.spotify_config.get("retry_delay_seconds", 15))
        self.blocked_cooldown_seconds = int(self.spotify_config.get("blocked_cooldown_seconds", 60))
        # FIX: default bumped from 4 → 6 so the two new non-YouTube-only
        # passes actually get a chance to run.
        self.max_passes              = int(self.spotify_config.get("max_retry_passes", 6))
        self.base_threads            = int(self.spotify_config.get("threads", 4))

    # ── metadata ──────────────────────────────────────────────────────

    def _get_playlist_meta(self, url: str):
        meta = {"name": None, "author": None, "track_count": None}
        songs = None
        if SpotPlaylist is not None and self._client is not None:
            try:
                pl_meta, songs = SpotPlaylist.get_metadata(url)
                meta["name"]        = pl_meta.get("name")
                meta["author"]      = pl_meta.get("author_name")
                meta["track_count"] = len(songs)
                return meta, songs
            except Exception:
                pass
        meta["name"] = _oembed_title(url)   # last-resort fallback
        return meta, songs

    def _get_album_meta(self, url: str):
        meta = {"name": None, "artist": None, "track_count": None}
        songs = None
        if SpotAlbum is not None and self._client is not None:
            try:
                al_meta, songs = SpotAlbum.get_metadata(url)
                meta["name"]        = al_meta.get("name")
                meta["artist"]      = al_meta.get("artist")
                meta["track_count"] = len(songs)
                return meta, songs
            except Exception:
                pass
        title = _oembed_title(url)
        if title:
            meta["name"] = re.sub(r"\s*[-–|].*$", "", title).strip()
        return meta, songs

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

    # ── core download engine (batched, ledger-driven, adaptive) ────────

    def _run_spotdl_batch(self, urls: list, out_dir: str, template: str,
                           audio_format: str, bitrate_arg: str,
                           archive_file: str, errors_file: str, log_file: str,
                           providers: list, dont_filter: bool,
                           threads: int, max_retries: int) -> int:
        """
        Run one spotdl batch. Returns the subprocess exit code.

        FIX: spotdl's CLI is `spotdl [operation] query...`. The operation
        slot only accepts download|save|web|sync|meta|url. Without the
        explicit `download` verb, argparse binds the first URL to
        `operation` and dies with:
            "invalid choice: 'https://open.spotify.com/...'"
        before doing any work at all. This was the reason every single
        batch silently produced 0 files while the ledger claimed success.
        """
        if os.path.exists(errors_file):
            os.remove(errors_file)

        cmd = [
            self.spotdl_path,
            "download",                 # ← THE FIX
            *urls,
            "--output", template,
            "--format", audio_format,
            "--bitrate", bitrate_arg,
            "--threads", str(threads),
            "--max-retries", str(max_retries),
            "--archive", archive_file,
            "--save-errors", errors_file,
            "--overwrite", "skip",
            "--audio", *providers,
        ]
        if dont_filter:
            cmd.append("--dont-filter-results")
        if self.client_id and self.client_secret:
            cmd += ["--client-id", self.client_id,
                    "--client-secret", self.client_secret]

        with open(log_file, "a", encoding="utf-8") as logf:
            logf.write(f"\n\n===== Batch — {datetime.now()} — "
                       f"providers={providers} dont_filter={dont_filter} =====\n")
            logf.write("CMD: " + " ".join(cmd) + "\n")
            proc = subprocess.Popen(cmd, stdout=logf,
                                    stderr=subprocess.STDOUT, text=True)
            proc.wait()
            return proc.returncode

    def _download_tracks(self, songs: list, item_type: str,
                          meta_name: str | None) -> tuple:
        """
        Download a list of Song objects with batched pacing and an
        adaptive, ledger-tracked multi-pass retry.

        Returns (final_count, out_dir, expected_total,
                 failed_report_path, error_breakdown).
        """
        audio_format = self.spotify_config.get("audio_format", "mp3").lower()
        quality  = self.spotify_config.get("audio_quality", "320k").replace("k", "")
        bitrate_arg = "disable" if audio_format in ("flac", "wav") else f"{quality}k"
        base_dir = str(self.download_dir)

        if item_type in ("album", "playlist"):
            folder_name = _safe_name(meta_name) if meta_name else f"{{{item_type}}}"
            out_dir = os.path.join(base_dir, folder_name)
        else:
            out_dir = base_dir
        template = os.path.join(out_dir, "{title} - {artists}.{ext}")
        os.makedirs(out_dir, exist_ok=True)

        archive_file = os.path.join(out_dir, ".spotdl_archive.spotdl")
        errors_file  = os.path.join(out_dir, ".spotdl_errors.txt")
        log_file     = os.path.join(out_dir, ".spotdl_log.txt")

        expected_total = len(songs) or 1

        print_info(f"Output folder : {out_dir}")

        # ── build / merge the ledger ────────────────────────────────
        ledger = _load_ledger(out_dir)
        song_urls = {_song_url(s) for s in songs if _song_url(s)}
        for song in songs:
            url = _song_url(song)
            if not url:
                continue
            if url not in ledger:
                ledger[url] = _init_ledger_entry(
                    url, _song_title(song), _song_artist(song))
        _save_ledger(out_dir, ledger)

        youtube_blocked = False

        # ── one and only one progress bar ──────────────────────────
        reporter = _ProgressReporter(out_dir, expected_total,
                                     f"⬇ Downloading 0/{expected_total}")
        reporter.start()

        try:
            for pass_num in range(1, self.max_passes + 1):
                pending_urls = [
                    u for u, rec in ledger.items()
                    if u in song_urls and rec["status"] != "success"
                ]
                if not pending_urls:
                    break

                providers, dont_filter, divisor, max_retries = \
                    _strategy_for_pass(pass_num, youtube_blocked)
                threads = max(1, self.base_threads // divisor)

                reporter.set_label(
                    f"⬇ Pass {pass_num}/{self.max_passes} "
                    f"({len(pending_urls)} left)"
                )

                batches = [
                    pending_urls[i:i + self.batch_size]
                    for i in range(0, len(pending_urls), self.batch_size)
                ]

                pass_start_success = sum(
                    1 for r in ledger.values() if r["status"] == "success")

                for b_idx, batch_urls in enumerate(batches, start=1):
                    exit_code = self._run_spotdl_batch(
                        batch_urls, out_dir, template, audio_format,
                        bitrate_arg, archive_file, errors_file, log_file,
                        providers, dont_filter, threads, max_retries,
                    )

                    batch_errors = _read_errors_file(errors_file)
                    archive_urls = _read_archive(archive_file)
                    now = datetime.now().isoformat(timespec="seconds")

                    for url in batch_urls:
                        rec = ledger.get(url)
                        if rec is None:
                            continue
                        rec["attempts"] += 1
                        rec["last_attempt"] = now
                        for p in providers:
                            if p not in rec["providers_tried"]:
                                rec["providers_tried"].append(p)

                        if url in batch_errors:
                            # confirmed per-track failure
                            msg = batch_errors[url]
                            rec["status"]     = "failed"
                            rec["last_error"] = msg
                            rec["error_type"] = _classify_error(msg)
                            if rec["error_type"] == "blocked_or_rate_limited":
                                youtube_blocked = True
                        elif url in archive_urls:
                            # confirmed success on disk
                            rec["status"]     = "success"
                            rec["last_error"] = None
                            rec["error_type"] = None
                        elif exit_code != 0:
                            # spotdl died before it could write per-track
                            # errors (argparse, missing deps, etc.) —
                            # FIX: do NOT lie and mark these as success.
                            rec["status"]     = "failed"
                            rec["last_error"] = (
                                f"spotdl exited with code {exit_code} "
                                f"(no per-track error captured; see "
                                f"{os.path.basename(log_file)})"
                            )
                            rec["error_type"] = "other"
                        else:
                            # exit 0, no error recorded, not in archive —
                            # spotdl sometimes skips writing to the
                            # archive for files that already existed on
                            # disk. Trust exit code 0 here.
                            rec["status"]     = "success"
                            rec["last_error"] = None
                            rec["error_type"] = None

                    _save_ledger(out_dir, ledger)

                    reporter.set_label(
                        f"⬇ Pass {pass_num}/{self.max_passes} "
                        f"batch {b_idx}/{len(batches)}"
                    )
                    reporter._render()

                    is_last_batch = b_idx == len(batches)
                    if not is_last_batch:
                        cd_low, cd_high = (self.batch_cooldown_min,
                                           self.batch_cooldown_max)
                        if youtube_blocked:
                            cd_low  = self.blocked_cooldown_seconds
                            cd_high = self.blocked_cooldown_seconds + 15
                        _jitter_sleep(cd_low, cd_high)

                pass_end_success = sum(
                    1 for r in ledger.values() if r["status"] == "success")
                gained = pass_end_success - pass_start_success
                still_missing = expected_total - pass_end_success

                if still_missing <= 0:
                    break

                if youtube_blocked:
                    reporter.say(
                        "⚠️  YouTube/YouTube Music is rate-limiting this "
                        "connection — switching remaining retries to "
                        "non-YouTube providers."
                    )

                if pass_num < self.max_passes:
                    cooldown = (self.blocked_cooldown_seconds
                                if youtube_blocked
                                else self.pass_cooldown_seconds)
                    reporter.say(
                        f"⚠️  {still_missing} track(s) still missing after "
                        f"pass {pass_num} (+{gained} recovered). Cooling "
                        f"down {cooldown}s before the next pass…"
                    )
                    _jitter_sleep(cooldown, cooldown + 5)
        finally:
            reporter.stop()

        final_count = _count_audio_files(out_dir)
        relevant_records = [ledger[u] for u in song_urls if u in ledger]
        failed_records   = [r for r in relevant_records if r["status"] != "success"]

        error_breakdown = {}
        for r in failed_records:
            etype = r.get("error_type") or "other"
            label = _ERROR_LABELS.get(etype, etype)
            error_breakdown[label] = error_breakdown.get(label, 0) + 1

        failed_report_path = None
        if failed_records:
            failed_report_path = _write_failed_report(
                out_dir, meta_name, failed_records,
                expected_total, final_count, error_breakdown
            )

        return final_count, out_dir, expected_total, failed_report_path, error_breakdown

    # ── public entry-points ───────────────────────────────────────────

    def download_single_track(self, url: str) -> None:
        start_spinner("🎶 Fetching track info")
        meta = self._get_track_meta(url)
        stop_spinner()
        _show_session_header("🎵 Spotify Downloader — Track")
        _display_track_info(meta)
        if not confirm("Proceed with download?"):
            return
        song = {"url": url, "name": meta.get("title"), "artist": meta.get("artist")}
        count, out_folder, expected, failed_report, breakdown = self._download_tracks(
            [song], "track", meta.get("title")
        )
        _display_download_result("track", meta.get("title"), out_folder,
                                  count, expected, failed_report, breakdown)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist=meta.get("artist", "spotdl"),
                     mode="Single", status=status)

    def download_album(self, url: str) -> None:
        start_spinner("💿 Fetching album info")
        meta, songs = self._get_album_meta(url)
        stop_spinner()
        _show_session_header("💿 Spotify Downloader — Album")
        _display_album_info(meta)
        if not confirm("Download all tracks?"):
            return
        if not songs:
            print_error("Could not resolve the album's track list.",
                        "Falling back to a single bulk download via spotdl.")
            songs = [{"url": url, "name": meta.get("name"),
                      "artist": meta.get("artist")}]
        count, out_folder, expected, failed_report, breakdown = self._download_tracks(
            songs, "album", meta["name"]
        )
        _display_download_result("album", meta["name"], out_folder,
                                  count, expected, failed_report, breakdown)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist="spotdl", mode="Album", status=status)

    def download_playlist(self, url: str) -> None:
        start_spinner("📂 Fetching playlist info")
        meta, songs = self._get_playlist_meta(url)
        stop_spinner()
        _show_session_header("📂 Spotify Downloader — Playlist")
        _display_playlist_info(meta)
        if not confirm("Download all tracks?"):
            return
        if not songs:
            print_error("Could not resolve the playlist's track list.",
                        "Falling back to a single bulk download via spotdl.")
            songs = [{"url": url, "name": meta.get("name"),
                      "artist": meta.get("author")}]
        count, out_folder, expected, failed_report, breakdown = self._download_tracks(
            songs, "playlist", meta["name"]
        )
        _display_download_result("playlist", meta["name"], out_folder,
                                  count, expected, failed_report, breakdown)
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


def _read_errors_file(path: str) -> dict:
    """
    Read spotdl's --save-errors output and return {url: message}.
    Each line looks like:
      https://open.spotify.com/track/XXXX - LookupError: No results found for song: Artist - Title
    """
    result = {}
    if not os.path.exists(path):
        return result
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^(\S+)\s*-\s*(.+)$", line)
                if m:
                    result[m.group(1)] = m.group(2)
                else:
                    result[line] = line
    except Exception:
        pass
    return result


# FIX: new helper — reads spotdl's own --archive file, which is the
# only authoritative record of which tracks actually made it to disk.
# Used to stop the ledger from claiming "success" when spotdl never
# even parsed its arguments.
def _read_archive(path: str) -> set:
    urls = set()
    if not os.path.exists(path):
        return urls
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("http"):
                    urls.add(line)
    except Exception:
        pass
    return urls


def _write_failed_report(out_dir: str, meta_name: str | None, failed_records: list,
                          expected_total: int, final_count: int,
                          error_breakdown: dict) -> str:
    """
    Write a plain-text report of everything that didn't make it, inside
    the download folder itself, alongside the machine-readable
    .linkcatty_state.json ledger.
    """
    report_path = os.path.join(out_dir, "failed_downloads.txt")
    missing = len(failed_records)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("LinkCatty — failed / missing tracks report\n")
        f.write(f"Playlist or album : {meta_name or 'Unknown'}\n")
        f.write(f"Generated         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Expected tracks   : {expected_total}\n")
        f.write(f"Downloaded tracks : {final_count}\n")
        f.write(f"Missing tracks    : {missing}\n")
        f.write("-" * 60 + "\n")
        if error_breakdown:
            f.write("Breakdown by cause:\n")
            for label, count in error_breakdown.items():
                f.write(f"  • {label}: {count}\n")
            f.write("-" * 60 + "\n")
        f.write("Per-track detail:\n\n")
        for r in failed_records:
            title = r.get("title") or "Unknown title"
            artist = r.get("artist") or "Unknown artist"
            etype = _ERROR_LABELS.get(r.get("error_type"),
                                       r.get("error_type") or "other")
            tried = ", ".join(r.get("providers_tried") or []) or "n/a"
            f.write(f"{r['url']}\n")
            f.write(f"    {artist} - {title}\n")
            f.write(f"    Cause      : {etype}\n")
            f.write(f"    Last error : {r.get('last_error') or 'n/a'}\n")
            f.write(f"    Providers tried : {tried}\n")
            f.write(f"    Attempts   : {r.get('attempts', 0)}\n\n")
        f.write("-" * 60 + "\n")
        f.write(
            "Tip: re-run the same playlist/album download again (even in a new\n"
            "session). LinkCatty keeps a machine-readable ledger next to this\n"
            "report (.linkcatty_state.json) plus spotdl's own archive file, so\n"
            "already-downloaded tracks are always skipped and only the tracks\n"
            "listed above are retried — picking up the provider/matching\n"
            "strategy where the previous run left off instead of starting over.\n"
        )
        if error_breakdown and _ERROR_LABELS["no_match"] in error_breakdown:
            f.write(
                "\nMost of these failed with 'no match found', not a rate limit —\n"
                "that means the audio-provider fallback chain (YouTube Music →\n"
                "YouTube → SoundCloud → Piped → Bandcamp) still couldn't find a\n"
                "usable match, most often for regional / film-soundtrack tracks\n"
                "whose Spotify title differs a lot from how it's titled on\n"
                "YouTube. Re-running with more passes gives the 'loosened\n"
                "matching' pass (--dont-filter-results) more chances to pick up\n"
                "a lower-confidence match for these specific stragglers.\n"
            )
        if error_breakdown and _ERROR_LABELS["blocked_or_rate_limited"] in error_breakdown:
            f.write(
                "\nSome failures were YouTube blocking/rate-limiting this\n"
                "connection. Waiting longer between runs, using a VPN/proxy\n"
                "(spotdl's --proxy), or lowering batch_size/threads further in\n"
                "config will help more than retrying immediately.\n"
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