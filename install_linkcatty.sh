#!/bin/bash
# LinkCatty Installer for Linux/macOS

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

# Download files (simplified list)
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
curl -s -L -o "$TEMP_DIR/sources/PortablePython.zip" "https://github.com/maiz-an/LinkCatty/releases/download/v1.0/PortablePython.zip"
mkdir -p "$TEMP_DIR/sources/FFmpeg/linux/bin"
curl -s -L -o "$TEMP_DIR/sources/FFmpeg/linux/bin/ffmpeg" "https://github.com/maiz-an/LinkCatty/releases/download/v1.0/ffmpeg-linux" 2>/dev/null || echo "FFmpeg not available, will download later"

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