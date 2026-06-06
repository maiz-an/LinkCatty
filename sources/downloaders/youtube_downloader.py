import re
import sys
import time
from pathlib import Path

from yt_dlp import YoutubeDL

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
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
    print_warning,
    start_spinner,
    stop_spinner,
)


def format_duration(seconds):
    if not seconds:
        return "Unknown"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_view_count(count):
    if not count:
        return "Unknown"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def is_youtube_url(url):
    return bool(re.match(r"^https?://", url)) and ("youtube.com" in url or "youtu.be" in url)


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


def get_browser_cookie_option():
    print_info("YouTube requires authentication. Close Chrome/Firefox/Edge completely first.")
    pause("Press Enter after closing your browser...")
    for browser in ("chrome", "firefox", "edge", "brave"):
        try:
            with YoutubeDL({"quiet": True, "cookiesfrombrowser": (browser,)}) as test:
                test.extract_info("https://youtube.com", download=False)
            print_info(f"Successfully loaded cookies from {browser}")
            return (browser,)
        except Exception:
            continue
    print_warning("Could not load cookies from a supported browser.")
    return None


def build_download_options(output_dir, mode, config):
    youtube_config = config["youtube"]
    quiet = youtube_config.get("quiet_mode", True)
    options = {
        "outtmpl": str(Path(output_dir) / "%(title)s - %(uploader)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": False,
    }

    if mode == "1":
        options.update({
            "format": get_video_format(youtube_config.get("video_quality", "best")),
            "merge_output_format": "mp4",
        })
    else:
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": youtube_config["audio_quality"].replace("k", ""),
            }],
        })

    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg
    return options


def download_single_video(video_url, output_dir, mode, config):
    options = build_download_options(output_dir, mode, config)
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as error:
        error_message = str(error)
        if "Sign in to confirm" not in error_message and "bot" not in error_message:
            return False, error_message
        print_warning("Direct download blocked. Trying browser cookies.")

    cookie_option = get_browser_cookie_option()
    if not cookie_option:
        return False, "No working browser cookies. Try logging into YouTube in your browser."
    options["cookiesfrombrowser"] = cookie_option
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([video_url])
        return True, None
    except Exception as error:
        return False, str(error)


download_completed_shown = False


def progress_hook(data):
    global download_completed_shown
    if data["status"] == "downloading" and "_percent_str" in data:
        percent = data["_percent_str"].strip()
        speed = data.get("_speed_str", "N/A").strip()
        eta = data.get("_eta_str", "N/A").strip()
        total_size = data.get("_total_bytes_str", "N/A").strip()
        downloaded = data.get("_downloaded_bytes_str", "N/A").strip()
        sys.stdout.write(f"\r⏳ Downloading... {percent} | {downloaded}/{total_size} | Speed: {speed} | ETA: {eta}")
        sys.stdout.flush()
    elif data["status"] == "finished" and not download_completed_shown:
        download_completed_shown = True
        filepath = data.get("filepath", "Unknown")
        time.sleep(0.5)
        if filepath and filepath != "Unknown" and Path(filepath).exists():
            path = Path(filepath).absolute()
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
            except OSError:
                size_mb = 0
            print("\n" + "═" * 55)
            print("            ✅ DOWNLOAD COMPLETED")
            print("═" * 55)
            print(f"📄 File name: {path.name}")
            print(f"📂 Location: {path.parent}")
            print(f"💾 File size: {size_mb:.2f} MB")
            print(f"⏰ Completed at: {time.strftime('%H:%M:%S')}")
            print("═" * 55 + "\n")
        else:
            print("\n✅ Download completed successfully\n")


def get_url_info(url):
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        return parse_info(info)
    except Exception as error:
        error_message = str(error)
        if "Sign in to confirm" not in error_message and "bot" not in error_message:
            print_error(f"Could not fetch info: {error}", "Check your internet connection and URL.")
            return None
        print_warning("Info fetch blocked. Trying browser cookies.")

    cookie_option = get_browser_cookie_option()
    if not cookie_option:
        print_error("No working browser cookies.")
        return None
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "cookiesfrombrowser": cookie_option}) as ydl:
            info = ydl.extract_info(url, download=False)
        return parse_info(info)
    except Exception as error:
        print_error(f"Could not fetch info with cookies: {error}")
        return None


def parse_info(info):
    if not isinstance(info, dict):
        raise ValueError("YouTube returned an unexpected response.")
    if "entries" in info:
        entries = [entry for entry in info["entries"] if entry]
        return {
            "type": "playlist",
            "title": info.get("title", "Unknown Playlist"),
            "uploader": info.get("uploader", "Unknown"),
            "video_count": len(entries),
            "videos": [entry.get("title", f"Video {index + 1}") for index, entry in enumerate(entries[:5])],
            "full_info": info,
        }
    return {
        "type": "video",
        "title": info.get("title", "Unknown"),
        "duration": info.get("duration", 0),
        "uploader": info.get("uploader", "Unknown"),
        "view_count": info.get("view_count", 0),
        "upload_date": info.get("upload_date", ""),
    }


def display_video_info(info):
    print("\n" + "─" * 61)
    print("📹 VIDEO INFORMATION")
    print("─" * 61)
    print(f"📺 Title: {info['title']}")
    print(f"👤 Channel: {info['uploader']}")
    print(f"⏱️ Duration: {format_duration(info['duration'])}")
    print(f"👀 Views: {format_view_count(info['view_count'])}")
    upload_date = info.get("upload_date")
    if upload_date and len(upload_date) >= 8:
        print(f"📅 Upload date: {upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}")
    print("─" * 61)


def display_playlist_info(info):
    print("\n" + "─" * 61)
    print("📂 PLAYLIST INFORMATION")
    print("─" * 61)
    print(f"📺 Playlist: {info['title']}")
    print(f"👤 Channel: {info['uploader']}")
    print(f"🎬 Total Videos: {info['video_count']}")
    print("\n📹 First few videos:")
    for index, title in enumerate(info["videos"], 1):
        print(f"  {index}. {title[:50]}")
    print("─" * 61)


def download_playlist(playlist_info, mode, config):
    full_info = playlist_info.get("full_info")
    if not full_info or "entries" not in full_info:
        print_error("Playlist information is missing or invalid.")
        return

    entries = [entry for entry in full_info["entries"] if entry]
    total = len(entries)
    if total == 0:
        print_error("Playlist has no downloadable videos.")
        return
    print_success(f"Found {total} videos in playlist")
    if not confirm(f"\n🚀 Download all {total} videos?"):
        return

    playlist_title = re.sub(r'[<>:"/\\|?*]', "_", full_info.get("title", "Playlist"))
    playlist_folder = Path(config["download_dir"]) / playlist_title
    try:
        playlist_folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print_error(f"Could not create playlist folder: {error}")
        return

    success_count = 0
    failed_videos = []
    for index, entry in enumerate(entries, 1):
        video_id = entry.get("id")
        if not video_id:
            failed_videos.append(("", entry.get("title", f"Video {index}"), "Missing video ID"))
            continue
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_title = entry.get("title", f"Video {index}")
        print(f"\n{'─' * 61}")
        print_info(f"[{index}/{total}] Downloading: {video_title[:50]}")
        success, error = download_single_video(video_url, str(playlist_folder), mode, config)
        if success:
            success_count += 1
            print_success(f"[{index}/{total}] Completed: {video_title[:50]}")
            log_download("YouTube", video_title, mode=mode, status="Success")
        else:
            failed_videos.append((video_url, video_title, error or "Unknown error"))
            print_error(f"[{index}/{total}] Failed: {video_title[:50]} - {(error or 'Unknown error')[:100]}")
            log_download("YouTube", video_title, mode=mode, status="Failed", error=error or "")
        time.sleep(0.5)

    print("\n" + "═" * 61)
    print_success(f"Playlist download finished: {success_count} successful, {len(failed_videos)} failed")
    if failed_videos:
        fail_log = playlist_folder / "_failed_videos.txt"
        try:
            with open(fail_log, "w", encoding="utf-8") as file:
                for url, title, error in failed_videos:
                    file.write(f"{url} | {title} | {error}\n")
            print_info(f"Failed URLs saved to: {fail_log}")
        except OSError as error:
            print_error(f"Could not save failed URL log: {error}")
    print("═" * 61)


def download_content(url, mode, config):
    start_spinner("🎬 Fetching video/playlist information")
    info = get_url_info(url)
    stop_spinner()
    if not info:
        return

    if info["type"] == "playlist":
        display_playlist_info(info)
        download_playlist(info, mode, config)
        return

    display_video_info(info)
    if not confirm("\n🚀 Download this video?"):
        print_info("Download cancelled")
        return
    success, error = download_single_video(url, config["download_dir"], mode, config)
    if success:
        print_success("Download completed!")
        log_download("YouTube", info["title"], mode=mode, status="Success")
    else:
        print_error(f"Download failed: {error}")
        log_download("YouTube", info["title"], mode=mode, status="Failed", error=error or "")


def run_manual_format(config):
    while True:
        url = input("\n🎯 YouTube URL (blank to go back): ").strip()
        if not url:
            return
        if not is_youtube_url(url):
            print_error("Not a valid YouTube URL", "URL should start with http(s) and contain youtube.com or youtu.be.")
            continue
        try:
            print_info("Fetching available formats...")
            with YoutubeDL({"quiet": True, "listformats": True}) as ydl:
                ydl.extract_info(url, download=False)
            format_id = input("🎯 Enter format ID: ").strip()
            if not format_id:
                print_error("No format ID provided", "Enter one of the listed format IDs.")
                continue
            options = build_download_options(config["download_dir"], "1", config)
            options["format"] = format_id
            start_spinner("Downloading custom format")
            with YoutubeDL(options) as ydl:
                ydl.download([url])
            stop_spinner()
            print_success("Download completed!")
            log_download("YouTube", url, mode="Manual Format", status="Success")
        except Exception as error:
            stop_spinner()
            print_error(f"Manual download failed: {error}", "Check the URL, format ID, and network connection.")
        if not confirm("\nDownload another manual format?"):
            return


def run_standard_downloads(mode, config):
    while True:
        url = input("\n🎯 YouTube URL (video or playlist, blank to go back): ").strip()
        if not url:
            return
        if is_youtube_url(url):
            download_content(url, mode, config)
        else:
            print_error("Not a valid YouTube URL", "URL should start with http(s) and contain youtube.com or youtu.be.")
        if not confirm("\nDownload another?"):
            return


def run(config):
    while True:
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
        mode = menu_choice("Select (1-4): ", "1234")
        if mode in (None, "4"):
            return
        try:
            if mode == "3":
                run_manual_format(config)
            else:
                run_standard_downloads(mode, config)
        except Exception as error:
            stop_spinner()
            print_error(f"YouTube workflow error: {error}", "You remain in the YouTube Downloader.")
            pause()
