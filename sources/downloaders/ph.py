#!/usr/bin/env python3
"""
PornHub downloader — uses yt-dlp.
Member/premium content requires browser cookies from a logged-in session.
"""
import re
import time
from pathlib import Path

from yt_dlp import YoutubeDL

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    BOLD, CYAN, GREEN, RESET, YELLOW,
    clear_screen, confirm, menu_choice, pause,
    print_banner, print_error, print_info,
    print_success, print_warning,
    start_spinner, stop_spinner,
)

_SECTION = "🔞 PornHub Downloader"

_QUALITY_MAP = {
    "1": "best",
    "2": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "3": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "4": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "5": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

_QUALITY_LABELS = {
    "1": "Best available",
    "2": "1080p",
    "3": "720p",
    "4": "480p",
    "5": "360p",
}


def is_ph_url(url: str) -> bool:
    return bool(re.search(r"pornhub\.com", url, re.IGNORECASE))


def _show_header() -> None:
    clear_screen()
    print_banner()
    print(f"{BOLD}                   {_SECTION}{RESET}")
    print("=" * 61)


def _build_options(output_dir: str, quality_key: str, cookie_opt=None) -> dict:
    options = {
        "outtmpl": str(Path(output_dir) / "%(title)s.%(ext)s"),
        "format": _QUALITY_MAP.get(quality_key, "best"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg
    if cookie_opt:
        options["cookiesfrombrowser"] = cookie_opt
    return options


def _try_browser_cookies():
    """Attempt to load cookies from an installed browser for member content."""
    print()
    print_info("Member/premium content needs your browser session cookies.")
    print_info("Close your browser completely before continuing.")
    try:
        input("Press Enter after closing your browser...")
    except (KeyboardInterrupt, EOFError):
        print()

    for browser in ("chrome", "firefox", "edge", "brave"):
        try:
            with YoutubeDL({"quiet": True, "cookiesfrombrowser": (browser,)}) as ydl:
                # Quick probe with a public URL to validate cookie extraction
                ydl.extract_info("https://www.pornhub.com", download=False)
            print_info(f"Loaded cookies from {browser}.")
            return (browser,)
        except Exception:
            continue

    print_warning("Could not extract cookies from any browser.")
    return None


def _fetch_info(url: str, cookie_opt=None):
    opts = {"quiet": True, "no_warnings": True}
    if cookie_opt:
        opts["cookiesfrombrowser"] = cookie_opt
    try:
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        return None, str(exc)


def _display_info(info: dict) -> None:
    title = info.get("title", "Unknown")
    duration = info.get("duration")
    uploader = info.get("uploader") or info.get("channel", "Unknown")
    views = info.get("view_count")

    print(f"\n  {CYAN}{BOLD}Title   :{RESET} {title}")
    print(f"  {CYAN}{BOLD}Channel :{RESET} {uploader}")
    if duration:
        m, s = divmod(int(duration), 60)
        h, m = divmod(m, 60)
        dur_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        print(f"  {CYAN}{BOLD}Duration:{RESET} {dur_str}")
    if views:
        v = views
        label = f"{v/1_000_000:.1f}M" if v >= 1_000_000 else (f"{v/1_000:.1f}K" if v >= 1_000 else str(v))
        print(f"  {CYAN}{BOLD}Views   :{RESET} {label}")
    print()


def _pick_quality() -> str | None:
    print(f"{BOLD}📐 Select Quality{RESET}")
    print("=" * 61)
    for k, label in _QUALITY_LABELS.items():
        print(f"{CYAN}{BOLD}{k}.{RESET} {label}")
    print(f"{CYAN}{BOLD}6.{RESET} Back")
    print("=" * 61)
    choice = menu_choice("Select (1-6): ", "123456")
    if choice in (None, "6"):
        return None
    return choice


def download_video(url: str, config: dict, cookie_opt=None) -> None:
    start_spinner("Fetching video information")
    try:
        opts_probe = {"quiet": True, "no_warnings": True}
        if cookie_opt:
            opts_probe["cookiesfrombrowser"] = cookie_opt
        with YoutubeDL(opts_probe) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        stop_spinner()
        err_msg = str(exc)
        # Premium/member content check
        if "premium" in err_msg.lower() or "members" in err_msg.lower() or "login" in err_msg.lower():
            print_warning("This content appears to require a PornHub account.")
            if confirm("Try with your browser cookies (you must be logged in)?"):
                cookie_opt = _try_browser_cookies()
                if cookie_opt:
                    download_video(url, config, cookie_opt)
                else:
                    print_error("No cookies available.", "Log in to PornHub in your browser first.")
            return
        print_error(f"Could not fetch video info: {err_msg}",
                    "Check the URL and your internet connection.")
        return
    finally:
        stop_spinner()

    _show_header()
    _display_info(info)

    quality_key = _pick_quality()
    if quality_key is None:
        return

    label = _QUALITY_LABELS[quality_key]
    if not confirm(f"\n🚀 Download at {label}?"):
        print_info("Download cancelled.")
        return

    options = _build_options(config["download_dir"], quality_key, cookie_opt)
    start_time = time.time()
    print()
    try:
        start_spinner("Downloading")
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        stop_spinner()
        elapsed = time.time() - start_time
        m, s = divmod(int(elapsed), 60)
        elapsed_str = f"{m}m {s:02d}s" if m else f"{s}s"
        print_success(f"Downloaded in {elapsed_str}!")
        log_download("PornHub", info.get("title", url), mode=label, status="Success")
    except Exception as exc:
        stop_spinner()
        print_error(f"Download failed: {exc}", "Check the URL and network connection.")
        log_download("PornHub", info.get("title", url), mode=label,
                     status="Failed", error=str(exc))


def run(config: dict, url: str | None = None) -> None:
    cookie_opt = None
    while True:
        _show_header()
        if url is None:
            print()
            raw = input("🎯 PornHub URL (blank to go back): ").strip()
            if not raw:
                return
            if not is_ph_url(raw):
                print_error("Not a PornHub URL.",
                             "URL must contain pornhub.com")
                pause()
                continue
            current_url = raw
        else:
            current_url = url
            url = None  # only use caller-supplied URL once

        download_video(current_url, config, cookie_opt)

        if not confirm("\nDownload another PornHub video?"):
            return
