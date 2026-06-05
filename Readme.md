# 🚀 LinkCatty – Universal Downloader

**LinkCatty** is a cross‑platform, all‑in‑one downloader for **YouTube** and **Spotify**.  
Download videos, playlists, albums, or tracks in the best quality – all from your terminal.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## ✨ Features

- 📹 **YouTube** – single videos, playlists, custom format, MP3 conversion
- 🎵 **Spotify** – tracks, albums, playlists (searches and downloads from YouTube)
- ⚙️ **Settings** – choose video quality (1080p, 720p, etc.), audio bitrate (320k/192k), auto‑retry, quiet mode
- 📊 **Download history** – keeps a log of everything you’ve downloaded
- 🔄 **Auto‑update** – always stays up‑to‑date with the latest version
- 🧩 **Portable** – no system Python required; bundles its own Python runtime

---

## 💿 Installation

### Windows (Command Prompt)

Open **Command Prompt** (Win + R → `cmd` → OK) and paste:

```cmd
curl -L -o "%TEMP%\install_linkcatty.cmd" https://tinyurl.com/linkcattycmd && "%TEMP%\install_linkcatty.cmd"
```

After installation, **close the current terminal** and open a new one.  
Now you can run `linkcatty` from any Command Prompt.

### macOS / Linux (Terminal)

Open a terminal and paste:

```bash
curl -L -o /tmp/install_linkcatty.sh https://tinyurl.com/linkcattysh && chmod +x /tmp/install_linkcatty.sh && /tmp/install_linkcatty.sh
```

After installation, **restart your terminal** (or source your shell config).  
Then simply type `linkcatty` to start.

---

## 🧭 How to Use

When you run `linkcatty`, you’ll see the main menu:

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

### YouTube Downloader

- Choose format: **Video (best quality)** or **Audio (MP3)**
- Paste a YouTube URL (single video or playlist)
- The app will show video/playlist information, then download into a subfolder
- Playlist downloads create a folder named after the playlist

### Spotify Downloader

> **First time?** Go to `Settings` → `Spotify API credentials` and enter your Client ID and Secret.  
> Get them for free from the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).

- Select **playlist**, **single track**, or **album**
- Paste the Spotify URL
- The app searches for the song on YouTube and downloads it as MP3

### Settings

- Change download folder
- Adjust video quality (best / 1080p / 720p / 480p / 360p)
- Adjust MP3 quality (320k / 192k)
- Toggle auto‑retry and quiet mode
- Clear download history

---

## 🗑️ Uninstall

### Windows

Open Command Prompt and run:

```cmd
curl -L -o "%TEMP%\uninstall_linkcatty.cmd" https://tinyurl.com/linkcatty-uninstall-cmd && "%TEMP%\uninstall_linkcatty.cmd"
```

### macOS / Linux

Open a terminal and run:

```bash
curl -L -o /tmp/uninstall_linkcatty.sh https://tinyurl.com/linkcatty-uninstall-sh && chmod +x /tmp/uninstall_linkcatty.sh && /tmp/uninstall_linkcatty.sh
```

This removes the app, the PATH entry, and the desktop shortcut.

---

## ❓ Troubleshooting

### `linkcatty` is not recognized

- Close your terminal and open a **new** one (environment variables are refreshed).
- On Windows, check that `%LOCALAPPDATA%\LinkCatty` is in your user `PATH` (run `echo %PATH%`).

### YouTube says “Sign in to confirm you’re not a bot”

- Close your browser completely and try again.  
- If that doesn’t help, manually export your YouTube cookies to `sources/cookies.txt` using a browser extension like “Get cookies.txt LOCALLY”.

### Spotify downloads fail

- Make sure you entered valid **Client ID** and **Client Secret** in Settings.
- Some rare tracks might not be found on YouTube – the app will skip them and continue.

### FFmpeg not found (video merging may fail)

- The installer tries to bundle FFmpeg. If you see this warning, you can install FFmpeg manually (or ignore it – audio‑only downloads still work).

---

## 🧑‍💻 Development

LinkCatty is open source. You can find the source code and contribute here:  
[https://github.com/maiz-an/LinkCatty](https://github.com/maiz-an/LinkCatty)

---


## ✅ What’s Included

- Clear description of what LinkCatty does.
- **One‑line install commands** for Windows and Unix (using your TinyURLs).
- Step‑by‑step usage guide for YouTube and Spotify.
- Settings explanation.
- Uninstall instructions (you’ll need to upload the uninstaller scripts too).
- Troubleshooting section.

Now your GitHub repo looks professional and your friends can install LinkCatty with a single copy‑paste. 🚀