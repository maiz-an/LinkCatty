import sys
import time
import re
from pathlib import Path
from yt_dlp import YoutubeDL

from utils.ui import (
    CYAN, BOLD,
    RESET, clear_screen, print_banner, print_error, print_success, print_info, print_warning,
    start_spinner, stop_spinner
)
from utils.logger import log_download
from utils.ffmpeg import get_ffmpeg_path

# ----------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------
def format_duration(seconds):
    if not seconds:
        return "Unknown"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def format_view_count(count):
    if not count:
        return "Unknown"
    if count >= 1_000_000:
        return f"{count/1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count/1_000:.1f}K"
    return str(count)

# ----------------------------------------------------------------------
# Get format specifier from video quality setting
# ----------------------------------------------------------------------
def get_video_format(video_quality):
    quality_map = {
        "best": "bestvideo+bestaudio/best",
        "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
        "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    }
    return quality_map.get(video_quality, "bestvideo+bestaudio/best")

# ----------------------------------------------------------------------
# Get browser cookie option with user guidance
# ----------------------------------------------------------------------
def get_browser_cookie_option():
    """Ask user to close browser, then try to get cookies from Chrome (or Firefox)."""
    print_info("YouTube requires authentication. Please close your browser (Chrome/Firefox/Edge) completely.")
    input("Press Enter to continue after closing your browser...")
    
    browsers = ['chrome', 'firefox', 'edge', 'brave']
    for browser in browsers:
        try:
            # Test if we can read cookies from this browser
            with YoutubeDL({'quiet': True, 'cookiesfrombrowser': (browser,)}) as test:
                test.extract_info("https://youtube.com", download=False)
            print_info(f"Successfully loaded cookies from {browser}")
            return (browser,)
        except Exception as e:
            continue
    print_warning("Could not load cookies from any browser. You may need to export cookies manually.")
    return None

# ----------------------------------------------------------------------
# Core download function with cookie fallback
# ----------------------------------------------------------------------
def download_single_video(video_url, output_dir, mode, config):
    yt_cfg = config['youtube']
    quiet = yt_cfg.get('quiet_mode', True)
    outtmpl = str(Path(output_dir) / '%(title)s - %(uploader)s.%(ext)s')

    # Build yt-dlp options (without cookies initially)
    if mode == "1":
        ydl_opts = {
            'outtmpl': outtmpl,
            'format': get_video_format(yt_cfg.get('video_quality', 'best')),
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': quiet,
            'no_warnings': quiet,
            'noprogress': False,
        }
    else:
        ydl_opts = {
            'outtmpl': outtmpl,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': yt_cfg['audio_quality'].replace('k', ''),
            }],
            'progress_hooks': [progress_hook],
            'quiet': quiet,
            'no_warnings': quiet,
            'noprogress': False,
        }

    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        ydl_opts['ffmpeg_location'] = ffmpeg

    # First attempt: direct (no cookies)
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" not in error_msg and "bot" not in error_msg:
            return False, error_msg
        print_warning("Direct download blocked. Attempting with browser cookies...")
    
    # Second attempt: with browser cookies (ask user to close browser)
    cookie_opt = get_browser_cookie_option()
    if cookie_opt:
        ydl_opts['cookiesfrombrowser'] = cookie_opt
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            return True, None
        except Exception as e:
            return False, str(e)
    else:
        return False, "No working cookies. Please export cookies to sources/cookies.txt"

# ----------------------------------------------------------------------
# Progress hook (same as original)
# ----------------------------------------------------------------------
download_completed_shown = False

def progress_hook(d):
    global download_completed_shown
    if d['status'] == 'downloading':
        if '_percent_str' in d:
            percent = d['_percent_str'].strip()
            speed = d.get('_speed_str', 'N/A').strip()
            eta = d.get('_eta_str', 'N/A').strip()
            total_size = d.get('_total_bytes_str', 'N/A').strip()
            downloaded = d.get('_downloaded_bytes_str', 'N/A').strip()
            sys.stdout.write(f"\r⏳ Downloading... {percent} | {downloaded}/{total_size} | Speed: {speed} | ETA: {eta}")
            sys.stdout.flush()
    elif d['status'] == 'finished' and not download_completed_shown:
        download_completed_shown = True
        filepath = d.get('filepath', 'Unknown')
        time.sleep(0.5)
        if filepath and filepath != 'Unknown' and Path(filepath).exists():
            filepath = str(Path(filepath).absolute())
            filename = Path(filepath).name
            try:
                size_mb = Path(filepath).stat().st_size / (1024 * 1024)
            except:
                size_mb = 0
            print("\n" + "═" * 55)
            print("            ✅ DOWNLOAD COMPLETED")
            print("═" * 55)
            print(f"📄 File name: {filename}")
            print(f"📂 Location: {Path(filepath).parent}")
            print(f"💾 File size: {size_mb:.2f} MB")
            print(f"⏰ Completed at: {time.strftime('%H:%M:%S')}")
            print("═" * 55 + "\n")
        else:
            print("\n✅ Download Completed Successfully\n")

# ----------------------------------------------------------------------
# Fetch video/playlist info with cookie fallback (same pattern)
# ----------------------------------------------------------------------
def get_url_info(url):
    # First attempt: no cookies
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return _parse_info(info)
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" not in error_msg and "bot" not in error_msg:
            print_error(f"Could not fetch info: {e}", "Check your internet connection and URL")
            return None
        print_warning("Info fetch blocked. Attempting with browser cookies...")
    
    # Second attempt: with browser cookies (ask user to close browser)
    cookie_opt = get_browser_cookie_option()
    if cookie_opt:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'cookiesfrombrowser': cookie_opt}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            print_info("Info fetch succeeded with browser cookies")
            return _parse_info(info)
        except Exception as e:
            print_error(f"Could not fetch info with cookies: {e}")
            return None
    else:
        print_error("No working cookies. Please export cookies to sources/cookies.txt")
        return None

def _parse_info(info):
    if 'entries' in info:
        entries = [e for e in info['entries'] if e]
        return {
            'type': 'playlist',
            'title': info.get('title', 'Unknown Playlist'),
            'uploader': info.get('uploader', 'Unknown'),
            'video_count': len(entries),
            'videos': [e.get('title', f'Video {i+1}') for i, e in enumerate(entries[:5])],
            'full_info': info
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

# ----------------------------------------------------------------------
# Display info
# ----------------------------------------------------------------------
def display_video_info(info):
    print("\n" + "─" * 61)
    print("📹 VIDEO INFORMATION")
    print("─" * 61)
    print(f"📺 Title: {info['title']}")
    print(f"👤 Artist/Channel: {info['uploader']}")
    print(f"⏱️ Duration: {format_duration(info['duration'])}")
    print(f"👀 Views: {format_view_count(info['view_count'])}")
    if info.get('upload_date'):
        print(f"📅 Upload date: {info['upload_date'][:4]}-{info['upload_date'][4:6]}-{info['upload_date'][6:]}")
    print("─" * 61)

def display_playlist_info(info):
    print("\n" + "─" * 61)
    print("📂 PLAYLIST INFORMATION")
    print("─" * 61)
    print(f"📺 Playlist: {info['title']}")
    print(f"👤 Channel: {info['uploader']}")
    print(f"🎬 Total Videos: {info['video_count']}")
    print("\n📹 First few videos:")
    for i, title in enumerate(info['videos'], 1):
        print(f"  {i}. {title[:50]}")
    print("─" * 61)

# ----------------------------------------------------------------------
# Download playlist with per-video progress and skipping existing files
# ----------------------------------------------------------------------
def download_playlist(playlist_info, mode, config):
    full_info = playlist_info.get('full_info')
    if not full_info or 'entries' not in full_info:
        print_error("Playlist information missing or invalid")
        return

    entries = [e for e in full_info['entries'] if e]
    total = len(entries)
    print_success(f"Found {total} videos in playlist")

    confirm = input(f"\n🚀 Download all {total} videos? (y/n): ").lower()
    if confirm != 'y':
        return

    playlist_title = full_info.get('title', 'Playlist').replace('/', '_').replace('\\', '_')
    playlist_folder = Path(config['download_dir']) / playlist_title
    playlist_folder.mkdir(exist_ok=True)

    success_count = 0
    fail_count = 0
    failed_videos = []

    for i, entry in enumerate(entries, 1):
        video_url = f"https://www.youtube.com/watch?v={entry['id']}"
        video_title = entry.get('title', f'Video {i}')
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)
        uploader = entry.get('uploader', 'Unknown Artist')
        ext = 'mp4' if mode == '1' else 'mp3'
        expected_filename = f"{safe_title} - {uploader}.{ext}"
        expected_path = playlist_folder / expected_filename

        if expected_path.exists():
            print(f"\n{'─' * 61}")
            print_info(f"[{i}/{total}] Skipping (already exists): {video_title[:50]}")
            success_count += 1
            continue

        print(f"\n{'─' * 61}")
        print_info(f"[{i}/{total}] Downloading: {video_title[:50]}")
        success, error = download_single_video(video_url, str(playlist_folder), mode, config)
        if success:
            success_count += 1
            print_success(f"[{i}/{total}] Completed: {video_title[:50]}")
            log_download("YouTube", video_title, mode=mode, status="Success")
        else:
            fail_count += 1
            failed_videos.append((video_url, video_title, error))
            print_error(f"[{i}/{total}] Failed: {video_title[:50]} - {error[:100]}")
            log_download("YouTube", video_title, mode=mode, status="Failed", error=error)

        time.sleep(0.5)

    print("\n" + "═" * 61)
    print_success(f"Playlist download finished: {success_count} successful, {fail_count} failed")
    if failed_videos:
        print_warning("The following videos failed. You can retry them manually:")
        for url, title, err in failed_videos[:10]:
            print(f"  - {title[:60]} : {err[:80]}")
        if len(failed_videos) > 10:
            print(f"  ... and {len(failed_videos)-10} more")
        fail_log = playlist_folder / "_failed_videos.txt"
        with open(fail_log, 'w', encoding='utf-8') as f:
            for url, title, err in failed_videos:
                f.write(f"{url} | {title}\n")
        print_info(f"Failed URLs saved to: {fail_log}")
    print("═" * 61)

# ----------------------------------------------------------------------
# Main download dispatcher
# ----------------------------------------------------------------------
def download_content(url, mode, config):
    start_spinner("🎬 Fetching video/playlist information")
    info = get_url_info(url)
    stop_spinner()
    if not info:
        return

    if info['type'] == 'playlist':
        display_playlist_info(info)
        download_playlist(info, mode, config)
    else:
        display_video_info(info)
        confirm = input("\n🚀 Download this video? (y/n): ").lower()
        if confirm != 'y':
            print_info("Download cancelled")
            return

        download_dir = Path(config['download_dir'])
        success, error = download_single_video(url, str(download_dir), mode, config)
        if success:
            print_success("Download completed!")
            log_download("YouTube", info['title'], mode=mode, status="Success")
        else:
            print_error(f"Download failed: {error}")
            log_download("YouTube", info['title'], mode=mode, status="Failed", error=error)

# ----------------------------------------------------------------------
# Entry point from main menu
# ----------------------------------------------------------------------
def run(config):
    clear_screen()
    print_banner()
    print("                   🎬 YouTube Downloader")
    print("=" * 61)
    print()
    print(f"{CYAN}{BOLD}1.{RESET} Download video (best quality)")
    print(f"{CYAN}{BOLD}2.{RESET} Download audio (MP3)")
    print(f"{CYAN}{BOLD}3.{RESET} Manual format selection")
    print(f"{CYAN}{BOLD}4.{RESET} Back to main menu")
    print()
    print("=" * 61)
    mode = input("Select (1-4): ").strip()
    if mode == "4":
        return
    if mode not in ("1", "2", "3"):
        print_error("Invalid choice", "Please enter 1, 2, 3, or 4")
        input("Press Enter...")
        return

    # Manual format selection (mode 3)
    if mode == "3":
        url = input("\n🎯 YouTube URL: ").strip()
        if not url:
            return
        print_info("Fetching available formats...")
        try:
            with YoutubeDL({'quiet': True, 'listformats': True}) as ydl:
                ydl.extract_info(url, download=False)
            fmt = input("🎯 Enter format ID: ").strip()
            if not fmt:
                print_error("No format ID provided")
                return
            download_dir = config['download_dir']
            yt_cfg = config['youtube']
            quiet = yt_cfg.get('quiet_mode', True)
            opts = {
                'outtmpl': str(Path(download_dir) / '%(title)s - %(uploader)s.%(ext)s'),
                'format': fmt,
                'quiet': quiet,
                'no_warnings': quiet,
                'noprogress': False,
                'progress_hooks': [progress_hook],
            }
            ffmpeg = get_ffmpeg_path()
            if ffmpeg:
                opts['ffmpeg_location'] = ffmpeg
            print_info(f"Started download with custom format ID: {fmt}")
            start_spinner() 
            with YoutubeDL(opts) as ydl:
                ydl.download([url])
            stop_spinner()
            print_success("Download completed!")
            log_download("YouTube", url, mode="Manual Format", status="Success")
        except Exception as e:
            stop_spinner()
            print_error(f"Manual download failed: {e}")
        input("\nPress Enter to continue...")
        return

    # Normal modes 1 & 2
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