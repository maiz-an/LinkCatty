#!/bin/bash
# LinkCatty Uninstaller for Linux/macOS

set -e

INSTALL_DIR="$HOME/.local/share/LinkCatty"
DESKTOP_FILE="$HOME/.local/share/applications/LinkCatty.desktop"
SHELL_RC="$HOME/.bashrc"
[ -f "$HOME/.zshrc" ] && SHELL_RC="$HOME/.zshrc"

echo ""
echo "============================================================"
echo "                  LinkCatty Uninstaller"
echo "============================================================"
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
    echo "LinkCatty is not installed."
    exit 0
fi

echo "This will remove:"
echo "  - Installation folder: $INSTALL_DIR"
echo "  - From user PATH (in $SHELL_RC)"
echo "  - Desktop shortcut"
echo ""
read -p "Continue? (y/n): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    exit 0
fi

echo ""
echo "[1/3] Removing files..."
rm -rf "$INSTALL_DIR"
if [ -d "$INSTALL_DIR" ]; then
    echo "[ERROR] Could not remove folder. Close any running LinkCatty processes."
    exit 1
fi
echo "[1/3] Done."

echo "[2/3] Removing from PATH..."
if [ -f "$SHELL_RC" ]; then
    sed -i.bak "/export PATH=\"\$PATH:$INSTALL_DIR\"/d" "$SHELL_RC"
    echo "Removed from $SHELL_RC"
else
    echo "[WARNING] Shell config file not found. PATH not modified."
fi
echo "[2/3] Done."

echo "[3/3] Removing desktop shortcut..."
if [ -f "$DESKTOP_FILE" ]; then
    rm -f "$DESKTOP_FILE"
    echo "Removed desktop shortcut"
else
    echo "No desktop shortcut found"
fi
echo "[3/3] Done."

echo ""
echo "    UNINSTALL COMPLETE!"
echo ""
echo "    You may need to restart your terminal for changes to take effect."
echo ""
read -p "    Press Enter to exit..."