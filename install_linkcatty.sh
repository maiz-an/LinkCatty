#!/bin/bash
# LinkCatty Installer for Linux/macOS – auto-detects architecture

set -e

INSTALL_DIR="$HOME/.local/share/LinkCatty"
TEMP_DIR="/tmp/LinkCatty_temp"

echo ""
echo "============================================================"
echo "                    LinkCatty Installer"
echo "============================================================"
echo ""

if [ -f "$INSTALL_DIR/linkcatty" ]; then
    echo "LinkCatty is already installed."
    read -p "Reinstall/update? (y/n): " OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Clean and prepare
rm -rf "$TEMP_DIR" 2>/dev/null
mkdir -p "$TEMP_DIR" 2>/dev/null

echo "Downloading files from GitHub..."

# Download core files
curl -s -L -o "$TEMP_DIR/run.sh" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"
curl -s -L -o "$TEMP_DIR/sources/LinkCatty.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/LinkCatty.py"
mkdir -p "$TEMP_DIR/sources/downloaders"
curl -s -L -o "$TEMP_DIR/sources/downloaders/spotify_downloader.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
curl -s -L -o "$TEMP_DIR/sources/downloaders/youtube_downloader.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
curl -s -L -o "$TEMP_DIR/sources/downloaders/__init__.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/__init__.py"
mkdir -p "$TEMP_DIR/sources/utils"
curl -s -L -o "$TEMP_DIR/sources/utils/config.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
curl -s -L -o "$TEMP_DIR/sources/utils/ffmpeg.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
curl -s -L -o "$TEMP_DIR/sources/utils/logger.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
curl -s -L -o "$TEMP_DIR/sources/utils/ui.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
curl -s -L -o "$TEMP_DIR/sources/utils/__init__.py" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/__init__.py"
curl -s -L -o "$TEMP_DIR/sources/requirements.txt" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
curl -s -L -o "$TEMP_DIR/sources/version.txt" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
curl -s -L -o "$TEMP_DIR/sources/PortablePython.zip" "https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/PortablePython.zip"

# Detect OS and architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

# Map architecture to our naming
case "$ARCH" in
    x86_64|amd64)
        ARCH="x64"
        ;;
    aarch64|arm64)
        ARCH="arm64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Determine FFmpeg zip file name
if [ "$OS" = "linux" ]; then
    FFMPEG_ZIP="linux-${ARCH}.zip"
elif [ "$OS" = "darwin" ]; then
    FFMPEG_ZIP="macos-${ARCH}.zip"
else
    echo "Unsupported OS: $OS"
    exit 1
fi

FFMPEG_URL="https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/${FFMPEG_ZIP}"
echo "Downloading FFmpeg for ${OS}-${ARCH} from: ${FFMPEG_URL}"

mkdir -p "$TEMP_DIR/sources/FFmpeg/${OS}/bin"
FFMPEG_ZIP_TEMP="${TEMP_DIR}/ffmpeg.zip"

curl -s -L -o "$FFMPEG_ZIP_TEMP" "$FFMPEG_URL"
if [ $? -ne 0 ]; then
    echo "Warning: FFmpeg download failed. Audio conversion may not work."
else
    # Extract and find the ffmpeg binary
    unzip -q "$FFMPEG_ZIP_TEMP" -d "$TEMP_DIR/ffmpeg_extract"
    EXTRACT_DIR="$TEMP_DIR/ffmpeg_extract"
    FFMPEG_BIN=$(find "$EXTRACT_DIR" -name "ffmpeg" -type f | head -n1)
    if [ -n "$FFMPEG_BIN" ]; then
        cp "$FFMPEG_BIN" "$TEMP_DIR/sources/FFmpeg/${OS}/bin/ffmpeg"
        chmod +x "$TEMP_DIR/sources/FFmpeg/${OS}/bin/ffmpeg"
        echo "FFmpeg installed successfully"
    else
        echo "Warning: Could not find ffmpeg binary in the zip"
    fi
    rm -rf "$EXTRACT_DIR"
    rm -f "$FFMPEG_ZIP_TEMP"
fi

echo "Installing..."

# Remove old installation
rm -rf "$INSTALL_DIR" 2>/dev/null
mkdir -p "$INSTALL_DIR" 2>/dev/null

# Copy files
cp -rf "$TEMP_DIR"/* "$INSTALL_DIR/"

# Make launcher executable and rename
if [ -f "$INSTALL_DIR/run.sh" ]; then
    mv "$INSTALL_DIR/run.sh" "$INSTALL_DIR/linkcatty"
    chmod +x "$INSTALL_DIR/linkcatty"
fi

# Clean temp
rm -rf "$TEMP_DIR"

# Add to PATH in .bashrc / .zshrc
SHELL_RC="$HOME/.bashrc"
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
fi

if ! grep -q "export PATH=\"\$PATH:$INSTALL_DIR\"" "$SHELL_RC" 2>/dev/null; then
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$SHELL_RC"
fi

# Create desktop shortcut
DESKTOP_FILE="$HOME/.local/share/applications/LinkCatty.desktop"
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=LinkCatty
Comment=Universal Downloader
Exec=$INSTALL_DIR/linkcatty
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Utility;
EOF

clear
echo ""
echo "    INSTALLATION SUCCESSFUL!"
echo ""
echo "    LinkCatty has been installed to:"
echo "    $INSTALL_DIR"
echo ""
echo "    Run 'linkcatty' from any terminal to start."
echo ""
echo "    Note:"
echo "      Close and reopen your terminal if 'linkcatty' is not recognized."
echo ""
read -p "Press Enter to exit..."