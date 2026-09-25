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
- yt-dlp in downloaders: pass `"logger": SilentLogger()` and show failures via `explain_error(exc, config)` (returns `(message, hint)`; the hint tells the user how to set the proxy when a block is detected); never print raw yt-dlp errors, they leak extractor names like `[SiteName]`

## Adding a New Downloader
1. Create `sources/downloaders/<site>.py` with a `run(config, url=None)` function
2. Register it in `sources/downloaders/other_downloader.py` — add domain detection and route
3. No changes needed to `LinkCatty.py` (option 3 always goes through `other_downloader.run`)

## Config Structure (settings.json)
```json
{
  "download_dir": "...",
  "youtube": { "audio_quality": "320k", "video_quality": "best", ... },
  "spotify":  { "audio_format": "mp3", "audio_quality": "320k", ... },
  "network":  { "proxy": "" }
}
```
`network.proxy` (Settings > 7) applies to Other Downloaders only. It is used **only as a fallback**: downloaders call `run_with_proxy_fallback(func, config, proxy=None)` from `utils/config.py`, which tries a direct connection first and retries once through the proxy only when the error looks like a blocked/reset connection (`is_block_error`). Reuse it in any new site handler; keep it preserved across "restore defaults".

## Key Dependencies
- `yt-dlp` — handles YouTube and 1000+ other sites
- `spotdl` — Spotify track/album/playlist downloader
- `spotipy` — Spotify API client for metadata
- FFmpeg is bundled under `sources/FFmpeg/`

## Auto-Update Mechanism
`run.cmd` compares `sources/version.txt` against the remote `version.txt` on GitHub main branch. If versions differ, it re-downloads all listed source files before launching, then replaces the running launcher itself.

Flags: `--update` (force update check), `--location` (print install dir), `--uninstall`.

### Checklist when adding/removing a source file
The file list is duplicated in **four** places. Update all of them or fresh installs / updates will break with ImportError:
- `run.cmd` — `FILE_LIST[n]`, `TOTAL_FILES`, and the `for /l` upper bound
- `run.sh` — `FILE_PATHS` and `FILE_URLS` (keep the two arrays index-aligned)
- `install_linkcatty.cmd` — `FILE_LIST[n]`, `TOTAL`, the `for /l` bound, and the FFmpeg `[N/N]` progress line
- `install_linkcatty.sh` — the `FILES` map
Then bump `sources/version.txt` (updates only trigger when the version string differs).

### Gotchas (each of these has caused a real breakage)
- **Installed launcher name differs**: the installer renames `run.cmd` -> `linkcatty.bat` (and `run.sh` -> `linkcatty`). The updater must overwrite the *running* launcher (`%~f0` / `$SELF`), never a literal `run.cmd`/`run.sh`, or the installed launcher never updates. The launcher is downloaded to a temp file and validated before it replaces the running one.
- **`.cmd` files must be pure ASCII.** `run.cmd` runs `chcp 65001`; any multi-byte character (e.g. an em dash in a comment) makes cmd misread later lines (`'tle' is not recognized`). Check with `grep -nP '[^\x00-\x7F]' *.cmd`.
- **`version.txt` must have no BOM.** In Windows PowerShell 5.1, `Set-Content -Encoding utf8` adds one. Write it with `printf "1.0.x" > sources/version.txt`.
- Inside parenthesized blocks in `.cmd` files use `rem`, not `::`.
- **A brand-new source file is not fetched by older launchers.** An update runs with the *installed* launcher's embedded file list, so a file added in version N is missing for users updating from N-1 (ImportError). Prefer extending an existing file (this is why the proxy helpers live in `utils/config.py`), or ship the new file in the lists one release before anything imports it.
