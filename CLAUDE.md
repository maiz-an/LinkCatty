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
│   │   ├── other_downloader.py  # Option 3: Spotify-style UI + engine (progress, silent retries, ledger, report)
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
├── run.cmd / run.sh            # Launchers (auto-update + dep install)
└── CLAUDE.md
```

## UI Conventions (sources/utils/ui.py is the UI kit)
Every downloader (YouTube, Spotify, Other) draws its screens with the shared kit, so all of them look and behave the same. To restyle, change `ui.py` and every downloader follows. Never hand-print layouts (rules, boxes, `\r` progress) inside a downloader. The kit lives in `ui.py` on purpose: a new source file would be missing for users updating from an older launcher.

| Component | Use |
|---|---|
| `section_header(title)` | clear screen + banner (logo + tagline) + bold centered title + dim version line + rule (same for the main menu and Settings). Call it again after a run so the screen shows just header + result |
| `show_menu(title, options)` | numbered sub-menu with `0. Back to main menu` listed last; returns the key (`"0"` for back, also on an empty Enter) |
| `ask_url(what)` | the URL prompt: `🎯 Enter <what> URL (0 or blank to go back):`, returns `""` for back |
| `card(title, rows, icon, details)` | info card (`┌ │ └`, dim aligned labels, optional bullets) |
| `result_card(status, headline, rows, details, footer)` | end-of-run summary; status `ok` / `warn` / `fail`; `details` = cause bullets, `footer` = e.g. the Report path |
| `plan_line(*parts)` | one dim line above the bar: what is about to run |
| `item_line(ok, i, n, title, detail)` / `note_line(text, icon)` | per-item and retry/cooldown lines, printed with `progress.say()` |
| `DownloadProgress(label, total, unit, count_fn)` | ONE live, width-aware bar. Feed it with yt-dlp hooks (`.hook`, `.pp_hook`) or `count_fn` (e.g. files on disk); `.say()` prints above the bar, `.paused()` wraps prompts; `.final_path` is the finished file |
| `fit` / `fit_tail` / `display_width` | column-aware shortening (`fit_tail` keeps the END, used automatically for path values) |
| `classify_error` / `strategy_for_pass` / `apply_strategy` / `is_final_failure` / `show_failure_now` | the shared **silent retry policy** (see below): used by YouTube, Other and (labels only) Spotify |

The flow every downloader follows: menu or URL prompt -> spinner -> header + info card -> `confirm("Proceed with download?", default=True)` (Enter = yes) -> plan line + live bar -> clear -> header + result card -> `Process another link?`.

Retries are invisible (a rule for every downloader): no "Pass 1/3", no "retrying in Ns", no "N left after pass" lines, no plan-line mention; the bar label stays `Downloading`. Behind the scenes each item gets up to `max_retry_passes` attempts (1 when Settings `auto_retry` is off), each with more patience (`PASS_STRATEGIES`: more retries and longer timeouts, then relaxed quality over IPv4). Failures are classified with `classify_error`; `unavailable`/`upcoming`/`unsupported`/`disk`/`login` are final at once (never retried); a connection reset gets one more attempt; rate limits wait longer (YouTube also halves its parallel workers). A per-item `✖` line is printed only when the item is really final (`show_failure_now`): recovered items never show one, login/VPN cases wait for their prompt. The "Turn on your VPN" prompt appears only when a whole round downloaded nothing and a failure looked like a block (one flaky video never triggers it). YouTube playlists are parallel (bar fed by the ledger, `Ctrl+C` cancels workers through a yt-dlp hook), single videos and manual-format downloads use the same silent attempts. Ledger `.linkcatty_state.json` (playlists) records cause/attempts and a re-run resumes; a finished file the user deleted is fetched again. Tests that stub `_download_one_video` must match its real signature, or a broken call hides behind the stub (this once broke every YouTube playlist).

Other rules:
- **Navigation is the same everywhere: `0` goes back / cancels, an empty Enter skips.** Menus list `0. Back` last (Enter also goes back); the main menu lists `0. Exit` and ignores a bare Enter so the app never closes by accident; URL and format-id prompts accept `0` or blank; `confirm` treats `0` as No; settings prompts are Enter = keep, `0` = cancel; Ctrl+C acts like back. Never number Back/Exit as the last digit
- Menus keep `CYAN+BOLD` numbers; console width is fixed at 62 columns (`set_console_width(62)`) and the bar adapts to it, never wrap
- `menu_choice(prompt, valid_chars)` single-key input (None on Ctrl+C); `confirm(prompt, default)` y/n; `pause()`; `start_spinner()` / `stop_spinner()` for the fetch step
- There is no per-downloader "quiet mode": yt-dlp output is always replaced by the bar
- yt-dlp in downloaders: pass `"logger": SilentLogger()` and show failures via `explain_error(exc, config)` (returns `(message, hint)`; the hint tells the user how to set the proxy when a block is detected); never print raw yt-dlp errors, they leak extractor names like `[SiteName]`. In a real terminal yt-dlp wraps `ERROR:` in ANSI color codes, which broke prefix stripping once; `explain_error` strips ANSI first, and tests must force `"color": {"stderr": "always"}` (redirected output has no colors and hides the bug). After a blocked-connection error, call `offer_retry_after_block(exc)` so the user can turn on a VPN and press Enter to retry (it only prompts for block-type errors)

## Adding a New Downloader (Other Downloader sites)
`other_downloader.py` owns the whole flow (info card, single live progress bar, classified errors, silent multi-pass retries with cooldowns, ledger/report for playlists, VPN retry prompt, workflow guard). A site file is only a small **profile**:
There are no per-site files: every link that is not YouTube or Spotify goes through `universal.py` and the generic yt-dlp engine, so most new sites need no code.
- `universal.dedicated(url)` returns `(name, menu number)` for links that have their own menu entry (YouTube, Spotify); the Other Downloader then tells the user to use that entry instead. To add a new *dedicated* downloader: create `downloaders/<name>.py` with a `run(config)`, add its menu entry in `LinkCatty.py`, add it to `_DEDICATED` in `universal.py`, and add the file to the four file lists (see the checklist below).
- `universal.login_options(config, proxy)` loads browser cookies for sites that need an account; the engine calls it once when a login-class error appears.
- History source key for these links is `Other`.

Behavior worth knowing: video quality comes from Settings > 8 (`other.video_quality`, default `best`); there is no per-download quality prompt, only `Proceed with download?` (Enter = yes). When a run ends the screen is cleared to the banner + section header + result panel, so the info panel and progress lines are gone. Single videos keep no ledger/report files (nothing extra on disk); playlists write `.linkcatty_state.json` + `failed_downloads.txt` in their folder and resume on re-run. Errors are classified (`login`, `blocked`, `network`, `rate_limited`, `unavailable`, `unsupported`, `format`, `disk`); `login`, `blocked`, `unavailable`, `unsupported` and `disk` are not retried by passes. Blocked errors end the round and ask the user to turn on a VPN, then retry.

## Config Structure (settings.json)
```json
{
  "download_dir": "<Downloads>/LinkCatty",
  "youtube": { "audio_quality": "320k", "video_quality": "best", ... },
  "spotify":  { "audio_format": "mp3", "audio_quality": "320k", ... },
  "network":  { "proxy": "" },
  "other":    { "video_quality": "best", "auto_retry": true, "max_retry_passes": 3, "retry_delay_seconds": 8, "rate_limit_cooldown_seconds": 45 }
}
```
`network.proxy` (Settings > 7) applies to Other Downloaders only. It is used **only as a fallback**: downloaders call `run_with_proxy_fallback(func, config, proxy=None)` from `utils/config.py`, which tries a direct connection first and retries once through the proxy only when the error looks like a blocked/reset connection (`is_block_error`). Reuse it in any new site handler; keep it preserved across "restore defaults".

## Files next to a download
By default a download is just the media file (tags are embedded with `embed_metadata`). The thumbnail (`.webp`) and `.info.json` sidecars are opt-in: `youtube.save_thumbnail` / `youtube.save_metadata` (default `false`, no menu entry, edit `settings.json`). Old installs had them saved as `true` without ever choosing, so `config_version` (currently 2, `CONFIG_VERSION` in `utils/config.py`) triggers a one-time `_migrate()` in `load_config()`; bump it and extend `_migrate` when a default must reach existing settings files. `playlist.info.json` was removed (nothing read it).

## Download folder
Default: `<system Downloads folder>/LinkCatty` (`get_default_download_dir()` in `utils/config.py`: the Windows known-folder API so a moved/OneDrive Downloads works, `XDG_DOWNLOAD_DIR` on Linux, `~/Downloads` on macOS and as the fallback). `main()` creates it on first launch. `load_config()` migrates a `download_dir` that still equals the old built-in default (`<install>/downloads`) to the new one and saves it; a folder the user picked is never touched, and files already in the old folder are not moved. "Restore defaults" resets to the new default.

## Key Dependencies
- `yt-dlp` — handles YouTube and 1000+ other sites
- `spotdl` — Spotify track/album/playlist downloader
- `spotipy` — Spotify API client for metadata
- FFmpeg is bundled under `sources/FFmpeg/`

## Auto-Update Mechanism
`run.cmd` / `run.sh` compare `sources/version.txt` against the remote `version.txt`. If versions differ, the launcher downloads all listed files into a **staging folder** first and only copies them over the install when every file arrived (a dropped connection can never leave old and new files mixed, which used to cause ImportError), then replaces the running launcher itself and restarts in the same window.

Flags: `--update` (force update check), `--location` (print install dir), `--uninstall`. Internal: `--restarted` (the launcher's own restart after an update or repair; it skips the update check so nothing can loop; `--repaired` is the old name and still accepted; never pass it by hand).

**Never stale:** `raw.githubusercontent.com` caches `main` for ~5 minutes and ignores `?query` cache-busting (verified: fresh query strings still return `X-Cache: HIT`). So on every launch the launcher asks `https://github.com/maiz-an/LinkCatty.git/info/refs?service=git-upload-pack` (sent `no-cache`) for the latest commit SHA and downloads `version.txt`, all files and the launcher from `raw.githubusercontent.com/maiz-an/LinkCatty/<sha>/...` (a new SHA is never cached). If the lookup fails it falls back to `main`. File-list URLs stay written with `/LinkCatty/main/`; the launcher rewrites that substring to the SHA, so keep it in every new entry. The installers do the same SHA lookup, so a fresh install always gets files of one commit.

### Checklist when adding/removing a source file
The file list is duplicated in **four** places. Update all of them or fresh installs / updates will break with ImportError:
- `run.cmd` — `FILE_LIST[n]`, `TOTAL_FILES`, and the `for /l` upper bound (in the update block)
- `run.sh` — the `FILE_PATHS` array (paths only; the URL is built from the pinned commit)
- `install_linkcatty.cmd` — `FILE_LIST[n]`, `TOTAL` and the `for /l` bound (the bar counts files + FFmpeg); it must also contain `run.sh`, which the launcher lists
- `install_linkcatty.sh` — the `FILES` array (plain indexed array, paths only; must include everything `run.sh` lists so a fresh install never triggers a repair)
Every listed file must exist on GitHub: the installers and the updater now treat a 404 as a failed download and stop without changing anything (the old lists contained a `sources/__init__.py` that was never in the repo and only worked because 404s were ignored).
Then bump `sources/version.txt` (updates only trigger when the version string differs).

### Gotchas (each of these has caused a real breakage)
- **Installed launcher name differs**: the installer renames `run.cmd` -> `linkcatty.bat` (and `run.sh` -> `linkcatty`). The updater must overwrite the *running* launcher (`%~f0` / `$SELF`), never a literal `run.cmd`/`run.sh`, or the installed launcher never updates. The launcher is downloaded to a temp file and validated before it replaces the running one.
- **`.cmd` files must be pure ASCII.** `run.cmd` runs `chcp 65001`; any multi-byte character (e.g. an em dash in a comment) makes cmd misread later lines (`'tle' is not recognized`). Check with `grep -nP '[^\x00-\x7F]' *.cmd`.
- **`version.txt` must have no BOM.** In Windows PowerShell 5.1, `Set-Content -Encoding utf8` adds one. Write it with `printf "1.0.x" > sources/version.txt`.
- Inside parenthesized blocks in `.cmd` files use `rem`, not `::`.
- **YouTube info must be fetched flat.** `get_url_info` uses `extract_flat: "in_playlist"` (titles and ids only). Loading every entry made playlists/channels take minutes, and one premiere or unavailable entry aborted the whole fetch ("Premieres in 11 hours"). `_normalize_url` also turns a video + auto-mix link (`list=RD...`) into just the video and a channel page (`@name`, `/channel/`, `/c/`, `/user/`) into its `/videos` tab; upcoming/live entries are skipped and counted.
- **Line endings are part of the code.** `.gitattributes` marks `*.cmd`/`*.bat`/`*.sh` as `-text` so Git never converts them: `.cmd` files are stored with **CRLF** (LF-only batch files can break labels/`goto` in cmd, the classic "format error"), `.sh` files with **LF** (CRLF gives `bad interpreter` / `\r` errors on macOS). GitHub serves the stored bytes to the installers and updaters. Check before committing: `git ls-files --eol | grep -E "\.(cmd|sh)$"` must show `i/crlf` for `.cmd` and `i/lf` for `.sh`. As a second line of defence the launchers and installers also force CRLF on downloaded `.cmd` files and LF on `.sh` files.
- **Launcher look (all four scripts + the two uninstallers):** identical to the app: `- a Maiz's one -`, bold title + dim version, a `─` rule, `✔ ⚠ ✖ ›` status lines, one in-place `━`/`─` bar and `┌ │ └` result cards. The `.cmd` files must stay pure ASCII, so `:ui_init` writes the glyphs as hex, decodes them with `certutil -decodehex` into a temp file and reads them back with `set /p` (verified to emit the exact UTF-8 bytes); if that fails, or on Windows older than 10, it falls back to `+ x ! > # . -`. Colors and the in-place redraw use ANSI codes (`ESC[2K ESC[1G`), enabled only on Windows 10+. The old "carriage return stored in a variable" trick (`copy /Z`) prints nothing on current Windows builds, do not bring it back. Each script carries its own copy of the helpers (`ui_*`, `:FetchFile`); keep them in sync by hand. In `.cmd` files pass text to the helpers through the `MSG` / `DET` / `ROW_K` / `ROW_V` variables, never as arguments (`!`, `%` and `&` in paths).
- **cmd traps that cost real bugs:** (1) a `)` inside a `rem` or `echo` line inside a parenthesized block closes the block early; (2) with delayed expansion enabled, a line that contains `!` treats `^` as an escape even inside quotes (a `[^0-9.]` pattern silently became `[0-9.]`), so keep such patterns on lines without `!` (use `%VAR%` there); (3) `findstr` `$`/`/x` anchors do not match a last line without a line ending (`version.txt` has none), and `timeout` refuses to run when input is redirected (use `ping -n N 127.0.0.1 >nul`); (4) a `goto` label search from `s.index(":ui_bar")` in a patch script hits `call :ui_bar` first, always search for `\n:label\n`.
- **Downloads are hardened** (`:FetchFile` in the cmd scripts, `fetch_file` in the sh scripts): raw.githubusercontent.com first, then a jsDelivr mirror when the commit is known, three rounds with growing pauses, the real reason is shown when it fails, and a downloaded file that is an HTML page (proxy / captive portal) or an invalid `version.txt` is rejected instead of being installed (it would surface later as a syntax or format error). On the first failure the remaining downloads are skipped and nothing is changed.
- **A batch file must never be read again after it was deleted or replaced.** cmd re-opens the caller when a `call` returns, so a launcher that `call`s an uninstaller which deletes the install folder prints `The system cannot find the path specified.` The uninstaller therefore copies itself to `%TEMP%`, starts the copy in its own window and exits; the update restart is `call "%~f0" --restarted & exit /b !errorlevel!` on one line and nothing after the launcher copy may call a label.
- **PATH on Windows is edited through PowerShell's user-scope `Path` variable**, never `setx PATH "%PATH%"` (that copies the machine PATH into the user PATH and cuts it at 1024 characters). The installer keeps `settings.json` and the history on reinstall.
- **macOS/Linux installer:** written for bash 3.2 (macOS): no `declare -A`, `mapfile`, `${var,,}` (this broke the first Mac install). PATH is written to the rc file of the user's actual shell (`$SHELL`: zsh -> `~/.zshrc`, created if missing, because zsh never reads `~/.bashrc`; bash -> `~/.bash_profile` on macOS, `~/.bashrc` on Linux; fish -> `config.fish`) plus any other rc file that exists. A symlink is also placed in a writable folder that is already on PATH (`~/.local/bin`, `~/bin`, `/opt/homebrew/bin`, `/usr/local/bin`) so `linkcatty` works in the current terminal; `run.sh` resolves symlinks to find its real folder. The uninstaller removes rc lines with `grep -vF`, never `sed` with the path in the pattern (the `/` characters broke it). FFmpeg lives in `sources/FFmpeg/macos/ffmpeg` / `linux/ffmpeg` (what `utils/ffmpeg.py` and `run.sh` look for).
- **Python packages on macOS/Linux live in a venv** (`sources/.venv`, created by `run.sh`): Homebrew and current Debian/Ubuntu Pythons refuse `pip install` into the system (`externally-managed-environment`). If `python -m venv` is unavailable the launcher falls back to `pip --user --break-system-packages`. Installs that already have `.deps_installed` and no venv keep working unchanged until their next update.
- **Testing the scripts:** run them in a sandbox with a fake HOME, a fake `uname`, and a local HTTP server standing in for GitHub (rewrite the `raw.githubusercontent.com` / `info/refs` / FFmpeg URLs in a copy). Never point a test at the real user PATH: swap the PowerShell PATH line for an `echo`.
- **Progress bar math (`DownloadProgress.hook`) must not trust yt-dlp byte totals.** Fragmented (HLS/DASH) streams report `total_bytes == downloaded_bytes` on the first event (`712 of 712`), which once pinned the bar at 99% for the whole download because the bar never goes backwards. The bar now (1) asks yt-dlp for the planned streams before the download (`progress.watch(ydl)` adds a `before_dl` post-processor: `requested_formats` is only present at that stage, not in the hook's `info_dict` and not at `pre_process`) and weights video/audio by size, (2) uses `fragment_index/fragment_count` for fragmented streams, exact `total_bytes` otherwise, (3) shows a size total only when yt-dlp knows real file sizes (bitrate estimates are used for weights only), and (4) measures its own ETA after a few seconds. Always add `progress.watch(ydl)` in a new downloader that feeds a bar with hooks; regression tests: `progress_test.py`-style cases (first report `712/712`, fragments, two streams, monotonic).
- **A brand-new source file is not fetched by launchers older than the missing-file repair** (added in 1.0.31). An update runs with the *installed* launcher's embedded file list, so a file added in version N is missing for users updating from N-1. Since 1.0.31 the launcher also treats a missing listed file as a reason to update: it re-downloads and restarts once with `--repaired` (which skips the check, so a failing download can never loop; renamed `--restarted` in 1.0.36). The hop therefore self-heals on the next start; keep the file lists complete and prefer extending existing files when possible.
