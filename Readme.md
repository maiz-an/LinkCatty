
<!-- Banner / Logo (optional) -->
<p align="center">
  <img src="https://linkcatty.vercel.app/linkcatty.svg" alt="LinkCatty Logo" width="160"/>
</p>

<h1 align="center">🚀 LinkCatty – Universal Downloader</h1>

<p align="center">
  <strong>Download YouTube videos and playlists, Spotify tracks and albums, and videos from 1000+ other sites – all from your terminal.</strong><br>
  Cross‑platform · Portable · Auto‑update · Fast parallel downloads · Resumable · Open Source
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
| 📹 **YouTube** | Single videos, playlists, channels, custom format selection, MP3 conversion. Quality up to 4K / 1080p / 720p / best available. Video + auto‑mix links download just the video; channel links download the uploads. |
| 🎵 **Spotify** | Tracks, albums, playlists. Downloads as MP3 (320k / 192k), FLAC, M4A, OPUS, OGG, or WAV. |
| 🌐 **Other Downloaders** | Paste a link from almost any other site that `yt-dlp` supports (1000+). Video quality comes from Settings; playlists get a folder, a resumable ledger and a failed‑items report. |
| 🎨 **One clean look** | All three downloaders share the same minimal UI: header, info card, one live progress bar, and a result card. No walls of scrolling text. |
| 🔁 **Silent auto‑retry** | Failed items are retried in the background with more patience each time. You never see "pass 1/3" or retry noise – only finished items and, at the end, what could not be downloaded and why. |
| 🧠 **Smart failure handling** | Errors are classified (removed/private, login needed, blocked network, rate limit, timeout…). Hopeless ones are not retried, temporary ones are, and the result card lists the causes. |
| 💾 **Resumable** | A per‑folder ledger (`.linkcatty_state.json`) records every attempt. Re‑running a playlist only downloads what's still missing. |
| 🌍 **Blocked network friendly** | Other Downloaders try a direct connection first and use your optional proxy only when it is blocked. If your network cuts the connection, LinkCatty asks you to turn on a VPN and retries on Enter. |
| 🚦 **Rate‑limit aware** | Automatic cooldowns and fewer parallel workers when a site throttles; Spotify switches to non‑YouTube providers when needed. |
| ⚡ **Parallel downloads** | 3 parallel workers for YouTube playlists, 3 batches × 2 threads for Spotify. |
| 📝 **Tags inside the file** | Title, artist and more are embedded in the file itself. No extra thumbnail or `.info.json` files are left next to your downloads (you can turn them on in `settings.json`). |
| 📂 **Easy folder** | Everything is saved to `Downloads/LinkCatty` inside your system Downloads folder (Windows, macOS and Linux). Change it in Settings. |
| ⌨️ **Consistent keys** | `0` always goes back or cancels, a bare Enter skips or keeps the default. |
| 🔄 **Auto‑update** | Checks for new versions on every launch and updates itself in place. `linkcatty --update` forces a check. |
| 🧩 **Portable** | No system Python required on Windows. Bundles its own runtime and FFmpeg. |
| 🔐 **Privacy‑first** | Open‑source, no tracking, no data collection. Everything runs locally. |

---

## 💿 Installation

### 📌 One‑line install (no admin rights needed)

| Platform | Command |
|----------|---------|
| **Windows (CMD)** | `curl -L -o "%TEMP%\install_linkcatty.cmd" https://tinyurl.com/linkcattycmd && "%TEMP%\install_linkcatty.cmd"` |
| **macOS / Linux** | `curl -L -o /tmp/install_linkcatty.sh https://tinyurl.com/linkcattysh && chmod +x /tmp/install_linkcatty.sh && /tmp/install_linkcatty.sh` |

> After installation the installer offers to start LinkCatty right away. To launch it later, open a **new terminal window** and type `linkcatty` (on macOS/Linux you can also run `source ~/.zshrc` first, or use the full path `~/.local/share/LinkCatty/linkcatty`).

### 📦 What the installer does

- Downloads the latest version from GitHub
- Installs everything to `%LOCALAPPDATA%\LinkCatty` (Windows) or `~/.local/share/LinkCatty` (Unix)
- Adds the folder to your **user PATH** (persistent). On macOS/Linux it writes to the startup file of *your* shell (`~/.zshrc` for zsh, the macOS default) and, when possible, also links `linkcatty` into a folder that is already on your PATH so it works right away
- Downloads every file from one exact GitHub commit and installs nothing unless all files arrived; your `settings.json` and history survive a reinstall
- Creates a **Start Menu / Desktop shortcut**
- Bundles FFmpeg (Windows x64, macOS Intel/ARM, Linux x64/ARM64)
- Creates `sources/settings.json` with full defaults on first launch
- Your downloads go to `Downloads/LinkCatty` (created on first launch)

### 🧰 Commands

| Command | What it does |
|---------|--------------|
| `linkcatty` | Start the app (checks for updates first) |
| `linkcatty --update` | Force an update check right now, even if you updated a minute ago |
| `linkcatty --location` | Print the folder where LinkCatty is installed |
| `linkcatty --uninstall` | Remove LinkCatty (see [Uninstall](#-uninstall)) |

### 🔄 How updates work

On every launch LinkCatty asks GitHub for the latest commit and compares `version.txt`. When the version differs it downloads the changed files, replaces its own launcher and restarts. Your `settings.json` and download history are preserved. If a file is ever missing (for example after a partial update) the launcher repairs it automatically on the next start.

---

## 🧭 How to Use

Run `linkcatty` — you'll see the main menu:

```
                       - a Maiz's one -

=============================================================
                        🎯 MAIN MENU
                           v1.0.34
=============================================================

1. YouTube Downloader
2. Spotify Downloader
3. Other Downloaders
4. Settings
0. Exit

=============================================================
```

**Keys everywhere:** type a number to choose. `0` goes back (or exits from the main menu), a bare Enter skips or keeps the default, and `Ctrl+C` acts like back. URL prompts accept `0` or an empty line to go back.

Every download follows the same flow:

1. Paste the link
2. LinkCatty fetches the info and shows a card (title, channel, duration, quality…)
3. **Proceed with download?** — press Enter for yes, `0` for no
4. One live progress bar (with size, speed and ETA for a single file, or `n/total` for playlists)
5. A result card: what was saved, where, how long it took, and what (if anything) was missing and why

```
  ┌ ✔ DOWNLOAD COMPLETE
  │ Title     Big Buck Bunny
  │ Saved to  …\Downloads\LinkCatty
  │ Size      414.5MB
  │ Time      55s
  └
```

### 🎬 YouTube Downloader

- Choose **Video (best quality)**, **Audio (MP3)** or **Manual format selection**
- Paste a YouTube link: a single video, a playlist, a channel (`@name`), or a video with an auto‑mix (only the video is downloaded)
- Upcoming premieres and live streams are skipped and counted, not treated as errors
- Playlist downloads create a folder named after the playlist and run 3 videos at a time
- **Clean folders**: only the video or MP3 is saved (tags are embedded); the thumbnail and `.info.json` sidecar files are optional, see `settings.json`
- Bot‑check or members‑only videos: LinkCatty offers to use your browser's cookies once

### 🎵 Spotify Downloader

- Select **playlist**, **single track**, or **album**
- Paste the Spotify URL
- The app resolves tracks via free/unauthenticated Spotify metadata, then downloads audio from YouTube Music / YouTube
- **Parallel batches**: 3 spotdl processes × 2 threads = 6 concurrent downloads
- **Adaptive retries** (silent): missing tracks are retried with progressively wider provider sets (`youtube-music` → `+youtube` → `+soundcloud +piped` → loosened matching)

### 🌐 Other Downloaders

Paste a video or playlist link from any other site supported by `yt-dlp`.

- Quality follows **Settings → 8** (best available by default) — there is no extra question per download
- Playlists get their own folder, a resumable ledger and `failed_downloads.txt` for anything that could not be downloaded
- Direct connection first; your optional proxy (**Settings → 7**) is used only if the direct connection is blocked
- Blocked by your network? LinkCatty tells you to turn on a VPN and retries when you press Enter
- Sites that need an account: LinkCatty can use your browser's cookies (you must be logged in there)
- If you paste a YouTube or Spotify link here, it points you to the dedicated option instead

### ⚙️ Settings

Every prompt accepts **Enter = keep current value** and **0 = cancel without saving**:

| # | Item |
|---|------|
| 1 | Change download folder |
| 2 | YouTube: audio quality, video quality, auto‑retry, metadata toggles |
| 3 | Spotify: audio format, bitrate, auto‑retry |
| 4 | Spotify API credentials (optional — only for higher‑confidence track resolution) |
| 5 | Clear download history |
| 6 | Restore all settings to defaults (credentials and proxy are preserved) |
| 7 | Network proxy for Other Downloaders (OFF by default; only used when a direct connection is blocked) |
| 8 | Other downloads: video quality (best / 1080p / 720p / 480p / 360p) and auto‑retry |
| 0 | Back to main menu |

The install location and current download folder are shown at the top.

---

## ⚡ Performance

Defaults are tuned for speed on a normal home connection:

| Setting | Default | Effect |
|---|---|---|
| Spotify `parallel_batches` | 3 | Concurrent spotdl processes |
| Spotify `threads` | 2 | Per‑process download threads |
| YouTube `parallel_downloads` | 3 | Concurrent yt-dlp workers |
| Spotify `max_retry_passes` | 4 | Silent retry rounds |
| YouTube / Other `max_retry_passes` | 3 | Silent retry rounds |
| `batch_size` (Spotify) | 10 | Tracks per spotdl subprocess |

Effective concurrency: **Spotify = 6 downloads**, **YouTube = 3 downloads**.

If you see YouTube rate‑limiting (`Sign in to confirm you're not a bot`), lower `parallel_batches`/`parallel_downloads` to `1` or `2` in `sources/settings.json`. LinkCatty also eases off by itself when it detects rate limiting.

A real‑world 222‑track Spotify playlist that used to take **~2 h 20 min** now completes in **~40 minutes**, with the same number of successful tracks.

---

## 📂 Output layout

Everything is written into your download folder. By default that is a `LinkCatty` folder inside your system **Downloads** folder (`C:\Users\<you>\Downloads\LinkCatty` on Windows, `~/Downloads/LinkCatty` on macOS and Linux). It is created automatically on first launch, and you can change it any time in Settings > 1.

```
Downloads/LinkCatty/
├── <single videos and tracks are saved right here>
├── <YouTube playlist title>/
│   ├── <title> - <uploader>.mp4            ← just the file (no thumbnail / json by default)
│   ├── .linkcatty_state.json               ← per-video ledger (resumable)
│   └── failed_downloads.txt                ← only if any video failed
├── <Other Downloaders playlist>/
│   ├── <title>.mp4
│   ├── .linkcatty_state.json               ← per-video ledger (resumable)
│   └── failed_downloads.txt                ← only if any video failed
└── <Spotify playlist title>/
    ├── <title> - <artists>.mp3
    ├── .spotdl_archive.spotdl              ← spotdl's own skip-list
    ├── .spotdl_log.txt                     ← full spotdl output
    ├── .linkcatty_state.json               ← per-track ledger (resumable)
    └── failed_downloads.txt                ← only if any track failed
```

**Re-running a playlist**: just run it again. The ledger means only missing tracks/videos are attempted; a file you deleted is downloaded again.

> **Upgrading from an older version?** If you never changed the download folder, new downloads now go to `Downloads/LinkCatty`. Files already in the old `downloads` folder inside the install directory are left where they are. A folder you picked yourself is never changed.

---

## ⚙️ settings.json

Located at `sources/settings.json`. Created automatically on first launch. Notable keys:

```jsonc
{
  "download_dir": "C:\\Users\\you\\Downloads\\LinkCatty",   // default: <Downloads>/LinkCatty
  "youtube": {
    "video_quality": "best",          // best | 2160p | 1440p | 1080p | 720p | 480p | 360p
    "audio_quality": "320k",          // for MP3
    "auto_retry": true,
    "parallel_downloads": 3,          // concurrent yt-dlp workers
    "max_retry_passes": 3,            // silent retry rounds
    "save_metadata": false,           // true = also write a .info.json next to every video
    "save_thumbnail": false,          // true = also write the thumbnail (.webp / .jpg)
    "embed_metadata": true,           // ID3 / MP4 tags
    "embed_thumbnail": false          // cover art inside file (can fail on some formats)
  },
  "spotify": {
    "audio_format": "mp3",            // mp3 | flac | m4a | opus | ogg | wav
    "audio_quality": "320k",          // only for lossy formats
    "auto_retry": true,
    "parallel_batches": 3,
    "threads": 2,
    "batch_size": 10,
    "max_retry_passes": 4
  },
  "network": {
    "proxy": ""                       // optional, e.g. socks5://127.0.0.1:1080 (Other Downloaders, only when blocked)
  },
  "other": {
    "video_quality": "best",          // best | 1080p | 720p | 480p | 360p
    "auto_retry": true,
    "max_retry_passes": 3,
    "retry_delay_seconds": 8,
    "rate_limit_cooldown_seconds": 45
  }
}
```

You can edit it by hand, or use **Settings** in the app. Press **Enter** on any prompt to keep the current value, **0** to cancel.

> **Note**: FLAC/WAV from spotdl re-encode the same ~256 kbps YouTube source into a lossless container — the file is ~4× larger with no quality gain. **MP3 @ 320k is the best trade-off** for Spotify tracks.

---

## 🗑️ Uninstall

Remove LinkCatty completely (installation folder, PATH entry, and shortcuts):

| Platform | Command |
|----------|---------|
| **Windows** | `curl -L -o "%TEMP%\uninstall_linkcatty.cmd" https://tinyurl.com/linkcatty-uninstall-cmd && "%TEMP%\uninstall_linkcatty.cmd"` |
| **macOS / Linux** | `curl -L -o /tmp/uninstall_linkcatty.sh https://tinyurl.com/linkcatty-uninstall-sh && chmod +x /tmp/uninstall_linkcatty.sh && /tmp/uninstall_linkcatty.sh` |

Your downloaded files (`Downloads/LinkCatty`) are never touched.

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| `linkcatty` not recognized (`command not found`) | Open a **new** terminal window. On macOS/Linux run `source ~/.zshrc` (zsh) or `source ~/.bashrc` (bash), or start it with `~/.local/share/LinkCatty/linkcatty`. On Windows, check `%LOCALAPPDATA%\LinkCatty` is in your `PATH`. Running the installer again is safe: it repairs the PATH entry and keeps your settings. |
| I want the newest version now | Run `linkcatty --update`. It always checks GitHub, even if you updated a moment ago. |
| **"Could not connect – blocked by your network"** (Other Downloaders) | Your network is cutting the connection. Turn on a VPN and press Enter to retry, or set a proxy in **Settings → 7**. The proxy is only used when a direct connection is blocked, and is OFF by default. |
| **"Nothing is running at your proxy address"** | A proxy address only works while a proxy/VPN app that provides it is running. Start it, fix the address, or clear it with `-` in Settings → 7. |
| **YouTube "Sign in to confirm you're not a bot"** | LinkCatty offers to use your browser cookies (Chrome → Firefox → Edge → Brave) **once per session** — close your browser first. If no browser works, export cookies with the "Get cookies.txt LOCALLY" extension to `sources/cookies.txt`. |
| **Rate limited** | LinkCatty waits and slows down by itself. You can also lower `parallel_downloads` (YouTube) or `parallel_batches` (Spotify) to `1`–`2`, wait an hour, or use a VPN. |
| **Some tracks/videos are missing** | The result card lists the causes (removed, private, region‑locked, login required…). `failed_downloads.txt` in the playlist folder has the exact URLs. Removed/private videos cannot be downloaded; for the rest, run the same link again to retry only what is missing. |
| **"That link belongs to the YouTube/Spotify Downloader"** | You pasted a YouTube or Spotify link into Other Downloaders. Use main menu option 1 or 2 instead. |
| **macOS/Linux: "externally managed environment" or pip errors** | LinkCatty keeps its packages in its own virtual environment (`sources/.venv`), so system Python is never touched. On Debian/Ubuntu install `python3-venv` if it is missing. |
| FFmpeg not found (video merging may fail) | The installer bundles FFmpeg. If you see this warning, install FFmpeg manually — audio-only downloads still work. |
| **Progress bar shows 0% but downloads finish** | This can happen if the app is writing to a slow external drive. The bar updates every 0.5 s. |
| **A folder contains `.linkcatty_state.json` / `.spotdl_archive.spotdl` / `.spotdl_log.txt`** | These are internal state files — safe to keep (they enable resumability). Delete them only if you want a fresh start. |

---

## 🧑‍💻 Development & Contribution

LinkCatty is open source and welcomes contributions.

```bash
git clone https://github.com/maiz-an/LinkCatty.git
cd LinkCatty

# Option 1: use the bundled portable Python
run.cmd

# Option 2: use your own Python
pip install -r sources/requirements.txt
python sources/LinkCatty.py
```

Key modules:

| Path | Purpose |
|---|---|
| `sources/LinkCatty.py` | Main menu, settings UI, entry point |
| `sources/downloaders/youtube_downloader.py` | yt-dlp wrapper — parallel playlists, ledger, silent retries |
| `sources/downloaders/spotify_downloader.py` | spotdl wrapper — parallel batches, provider fallback |
| `sources/downloaders/other_downloader.py` | Engine for every other site — progress, retries, ledger, report |
| `sources/downloaders/universal.py` | Redirect hints (YouTube/Spotify links) and browser‑cookie login |
| `sources/utils/config.py` | `settings.json` load/save/reset, default download folder, proxy fallback |
| `sources/utils/ui.py` | UI kit (header, menus, cards, progress bar) and the shared retry/error policy |
| `sources/utils/logger.py` | Download history |
| `run.cmd` / `run.sh` | Launchers: update check, dependency setup, self‑repair |
| `CLAUDE.md` | Detailed codebase guide (UI conventions, update mechanism, gotchas) |

When you add or remove a source file, update the file lists in `run.cmd`, `run.sh`, `install_linkcatty.cmd` and `install_linkcatty.sh`, then bump `sources/version.txt` — see `CLAUDE.md`.

- **Issues / Feature requests**: [GitHub Issues](https://github.com/maiz-an/LinkCatty/issues)
- **Pull requests**: Always welcome

---

<p align="center">
  <sub>Made with ❤️ for the open‑source community</sub>
</p>

