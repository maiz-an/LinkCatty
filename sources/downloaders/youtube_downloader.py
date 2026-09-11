import re
import sys
import time
import json
import threading
import os
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from yt_dlp import YoutubeDL

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
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
    print_warning,
    start_spinner,
    stop_spinner,
)


# ─────────────────────────────────────────────────────────────────────
#  Formatting helpers
# ─────────────────────────────────────────────────────────────────────

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_view_count(count):
    if not count:
        return "Unknown"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def _format_bytes(num_bytes):
    if not num_bytes:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} TB"


def _format_eta(seconds):
    if seconds is None or seconds < 0:
        return "—"
    try:
        return str(timedelta(seconds=int(seconds)))
    except Exception:
        return "—"


def _format_elapsed(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def is_youtube_url(url):
    return bool(re.match(r"^https?://", url)) and ("youtube.com" in url or "youtu.be" in url)


def get_video_format(video_quality):
    quality_map = {
        "best": "bestvideo+bestaudio/best",
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    }
    return quality_map.get(video_quality, "bestvideo+bestaudio/best")


def _show_session_header(section_title: str) -> None:
    """Redraw the banner + section title so an info panel isn't stacked
    under the numbered menu the user already picked from."""
    clear_screen()
    print_banner()
    print(f"{BOLD}                   {section_title}{RESET}")
    print("=" * 61)


# ─────────────────────────────────────────────────────────────────────
#  Browser-cookie fallback — resolved once per process, thread-safe
# ─────────────────────────────────────────────────────────────────────
_COOKIE_OPTION = None
_COOKIE_ATTEMPTED = False
_COOKIE_LOCK = threading.Lock()


def get_browser_cookie_option(force_retry: bool = False):
    global _COOKIE_OPTION, _COOKIE_ATTEMPTED
    with _COOKIE_LOCK:
        if _COOKIE_ATTEMPTED and not force_retry:
            return _COOKIE_OPTION

        print_info("YouTube requires authentication. Close Chrome/Firefox/Edge completely first.")
        try:
            input("Press Enter after closing your browser...")
        except (KeyboardInterrupt, EOFError):
            print()

        for browser in ("chrome", "firefox", "edge", "brave"):
            try:
                with YoutubeDL({"quiet": True, "cookiesfrombrowser": (browser,)}) as test:
                    test.extract_info("https://youtube.com", download=False)
                print_info(f"Successfully loaded cookies from {browser}")
                _COOKIE_OPTION = (browser,)
                _COOKIE_ATTEMPTED = True
                return _COOKIE_OPTION
            except Exception:
                continue

        print_warning("Could not load cookies from a supported browser.")
        _COOKIE_OPTION = None
        _COOKIE_ATTEMPTED = True
        return None


# ─────────────────────────────────────────────────────────────────────
#  yt-dlp option builder
# ─────────────────────────────────────────────────────────────────────

def build_download_options(output_dir, mode, config, quiet_progress=False):
    youtube_config = config["youtube"]
    quiet = youtube_config.get("quiet_mode", True)

    options = {
        "outtmpl": str(Path(output_dir) / "%(title)s - %(uploader)s.%(ext)s"),
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": quiet_progress or False,
        "retries": int(youtube_config.get("max_retries", 3)),
        "ignoreerrors": False,

        # ── metadata sidecar files ──────────────────────────────────
        "writeinfojson":     bool(youtube_config.get("save_metadata", True)),
        "writethumbnail":    bool(youtube_config.get("save_thumbnail", True)),
        "writedescription":  bool(youtube_config.get("save_description", False)),

        # ── embed metadata directly into the media file ─────────────
        "embedmetadata":     bool(youtube_config.get("embed_metadata", True)),
        "embedthumbnail":    bool(youtube_config.get("embed_thumbnail", False)),
    }

    if not quiet_progress and not quiet:
        options["progress_hooks"] = [progress_hook]

    if mode == "1":
        options.update({
            "format": get_video_format(youtube_config.get("video_quality", "best")),
            "merge_output_format": "mp4",
        })
    else:
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": youtube_config["audio_quality"].replace("k", ""),
            }],
        })

    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg
    return options


# ─────────────────────────────────────────────────────────────────────
#  Progress hook (sequential mode only)
# ─────────────────────────────────────────────────────────────────────

_download_completed_shown = False


def progress_hook(data):
    global _download_completed_shown
    if data["status"] == "downloading" and "_percent_str" in data:
        percent = data["_percent_str"].strip()
        speed = data.get("_speed_str", "N/A").strip()
        eta = data.get("_eta_str", "N/A").strip()
        total_size = data.get("_total_bytes_str", "N/A").strip()
        downloaded = data.get("_downloaded_bytes_str", "N/A").strip()
        sys.stdout.write(
            f"\r⏳ Downloading... {percent} | {downloaded}/{total_size} "
            f"| Speed: {speed} | ETA: {eta}"
        )
        sys.stdout.flush()
    elif data["status"] == "finished" and not _download_completed_shown:
        _download_completed_shown = True
        info = data.get("info_dict") or {}
        if info.get("__quiet_box__"):
            print()
            return
        filepath = data.get("filepath", "Unknown")
        time.sleep(0.5)
        if filepath and filepath != "Unknown" and Path(filepath).exists():
            path = Path(filepath).absolute()
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
            except OSError:
                size_mb = 0
            print("\n" + "═" * 55)
            print("            ✅ DOWNLOAD COMPLETED")
            print("═" * 55)
            print(f"📄 File name: {path.name}")
            print(f"📂 Location: {path.parent}")
            print(f"💾 File size: {size_mb:.2f} MB")
            print(f"⏰ Completed at: {time.strftime('%H:%M:%S')}")
            print("═" * 55 + "\n")
        else:
            print("\n✅ Download completed successfully\n")


# ─────────────────────────────────────────────────────────────────────
#  Single-video download (used by single-video flow + manual format)
# ─────────────────────────────────────────────────────────────────────

def download_single_video(video_url, output_dir, mode, config, quiet_box=False):
    global _download_completed_shown
    _download_completed_shown = False
    options = build_download_options(output_dir, mode, config,
                                     quiet_progress=quiet_box)
    if quiet_box:
        options["__quiet_box__"] = True

    if _COOKIE_OPTION is not None:
        options["cookiesfrombrowser"] = _COOKIE_OPTION

    try:
        with YoutubeDL(options) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as error:
        error_message = str(error)
        if "Sign in to confirm" not in error_message and "bot" not in error_message:
            return False, error_message
        if _COOKIE_ATTEMPTED and _COOKIE_OPTION is None:
            return False, ("Blocked (sign-in required) — no working browser "
                           "cookies found earlier this session.")
        print_warning("Direct download blocked. Trying browser cookies.")

    cookie_option = get_browser_cookie_option()
    if not cookie_option:
        return False, "No working browser cookies. Try logging into YouTube in your browser."
    options["cookiesfrombrowser"] = cookie_option
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as error:
        return False, str(error)


# ─────────────────────────────────────────────────────────────────────
#  Info fetching
# ─────────────────────────────────────────────────────────────────────

def get_url_info(url):
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        return parse_info(info)
    except Exception as error:
        error_message = str(error)
        if "Sign in to confirm" not in error_message and "bot" not in error_message:
            print_error(f"Could not fetch info: {error}",
                        "Check your internet connection and URL.")
            return None
        print_warning("Info fetch blocked. Trying browser cookies.")

    cookie_option = get_browser_cookie_option()
    if not cookie_option:
        print_error("No working browser cookies.")
        return None
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True,
                        "cookiesfrombrowser": cookie_option}) as ydl:
            info = ydl.extract_info(url, download=False)
        return parse_info(info)
    except Exception as error:
        print_error(f"Could not fetch info with cookies: {error}")
        return None


def parse_info(info):
    if not isinstance(info, dict):
        raise ValueError("YouTube returned an unexpected response.")
    if "entries" in info:
        entries = [entry for entry in info["entries"] if entry]
        return {
            "type": "playlist",
            "title": info.get("title", "Unknown Playlist"),
            "uploader": info.get("uploader", "Unknown"),
            "video_count": len(entries),
            "videos": [entry.get("title", f"Video {i+1}")
                       for i, entry in enumerate(entries[:5])],
            "full_info": info,
        }
    return {
        "type": "video",
        "title": info.get("title", "Unknown"),
        "duration": info.get("duration", 0),
        "uploader": info.get("uploader", "Unknown"),
        "view_count": info.get("view_count", 0),
        "upload_date": info.get("upload_date", ""),
    }


# ─────────────────────────────────────────────────────────────────────
#  Display panels
# ─────────────────────────────────────────────────────────────────────

def display_video_info(info):
    print("\n" + "─" * 61)
    print("📹 VIDEO INFORMATION")
    print("─" * 61)
    print(f"📺 Title: {info['title']}")
    print(f"👤 Channel: {info['uploader']}")
    print(f"⏱️ Duration: {format_duration(info['duration'])}")
    print(f"👀 Views: {format_view_count(info['view_count'])}")
    upload_date = info.get("upload_date")
    if upload_date and len(upload_date) >= 8:
        print(f"📅 Upload date: {upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}")
    print("─" * 61)


def display_playlist_info(info):
    print("\n" + "─" * 61)
    print("📂 PLAYLIST INFORMATION")
    print("─" * 61)
    print(f"📺 Playlist: {info['title']}")
    print(f"👤 Channel: {info['uploader']}")
    print(f"🎬 Total Videos: {info['video_count']}")
    print("\n📹 First few videos:")
    for index, title in enumerate(info["videos"], 1):
        print(f"  {index}. {title[:50]}")
    print("─" * 61)


# ─────────────────────────────────────────────────────────────────────
#  Ledger for playlist downloads (parallel + retry-pass tracking)
# ─────────────────────────────────────────────────────────────────────

def _ledger_path(folder):
    return Path(folder) / ".linkcatty_state.json"


def _load_ledger(folder):
    p = _ledger_path(folder)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_ledger(folder, ledger):
    try:
        with open(_ledger_path(folder), "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _init_ledger_entry(video_id, title):
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "video_id": video_id,
        "title": title,
        "status": "pending",
        "attempts": 0,
        "last_error": None,
        "first_seen": now,
        "last_attempt": None,
    }


# ─────────────────────────────────────────────────────────────────────
#  Playlist download — parallel batches + retry passes
# ─────────────────────────────────────────────────────────────────────

def _download_one_video(video_id, output_dir, mode, config, cookie_option):
    """Worker used inside the ThreadPoolExecutor. Must be thread-safe."""
    options = build_download_options(output_dir, mode, config, quiet_progress=True)
    if cookie_option is not None:
        options["cookiesfrombrowser"] = cookie_option
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        return video_id, True, None
    except Exception as error:
        return video_id, False, str(error)


def _count_audio_video_files(folder):
    exts = {".mp3", ".mp4", ".mkv", ".webm", ".m4a", ".opus", ".ogg", ".flac", ".wav"}
    count = 0
    folder = Path(folder)
    if not folder.is_dir():
        return 0
    for root, _, files in os.walk(folder):
        for f in files:
            if Path(f).suffix.lower() in exts:
                count += 1
    return count


def _latest_media_file(folder, since_ts):
    """Return the newest audio/video file written to `folder` after `since_ts`."""
    folder = Path(folder)
    exts = {".mp3", ".mp4", ".mkv", ".webm", ".m4a", ".opus", ".ogg", ".flac", ".wav"}
    newest = None
    newest_mtime = since_ts
    for root, _, files in os.walk(folder):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() not in exts:
                continue
            try:
                mt = p.stat().st_mtime
            except OSError:
                continue
            if mt >= newest_mtime:
                newest_mtime = mt
                newest = p
    return newest


class _ProgressReporter:
    """Single-line progress bar with ETA — Spotify-style."""

    BAR_WIDTH = 40

    def __init__(self, folder, total, label):
        self.folder = folder
        self.total  = max(int(total), 1)
        self.label  = label
        self._start = time.time()
        self._stop  = threading.Event()
        self._thread = None
        self._lock  = threading.Lock()
        self._last_len = 0

    def start(self):
        self._render()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()
        self._render()
        with self._lock:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def set_label(self, label):
        with self._lock:
            self.label = label

    def say(self, message):
        with self._lock:
            sys.stdout.write("\r" + " " * self._last_len + "\r")
            sys.stdout.flush()
            print(message)
            self._last_len = 0

    def _loop(self):
        while not self._stop.wait(0.5):
            self._render()

    def _render(self):
        count   = _count_audio_video_files(self.folder)
        elapsed = max(time.time() - self._start, 0.001)
        remaining = max(self.total - count, 0)
        pct     = (count / self.total) * 100 if self.total else 0.0
        filled  = int(self.BAR_WIDTH * count / self.total) if self.total else 0
        filled  = max(0, min(self.BAR_WIDTH, filled))
        bar     = "█" * filled + "░" * (self.BAR_WIDTH - filled)

        eta_str = ""
        if count > 0 and remaining > 0:
            rate = count / elapsed
            if rate > 0:
                eta_str = f" · ETA {int(remaining / rate)}s"

        line = f"{self.label} |{bar}| {pct:5.1f}% {count}/{self.total}{eta_str}"
        with self._lock:
            pad = max(0, self._last_len - len(line))
            sys.stdout.write("\r" + line + (" " * pad))
            sys.stdout.flush()
            self._last_len = len(line)


def _write_failed_report(folder, playlist_title, total, success_count, failed_entries):
    report_path = Path(folder) / "failed_downloads.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("LinkCatty — failed / missing videos report\n")
        f.write(f"Playlist          : {playlist_title}\n")
        f.write(f"Generated         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Expected videos   : {total}\n")
        f.write(f"Downloaded videos : {success_count}\n")
        f.write(f"Missing videos    : {len(failed_entries)}\n")
        f.write("-" * 60 + "\n")
        for video_id, title, error in failed_entries:
            url = f"https://www.youtube.com/watch?v={video_id}" if video_id else "(no video id)"
            f.write(f"{title}\n  URL   : {url}\n  Error : {error}\n\n")
    return report_path


def _save_playlist_metadata(folder, playlist_info):
    """Write a compact playlist.info.json to the playlist folder."""
    try:
        full = playlist_info.get("full_info") or {}
        entries = [e for e in full.get("entries", []) if e]
        summary = {
            "title":       playlist_info.get("title"),
            "uploader":    playlist_info.get("uploader"),
            "video_count": playlist_info.get("video_count"),
            "saved_at":    datetime.now().isoformat(timespec="seconds"),
            "video_ids":   [e.get("id") for e in entries if e.get("id")],
        }
        with open(Path(folder) / "playlist.info.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def download_playlist(playlist_info, mode, config):
    full_info = playlist_info.get("full_info")
    if not full_info or "entries" not in full_info:
        print_error("Playlist information is missing or invalid.")
        return

    entries = [e for e in full_info["entries"] if e]
    total = len(entries)
    if total == 0:
        print_error("Playlist has no downloadable videos.")
        return
    print_success(f"Found {total} videos in playlist")
    if not confirm(f"\n🚀 Download all {total} videos?"):
        return

    playlist_title = re.sub(r'[<>:"/\\|?*]', "_", full_info.get("title", "Playlist"))
    playlist_folder = Path(config["download_dir"]) / playlist_title
    try:
        playlist_folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print_error(f"Could not create playlist folder: {error}")
        return

    _save_playlist_metadata(playlist_folder, playlist_info)

    youtube_config = config["youtube"]
    max_passes = int(youtube_config.get("max_retry_passes", 3))
    cooldown   = int(youtube_config.get("retry_delay_seconds", 8))
    parallel   = max(1, int(youtube_config.get("parallel_downloads", 3)))
    mode_label = "video (best quality)" if mode == "1" else "audio (MP3)"

    # ── startup summary (mirrors Spotify's panel) ───────────────────
    print()
    print("─" * 61)
    print("📋 PLAYLIST DOWNLOAD PLAN")
    print("─" * 61)
    print(f"  🎬 Mode             : {mode_label}")
    if mode == "1":
        print(f"  🎞️  Video quality    : "
              f"{youtube_config.get('video_quality', 'best')}")
    else:
        print(f"  🎵 Audio bitrate    : "
              f"{youtube_config.get('audio_quality', '320k')}")
    print(f"  📁 Output folder    : {playlist_folder}")
    print(f"  ⚡ Parallel workers : {parallel} concurrent downloads")
    print(f"  🔁 Retry passes     : {max_passes}")
    if youtube_config.get("save_metadata", True):
        print(f"  📝 Sidecar metadata : .info.json per video")
    if youtube_config.get("save_thumbnail", True):
        print(f"  🖼️  Thumbnails       : saved alongside each video")
    print("─" * 61)

    # ── build / merge ledger ────────────────────────────────────────
    ledger = _load_ledger(playlist_folder)
    for entry in entries:
        vid = entry.get("id")
        if not vid:
            continue
        if vid not in ledger:
            ledger[vid] = _init_ledger_entry(vid, entry.get("title", ""))
    _save_ledger(playlist_folder, ledger)

    # ── progress reporter ───────────────────────────────────────────
    reporter = _ProgressReporter(playlist_folder, total,
                                 f"⬇ Downloading 0/{total}")
    reporter.start()

    started_at = time.time()
    success_count = sum(1 for r in ledger.values() if r["status"] == "success")
    last_failed = []

    try:
        for attempt in range(1, max_passes + 1):
            pending = [
                e for e in entries
                if e.get("id")
                and ledger.get(e["id"], {}).get("status") != "success"
            ]
            if not pending:
                break

            reporter.set_label(
                f"⬇ Pass {attempt}/{max_passes} ({len(pending)} left)"
            )

            cookie_option = _COOKIE_OPTION

            with ThreadPoolExecutor(max_workers=parallel) as executor:
                futures = {
                    executor.submit(
                        _download_one_video,
                        e["id"], str(playlist_folder), mode, config, cookie_option,
                    ): e
                    for e in pending
                }

                completed = 0
                for future in as_completed(futures):
                    entry = futures[future]
                    vid = entry["id"]
                    title = entry.get("title", f"Video {vid}")
                    completed += 1

                    submit_ts = time.time() - 5   # look back a few seconds

                    try:
                        _, ok, err = future.result()
                    except Exception as exc:
                        ok, err = False, str(exc)

                    now = datetime.now().isoformat(timespec="seconds")
                    rec = ledger.setdefault(vid, _init_ledger_entry(vid, title))
                    rec["attempts"] += 1
                    rec["last_attempt"] = now

                    if ok:
                        rec["status"] = "success"
                        rec["last_error"] = None

                        # Try to find the file that was just written
                        written = _latest_media_file(playlist_folder, submit_ts)
                        size_str = ""
                        if written:
                            try:
                                size_str = f" ({_format_bytes(written.stat().st_size)})"
                            except OSError:
                                pass

                        print_success(
                            f"[{completed}/{len(pending)}] ✓ "
                            f"{title[:45]}{size_str}"
                        )
                        log_download("YouTube", title, mode=mode, status="Success")
                    else:
                        rec["status"] = "failed"
                        rec["last_error"] = err or "Unknown error"
                        print_error(
                            f"[{completed}/{len(pending)}] ✗ "
                            f"{title[:45]} — {(err or '')[:80]}"
                        )
                        log_download("YouTube", title, mode=mode,
                                     status="Failed", error=err or "")

                    _save_ledger(playlist_folder, ledger)
                    reporter.set_label(
                        f"⬇ Pass {attempt}/{max_passes} "
                        f"({completed}/{len(pending)})"
                    )
                    reporter._render()

            success_count = sum(
                1 for r in ledger.values() if r["status"] == "success"
            )
            last_failed = [
                (vid, ledger[vid].get("title", ""),
                 ledger[vid].get("last_error", ""))
                for vid in ledger
                if ledger[vid]["status"] != "success"
            ]

            if not last_failed:
                break

            bot_failures = [
                f for f in last_failed
                if "Sign in to confirm" in (f[2] or "")
                or "bot" in (f[2] or "").lower()
            ]
            if bot_failures and not _COOKIE_ATTEMPTED:
                reporter.say(
                    f"⚠️  {len(bot_failures)} video(s) hit a YouTube bot-check. "
                    f"Trying browser cookies…"
                )
                get_browser_cookie_option()

            if attempt < max_passes:
                reporter.say(
                    f"⚠️  {len(last_failed)} video(s) missing after pass "
                    f"{attempt}. Cooling down {cooldown}s before retrying…"
                )
                time.sleep(cooldown)
    finally:
        reporter.stop()

    elapsed = time.time() - started_at

    # ── summary panel (mirrors Spotify's result panel) ──────────────
    print()
    print("─" * 61)
    if not last_failed:
        print("✅ PLAYLIST DOWNLOAD COMPLETE — everything downloaded")
    else:
        print("⚠️  PLAYLIST FINISHED WITH MISSING VIDEOS")
    print("─" * 61)
    print(f"📺 Playlist    : {playlist_title}")
    print(f"📁 Saved to    : {playlist_folder}")
    print(f"🎵 Files       : {success_count}/{total} video(s)")
    if last_failed:
        print(f"❌ Missing     : {len(last_failed)}")
    print(f"⏱️  Elapsed     : {_format_elapsed(elapsed)}")
    if elapsed > 0 and success_count > 0:
        avg = elapsed / success_count
        print(f"⚡ Avg / video : {avg:.1f}s")
    if last_failed:
        report_path = _write_failed_report(
            playlist_folder, playlist_title, total, success_count, last_failed
        )
        print(f"📝 Failed list : {report_path}")
    print("─" * 61)


# ─────────────────────────────────────────────────────────────────────
#  Top-level content router
# ─────────────────────────────────────────────────────────────────────

def download_content(url, mode, config):
    start_spinner("🎬 Fetching video/playlist information")
    info = get_url_info(url)
    stop_spinner()
    if not info:
        return

    if info["type"] == "playlist":
        _show_session_header("📂 YouTube Downloader — Playlist")
        display_playlist_info(info)
        download_playlist(info, mode, config)
        return

    # ── single video: mode-aware confirmation ───────────────────────
    _show_session_header("📹 YouTube Downloader — Video")
    display_video_info(info)
    label = "video" if mode == "1" else "audio (MP3)"
    if not confirm(f"\n🚀 Download this {label}?"):
        print_info("Download cancelled")
        return

    start = time.time()
    success, error = download_single_video(
        url, config["download_dir"], mode, config
    )
    elapsed = time.time() - start

    if success:
        print_success(f"Download completed in {_format_elapsed(elapsed)}!")
        log_download("YouTube", info["title"], mode=mode, status="Success")
    else:
        print_error(f"Download failed: {error}")
        log_download("YouTube", info["title"], mode=mode,
                     status="Failed", error=error or "")


# ─────────────────────────────────────────────────────────────────────
#  Manual format + standard runner
# ─────────────────────────────────────────────────────────────────────

def run_manual_format(config):
    while True:
        url = input("\n🎯 YouTube URL (blank to go back): ").strip()
        if not url:
            return
        if not is_youtube_url(url):
            print_error("Not a valid YouTube URL",
                        "URL should start with http(s) and contain youtube.com or youtu.be.")
            continue
        try:
            print_info("Fetching available formats...")
            with YoutubeDL({"quiet": True, "listformats": True}) as ydl:
                ydl.extract_info(url, download=False)
            format_id = input("🎯 Enter format ID: ").strip()
            if not format_id:
                print_error("No format ID provided",
                            "Enter one of the listed format IDs.")
                continue
            options = build_download_options(config["download_dir"], "1", config)
            options["format"] = format_id
            start_spinner("Downloading custom format")
            with YoutubeDL(options) as ydl:
                ydl.download([url])
            stop_spinner()
            print_success("Download completed!")
            log_download("YouTube", url, mode="Manual Format", status="Success")
        except Exception as error:
            stop_spinner()
            print_error(f"Manual download failed: {error}",
                        "Check the URL, format ID, and network connection.")
        if not confirm("\nDownload another manual format?"):
            return


def run_standard_downloads(mode, config):
    while True:
        url = input("\n🎯 YouTube URL (video or playlist, blank to go back): ").strip()
        if not url:
            return
        if is_youtube_url(url):
            download_content(url, mode, config)
        else:
            print_error("Not a valid YouTube URL",
                        "URL should start with http(s) and contain youtube.com or youtu.be.")
        if not confirm("\nDownload another?"):
            return


def run(config):
    while True:
        clear_screen()
        print_banner()
        print(f"{BOLD}                   🎬 YouTube Downloader")
        print("=" * 61)
        print()
        print(f"{CYAN}{BOLD}1.{RESET} Download video (best quality)")
        print(f"{CYAN}{BOLD}2.{RESET} Download audio (MP3)")
        print(f"{CYAN}{BOLD}3.{RESET} Manual format selection")
        print(f"{CYAN}{BOLD}4.{RESET} Back to main menu")
        print()
        print("=" * 61)
        mode = menu_choice("Select (1-4): ", "1234")
        if mode in (None, "4"):
            return
        try:
            if mode == "3":
                run_manual_format(config)
            else:
                run_standard_downloads(mode, config)
        except Exception as error:
            stop_spinner()
            print_error(f"YouTube workflow error: {error}",
                        "You remain in the YouTube Downloader.")
            pause()