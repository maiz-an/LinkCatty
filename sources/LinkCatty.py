#!/usr/bin/env python3
"""
LinkCatty - Unified Downloader for YouTube, Spotify and more.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_ROOT = BASE_DIR.parent          # app root (works in dev + installed)
sys.path.insert(0, str(BASE_DIR))

from downloaders import spotify_downloader, youtube_downloader, other_downloader
from utils.config import (
    get_proxy,
    is_valid_proxy,
    load_config,
    mask_proxy,
    reset_to_defaults,
    save_config,
)
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

_HINT = "Press Enter to keep the current value, or type a number to change it."
_HINT2 = "Type 0 at any prompt to cancel — no changes will be saved."


# ─────────────────────────────────────────────────────────────────────
#  Settings menu
# ─────────────────────────────────────────────────────────────────────

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
            print("7. Network proxy (Other Downloaders)")
            print("8. Back to main menu")
            print("=" * 61)
            choice = menu_choice("Select (1-8): ", "12345678")

            if choice in (None, "8"):
                return

            if choice == "1":
                new_dir = input("New download folder (absolute path, Enter to keep): ").strip()
                if not new_dir:
                    print_info("Download folder unchanged.")
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
                client_id = input("Client ID (Enter to keep): ").strip()
                client_secret = input("Client Secret (Enter to keep): ").strip()
                changed = False
                if client_id:
                    config["spotify"]["client_id"] = client_id
                    changed = True
                if client_secret:
                    config["spotify"]["client_secret"] = client_secret
                    changed = True
                if changed:
                    save_config(config)
                    print_success("Credentials saved.")
                else:
                    print_info("Credentials unchanged.")

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
                    "never touched. Spotify API credentials and the "
                    "network proxy are preserved."
                )
                if not confirm("Restore all settings to defaults?", default=False):
                    print_info("Cancelled.")
                else:
                    fresh = reset_to_defaults()
                    config.clear()
                    config.update(fresh)
                    print_success("Settings restored to defaults.")
                    print_info("Note: some changes take effect next time you "
                               "start a download.")

            elif choice == "7":
                network_settings(config)

        except Exception as error:
            print_error(
                f"Settings error: {error}",
                "Correct the value and try again. You remain in Settings.",
            )

        pause()


# ─────────────────────────────────────────────────────────────────────
#  Network proxy settings (Other Downloaders)
# ─────────────────────────────────────────────────────────────────────

def network_settings(config):
    print("\n🌐 Network Proxy (Other Downloaders)")
    print_info("Used only when a direct connection is blocked. If the "
               "direct connection works, no proxy is used.")
    print_info("Examples: socks5://127.0.0.1:1080   http://127.0.0.1:8080")
    print_info("Enter = keep current, - = turn OFF (remove), 0 = cancel.")
    current = get_proxy(config)
    if current:
        print(f"\nProxy status: ON  ({mask_proxy(current)})")
    else:
        print("\nProxy status: OFF (default). Enter a proxy URL below to turn it ON.")

    value = input("Proxy URL: ").strip()
    if value in ("", "0"):
        print_info("Proxy unchanged.")
        return

    network = config.setdefault("network", {})
    if value == "-":
        network["proxy"] = ""
        save_config(config)
        print_success("Proxy removed. Status: OFF.")
        return

    if not is_valid_proxy(value):
        print_error(
            "Invalid proxy URL.",
            "Use a full URL starting with http://, https://, socks4:// "
            "or socks5://, e.g. socks5://127.0.0.1:1080",
        )
        return

    network["proxy"] = value
    save_config(config)
    print_success(f"Proxy saved: {mask_proxy(value)}. Status: ON.")


# ─────────────────────────────────────────────────────────────────────
#  YouTube settings
# ─────────────────────────────────────────────────────────────────────

def youtube_settings(config):
    youtube = config["youtube"]
    print("\n▶️  YouTube Settings")
    print_info(_HINT)
    print_info(_HINT2)
    print()

    # Stage changes in a draft so 0 = truly non-destructive.
    draft = dict(youtube)

    # ── audio quality ─────────────────────────────────────────────
    current = draft.get("audio_quality", "320k")
    print(f"Audio quality for MP3 (current: {current})")
    print("1. 320k")
    print("2. 192k")
    choice = menu_choice(
        "Select (1-2) [Enter=keep, 0=cancel]: ",
        "12", back_choices={"0"}, allow_empty=True,
    )
    if choice is None or choice == "0":
        print_info("Cancelled — no changes saved.")
        return
    if choice != "":
        draft["audio_quality"] = "320k" if choice == "1" else "192k"

    # ── video quality ─────────────────────────────────────────────
    current = draft.get("video_quality", "best")
    print(f"\nVideo quality (current: {current})")
    print("1. Best (highest MP4)")
    print("2. 1080p")
    print("3. 720p")
    print("4. 480p")
    print("5. 360p")
    quality_map = {"1": "best", "2": "1080p", "3": "720p", "4": "480p", "5": "360p"}
    choice = menu_choice(
        "Select (1-5) [Enter=keep, 0=cancel]: ",
        "12345", back_choices={"0"}, allow_empty=True,
    )
    if choice is None or choice == "0":
        print_info("Cancelled — no changes saved.")
        return
    if choice != "":
        draft["video_quality"] = quality_map[choice]

    # ── auto-retry ────────────────────────────────────────────────
    current = draft.get("auto_retry", True)
    print(f"\nAuto-retry failed downloads? (current: {'yes' if current else 'no'})")
    print("1. Yes")
    print("2. No")
    choice = menu_choice(
        "Select (1-2) [Enter=keep, 0=cancel]: ",
        "12", back_choices={"0"}, allow_empty=True,
    )
    if choice is None or choice == "0":
        print_info("Cancelled — no changes saved.")
        return
    if choice != "":
        draft["auto_retry"] = (choice == "1")

    # ── quiet mode ────────────────────────────────────────────────
    current = draft.get("quiet_mode", True)
    print(f"\nQuiet mode (less output)? (current: {'yes' if current else 'no'})")
    print("1. Yes")
    print("2. No")
    choice = menu_choice(
        "Select (1-2) [Enter=keep, 0=cancel]: ",
        "12", back_choices={"0"}, allow_empty=True,
    )
    if choice is None or choice == "0":
        print_info("Cancelled — no changes saved.")
        return
    if choice != "":
        draft["quiet_mode"] = (choice == "1")

    # ── commit ────────────────────────────────────────────────────
    youtube.clear()
    youtube.update(draft)
    save_config(config)
    print_success("YouTube settings saved.")


# ─────────────────────────────────────────────────────────────────────
#  Spotify settings
# ─────────────────────────────────────────────────────────────────────

def spotify_settings(config):
    spotify = config["spotify"]
    print("\n🎧 Spotify Settings")
    print_info(_HINT)
    print_info(_HINT2)
    print()

    draft = dict(spotify)

    # ── audio format ──────────────────────────────────────────────
    current = draft.get("audio_format", "mp3")
    print(f"Audio format (current: {current})")
    print("1. MP3   (compressed, small size, universal)")
    print("2. FLAC  (lossless, full original quality, larger files)")
    print("3. M4A   (compressed, Apple-friendly)")
    print("4. OPUS  (compressed, best quality-per-KB)")
    print("5. OGG   (compressed, open format)")
    print("6. WAV   (uncompressed, largest files)")
    format_map = {"1": "mp3", "2": "flac", "3": "m4a",
                  "4": "opus", "5": "ogg", "6": "wav"}
    choice = menu_choice(
        "Select (1-6) [Enter=keep, 0=cancel]: ",
        "123456", back_choices={"0"}, allow_empty=True,
    )
    if choice is None or choice == "0":
        print_info("Cancelled — no changes saved.")
        return
    if choice != "":
        draft["audio_format"] = format_map[choice]

    # ── audio quality (skipped for lossless formats) ──────────────
    if draft["audio_format"] in ("flac", "wav"):
        print_info(
            f"{draft['audio_format'].upper()} is lossless — bitrate setting "
            f"is ignored."
        )
    else:
        current = draft.get("audio_quality", "320k")
        print(f"\nAudio quality (current: {current})")
        print("1. 320k")
        print("2. 192k")
        choice = menu_choice(
            "Select (1-2) [Enter=keep, 0=cancel]: ",
            "12", back_choices={"0"}, allow_empty=True,
        )
        if choice is None or choice == "0":
            print_info("Cancelled — no changes saved.")
            return
        if choice != "":
            draft["audio_quality"] = "320k" if choice == "1" else "192k"

    # ── auto-retry ────────────────────────────────────────────────
    current = draft.get("auto_retry", True)
    print(f"\nAuto-retry failed downloads? (current: {'yes' if current else 'no'})")
    print("1. Yes")
    print("2. No")
    choice = menu_choice(
        "Select (1-2) [Enter=keep, 0=cancel]: ",
        "12", back_choices={"0"}, allow_empty=True,
    )
    if choice is None or choice == "0":
        print_info("Cancelled — no changes saved.")
        return
    if choice != "":
        draft["auto_retry"] = (choice == "1")

    # ── quiet mode ────────────────────────────────────────────────
    current = draft.get("quiet_mode", True)
    print(f"\nQuiet mode? (current: {'yes' if current else 'no'})")
    print("1. Yes")
    print("2. No")
    choice = menu_choice(
        "Select (1-2) [Enter=keep, 0=cancel]: ",
        "12", back_choices={"0"}, allow_empty=True,
    )
    if choice is None or choice == "0":
        print_info("Cancelled — no changes saved.")
        return
    if choice != "":
        draft["quiet_mode"] = (choice == "1")

    # ── commit ────────────────────────────────────────────────────
    spotify.clear()
    spotify.update(draft)
    save_config(config)
    print_success("Spotify settings saved.")


# ─────────────────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────────────────

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
                other_downloader.run(config)
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