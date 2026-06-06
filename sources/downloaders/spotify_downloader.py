import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yt_dlp

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    spotipy = None
    SpotifyClientCredentials = None

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


def extract_spotify_id(url, item_type):
    match = re.search(rf"{item_type}/([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None


def is_spotify_url(url, item_type):
    return bool(re.match(r"^https?://", url)) and f"spotify.com/{item_type}/" in url


def normalize_spotify_url(url):
    parsed = urllib.parse.urlparse(url.strip())
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def fetch_url(url, timeout=15):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_meta_content(page, key):
    pattern = (
        rf"<meta\b(?=[^>]*(?:property|name)=[\"']{re.escape(key)}[\"'])"
        rf"(?=[^>]*content=[\"']([^\"']+)[\"'])[^>]*>"
    )
    match = re.search(pattern, page, re.IGNORECASE)
    return html.unescape(match.group(1)).strip() if match else ""


def split_artists(value):
    value = html.unescape(value or "").strip()
    value = re.sub(r"\s+on Spotify$", "", value, flags=re.IGNORECASE)
    artists = [artist.strip() for artist in re.split(r"\s*(?:,|&|\band\b)\s*", value) if artist.strip()]
    return artists or ([value] if value else [])


def clean_spotify_title(title):
    title = html.unescape(title or "").strip()
    title = re.sub(r"\s*\|\s*Spotify\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*-\s*song and lyrics by .*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*-\s*single by .*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*-\s*track by .*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def parse_artist_from_text(text, track_name):
    text = html.unescape(text or "")
    text = re.sub(r"\s*\|\s*Spotify\s*$", "", text, flags=re.IGNORECASE)
    for pattern in (
        r"song and lyrics by\s+(.+)$",
        r"single by\s+(.+)$",
        r"track by\s+(.+)$",
        r"album by\s+(.+)$",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return split_artists(match.group(1))

    parts = [part.strip() for part in re.split(r"\s*[·•]\s*", text) if part.strip()]
    for part in parts:
        if part.lower() != track_name.lower() and not part.lower().startswith("spotify"):
            return split_artists(part)
    return []


def fetch_public_track_info(url):
    normalized_url = normalize_spotify_url(url)
    oembed_title = ""
    oembed_author = ""

    try:
        oembed_url = "https://open.spotify.com/oembed?url=" + urllib.parse.quote(normalized_url, safe="")
        oembed = json.loads(fetch_url(oembed_url))
        oembed_title = oembed.get("title", "")
        oembed_author = oembed.get("author_name", "")
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        pass

    page_title = ""
    page_description = ""
    try:
        page = fetch_url(normalized_url)
        page_title = extract_meta_content(page, "og:title") or extract_meta_content(page, "twitter:title")
        page_description = extract_meta_content(page, "og:description") or extract_meta_content(page, "twitter:description")
    except (OSError, urllib.error.URLError):
        pass

    raw_title = page_title or oembed_title
    track_name = clean_spotify_title(raw_title)
    artists = parse_artist_from_text(raw_title, track_name)
    if not artists:
        artists = parse_artist_from_text(page_description, track_name)
    if not artists and oembed_author and oembed_author.lower() != "spotify":
        artists = split_artists(oembed_author)

    if not track_name:
        raise ValueError("Could not read public track metadata from Spotify.")

    return {
        "name": track_name,
        "artists": artists or ["Unknown Artist"],
        "album": "",
        "source": "public Spotify page",
    }


def fetch_public_playlist_tracks(playlist_url):
    """
    Extract track list (names and artists) from a public Spotify playlist page.
    Returns list of dicts: [{'name': ..., 'artists': [...]}, ...]
    """
    normalized_url = normalize_spotify_url(playlist_url)
    page = fetch_url(normalized_url)
    # Spotify embeds track data in a <script> tag with id "initial-state" or inline JSON.
    # Simplified approach: look for the "initialData" or embedded list.
    # We'll parse the JSON inside the script.
    tracks = []

    # Try to find the JSON data containing tracks
    # Pattern: "tracks": { "items": [ ... ] }
    # Extract the large JSON object
    script_pattern = r'<script[^>]*id="initial-state"[^>]*>([\s\S]*?)</script>'
    match = re.search(script_pattern, page)
    if match:
        try:
            data = json.loads(match.group(1))
            # Navigate to tracks
            # The structure can vary; look for "entities" -> "items" or "playlist" -> "tracks"
            # Common path: data['entities']['items'] or data['playlist']['tracks']['items']
            if 'entities' in data and 'items' in data['entities']:
                for item in data['entities']['items']:
                    track = item.get('track', {})
                    if track:
                        tracks.append({
                            'name': track.get('name', 'Unknown'),
                            'artists': [a.get('name', 'Unknown') for a in track.get('artists', [])]
                        })
            elif 'playlist' in data and 'tracks' in data['playlist'] and 'items' in data['playlist']['tracks']:
                for item in data['playlist']['tracks']['items']:
                    track = item.get('track', {})
                    if track:
                        tracks.append({
                            'name': track.get('name', 'Unknown'),
                            'artists': [a.get('name', 'Unknown') for a in track.get('artists', [])]
                        })
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: look for <meta> tags and oembed for playlist metadata? Not for tracks.
    # If JSON extraction failed, use a more resilient method: request the embed page.
    if not tracks:
        # Use embed endpoint which returns JSON with track list
        embed_url = f"https://open.spotify.com/embed/playlist/{extract_spotify_id(playlist_url, 'playlist')}"
        embed_data = fetch_url(embed_url)
        # The embed page contains a JSON script
        embed_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({[\s\S]+?});', embed_data)
        if embed_match:
            try:
                embed_json = json.loads(embed_match.group(1))
                # Navigate to tracks
                if 'context' in embed_json and 'tracks' in embed_json['context']:
                    for item in embed_json['context']['tracks'].get('items', []):
                        track = item.get('track', {})
                        if track:
                            tracks.append({
                                'name': track.get('name', 'Unknown'),
                                'artists': [a.get('name', 'Unknown') for a in track.get('artists', [])]
                            })
            except (json.JSONDecodeError, KeyError):
                pass

    if not tracks:
        raise ValueError("Could not extract playlist tracks from public Spotify page. The playlist may be private or require API credentials.")

    return tracks


def fetch_public_album_tracks(album_url):
    """
    Extract track list from a public Spotify album page.
    Similar to playlist extraction but for album endpoint.
    """
    album_id = extract_spotify_id(album_url, 'album')
    if not album_id:
        raise ValueError("Invalid album URL")

    embed_url = f"https://open.spotify.com/embed/album/{album_id}"
    page = fetch_url(embed_url)
    tracks = []
    # Look for __INITIAL_STATE__ JSON
    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({[\s\S]+?});', page)
    if match:
        try:
            data = json.loads(match.group(1))
            # Navigate to tracks
            if 'context' in data and 'tracks' in data['context']:
                for item in data['context']['tracks'].get('items', []):
                    track = item.get('track', {})
                    if track:
                        tracks.append({
                            'name': track.get('name', 'Unknown'),
                            'artists': [a.get('name', 'Unknown') for a in track.get('artists', [])]
                        })
        except (json.JSONDecodeError, KeyError):
            pass

    if not tracks:
        raise ValueError("Could not extract album tracks from public Spotify page. The album may be private or require API credentials.")
    return tracks


def is_premium_required_error(error):
    message = str(error).lower()
    return "premium subscription required" in message or "http status: 403" in message


class SpotifyDownloader:
    def __init__(self, config):
        self.config = config
        self.spotify_config = config["spotify"]
        self.download_dir = Path(config["download_dir"])
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.spotify = None

        client_id = self.spotify_config.get("client_id", "").strip()
        client_secret = self.spotify_config.get("client_secret", "").strip()
        if not client_id or not client_secret or spotipy is None:
            return

        try:
            self.spotify = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret,
                )
            )
        except Exception as error:
            print_error(f"Spotify API setup failed: {error}", "Single tracks can still use public Spotify metadata.")

    def get_ydl_opts(self):
        quality = self.spotify_config.get("audio_quality", "320k").replace("k", "")
        options = {
            "format": "bestaudio/best",
            "outtmpl": str(self.download_dir / "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }],
            "quiet": self.spotify_config.get("quiet_mode", True),
            "no_warnings": True,
            "ignoreerrors": True,
        }
        ffmpeg = get_ffmpeg_path()
        if ffmpeg:
            options["ffmpeg_location"] = ffmpeg
        return options

    def search_youtube(self, track, retry=0):
        artists = [artist for artist in track["artists"] if artist != "Unknown Artist"]
        if artists:
            query = f"{' & '.join(artists)} - {track['name']} official audio"
        else:
            query = f"{track['name']} official audio"
        query = re.sub(r"[^\w\s-]", "", query)
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if results and results.get("entries"):
                result_url = results["entries"][0].get("url")
                if result_url and not result_url.startswith("http"):
                    return f"https://www.youtube.com/watch?v={result_url}"
                return result_url
        except Exception:
            if retry < self.spotify_config.get("max_retries", 3):
                time.sleep(1)
                return self.search_youtube(track, retry + 1)
        return None

    def download_track(self, youtube_url, track_info, index=None, total=None):
        artists = " & ".join(track_info["artists"])
        title = f"{track_info['name']} - {artists}" if artists != "Unknown Artist" else track_info["name"]
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
        options = self.get_ydl_opts()
        options["outtmpl"] = str(self.download_dir / f"{safe_title}.%(ext)s")
        if index and total:
            print(f"[{index}/{total}] ", end="")
        print_info(f"Downloading: {artists} - {track_info['name']}")
        try:
            start_spinner("Downloading from YouTube")
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([youtube_url])
            stop_spinner()
            return True
        except Exception as error:
            stop_spinner()
            print_error(f"Download error: {error}", "Check FFmpeg, network access, and the YouTube result.")
            return False

    def get_track_info(self, track_id, url):
        if self.spotify is not None:
            try:
                track = self.spotify.track(track_id)
                return {
                    "name": track["name"],
                    "artists": [artist["name"] for artist in track["artists"]],
                    "album": track["album"]["name"],
                    "source": "Spotify API",
                }
            except Exception as error:
                if is_premium_required_error(error):
                    print_info("Spotify API requires Premium for this app. Trying public metadata fallback.")
                else:
                    print_error(f"Spotify API track lookup failed: {error}", "Trying public metadata fallback.")
        return fetch_public_track_info(url)

    def download_single_track(self, url):
        track_id = extract_spotify_id(url, "track")
        if not track_id:
            print_error("Invalid Spotify track URL", "Use a link containing spotify.com/track/.")
            return
        try:
            track_info = self.get_track_info(track_id, url)
            print_info(f"Track: {track_info['name']} by {', '.join(track_info['artists'])}")
            if track_info.get("source") == "public Spotify page":
                print_info("Using public Spotify metadata fallback; Premium/API access is not required.")
            if not confirm("Download?"):
                return

            print_info("Searching on YouTube...")
            youtube_url = self.search_youtube(track_info)
            if not youtube_url:
                print_error("Track not found on YouTube", "Try a different spelling or manual YouTube download.")
                log_download("Spotify", track_info["name"], artist=" & ".join(track_info["artists"]), mode="Single", status="Failed")
                return
            if self.download_track(youtube_url, track_info):
                print_success("Download completed")
                log_download("Spotify", track_info["name"], artist=" & ".join(track_info["artists"]), mode="Single", status="Success")
            else:
                log_download("Spotify", track_info["name"], artist=" & ".join(track_info["artists"]), mode="Single", status="Failed")
        except Exception as error:
            print_error(f"Error fetching track: {error}", "Check the track link and network connection.")

    def download_playlist(self, url):
        playlist_id = extract_spotify_id(url, "playlist")
        if not playlist_id:
            print_error("Invalid Spotify playlist URL", "Use a link containing spotify.com/playlist/.")
            return
        tracks = []
        try:
            # Try API first (requires API credentials, may need Premium)
            if self.spotify is not None:
                playlist = self.spotify.playlist(playlist_id)
                print_info(f"Playlist: {playlist['name']} by {playlist['owner']['display_name']}")
                print_info(f"Total tracks: {playlist['tracks']['total']}")
                if not confirm("Download all?"):
                    return
                print_info("Fetching playlist tracks via API...")
                tracks = self.fetch_playlist_tracks_via_api(playlist_id)
            else:
                raise Exception("No API credentials")
        except Exception as error:
            if is_premium_required_error(error):
                print_info("Spotify API blocked (Premium required). Falling back to public web scraping.")
            else:
                print_warning(f"API failed ({error}). Falling back to public web scraping.")
            # Fallback to public scraping
            try:
                tracks = fetch_public_playlist_tracks(url)
                print_success(f"Found {len(tracks)} tracks via public scraping.")
                if not confirm("Download all tracks from this playlist?"):
                    return
            except Exception as scrape_error:
                print_error(f"Failed to extract playlist tracks: {scrape_error}", "Playlist may be private or require API credentials.")
                return
        self.download_track_list(tracks, "Playlist")

    def fetch_playlist_tracks_via_api(self, playlist_id):
        if self.spotify is None:
            raise ValueError("Spotify API not available")
        tracks = []
        results = self.spotify.playlist_tracks(playlist_id)
        while results:
            for item in results.get("items", []):
                track = item.get("track")
                if track:
                    tracks.append({
                        "name": track["name"],
                        "artists": [artist["name"] for artist in track["artists"]],
                    })
            results = self.spotify.next(results) if results.get("next") else None
        return tracks

    def download_album(self, url):
        album_id = extract_spotify_id(url, "album")
        if not album_id:
            print_error("Invalid Spotify album URL", "Use a link containing spotify.com/album/.")
            return
        tracks = []
        try:
            # Try API first
            if self.spotify is not None:
                album = self.spotify.album(album_id)
                print_info(f"Album: {album['name']} by {album['artists'][0]['name']}")
                print_info(f"Total tracks: {album['total_tracks']}")
                if not confirm("Download all?"):
                    return
                tracks = [
                    {"name": track["name"], "artists": [artist["name"] for artist in track["artists"]]}
                    for track in album["tracks"]["items"]
                ]
            else:
                raise Exception("No API credentials")
        except Exception as error:
            if is_premium_required_error(error):
                print_info("Spotify API blocked (Premium required). Falling back to public web scraping.")
            else:
                print_warning(f"API failed ({error}). Falling back to public web scraping.")
            try:
                tracks = fetch_public_album_tracks(url)
                print_success(f"Found {len(tracks)} tracks via public scraping.")
                if not confirm("Download all tracks from this album?"):
                    return
            except Exception as scrape_error:
                print_error(f"Failed to extract album tracks: {scrape_error}", "Album may be private or require API credentials.")
                return
        self.download_track_list(tracks, "Album")

    def download_track_list(self, tracks, mode):
        total = len(tracks)
        if total == 0:
            print_error("No tracks were found.")
            return
        print_success(f"Found {total} tracks")
        success = 0
        failed = 0
        for index, track in enumerate(tracks, 1):
            print(f"\n{'─' * 61}")
            print_info(f"[{index}/{total}] Searching: {track['name']}")
            youtube_url = self.search_youtube(track)
            artist = " & ".join(track["artists"])
            if not youtube_url:
                print_error(f"[{index}/{total}] Not found on YouTube: {track['name']}")
                log_download("Spotify", track["name"], artist=artist, mode=mode, status="Failed")
                failed += 1
                continue
            if self.download_track(youtube_url, track, index, total):
                print_success(f"[{index}/{total}] Downloaded: {track['name']}")
                log_download("Spotify", track["name"], artist=artist, mode=mode, status="Success")
                success += 1
            else:
                print_error(f"[{index}/{total}] Failed: {track['name']}")
                log_download("Spotify", track["name"], artist=artist, mode=mode, status="Failed")
                failed += 1
            time.sleep(1)
        print("\n" + "═" * 61)
        print_success(f"{mode} download finished: {success} successful, {failed} failed")
        print("═" * 61)


def create_downloader(config):
    try:
        return SpotifyDownloader(config)
    except Exception as error:
        print_error(str(error), "Fix the download folder or configuration and try again.")
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
        elif choice == "1":
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
        print("                   🎵 Spotify Downloader")
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