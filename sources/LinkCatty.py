#!/usr/bin/env python3
"""
LinkCatty - Unified Downloader for YouTube, Spotify and more.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_ROOT = BASE_DIR.parent          # app root (works in dev + installed)
sys.path.insert(0, str(BASE_DIR))

from downloaders import spotify_downloader, youtube_downloader
from utils.config import load_config, save_config, reset_to_defaults
from utils.ui import (
    clear_screen,
    confirm,
    menu_choice,
    pause,
    print_banner,
    print_error,
    print_info,
    print_main_menu,
    print_success,
    print_warning,
    set_console_width,
)

set_console_width(62)


def settings_menu(config):
    from utils.logger import clear_history

    while True:
        try:
            clear_screen()
            print_banner()
            print("                        ⚙️  SETTINGS")
            print("=" * 61)
            print(f"📍 Install location : {APP_ROOT}")
            print(f"📂 Download folder  : {config['download_dir']}")
            print("=" * 61)
            print("1. Change download folder")
            print("2. YouTube settings")
            print("3. Spotify settings")
            print("4. Spotify API credentials")
            print("5. Clear download history")
            print("6. Restore all settings to defaults")
            print("7. Back to main menu")
            print("=" * 61)
            choice = menu_choice("Select (1-7): ", "1234567")

            if choice in (None, "7"):
                return

            if choice == "1":
                new_dir = input("New download folder (absolute path): ").strip()
                if not new_dir:
                    print_error("Download folder was not changed",
                                "Enter a full folder path or choose Back.")
                else:
                    path = Path(new_dir).expanduser().resolve()
                    path.mkdir(parents=True, exist_ok=True)
                    config["download_dir"] = str(path)
                    save_config(config)
                    print_success(f"Folder changed to: {path}")

            elif choice == "2":
                youtube_settings(config)

            elif choice == "3":
                spotify_settings(config)

            elif choice == "4":
                print("\n🔑 Spotify API Credentials")
                print("Get them from: https://developer.spotify.com/dashboard/")
                client_id = input("Client ID: ").strip()
                client_secret = input("Client Secret: ").strip()
                if client_id and client_secret:
                    config["spotify"]["client_id"] = client_id
                    config["spotify"]["client_secret"] = client_secret
                    save_config(config)
                    print_success("Credentials saved.")
                else:
                    print_error("Both Client ID and Client Secret are required.")

            elif choice == "5":
                if confirm("Clear all download history?"):
                    clear_history()
                    print_success("History cleared.")
                else:
                    print_info("Cancelled.")

            elif choice == "6":
                print()
                print_warning(
                    "This will reset download folder, YouTube, and Spotify "
                    "settings to their factory defaults."
                )
                print_warning(
                    "Your downloaded files and the install location are "
                    "never touched. Spotify API credentials are preserved."
                )
                if not confirm("Restore all settings to defaults?", default=False):
                    print_info("Cancelled.")
                else:
                    fresh = reset_to_defaults()
                    # Swap in place so the running session picks up the
                    # new values immediately (no restart needed).
                    config.clear()
                    config.update(fresh)
                    print_success("Settings restored to defaults.")
                    print_info("Note: some changes take effect next time you "
                               "start a download.")

        except Exception as error:
            print_error(
                f"Settings error: {error}",
                "Correct the value and try again. You remain in Settings.",
            )

        pause()


def youtube_settings(config):
    youtube = config["youtube"]
    print("\n▶️  YouTube Settings")
    print(f"Audio quality (for MP3) [{youtube['audio_quality']}]: 1. 320k  2. 192k")
    audio_choice = menu_choice("Choice (1/2): ", "12")
    youtube["audio_quality"] = "320k" if audio_choice == "1" else "192k"

    print(f"\nVideo quality (current: {youtube['video_quality']})")
    print("1. Best (highest MP4)")
    print("2. 1080p")
    print("3. 720p")
    print("4. 480p")
    print("5. 360p")
    quality_map = {"1": "best", "2": "1080p", "3": "720p", "4": "480p", "5": "360p"}
    youtube["video_quality"] = quality_map[menu_choice("Select (1-5): ", "12345")]
    youtube["auto_retry"] = confirm("Auto-retry failed downloads?", youtube.get("auto_retry", True))
    youtube["quiet_mode"] = confirm("Quiet mode (less output)?", youtube.get("quiet_mode", True))
    save_config(config)
    print_success("YouTube settings saved.")


def spotify_settings(config):
    spotify = config["spotify"]
    print("\n🎧 Spotify Settings")

    print(f"\nAudio format (current: {spotify.get('audio_format', 'mp3')})")
    print("1. MP3   (compressed, small size, universal)")
    print("2. FLAC  (lossless, full original quality, larger files)")
    print("3. M4A   (compressed, Apple-friendly)")
    print("4. OPUS  (compressed, best quality-per-KB)")
    print("5. OGG   (compressed, open format)")
    print("6. WAV   (uncompressed, largest files)")
    format_map = {"1": "mp3", "2": "flac", "3": "m4a", "4": "opus", "5": "ogg", "6": "wav"}
    format_choice = menu_choice("Select (1-6): ", "123456")
    spotify["audio_format"] = format_map[format_choice]

    if spotify["audio_format"] in ("flac", "wav"):
        print_info(f"{spotify['audio_format'].upper()} is lossless — the bitrate setting below is ignored.")
    else:
        print(f"\nAudio quality [{spotify['audio_quality']}]: 1. 320k  2. 192k")
        audio_choice = menu_choice("Choice (1/2): ", "12")
        spotify["audio_quality"] = "320k" if audio_choice == "1" else "192k"

    spotify["auto_retry"] = confirm("Auto-retry failed downloads?", spotify.get("auto_retry", True))
    spotify["quiet_mode"] = confirm("Quiet mode?", spotify.get("quiet_mode", True))
    save_config(config)
    print_success("Spotify settings saved.")


def main():
    config = load_config()
    try:
        Path(config["download_dir"]).mkdir(parents=True, exist_ok=True)
    except Exception as error:
        print_error(f"Could not create download folder: {error}",
                    "Choose a writable folder in Settings.")
        pause()

    while True:
        clear_screen()
        print_banner()
        print_main_menu()
        choice = menu_choice("Select option (1-5): ", "12345")

        try:
            if choice == "1":
                youtube_downloader.run(config)
            elif choice == "2":
                spotify_downloader.run(config)
            elif choice == "3":
                print("\n🛠️  Other downloaders (e.g., SoundCloud, Vimeo) coming soon.")
                pause("Press Enter to continue...")
            elif choice == "4":
                settings_menu(config)
            elif choice in (None, "5"):
                print("\n👋 Thanks for using LinkCatty! Goodbye.")
                return
        except Exception as error:
            print_error(
                f"Workflow error: {error}",
                "This section recovered without closing the application.",
            )
            pause("Press Enter...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user. Goodbye!")
    except Exception as error:
        print_error(f"Unexpected error: {error}")
        pause("Press Enter to exit...")