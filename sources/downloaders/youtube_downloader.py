import random
import re
import time
import json
import threading
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled

from utils.config import is_block_error
from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    DownloadProgress,
    ERROR_LABELS,
    SHORT_REASONS,
    SilentLogger,
    apply_strategy,
    ask_retry_vpn,
    ask_url,
    card,
    classify_error,
    confirm,
    final_path,
    fit,
    format_bytes,
    format_count,
    format_duration,
    format_eta,
    is_final_failure,
    item_line,
    pause,
    plan_line,
    print_error,
    print_info,
    print_warning,
    result_card,
    scrub_error,
    section_header,
    show_failure_now,
    show_menu,
    start_spinner,
    stop_spinner,
    strategy_for_pass,
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

def build_download_options(output_dir, mode, config, progress=None, strategy=None):
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
        "writeinfojson":     bool(youtube_config.get("save_metadata", False)),
        "writethumbnail":    bool(youtube_config.get("save_thumbnail", False)),
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

    if strategy is not None:
        apply_strategy(options, strategy)
        if strategy[1] and mode == "1":          # relaxed pass: any quality will do
            options["format"] = "bestvideo+bestaudio/best"

    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg
    return options


def _retry_settings(config):
    """(passes, cooldown, rate-limit cooldown) - retries run silently."""
    yt = config["youtube"]
    passes = max(1, int(yt.get("max_retry_passes", 3))) if yt.get("auto_retry", True) else 1
    cooldown = max(0, int(yt.get("retry_delay_seconds", 8)))
    return passes, cooldown, max(cooldown, int(yt.get("rate_limit_cooldown_seconds", 45)))


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


def download_single_video(video_url, output_dir, mode, config, progress=None,
                          format_id=None):
    """Download one video. Failed attempts are retried silently (more patience
    each time); returns (success, error message)."""
    passes, cooldown, rate_cooldown = _retry_settings(config)
    error, attempt = None, 0
    while attempt < passes:
        attempt += 1
        options = build_download_options(output_dir, mode, config, progress,
                                         strategy_for_pass(attempt))
        if format_id:
            options["format"] = format_id
        if _COOKIE_OPTION is not None:
            options["cookiesfrombrowser"] = _COOKIE_OPTION
        try:
            with YoutubeDL(options) as ydl:
                if getattr(progress, "watch", None):
                    progress.watch(ydl)
                ydl.download([video_url])
            return True, None
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            error = _clean_error(exc)
            kind = classify_error(scrub_error(exc))
        if progress is not None:
            progress.item_reset()
        if kind == "login":
            if _COOKIE_ATTEMPTED:
                break
            if not _cookie_option(progress):
                return False, "No working browser cookies. Try logging into YouTube in your browser."
            attempt -= 1                      # the login pass does not use up a retry
            continue
        if is_final_failure(kind, attempt) or attempt >= passes:
            break
        time.sleep(rate_cooldown if kind == "rate_limited" else cooldown)
    return False, error


# ─────────────────────────────────────────────────────────────────────
#  Info fetching
# ─────────────────────────────────────────────────────────────────────

def _normalize_url(url):
    """Turn what people paste into what we actually want to download.

    * video + auto-generated "mix" (list=RD...)  -> just that video
    * channel page (@name, /channel/, /c/, /user/) -> its Videos tab (uploads)
    """
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    host = (parts.hostname or "").lower()
    if query.get("list", [""])[0].startswith("RD") and (
            "v" in query or host.endswith("youtu.be")):
        keep = {k: v for k, v in query.items() if k == "v"}
        return urlunsplit((parts.scheme, parts.netloc, parts.path,
                           urlencode(keep, doseq=True), ""))
    if re.fullmatch(r"/(@[^/]+|channel/[^/]+|c/[^/]+|user/[^/]+)/?", parts.path):
        return urlunsplit((parts.scheme, parts.netloc,
                           parts.path.rstrip("/") + "/videos", "", ""))
    return url


def _info_options(cookie_option=None):
    """Fast info fetch: playlists/channels are listed flat (titles and ids
    only) instead of loading every single video, and one bad entry cannot
    abort the whole listing."""
    options = {
        "quiet": True,
        "no_warnings": True,
        "logger": SilentLogger(),
        "extract_flat": "in_playlist",
    }
    if cookie_option:
        options["cookiesfrombrowser"] = cookie_option
    return options


def _fetch_hint(error):
    text = _clean_error(error).lower()
    if any(t in text for t in ("premieres in", "will begin in", "live event",
                               "upcoming")):
        return "It is not available yet. Try again once it has started."
    if any(t in text for t in ("private video", "unavailable", "removed")):
        return "The video may be private, removed or region-locked."
    return "Check your internet connection and URL."


def get_url_info(url):
    try:
        with YoutubeDL(_info_options()) as ydl:
            info = ydl.extract_info(url, download=False)
        return parse_info(info)
    except Exception as error:
        error_message = _clean_error(error)
        if "Sign in to confirm" not in error_message and "bot" not in error_message:
            print_error(f"Could not fetch info: {_short_reason(error, 120)}",
                        _fetch_hint(error))
            return None
        print_warning("Info fetch blocked. Trying browser cookies.")

    cookie_option = get_browser_cookie_option()
    if not cookie_option:
        print_error("No working browser cookies.")
        return None
    try:
        with YoutubeDL(_info_options(cookie_option)) as ydl:
            info = ydl.extract_info(url, download=False)
        return parse_info(info)
    except Exception as error:
        print_error(f"Could not fetch info with cookies: {_short_reason(error, 100)}",
                    _fetch_hint(error))
        return None


def parse_info(info):
    if not isinstance(info, dict):
        raise ValueError("YouTube returned an unexpected response.")
    if "entries" in info:
        listed = [entry for entry in info["entries"] if entry]
        # not-yet-released premieres and live streams cannot be downloaded
        entries = [e for e in listed
                   if e.get("live_status") not in ("is_upcoming", "is_live")]
        info["entries"] = entries          # a list, so it can be read again later
        return {
            "type": "playlist",
            "title": info.get("title", "Unknown Playlist"),
            "uploader": info.get("uploader", "Unknown"),
            "video_count": len(entries),
            "skipped": len(listed) - len(entries),
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
        ("Skipped", f'{info["skipped"]} upcoming/live' if info.get("skipped") else None),
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
        "error_type": None,
        "last_error": None,
        "reach_error": False,
        "final": False,
        "strategies_tried": [],
        "file": None,
        "first_seen": now,
        "last_attempt": None,
    }


# ─────────────────────────────────────────────────────────────────────
#  Playlist download - parallel workers, silent retry passes
# ─────────────────────────────────────────────────────────────────────

def _download_one_video(video_id, output_dir, mode, config, cookie_option,
                        strategy, abort):
    """Worker used inside the ThreadPoolExecutor. Must be thread-safe.
    Returns (video_id, ok, error message, file path, title)."""
    def check_abort(_data):
        if abort.is_set():
            raise DownloadCancelled()

    try:
        if abort.is_set():
            raise DownloadCancelled()
        options = build_download_options(output_dir, mode, config, None, strategy)
        options["progress_hooks"] = [check_abort]
        if cookie_option is not None:
            options["cookiesfrombrowser"] = cookie_option
        url = f"https://www.youtube.com/watch?v={video_id}"
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
        title = info.get("title") if isinstance(info, dict) else None
        return video_id, True, None, final_path(info), title
    except Exception as error:
        return video_id, False, _clean_error(error), None, None


def _write_failed_report(folder, playlist_title, total, success_count, failed, breakdown):
    report_path = Path(folder) / "failed_downloads.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("LinkCatty - failed / missing videos report\n")
        f.write(f"Playlist          : {playlist_title}\n")
        f.write(f"Generated         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Expected videos   : {total}\n")
        f.write(f"Downloaded videos : {success_count}\n")
        f.write(f"Missing videos    : {len(failed)}\n")
        f.write("-" * 60 + "\n")
        if breakdown:
            f.write("Breakdown by cause:\n")
            for label, count in breakdown.items():
                f.write(f"  - {label}: {count}\n")
            f.write("-" * 60 + "\n")
        f.write("Per-video detail:\n\n")
        for rec in failed:
            cause = ERROR_LABELS.get(rec.get("error_type"), ERROR_LABELS["other"])
            f.write(f"{rec.get('title') or 'Unknown title'}\n")
            f.write(f"    URL        : https://www.youtube.com/watch?v={rec['video_id']}\n")
            f.write(f"    Cause      : {cause}\n")
            f.write(f"    Last error : {rec.get('last_error') or 'n/a'}\n")
            f.write(f"    Attempts   : {rec.get('attempts', 0)}\n\n")
        f.write("-" * 60 + "\n")
        f.write("Tip: run the same playlist link again (even in a new session).\n"
                "LinkCatty keeps a ledger (.linkcatty_state.json) next to this\n"
                "report, so finished videos are skipped and only the videos listed\n"
                "above are retried.\n")
        if ERROR_LABELS["blocked"] in breakdown:
            f.write("\nSome failures were your network cutting the connection. Turn on\n"
                    "your VPN and run the link again.\n")
    return report_path


def _needs_work(rec):
    return rec["status"] != "success" and not rec.get("final")


def download_playlist(playlist_info, mode, config):
    full_info = playlist_info.get("full_info")
    if not full_info or "entries" not in full_info:
        print_error("Playlist information is missing or invalid.")
        return

    entries = [e for e in full_info["entries"] if e]
    if not entries:
        print_error("Playlist has no downloadable videos.")
        return
    if not confirm(f"Download all {len(entries)} videos?", default=True):
        return

    section_title = "📂 YouTube Downloader — Playlist"
    playlist_title = re.sub(r'[<>:"/\\|?*]', "_", full_info.get("title", "Playlist"))
    playlist_folder = Path(config["download_dir"]) / playlist_title
    try:
        playlist_folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print_error(f"Could not create playlist folder: {error}")
        return

    youtube_config = config["youtube"]
    max_passes, cooldown, rate_cooldown = _retry_settings(config)
    parallel = max(1, int(youtube_config.get("parallel_downloads", 3)))
    if mode == "1":
        quality_label = f"Video {youtube_config.get('video_quality', 'best')}"
    else:
        quality_label = f"MP3 {youtube_config.get('audio_quality', '320k')}"

    # ── build / merge ledger (a re-run resumes where it stopped) ────
    ledger = _load_ledger(playlist_folder)
    keys = []
    for entry in entries:
        vid = entry.get("id")
        if not vid or vid in keys:
            continue
        keys.append(vid)
        rec = ledger.setdefault(vid, _init_ledger_entry(vid, entry.get("title", "")))
        if not rec.get("title"):
            rec["title"] = entry.get("title", "")
    if not keys:
        print_error("Playlist has no downloadable videos.")
        return
    for vid in keys:
        rec = ledger[vid]
        if rec["status"] == "success" and rec.get("file") \
                and not os.path.exists(rec["file"]):
            rec["status"] = "pending"           # the user deleted it
        if rec["status"] != "success":
            rec.update(status="pending", final=False)
    _save_ledger(playlist_folder, ledger)

    total = len(keys)
    position = {vid: i for i, vid in enumerate(keys, 1)}
    done = lambda: sum(1 for vid in keys if ledger[vid]["status"] == "success")
    already = done()
    plan_line(quality_label, f"{parallel} parallel",
              f"resuming, {already}/{total} done" if already else None)

    started_at = time.time()
    abort = threading.Event()

    def run_round():
        reporter = DownloadProgress("Downloading", total, unit="videos", count_fn=done)
        reporter.start()
        workers = parallel
        limit, attempt = max_passes, 0
        try:
            while attempt < limit:
                attempt += 1
                pending = [v for v in keys if _needs_work(ledger[v])]
                if not pending:
                    break
                strategy = strategy_for_pass(attempt)
                last_pass = attempt == limit
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {executor.submit(
                        _download_one_video, vid, str(playlist_folder), mode,
                        config, _COOKIE_OPTION, strategy, abort): vid
                        for vid in pending}
                    try:
                        for future in as_completed(futures):
                            vid, ok, err, path, title = future.result()
                            rec = ledger[vid]
                            rec["attempts"] += 1
                            rec["last_attempt"] = datetime.now().isoformat(timespec="seconds")
                            if strategy[0] not in rec["strategies_tried"]:
                                rec["strategies_tried"].append(strategy[0])
                            if title and not rec.get("title"):
                                rec["title"] = title
                            name = rec.get("title") or vid
                            if ok:
                                rec.update(status="success", last_error=None,
                                           error_type=None, reach_error=False,
                                           final=False, file=path)
                                reporter.say(item_line(True, position[vid], total,
                                                       name, _file_size(path) or ""))
                                log_download("YouTube", name, mode=mode, status="Success")
                            else:
                                scrubbed = scrub_error(err or "")
                                kind = classify_error(scrubbed)
                                rec.update(status="failed", last_error=_short_reason(err, 200),
                                           error_type=kind,
                                           reach_error=is_block_error(scrubbed),
                                           final=is_final_failure(kind, attempt))
                                if show_failure_now(kind, last_pass):
                                    detail = (SHORT_REASONS[kind] if kind != "other"
                                              else _short_reason(err))
                                    reporter.say(item_line(False, position[vid], total,
                                                           name, detail))
                            _save_ledger(playlist_folder, ledger)
                    except KeyboardInterrupt:
                        abort.set()
                        for future in futures:
                            future.cancel()
                        raise

                # bot-check / members-only: offer the browser cookies once
                login_failed = [v for v in keys if ledger[v]["status"] != "success"
                                and ledger[v].get("error_type") == "login"]
                if login_failed and not _COOKIE_ATTEMPTED:
                    with reporter.paused():
                        cookies = get_browser_cookie_option()
                    if cookies:
                        for vid in login_failed:
                            ledger[vid].update(status="pending", final=False)
                        limit = max(limit, attempt + 1)   # one pass with the cookies
                        _save_ledger(playlist_folder, ledger)

                remaining = [v for v in keys if _needs_work(ledger[v])]
                if not remaining:
                    break
                if attempt < limit:
                    rate_limited = any(ledger[v].get("error_type") == "rate_limited"
                                       for v in remaining)
                    if rate_limited:
                        workers = max(1, workers // 2)   # ease off the site
                    wait = rate_cooldown if rate_limited else cooldown
                    if wait:
                        time.sleep(random.uniform(wait, wait + 3))
        finally:
            reporter.stop()

    try:
        while True:
            before = done()
            run_round()
            reach = [v for v in keys if ledger[v]["status"] != "success"
                     and ledger[v].get("reach_error")]
            # a real block stops everything; a single flaky video does not
            if reach and done() == before and ask_retry_vpn():
                for vid in reach:
                    ledger[vid].update(status="pending", final=False)
                continue
            break
    except KeyboardInterrupt:
        _save_ledger(playlist_folder, ledger)
        print_warning("Cancelled. Run the same link again to resume where it stopped.")
        return

    elapsed = time.time() - started_at
    success_count = done()
    failed = [ledger[v] for v in keys if ledger[v]["status"] != "success"]
    breakdown = {}
    for rec in failed:
        label = ERROR_LABELS.get(rec.get("error_type") or "other", ERROR_LABELS["other"])
        breakdown[label] = breakdown.get(label, 0) + 1
    for rec in failed:
        log_download("YouTube", rec.get("title") or rec["video_id"], mode=mode,
                     status="Failed", error=rec.get("last_error") or "")

    # ── result card ─────────────────────────────────────────────────
    section_header(section_title)
    rows = [("Playlist", playlist_title), ("Saved to", str(playlist_folder)),
            ("Files", f"{success_count} of {total}")]
    if not failed:
        rows.append(("Time", format_eta(elapsed)))
        result_card("ok", "DOWNLOAD COMPLETE", rows)
        return
    rows += [("Missing", len(failed)), ("Time", format_eta(elapsed))]
    details = [f"{label}  ×{count}" for label, count in breakdown.items()]
    report_path = _write_failed_report(playlist_folder, playlist_title, total,
                                       success_count, failed, breakdown)
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
    url = _normalize_url(url)
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

    start = time.time()
    while True:
        progress = DownloadProgress("Downloading", 1)
        progress.start()
        try:
            success, error = download_single_video(
                url, config["download_dir"], mode, config, progress
            )
            if success:
                progress.item_done()
        finally:
            progress.stop()
        if not success and is_block_error(error or "") and ask_retry_vpn():
            continue
        break
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
        url = _normalize_url(url)
        try:
            print_info("Fetching available formats...")
            with YoutubeDL({"quiet": True, "listformats": True}) as ydl:
                ydl.extract_info(url, download=False)
            format_id = input("🎯 Enter format ID (0 or blank to go back): ").strip()
            if format_id in ("", "0"):
                continue
            start = time.time()
            while True:
                progress = DownloadProgress("Downloading", 1)
                progress.start()
                try:
                    success, error = download_single_video(
                        url, config["download_dir"], "1", config, progress,
                        format_id=format_id)
                    if success:
                        progress.item_done()
                finally:
                    progress.stop()
                if not success and is_block_error(error or "") and ask_retry_vpn():
                    continue
                break
            section_header(title)
            if success:
                result_card("ok", "DOWNLOAD COMPLETE", [
                    ("Format", format_id),
                    ("Saved to", config["download_dir"]),
                    ("Size", _file_size(progress.final_path)),
                    ("Time", format_eta(time.time() - start)),
                ])
                log_download("YouTube", url, mode="Manual Format", status="Success")
            else:
                result_card("fail", "DOWNLOAD FAILED", [
                    ("Format", format_id),
                    ("Time", format_eta(time.time() - start)),
                ])
                print_error(_short_reason(error, 200),
                            "Check the format ID and try again.")
                log_download("YouTube", url, mode="Manual Format",
                             status="Failed", error=error or "")
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
        ])
        if mode in (None, "0"):
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
