import re
import time
from pathlib import Path
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from utils.ui import (
    RESET, CYAN, BOLD,
    clear_screen, print_banner, print_error, print_success, print_info, print_warning,
    start_spinner, stop_spinner
)
from utils.logger import log_download
from utils.ffmpeg import get_ffmpeg_path

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def extract_playlist_id(url):
    m = re.search(r'playlist/([a-zA-Z0-9]+)', url)
    return m.group(1) if m else None

def extract_track_id(url):
    m = re.search(r'track/([a-zA-Z0-9]+)', url)
    return m.group(1) if m else None

def extract_album_id(url):
    m = re.search(r'album/([a-zA-Z0-9]+)', url)
    return m.group(1) if m else None

# ----------------------------------------------------------------------
# Main Spotify Downloader Class
# ----------------------------------------------------------------------
class SpotifyDownloader:
    def __init__(self, config):
        self.config = config
        self.spotify_config = config['spotify']
        self.download_dir = Path(config['download_dir'])
        self.download_dir.mkdir(parents=True, exist_ok=True)

        client_id = self.spotify_config.get('client_id', '')
        client_secret = self.spotify_config.get('client_secret', '')
        if not client_id or not client_secret:
            raise ValueError("Spotify API credentials missing")
        try:
            self.spotify = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret
                )
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Spotify API: {e}")

    def get_ydl_opts(self):
        quality = self.spotify_config.get('audio_quality', '320k').replace('k', '')
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.download_dir / '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
            'quiet': self.spotify_config.get('quiet_mode', True),
            'no_warnings': True,
            'ignoreerrors': True,
        }
        ffmpeg = get_ffmpeg_path()
        if ffmpeg:
            opts['ffmpeg_location'] = ffmpeg
        return opts

    def search_youtube(self, track, retry=0):
        artists = " & ".join(track['artists'])
        query = f"{artists} - {track['name']} official audio"
        query = re.sub(r'[^\w\s-]', '', query)
        ydl_opts = {'quiet': True, 'extract_flat': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
                if results and 'entries' in results and results['entries']:
                    return results['entries'][0]['url']
        except Exception:
            if retry < 2:
                time.sleep(1)
                return self.search_youtube(track, retry+1)
        return None

    def download_track(self, youtube_url, track_info, index=None, total=None):
        artists = " & ".join(track_info['artists'])
        title = f"{track_info['name']} - {artists}"
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        opts = self.get_ydl_opts()
        opts['outtmpl'] = str(self.download_dir / f"{safe_title}.%(ext)s")
        if index and total:
            print(f"[{index}/{total}] ", end="")
        print_info(f"Downloading: {artists} - {track_info['name']}")
        try:
            start_spinner("Downloading from YouTube")
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([youtube_url])
            stop_spinner()
            return True
        except Exception as e:
            stop_spinner()
            print_error(f"Download error: {e}")
            return False

    def download_playlist(self, url):
        playlist_id = extract_playlist_id(url)
        if not playlist_id:
            print_error("Invalid Spotify playlist URL", "URL should contain /playlist/")
            return
        try:
            playlist = self.spotify.playlist(playlist_id)
            print_info(f"Playlist: {playlist['name']} by {playlist['owner']['display_name']}")
            print_info(f"Total tracks: {playlist['tracks']['total']}")
            confirm = input("Download all? (y/n): ").lower()
            if confirm != 'y':
                return

            # Fetch all tracks
            print_info("Fetching playlist tracks...")
            tracks = []
            results = self.spotify.playlist_tracks(playlist_id)
            while results:
                for item in results['items']:
                    if item['track']:
                        t = item['track']
                        tracks.append({
                            'name': t['name'],
                            'artists': [a['name'] for a in t['artists']]
                        })
                results = self.spotify.next(results) if results['next'] else None

            total = len(tracks)
            print_success(f"Found {total} tracks")

            success, fail = 0, 0
            for i, track in enumerate(tracks, 1):
                print(f"\n{'─' * 61}")
                print_info(f"[{i}/{total}] Searching: {track['name']}")
                yt_url = self.search_youtube(track)
                if not yt_url:
                    print_error(f"[{i}/{total}] Not found on YouTube: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Playlist", status="Failed")
                    fail += 1
                    continue
                if self.download_track(yt_url, track, i, total):
                    success += 1
                    print_success(f"[{i}/{total}] Downloaded: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Playlist", status="Success")
                else:
                    fail += 1
                    print_error(f"[{i}/{total}] Failed: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Playlist", status="Failed")
                time.sleep(1)

            print("\n" + "═" * 61)
            print_success(f"Playlist download finished: {success} successful, {fail} failed")
            print("═" * 61)
        except Exception as e:
            print_error(f"Error fetching playlist: {e}")

    def download_single_track(self, url):
        track_id = extract_track_id(url)
        if not track_id:
            print_error("Invalid Spotify track URL", "URL should contain /track/")
            return
        try:
            track = self.spotify.track(track_id)
            track_info = {
                'name': track['name'],
                'artists': [a['name'] for a in track['artists']],
                'album': track['album']['name']
            }
            print_info(f"Track: {track_info['name']} by {', '.join(track_info['artists'])}")
            confirm = input("Download? (y/n): ").lower()
            if confirm != 'y':
                return

            print_info("Searching on YouTube...")
            yt_url = self.search_youtube(track_info)
            if not yt_url:
                print_error("Track not found on YouTube", "Try a different spelling or manual search")
                log_download("Spotify", track_info['name'], artist=" & ".join(track_info['artists']), mode="Single", status="Failed")
                return
            if self.download_track(yt_url, track_info):
                print_success("Download completed")
                log_download("Spotify", track_info['name'], artist=" & ".join(track_info['artists']), mode="Single", status="Success")
            else:
                print_error("Download failed")
                log_download("Spotify", track_info['name'], artist=" & ".join(track_info['artists']), mode="Single", status="Failed")
        except Exception as e:
            print_error(f"Error: {e}")

    def download_album(self, url):
        album_id = extract_album_id(url)
        if not album_id:
            print_error("Invalid Spotify album URL", "URL should contain /album/")
            return
        try:
            album = self.spotify.album(album_id)
            print_info(f"Album: {album['name']} by {album['artists'][0]['name']}")
            print_info(f"Total tracks: {album['total_tracks']}")
            confirm = input("Download all? (y/n): ").lower()
            if confirm != 'y':
                return

            tracks = []
            for t in album['tracks']['items']:
                tracks.append({
                    'name': t['name'],
                    'artists': [a['name'] for a in t['artists']]
                })
            total = len(tracks)
            print_success(f"Found {total} tracks")

            success, fail = 0, 0
            for i, track in enumerate(tracks, 1):
                print(f"\n{'─' * 61}")
                print_info(f"[{i}/{total}] Searching: {track['name']}")
                yt_url = self.search_youtube(track)
                if not yt_url:
                    print_error(f"[{i}/{total}] Not found on YouTube: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Album", status="Failed")
                    fail += 1
                    continue
                if self.download_track(yt_url, track, i, total):
                    success += 1
                    print_success(f"[{i}/{total}] Downloaded: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Album", status="Success")
                else:
                    fail += 1
                    print_error(f"[{i}/{total}] Failed: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Album", status="Failed")
                time.sleep(1)

            print("\n" + "═" * 61)
            print_success(f"Album download finished: {success} successful, {fail} failed")
            print("═" * 61)
        except Exception as e:
            print_error(f"Error: {e}")

# ----------------------------------------------------------------------
# Entry point called from main menu
# ----------------------------------------------------------------------
def run(config):
    clear_screen()
    print_banner()
    print("                   🎵 Spotify Downloader")
    print("=" * 61)
    print()
    print(f"{CYAN}{BOLD}1.{RESET} Download playlist")
    print(f"{CYAN}{BOLD}2.{RESET} Download single track")
    print(f"{CYAN}{BOLD}3.{RESET} Download album")
    print(f"{CYAN}{BOLD}4.{RESET} Back to main menu")
    print()
    print("=" * 61)
    choice = input("Select (1-4): ").strip()
    if choice == "4":
        return

    try:
        downloader = SpotifyDownloader(config)
    except (ValueError, ConnectionError) as e:
        print_error(str(e), "Please set your Spotify API credentials in Settings → Spotify API credentials")
        input("Press Enter to continue...")
        return

    url = input("\n🎯 Enter Spotify URL: ").strip()
    if not url:
        return

    if choice == "1":
        downloader.download_playlist(url)
    elif choice == "2":
        downloader.download_single_track(url)
    elif choice == "3":
        downloader.download_album(url)
    else:
        print_error("Invalid choice", "Please select 1-4")

    input("\nPress Enter to continue...")