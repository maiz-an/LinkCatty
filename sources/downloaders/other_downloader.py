#!/usr/bin/env python3
"""
Other Downloaders — URL router for sites beyond YouTube and Spotify.
Detects the site from a pasted URL and dispatches to the right handler.
Unknown sites fall back to a generic yt-dlp download.
"""
import re
import time
from pathlib import Path

from yt_dlp import YoutubeDL

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    BOLD, CYAN, RESET,
    clear_screen, confirm, menu_choice, pause,
    print_banner, print_error, print_info,
    print_success, print_warning,
    start_spinner, stop_spinner,
)

from downloaders.ph import is_ph_url, run as ph_run
from downloaders.xm import is_xm_url, run as xm_run

_SECTION = "🌐 Other Downloaders"


def _show_header() -> None:
    clear_screen()
    print_banner()
    print(f"{BOLD}                   {_SECTION}{RESET}")
    print("=" * 61)


def _detect_site(url: str) -> str:
    """Return a short site identifier from a URL."""
    if is_ph_url(url):
        return "ph"
    if is_xm_url(url):
        return "xm"
    return "generic"


def _generic_download(url: str, config: dict) -> None:
    """Generic yt-dlp fallback for any yt-dlp-supported site."""
    start_spinner("Fetching information")
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        stop_spinner()
        print_error(f"Cannot retrieve info: {exc}",
                    "This URL may not be supported by the downloader.")
        return
    finally:
        stop_spinner()

    title = info.get("title") or url
    print(f"\n  {CYAN}{BOLD}Title :{RESET} {title}")
    print(f"  {CYAN}{BOLD}Site  :{RESET} {info.get('extractor_key', 'Unknown')}")
    print()

    if not confirm("🚀 Download this (best quality)?"):
        print_info("Download cancelled.")
        return

    ffmpeg = get_ffmpeg_path()
    options = {
        "outtmpl": str(Path(config["download_dir"]) / "%(title)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg

    start_time = time.time()
    try:
        start_spinner("Downloading")
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        stop_spinner()
        elapsed = time.time() - start_time
        m, s = divmod(int(elapsed), 60)
        print_success(f"Downloaded in {m}m {s:02d}s!" if m else f"Downloaded in {s}s!")
        log_download("Generic", title, mode="best", status="Success")
    except Exception as exc:
        stop_spinner()
        print_error(f"Download failed: {exc}")
        log_download("Generic", title, mode="best", status="Failed", error=str(exc))


def run(config: dict) -> None:
    while True:
        _show_header()
        print()
        print_info("Paste any video link — the right downloader is used automatically.")
        print_info("Supports 1000+ sites via yt-dlp.")
        print()
        raw = input("🔗 Enter URL (blank to go back): ").strip()
        if not raw:
            return

        if not re.match(r"^https?://", raw, re.IGNORECASE):
            print_error("Invalid URL.", "URL must start with http:// or https://")
            pause()
            continue

        site = _detect_site(raw)

        if site == "ph":
            print_info("Supported link detected.")
            ph_run(config, url=raw)
        elif site == "xm":
            print_info("Supported link detected.")
            xm_run(config, url=raw)
        else:
            print_info(f"Attempting generic yt-dlp download...")
            _show_header()
            _generic_download(raw, config)

        if not confirm("\nDownload another?"):
            return
