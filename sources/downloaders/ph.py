#!/usr/bin/env python3
"""
ph — video downloader via yt-dlp.
Member content requires browser cookies from a logged-in session.
"""
import re
import time
from pathlib import Path

from yt_dlp import YoutubeDL

from utils.config import get_proxy, run_with_proxy_fallback
from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    BOLD, CYAN, GREEN, RESET, YELLOW,
    clear_screen, confirm, menu_choice, pause,
    print_banner, print_error, print_info,
    print_success, print_warning,
    start_spinner, stop_spinner,
    SilentLogger, explain_error,
)

_SECTION = "📥 Video Downloader"

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

_PH_DOMAIN = re.compile(r"pornhub\.com", re.IGNORECASE)


def is_ph_url(url: str) -> bool:
    return bool(_PH_DOMAIN.search(url))


def _show_header() -> None:
    clear_screen()
    print_banner()
    print(f"{BOLD}                   {_SECTION}{RESET}")
    print("=" * 61)


def _build_options(output_dir: str, quality_key: str, cookie_opt=None, proxy=None) -> dict:
    options = {
        "outtmpl": str(Path(output_dir) / "%(title)s.%(ext)s"),
        "format": _QUALITY_MAP.get(quality_key, "best"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "logger": SilentLogger(),
    }
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg
    if cookie_opt:
        options["cookiesfrombrowser"] = cookie_opt
    if proxy:
        options["proxy"] = proxy
    return options


def _try_browser_cookies(proxy=None):
    """Attempt to load cookies from an installed browser for member content."""
    print()
    print_info("Member content needs your browser session cookies.")
    print_info("Close your browser completely before continuing.")
    try:
        input("Press Enter after closing your browser...")
    except (KeyboardInterrupt, EOFError):
        print()

    for browser in ("chrome", "firefox", "edge", "brave"):
        try:
            probe = {"quiet": True, "logger": SilentLogger(), "cookiesfrombrowser": (browser,)}
            if proxy:
                probe["proxy"] = proxy
            with YoutubeDL(probe) as ydl:
                ydl.extract_info("https://www.pornhub.com", download=False)
            print_info(f"Loaded cookies from {browser}.")
            return (browser,)
        except Exception:
            continue

    print_warning("Could not extract cookies from any browser.")
    return None


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
        def _fetch(px):
            opts_probe = {"quiet": True, "no_warnings": True, "logger": SilentLogger()}
            if cookie_opt:
                opts_probe["cookiesfrombrowser"] = cookie_opt
            if px:
                opts_probe["proxy"] = px
            with YoutubeDL(opts_probe) as ydl:
                return ydl.extract_info(url, download=False)

        info, proxy = run_with_proxy_fallback(_fetch, config)
    except Exception as exc:
        stop_spinner()
        err_msg = str(exc)
        if "premium" in err_msg.lower() or "members" in err_msg.lower() or "login" in err_msg.lower():
            print_warning("This content requires an account login.")
            if confirm("Try with your browser cookies (you must be logged in)?"):
                cookie_opt = _try_browser_cookies(get_proxy(config) or None)
                if cookie_opt:
                    download_video(url, config, cookie_opt)
                else:
                    print_error("No cookies available.", "Log in to the site in your browser first.")
            return
        msg, hint = explain_error(exc, config)
        print_error(f"Could not fetch video info: {msg}", hint)
        return
    finally:
        stop_spinner()

    _show_header()
    _display_info(info)
    if proxy:
        print_info("Direct connection was blocked, using your proxy.")

    quality_key = _pick_quality()
    if quality_key is None:
        return

    label = _QUALITY_LABELS[quality_key]
    if not confirm(f"\n🚀 Download at {label}?"):
        print_info("Download cancelled.")
        return

    def _download(px):
        options = _build_options(config["download_dir"], quality_key, cookie_opt, px)
        with YoutubeDL(options) as ydl:
            ydl.download([url])

    start_time = time.time()
    print()
    try:
        start_spinner("Downloading")
        run_with_proxy_fallback(_download, config, proxy)
        stop_spinner()
        elapsed = time.time() - start_time
        m, s = divmod(int(elapsed), 60)
        elapsed_str = f"{m}m {s:02d}s" if m else f"{s}s"
        print_success(f"Downloaded in {elapsed_str}!")
        log_download("ph", info.get("title", url), mode=label, status="Success")
    except Exception as exc:
        stop_spinner()
        msg, hint = explain_error(exc, config)
        print_error(f"Download failed: {msg}", hint)
        log_download("ph", info.get("title", url), mode=label,
                     status="Failed", error=msg)


def run(config: dict, url: str | None = None) -> None:
    cookie_opt = None
    while True:
        _show_header()
        if url is None:
            print()
            raw = input("🎯 URL (blank to go back): ").strip()
            if not raw:
                return
            if not is_ph_url(raw):
                print_error("Unsupported URL for this downloader.",
                             "Check the link and try again.")
                pause()
                continue
            current_url = raw
        else:
            current_url = url
            url = None

        download_video(current_url, config, cookie_opt)

        if not confirm("\nDownload another video?"):
            return
