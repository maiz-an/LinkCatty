#!/bin/bash
# LinkCatty Installer for Linux/macOS – clean UI

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
mkdir -p "$TEMP_DIR/sources/downloaders" "$TEMP_DIR/sources/utils"

echo "Downloading files from GitHub..."

# List of files to download
declare -A FILES=(
    ["run.sh"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/run.sh"
    ["uninstall_linkcatty.sh"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/uninstall_linkcatty.sh"
    ["sources/LinkCatty.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/LinkCatty.py"
    ["sources/downloaders/spotify_downloader.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/spotify_downloader.py"
    ["sources/downloaders/youtube_downloader.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/youtube_downloader.py"
    ["sources/downloaders/__init__.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/downloaders/__init__.py"
    ["sources/utils/config.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/config.py"
    ["sources/utils/ffmpeg.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ffmpeg.py"
    ["sources/utils/logger.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/logger.py"
    ["sources/utils/ui.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/ui.py"
    ["sources/utils/__init__.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/utils/__init__.py"
    ["sources/requirements.txt"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/requirements.txt"
    ["sources/version.txt"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/version.txt"
    ["sources/PortablePython.zip"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/PortablePython.zip"
    ["sources/__init__.py"]="https://raw.githubusercontent.com/maiz-an/LinkCatty/main/sources/__init__.py"
)
TOTAL=${#FILES[@]}
CURRENT=0

for FILE_PATH in "${!FILES[@]}"; do
    CURRENT=$((CURRENT + 1))
    PERCENT=$((CURRENT * 100 / TOTAL))
    printf "\rProgress: [%d/%d] %d%%  " "$CURRENT" "$TOTAL" "$PERCENT"
    mkdir -p "$(dirname "$TEMP_DIR/$FILE_PATH")"
    curl -s -L -o "$TEMP_DIR/$FILE_PATH" "${FILES[$FILE_PATH]}"
done

# Download FFmpeg based on OS/architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64) ARCH="x64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

if [ "$OS" = "linux" ]; then
    FFMPEG_ZIP="linux-${ARCH}.zip"
elif [ "$OS" = "darwin" ]; then
    FFMPEG_ZIP="macos-${ARCH}.zip"
else
    echo "Unsupported OS: $OS"; exit 1
fi

FFMPEG_URL="https://github.com/maiz-an/LinkCatty/releases/download/FFmpeg/${FFMPEG_ZIP}"
CURRENT=$((CURRENT + 1))
PERCENT=$((CURRENT * 100 / (TOTAL + 1)))
printf "\rProgress: [%d/%d] %d%% - Downloading FFmpeg... " "$CURRENT" "$((TOTAL + 1))" "$PERCENT"
mkdir -p "$TEMP_DIR/sources/FFmpeg/${OS}/bin"
FFMPEG_ZIP_TEMP="${TEMP_DIR}/ffmpeg.zip"
curl -s -L -o "$FFMPEG_ZIP_TEMP" "$FFMPEG_URL"
if [ $? -eq 0 ]; then
    unzip -q "$FFMPEG_ZIP_TEMP" -d "$TEMP_DIR/ffmpeg_extract"
    FFMPEG_BIN=$(find "$TEMP_DIR/ffmpeg_extract" -name "ffmpeg" -type f | head -n1)
    if [ -n "$FFMPEG_BIN" ]; then
        cp "$FFMPEG_BIN" "$TEMP_DIR/sources/FFmpeg/${OS}/bin/ffmpeg"
        chmod +x "$TEMP_DIR/sources/FFmpeg/${OS}/bin/ffmpeg"
    fi
    rm -rf "$TEMP_DIR/ffmpeg_extract" "$FFMPEG_ZIP_TEMP"
fi
echo " Done"

echo ""
echo "Installing..."

# Remove old installation
rm -rf "$INSTALL_DIR" 2>/dev/null
mkdir -p "$INSTALL_DIR"

# Copy files
cp -rf "$TEMP_DIR"/* "$INSTALL_DIR/"

# Make launcher executable and rename
if [ -f "$INSTALL_DIR/run.sh" ]; then
    mv "$INSTALL_DIR/run.sh" "$INSTALL_DIR/linkcatty"
    chmod +x "$INSTALL_DIR/linkcatty"
fi

# Clean temp
rm -rf "$TEMP_DIR"

# Add to PATH
SHELL_RC="$HOME/.bashrc"
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"
if ! grep -q "export PATH=\"\$PATH:$INSTALL_DIR\"" "$SHELL_RC" 2>/dev/null; then
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$SHELL_RC"
fi

# Desktop shortcut
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

clear
echo ""
echo "============================================================"
echo "               INSTALLATION SUCCESSFUL!"
echo "============================================================"
echo ""
echo "    LinkCatty has been installed to:"
echo "    $INSTALL_DIR"
echo ""
echo "    Run 'linkcatty' from any terminal to start."
echo ""
echo "    Note: Close and reopen your terminal if 'linkcatty' is not recognized."
echo ""
read -p "Press Enter to exit..."