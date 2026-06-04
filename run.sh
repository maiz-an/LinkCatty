#!/bin/bash
echo "Checking for updates..."
REMOTE_VERSION_URL="https://raw.githubusercontent.com/maiz-an/LinkCatty/refs/heads/main/sources/version.txt"
LOCAL_VERSION_FILE="./sources/version.txt"
UPDATE_AVAILABLE=0

if [ -f "$LOCAL_VERSION_FILE" ]; then
    LOCAL_VER=$(cat "$LOCAL_VERSION_FILE")
    REMOTE_VER=$(curl -s "$REMOTE_VERSION_URL")
    if [ -n "$REMOTE_VER" ] && [ "$LOCAL_VER" != "$REMOTE_VER" ]; then
        UPDATE_AVAILABLE=1
    fi
fi

if [ $UPDATE_AVAILABLE -eq 1 ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "                     UPDATE AVAILABLE!"
    echo "════════════════════════════════════════════════════════════════"
    echo "Current version: $LOCAL_VER"
    echo "Latest version:  $REMOTE_VER"
    echo "Download from: https://github.com/maiz-an/LinkCatty"
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
if [ ! -f "$PORTABLE_DIR/bin/python3" ] && [ ! -f "$PORTABLE_DIR/bin/python" ]; then
    echo "📦 Extracting Portable Python..."
    if [ ! -f "./sources/PortablePython.zip" ]; then
        echo "❌ sources/PortablePython.zip not found!"
        read -p "Press Enter to exit..."
        exit 1
    fi
    unzip -q "./sources/PortablePython.zip" -d "./sources"
    echo "✅ Portable Python extracted."
fi

# Find python
if [ -f "$PORTABLE_DIR/bin/python3" ]; then
    PYTHON_EXE="$PORTABLE_DIR/bin/python3"
elif [ -f "$PORTABLE_DIR/bin/python" ]; then
    PYTHON_EXE="$PORTABLE_DIR/bin/python"
elif [ -f "$PORTABLE_DIR/python.exe" ]; then
    PYTHON_EXE="$PORTABLE_DIR/python.exe"
else
    echo "❌ Python not found."
    read -p "Press Enter to exit..."
    exit 1
fi

export PATH="$PORTABLE_DIR/bin:$PORTABLE_DIR/Scripts:$PATH"

# FFmpeg for macOS/Linux (auto download if missing)
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

echo ""
echo "🚀 Launching LinkCaty..."
echo ""
$PYTHON_EXE LinkCaty.py
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "❌ Exit code: $EXIT_CODE"
fi
read -p "Press Enter to exit..."
exit $EXIT_CODE