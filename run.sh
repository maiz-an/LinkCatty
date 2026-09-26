#!/bin/bash
# LinkCatty Launcher for Linux/macOS
# Works with the bash 3.2 that ships with macOS (no associative arrays, no bash 4 features).
# This file must keep LF line endings (see .gitattributes).

# -------------------------------------------------------------------
# Resolve where LinkCatty lives (also when started through a symlink)
# -------------------------------------------------------------------
SELF="${BASH_SOURCE[0]}"
while [ -L "$SELF" ]; do
    LINK_DIR="$(cd -P "$(dirname "$SELF")" && pwd)"
    SELF="$(readlink "$SELF")"
    case "$SELF" in
        /*) ;;
        *) SELF="$LINK_DIR/$SELF" ;;
    esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SELF")" && pwd)"
SELF="$SCRIPT_DIR/$(basename "$SELF")"

# -------------------------------------------------------------------
# Look and feel (same as the app)
# -------------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_RST=$'\033[0m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'
    C_CY=$'\033[36m'; C_GR=$'\033[32m'; C_RD=$'\033[31m'; C_YL=$'\033[33m'
    IS_TTY=1
else
    C_RST=""; C_DIM=""; C_BOLD=""; C_CY=""; C_GR=""; C_RD=""; C_YL=""
    IS_TTY=0
fi
RULE=""; _i=0
while [ $_i -lt 58 ]; do RULE="$RULE─"; _i=$((_i + 1)); done

ui_header() {   # title, small text
    echo ""
    printf "  %s- a Maiz's one -%s\n" "$C_DIM" "$C_RST"
    printf "  %s%s%s  %s%s%s\n" "$C_BOLD" "$1" "$C_RST" "$C_DIM" "$2" "$C_RST"
    printf "  %s%s%s\n" "$C_DIM" "$RULE" "$C_RST"
}
ui_line() {     # color, icon, text, detail
    if [ -n "$4" ]; then
        printf "  %s%s%s %s  %s%s%s\n" "$1" "$2" "$C_RST" "$3" "$C_DIM" "$4" "$C_RST"
    else
        printf "  %s%s%s %s\n" "$1" "$2" "$C_RST" "$3"
    fi
}
ui_ok()    { ui_line "$C_GR" "✔" "$1" "$2"; }
ui_fail()  { ui_line "$C_RD" "✖" "$1" "$2"; }
ui_warn()  { ui_line "$C_YL" "⚠" "$1" "$2"; }
ui_arrow() { ui_line "$C_CY" "›" "$1" "$2"; }
ui_note()  { printf "  %s%s%s\n" "$C_DIM" "$1" "$C_RST"; }
ui_bar() {      # label, done, total  (in place, only on a real terminal)
    [ "$IS_TTY" = 1 ] || return 0
    local label="$1" n="$2" total="$3" w=24 pct filled b1="" b2="" k=0
    pct=$(( n * 100 / total )); filled=$(( n * w / total ))
    while [ $k -lt $w ]; do
        if [ $k -lt $filled ]; then b1="$b1━"; else b2="$b2─"; fi
        k=$((k + 1))
    done
    printf "\r  %s%s%s  %s%s%s%s%s%s  %s%3d%%%s  %s%d/%d%s\033[K" \
        "$C_CY" "$label" "$C_RST" "$C_CY" "$b1" "$C_RST" "$C_DIM" "$b2" "$C_RST" \
        "$C_BOLD" "$pct" "$C_RST" "$C_DIM" "$n" "$total" "$C_RST"
}

# One file from GitHub. Tries the raw server, then a mirror (jsDelivr, only when the commit is
# known), three rounds with growing pauses. A web page from a proxy or captive portal is
# rejected instead of being installed (it would show up later as a syntax or format error).
# Sets FETCH_ERR when it fails.
fetch_file() {   # repo-relative path, output file
    local rel="$1" out="$2" try=1 mirror=""
    FETCH_ERR=""
    if [ "$REF" != "main" ]; then mirror="https://cdn.jsdelivr.net/gh/maiz-an/LinkCatty@$REF/$rel"; fi
    while [ $try -le 3 ]; do
        FETCH_ERR="could not reach GitHub"
        if curl -fsSL --connect-timeout 15 --max-time 120 -o "$out" "$RAW_BASE/$rel" 2>/dev/null \
            || { [ -n "$mirror" ] && curl -fsSL --connect-timeout 15 --max-time 120 -o "$out" "$mirror" 2>/dev/null; }; then
            if head -c 300 "$out" | tr 'A-Z' 'a-z' | grep -q '^<!doctype\|^<html'; then
                FETCH_ERR="received a web page instead of the file"
            elif [ "$rel" = "sources/version.txt" ] && ! tr -d '\r\n ' < "$out" | grep -Eq '^[0-9][0-9.]*$'; then
                FETCH_ERR="the version file is not valid"
            else
                FETCH_ERR=""
                return 0
            fi
        fi
        try=$((try + 1))
        [ $try -le 3 ] && sleep $((try * 2 - 3))
    done
    return 1
}

# -------------------------------------------------------------------
# Flags
# -------------------------------------------------------------------
case " $* " in
    *" --uninstall "*)
        if [ -f "$SCRIPT_DIR/uninstall_linkcatty.sh" ]; then
            bash "$SCRIPT_DIR/uninstall_linkcatty.sh"
        else
            UN="$(mktemp "${TMPDIR:-/tmp}/linkcatty_un.XXXXXX")"
            if curl -fsSL -o "$UN" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"; then
                bash "$UN"
            else
                echo "Could not download the uninstaller."
            fi
            rm -f "$UN"
        fi
        exit 0
        ;;
esac

case " $* " in
    *" --location "*)
        echo ""
        echo "LinkCatty is installed at:"
        echo "$SCRIPT_DIR"
        exit 0
        ;;
esac

FORCE_UPDATE=0
case " $* " in *" --update "*) FORCE_UPDATE=1 ;; esac
RESTARTED=0
case " $* " in *" --restarted "*|*" --repaired "*) RESTARTED=1 ;; esac

LOCAL_VERSION_FILE="$SCRIPT_DIR/sources/version.txt"
if [ -f "$LOCAL_VERSION_FILE" ]; then
    LOCAL_VER="$(tr -d '\r\n ' < "$LOCAL_VERSION_FILE")"
else
    LOCAL_VER="0.0.0"
fi
[ -n "$LOCAL_VER" ] || LOCAL_VER="0.0.0"

ui_header "LinkCatty" "v$LOCAL_VER"

# -------------------------------------------------------------------
# 1. Updates
# -------------------------------------------------------------------
# raw.githubusercontent.com caches "main" for ~5 minutes and ignores query strings.
# Ask git (never cached) for the latest commit SHA and download from a SHA-pinned URL.
# If the lookup fails we fall back to "main".
REF="main"
LATEST_SHA="$(curl -sf --max-time 8 "https://github.com/maiz-an/LinkCatty.git/info/refs?service=git-upload-pack" 2>/dev/null \
    | grep -a -o '[0-9a-f]\{40\} refs/heads/main' | head -n1 | cut -c1-40)"
if [ "${#LATEST_SHA}" -eq 40 ] && echo "$LATEST_SHA" | grep -q '^[0-9a-f]*$'; then
    REF="$LATEST_SHA"
fi
RAW_BASE="https://raw.githubusercontent.com/maiz-an/LinkCatty/$REF"
DEPS_MARKER="$SCRIPT_DIR/sources/.deps_installed"

REMOTE_VER="$(curl -sf --max-time 8 "$RAW_BASE/sources/version.txt" | tr -d '\r\n ')"
[ -n "$REMOTE_VER" ] || REMOTE_VER="$LOCAL_VER"

FILE_PATHS=(
    "sources/downloaders/spotify_downloader.py"
    "sources/downloaders/youtube_downloader.py"
    "sources/utils/config.py"
    "sources/utils/ffmpeg.py"
    "sources/utils/logger.py"
    "sources/utils/ui.py"
    "sources/requirements.txt"
    "sources/version.txt"
    "run.cmd"
    "uninstall_linkcatty.cmd"
    "uninstall_linkcatty.sh"
    "sources/LinkCatty.py"
    "sources/downloaders/other_downloader.py"
    "sources/downloaders/universal.py"
)
# If a managed file is missing (e.g. a module added in a newer release), repair by
# re-downloading. The restart flag stops any update loop.
NEED_UPDATE=0
UPDATE_KIND="update"
if [ "$RESTARTED" = 0 ]; then
    [ "$LOCAL_VER" != "$REMOTE_VER" ] && NEED_UPDATE=1
    [ "$FORCE_UPDATE" = 1 ] && NEED_UPDATE=1
    if [ "$NEED_UPDATE" = 0 ]; then
        for p in "${FILE_PATHS[@]}"; do
            if [ ! -f "$SCRIPT_DIR/$p" ]; then
                NEED_UPDATE=1
                UPDATE_KIND="repair"
                break
            fi
        done
    fi
fi

if [ "$NEED_UPDATE" = 0 ]; then
    ui_ok "Up to date" "v$LOCAL_VER"
else
    if [ "$UPDATE_KIND" = "repair" ]; then
        ui_arrow "Repairing missing files"
    elif [ "$FORCE_UPDATE" = 1 ]; then
        ui_arrow "Update check" "latest is $REMOTE_VER"
    else
        ui_arrow "Update available" "$LOCAL_VER → $REMOTE_VER"
    fi
    echo ""

    # Everything goes to a staging folder first; the install is only touched when every
    # file arrived, so a dropped connection can never leave a half update.
    STAGE="$(mktemp -d "${TMPDIR:-/tmp}/linkcatty.XXXXXX")"
    trap 'rm -rf "$STAGE"; exit 130' INT TERM
    TOTAL=${#FILE_PATHS[@]}
    FAILED=0
    i=0
    while [ $i -lt $TOTAL ]; do
        ui_bar "Updating" "$i" "$TOTAL"
        FILE_PATH="${FILE_PATHS[$i]}"
        mkdir -p "$(dirname "$STAGE/$FILE_PATH")"
        if ! fetch_file "$FILE_PATH" "$STAGE/$FILE_PATH"; then
            FAILED=1
            FAILED_FILE="$FILE_PATH"
            break
        fi
        case "$FILE_PATH" in
            *.sh) tr -d '\r' < "$STAGE/$FILE_PATH" > "$STAGE/$FILE_PATH.lf" && mv -f "$STAGE/$FILE_PATH.lf" "$STAGE/$FILE_PATH" ;;
        esac
        i=$((i + 1))
    done
    ui_bar "Updating" "$i" "$TOTAL"
    [ "$IS_TTY" = 1 ] && printf "\n"
    echo ""

    if [ "$FAILED" = 1 ]; then
        rm -rf "$STAGE"
        trap - INT TERM
        ui_warn "Could not download $FAILED_FILE" "$FETCH_ERR"
        ui_note "Nothing was changed. LinkCatty will try again next time you start it."
        echo ""
        sleep 2
    else
        cp -R "$STAGE"/. "$SCRIPT_DIR"/
        rm -rf "$STAGE"
        trap - INT TERM
        chmod +x "$SCRIPT_DIR/uninstall_linkcatty.sh" 2>/dev/null
        printf "%s" "$REMOTE_VER" > "$LOCAL_VERSION_FILE"
        rm -f "$DEPS_MARKER"     # dependencies are re-checked after an update

        ui_ok "Updated to $REMOTE_VER" "restarting"

        # Update the launcher itself. Installed name is "linkcatty", repo name is run.sh.
        # Download to temp, validate, then mv (atomic) so the running bash keeps its old inode.
        LAUNCHER_NEW="$(mktemp "${TMPDIR:-/tmp}/linkcatty_launcher.XXXXXX")"
        if curl -fsSL -o "$LAUNCHER_NEW" "$RAW_BASE/run.sh" && grep -q "LinkCatty Launcher" "$LAUNCHER_NEW"; then
            tr -d '\r' < "$LAUNCHER_NEW" > "$LAUNCHER_NEW.lf" && mv -f "$LAUNCHER_NEW.lf" "$SELF"
        fi
        rm -f "$LAUNCHER_NEW" "$LAUNCHER_NEW.lf"
        chmod +x "$SELF" 2>/dev/null

        sleep 1
        exec "$SELF" --restarted
    fi
fi

# -------------------------------------------------------------------
# 2. Python: find a system Python 3.8+ (no portable Python on macOS/Linux)
# -------------------------------------------------------------------
UNAME="$(uname -s)"

find_python() {
    local cmd path ver
    for cmd in python3 python python3.13 python3.12 python3.11 python3.10 python3.9 python3.8; do
        path="$(command -v "$cmd" 2>/dev/null)" || continue
        # macOS ships a /usr/bin/python3 stub that pops up an installer when the
        # developer tools are missing; do not run it in that case.
        if [ "$UNAME" = "Darwin" ] && [ "$path" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then
            continue
        fi
        ver="$("$cmd" -c "import sys; v=sys.version_info; print(v.major*100+v.minor)" 2>/dev/null)"
        if [ -n "$ver" ] && [ "$ver" -ge 308 ] 2>/dev/null; then
            echo "$cmd"
            return 0
        fi
    done
    return 1
}

PYTHON_EXE="$(find_python)"

if [ -z "$PYTHON_EXE" ]; then
    ui_fail "Python 3.8 or newer was not found"
    if [ "$UNAME" = "Darwin" ]; then
        ui_note "Install it with Homebrew:   brew install python"
        ui_note "or from https://www.python.org/downloads/"
    else
        ui_note "Debian/Ubuntu:  sudo apt install python3 python3-venv"
        ui_note "Fedora/RHEL:    sudo dnf install python3"
        ui_note "Arch:           sudo pacman -S python"
    fi
    echo ""
    read -r -p "  Press Enter to exit..." _
    exit 1
fi
PY_VERSION="$("$PYTHON_EXE" -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>/dev/null)"
ui_ok "Python ready" "$PY_VERSION"

# FFmpeg: downloaded once per OS/arch, never again
download_ffmpeg() {   # os-folder name, release asset name
    local dir="$SCRIPT_DIR/sources/FFmpeg/$1" zip found
    mkdir -p "$dir"
    zip="$dir/ffmpeg_dl.zip"
    if curl -fsSL --retry 2 -o "$zip" "https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/$2" \
        && unzip -q -o "$zip" -d "$dir/extract" 2>/dev/null; then
        found="$(find "$dir/extract" -name ffmpeg -type f 2>/dev/null | head -n1)"
        if [ -n "$found" ]; then
            mv -f "$found" "$dir/ffmpeg"
            chmod +x "$dir/ffmpeg" 2>/dev/null
        fi
    fi
    rm -rf "$dir/extract" "$zip"
    [ -x "$dir/ffmpeg" ]
}

ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
    aarch64|arm64) ARCH_NAME="arm64" ;;
    *) ARCH_NAME="x64" ;;
esac
FFMPEG_DIR=""
if [ "$UNAME" = "Darwin" ]; then
    FFMPEG_DIR="$SCRIPT_DIR/sources/FFmpeg/macos"
    if [ ! -x "$FFMPEG_DIR/ffmpeg" ]; then
        ui_arrow "Getting FFmpeg" "first run only"
        download_ffmpeg "macos" "macos-$ARCH_NAME.zip"
    fi
elif [ "$UNAME" = "Linux" ]; then
    FFMPEG_DIR="$SCRIPT_DIR/sources/FFmpeg/linux"
    if [ ! -x "$FFMPEG_DIR/ffmpeg" ]; then
        ui_arrow "Getting FFmpeg" "first run only"
        download_ffmpeg "linux" "linux-$ARCH_NAME.zip"
    fi
fi
if [ -n "$FFMPEG_DIR" ] && [ -x "$FFMPEG_DIR/ffmpeg" ]; then
    export PATH="$FFMPEG_DIR:$PATH"
elif command -v ffmpeg >/dev/null 2>&1; then
    :
else
    ui_warn "FFmpeg is not available" "video merging and MP3 conversion need it"
fi

# -------------------------------------------------------------------
# 3. Dependencies, kept in a private virtual environment. Homebrew and newer Linux
#    Pythons refuse "pip install" into the system ("externally managed environment").
# -------------------------------------------------------------------
VENV_DIR="$SCRIPT_DIR/sources/.venv"
if [ -f "$DEPS_MARKER" ] && { [ -x "$VENV_DIR/bin/python" ] || [ ! -d "$VENV_DIR" ]; }; then
    ui_ok "Dependencies ready"
else
    ui_arrow "Installing packages" "first run only, one moment"
    RUN_PY="$PYTHON_EXE"
    if [ ! -x "$VENV_DIR/bin/python" ]; then
        rm -rf "$VENV_DIR"
        "$PYTHON_EXE" -m venv "$VENV_DIR" >/dev/null 2>&1 || rm -rf "$VENV_DIR"
    fi
    if [ -x "$VENV_DIR/bin/python" ]; then
        RUN_PY="$VENV_DIR/bin/python"
        PIP_EXTRA=""
    else
        # no venv module (some Debian/Ubuntu installs): fall back to the user site
        PIP_EXTRA="--user --break-system-packages"
    fi
    "$RUN_PY" -m pip install --quiet --upgrade pip $PIP_EXTRA >/dev/null 2>&1 || true
    if "$RUN_PY" -m pip install --quiet --upgrade $PIP_EXTRA yt-dlp spotipy spotdl --no-cache-dir 2>/dev/null \
        || "$RUN_PY" -m pip install --quiet --upgrade --user yt-dlp spotipy spotdl --no-cache-dir; then
        printf "%s" "$LOCAL_VER" > "$DEPS_MARKER"
        ui_ok "Dependencies ready"
    else
        ui_fail "Could not install the packages"
        ui_note "Check your internet connection and start LinkCatty again."
        echo ""
        read -r -p "  Press Enter to exit..." _
        exit 1
    fi
fi
if [ -x "$VENV_DIR/bin/python" ]; then
    PYTHON_EXE="$VENV_DIR/bin/python"
    export PATH="$VENV_DIR/bin:$PATH"
fi
USER_BASE="$("$PYTHON_EXE" -m site --user-base 2>/dev/null)"
[ -n "$USER_BASE" ] && export PATH="$USER_BASE/bin:$PATH"

"$PYTHON_EXE" "$SCRIPT_DIR/sources/LinkCatty.py"
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    ui_fail "LinkCatty stopped unexpectedly" "error code $EXIT_CODE"
    echo ""
    read -r -p "  Press Enter to exit..." _
fi
exit $EXIT_CODE
