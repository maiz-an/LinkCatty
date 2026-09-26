#!/bin/bash
# LinkCatty Installer for Linux/macOS
# Works with the bash 3.2 that ships with macOS (no associative arrays, no bash 4 features).
# This file must keep LF line endings (see .gitattributes).

INSTALL_DIR="$HOME/.local/share/LinkCatty"
UNAME="$(uname -s)"

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
ui_row()   { printf "  %s│%s  %s%-10s%s %s\n" "$C_GR" "$C_RST" "$C_DIM" "$1" "$C_RST" "$2"; }
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

ask() {         # prompt -> answer (empty when there is no terminal; LINKCATTY_YES=1 answers y)
    local ans=""
    if [ "${LINKCATTY_YES:-}" = "1" ]; then echo "y"; return 0; fi
    if [ -r /dev/tty ]; then
        read -r -p "$1" ans < /dev/tty 2>/dev/null || ans=""
    fi
    echo "$ans"
}

unzip_to() {    # zip, folder
    if command -v unzip >/dev/null 2>&1; then
        unzip -q -o "$1" -d "$2" 2>/dev/null
    else
        python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$1" "$2" 2>/dev/null
    fi
}

ui_header "LinkCatty" "Setup"

if [ -f "$INSTALL_DIR/linkcatty" ]; then
    ui_warn "LinkCatty is already installed"
    ANSWER="$(ask "    Reinstall / update? (y/n): ")"
    case "$ANSWER" in
        [Yy]*) ;;
        *) exit 0 ;;
    esac
    echo ""
fi

# raw.githubusercontent.com caches "main" for ~5 minutes. Ask git (never cached) for the
# latest commit and download every file from that exact commit, so a fresh install can
# never mix files of two versions. Falls back to "main".
REF="main"
LATEST_SHA="$(curl -sf --max-time 8 "https://github.com/maiz-an/LinkCatty.git/info/refs?service=git-upload-pack" 2>/dev/null \
    | grep -a -o '[0-9a-f]\{40\} refs/heads/main' | head -n1 | cut -c1-40)"
if [ "${#LATEST_SHA}" -eq 40 ] && echo "$LATEST_SHA" | grep -q '^[0-9a-f]*$'; then
    REF="$LATEST_SHA"
fi
RAW_BASE="https://raw.githubusercontent.com/maiz-an/LinkCatty/$REF"

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/linkcatty_setup.XXXXXX")"
trap 'rm -rf "$TEMP_DIR"; exit 130' INT TERM

# Files to download (paths relative to the repository root)
FILES=(
    "run.sh"
    "run.cmd"
    "uninstall_linkcatty.sh"
    "uninstall_linkcatty.cmd"
    "sources/LinkCatty.py"
    "sources/downloaders/spotify_downloader.py"
    "sources/downloaders/youtube_downloader.py"
    "sources/downloaders/other_downloader.py"
    "sources/downloaders/universal.py"
    "sources/downloaders/__init__.py"
    "sources/utils/config.py"
    "sources/utils/ffmpeg.py"
    "sources/utils/logger.py"
    "sources/utils/ui.py"
    "sources/utils/__init__.py"
    "sources/requirements.txt"
    "sources/version.txt"
)
TOTAL=${#FILES[@]}
STEPS=$((TOTAL + 1))

i=0
FAILED_FILE=""
while [ $i -lt $TOTAL ]; do
    ui_bar "Downloading" "$i" "$STEPS"
    F="${FILES[$i]}"
    mkdir -p "$(dirname "$TEMP_DIR/$F")"
    if ! curl -fsSL --retry 2 --connect-timeout 15 --max-time 120 -o "$TEMP_DIR/$F" "$RAW_BASE/$F"; then
        FAILED_FILE="$F"
        break
    fi
    case "$F" in
        *.sh) tr -d '\r' < "$TEMP_DIR/$F" > "$TEMP_DIR/$F.lf" && mv -f "$TEMP_DIR/$F.lf" "$TEMP_DIR/$F" ;;
    esac
    i=$((i + 1))
done

if [ -n "$FAILED_FILE" ]; then
    [ "$IS_TTY" = 1 ] && printf "\n"
    echo ""
    ui_fail "Could not download $FAILED_FILE"
    ui_note "Check your internet connection and run the installer again."
    ui_note "Nothing was changed on your computer."
    rm -rf "$TEMP_DIR"
    echo ""
    exit 1
fi

# FFmpeg (a failure here is not fatal: audio downloads still work)
ui_bar "Downloading" "$TOTAL" "$STEPS"
case "$(uname -m)" in
    aarch64|arm64) ARCH_NAME="arm64" ;;
    x86_64|amd64) ARCH_NAME="x64" ;;
    *) ARCH_NAME="" ;;
esac
FFMPEG_OK=0
case "$UNAME" in
    Darwin) FF_OS="macos" ;;
    Linux)  FF_OS="linux" ;;
    *)      FF_OS="" ;;
esac
if [ -n "$FF_OS" ] && [ -n "$ARCH_NAME" ]; then
    FF_DIR="$TEMP_DIR/sources/FFmpeg/$FF_OS"
    mkdir -p "$FF_DIR"
    if curl -fsSL --retry 2 --connect-timeout 15 --max-time 300 -o "$TEMP_DIR/ffmpeg.zip" \
            "https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/$FF_OS-$ARCH_NAME.zip" \
        && unzip_to "$TEMP_DIR/ffmpeg.zip" "$TEMP_DIR/ffmpeg_extract"; then
        FOUND="$(find "$TEMP_DIR/ffmpeg_extract" -name ffmpeg -type f 2>/dev/null | head -n1)"
        if [ -n "$FOUND" ]; then
            # the app and the launcher look for  sources/FFmpeg/<macos|linux>/ffmpeg
            cp "$FOUND" "$FF_DIR/ffmpeg"
            chmod +x "$FF_DIR/ffmpeg"
            FFMPEG_OK=1
        fi
    fi
    rm -rf "$TEMP_DIR/ffmpeg_extract" "$TEMP_DIR/ffmpeg.zip"
fi
ui_bar "Downloading" "$STEPS" "$STEPS"
[ "$IS_TTY" = 1 ] && printf "\n"
echo ""

# -------------------------------------------------------------------
# Install (settings and history survive a reinstall)
# -------------------------------------------------------------------
ui_arrow "Installing"
KEEP="$(mktemp -d "${TMPDIR:-/tmp}/linkcatty_keep.XXXXXX")"
[ -f "$INSTALL_DIR/sources/settings.json" ] && cp "$INSTALL_DIR/sources/settings.json" "$KEEP/"
[ -f "$INSTALL_DIR/sources/download_history.json" ] && cp "$INSTALL_DIR/sources/download_history.json" "$KEEP/"

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
if ! cp -R "$TEMP_DIR"/. "$INSTALL_DIR"/; then
    ui_fail "Could not copy the files"
    rm -rf "$TEMP_DIR" "$KEEP"
    exit 1
fi
mv -f "$INSTALL_DIR/run.sh" "$INSTALL_DIR/linkcatty"
chmod +x "$INSTALL_DIR/linkcatty" "$INSTALL_DIR/uninstall_linkcatty.sh"
[ -f "$KEEP/settings.json" ] && cp "$KEEP/settings.json" "$INSTALL_DIR/sources/settings.json"
[ -f "$KEEP/download_history.json" ] && cp "$KEEP/download_history.json" "$INSTALL_DIR/sources/download_history.json"
rm -rf "$TEMP_DIR" "$KEEP"
trap - INT TERM

# -------------------------------------------------------------------
# Make the "linkcatty" command available
#   1. PATH line in the rc file of YOUR shell (zsh is the macOS default and does not
#      read ~/.bashrc), plus any other rc file that already exists
#   2. a symlink in a folder that is already on PATH and writable, so the command
#      also works in the terminal you are using right now
# -------------------------------------------------------------------
PATH_LINE="export PATH=\"\$PATH:$INSTALL_DIR\""
PATH_FILES=""
add_path_to() {
    local rc="$1"
    if [ ! -f "$rc" ]; then
        mkdir -p "$(dirname "$rc")" && : > "$rc" || return 1
    fi
    if ! grep -qF "$PATH_LINE" "$rc" 2>/dev/null; then
        if [ -s "$rc" ] && [ -n "$(tail -c1 "$rc" 2>/dev/null)" ]; then printf "\n" >> "$rc"; fi
        printf "# LinkCatty\n%s\n" "$PATH_LINE" >> "$rc" || return 1
    fi
    PATH_FILES="$PATH_FILES $rc"
    return 0
}

SHELL_NAME="$(basename "${SHELL:-/bin/bash}")"
case "$SHELL_NAME" in
    zsh)  add_path_to "$HOME/.zshrc" ;;
    bash) if [ "$UNAME" = "Darwin" ]; then add_path_to "$HOME/.bash_profile"; else add_path_to "$HOME/.bashrc"; fi ;;
    fish)
        FISH_CONF="$HOME/.config/fish/config.fish"
        mkdir -p "$(dirname "$FISH_CONF")"
        if ! grep -qF "$INSTALL_DIR" "$FISH_CONF" 2>/dev/null; then
            printf "# LinkCatty\nset -gx PATH \$PATH \"%s\"\n" "$INSTALL_DIR" >> "$FISH_CONF"
        fi
        PATH_FILES="$PATH_FILES $FISH_CONF"
        ;;
    *)    add_path_to "$HOME/.profile" ;;
esac
for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
    [ -f "$rc" ] && add_path_to "$rc"
done

LINKED_IN=""
OLD_IFS="$IFS"; IFS=":"
set -- $PATH
IFS="$OLD_IFS"
for dir in "$@"; do
    case "$dir" in
        "$HOME/.local/bin"|"$HOME/bin"|/opt/homebrew/bin|/usr/local/bin)
            if [ -d "$dir" ] && [ -w "$dir" ] && { [ ! -e "$dir/linkcatty" ] || [ -L "$dir/linkcatty" ]; }; then
                if ln -sf "$INSTALL_DIR/linkcatty" "$dir/linkcatty" 2>/dev/null; then
                    LINKED_IN="$dir"
                    break
                fi
            fi
            ;;
    esac
done

# Desktop entry (Linux only)
if [ "$UNAME" = "Linux" ]; then
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/LinkCatty.desktop" << EOF
[Desktop Entry]
Name=LinkCatty
Comment=Universal Downloader
Exec=$INSTALL_DIR/linkcatty
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Utility;
EOF
fi

INSTALLED_VER="$(tr -d '\r\n ' < "$INSTALL_DIR/sources/version.txt" 2>/dev/null)"
ui_ok "LinkCatty is installed" "v${INSTALLED_VER:-?}"
if [ "$FFMPEG_OK" = 0 ]; then
    ui_warn "FFmpeg could not be downloaded" "it is fetched on first start; video merging needs it"
fi
if [ -z "$PATH_FILES" ] && [ -z "$LINKED_IN" ]; then
    ui_warn "Could not add LinkCatty to your PATH" "start it with the full path below"
fi

echo ""
printf "  %s┌ ✔ READY%s\n" "$C_GR" "$C_RST"
ui_row "Location" "$INSTALL_DIR"
ui_row "Downloads" "your Downloads folder, in a LinkCatty folder"
if [ -n "$LINKED_IN" ]; then
    ui_row "Start" "type  ${C_BOLD}linkcatty${C_RST}"
else
    FIRST_RC="$(echo "$PATH_FILES" | awk '{print $1}')"
    ui_row "Start" "open a NEW terminal window and type  ${C_BOLD}linkcatty${C_RST}"
    case "$FIRST_RC" in
        "$HOME"/*) SHOW_RC="~${FIRST_RC#$HOME}" ;;
        *) SHOW_RC="$FIRST_RC" ;;
    esac
    [ -n "$FIRST_RC" ] && ui_row "" "or right now:  ${C_BOLD}source $SHOW_RC${C_RST}"
    ui_row "" "or use the full path:  $INSTALL_DIR/linkcatty"
fi
printf "  %s└%s\n" "$C_GR" "$C_RST"
echo ""

ANSWER="$(ask "    Start LinkCatty now? (Y/n): ")"
case "$ANSWER" in
    [Nn]*) exit 0 ;;
esac
exec "$INSTALL_DIR/linkcatty"
