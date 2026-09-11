
<!-- Banner / Logo (optional) -->
<p align="center">
  <img src="https://linkcatty.vercel.app/linkcatty.svg" alt="LinkCatty Logo" width="160"/>
</p>

<h1 align="center">🚀 LinkCatty – Universal Downloader</h1>

<p align="center">
  <strong>Download YouTube videos, playlists, and Spotify tracks – all from your terminal.</strong><br>
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
| 📹 **YouTube** | Single videos, playlists, custom format selection, MP3 conversion. Quality up to 4K / 1080p / 720p / best available. |
| 🎵 **Spotify** | Tracks, albums, playlists. Downloads as MP3 (320k / 192k), FLAC, M4A, OPUS, OGG, or WAV. |
| ⚡ **Parallel downloads** | Multiple concurrent downloads — 3 parallel batches × 2 threads (Spotify) and 3 workers (YouTube) out of the box. |
| 🔁 **Adaptive retry passes** | Missing tracks/videos are automatically retried with wider search strategies; only failures are re-attempted each pass. |
| 📝 **Full metadata** | `.info.json` sidecar files, thumbnails, and embedded tags (title/artist/album/cover) — all written automatically. |
| 💾 **Resumable** | A per‑folder ledger (`.linkcatty_state.json`) records every attempt. Re‑running a playlist only downloads what's still missing. |
| 🚦 **Rate‑limit aware** | Automatic cooldowns when YouTube throttles; switch to non‑YouTube providers when needed. |
| ⚙️ **Settings** | Download folder, quality, format, metadata toggles, parallelism, retry passes, quiet mode. Press Enter to keep current value. |
| 🔄 **Auto‑update** | Checks for new versions on launch and updates itself in place. |
| 🧩 **Portable** | No system Python required on Windows. Bundles its own runtime. |
| 🔐 **Privacy‑first** | Open‑source, no tracking, no data collection. Everything runs locally. |

---

## 💿 Installation

### 📌 One‑line install (no admin rights needed)

| Platform | Command |
|----------|---------|
| **Windows (CMD)** | `curl -L -o "%TEMP%\install_linkcatty.cmd" https://tinyurl.com/linkcattycmd && "%TEMP%\install_linkcatty.cmd"` |
| **macOS / Linux** | `curl -L -o /tmp/install_linkcatty.sh https://tinyurl.com/linkcattysh && chmod +x /tmp/install_linkcatty.sh && /tmp/install_linkcatty.sh` |

> After installation: **close and reopen your terminal** — then simply type `linkcatty` to launch.

### 📦 What the installer does

- Downloads the latest version from GitHub
- Installs everything to `%LOCALAPPDATA%\LinkCatty` (Windows) or `~/.local/share/LinkCatty` (Unix)
- Adds the folder to your **user PATH** (persistent)
- Creates a **Start Menu / desktop shortcut**
- Bundles FFmpeg (Windows x64, macOS Intel/ARM, Linux x64/ARM64)
- Creates `sources/settings.json` with full defaults on first launch

---

## 🧭 How to Use

Run `linkcatty` — you'll see the main menu:

```
=============================================================
                           v1.0.18
                      🎯 MAIN MENU
=============================================================
1. YouTube Downloader
2. Spotify Downloader
3. Other (coming soon)
4. Settings
5. Exit
=============================================================
```

### 🎬 YouTube Downloader

- Choose **Video (best quality)** or **Audio (MP3)**
- Paste a YouTube URL (single video or playlist)
- The app shows video/playlist info, then downloads into a subfolder
- Playlist downloads create a folder named after the playlist
- **Parallel downloads**: 3 videos at a time by default
- **Metadata is saved automatically**: `.info.json` sidecar + thumbnail + embedded tags

### 🎵 Spotify Downloader

- Select **playlist**, **single track**, or **album**
- Paste the Spotify URL
- The app resolves tracks via free/unauthenticated Spotify metadata, then downloads audio from YouTube Music / YouTube
- **Parallel batches**: 3 spotdl processes × 2 threads = 6 concurrent downloads
- **Adaptive retries**: missing tracks are retried with progressively wider provider sets (`youtube-music` → `+youtube` → `+soundcloud +piped` → loosened matching)

### ⚙️ Settings

Every prompt now accepts **Enter = keep current value** and **0 = cancel without saving**:

- Change download folder (Enter keeps current)
- YouTube: audio quality, video quality, auto‑retry, quiet mode, metadata toggles
- Spotify: audio format, bitrate, auto‑retry, quiet mode
- Spotify API credentials (optional — only needed for higher‑confidence track resolution)
- Clear download history
- **Restore all settings to defaults** (credentials are preserved)
- View the install location at a glance

---

## ⚡ Performance

Defaults are tuned for speed on a normal home connection:

| Setting | Default | Effect |
|---|---|---|
| Spotify `parallel_batches` | 3 | Concurrent spotdl processes |
| Spotify `threads` | 2 | Per‑process download threads |
| YouTube `parallel_downloads` | 3 | Concurrent yt-dlp workers |
| Spotify `max_retry_passes` | 4 | Adaptive retry rounds |
| YouTube `max_retry_passes` | 3 | Adaptive retry rounds |
| `batch_size` (Spotify) | 10 | Tracks per spotdl subprocess |

Effective concurrency: **Spotify = 6 downloads**, **YouTube = 3 downloads**.

If you see YouTube rate‑limiting (`Sign in to confirm you're not a bot`, `blocked by youtube`), lower `parallel_batches`/`parallel_downloads` to `1` or `2` in `sources/settings.json`.

A real‑world 222‑track Spotify playlist that used to take **~2 h 20 min** now completes in **~40 minutes**, with the same number of successful tracks.

---

## 📂 Output layout

Everything is written into your configured download folder:

```
downloads/
├── <YouTube playlist title>/
│   ├── <title> - <uploader>.mp4
│   ├── <title> - <uploader>.info.json      ← full yt-dlp metadata
│   ├── <title> - <uploader>.webp           ← thumbnail
│   ├── playlist.info.json                  ← playlist title/author/id list
│   ├── .linkcatty_state.json               ← per-video ledger (resumable)
│   └── failed_downloads.txt                ← only if any video failed
└── <Spotify playlist title>/
    ├── <title> - <artists>.mp3
    ├── .spotdl_archive.spotdl              ← spotdl's own skip-list
    ├── .spotdl_log.txt                     ← full spotdl output
    ├── .linkcatty_state.json               ← per-track ledger (resumable)
    └── failed_downloads.txt                ← only if any track failed
```

**Re-running a playlist**: just run it again. The ledger + spotdl archive mean only missing tracks/videos are attempted.

---

## ⚙️ settings.json

Located at `sources/settings.json`. Created automatically on first launch. Notable keys:

```jsonc
{
  "youtube": {
    "video_quality": "best",          // best | 2160p | 1440p | 1080p | 720p | 480p | 360p
    "audio_quality": "320k",          // for MP3
    "parallel_downloads": 3,          // concurrent yt-dlp workers
    "max_retry_passes": 3,
    "save_metadata": true,            // writes .info.json per video
    "save_thumbnail": true,           // writes .webp / .jpg
    "embed_metadata": true,           // ID3 / MP4 tags
    "embed_thumbnail": false          // cover art inside file (can fail on some formats)
  },
  "spotify": {
    "audio_format": "mp3",            // mp3 | flac | m4a | opus | ogg | wav
    "audio_quality": "320k",          // only for lossy formats
    "parallel_batches": 3,
    "threads": 2,
    "batch_size": 10,
    "max_retry_passes": 4
  }
}
```

You can edit it by hand, or use **Settings → 2 / 3** in the app. Press **Enter** on any prompt to keep the current value, **0** to cancel.

> **Note**: FLAC/WAV from spotdl re-encode the same ~256 kbps YouTube source into a lossless container — the file is ~4× larger with no quality gain. **MP3 @ 320k is the best trade-off** for Spotify tracks.

---

## 🗑️ Uninstall

Remove LinkCatty completely (installation folder, PATH entry, and shortcuts):

| Platform | Command |
|----------|---------|
| **Windows** | `curl -L -o "%TEMP%\uninstall_linkcatty.cmd" https://tinyurl.com/linkcatty-uninstall-cmd && "%TEMP%\uninstall_linkcatty.cmd"` |
| **macOS / Linux** | `curl -L -o /tmp/uninstall_linkcatty.sh https://tinyurl.com/linkcatty-uninstall-sh && chmod +x /tmp/uninstall_linkcatty.sh && /tmp/uninstall_linkcatty.sh` |

Your downloaded files and `settings.json` are never touched.

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| `linkcatty` not recognized | Close and reopen your terminal. On Windows, check `%LOCALAPPDATA%\LinkCatty` is in your `PATH`. |
| **YouTube "Sign in to confirm you're not a bot"** | LinkCatty automatically tries browser cookies (Chrome → Firefox → Edge → Brave) **once per session** — close your browser before the first failure. If no browser works, export cookies with the "Get cookies.txt LOCALLY" extension to `sources/cookies.txt`. |
| **`blocked by youtube` / rate limited** | Lower `parallel_downloads` (YouTube) or `parallel_batches` (Spotify) to `1`–`2`. Wait an hour. Or use a VPN. |
| **Some tracks/videos fail** | These are catalogue mismatches on YouTube's side, not bugs. Check `failed_downloads.txt` in the playlist folder for the exact URLs. Re-running the same download retries only those. |
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
| `sources/downloaders/youtube_downloader.py` | yt-dlp wrapper — parallel, ledger, retries |
| `sources/downloaders/spotify_downloader.py` | spotdl wrapper — parallel batches, provider fallback |
| `sources/utils/config.py` | `settings.json` load/save/reset |
| `sources/utils/ui.py` | Banners, menus, progress bars |
| `sources/utils/logger.py` | Download history |

- **Issues / Feature requests**: [GitHub Issues](https://github.com/maiz-an/LinkCatty/issues)
- **Pull requests**: Always welcome

---

<p align="center">
  <sub>Made with ❤️ for the open‑source community</sub>
</p>

