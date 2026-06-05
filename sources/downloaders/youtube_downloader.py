import sys
import time
from pathlib import Path
from yt_dlp import YoutubeDL

from utils.ui import (
    clear_screen, print_banner, print_error, print_success, print_info, print_warning,
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

def format_view_count(count):
    if not count:
        return "Unknown"
    if count >= 1_000_000:
        return f"{count/1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count/1_000:.1f}K"
    return str(count)

def get_url_info(url):
    """Fetch video/playlist info and return formatted display."""
    try:
        with YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                # Playlist
                entries = [e for e in info['entries'] if e]
                return {
                    'type': 'playlist',
                    'title': info.get('title', 'Unknown Playlist'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'video_count': len(entries),
                    'videos': [(e.get('title', f'Video {i+1}'), e.get('duration', 0)) for i, e in enumerate(entries[:5])],
                    'total_videos': len(entries)
                }
            else:
                # Single video
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

def display_video_info(info):
    """Print detailed video information."""
    print("\n" + "─" * 61)
    print(f"📹 VIDEO INFORMATION")
    print("─" * 61)
    print(f"📺 Title: {info['title']}")
    print(f"👤 Channel: {info['uploader']}")
    print(f"⏱️ Duration: {format_duration(info['duration'])}")
    print(f"👀 Views: {format_view_count(info['view_count'])}")
    if info.get('upload_date'):
        print(f"📅 Upload date: {info['upload_date'][:4]}-{info['upload_date'][4:6]}-{info['upload_date'][6:]}")
    print("─" * 61)

def display_playlist_info(info):
    """Print playlist information."""
    print("\n" + "─" * 61)
    print(f"📂 PLAYLIST INFORMATION")
    print("─" * 61)
    print(f"📺 Playlist: {info['title']}")
    print(f"👤 Channel: {info['uploader']}")
    print(f"🎬 Total Videos: {info['video_count']}")
    print("\n📹 First few videos:")
    for i, (title, duration) in enumerate(info['videos'], 1):
        dur_str = format_duration(duration)
        print(f"  {i}. {title[:50]} ({dur_str})")
    print("─" * 61)

def progress_hook(d, video_index=None, total_videos=None, video_title=""):
    """Progress hook with optional playlist tracking."""
    if d['status'] == 'downloading':
        total = d.get('total_bytes', d.get('total_bytes_estimate', 1))
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
        speed_str = f"{speed/1024/1024:.1f} MB/s" if speed else "N/A"
        eta = d.get('eta', 0)
        eta_str = f"{eta}s" if eta else "N/A"
        
        # Build prefix with playlist progress if applicable
        prefix = ""
        if video_index is not None and total_videos:
            prefix = f"[{video_index}/{total_videos}] {video_title[:30]}... "
        else:
            prefix = "Downloading "
        
        progress_bar(downloaded, total, prefix=prefix, suffix=f"{speed_str} | ETA: {eta_str}")
    elif d['status'] == 'finished':
        print("\n" + " " * 80, end="\r")
        print_success("Download finished, now converting...")

def download_video(url, mode, config, playlist_context=None):
    """Download a single video (used for both single and playlist)."""
    download_dir = config['download_dir']
    yt_cfg = config['youtube']
    quiet = yt_cfg.get('quiet_mode', True)
    
    opts = {
        'outtmpl': str(Path(download_dir) / '%(title)s.%(ext)s'),
        'quiet': quiet,
        'no_warnings': quiet,
        'noprogress': True,
    }
    
    # Add custom progress hook with playlist context
    if playlist_context:
        opts['progress_hooks'] = [lambda d: progress_hook(
            d, 
            video_index=playlist_context['index'],
            total_videos=playlist_context['total'],
            video_title=playlist_context['title']
        )]
    else:
        opts['progress_hooks'] = [lambda d: progress_hook(d)]
    
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        opts['ffmpeg_location'] = ffmpeg
    
    if mode == "1":  # Video
        opts['format'] = 'bestvideo+bestaudio/best'
        opts['merge_output_format'] = 'mp4'
    elif mode == "2":  # MP3
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': yt_cfg['audio_quality'].replace('k', ''),
        }]
    elif mode == "3":  # Manual format
        # Handled in download_content for single video
        pass
    
    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print_error(f"Download failed: {e}")
        return False

def download_playlist(url, mode, config):
    """Download all videos in a playlist with progress tracking."""
    yt_cfg = config['youtube']
    quiet = yt_cfg.get('quiet_mode', True)
    
    # First, get playlist info to know all video URLs
    print_info("Fetching playlist videos...")
    try:
        with YoutubeDL({'quiet': True, 'extract_flat': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' not in info:
                print_error("Not a valid playlist URL")
                return False
        
        entries = [e for e in info['entries'] if e]
        total = len(entries)
        print_success(f"Found {total} videos in playlist")
        
        confirm = input(f"\n🚀 Download all {total} videos as {'MP3' if mode=='2' else 'video'}? (y/n): ").lower()
        if confirm != 'y':
            return False
        
        # Create playlist folder
        playlist_title = info.get('title', 'Playlist').replace('/', '_').replace('\\', '_')
        playlist_folder = Path(config['download_dir']) / playlist_title
        playlist_folder.mkdir(exist_ok=True)
        
        success_count = 0
        fail_count = 0
        
        for i, entry in enumerate(entries, 1):
            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
            video_title = entry.get('title', f'Video {i}')
            
            print(f"\n{'─' * 61}")
            print_info(f"[{i}/{total}] Downloading: {video_title[:50]}")
            
            # Prepare playlist context for progress hook
            context = {
                'index': i,
                'total': total,
                'title': video_title[:40]
            }
            
            # Custom download for this video with playlist folder
            download_dir = config['download_dir']
            yt_cfg = config['youtube']
            opts = {
                'outtmpl': str(playlist_folder / '%(title)s.%(ext)s'),
                'quiet': quiet,
                'no_warnings': quiet,
                'noprogress': True,
                'progress_hooks': [lambda d: progress_hook(d, video_index=i, total_videos=total, video_title=video_title[:40])]
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
            
            try:
                with YoutubeDL(opts) as ydl:
                    ydl.download([video_url])
                success_count += 1
                print_success(f"[{i}/{total}] Completed: {video_title[:50]}")
                log_download("YouTube", video_title, mode=mode, status="Success")
            except Exception as e:
                fail_count += 1
                print_error(f"[{i}/{total}] Failed: {video_title[:50]} - {str(e)[:50]}")
                log_download("YouTube", video_title, mode=mode, status="Failed", error=str(e))
            
            # Small delay to be respectful
            time.sleep(0.5)
        
        print("\n" + "═" * 61)
        print_success(f"Playlist download complete: {success_count} successful, {fail_count} failed")
        print("═" * 61)
        return True
        
    except Exception as e:
        print_error(f"Failed to process playlist: {e}")
        return False

def download_content(url, mode, config):
    """Main entry for download - detects playlist vs single."""
    # First, get info
    info = get_url_info(url)
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
        
        # Download single video
        try:
            start_spinner("Preparing download")
            success = download_video(url, mode, config)
            stop_spinner()
            if success:
                print_success("Download completed!")
                log_download("YouTube", info['title'], mode=mode, status="Success")
        except Exception as e:
            stop_spinner()
            print_error(f"Download failed: {e}", "Check your internet connection and try again")
            if config['youtube'].get('auto_retry', True):
                retry = input("Retry? (y/n): ").lower()
                if retry == 'y':
                    download_content(url, mode, config)
            else:
                log_download("YouTube", info['title'], mode=mode, status="Failed", error=str(e))

def run(config):
    clear_screen()
    print_banner()            
    print("                   🎬 YouTube Downloader")
    print("=" * 61)
    print("")
    print("1. Download video (best quality)")
    print("2. Download audio (MP3)")
    print("3. Manual format selection")
    print("4. Back to main menu")
    print("")
    print("=" * 61)
    mode = input("Select (1-4): ").strip()
    if mode == "4":
        return
    if mode not in ("1", "2", "3"):
        print_error("Invalid choice", "Please enter 1, 2, 3, or 4")
        input("Press Enter...")
        return
    
    # Manual format selection mode
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
            # For manual format, we need to set the format in opts
            # Reuse download_video but with custom format
            download_dir = config['download_dir']
            yt_cfg = config['youtube']
            quiet = yt_cfg.get('quiet_mode', True)
            opts = {
                'outtmpl': str(Path(download_dir) / '%(title)s.%(ext)s'),
                'format': fmt,
                'quiet': quiet,
                'no_warnings': quiet,
                'noprogress': True,
                'progress_hooks': [lambda d: progress_hook(d)]
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
    
    # For modes 1 and 2, loop for multiple URLs
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