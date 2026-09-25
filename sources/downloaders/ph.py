#!/usr/bin/env python3
"""
ph - site profile for the Other Downloader.

Provides URL matching plus an optional member login that reuses the
browser's own logged-in session cookies.
"""
import re

from yt_dlp import YoutubeDL

from utils.ui import SilentLogger, print_info, print_warning

KEY = "ph"

_DOMAIN = re.compile(r"pornhub\.com", re.IGNORECASE)


def matches(url: str) -> bool:
    return bool(_DOMAIN.search(url))


def login_options(config: dict, proxy=None):
    """Return yt-dlp options carrying browser cookies, or None if unavailable."""
    print()
    print_info("Member content needs your browser session cookies.")
    print_info("Close your browser completely before continuing.")
    try:
        input("Press Enter after closing your browser...")
    except (KeyboardInterrupt, EOFError):
        print()

    for browser in ("chrome", "firefox", "edge", "brave"):
        try:
            probe = {"quiet": True, "logger": SilentLogger(),
                     "cookiesfrombrowser": (browser,)}
            if proxy:
                probe["proxy"] = proxy
            with YoutubeDL(probe) as ydl:
                ydl.extract_info("https://www.pornhub.com", download=False)
            print_info(f"Loaded cookies from {browser}.")
            return {"cookiesfrombrowser": (browser,)}
        except Exception:
            continue

    print_warning("Could not extract cookies from any browser.")
    return None
