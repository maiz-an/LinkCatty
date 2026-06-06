import os
import shutil
import subprocess
import re
from pathlib import Path

from utils.ffmpeg import get_ffmpeg_path          # kept for yt-dlp fallback (now unused, but import stays)
from utils.logger import log_download
from utils.ui import (
    print_warning,
    BOLD,
    CYAN,
    RESET,
    clear_screen,
    confirm,
    menu_choice,
    pause,
    print_banner,
    print_error,
    print_info,
    print_success,
    start_spinner,
    stop_spinner,
)


# ----------------------------------------------------------------------
# Spotify Downloader – purely spotdl‑based
# ----------------------------------------------------------------------
class SpotifyDownloader:
    def __init__(self, config):
        self.config = config
        self.spotify_config = config["spotify"]
        self.download_dir = Path(config["download_dir"])
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Only requirement: spotdl must be installed
        self.spotdl_path = shutil.which("spotdl")
        if not self.spotdl_path:
            raise RuntimeError(
                "spotdl is not installed or not in PATH. "
                "Please run: pip install spotdl"
            )

    # ------------------------------------------------------------------
    def _spotdl_download(self, url, item_type):
        """
        Launch spotdl with the appropriate output template.
        item_type: 'track', 'playlist', 'album'
        """
        quality = self.spotify_config.get("audio_quality", "320k").replace("k", "")
        output_dir = str(self.download_dir)

        # Build template – spotdl will create folders for playlists/albums
        if item_type == "album":
            template = os.path.join(output_dir, "{album}", "{title} - {artists}.{ext}")
        elif item_type == "playlist":
            template = os.path.join(output_dir, "{playlist}", "{title} - {artists}.{ext}")
        else:  # single track
            template = os.path.join(output_dir, "{title} - {artists}.{ext}")

        cmd = [
            "spotdl",
            url,
            "--output", template,
            "--bitrate", f"{quality}k",
        ]

        print_info("Launching spotdl...")
        print_info(f"Output folder: {output_dir}")
        # Let spotdl show its own progress – we do NOT capture stdout
        result = subprocess.run(cmd)
        return result.returncode == 0

    # ------------------------------------------------------------------
    def download_single_track(self, url):
        # Validate URL format
        if "/track/" not in url:
            print_error("Invalid Spotify track URL")
            return

        print_info("Starting single track download via spotdl...")
        if not confirm("Proceed?"):
            return

        success = self._spotdl_download(url, "track")
        if success:
            print_success("Track downloaded successfully")
            log_download("Spotify", url, artist="spotdl", mode="Single", status="Success")
        else:
            print_error("Download failed")
            log_download("Spotify", url, artist="spotdl", mode="Single", status="Failed")

    # ------------------------------------------------------------------
    def download_playlist(self, url):
        if "/playlist/" not in url:
            print_error("Invalid Spotify playlist URL")
            return

        print_info("Starting playlist download via spotdl...")
        print_info("A subfolder will be created with the playlist name.")
        if not confirm("Download all tracks?"):
            return

        success = self._spotdl_download(url, "playlist")
        if success:
            print_success("Playlist downloaded successfully")
            log_download("Spotify", url, artist="spotdl", mode="Playlist", status="Success")
        else:
            print_error("Playlist download failed")
            log_download("Spotify", url, artist="spotdl", mode="Playlist", status="Failed")

    # ------------------------------------------------------------------
    def download_album(self, url):
        if "/album/" not in url:
            print_error("Invalid Spotify album URL")
            return

        print_info("Starting album download via spotdl...")
        print_info("A subfolder will be created with the album name.")
        if not confirm("Download all tracks?"):
            return

        success = self._spotdl_download(url, "album")
        if success:
            print_success("Album downloaded successfully")
            log_download("Spotify", url, artist="spotdl", mode="Album", status="Success")
        else:
            print_error("Album download failed")
            log_download("Spotify", url, artist="spotdl", mode="Album", status="Failed")


# ----------------------------------------------------------------------
# Helpers unchanged – kept for compatibility with other modules
# ----------------------------------------------------------------------
def extract_spotify_id(url, item_type):
    match = re.search(rf"{item_type}/([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None


def is_spotify_url(url, item_type):
    return bool(re.match(r"^https?://", url)) and f"spotify.com/{item_type}/" in url


# ----------------------------------------------------------------------
# Workflow runners (unchanged)
# ----------------------------------------------------------------------
def create_downloader(config):
    try:
        return SpotifyDownloader(config)
    except Exception as error:
        print_error(str(error))
        return None


def run_spotify_workflow(config, choice):
    downloader = create_downloader(config)
    if downloader is None:
        pause()
        return

    item_type = {"1": "playlist", "2": "track", "3": "album"}[choice]
    while True:
        url = input(f"\n🎯 Enter Spotify {item_type} URL (blank to go back): ").strip()
        if not url:
            return
        if not is_spotify_url(url, item_type):
            print_error(f"Invalid Spotify {item_type} URL", f"Use a link containing spotify.com/{item_type}/.")
            continue

        if choice == "1":
            downloader.download_playlist(url)
        elif choice == "2":
            downloader.download_single_track(url)
        elif choice == "3":
            downloader.download_album(url)

        if not confirm(f"\nProcess another Spotify {item_type}?"):
            return


def run(config):
    while True:
        clear_screen()
        print_banner()
        print("                🎵 Spotify Downloader")
        print("=" * 61)
        print()
        print(f"{CYAN}{BOLD}1.{RESET} Download playlist")
        print(f"{CYAN}{BOLD}2.{RESET} Download single track")
        print(f"{CYAN}{BOLD}3.{RESET} Download album")
        print(f"{CYAN}{BOLD}4.{RESET} Back to main menu")
        print()
        print("=" * 61)
        choice = menu_choice("Select (1-4): ", "1234")
        if choice in (None, "4"):
            return
        try:
            run_spotify_workflow(config, choice)
        except Exception as error:
            stop_spinner()
            print_error(f"Spotify workflow error: {error}", "You remain in the Spotify Downloader.")
            pause()