import sys
import time
from pathlib import Path
from yt_dlp import YoutubeDL

from utils.config import load_config
from utils.ui import start_spinner, stop_spinner, clear_screen
from utils.logger import log_download
from utils.ffmpeg import get_ffmpeg_path

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def format_duration(seconds):
    if not seconds:
        return "Unknown"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def get_url_info(url):
    """Extract video/playlist info without downloading."""
    try:
        with YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                return {
                    'type': 'playlist',
                    'title': info.get('title', 'Unknown Playlist'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'video_count': len(info['entries']),
                    'videos': [e.get('title', '?') for e in info['entries'][:5]]
                }
            else:
                return {
                    'type': 'video',
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'upload_date': info.get('upload_date', 'Unknown')
                }
    except Exception as e:
        print(f"❌ Error fetching info: {e}")
        return None

def progress_hook(d):
    """Display download progress."""
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%').strip()
        speed = d.get('_speed_str', 'N/A').strip()
        eta = d.get('_eta_str', 'N/A').strip()
        sys.stdout.write(f"\r⏳ Downloading... {percent} | Speed: {speed} | ETA: {eta}")
        sys.stdout.flush()
    elif d['status'] == 'finished':
        print("\n✅ Download finished, now converting...")

def download_content(url, mode, config):
    """Main download function for single video/playlist."""
    download_dir = config['download_dir']
    yt_cfg = config['youtube']
    quiet = yt_cfg.get('quiet_mode', True)

    opts = {
        'outtmpl': str(Path(download_dir) / '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': quiet,
        'no_warnings': quiet,
        'noprogress': not quiet,
    }

    # Add FFmpeg if available
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        opts['ffmpeg_location'] = ffmpeg

    if mode == "1":  # Video best quality
        opts['format'] = 'bestvideo+bestaudio/best'
        opts['merge_output_format'] = 'mp4'
    elif mode == "2":  # MP3
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': yt_cfg['audio_quality'].replace('k', ''),
        }]
    elif mode == "3":  # Manual format selection
        print("\n📋 Fetching available formats...")
        with YoutubeDL({'quiet': True, 'listformats': True}) as ydl:
            ydl.extract_info(url, download=False)
        fmt = input("🎯 Enter format ID: ").strip()
        if not fmt:
            print("❌ No format ID.")
            return
        opts['format'] = fmt

    # Get info for display
    info = get_url_info(url)
    if info:
        if info['type'] == 'playlist':
            print(f"\n📂 Playlist: {info['title']} ({info['video_count']} videos)")
            confirm = input(f"Download all as {'MP3' if mode=='2' else 'video'}? (y/n): ").lower()
            if confirm != 'y':
                return
            # Create subfolder for playlist
            playlist_folder = Path(download_dir) / info['title']
            playlist_folder.mkdir(exist_ok=True)
            opts['outtmpl'] = str(playlist_folder / '%(title)s.%(ext)s')
        else:
            print(f"\n📹 {info['title']} ({info['uploader']})")
            confirm = input("Download? (y/n): ").lower()
            if confirm != 'y':
                return

    # Download
    try:
        start_spinner("⏳ Starting download")
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        stop_spinner()
        print("\n✅ Download completed!")
        log_download("YouTube", info.get('title', url), mode=mode, status="Success")
    except Exception as e:
        stop_spinner()
        print(f"\n❌ Download error: {e}")
        if yt_cfg.get('auto_retry', True):
            retry = input("Retry? (y/n): ").lower()
            if retry == 'y':
                download_content(url, mode, config)
        else:
            log_download("YouTube", info.get('title', url), mode=mode, status="Failed", error=str(e))

# ----------------------------------------------------------------------
# Main entry point from LinkCaty
# ----------------------------------------------------------------------
def run(config):
    """Called from main menu."""
    clear_screen()
    print("\n" + "═" * 55)
    print("            🎬 YouTube Downloader")
    print("═" * 55)
    print("1. Download video (best quality)")
    print("2. Download audio (MP3)")
    print("3. Manual format selection")
    print("4. Back to main menu")
    print("═" * 55)
    mode = input("Select (1-4): ").strip()
    if mode == "4":
        return
    if mode not in ("1", "2", "3"):
        print("Invalid choice.")
        input("Press Enter...")
        return

    while True:
        url = input("\n🎯 YouTube URL (video or playlist): ").strip()
        if not url:
            break
        if "youtube.com" in url or "youtu.be" in url:
            download_content(url, mode, config)
        else:
            print("❌ Not a valid YouTube URL.")
        again = input("\nDownload another? (y/n): ").lower()
        if again != 'y':
            break