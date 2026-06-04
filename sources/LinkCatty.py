#!/usr/bin/env python3
"""
LinkCatty - Unified Downloader for YouTube, Spotify and more.
Now located inside the 'sources' folder.
"""
import sys
import os
from pathlib import Path

# Add the parent directory (root) to sys.path so we can import from sources
# But since we are already inside sources, we can import directly from downloaders and utils
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent  # the root folder (where run.bat lives)

# Add root to sys.path for any root-level modules (none currently)
sys.path.insert(0, str(BASE_DIR))

# Import our modules
from utils.config import load_config, save_config
from utils.ui import clear_screen, print_banner, print_main_menu
from downloaders import youtube_downloader, spotify_downloader

# ----------------------------------------------------------------------
# Settings Menu
# ----------------------------------------------------------------------
def settings_menu(config):
    from utils.ui import clear_screen, print_banner
    from utils.logger import clear_history

    while True:
        clear_screen()
        print_banner()
        print("\n" + "═" * 55)
        print("            ⚙️  SETTINGS")
        print("═" * 55)
        print(f"1. 📂 Download folder   [{config['download_dir']}]")
        print("2. 🎬 YouTube settings")
        print("3. 🎧 Spotify settings")
        print("4. 🔑 Spotify API credentials")
        print("5. 🧹 Clear download history")
        print("6. ↩️  Back to main menu")
        print("═" * 55)
        choice = input("Select (1-6): ").strip()

        if choice == "1":
            new_dir = input("New download folder (absolute path): ").strip()
            if new_dir:
                p = Path(new_dir).expanduser().resolve()
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    config['download_dir'] = str(p)
                    save_config(config)
                    print(f"✅ Folder changed to: {p}")
                except Exception as e:
                    print(f"❌ Error: {e}")

        elif choice == "2":
            yt = config['youtube']
            print(f"\n▶️  YouTube Settings")
            print(f"Audio quality [{yt['audio_quality']}]: 1. 320k  2. 192k")
            q = input("Choice (1/2): ")
            if q == '1':
                yt['audio_quality'] = '320k'
            elif q == '2':
                yt['audio_quality'] = '192k'
            yt['auto_retry'] = input("Auto-retry failed downloads? (y/n): ").lower() == 'y'
            yt['quiet_mode'] = input("Quiet mode (less output)? (y/n): ").lower() == 'y'
            save_config(config)
            print("✅ YouTube settings saved.")

        elif choice == "3":
            sp = config['spotify']
            print(f"\n🎧 Spotify Settings")
            print(f"Audio quality [{sp['audio_quality']}]: 1. 320k  2. 192k")
            q = input("Choice (1/2): ")
            if q == '1':
                sp['audio_quality'] = '320k'
            elif q == '2':
                sp['audio_quality'] = '192k'
            sp['auto_retry'] = input("Auto-retry failed downloads? (y/n): ").lower() == 'y'
            sp['quiet_mode'] = input("Quiet mode? (y/n): ").lower() == 'y'
            save_config(config)
            print("✅ Spotify settings saved.")

        elif choice == "4":
            print("\n🔑 Spotify API Credentials")
            print("Get them from: https://developer.spotify.com/dashboard/")
            new_id = input("Client ID: ").strip()
            new_secret = input("Client Secret: ").strip()
            if new_id and new_secret:
                config['spotify']['client_id'] = new_id
                config['spotify']['client_secret'] = new_secret
                save_config(config)
                print("✅ Credentials saved.")
            else:
                print("❌ Both ID and Secret are required.")

        elif choice == "5":
            confirm = input("Are you sure you want to clear all download history? (y/n): ").lower()
            if confirm == 'y':
                clear_history()
                print("✅ History cleared.")
            else:
                print("Cancelled.")

        elif choice == "6":
            break

        input("\nPress Enter to continue...")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    config = load_config()
    # Ensure download directory exists
    Path(config['download_dir']).mkdir(parents=True, exist_ok=True)

    while True:
        clear_screen()
        print_banner()
        print_main_menu()
        choice = input("Select option (1-5): ").strip()

        if choice == "1":
            youtube_downloader.run(config)
        elif choice == "2":
            spotify_downloader.run(config)
        elif choice == "3":
            print("\n🛠️  Other downloaders (e.g., SoundCloud, Vimeo) coming soon.")
            input("Press Enter to continue...")
        elif choice == "4":
            settings_menu(config)
        elif choice == "5":
            print("\n👋 Thanks for using LinkCatty! Goodbye.")
            break
        else:
            print("❌ Invalid choice. Please enter 1-5.")
            input("Press Enter...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        input("Press Enter to exit...")