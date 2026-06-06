import os
import shutil
import subprocess
import re
import json
import urllib.request
import urllib.parse
from pathlib import Path

from utils.ffmpeg import get_ffmpeg_path
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

# spotdl library – only used for metadata (optional)
try:
    from spotdl.utils.spotify import SpotifyClient
except ImportError:
    SpotifyClient = None


# ----------------------------------------------------------------------
# Spotify Downloader – purely spotdl‑based
# ----------------------------------------------------------------------
class SpotifyDownloader:
    def __init__(self, config):
        self.config = config
        self.spotify_config = config["spotify"]
        self.download_dir = Path(config["download_dir"])
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # spotdl CLI must be installed
        self.spotdl_path = shutil.which("spotdl")
        if not self.spotdl_path:
            raise RuntimeError(
                "spotdl is not installed or not in PATH. "
                "Please run: pip install spotdl"
            )

        # Credentials (needed by spotdl CLI to resolve {playlist}/{album})
        self.client_id = self.spotify_config.get("client_id", "").strip()
        self.client_secret = self.spotify_config.get("client_secret", "").strip()

        # Initialise spotdl's Spotify client for metadata (if credentials exist)
        self.spotdl_client_available = False
        if SpotifyClient is not None and self.client_id and self.client_secret:
            try:
                SpotifyClient.init(self.client_id, self.client_secret)
                self.spotdl_client_available = True
            except Exception:
                pass

        # Ensure Deno is installed (spotdl needs it for some YouTube tracks)
        self._ensure_deno()

    # ------------------------------------------------------------------
    def _ensure_deno(self):
        """Install Deno silently if it's not already present."""
        if shutil.which("deno"):
            return
        print_info("Deno not found – installing automatically (required for Spotify downloads).")
        try:
            # Run spotdl's own Deno installer, answer 'y' automatically
            proc = subprocess.Popen(
                [self.spotdl_path, "--download-deno"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            proc.communicate(input="y\n", timeout=60)
        except Exception:
            print_warning("Could not install Deno automatically. Some downloads may fail.")

    # ------------------------------------------------------------------
    def _get_playlist_meta(self, url):
        """Return (name, track_count). track_count is None if unknown."""
        if self.spotdl_client_available:
            try:
                playlist = SpotifyClient.get_playlist(url)
                return playlist.name, playlist.total
            except Exception:
                pass

        name = self._get_oembed_title(url)
        if name:
            return name, None
        return None, None

    def _get_album_meta(self, url):
        """Return (name, track_count) for albums."""
        if self.spotdl_client_available:
            try:
                album = SpotifyClient.get_album(url)
                return album.name, album.total_tracks
            except Exception:
                pass

        name = self._get_oembed_title(url)
        if name:
            name = re.sub(r"\s*[-–|].*$", "", name).strip()
        if name:
            return name, None
        return None, None

    @staticmethod
    def _get_oembed_title(url):
        """Fetch title from Spotify oEmbed (no auth needed)."""
        try:
            embed_url = "https://open.spotify.com/oembed?url=" + urllib.parse.quote(url, safe="")
            req = urllib.request.Request(
                embed_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("title", "").strip()
        except Exception:
            return None

    # ------------------------------------------------------------------
    def _clean_name(self, name):
        """Remove characters invalid in folder names."""
        return re.sub(r'[\\/*?:"<>|]', "", name) if name else None

    def _find_output_folder(self, item_type, expected_name):
        """
        After download, find the folder spotdl actually created.
        Uses the expected name (from metadata) if it exists, otherwise falls back to
        the most recently modified subdirectory in download_dir.
        """
        base = str(self.download_dir)
        if not expected_name:
            return base

        safe_name = self._clean_name(expected_name)
        if not safe_name:
            return base

        candidate = os.path.join(base, safe_name)
        if os.path.isdir(candidate):
            return candidate

        # Fallback: find newest subdirectory (spotdl might have cleaned the name differently)
        try:
            subdirs = [os.path.join(base, d) for d in os.listdir(base)
                       if os.path.isdir(os.path.join(base, d))]
            if subdirs:
                return max(subdirs, key=lambda d: os.path.getmtime(d))
        except Exception:
            pass

        return base

    def _count_audio_files(self, folder):
        """Recursively count audio files in folder."""
        count = 0
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(('.mp3', '.m4a', '.opus', '.ogg', '.flac', '.wav')):
                    count += 1
        return count

    # ------------------------------------------------------------------
    def _spotdl_download(self, url, item_type, metadata_name=None):
        """
        Run spotdl with credentials, clean output (no Deno prompt).
        Returns (success_bool, output_folder_path).
        """
        quality = self.spotify_config.get("audio_quality", "320k").replace("k", "")
        output_dir = str(self.download_dir)

        # Output template
        if item_type == "album":
            template = os.path.join(output_dir, "{album}", "{title} - {artists}.{ext}")
        elif item_type == "playlist":
            template = os.path.join(output_dir, "{playlist}", "{title} - {artists}.{ext}")
        else:
            template = os.path.join(output_dir, "{title} - {artists}.{ext}")

        cmd = [
            "spotdl",
            url,
            "--output", template,
            "--bitrate", f"{quality}k",
            "--no-progress",
            # "--download-deno"  ← removed – Deno already installed by _ensure_deno()
        ]

        # Pass credentials so spotdl can resolve {playlist}/{album}
        if self.client_id and self.client_secret:
            cmd += ["--client-id", self.client_id, "--client-secret", self.client_secret]

        print_info(f"Output folder: {output_dir}")
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True, bufsize=1) as proc:
            for line in proc.stdout:
                print(line, end="")
            proc.wait()

        # Find where spotdl actually saved the files
        out_folder = self._find_output_folder(item_type, metadata_name)

        # Success = at least one audio file created (recursively)
        file_count = self._count_audio_files(out_folder)
        return file_count > 0, out_folder

    # ------------------------------------------------------------------
    def download_single_track(self, url):
        if "/track/" not in url:
            print_error("Invalid Spotify track URL")
            return

        if not confirm("Proceed with download?"):
            return

        success, out_folder = self._spotdl_download(url, "track")
        if success:
            print_success("Track downloaded successfully")
            log_download("Spotify", url, artist="spotdl", mode="Single", status="Success")
        else:
            print_error("Download failed – no audio file was created")
            log_download("Spotify", url, artist="spotdl", mode="Single", status="Failed")

    # ------------------------------------------------------------------
    def download_album(self, url):
        if "/album/" not in url:
            print_error("Invalid Spotify album URL")
            return

        name, track_count = self._get_album_meta(url)
        if name:
            track_str = f"{track_count} track(s)" if track_count is not None else "unknown tracks"
            print_info(f"Album: {name} – {track_str}")
        else:
            print_info("Album metadata unavailable")

        if not confirm("Download all tracks?"):
            return

        success, out_folder = self._spotdl_download(url, "album", metadata_name=name)
        if success:
            print_success(f"Album downloaded successfully → {out_folder}")
            log_download("Spotify", url, artist="spotdl", mode="Album", status="Success")
        else:
            print_error("Album download failed – no tracks were saved")
            log_download("Spotify", url, artist="spotdl", mode="Album", status="Failed")

    # ------------------------------------------------------------------
    def download_playlist(self, url):
        if "/playlist/" not in url:
            print_error("Invalid Spotify playlist URL")
            return

        name, track_count = self._get_playlist_meta(url)
        if name:
            track_str = f"{track_count} track(s)" if track_count is not None else "unknown tracks"
            print_info(f"Playlist: {name} – {track_str}")
        else:
            print_info("Playlist metadata unavailable")

        if not confirm("Download all tracks?"):
            return

        success, out_folder = self._spotdl_download(url, "playlist", metadata_name=name)
        if success:
            print_success(f"Playlist downloaded successfully → {out_folder}")
            log_download("Spotify", url, artist="spotdl", mode="Playlist", status="Success")
        else:
            print_error("Playlist download failed – no tracks were saved")
            log_download("Spotify", url, artist="spotdl", mode="Playlist", status="Failed")


# ----------------------------------------------------------------------
# Helpers (unchanged)
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

    item_type = {"1": "track", "2": "album", "3": "playlist"}[choice]
    while True:
        url = input(f"\n🎯 Enter Spotify {item_type} URL (blank to go back): ").strip()
        if not url:
            return
        if not is_spotify_url(url, item_type):
            print_error(f"Invalid Spotify {item_type} URL", f"Use a link containing spotify.com/{item_type}/.")
            continue

        if choice == "1":
            downloader.download_single_track(url)
        elif choice == "2":
            downloader.download_album(url)
        elif choice == "3":
            downloader.download_playlist(url)

        if not confirm(f"\nProcess another Spotify {item_type}?"):
            return


def run(config):
    while True:
        clear_screen()
        print_banner()
        print("                🎵 Spotify Downloader")
        print("=" * 61)
        print()
        print(f"{CYAN}{BOLD}1.{RESET} Download single track")
        print(f"{CYAN}{BOLD}2.{RESET} Download album")
        print(f"{CYAN}{BOLD}3.{RESET} Download playlist")
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