import re
import time
import os
from pathlib import Path
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from utils.config import load_config, save_config
from utils.ui import clear_screen, start_spinner, stop_spinner
from utils.logger import log_download

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

def format_duration(ms):
    seconds = ms // 1000
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"

# ----------------------------------------------------------------------
# Main Spotify Downloader Class
# ----------------------------------------------------------------------
class SpotifyDownloader:
    def __init__(self, config):
        self.config = config
        self.spotify_config = config['spotify']
        self.download_dir = Path(config['download_dir'])
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Check credentials
        client_id = self.spotify_config.get('client_id', '')
        client_secret = self.spotify_config.get('client_secret', '')
        if not client_id or not client_secret:
            raise ValueError("Spotify API credentials missing. Please set them in Settings.")
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
        # Optional: add ffmpeg location if bundled
        return opts

    def search_youtube(self, track):
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
            pass
        return None

    def download_track(self, youtube_url, track_info, index=None, total=None):
        artists = " & ".join(track_info['artists'])
        title = f"{track_info['name']} - {artists}"
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        opts = self.get_ydl_opts()
        opts['outtmpl'] = str(self.download_dir / f"{safe_title}.%(ext)s")
        if index and total:
            print(f"[{index}/{total}] ", end="")
        print(f"📥 Downloading: {artists} - {track_info['name']}")
        try:
            start_spinner("⏳ Downloading")
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([youtube_url])
            stop_spinner()
            return True
        except Exception as e:
            stop_spinner()
            print(f"❌ Error: {e}")
            return False

    def download_playlist(self, url):
        playlist_id = extract_playlist_id(url)
        if not playlist_id:
            print("❌ Invalid Spotify playlist URL.")
            return
        try:
            playlist = self.spotify.playlist(playlist_id)
            print(f"\n📂 Playlist: {playlist['name']} by {playlist['owner']['display_name']}")
            print(f"🎵 Total tracks: {playlist['tracks']['total']}")
            confirm = input("Download all? (y/n): ").lower()
            if confirm != 'y':
                return
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
            success, fail = 0, 0
            for i, track in enumerate(tracks, 1):
                yt_url = self.search_youtube(track)
                if not yt_url:
                    print(f"❌ [{i}/{len(tracks)}] Not found: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Playlist", status="Failed")
                    fail += 1
                    continue
                if self.download_track(yt_url, track, i, len(tracks)):
                    success += 1
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Playlist", status="Success")
                else:
                    fail += 1
                time.sleep(1)
            print(f"\n✅ Completed: {success} successful, {fail} failed.")
        except Exception as e:
            print(f"❌ Error fetching playlist: {e}")

    def download_single_track(self, url):
        track_id = extract_track_id(url)
        if not track_id:
            print("❌ Invalid Spotify track URL.")
            return
        try:
            track = self.spotify.track(track_id)
            track_info = {
                'name': track['name'],
                'artists': [a['name'] for a in track['artists']],
                'album': track['album']['name']
            }
            print(f"\n🎵 {track_info['name']} by {', '.join(track_info['artists'])}")
            confirm = input("Download? (y/n): ").lower()
            if confirm != 'y':
                return
            yt_url = self.search_youtube(track_info)
            if not yt_url:
                print("❌ Not found on YouTube.")
                log_download("Spotify", track_info['name'], artist=" & ".join(track_info['artists']), mode="Single", status="Failed")
                return
            if self.download_track(yt_url, track_info):
                print("✅ Download completed.")
                log_download("Spotify", track_info['name'], artist=" & ".join(track_info['artists']), mode="Single", status="Success")
        except Exception as e:
            print(f"❌ Error: {e}")

    def download_album(self, url):
        album_id = extract_album_id(url)
        if not album_id:
            print("❌ Invalid Spotify album URL.")
            return
        try:
            album = self.spotify.album(album_id)
            print(f"\n💿 Album: {album['name']} by {album['artists'][0]['name']}")
            print(f"🎵 Total tracks: {album['total_tracks']}")
            confirm = input("Download all? (y/n): ").lower()
            if confirm != 'y':
                return
            tracks = []
            for t in album['tracks']['items']:
                tracks.append({
                    'name': t['name'],
                    'artists': [a['name'] for a in t['artists']]
                })
            success, fail = 0, 0
            for i, track in enumerate(tracks, 1):
                yt_url = self.search_youtube(track)
                if not yt_url:
                    print(f"❌ [{i}/{len(tracks)}] Not found: {track['name']}")
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Album", status="Failed")
                    fail += 1
                    continue
                if self.download_track(yt_url, track, i, len(tracks)):
                    success += 1
                    log_download("Spotify", track['name'], artist=" & ".join(track['artists']), mode="Album", status="Success")
                else:
                    fail += 1
                time.sleep(1)
            print(f"\n✅ Completed: {success} successful, {fail} failed.")
        except Exception as e:
            print(f"❌ Error: {e}")

# ----------------------------------------------------------------------
# Run function called from main menu
# ----------------------------------------------------------------------
def run(config):
    clear_screen()
    print("\n" + "═" * 55)
    print("            🎵 Spotify Downloader")
    print("═" * 55)
    print("1. Download playlist")
    print("2. Download single track")
    print("3. Download album")
    print("4. Back to main menu")
    print("═" * 55)
    choice = input("Select (1-4): ").strip()
    if choice == "4":
        return
    try:
        downloader = SpotifyDownloader(config)
    except (ValueError, ConnectionError) as e:
        print(f"\n❌ {e}")
        print("💡 Please set your Spotify API credentials in the Settings menu.")
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
        print("Invalid choice.")
    input("\nPress Enter to continue...")