#!/bin/bash
# LinkCatty Launcher for Linux/macOS with auto-update

echo "Checking for updates..."
REMOTE_VERSION_URL="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
LOCAL_VERSION_FILE="./sources/version.txt"

# Read local version (trim whitespace and carriage return)
if [ -f "$LOCAL_VERSION_FILE" ]; then
    LOCAL_VER=$(tr -d '\r\n' < "$LOCAL_VERSION_FILE")
else
    LOCAL_VER="0.0.0"
fi

REMOTE_VER=$(curl -s "$REMOTE_VERSION_URL" | tr -d '\r\n')

if [ -z "$REMOTE_VER" ]; then
    echo "Warning: Could not check for updates."
    REMOTE_VER="$LOCAL_VER"
fi

echo "Local version: [$LOCAL_VER]"
echo "Remote version: [$REMOTE_VER]"

if [ "$LOCAL_VER" != "$REMOTE_VER" ]; then
    echo ""
    echo "============================================================"
    echo "                     UPDATE AVAILABLE!"
    echo "============================================================"
    echo "Current Version: $LOCAL_VER"
    echo "Latest Version:  $REMOTE_VER"
    echo ""
    echo "Downloading updated files..."

    # Define all files to update
    declare -a FILE_PATHS=(
        "sources/downloaders/spotify_downloader.py"
        "sources/downloaders/youtube_downloader.py"
        "sources/utils/config.py"
        "sources/utils/ffmpeg.py"
        "sources/utils/logger.py"
        "sources/utils/ui.py"
        "sources/requirements.txt"
        "sources/version.txt"
        "run.bat"
        "run.sh"
    )

    declare -a FILE_URLS=(
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.bat"
        "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"
    )

    # Backup protected files
    [ -f "./sources/settings.json" ] && cp "./sources/settings.json" "/tmp/settings_backup.json"
    [ -f "./sources/download_history.json" ] && cp "./sources/download_history.json" "/tmp/download_history_backup.json"
    [ -f "./sources/PortablePython.zip" ] && cp "./sources/PortablePython.zip" "/tmp/PortablePython_backup.zip"

    # Download and update each file
    for i in "${!FILE_PATHS[@]}"; do
        FILE_PATH="${FILE_PATHS[$i]}"
        FILE_URL="${FILE_URLS[$i]}"
        mkdir -p "$(dirname "$FILE_PATH")"
        curl -s -L -o "$FILE_PATH" "$FILE_URL"
    done

    # Restore protected files
    [ -f "/tmp/settings_backup.json" ] && cp "/tmp/settings_backup.json" "./sources/settings.json"
    [ -f "/tmp/download_history_backup.json" ] && cp "/tmp/download_history_backup.json" "./sources/download_history.json"
    [ -f "/tmp/PortablePython_backup.zip" ] && cp "/tmp/PortablePython_backup.zip" "./sources/PortablePython.zip"

    # Cleanup backup
    rm -f "/tmp/settings_backup.json" "/tmp/download_history_backup.json" "/tmp/PortablePython_backup.zip"

    echo "Update completed. Restarting..."
    sleep 2
    exec "$0"
    exit 0
fi

# -------------------------------------------------------------------
# Continue with normal launch
# -------------------------------------------------------------------
echo ""
echo "============================================================"
echo "                    LinkCatty Setup"
echo "============================================================"
echo ""

PORTABLE_DIR="./sources/portable_python"
if [ ! -d "$PORTABLE_DIR" ] || [ -z "$(ls -A "$PORTABLE_DIR")" ]; then
    echo "📦 Extracting Portable Python..."
    if [ ! -f "./sources/PortablePython.zip" ]; then
        echo "❌ Error: sources/PortablePython.zip not found!"
        read -p "Press Enter to exit..."
        exit 1
    fi
    mkdir -p "$PORTABLE_DIR"
    unzip -q "./sources/PortablePython.zip" -d "$PORTABLE_DIR"
    # If a single subfolder exists, move contents up
    SUBDIR=$(find "$PORTABLE_DIR" -maxdepth 1 -type d | tail -n +2 | head -n1)
    if [ -n "$SUBDIR" ] && [ -f "$SUBDIR/python.exe" -o -f "$SUBDIR/bin/python" ]; then
        mv "$SUBDIR"/* "$PORTABLE_DIR/" 2>/dev/null
        rmdir "$SUBDIR" 2>/dev/null
    fi
    echo "✅ Portable Python ready."
fi

# Find python executable
PYTHON_EXE=""
if [ -f "$PORTABLE_DIR/bin/python3" ]; then
    PYTHON_EXE="$PORTABLE_DIR/bin/python3"
elif [ -f "$PORTABLE_DIR/bin/python" ]; then
    PYTHON_EXE="$PORTABLE_DIR/bin/python"
elif [ -f "$PORTABLE_DIR/python.exe" ]; then
    PYTHON_EXE="$PORTABLE_DIR/python.exe"
else
    PYTHON_EXE=$(find "$PORTABLE_DIR" -name "python3" -o -name "python" -o -name "python.exe" | head -n1)
fi

if [ -z "$PYTHON_EXE" ]; then
    echo "❌ Python not found in extracted folder."
    read -p "Press Enter to exit..."
    exit 1
fi

# Add to PATH
if [ -d "$PORTABLE_DIR/bin" ]; then
    export PATH="$PORTABLE_DIR/bin:$PATH"
fi
if [ -d "$PORTABLE_DIR/Scripts" ]; then
    export PATH="$PORTABLE_DIR/Scripts:$PATH"
fi

# FFmpeg for macOS/Linux
UNAME=$(uname)
if [ "$UNAME" = "Darwin" ]; then
    FFMPEG_DIR="./sources/FFmpeg/macos"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
    if [ ! -f "$FFMPEG_BIN" ]; then
        echo "📥 Downloading FFmpeg for macOS..."
        mkdir -p "$FFMPEG_DIR"
        curl -L -o "$FFMPEG_DIR/ffmpeg.zip" "https://evermeet.cx/ffmpeg/ffmpeg-7.0.1.zip"
        unzip -q "$FFMPEG_DIR/ffmpeg.zip" -d "$FFMPEG_DIR"
        rm "$FFMPEG_DIR/ffmpeg.zip"
        chmod +x "$FFMPEG_BIN"
    fi
    export PATH="$FFMPEG_DIR:$PATH"
elif [ "$UNAME" = "Linux" ]; then
    FFMPEG_DIR="./sources/FFmpeg/linux"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
    if [ ! -f "$FFMPEG_BIN" ]; then
        echo "📥 Downloading FFmpeg for Linux..."
        mkdir -p "$FFMPEG_DIR"
        curl -L -o "$FFMPEG_DIR/ffmpeg.tar.xz" "https://johnvansickle.com/ffmpeg/releases/ffmpeg-git-amd64-static.tar.xz"
        tar -xf "$FFMPEG_DIR/ffmpeg.tar.xz" -C "$FFMPEG_DIR"
        rm "$FFMPEG_DIR/ffmpeg.tar.xz"
        EXTRACTED_DIR=$(find "$FFMPEG_DIR" -maxdepth 1 -type d -name "ffmpeg-*" | head -n1)
        if [ -n "$EXTRACTED_DIR" ]; then
            mv "$EXTRACTED_DIR/ffmpeg" "$FFMPEG_BIN"
            rm -rf "$EXTRACTED_DIR"
            chmod +x "$FFMPEG_BIN"
        fi
    fi
    export PATH="$FFMPEG_DIR:$PATH"
fi

# Upgrade packages if pip is available
$PYTHON_EXE -m pip --version >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Checking for package updates..."
    $PYTHON_EXE -m pip install --quiet --upgrade yt-dlp spotipy
fi

# Launch
echo ""
echo "🚀 Launching LinkCatty..."
echo ""
$PYTHON_EXE "./sources/LinkCatty.py"
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Application exited with error code $EXIT_CODE"
fi
read -p "Press Enter to exit..."
exit $EXIT_CODE