#!/usr/bin/env python3
"""
Other Downloader - paste any video or playlist link.

Same look and failure handling as the Spotify downloader: header, info
panel, one live progress bar, classified errors, multi-pass retries with
cooldowns, a resumable ledger (playlists) and a failed-items report.
Site profiles (ph.py, xm.py) only supply URL matching / member login.
"""
import json
import os
import random
import re
import time
from datetime import datetime

from yt_dlp import YoutubeDL

from downloaders import ph, xm
from utils.config import is_block_error, run_with_proxy_fallback
from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    BOLD, CYAN, RESET,
    DownloadProgress, SilentLogger,
    ask_retry_vpn, clear_screen, confirm, explain_error, format_bytes,
    format_count, format_duration, format_eta, menu_choice, pause,
    print_banner, print_error, print_info, print_warning,
    start_spinner, stop_spinner, strip_ansi,
)

_SECTION = "🌐 Other Downloader"
_SITES = (ph, xm)


# ─────────────────────────────────────────────────────────────────────
#  Display helpers
# ─────────────────────────────────────────────────────────────────────

def _show_session_header(title: str) -> None:
    clear_screen()
    print_banner()
    print(f"{BOLD}               {title}{RESET}")
    print("=" * 61)


def _quality_label(quality: str) -> str:
    return "Best available" if quality == "best" else f"{quality}p"


def _display_video_info(info: dict, heights: list) -> None:
    print("\n" + "─" * 61)
    print("🎬 VIDEO INFORMATION")
    print("─" * 61)
    print(f"🎞️ Title    : {info.get('title') or 'Unknown'}")
    uploader = info.get("uploader") or info.get("channel") or info.get("uploader_id")
    print(f"📺 Channel  : {uploader or 'Unknown'}")
    if info.get("duration"):
        print(f"⏱️ Duration : {format_duration(info['duration'])}")
    if info.get("view_count"):
        print(f"👀 Views    : {format_count(info['view_count'])}")
    if heights:
        print(f"🖥️ Quality  : {' · '.join(f'{h}p' for h in heights[:6])}")
    print("─" * 61)


def _display_playlist_info(info: dict, count: int) -> None:
    print("\n" + "─" * 61)
    print("📂 PLAYLIST INFORMATION")
    print("─" * 61)
    print(f"📋 Playlist    : {info.get('title') or 'Unknown'}")
    uploader = info.get("uploader") or info.get("channel")
    if uploader:
        print(f"👤 Author      : {uploader}")
    print(f"🎬 Total Videos: {count}")
    print("─" * 61)


def _display_result(kind: str, name, out_folder: str, result: dict) -> None:
    downloaded, expected = result["downloaded"], result["expected"]
    complete = downloaded >= expected
    print("\n" + "─" * 61)
    if complete:
        print("✅ DOWNLOAD COMPLETE — everything downloaded")
    else:
        print("⚠️  DOWNLOAD FINISHED WITH MISSING VIDEOS")
    print("─" * 61)
    if name:
        label = {"video": "🎬 Video", "playlist": "📋 Playlist"}[kind]
        print(f"{label}    : {name}")
    print(f"📁 Saved to  : {out_folder}")
    print(f"🎞️ Files     : {downloaded}/{expected} video file(s)")
    if result.get("size"):
        print(f"💾 Size      : {format_bytes(result['size'])}")
    if not complete:
        print(f"❌ Missing   : {max(expected - downloaded, 0)}")
        if result["breakdown"]:
            print("   Breakdown  :")
            for label, count in result["breakdown"].items():
                print(f"     • {label}: {count}")
        if result["failed_report"]:
            print(f"📝 Failed list saved to : {result['failed_report']}")
    print(f"⏱️ Elapsed   : {format_eta(result['elapsed'])}")
    print("─" * 61)
    if not complete and result.get("first_failure") and len(result["breakdown"]) == 1:
        message, hint = result["first_failure"]
        print_error(message, hint)


# ─────────────────────────────────────────────────────────────────────
#  Error classification
# ─────────────────────────────────────────────────────────────────────

_ERROR_LABELS = {
    "login":        "Members-only content (login required)",
    "blocked":      "Blocked by your network (connection reset)",
    "network":      "Network / timeout error",
    "rate_limited": "Rate-limited or refused by the site",
    "unavailable":  "Video removed, private, or region-locked",
    "unsupported":  "Link not supported",
    "format":       "Requested quality not available",
    "disk":         "Disk full or folder not writable",
    "other":        "Other / unclassified error",
}

# Retrying these with the same setup cannot help; they wait for the user
# (login / VPN) or are simply final.
_NON_RETRYABLE = {"login", "blocked", "unavailable", "unsupported", "disk"}


def _scrub(exc) -> str:
    """Error text without color codes, extractor tag, id prefix or URLs."""
    text = strip_ansi(str(exc)).strip()
    text = re.sub(r"^ERROR:\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*\S+:\s*", "", text)
    return re.sub(r"https?://\S+", "", text)


def _classify_error(message: str) -> str:
    msg = (message or "").lower()
    if any(t in msg for t in ("no space left", "disk full", "permission denied",
                              "access is denied", "errno 28")):
        return "disk"
    if any(t in msg for t in ("premium", "sign in", "log in", "login",
                              "members only", "members-only", "subscribe")):
        return "login"
    if "unsupported url" in msg:
        return "unsupported"
    if any(t in msg for t in ("too many requests", "rate limit", "captcha",
                              "forbidden")) or re.search(r"\b(429|403)\b", msg):
        return "rate_limited"
    if any(t in msg for t in ("requested format is not available",
                              "no video formats found")):
        return "format"
    if any(t in msg for t in ("video unavailable", "has been removed", "removed",
                              "not found", "does not exist", "no longer available",
                              "deleted", "private video",
                              "not available in your country")) \
            or re.search(r"\b404\b", msg):
        return "unavailable"
    if any(t in msg for t in ("connection was reset", "connection reset",
                              "forcibly closed", "curl: (35)", "curl: (7)",
                              "connection refused", "failed to connect",
                              "connection aborted", "remote end closed")) \
            or re.search(r"\bssl|\b10054\b", msg):
        return "blocked"
    if any(t in msg for t in ("timed out", "timeout", "temporary failure",
                              "name or service not known", "getaddrinfo",
                              "network is unreachable", "incompleteread",
                              "connection broken", "bytes read",
                              "more expected")):
        return "network"
    return "other"


# Short reason shown on the per-video line while a run is in progress.
_SHORT_REASONS = {
    "login":        "login required",
    "blocked":      "blocked by your network",
    "network":      "network / timeout error",
    "rate_limited": "rate-limited by the site",
    "unavailable":  "removed, private, or region-locked",
    "unsupported":  "link not supported",
    "format":       "quality not available",
    "disk":         "disk or folder error",
    "other":        "download error",
}


# ─────────────────────────────────────────────────────────────────────
#  Adaptive retry-pass strategy
#
#  Pass 1: normal settings. Later passes get more patience, then a relaxed
#  quality fallback over IPv4, for whatever is STILL missing.
# ─────────────────────────────────────────────────────────────────────

_PASS_STRATEGIES = [
    # (label, relaxed_quality, retries, socket_timeout, force_ipv4)
    ("standard", False, 3, 20, False),
    ("patient",  False, 8, 45, False),
    ("relaxed",  True, 10, 60, True),
]


def _strategy_for_pass(pass_num: int) -> tuple:
    return _PASS_STRATEGIES[min(pass_num - 1, len(_PASS_STRATEGIES) - 1)]


def _format_selector(quality: str, relaxed: bool) -> str:
    if quality == "best":
        return "bv*+ba/b"
    strict = f"bv*[height<={quality}]+ba/b[height<={quality}]"
    return strict + "/bv*+ba/b" if relaxed else strict


# ─────────────────────────────────────────────────────────────────────
#  JSON ledger (playlists only: lets a re-run resume where it stopped)
# ─────────────────────────────────────────────────────────────────────

def _ledger_path(out_dir: str) -> str:
    return os.path.join(out_dir, ".linkcatty_state.json")


def _load_ledger(out_dir: str) -> dict:
    try:
        with open(_ledger_path(out_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_ledger(out_dir: str, ledger: dict) -> None:
    try:
        with open(_ledger_path(out_dir), "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print_warning(f"Could not write download ledger: {exc}")


def _init_ledger_entry(url: str, title) -> dict:
    return {
        "url": url,
        "title": title,
        "status": "pending",
        "attempts": 0,
        "error_type": None,
        "last_error": None,
        "hint": None,
        "reach_error": False,
        "final": False,
        "strategies_tried": [],
        "file": None,
        "first_seen": datetime.now().isoformat(timespec="seconds"),
        "last_attempt": None,
    }


def _safe_name(name) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name or "").strip(" .")
    return cleaned or "Playlist"


def _count_success(ledger: dict, keys: list) -> int:
    return sum(1 for k in keys if ledger[k]["status"] == "success")


def _needs_work(rec: dict) -> bool:
    return rec["status"] != "success" and not rec.get("final")


def _write_failed_report(out_dir: str, name, failed: list, expected: int,
                         downloaded: int, breakdown: dict) -> str:
    path = os.path.join(out_dir, "failed_downloads.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("LinkCatty - failed / missing videos report\n")
        f.write(f"Playlist          : {name or 'Unknown'}\n")
        f.write(f"Generated         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Expected videos   : {expected}\n")
        f.write(f"Downloaded videos : {downloaded}\n")
        f.write(f"Missing videos    : {len(failed)}\n")
        f.write("-" * 60 + "\n")
        if breakdown:
            f.write("Breakdown by cause:\n")
            for label, count in breakdown.items():
                f.write(f"  - {label}: {count}\n")
            f.write("-" * 60 + "\n")
        f.write("Per-video detail:\n\n")
        for rec in failed:
            cause = _ERROR_LABELS.get(rec.get("error_type"), "Other / unclassified error")
            f.write(f"{rec['url']}\n")
            f.write(f"    {rec.get('title') or 'Unknown title'}\n")
            f.write(f"    Cause      : {cause}\n")
            f.write(f"    Last error : {rec.get('last_error') or 'n/a'}\n")
            f.write(f"    Strategies tried : {', '.join(rec.get('strategies_tried') or []) or 'n/a'}\n")
            f.write(f"    Attempts   : {rec.get('attempts', 0)}\n\n")
        f.write("-" * 60 + "\n")
        f.write(
            "Tip: run the same playlist link again (even in a new session).\n"
            "LinkCatty keeps a ledger (.linkcatty_state.json) next to this\n"
            "report, so finished videos are skipped and only the videos listed\n"
            "above are retried.\n"
        )
        if _ERROR_LABELS["blocked"] in breakdown:
            f.write(
                "\nSome failures were your network cutting the connection. Turn on\n"
                "your VPN (or set a proxy in Settings > Network proxy) and run the\n"
                "link again.\n"
            )
    return path


# ─────────────────────────────────────────────────────────────────────
#  Session: proxy state, login cookies, yt-dlp options
# ─────────────────────────────────────────────────────────────────────

class _Session:
    def __init__(self, config: dict, handler):
        self.config = config
        self.handler = handler
        self.other = config.get("other") or {}
        self.extra_opts = {}
        self.proxy = None
        self.login_tried = False
        self._proxy_told = False
        self._notice_pending = False

    def ydl_options(self, proxy) -> dict:
        opts = {"quiet": True, "no_warnings": True, "noprogress": True,
                "logger": SilentLogger()}
        opts.update(self.extra_opts)
        ffmpeg = get_ffmpeg_path()
        if ffmpeg:
            opts["ffmpeg_location"] = ffmpeg
        if proxy:
            opts["proxy"] = proxy
        return opts

    def run(self, func, say=None):
        """Direct first, proxy only if blocked; remembers what worked."""
        result, used = run_with_proxy_fallback(func, self.config, self.proxy)
        if used and not self._proxy_told:
            self._proxy_told = True
            if say:
                say("ℹ️  Direct connection was blocked, using your proxy.")
            else:
                self._notice_pending = True
        self.proxy = used
        return result

    def flush_notice(self) -> None:
        if self._notice_pending:
            self._notice_pending = False
            print_info("Direct connection was blocked, using your proxy.")

    def fetch_info(self, url: str):
        def go(px):
            opts = self.ydl_options(px)
            opts["extract_flat"] = "in_playlist"
            with YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)
        return self.run(go)

    def can_login(self) -> bool:
        return hasattr(self.handler, "login_options") and not self.login_tried

    def login(self) -> bool:
        self.login_tried = True
        opts = self.handler.login_options(self.config, self.proxy)
        if opts:
            self.extra_opts.update(opts)
            return True
        return False


# ─────────────────────────────────────────────────────────────────────
#  Core download engine (ledger-driven, multi-pass, adaptive)
# ─────────────────────────────────────────────────────────────────────

def _final_path(info):
    if not isinstance(info, dict):
        return None
    for item in info.get("requested_downloads") or []:
        if item.get("filepath"):
            return item["filepath"]
    return info.get("filepath") or info.get("_filename")


def _download_one(url, out_dir, quality, strategy, session, progress):
    _label, relaxed, retries, timeout, ipv4 = strategy

    def go(px):
        opts = session.ydl_options(px)
        opts.update({
            "outtmpl": os.path.join(out_dir, "%(title).150s.%(ext)s"),
            "format": _format_selector(quality, relaxed),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "retries": retries,
            "fragment_retries": retries,
            "socket_timeout": timeout,
            "progress_hooks": [progress.hook],
            "postprocessor_hooks": [progress.pp_hook],
        })
        if ipv4:
            opts["source_address"] = "0.0.0.0"
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    return session.run(go, say=progress.say)


def _attempt_entry(key, out_dir, quality, strategy, session, progress,
                   ledger, persist, multi, index, count):
    rec = ledger[key]
    title = rec.get("title") or key
    rec["attempts"] += 1
    rec["last_attempt"] = datetime.now().isoformat(timespec="seconds")
    if strategy[0] not in rec["strategies_tried"]:
        rec["strategies_tried"].append(strategy[0])
    progress.item_reset()
    try:
        info = _download_one(key, out_dir, quality, strategy, session, progress)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        scrubbed = _scrub(exc)
        kind = _classify_error(scrubbed)
        message, hint = explain_error(exc, session.config)
        rec.update(status="failed", last_error=message, hint=hint,
                   error_type=kind, reach_error=is_block_error(scrubbed),
                   final=kind in _NON_RETRYABLE)
        progress.item_reset()
        if multi:
            progress.say(f"❌ [{index}/{count}] {title[:40]} — "
                         f"{_SHORT_REASONS.get(kind, _SHORT_REASONS['other'])}")
    else:
        path = _final_path(info)
        rec.update(status="success", last_error=None, hint=None,
                   error_type=None, reach_error=False, final=False, file=path)
        if isinstance(info, dict) and info.get("title") and not rec.get("title"):
            rec["title"] = info["title"]
        progress.item_done()
        if multi:
            size = ""
            if path and os.path.exists(path):
                size = f" ({format_bytes(os.path.getsize(path))})"
            progress.say(f"✅ [{index}/{count}] {title[:45]}{size}")
    if persist:
        _save_ledger(out_dir, ledger)


def _download_entries(entries, out_dir, quality, session, kind, name, persist):
    other = session.other
    auto_retry = bool(other.get("auto_retry", True))
    max_passes = max(1, int(other.get("max_retry_passes", 3))) if auto_retry else 1
    cooldown = max(0, int(other.get("retry_delay_seconds", 8)))
    rate_cooldown = max(cooldown, int(other.get("rate_limit_cooldown_seconds", 45)))
    os.makedirs(out_dir, exist_ok=True)

    ledger = _load_ledger(out_dir) if persist else {}
    keys = []
    for entry in entries:
        url = entry["url"]
        if url in keys:
            continue
        keys.append(url)
        rec = ledger.setdefault(url, _init_ledger_entry(url, entry.get("title")))
        if not rec.get("title"):
            rec["title"] = entry.get("title")
    for key in keys:
        rec = ledger[key]
        if rec["status"] == "success" and rec.get("file") \
                and not os.path.exists(rec["file"]):
            rec["status"] = "pending"
        if rec["status"] != "success":
            rec["status"] = "pending"
            rec["final"] = False
    total = len(keys)
    multi = total > 1
    if persist:
        _save_ledger(out_dir, ledger)

    print_info(f"Output folder : {out_dir}")
    print_info(f"Quality       : {_quality_label(quality)}")
    print_info(f"Retry passes  : up to {max_passes}")
    already = _count_success(ledger, keys)
    if already:
        print_info(f"Resuming      : {already}/{total} already downloaded, skipping them")

    started = time.time()

    def run_round():
        progress = DownloadProgress(f"⬇ Pass 1/{max_passes}", total)
        progress.done_items = _count_success(ledger, keys)
        progress.start()
        try:
            for pass_num in range(1, max_passes + 1):
                pending = [k for k in keys if _needs_work(ledger[k])]
                if not pending:
                    break
                strategy = _strategy_for_pass(pass_num)
                progress.set_label(
                    f"⬇ Pass {pass_num}/{max_passes} ({len(pending)} left)")
                start_success = _count_success(ledger, keys)
                for index, key in enumerate(pending, 1):
                    _attempt_entry(key, out_dir, quality, strategy, session,
                                   progress, ledger, persist, multi,
                                   index, len(pending))

                # member content: offer the browser-cookie login once
                login_failed = [k for k in keys
                                if ledger[k]["status"] != "success"
                                and ledger[k].get("error_type") == "login"]
                if login_failed and session.can_login():
                    with progress.paused():
                        print_warning("This content requires an account login.")
                        if confirm("Try with your browser cookies "
                                   "(you must be logged in)?"):
                            if session.login():
                                for k in login_failed:
                                    ledger[k].update(status="pending", final=False)
                            else:
                                print_error("No cookies available.",
                                            "Log in to the site in your browser first.")
                        else:
                            session.login_tried = True

                end_success = _count_success(ledger, keys)
                gained = end_success - start_success
                still_missing = total - end_success
                if still_missing <= 0:
                    break
                if not [k for k in keys if _needs_work(ledger[k])]:
                    break
                if pass_num < max_passes:
                    rate_limited = any(
                        ledger[k].get("error_type") == "rate_limited"
                        for k in keys if _needs_work(ledger[k]))
                    wait = rate_cooldown if rate_limited else cooldown
                    if rate_limited:
                        progress.say("⚠️  The site is rate-limiting this "
                                     "connection — waiting longer before retrying.")
                    progress.say(
                        f"⚠️  {still_missing} video(s) still missing after pass "
                        f"{pass_num} (+{gained} recovered). Cooling down "
                        f"{wait}s before the next pass…")
                    if wait:
                        time.sleep(random.uniform(wait, wait + 3))
        finally:
            progress.stop()

    while True:
        run_round()
        failed_keys = [k for k in keys if ledger[k]["status"] != "success"]
        reach = [k for k in failed_keys if ledger[k].get("reach_error")]
        if reach and ask_retry_vpn():
            for k in reach:
                ledger[k].update(status="pending", final=False)
            continue
        break

    downloaded = _count_success(ledger, keys)
    failed = [ledger[k] for k in keys if ledger[k]["status"] != "success"]
    breakdown = {}
    for rec in failed:
        label = _ERROR_LABELS.get(rec.get("error_type") or "other",
                                  _ERROR_LABELS["other"])
        breakdown[label] = breakdown.get(label, 0) + 1

    failed_report = None
    if failed and persist:
        failed_report = _write_failed_report(out_dir, name, failed, total,
                                             downloaded, breakdown)
    size = None
    first = ledger[keys[0]]
    if not multi and first["status"] == "success" and first.get("file"):
        try:
            size = os.path.getsize(first["file"])
        except OSError:
            pass

    return {
        "downloaded": downloaded,
        "expected": total,
        "failed_report": failed_report,
        "breakdown": breakdown,
        "elapsed": time.time() - started,
        "size": size,
        "first_failure": ((failed[0].get("last_error") or "Download failed",
                           failed[0].get("hint")) if failed else None),
    }


# ─────────────────────────────────────────────────────────────────────
#  Link workflow
# ─────────────────────────────────────────────────────────────────────

def _pick_handler(url: str):
    for site in _SITES:
        if site.matches(url):
            return site
    return None


def _available_heights(info: dict) -> list:
    heights = set()
    for fmt in info.get("formats") or []:
        height = fmt.get("height")
        if height and fmt.get("vcodec") not in (None, "none"):
            heights.add(int(height))
    return sorted((h for h in heights if h <= 2160), reverse=True)


def _pick_quality(heights: list):
    if heights:
        options = ["best"] + [str(h) for h in heights[:6]]
    else:
        options = ["best", "1080", "720", "480", "360"]
    print(f"\n{BOLD}📐 Select quality{RESET}")
    print("=" * 61)
    for number, quality in enumerate(options, 1):
        print(f"{CYAN}{BOLD}{number}.{RESET} {_quality_label(quality)}")
    back = len(options) + 1
    print(f"{CYAN}{BOLD}{back}.{RESET} Back")
    print("=" * 61)
    choice = menu_choice(f"Select (1-{back}): ",
                         "".join(str(n) for n in range(1, back + 1)))
    if choice in (None, str(back)):
        return None
    return options[int(choice) - 1]


def _entries_from(info: dict) -> list:
    entries = []
    for entry in info.get("entries") or []:
        if not entry:
            continue
        url = entry.get("webpage_url") or entry.get("url")
        if url and re.match(r"^https?://", str(url)):
            entries.append({"url": url, "title": entry.get("title")})
    return entries


def _fetch_with_recovery(url: str, session: _Session):
    """Fetch link info; handles member login and the VPN retry prompt."""
    while True:
        start_spinner("🎬 Fetching video info")
        try:
            info = session.fetch_info(url)
            stop_spinner()
            if not isinstance(info, dict):
                print_error("Could not read this link.", "Check the link and try again.")
                return None
            return info
        except KeyboardInterrupt:
            stop_spinner()
            raise
        except Exception as exc:
            stop_spinner()
            scrubbed = _scrub(exc)
            if _classify_error(scrubbed) == "login" and session.can_login():
                print_warning("This content requires an account login.")
                if confirm("Try with your browser cookies (you must be logged in)?"):
                    if session.login():
                        continue
                    print_error("No cookies available.",
                                "Log in to the site in your browser first.")
                    return None
                session.login_tried = True
            message, hint = explain_error(exc, session.config)
            print_error(f"Could not fetch video info: {message}", hint)
            if is_block_error(scrubbed) and ask_retry_vpn():
                continue
            return None


def _process_link(url: str, config: dict) -> None:
    handler = _pick_handler(url)
    session = _Session(config, handler)
    site_key = handler.KEY if handler else "Generic"

    info = _fetch_with_recovery(url, session)
    if info is None:
        return

    if info.get("entries") is not None or info.get("_type") == "playlist":
        entries = _entries_from(info)
        _show_session_header("📂 Other Downloader — Playlist")
        _display_playlist_info(info, len(entries))
        session.flush_notice()
        if not entries:
            print_error("This link has no downloadable videos.",
                        "Check the link and try again.")
            return
        if not confirm(f"Download all {len(entries)} videos?"):
            return
        quality = _pick_quality([])
        if quality is None:
            return
        name = info.get("title") or "Playlist"
        out_dir = os.path.join(config["download_dir"], _safe_name(name))
        result = _download_entries(entries, out_dir, quality, session,
                                   "playlist", name, persist=True)
        _display_result("playlist", name, out_dir, result)
        mode = "Playlist"
    else:
        heights = _available_heights(info)
        _show_session_header("📥 Other Downloader — Video")
        _display_video_info(info, heights)
        session.flush_notice()
        quality = _pick_quality(heights)
        if quality is None:
            return
        name = info.get("title")
        entries = [{"url": url, "title": name}]
        out_dir = config["download_dir"]
        result = _download_entries(entries, out_dir, quality, session,
                                   "video", name, persist=False)
        _display_result("video", name, out_dir, result)
        mode = "Single"

    if result["downloaded"] >= result["expected"]:
        status = "Success"
    else:
        status = "Partial" if result["downloaded"] else "Failed"
    error = ""
    if result.get("first_failure") and status != "Success":
        error = result["first_failure"][0]
    log_download(site_key, name or "Unknown", mode=mode, status=status, error=error)


def run_workflow(config: dict) -> None:
    _show_session_header(_SECTION)
    print_info("Paste a video or playlist link. The right downloader "
               "is picked automatically.")
    while True:
        url = input("\n🎯 Enter video URL (blank to go back): ").strip()
        if not url:
            return
        if not re.match(r"^https?://", url, re.IGNORECASE):
            print_error("Invalid URL", "Use a full link starting with http:// or https://.")
            continue
        try:
            _process_link(url, config)
        except KeyboardInterrupt:
            stop_spinner()
            print("\n⏹️  Cancelled. Partial downloads are kept and resume "
                  "next time you run the same link.")
        if not confirm("\nProcess another link?"):
            return


def run(config: dict) -> None:
    while True:
        try:
            run_workflow(config)
            return
        except EOFError:
            return
        except Exception as err:
            stop_spinner()
            print_error(f"Other downloader workflow error: {err}",
                        "You remain in the Other Downloader.")
            pause()
