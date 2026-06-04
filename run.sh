#!/bin/bash
# LinkCaty Launcher for Linux/macOS

echo "Checking for updates..."
REMOTE_VERSION_URL="https://raw.githubusercontent.com/maiz-an/LinkCatty/refs/heads/main/sources/version.txt"
LOCAL_VERSION_FILE="./sources/version.txt"

if [ -f "$LOCAL_VERSION_FILE" ]; then
    LOCAL_VER=$(cat "$LOCAL_VERSION_FILE")
else
    LOCAL_VER="0.0.0"
fi

REMOTE_VER=$(curl -s "$REMOTE_VERSION_URL")

if [ -z "$REMOTE_VER" ]; then
    echo "Warning: Could not check for updates."
    REMOTE_VER="$LOCAL_VER"
fi

if [ "$LOCAL_VER" != "$REMOTE_VER" ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "                     UPDATE AVAILABLE!"
    echo "════════════════════════════════════════════════════════════════"
    echo "Current Version: $LOCAL_VER"
    echo "Latest Version:  $REMOTE_VER"
    echo ""
    echo "Please download the latest version from:"
    echo "https://github.com/maiz-an/LinkCatty"
    echo ""
    read -p "Press Enter to exit..."
    exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "                    LinkCaty Setup"
echo "════════════════════════════════════════════════════════════════"
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
    # Recursive search
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

# Launch
echo ""
echo "🚀 Launching LinkCaty..."
echo ""

$PYTHON_EXE "./sources/LinkCaty.py"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Application exited with error code $EXIT_CODE"
fi
read -p "Press Enter to exit..."
exit $EXIT_CODE