import sys
import time
from pathlib import Path
from yt_dlp import YoutubeDL

from utils.ui import (
    clear_screen, print_error, print_success, print_info, print_warning,
    start_spinner, stop_spinner, progress_bar
)
from utils.logger import log_download
from utils.ffmpeg import get_ffmpeg_path

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def get_url_info(url):
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
        print_error(f"Could not fetch info: {e}", "Check your internet connection and URL")
        return None

def progress_hook(d):
    if d['status'] == 'downloading':
        total = d.get('total_bytes', d.get('total_bytes_estimate', 1))
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
        speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"
        eta = d.get('eta', 0)
        eta_str = f"{eta}s" if eta else "N/A"
        progress_bar(downloaded, total, prefix="Downloading", suffix=f"{speed_str} | ETA: {eta_str}")
    elif d['status'] == 'finished':
        print("\n" + " " * 80, end="\r")
        print_success("Download finished, now converting...")

def download_content(url, mode, config):
    download_dir = config['download_dir']
    yt_cfg = config['youtube']
    quiet = yt_cfg.get('quiet_mode', True)

    opts = {
        'outtmpl': str(Path(download_dir) / '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': quiet,
        'no_warnings': quiet,
        'noprogress': True,  # use our custom hook only
    }
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        opts['ffmpeg_location'] = ffmpeg

    if mode == "1":
        opts['format'] = 'bestvideo+bestaudio/best'
        opts['merge_output_format'] = 'mp4'
    elif mode == "2":
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': yt_cfg['audio_quality'].replace('k', ''),
        }]
    elif mode == "3":
        print_info("Fetching available formats...")
        with YoutubeDL({'quiet': True, 'listformats': True}) as ydl:
            ydl.extract_info(url, download=False)
        fmt = input("🎯 Enter format ID: ").strip()
        if not fmt:
            print_error("No format ID provided", "Please enter a valid format ID")
            return
        opts['format'] = fmt

    info = get_url_info(url)
    if info:
        if info['type'] == 'playlist':
            print_info(f"Playlist: {info['title']} ({info['video_count']} videos)")
            confirm = input(f"Download all as {'MP3' if mode=='2' else 'video'}? (y/n): ").lower()
            if confirm != 'y':
                return
            playlist_folder = Path(download_dir) / info['title']
            playlist_folder.mkdir(exist_ok=True)
            opts['outtmpl'] = str(playlist_folder / '%(title)s.%(ext)s')
        else:
            print_info(f"Video: {info['title']} by {info['uploader']}")
            confirm = input("Download? (y/n): ").lower()
            if confirm != 'y':
                return

    try:
        start_spinner("Preparing download")
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        stop_spinner()
        print_success("Download completed!")
        log_download("YouTube", info.get('title', url), mode=mode, status="Success")
    except Exception as e:
        stop_spinner()
        print_error(f"Download failed: {e}", "Check your internet connection and try again")
        if yt_cfg.get('auto_retry', True):
            retry = input("Retry? (y/n): ").lower()
            if retry == 'y':
                download_content(url, mode, config)
        else:
            log_download("YouTube", info.get('title', url), mode=mode, status="Failed", error=str(e))

def run(config):
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
        print_error("Invalid choice", "Please enter 1, 2, 3, or 4")
        input("Press Enter...")
        return

    while True:
        url = input("\n🎯 YouTube URL (video or playlist): ").strip()
        if not url:
            break
        if "youtube.com" in url or "youtu.be" in url:
            download_content(url, mode, config)
        else:
            print_error("Not a valid YouTube URL", "URL should contain youtube.com or youtu.be")
        again = input("\nDownload another? (y/n): ").lower()
        if again != 'y':
            break