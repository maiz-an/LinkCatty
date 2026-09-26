#!/usr/bin/env python3
"""
universal - the profile for every link that is not YouTube or Spotify.

  dedicated(url)   -> (name, menu number) when the link belongs to a downloader
                      that has its own menu entry, so the user can be pointed there
  login_options()  -> browser-cookie login for sites that need an account
"""
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL

from utils.ui import SilentLogger, print_info, print_warning

KEY = "Other"

_DEDICATED = (
    (("youtube.com", "youtu.be", "youtube-nocookie.com"), "YouTube Downloader", 1),
    (("spotify.com", "spotify.link"), "Spotify Downloader", 2),
)


def dedicated(url: str):
    host = (urlsplit(url).hostname or "").lower()
    for domains, name, number in _DEDICATED:
        if any(host == d or host.endswith("." + d) for d in domains):
            return name, number
    return None


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
                ydl.cookiejar  # loading the cookie jar is what can fail
            print_info(f"Loaded cookies from {browser}.")
            return {"cookiesfrombrowser": (browser,)}
        except Exception:
            continue

    print_warning("Could not read cookies from any browser.")
    return None
