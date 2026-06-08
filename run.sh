#!/bin/bash
# LinkCatty Launcher for Linux/macOS
# Production-ready: smart Python detection, no-op on re-runs, cross-platform

# -------------------------------------------------------------------
# Check for uninstall flag
# -------------------------------------------------------------------
if [[ "$*" == *"--uninstall"* ]]; then
    if [ -f "./uninstall_linkcatty.sh" ]; then
        ./uninstall_linkcatty.sh
    elif [ -f "$HOME/.local/share/LinkCatty/uninstall_linkcatty.sh" ]; then
        "$HOME/.local/share/LinkCatty/uninstall_linkcatty.sh"
    else
        echo "Uninstaller not found. Downloading..."
        UNINSTALL_URL="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"
        UNINSTALL_FILE="/tmp/uninstall_linkcatty.sh"
        curl -s -L -o "$UNINSTALL_FILE" "$UNINSTALL_URL"
        if [ -f "$UNINSTALL_FILE" ]; then
            chmod +x "$UNINSTALL_FILE"
            "$UNINSTALL_FILE"
        else
            echo "Failed to download uninstaller."
            read -p "Press Enter to exit..."
        fi
    fi
    exit 0
fi

# -------------------------------------------------------------------
# Resolve script directory (works even when called via symlink)
# -------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "============================================================"
echo "                    LinkCatty Launcher"
echo "============================================================"
echo ""

# -------------------------------------------------------------------
# [1/3] Check for updates
# -------------------------------------------------------------------
echo "[1/3] Checking for updates..."

REMOTE_VERSION_URL="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
LOCAL_VERSION_FILE="$SCRIPT_DIR/sources/version.txt"
DEPS_MARKER="$SCRIPT_DIR/sources/.deps_installed"

if [ -f "$LOCAL_VERSION_FILE" ]; then
    LOCAL_VER=$(tr -d '\r\n' < "$LOCAL_VERSION_FILE" | xargs)
else
    LOCAL_VER="0.0.0"
fi

REMOTE_VER=$(curl -sf --max-time 5 "$REMOTE_VERSION_URL" | tr -d '\r\n' | xargs)
if [ -z "$REMOTE_VER" ]; then
    REMOTE_VER="$LOCAL_VER"
fi

if [ "$LOCAL_VER" != "$REMOTE_VER" ]; then
    echo ""
    echo "============================================================"
    echo "                     UPDATE AVAILABLE!"
    echo "============================================================"
    echo "  Current version : $LOCAL_VER"
    echo "  Latest version  : $REMOTE_VER"
    echo ""
    echo "[2/3] Downloading update..."

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
        "run.sh"
        "uninstall_linkcatty.cmd"
        "uninstall_linkcatty.sh"
    )
    FILE_URLS=(
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.cmd"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.cmd"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"
    )
    TOTAL=${#FILE_PATHS[@]}

    # Backup user data
    [ -f "$SCRIPT_DIR/sources/settings.json" ] && cp "$SCRIPT_DIR/sources/settings.json" "/tmp/settings_backup.json"
    [ -f "$SCRIPT_DIR/sources/download_history.json" ] && cp "$SCRIPT_DIR/sources/download_history.json" "/tmp/download_history_backup.json"

    for i in "${!FILE_PATHS[@]}"; do
        FILE_PATH="${FILE_PATHS[$i]}"
        FILE_URL="${FILE_URLS[$i]}"
        PERCENT=$(( (i+1) * 100 / TOTAL ))
        printf "\rProgress: [%d/%d] %d%%  " "$((i+1))" "$TOTAL" "$PERCENT"
        mkdir -p "$(dirname "$SCRIPT_DIR/$FILE_PATH")"
        curl -s -L -o "$SCRIPT_DIR/$FILE_PATH" "$FILE_URL"
    done
    echo ""

    # Restore user data
    [ -f "/tmp/settings_backup.json" ] && cp "/tmp/settings_backup.json" "$SCRIPT_DIR/sources/settings.json"
    [ -f "/tmp/download_history_backup.json" ] && cp "/tmp/download_history_backup.json" "$SCRIPT_DIR/sources/download_history.json"
    rm -f "/tmp/settings_backup.json" "/tmp/download_history_backup.json"

    printf "%s" "$REMOTE_VER" > "$SCRIPT_DIR/sources/version.txt"

    # Invalidate deps marker so deps reinstall after update
    rm -f "$DEPS_MARKER"

    # Make sure run.sh is executable after update
    chmod +x "$SCRIPT_DIR/run.sh" 2>/dev/null

    echo ""
    echo "[3/3] Update completed. Restarting..."
    sleep 2
    exec "$0"
    exit 0
fi

# -------------------------------------------------------------------
# [2/3] Python setup - NO portable python on Mac/Linux
#        Find system Python 3 (3.8+) or guide user to install it
# -------------------------------------------------------------------
echo "[2/3] Setting up Python..."

UNAME="$(uname -s)"
PYTHON_EXE=""

# Search for python3 / python in PATH, verify it's actually Python 3.8+
find_python() {
    for cmd in python3 python python3.13 python3.12 python3.11 python3.10 python3.9 python3.8; do
        if command -v "$cmd" >/dev/null 2>&1; then
            PY_VER=$("$cmd" -c "import sys; v=sys.version_info; print(v.major*100+v.minor)" 2>/dev/null)
            if [ -n "$PY_VER" ] && [ "$PY_VER" -ge 308 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_EXE=$(find_python)

if [ -z "$PYTHON_EXE" ]; then
    echo ""
    echo "ERROR: Python 3.8+ not found!"
    echo ""
    if [ "$UNAME" = "Darwin" ]; then
        echo "Install Python on macOS with one of:"
        echo "  brew install python          (Homebrew)"
        echo "  https://www.python.org/downloads/"
    elif [ "$UNAME" = "Linux" ]; then
        echo "Install Python on Linux with:"
        echo "  sudo apt install python3      (Debian/Ubuntu)"
        echo "  sudo dnf install python3      (Fedora/RHEL)"
        echo "  sudo pacman -S python         (Arch)"
    fi
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Using Python: $PYTHON_EXE ($($PYTHON_EXE --version 2>&1))"

# Add user scripts dir to PATH so installed tools (yt-dlp etc.) are usable
USER_SCRIPTS=$("$PYTHON_EXE" -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)
if [ -n "$USER_SCRIPTS" ] && [ -d "$USER_SCRIPTS" ]; then
    export PATH="$USER_SCRIPTS:$PATH"
fi
# Also add --user scripts location
USER_BASE=$("$PYTHON_EXE" -m site --user-base 2>/dev/null)
if [ -n "$USER_BASE" ]; then
    export PATH="$USER_BASE/bin:$PATH"
fi

# ── FFmpeg: download once per OS/arch, never again
if [ "$UNAME" = "Darwin" ]; then
    FFMPEG_DIR="$SCRIPT_DIR/sources/FFmpeg/macos"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
    if [ ! -f "$FFMPEG_BIN" ]; then
        echo "Downloading FFmpeg for macOS (first run only)..."
        mkdir -p "$FFMPEG_DIR"
        ARCH_RAW="$(uname -m)"
        if [ "$ARCH_RAW" = "arm64" ]; then
            # Apple Silicon
            curl -L --progress-bar -o "$FFMPEG_DIR/ffmpeg.zip" \
                "https://evermeet.cx/ffmpeg/ffmpeg-7.0.1.zip" 2>&1 || \
            curl -L --progress-bar -o "$FFMPEG_DIR/ffmpeg.zip" \
                "https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/macos-arm64.zip" 2>&1
        else
            curl -L --progress-bar -o "$FFMPEG_DIR/ffmpeg.zip" \
                "https://evermeet.cx/ffmpeg/ffmpeg-7.0.1.zip" 2>&1 || \
            curl -L --progress-bar -o "$FFMPEG_DIR/ffmpeg.zip" \
                "https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/macos-x64.zip" 2>&1
        fi
        if [ -f "$FFMPEG_DIR/ffmpeg.zip" ]; then
            unzip -q "$FFMPEG_DIR/ffmpeg.zip" -d "$FFMPEG_DIR"
            rm -f "$FFMPEG_DIR/ffmpeg.zip"
            chmod +x "$FFMPEG_BIN" 2>/dev/null
        fi
    fi
    [ -f "$FFMPEG_BIN" ] && export PATH="$FFMPEG_DIR:$PATH" || echo "Warning: FFmpeg not available."

elif [ "$UNAME" = "Linux" ]; then
    ARCH_RAW="$(uname -m)"
    FFMPEG_DIR="$SCRIPT_DIR/sources/FFmpeg/linux"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
    if [ ! -f "$FFMPEG_BIN" ]; then
        echo "Downloading FFmpeg for Linux (first run only)..."
        mkdir -p "$FFMPEG_DIR"
        if [ "$ARCH_RAW" = "aarch64" ] || [ "$ARCH_RAW" = "arm64" ]; then
            FFMPEG_URL="https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/linux-arm64.zip"
        else
            FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-git-amd64-static.tar.xz"
        fi
        curl -L --progress-bar -o "$FFMPEG_DIR/ffmpeg_dl" "$FFMPEG_URL"
        if [[ "$FFMPEG_URL" == *.tar.xz ]]; then
            tar -xf "$FFMPEG_DIR/ffmpeg_dl" -C "$FFMPEG_DIR" 2>/dev/null
            EXTRACTED=$(find "$FFMPEG_DIR" -maxdepth 2 -name "ffmpeg" -type f | head -n1)
            if [ -n "$EXTRACTED" ]; then
                cp "$EXTRACTED" "$FFMPEG_BIN"
                rm -rf "$FFMPEG_DIR"/ffmpeg-*/ "$FFMPEG_DIR/ffmpeg_dl"
            fi
        else
            unzip -q "$FFMPEG_DIR/ffmpeg_dl" -d "$FFMPEG_DIR" 2>/dev/null
            EXTRACTED=$(find "$FFMPEG_DIR" -maxdepth 2 -name "ffmpeg" -type f | head -n1)
            [ -n "$EXTRACTED" ] && mv "$EXTRACTED" "$FFMPEG_BIN"
            rm -f "$FFMPEG_DIR/ffmpeg_dl"
        fi
        chmod +x "$FFMPEG_BIN" 2>/dev/null
    fi
    [ -f "$FFMPEG_BIN" ] && export PATH="$FFMPEG_DIR:$PATH" || echo "Warning: FFmpeg not available."
fi

# -------------------------------------------------------------------
# [3/3] Install dependencies (only if not already done)
# -------------------------------------------------------------------
echo "[3/3] Checking dependencies..."

if [ -f "$DEPS_MARKER" ]; then
    echo "Dependencies already installed. Skipping."
else
    echo "Installing packages (first run or after update)..."
    # Upgrade pip
    "$PYTHON_EXE" -m pip install --quiet --upgrade pip --no-warn-script-location 2>/dev/null || true
    # Install deps
    if "$PYTHON_EXE" -m pip install --quiet --upgrade yt-dlp spotipy spotdl \
        --no-warn-script-location --no-cache-dir; then
        # Re-source user scripts after install
        USER_BASE=$("$PYTHON_EXE" -m site --user-base 2>/dev/null)
        [ -n "$USER_BASE" ] && export PATH="$USER_BASE/bin:$PATH"
        printf "%s" "$LOCAL_VER" > "$DEPS_MARKER"
        echo "Packages installed successfully."
    else
        echo "ERROR: Failed to install some packages. Check your internet connection."
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

echo ""
echo "Launching LinkCatty..."
echo ""

"$PYTHON_EXE" "$SCRIPT_DIR/sources/LinkCatty.py"
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "Application exited with error code $EXIT_CODE"
fi
read -p "Press Enter to exit..."
exit $EXIT_CODE