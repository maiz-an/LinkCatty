#!/bin/bash
# LinkCaty Launcher for Linux/macOS

echo "════════════════════════════════════════════════════════════════"
echo "                    LinkCaty Setup"
echo "════════════════════════════════════════════════════════════════"
echo ""

# ----- Extract Portable Python if not present -----
if [ ! -f "portable_python/bin/python3" ]; then
    echo "📦 Extracting Portable Python..."
    if [ ! -f "sources/PortablePython.zip" ]; then
        echo "❌ Error: sources/PortablePython.zip not found!"
        read -p "Press Enter to exit..."
        exit 1
    fi
    unzip -q "sources/PortablePython.zip" -d "portable_python"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to extract Portable Python."
        read -p "Press Enter to exit..."
        exit 1
    fi
    echo "✅ Portable Python extracted."
fi

PYTHON_EXE="portable_python/bin/python3"
if [ ! -f "$PYTHON_EXE" ]; then
    echo "❌ python3 not found in portable_python folder."
    read -p "Press Enter to exit..."
    exit 1
fi

# ----- Ensure pip is available -----
$PYTHON_EXE -m pip --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "📦 Installing pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py -o portable_python/get-pip.py
    if [ $? -ne 0 ]; then
        echo "❌ Failed to download get-pip.py. Please check your internet connection."
        read -p "Press Enter to exit..."
        exit 1
    fi
    $PYTHON_EXE portable_python/get-pip.py --quiet
    rm portable_python/get-pip.py
    echo "✅ pip installed."
fi

# ----- Install required packages from requirements.txt -----
echo "📦 Installing required packages from sources/requirements.txt..."
if [ ! -f "sources/requirements.txt" ]; then
    echo "⚠️ sources/requirements.txt not found. Creating default."
    echo "yt-dlp" > sources/requirements.txt
    echo "spotipy" >> sources/requirements.txt
fi
$PYTHON_EXE -m pip install -r sources/requirements.txt --quiet --upgrade
if [ $? -ne 0 ]; then
    echo "❌ Failed to install required packages. Please check your internet connection."
    read -p "Press Enter to exit..."
    exit 1
fi
echo "✅ Packages ready."

# ----- Determine OS and setup FFmpeg -----
UNAME=$(uname)
if [ "$UNAME" = "Darwin" ]; then
    PLATFORM="macos"
    FFMPEG_DIR="sources/FFmpeg/macos"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
elif [ "$UNAME" = "Linux" ]; then
    PLATFORM="linux"
    FFMPEG_DIR="sources/FFmpeg/linux"
    FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
else
    echo "⚠️ Unsupported OS: $UNAME"
    PLATFORM=""
fi

# ----- Download FFmpeg if missing (macOS / Linux) -----
if [ -n "$PLATFORM" ]; then
    if [ ! -f "$FFMPEG_BIN" ]; then
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
                echo "⚠️ FFmpeg download failed. Audio conversion may not work."
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
                echo "⚠️ FFmpeg download failed. Audio conversion may not work."
            fi
        fi
    else
        echo "✅ FFmpeg found at $FFMPEG_BIN"
    fi
    export PATH="$FFMPEG_DIR:$PATH"
fi

# ----- Run the application -----
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