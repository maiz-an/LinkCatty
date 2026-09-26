import re
import time
import json
import threading
import os
from collections import Counter
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from yt_dlp import YoutubeDL

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    DownloadProgress,
    SilentLogger,
    ask_url,
    card,
    confirm,
    fit,
    format_bytes,
    format_count,
    format_duration,
    format_eta,
    item_line,
    note_line,
    pause,
    plan_line,
    print_error,
    print_info,
    print_warning,
    result_card,
    section_header,
    show_menu,
    start_spinner,
    stop_spinner,
    strip_ansi,
)


# ─────────────────────────────────────────────────────────────────────
#  Small helpers
# ─────────────────────────────────────────────────────────────────────

def _clean_error(error):
    """yt-dlp error text without color codes or the ERROR: prefix."""
    text = strip_ansi(str(error)).strip()
    text = re.sub(r"^ERROR:\s*", "", text)
    return text.split("; please report")[0].strip()


def _short_reason(error, width=34):
    """A short, single-line reason for a failed video."""
    text = re.sub(r"^\[[^\]]+\]\s*[\w-]+:\s*", "", _clean_error(error))
    text = re.sub(r"\s*\(caused by .*$", "", text).replace("<", "").replace(">", "")
    if len(text) > width and ": " in text:
        text = text.rsplit(": ", 1)[-1]          # the specific cause is last
    text = text.split(". ")[0]                    # first sentence only
    return fit(text or "download error", width)


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

def build_download_options(output_dir, mode, config, progress=None):
    youtube_config = config["youtube"]

    options = {
        "outtmpl": str(Path(output_dir) / "%(title)s - %(uploader)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": SilentLogger(),
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

    if progress is not None:
        options["progress_hooks"] = [progress.hook]
        options["postprocessor_hooks"] = [progress.pp_hook]

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
#  Single-video download (used by the single-video flow)
# ─────────────────────────────────────────────────────────────────────

def _say(progress, message):
    if progress is not None:
        progress.say(message)
    else:
        print(message)


def _cookie_option(progress):
    """get_browser_cookie_option() asks the user something, so pause the bar."""
    if progress is None:
        return get_browser_cookie_option()
    with progress.paused():
        return get_browser_cookie_option()


def download_single_video(video_url, output_dir, mode, config, progress=None):
    options = build_download_options(output_dir, mode, config, progress)

    if _COOKIE_OPTION is not None:
        options["cookiesfrombrowser"] = _COOKIE_OPTION

    try:
        with YoutubeDL(options) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as error:
        error_message = _clean_error(error)
        if "Sign in to confirm" not in error_message and "bot" not in error_message:
            return False, error_message
        if _COOKIE_ATTEMPTED and _COOKIE_OPTION is None:
            return False, ("Blocked (sign-in required) — no working browser "
                           "cookies found earlier this session.")
        _say(progress, note_line(
            "YouTube asked for a sign-in, trying your browser cookies", "🍪"))

    cookie_option = _cookie_option(progress)
    if not cookie_option:
        return False, "No working browser cookies. Try logging into YouTube in your browser."
    options["cookiesfrombrowser"] = cookie_option
    if progress is not None:
        progress.item_reset()
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as error:
        return False, _clean_error(error)


# ─────────────────────────────────────────────────────────────────────
#  Info fetching
# ─────────────────────────────────────────────────────────────────────

def get_url_info(url):
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        return parse_info(info)
    except Exception as error:
        error_message = _clean_error(error)
        if "Sign in to confirm" not in error_message and "bot" not in error_message:
            print_error(f"Could not fetch info: {_short_reason(error, 120)}",
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
        print_error(f"Could not fetch info with cookies: {_short_reason(error, 100)}")
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
#  Display panels (drawn with the shared UI kit)
# ─────────────────────────────────────────────────────────────────────

def display_video_info(info):
    date = info.get("upload_date") or ""
    uploaded = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) >= 8 else None
    card("VIDEO", [
        ("Title", info["title"]),
        ("Channel", info["uploader"]),
        ("Duration", format_duration(info["duration"])),
        ("Views", format_count(info["view_count"])),
        ("Uploaded", uploaded),
    ], icon="📹")


def display_playlist_info(info):
    card("PLAYLIST", [
        ("Name", info["title"]),
        ("Channel", info["uploader"]),
        ("Videos", info["video_count"]),
    ], icon="📂",
        details=[f"{index}. {title}" for index, title in enumerate(info["videos"], 1)])


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
    if not confirm(f"Download all {total} videos?", default=True):
        return

    section_title = "📂 YouTube Downloader — Playlist"
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
    if mode == "1":
        quality_label = f"Video {youtube_config.get('video_quality', 'best')}"
    else:
        quality_label = f"MP3 {youtube_config.get('audio_quality', '320k')}"

    plan_line(quality_label, f"{parallel} parallel", f"up to {max_passes} passes")

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
    reporter = DownloadProgress(
        "Downloading", total, unit="videos",
        count_fn=lambda: _count_audio_video_files(playlist_folder))
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

            reporter.set_label(f"Pass {attempt}/{max_passes}")

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
                                size_str = format_bytes(written.stat().st_size)
                            except OSError:
                                pass

                        reporter.say(item_line(True, completed, len(pending),
                                               title, size_str))
                        log_download("YouTube", title, mode=mode, status="Success")
                    else:
                        rec["status"] = "failed"
                        rec["last_error"] = _clean_error(err or "Unknown error")
                        reporter.say(item_line(False, completed, len(pending),
                                               title, _short_reason(err)))
                        log_download("YouTube", title, mode=mode,
                                     status="Failed", error=rec["last_error"])

                    _save_ledger(playlist_folder, ledger)
                    reporter.set_label(
                        f"Pass {attempt}/{max_passes} · {completed}/{len(pending)}")
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
                reporter.say(note_line(
                    f"{len(bot_failures)} video(s) hit a YouTube bot-check, "
                    "trying your browser cookies", "🍪"))
                with reporter.paused():
                    get_browser_cookie_option()

            if attempt < max_passes:
                reporter.say(note_line(
                    f"{len(last_failed)} left after pass {attempt} "
                    f"· retrying in {cooldown}s"))
                time.sleep(cooldown)
    finally:
        reporter.stop()

    elapsed = time.time() - started_at

    # ── result card ─────────────────────────────────────────────────
    section_header(section_title)
    rows = [("Playlist", playlist_title), ("Saved to", str(playlist_folder)),
            ("Files", f"{success_count} of {total}")]
    if not last_failed:
        rows.append(("Time", format_eta(elapsed)))
        result_card("ok", "DOWNLOAD COMPLETE", rows)
        return
    rows += [("Missing", len(last_failed)), ("Time", format_eta(elapsed))]
    reasons = Counter(_short_reason(f[2] or "Unknown error") for f in last_failed)
    details = [f"{text}  ×{count}" for text, count in reasons.most_common(4)]
    report_path = _write_failed_report(
        playlist_folder, playlist_title, total, success_count, last_failed
    )
    result_card("warn" if success_count else "fail",
                "FINISHED WITH MISSING VIDEOS" if success_count else "DOWNLOAD FAILED",
                rows, details, [("Report", str(report_path))])


# ─────────────────────────────────────────────────────────────────────
#  Top-level content router
# ─────────────────────────────────────────────────────────────────────

def _file_size(path):
    try:
        return format_bytes(os.path.getsize(path)) if path else None
    except OSError:
        return None


def download_content(url, mode, config):
    start_spinner("🎬 Fetching video/playlist information")
    info = get_url_info(url)
    stop_spinner()
    if not info:
        return

    if info["type"] == "playlist":
        section_header("📂 YouTube Downloader — Playlist")
        display_playlist_info(info)
        download_playlist(info, mode, config)
        return

    # ── single video ────────────────────────────────────────────────
    title = "📹 YouTube Downloader — Video"
    section_header(title)
    display_video_info(info)
    if not confirm("Proceed with download?", default=True):
        return

    youtube_config = config["youtube"]
    if mode == "1":
        plan_line(f"Video {youtube_config.get('video_quality', 'best')}")
    else:
        plan_line(f"MP3 {youtube_config.get('audio_quality', '320k')}")

    progress = DownloadProgress("Downloading", 1)
    progress.start()
    start = time.time()
    try:
        success, error = download_single_video(
            url, config["download_dir"], mode, config, progress
        )
        if success:
            progress.item_done()
    finally:
        progress.stop()
    elapsed = time.time() - start

    section_header(title)
    if success:
        result_card("ok", "DOWNLOAD COMPLETE", [
            ("Title", info["title"]),
            ("Saved to", config["download_dir"]),
            ("Size", _file_size(progress.final_path)),
            ("Time", format_eta(elapsed)),
        ])
        log_download("YouTube", info["title"], mode=mode, status="Success")
    else:
        result_card("fail", "DOWNLOAD FAILED", [
            ("Title", info["title"]),
            ("Time", format_eta(elapsed)),
        ])
        print_error(_short_reason(error, 200))
        log_download("YouTube", info["title"], mode=mode,
                     status="Failed", error=error or "")


# ─────────────────────────────────────────────────────────────────────
#  Manual format + standard runner
# ─────────────────────────────────────────────────────────────────────

def run_manual_format(config):
    title = "🎬 YouTube Downloader — Manual format"
    while True:
        url = ask_url("YouTube video")
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
            progress = DownloadProgress("Downloading", 1)
            options = build_download_options(config["download_dir"], "1", config, progress)
            options["format"] = format_id
            progress.start()
            start = time.time()
            try:
                with YoutubeDL(options) as ydl:
                    ydl.download([url])
                progress.item_done()
            finally:
                progress.stop()
            section_header(title)
            result_card("ok", "DOWNLOAD COMPLETE", [
                ("Format", format_id),
                ("Saved to", config["download_dir"]),
                ("Size", _file_size(progress.final_path)),
                ("Time", format_eta(time.time() - start)),
            ])
            log_download("YouTube", url, mode="Manual Format", status="Success")
        except Exception as error:
            stop_spinner()
            print_error(f"Manual download failed: {_short_reason(error, 120)}",
                        "Check the URL, format ID, and network connection.")
        if not confirm("\nProcess another link?"):
            return


def run_standard_downloads(mode, config):
    while True:
        url = ask_url("YouTube video or playlist")
        if not url:
            return
        if is_youtube_url(url):
            download_content(url, mode, config)
        else:
            print_error("Not a valid YouTube URL",
                        "URL should start with http(s) and contain youtube.com or youtu.be.")
        if not confirm("\nProcess another link?"):
            return


def run(config):
    while True:
        mode = show_menu("🎬 YouTube Downloader", [
            "Download video (best quality)",
            "Download audio (MP3)",
            "Manual format selection",
            "Back to main menu",
        ])
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
