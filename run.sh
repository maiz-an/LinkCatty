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
            # Download from evermeet.cx
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
            # Download static build from johnvansickle.com
            curl -L -o "$FFMPEG_DIR/ffmpeg.tar.xz" "https://johnvansickle.com/ffmpeg/releases/ffmpeg-git-amd64-static.tar.xz"
            if [ $? -eq 0 ]; then
                tar -xf "$FFMPEG_DIR/ffmpeg.tar.xz" -C "$FFMPEG_DIR"
                rm "$FFMPEG_DIR/ffmpeg.tar.xz"
                # Find the actual binary inside extracted folder
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
    # Add to PATH for this session
    export PATH="$FFMPEG_DIR:$PATH"
fi

# ----- Run the application using portable Python -----
echo ""
echo "🚀 Launching LinkCaty..."
echo ""

./portable_python/bin/python3 LinkCaty.py
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Application exited with error code $EXIT_CODE"
    read -p "Press Enter to exit..."
fi
exit $EXIT_CODE