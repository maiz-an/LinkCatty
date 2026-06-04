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

# Extract Portable Python into sources/portable_python
PORTABLE_PYTHON_DIR="./sources/portable_python"
if [ ! -f "$PORTABLE_PYTHON_DIR/bin/python3" ]; then
    echo "📦 Extracting Portable Python into sources/portable_python..."
    if [ ! -f "./sources/PortablePython.zip" ]; then
        echo "❌ Error: sources/PortablePython.zip not found!"
        read -p "Press Enter to exit..."
        exit 1
    fi
    mkdir -p "$PORTABLE_PYTHON_DIR"
    unzip -q "./sources/PortablePython.zip" -d "$PORTABLE_PYTHON_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to extract Portable Python."
        read -p "Press Enter to exit..."
        exit 1
    fi
    echo "✅ Portable Python extracted."
fi

PYTHON_EXE="$PORTABLE_PYTHON_DIR/bin/python3"
if [ ! -f "$PYTHON_EXE" ]; then
    echo "❌ python3 not found in $PORTABLE_PYTHON_DIR"
    read -p "Press Enter to exit..."
    exit 1
fi

# Ensure pip is available
$PYTHON_EXE -m ensurepip --upgrade >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "📦 Installing pip via get-pip.py..."
    curl -sS https://bootstrap.pypa.io/get-pip.py -o "$PORTABLE_PYTHON_DIR/get-pip.py"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to download get-pip.py. Please check your internet connection."
        read -p "Press Enter to exit..."
        exit 1
    fi
    $PYTHON_EXE "$PORTABLE_PYTHON_DIR/get-pip.py" --quiet
    rm "$PORTABLE_PYTHON_DIR/get-pip.py"
fi
echo "✅ pip ready."

# Install requirements
echo "📦 Installing required packages from sources/requirements.txt..."
if [ ! -f "./sources/requirements.txt" ]; then
    echo "yt-dlp" > ./sources/requirements.txt
    echo "spotipy" >> ./sources/requirements.txt
fi
$PYTHON_EXE -m pip install -r ./sources/requirements.txt --quiet --upgrade
if [ $? -ne 0 ]; then
    echo "❌ Failed to install required packages. Please check your internet connection."
    read -p "Press Enter to exit..."
    exit 1
fi
echo "✅ Packages ready."

# Setup FFmpeg (macOS/Linux)
UNAME=$(uname)
if [ "$UNAME" = "Darwin" ]; then
    PLATFORM="macos"
    FFMPEG_DIR="./sources/FFmpeg/macos"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
elif [ "$UNAME" = "Linux" ]; then
    PLATFORM="linux"
    FFMPEG_DIR="./sources/FFmpeg/linux"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
else
    PLATFORM=""
fi

if [ -n "$PLATFORM" ] && [ ! -f "$FFMPEG_BIN" ]; then
    echo "📥 FFmpeg not found. Downloading for $PLATFORM..."
    mkdir -p "$FFMPEG_DIR"
    if [ "$PLATFORM" = "macos" ]; then
        curl -L -o "$FFMPEG_DIR/ffmpeg.zip" "https://evermeet.cx/ffmpeg/ffmpeg-7.0.1.zip"
        if [ $? -eq 0 ]; then
            unzip -q "$FFMPEG_DIR/ffmpeg.zip" -d "$FFMPEG_DIR"
            rm "$FFMPEG_DIR/ffmpeg.zip"
            chmod +x "$FFMPEG_BIN"
            echo "✅ FFmpeg downloaded for macOS."
        else
            echo "⚠️ FFmpeg download failed."
        fi
    elif [ "$PLATFORM" = "linux" ]; then
        curl -L -o "$FFMPEG_DIR/ffmpeg.tar.xz" "https://johnvansickle.com/ffmpeg/releases/ffmpeg-git-amd64-static.tar.xz"
        if [ $? -eq 0 ]; then
            tar -xf "$FFMPEG_DIR/ffmpeg.tar.xz" -C "$FFMPEG_DIR"
            rm "$FFMPEG_DIR/ffmpeg.tar.xz"
            EXTRACTED_DIR=$(find "$FFMPEG_DIR" -maxdepth 1 -type d -name "ffmpeg-*" | head -n1)
            if [ -n "$EXTRACTED_DIR" ]; then
                mv "$EXTRACTED_DIR/ffmpeg" "$FFMPEG_BIN"
                rm -rf "$EXTRACTED_DIR"
                chmod +x "$FFMPEG_BIN"
                echo "✅ FFmpeg downloaded for Linux."
            else
                echo "⚠️ Could not locate FFmpeg binary."
            fi
        else
            echo "⚠️ FFmpeg download failed."
        fi
    fi
    export PATH="$FFMPEG_DIR:$PATH"
fi

# Launch the application
echo ""
echo "🚀 Launching LinkCaty..."
echo ""

$PYTHON_EXE LinkCaty.py
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Application exited with error code $EXIT_CODE"
    read -p "Press Enter to exit..."
fi
exit $EXIT_CODE