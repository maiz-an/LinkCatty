# LinkCatty — Codebase Guide

## Project Overview
LinkCatty is a portable, CLI-based media downloader for Windows (and Linux/macOS via shell scripts). It uses `yt-dlp` for video/audio extraction and `spotdl` + `spotipy` for Spotify. The app is fully self-contained: it ships a portable Python and FFmpeg, installs deps on first run, and auto-updates from GitHub.

## Entry Points
- **Windows**: `run.cmd` → installs deps, then runs `sources\LinkCatty.py`
- **Linux/macOS**: `run.sh` → same flow
- **Main loop**: `sources/LinkCatty.py` — `main()` is the top-level while-loop

## Directory Layout
```
LinkCatty/
├── sources/
│   ├── LinkCatty.py            # Main entry point, main loop, settings menus
│   ├── downloaders/
│   │   ├── youtube_downloader.py
│   │   ├── spotify_downloader.py
│   │   ├── other_downloader.py  # Option 3 router — detects site, dispatches
│   │   ├── ph.py                # site handler (yt-dlp + browser cookies for member content)
│   │   └── xm.py                # site handler (yt-dlp)
│   ├── utils/
│   │   ├── ui.py               # All CLI output helpers + ANSI colors
│   │   ├── config.py           # JSON settings load/save
│   │   ├── logger.py           # download_history.json
│   │   └── ffmpeg.py           # FFmpeg path resolver
│   ├── settings.json           # User config
│   ├── download_history.json
│   ├── requirements.txt        # yt-dlp, spotipy, spotdl
│   └── version.txt
├── downloads/                  # Default download folder
├── run.cmd / run.sh            # Launchers (auto-update + dep install)
└── CLAUDE.md
```

## UI Conventions (sources/utils/ui.py)
- All menus: `print_banner()` → section header → numbered options → `menu_choice()`
- Colors: `CYAN+BOLD` for option numbers, `GREEN` for success, `RED` for error, `YELLOW` for warnings
- Console width: fixed 62 columns (`set_console_width(62)`)
- `menu_choice(prompt, valid_chars)` — single-key input, returns string or None on Ctrl+C
- `confirm(prompt)` — y/n single-key
- `pause()` — press Enter to continue
- `start_spinner()` / `stop_spinner()` — animated progress indicator
- Always `clear_screen()` + `print_banner()` at the start of each downloader sub-menu

## Adding a New Downloader
1. Create `sources/downloaders/<site>.py` with a `run(config, url=None)` function
2. Register it in `sources/downloaders/other_downloader.py` — add domain detection and route
3. No changes needed to `LinkCatty.py` (option 3 always goes through `other_downloader.run`)

## Config Structure (settings.json)
```json
{
  "download_dir": "...",
  "youtube": { "audio_quality": "320k", "video_quality": "best", ... },
  "spotify":  { "audio_format": "mp3", "audio_quality": "320k", ... }
}
```

## Key Dependencies
- `yt-dlp` — handles YouTube and 1000+ other sites
- `spotdl` — Spotify track/album/playlist downloader
- `spotipy` — Spotify API client for metadata
- FFmpeg is bundled under `sources/FFmpeg/`

## Auto-Update Mechanism
`run.cmd` compares `sources/version.txt` against the remote `version.txt` on GitHub main branch. If versions differ, it re-downloads all listed source files before launching. New downloaders must be added to `FILE_LIST` in `run.cmd` and `run.sh` to be included in updates.
