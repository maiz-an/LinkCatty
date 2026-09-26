import os
import shutil
import sys
import subprocess
import re
import json
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    DownloadProgress,
    ask_url,
    card,
    confirm,
    format_eta,
    pause,
    plan_line,
    print_error,
    print_info,
    print_success,
    print_warning,
    result_card,
    section_header,
    show_menu,
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


def _find_spotdl_command() -> list:
    """How to run spotdl, without relying on PATH.

    pip often puts spotdl.exe in a Scripts folder that is not on PATH, so
    run it through the interpreter that is running LinkCatty instead.
    """
    if _SPOTDL_AVAILABLE:
        return [sys.executable, "-m", "spotdl"]
    found = shutil.which("spotdl")
    if found:
        return [found]
    raise RuntimeError(
        "spotdl is not installed for this Python.\n"
        "  → Run: pip install spotdl"
    )


# ─────────────────────────────────────────────────────────────────────
#  Deno – install once per process, never again
# ─────────────────────────────────────────────────────────────────────
_DENO_READY = False


def _deno_already_available() -> bool:
    try:
        from spotdl.utils.deno import get_deno_path
        return get_deno_path() is not None
    except Exception:
        return bool(shutil.which("deno"))


def _ensure_deno(spotdl_cmd: list) -> None:
    global _DENO_READY
    if _DENO_READY:
        return
    if _deno_already_available():
        _DENO_READY = True
        return
    print_info("Deno not found – installing automatically (one-time setup)…")
    try:
        proc = subprocess.Popen(
            [*spotdl_cmd, "--download-deno"],
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
    _DENO_READY = True


# ─────────────────────────────────────────────────────────────────────
#  SpotifyClient – FREE MODE ONLY  (SpotipyFree / no credentials)
# ─────────────────────────────────────────────────────────────────────
_FREE_CLIENT = None


def _get_free_client():
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
            use_official_api=False,
        )
    except Exception:
        try:
            _FREE_CLIENT = SpotifyClient()
        except Exception:
            _FREE_CLIENT = None

    return _FREE_CLIENT


# ─────────────────────────────────────────────────────────────────────
#  Display helpers (all drawn with the shared UI kit in utils/ui.py)
# ─────────────────────────────────────────────────────────────────────

def _display_track_info(info: dict) -> None:
    card("TRACK", [
        ("Title", info.get("title") or "Unknown"),
        ("Artist", info.get("artist") or "Unknown"),
        ("Album", info.get("album")),
    ], icon="🎵")


def _display_album_info(info: dict) -> None:
    count = info.get("track_count")
    card("ALBUM", [
        ("Album", info.get("name") or "Unknown"),
        ("Artist", info.get("artist")),
        ("Tracks", count if count is not None else "Unknown"),
    ], icon="💿")


def _display_playlist_info(info: dict) -> None:
    count = info.get("track_count")
    card("PLAYLIST", [
        ("Name", info.get("name") or "Unknown"),
        ("Author", info.get("author")),
        ("Tracks", count if count is not None else "Unknown"),
    ], icon="📂")


def _display_download_result(item_type: str, name: str | None, out_folder: str,
                              downloaded: int, expected: int,
                              failed_report: str | None,
                              error_breakdown: dict | None = None,
                              elapsed: float | None = None) -> None:
    what = {"track": "Track", "album": "Album", "playlist": "Playlist"}[item_type]
    time_text = format_eta(elapsed) if elapsed is not None else None
    if failed_report is None:
        rows = [(what, name), ("Saved to", out_folder)]
        if item_type != "track":
            rows.append(("Files", f"{downloaded} of {expected}"))
        rows.append(("Time", time_text))
        result_card("ok", "DOWNLOAD COMPLETE", rows)
        return
    rows = [(what, name), ("Saved to", out_folder),
            ("Files", f"{downloaded} of {expected}"),
            ("Missing", max(expected - downloaded, 0)),
            ("Time", time_text)]
    details = [f"{label}  ×{count}"
               for label, count in (error_breakdown or {}).items() if count]
    result_card("warn" if downloaded else "fail",
                "FINISHED WITH MISSING TRACKS" if downloaded else "DOWNLOAD FAILED",
                rows, details, [("Report", failed_report)])


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
#  Pass 1: spotdl's normal, high-confidence settings (youtube-music
#          only, strict filtering).
#  Later passes widen the net progressively for whatever is STILL
#  missing: more audio-provider fallbacks, then loosened filtering.
#
#  max_passes default is now 4 (was 6). In practice passes 5 and 6
#  recovered almost nothing in real runs — the last two provider sets
#  rarely succeed on tracks that YouTube Music + YouTube couldn't
#  match. Users who want them can raise max_retry_passes in config.
# ─────────────────────────────────────────────────────────────────────

_PASS_STRATEGIES = [
    # (audio_providers,                                    dont_filter, thread_divisor, max_retries)
    (["youtube-music"],                                         False, 1,  5),
    (["youtube-music", "youtube"],                              False, 1,  6),
    (["youtube-music", "youtube", "soundcloud", "piped"],       False, 2,  8),
    (["youtube-music", "youtube", "soundcloud", "piped"],       True,  2,  8),
    (["soundcloud", "piped", "bandcamp", "youtube"],            True,  2,  8),
    (["soundcloud", "piped", "bandcamp"],                       True,  2, 10),
]


def _strategy_for_pass(pass_num: int, youtube_blocked: bool) -> tuple:
    idx = min(pass_num - 1, len(_PASS_STRATEGIES) - 1)
    providers, dont_filter, divisor, max_retries = _PASS_STRATEGIES[idx]
    if youtube_blocked:
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
        "status": "pending",
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
#  Jittered sleep
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

        self.spotdl_cmd = _find_spotdl_command()

        self.client_id     = self.spotify_config.get("client_id", "").strip()
        self.client_secret = self.spotify_config.get("client_secret", "").strip()

        self._client = _get_free_client()

        _ensure_deno(self.spotdl_cmd)

        # ── pacing / anti-rate-limit settings (all overridable in config) ──
        #
        #  Speed tuning: batches within a pass now run in PARALLEL, so the
        #  effective concurrency is parallel_batches * threads. Defaults
        #  give 3 * 2 = 6 concurrent downloads, which is fast without
        #  tripping YouTube's rate limiter. Lower parallel_batches to 2 (or
        #  threads to 1) if you see "blocked by youtube" errors.
        self.parallel_batches         = max(1, int(self.spotify_config.get("parallel_batches", 3)))
        self.batch_size               = max(1, int(self.spotify_config.get("batch_size", 10)))
        self.batch_cooldown_min       = float(self.spotify_config.get("batch_cooldown_min", 1))
        self.batch_cooldown_max       = float(self.spotify_config.get("batch_cooldown_max", 3))
        self.pass_cooldown_seconds    = int(self.spotify_config.get("retry_delay_seconds", 8))
        self.blocked_cooldown_seconds = int(self.spotify_config.get("blocked_cooldown_seconds", 45))
        self.max_passes               = (max(1, int(self.spotify_config.get("max_retry_passes", 4)))
                                         if self.spotify_config.get("auto_retry", True) else 1)
        self.base_threads             = int(self.spotify_config.get("threads", 2))

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
        meta["name"] = _oembed_title(url)
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

    # ── core download engine (parallel batches, ledger-driven, adaptive) ──

    def _run_spotdl_batch(self, urls: list, out_dir: str, template: str,
                           audio_format: str, bitrate_arg: str,
                           archive_file: str, errors_file: str, log_file: str,
                           providers: list, dont_filter: bool,
                           threads: int, max_retries: int) -> int:
        """
        Run one spotdl batch. Returns the subprocess exit code.

        spotdl's CLI is `spotdl [operation] query...`; the operation slot
        only accepts download|save|web|sync|meta|url. Without the explicit
        `download` verb, argparse binds the first URL to `operation` and
        dies immediately.
        """
        if os.path.exists(errors_file):
            os.remove(errors_file)

        cmd = [
            *self.spotdl_cmd,
            "download",
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

    def _run_spotdl_batch_isolated(self, batch_urls, batch_idx, pass_temp,
                                    out_dir, template, audio_format, bitrate_arg,
                                    main_archive_file, providers, dont_filter,
                                    threads, max_retries):
        """
        Runs one spotdl batch with its own archive/errors/log files.
        Designed to be called from a ThreadPoolExecutor — nothing here
        touches shared state (only per-batch files in pass_temp), so it
        is safe to run several in parallel.
        """
        batch_archive = os.path.join(pass_temp, f"archive.{batch_idx}.spotdl")
        batch_errors  = os.path.join(pass_temp, f"errors.{batch_idx}.txt")
        batch_log     = os.path.join(pass_temp, f"log.{batch_idx}.txt")

        # Seed the batch archive with the main archive so spotdl skips
        # anything already downloaded in previous passes / runs.
        if os.path.exists(main_archive_file):
            try:
                shutil.copyfile(main_archive_file, batch_archive)
            except Exception:
                pass

        exit_code = self._run_spotdl_batch(
            batch_urls, out_dir, template, audio_format, bitrate_arg,
            batch_archive, batch_errors, batch_log,
            providers, dont_filter, threads, max_retries,
        )

        return {
            "batch_idx":     batch_idx,
            "batch_urls":    batch_urls,
            "exit_code":     exit_code,
            "errors":        _read_errors_file(batch_errors),
            "archive":       _read_archive(batch_archive),
            "archive_path":  batch_archive,
            "log_path":      batch_log,
        }

    def _merge_archive(self, main_path: str, batch_path: str) -> None:
        """Append any new URLs from a per-batch archive to the main one."""
        if not os.path.exists(batch_path):
            return
        try:
            existing = _read_archive(main_path)
            new_urls = []
            with open(batch_path, "r", encoding="utf-8", errors="ignore") as src:
                for line in src:
                    line = line.strip()
                    if line.startswith("http") and line not in existing:
                        new_urls.append(line)
                        existing.add(line)
            if new_urls:
                with open(main_path, "a", encoding="utf-8") as dst:
                    for url in new_urls:
                        dst.write(url + "\n")
        except Exception:
            pass

    def _download_tracks(self, songs: list, item_type: str,
                          meta_name: str | None) -> tuple:
        """
        Download a list of Song objects with parallel batched pacing and
        an adaptive, ledger-tracked multi-pass retry.

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

        format_label = audio_format.upper() + (
            "" if audio_format in ("flac", "wav") else f" {quality}k")
        plan_line(format_label,
                  f"{self.parallel_batches * self.base_threads} parallel")

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

        reporter = DownloadProgress(
            "Downloading", expected_total, unit="tracks",
            count_fn=lambda: _count_audio_files(out_dir))
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

                batches = [
                    pending_urls[i:i + self.batch_size]
                    for i in range(0, len(pending_urls), self.batch_size)
                ]

                # Per-pass scratch dir for per-batch archive/errors/log.
                pass_temp = os.path.join(out_dir, f".linkcatty_pass{pass_num}")
                shutil.rmtree(pass_temp, ignore_errors=True)
                os.makedirs(pass_temp, exist_ok=True)

                try:
                    with ThreadPoolExecutor(max_workers=self.parallel_batches) as executor:
                        futures = {
                            executor.submit(
                                self._run_spotdl_batch_isolated,
                                batch_urls, b_idx, pass_temp, out_dir, template,
                                audio_format, bitrate_arg, archive_file,
                                providers, dont_filter, threads, max_retries,
                            ): (b_idx, batch_urls)
                            for b_idx, batch_urls in enumerate(batches)
                        }

                        for future in as_completed(futures):
                            b_idx, batch_urls = futures[future]

                            try:
                                result       = future.result()
                                exit_code    = result["exit_code"]
                                batch_errors = result["errors"]
                                batch_archive_set = result["archive"]
                                batch_archive_path = result["archive_path"]
                                batch_log_path     = result["log_path"]
                            except Exception as exc:
                                exit_code = -1
                                batch_errors = {}
                                batch_archive_set = set()
                                batch_archive_path = None
                                batch_log_path = None

                            # Merge archive & append log
                            if batch_archive_path:
                                self._merge_archive(archive_file, batch_archive_path)
                            if batch_log_path and os.path.exists(batch_log_path):
                                try:
                                    with open(batch_log_path, "r",
                                              encoding="utf-8",
                                              errors="ignore") as src:
                                        with open(log_file, "a",
                                                  encoding="utf-8") as dst:
                                            dst.write(
                                                f"\n\n===== Pass {pass_num} "
                                                f"batch {b_idx} =====\n"
                                            )
                                            dst.write(src.read())
                                except Exception:
                                    pass

                            # Update ledger (main thread only — no lock needed)
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
                                    msg = batch_errors[url]
                                    rec["status"]     = "failed"
                                    rec["last_error"] = msg
                                    rec["error_type"] = _classify_error(msg)
                                    if rec["error_type"] == "blocked_or_rate_limited":
                                        youtube_blocked = True
                                elif url in batch_archive_set:
                                    rec["status"]     = "success"
                                    rec["last_error"] = None
                                    rec["error_type"] = None
                                elif exit_code != 0:
                                    rec["status"]     = "failed"
                                    rec["last_error"] = (
                                        f"spotdl exited with code {exit_code} "
                                        f"(no per-track error captured; see "
                                        f"{os.path.basename(log_file)})"
                                    )
                                    rec["error_type"] = "other"
                                else:
                                    rec["status"]     = "success"
                                    rec["last_error"] = None
                                    rec["error_type"] = None

                            _save_ledger(out_dir, ledger)

                            reporter._render()
                finally:
                    shutil.rmtree(pass_temp, ignore_errors=True)

                pass_end_success = sum(
                    1 for r in ledger.values() if r["status"] == "success")
                still_missing = expected_total - pass_end_success

                if still_missing <= 0:
                    break

                if pass_num < self.max_passes:
                    cooldown = (self.blocked_cooldown_seconds
                                if youtube_blocked
                                else self.pass_cooldown_seconds)
                    _jitter_sleep(cooldown, cooldown + 3)
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
        title = "🎵 Spotify Downloader — Track"
        start_spinner("🎶 Fetching track info")
        meta = self._get_track_meta(url)
        stop_spinner()
        section_header(title)
        _display_track_info(meta)
        if not confirm("Proceed with download?", default=True):
            return
        song = {"url": url, "name": meta.get("title"), "artist": meta.get("artist")}
        started = time.time()
        count, out_folder, expected, failed_report, breakdown = self._download_tracks(
            [song], "track", meta.get("title")
        )
        section_header(title)
        _display_download_result("track", meta.get("title"), out_folder,
                                  count, expected, failed_report, breakdown,
                                  elapsed=time.time() - started)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist=meta.get("artist", "spotdl"),
                     mode="Single", status=status)

    def download_album(self, url: str) -> None:
        title = "💿 Spotify Downloader — Album"
        start_spinner("💿 Fetching album info")
        meta, songs = self._get_album_meta(url)
        stop_spinner()
        section_header(title)
        _display_album_info(meta)
        if not confirm("Download all tracks?", default=True):
            return
        if not songs:
            print_error("Could not resolve the album's track list.",
                        "Falling back to a single bulk download via spotdl.")
            songs = [{"url": url, "name": meta.get("name"),
                      "artist": meta.get("artist")}]
        started = time.time()
        count, out_folder, expected, failed_report, breakdown = self._download_tracks(
            songs, "album", meta["name"]
        )
        section_header(title)
        _display_download_result("album", meta["name"], out_folder,
                                  count, expected, failed_report, breakdown,
                                  elapsed=time.time() - started)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist="spotdl", mode="Album", status=status)

    def download_playlist(self, url: str) -> None:
        title = "📂 Spotify Downloader — Playlist"
        start_spinner("📂 Fetching playlist info")
        meta, songs = self._get_playlist_meta(url)
        stop_spinner()
        section_header(title)
        _display_playlist_info(meta)
        if not confirm("Download all tracks?", default=True):
            return
        if not songs:
            print_error("Could not resolve the playlist's track list.",
                        "Falling back to a single bulk download via spotdl.")
            songs = [{"url": url, "name": meta.get("name"),
                      "artist": meta.get("author")}]
        started = time.time()
        count, out_folder, expected, failed_report, breakdown = self._download_tracks(
            songs, "playlist", meta["name"]
        )
        section_header(title)
        _display_download_result("playlist", meta["name"], out_folder,
                                  count, expected, failed_report, breakdown,
                                  elapsed=time.time() - started)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist="spotdl", mode="Playlist", status=status)


# ─────────────────────────────────────────────────────────────────────
#  Standalone helpers
# ─────────────────────────────────────────────────────────────────────

def _oembed_title(url: str) -> str | None:
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
            "listed above are retried.\n"
        )
        if error_breakdown and _ERROR_LABELS["no_match"] in error_breakdown:
            f.write(
                "\nMost of these failed with 'no match found', not a rate limit —\n"
                "the audio-provider fallback chain still couldn't find a usable\n"
                "match, most often for regional / film-soundtrack tracks whose\n"
                "Spotify title differs a lot from how it's titled on YouTube.\n"
            )
        if error_breakdown and _ERROR_LABELS["blocked_or_rate_limited"] in error_breakdown:
            f.write(
                "\nSome failures were YouTube blocking/rate-limiting this\n"
                "connection. Lower parallel_batches or threads in settings,\n"
                "wait longer between runs, or use a proxy (spotdl --proxy).\n"
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
        url = ask_url(f"Spotify {item_type}")
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
        choice = show_menu("🎵 Spotify Downloader", [
            "Download single track",
            "Download album",
            "Download playlist",
        ])
        if choice in (None, "0"):
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
