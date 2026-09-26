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
│   │   ├── other_downloader.py  # Option 3: Spotify-style UI + engine (progress, retry passes, ledger, report)
│   │   └── universal.py         # profile for every non-YouTube/Spotify link: redirect hints + member login
│   ├── utils/
│   │   ├── ui.py               # UI kit (header, menu, cards, progress bar) + CLI helpers
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

## UI Conventions (sources/utils/ui.py is the UI kit)
Every downloader (YouTube, Spotify, Other) draws its screens with the shared kit, so all of them look and behave the same. To restyle, change `ui.py` and every downloader follows. Never hand-print layouts (rules, boxes, `\r` progress) inside a downloader. The kit lives in `ui.py` on purpose: a new source file would be missing for users updating from an older launcher.

| Component | Use |
|---|---|
| `section_header(title)` | clear screen + banner (logo + tagline) + bold centered title + dim version line + rule (same for the main menu and Settings). Call it again after a run so the screen shows just header + result |
| `show_menu(title, options)` | numbered sub-menu; returns the chosen key (last option = Back) |
| `ask_url(what)` | the URL prompt: `🎯 Enter <what> URL (blank to go back):` |
| `card(title, rows, icon, details)` | info card (`┌ │ └`, dim aligned labels, optional bullets) |
| `result_card(status, headline, rows, details, footer)` | end-of-run summary; status `ok` / `warn` / `fail`; `details` = cause bullets, `footer` = e.g. the Report path |
| `plan_line(*parts)` | one dim line above the bar: what is about to run |
| `item_line(ok, i, n, title, detail)` / `note_line(text, icon)` | per-item and retry/cooldown lines, printed with `progress.say()` |
| `DownloadProgress(label, total, unit, count_fn)` | ONE live, width-aware bar. Feed it with yt-dlp hooks (`.hook`, `.pp_hook`) or `count_fn` (e.g. files on disk); `.say()` prints above the bar, `.paused()` wraps prompts; `.final_path` is the finished file |
| `fit` / `fit_tail` / `display_width` | column-aware shortening (`fit_tail` keeps the END, used automatically for path values) |

The flow every downloader follows: menu or URL prompt -> spinner -> header + info card -> `confirm("Proceed with download?", default=True)` (Enter = yes) -> plan line + live bar -> clear -> header + result card -> `Process another link?`.

Other rules:
- Menus keep `CYAN+BOLD` numbers; console width is fixed at 62 columns (`set_console_width(62)`) and the bar adapts to it, never wrap
- `menu_choice(prompt, valid_chars)` single-key input (None on Ctrl+C); `confirm(prompt, default)` y/n; `pause()`; `start_spinner()` / `stop_spinner()` for the fetch step
- There is no per-downloader "quiet mode": yt-dlp output is always replaced by the bar
- yt-dlp in downloaders: pass `"logger": SilentLogger()` and show failures via `explain_error(exc, config)` (returns `(message, hint)`; the hint tells the user how to set the proxy when a block is detected); never print raw yt-dlp errors, they leak extractor names like `[SiteName]`. In a real terminal yt-dlp wraps `ERROR:` in ANSI color codes, which broke prefix stripping once; `explain_error` strips ANSI first, and tests must force `"color": {"stderr": "always"}` (redirected output has no colors and hides the bug). After a blocked-connection error, call `offer_retry_after_block(exc)` so the user can turn on a VPN and press Enter to retry (it only prompts for block-type errors)

## Adding a New Downloader (Other Downloader sites)
`other_downloader.py` owns the whole flow (info card, single live progress bar, classified errors, multi-pass retries with cooldowns, ledger/report for playlists, VPN retry prompt, workflow guard). A site file is only a small **profile**:
There are no per-site files: every link that is not YouTube or Spotify goes through `universal.py` and the generic yt-dlp engine, so most new sites need no code.
- `universal.dedicated(url)` returns `(name, menu number)` for links that have their own menu entry (YouTube, Spotify); the Other Downloader then tells the user to use that entry instead. To add a new *dedicated* downloader: create `downloaders/<name>.py` with a `run(config)`, add its menu entry in `LinkCatty.py`, add it to `_DEDICATED` in `universal.py`, and add the file to the four file lists (see the checklist below).
- `universal.login_options(config, proxy)` loads browser cookies for sites that need an account; the engine calls it once when a login-class error appears.
- History source key for these links is `Other`.

Behavior worth knowing: video quality comes from Settings > 8 (`other.video_quality`, default `best`); there is no per-download quality prompt, only `Proceed with download?` (Enter = yes). When a run ends the screen is cleared to the banner + section header + result panel, so the info panel and progress lines are gone. Single videos keep no ledger/report files (nothing extra on disk); playlists write `.linkcatty_state.json` + `failed_downloads.txt` in their folder and resume on re-run. Errors are classified (`login`, `blocked`, `network`, `rate_limited`, `unavailable`, `unsupported`, `format`, `disk`); `login`, `blocked`, `unavailable`, `unsupported` and `disk` are not retried by passes. Blocked errors end the round and ask the user to turn on a VPN, then retry.

## Config Structure (settings.json)
```json
{
  "download_dir": "...",
  "youtube": { "audio_quality": "320k", "video_quality": "best", ... },
  "spotify":  { "audio_format": "mp3", "audio_quality": "320k", ... },
  "network":  { "proxy": "" },
  "other":    { "video_quality": "best", "auto_retry": true, "max_retry_passes": 3, "retry_delay_seconds": 8, "rate_limit_cooldown_seconds": 45 }
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

Flags: `--update` (force update check), `--location` (print install dir), `--uninstall`. Internal: `--repaired` (set by the launcher on its own restart after repairing missing files; never pass it by hand).

**Never stale:** `raw.githubusercontent.com` caches `main` for ~5 minutes and ignores `?query` cache-busting (verified: fresh query strings still return `X-Cache: HIT`). So on every launch the launcher asks `https://github.com/maiz-an/LinkCatty.git/info/refs?service=git-upload-pack` (sent `no-cache`) for the latest commit SHA and downloads `version.txt`, all files and the launcher from `raw.githubusercontent.com/maiz-an/LinkCatty/<sha>/...` (a new SHA is never cached). If the lookup fails it falls back to `main`. File-list URLs stay written with `/LinkCatty/main/`; the launcher rewrites that substring to the SHA, so keep it in every new entry. The installers still use `main`, so a fresh install right after a push can be up to 5 minutes stale.

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
- **YouTube info must be fetched flat.** `get_url_info` uses `extract_flat: "in_playlist"` (titles and ids only). Loading every entry made playlists/channels take minutes, and one premiere or unavailable entry aborted the whole fetch ("Premieres in 11 hours"). `_normalize_url` also turns a video + auto-mix link (`list=RD...`) into just the video and a channel page (`@name`, `/channel/`, `/c/`, `/user/`) into its `/videos` tab; upcoming/live entries are skipped and counted.
- **A brand-new source file is not fetched by launchers older than the missing-file repair** (added in 1.0.31). An update runs with the *installed* launcher's embedded file list, so a file added in version N is missing for users updating from N-1. Since 1.0.31 the launcher also treats a missing listed file as a reason to update: it re-downloads and restarts once with `--repaired` (which skips the check, so a failing download can never loop). The hop therefore self-heals on the next start; keep the file lists complete and prefer extending existing files when possible.
