<!-- Banner / Logo (optional) -->
<p align="center">
  <img src="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/assets/logo.png" alt="LinkCatty Logo" width="200"/>
</p>

<h1 align="center">🚀 LinkCatty – Universal Downloader</h1>

<p align="center">
  <strong>Download YouTube videos, playlists, and Spotify tracks – all from your terminal.</strong><br>
  Cross‑platform · Portable · Auto‑update · Open Source
</p>

<p align="center">
  <a href="#-installation"><img src="https://img.shields.io/badge/Install-1‑click-8b5cf6?style=for-the-badge&logo=windows&logoColor=white"></a>
  <a href="#-uninstall"><img src="https://img.shields.io/badge/Uninstall-clean-ef4444?style=for-the-badge&logo=windows&logoColor=white"></a>
  <a href="https://github.com/maiz-an/LinkCatty"><img src="https://img.shields.io/badge/GitHub-Repo-181717?style=for-the-badge&logo=github&logoColor=white"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue?style=flat-square">
  <img src="https://img.shields.io/badge/Python-3.12+-green?style=flat-square">
  <img src="https://img.shields.io/badge/License-MIT-orange?style=flat-square">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square">
</p>

---

## ✨ Features

| Area | Description |
|------|-------------|
| 📹 **YouTube** | Single videos, playlists, custom format selection, MP3 conversion. Choose quality up to 1080p / 720p / best available. |
| 🎵 **Spotify** | Tracks, albums, playlists – searches for the song on YouTube and downloads as high‑quality MP3 (320k or 192k). |
| ⚙️ **Settings** | Download folder, video quality, audio bitrate, auto‑retry, quiet mode, download history. |
| 🔄 **Auto‑update** | Automatically checks for new versions and updates itself – always up‑to‑date. |
| 🧩 **Portable** | No system Python required. Bundles its own Python runtime. |
| 🔐 **Privacy‑first** | Open‑source, no tracking, no data collection. Everything runs locally. |

---

## 💿 Installation

### 📌 One‑line install (no admin rights needed)

| Platform | Command |
|----------|---------|
| **Windows (CMD)** | `curl -L -o "%TEMP%\install_linkcatty.cmd" https://tinyurl.com/linkcattycmd && "%TEMP%\install_linkcatty.cmd"` |
| **macOS / Linux** | `curl -L -o /tmp/install_linkcatty.sh https://tinyurl.com/linkcattysh && chmod +x /tmp/install_linkcatty.sh && /tmp/install_linkcatty.sh` |

> After installation: **close and reopen your terminal** – then simply type `linkcatty` to launch.

### 📦 What the installer does

- Downloads the latest version from GitHub
- Installs everything to `%LOCALAPPDATA%\LinkCatty` (Windows) or `~/.local/share/LinkCatty` (Unix)
- Adds the folder to your **user PATH** (persistent)
- Creates a **Start Menu / desktop shortcut**
- Bundles FFmpeg (Windows x64, macOS Intel/ARM, Linux x64/ARM64)

---

## 🧭 How to Use

Run `linkcatty` – you’ll see the main menu:

```
=============================================================
                      🎯 MAIN MENU
=============================================================
1. 📹 YouTube Downloader
2. 🎵 Spotify Downloader
3. 🛠️  Other (coming soon)
4. ⚙️  Settings
5. ❌ Exit
=============================================================
```
### 🎬 YouTube Downloader

- Choose **Video (best quality)** or **Audio (MP3)**
- Paste a YouTube URL (single video or playlist)
- The app shows video/playlist information, then downloads into a subfolder
- Playlist downloads create a folder named after the playlist

### 🎵 Spotify Downloader

- Select **playlist**, **single track**, or **album**
- Paste the Spotify URL
- The app searches for the song on YouTube and downloads it as MP3

### ⚙️ Settings

- Change download folder
- Adjust video quality (best / 1080p / 720p / 480p / 360p)
- Adjust MP3 quality (320k / 192k)
- Toggle auto‑retry and quiet mode
- (Optionally) enter Spotify Client ID / Secret for better folder naming
- Clear download history

---

## 🗑️ Uninstall

Remove LinkCatty completely (installation folder, PATH entry, and shortcuts):

| Platform | Command |
|----------|---------|
| **Windows** | `curl -L -o "%TEMP%\uninstall_linkcatty.cmd" https://tinyurl.com/linkcatty-uninstall-cmd && "%TEMP%\uninstall_linkcatty.cmd"` |
| **macOS / Linux** | `curl -L -o /tmp/uninstall_linkcatty.sh https://tinyurl.com/linkcatty-uninstall-sh && chmod +x /tmp/uninstall_linkcatty.sh && /tmp/uninstall_linkcatty.sh` |

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| `linkcatty` not recognized | Close and reopen your terminal. On Windows, check `%LOCALAPPDATA%\LinkCatty` is in your `PATH`. |
| YouTube “Sign in to confirm you’re not a bot” | Close your browser completely and retry. If still fails, export YouTube cookies to `sources/cookies.txt` (use “Get cookies.txt LOCALLY” extension). |
| FFmpeg not found (video merging may fail) | The installer bundles FFmpeg. If you see this warning, you can install FFmpeg manually (audio‑only downloads still work). |

---

## 🧑‍💻 Development & Contribution

LinkCatty is open source and welcomes contributions.

```bash
git clone https://github.com/maiz-an/LinkCatty.git
cd LinkCatty
# Use the portable Python environment, or install dependencies manually:
pip install -r sources/requirements.txt
```

- **Issues / Feature requests**: [GitHub Issues](https://github.com/maiz-an/LinkCatty/issues)
- **Pull requests**: Always welcome

---

<p align="center">
  <sub>Made with ❤️ for the open‑source community</sub>
</p>