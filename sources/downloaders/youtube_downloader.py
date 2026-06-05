import sys
import time
from pathlib import Path
from yt_dlp import YoutubeDL

from utils.ui import (
    clear_screen, print_banner, print_error, print_success, print_info, print_warning,
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
# Fetch video/playlist info (with spinner)
# ----------------------------------------------------------------------
def get_url_info(url):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                entries = [e for e in info['entries'] if e]
                return {
                    'type': 'playlist',
                    'title': info.get('title', 'Unknown Playlist'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'video_count': len(entries),
                    'videos': [e.get('title', f'Video {i+1}') for i, e in enumerate(entries[:5])]
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
# Progress hook (exactly like original)
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
# Download a single video (with retry)
# ----------------------------------------------------------------------
def download_single_video(video_url, output_dir, mode, config, max_retries=2):
    """Download one video with up to max_retries. Returns (success, error_msg)."""
    yt_cfg = config['youtube']
    quiet = yt_cfg.get('quiet_mode', True)

    # Template: Artist - Title (artist is the uploader/channel name)
    outtmpl = str(Path(output_dir) / '%(uploader)s - %(title)s.%(ext)s')

    if mode == "1":
        ydl_opts = {
            'outtmpl': outtmpl,
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': quiet,
            'no_warnings': quiet,
            'noprogress': False,
        }
    else:  # mode 2
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

    # Add FFmpeg if available
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        ydl_opts['ffmpeg_location'] = ffmpeg

    # Attempt with retries
    for attempt in range(max_retries + 1):
        use_cookies = (attempt > 0)  # retry with cookies on second attempt
        if use_cookies:
            # Try to find a working browser
            for browser in ['chrome', 'firefox', 'edge', 'brave']:
                try:
                    ydl_opts['cookiesfrombrowser'] = (browser,)
                    # Test cookie extraction
                    with YoutubeDL({'quiet': True, 'cookiesfrombrowser': (browser,)}) as test:
                        test.extract_info("https://youtube.com", download=False)
                    print_info(f"Retry using cookies from {browser}")
                    break
                except:
                    continue
            else:
                print_warning("No browser cookies available. Trying without cookies...")
                # Remove cookies option if none work
                ydl_opts.pop('cookiesfrombrowser', None)

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            return True, None
        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries and ("Sign in to confirm" in error_msg or "bot" in error_msg):
                print_warning(f"Authentication failed. Retry {attempt+1}/{max_retries} with cookies...")
                print_info("Please close your browser and press Enter to continue.")
                input("Press Enter to continue...")
                continue
            else:
                return False, error_msg
    return False, "Max retries exceeded"

# ----------------------------------------------------------------------
# Download playlist with per-video retry and skip if already exists
# ----------------------------------------------------------------------
def download_playlist(url, mode, config):
    print_info("Fetching playlist information...")
    start_spinner("Loading playlist")
    try:
        with YoutubeDL({'quiet': True, 'extract_flat': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' not in info:
                stop_spinner()
                print_error("Not a valid playlist URL")
                return
            entries = [e for e in info['entries'] if e]
            total = len(entries)
            stop_spinner()
            print_success(f"Found {total} videos in playlist")
    except Exception as e:
        stop_spinner()
        print_error(f"Failed to fetch playlist: {e}")
        return

    confirm = input(f"\n🚀 Download all {total} videos? (y/n): ").lower()
    if confirm != 'y':
        return

    playlist_title = info.get('title', 'Playlist').replace('/', '_').replace('\\', '_')
    playlist_folder = Path(config['download_dir']) / playlist_title
    playlist_folder.mkdir(exist_ok=True)

    success_count = 0
    fail_count = 0
    failed_videos = []

    for i, entry in enumerate(entries, 1):
        video_url = f"https://www.youtube.com/watch?v={entry['id']}"
        video_title = entry.get('title', f'Video {i}')
        # Sanitize filename to check existence
        safe_title = video_title.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        # Get uploader (if available from flat info) – fallback to "Unknown Artist"
        uploader = entry.get('uploader', 'Unknown Artist')
        expected_filename = f"{uploader} - {safe_title}.{'mp4' if mode=='1' else 'mp3'}"
        expected_path = playlist_folder / expected_filename

        if expected_path.exists():
            print(f"\n{'─' * 61}")
            print_info(f"[{i}/{total}] Skipping (already exists): {video_title[:50]}")
            success_count += 1
            continue

        print(f"\n{'─' * 61}")
        print_info(f"[{i}/{total}] Downloading: {video_title[:50]}")
        success, error = download_single_video(video_url, str(playlist_folder), mode, config, max_retries=2)
        if success:
            success_count += 1
            print_success(f"[{i}/{total}] Completed: {video_title[:50]}")
            log_download("YouTube", video_title, mode=mode, status="Success")
        else:
            fail_count += 1
            failed_videos.append((video_url, video_title, error))
            print_error(f"[{i}/{total}] Failed: {video_title[:50]} - {error[:100]}")
            log_download("YouTube", video_title, mode=mode, status="Failed", error=error)

        # Small delay between videos
        time.sleep(0.5)

    # Summary
    print("\n" + "═" * 61)
    print_success(f"Playlist download finished: {success_count} successful, {fail_count} failed")
    if failed_videos:
        print_warning("The following videos failed. You can retry them manually:")
        for url, title, err in failed_videos:
            print(f"  - {title[:60]} : {err[:80]}")
        # Save failed list to a file for later retry
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
        download_playlist(url, mode, config)
    else:
        display_video_info(info)
        confirm = input("\n🚀 Download this video? (y/n): ").lower()
        if confirm != 'y':
            print_info("Download cancelled")
            return

        download_dir = Path(config['download_dir'])
        success, error = download_single_video(url, str(download_dir), mode, config, max_retries=2)
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
    print("1. Download video (best quality)")
    print("2. Download audio (MP3)")
    print("3. Manual format selection")
    print("4. Back to main menu")
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
                'outtmpl': str(Path(download_dir) / '%(uploader)s - %(title)s.%(ext)s'),
                'format': fmt,
                'quiet': quiet,
                'no_warnings': quiet,
                'noprogress': False,
                'progress_hooks': [progress_hook],
            }
            ffmpeg = get_ffmpeg_path()
            if ffmpeg:
                opts['ffmpeg_location'] = ffmpeg
            start_spinner("Downloading with custom format")
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