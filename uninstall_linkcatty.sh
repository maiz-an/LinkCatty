#!/bin/bash
# LinkCatty Uninstaller for Linux/macOS
# Works with the bash 3.2 that ships with macOS. This file must keep LF line endings.

INSTALL_DIR="$HOME/.local/share/LinkCatty"
DESKTOP_FILE="$HOME/.local/share/applications/LinkCatty.desktop"
PATH_LINE="export PATH=\"\$PATH:$INSTALL_DIR\""

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_RST=$'\033[0m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'
    C_GR=$'\033[32m'; C_RD=$'\033[31m'; C_YL=$'\033[33m'
else
    C_RST=""; C_DIM=""; C_BOLD=""; C_GR=""; C_RD=""; C_YL=""
fi
RULE=""; _i=0
while [ $_i -lt 58 ]; do RULE="$RULE─"; _i=$((_i + 1)); done

ui_header() {
    echo ""
    printf "  %s- a Maiz's one -%s\n" "$C_DIM" "$C_RST"
    printf "  %s%s%s  %s%s%s\n" "$C_BOLD" "$1" "$C_RST" "$C_DIM" "$2" "$C_RST"
    printf "  %s%s%s\n" "$C_DIM" "$RULE" "$C_RST"
}
ui_line() {
    if [ -n "$4" ]; then
        printf "  %s%s%s %s  %s%s%s\n" "$1" "$2" "$C_RST" "$3" "$C_DIM" "$4" "$C_RST"
    else
        printf "  %s%s%s %s\n" "$1" "$2" "$C_RST" "$3"
    fi
}
ui_ok()   { ui_line "$C_GR" "✔" "$1" "$2"; }
ui_fail() { ui_line "$C_RD" "✖" "$1" "$2"; }
ui_warn() { ui_line "$C_YL" "⚠" "$1" "$2"; }

ask() {
    local ans=""
    if [ "${LINKCATTY_YES:-}" = "1" ]; then echo "y"; return 0; fi
    if [ -r /dev/tty ]; then
        read -r -p "$1" ans < /dev/tty 2>/dev/null || ans=""
    fi
    echo "$ans"
}

ui_header "LinkCatty" "Uninstall"

if [ ! -d "$INSTALL_DIR" ]; then
    ui_warn "LinkCatty is not installed"
    echo ""
    exit 0
fi

echo ""
printf "  %sThis will remove%s\n" "$C_DIM" "$C_RST"
printf "  %s-%s the LinkCatty folder  %s%s%s\n" "$C_DIM" "$C_RST" "$C_DIM" "$INSTALL_DIR" "$C_RST"
printf "  %s-%s its entry in your shell startup files (PATH)\n" "$C_DIM" "$C_RST"
printf "  %s-%s the desktop shortcut and command link, if any\n" "$C_DIM" "$C_RST"
echo ""
printf "  %sYour downloaded files are not touched.%s\n" "$C_DIM" "$C_RST"
echo ""
ANSWER="$(ask "    Continue? (y/n): ")"
case "$ANSWER" in
    [Yy]*) ;;
    *) exit 0 ;;
esac
echo ""

rm -rf "$INSTALL_DIR"
if [ -d "$INSTALL_DIR" ]; then
    ui_fail "Could not remove the folder" "close any running LinkCatty first"
    exit 1
fi
ui_ok "Files removed"

# PATH lines: rewrite each startup file without them (no sed, so paths with "/" are safe)
CLEANED=0
for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile" "$HOME/.config/fish/config.fish"; do
    [ -f "$rc" ] || continue
    if grep -qF "$INSTALL_DIR" "$rc" 2>/dev/null; then
        TMP_RC="$(mktemp "${TMPDIR:-/tmp}/linkcatty_rc.XXXXXX")"
        if grep -vF -e "$INSTALL_DIR" -e "# LinkCatty" "$rc" > "$TMP_RC"; then :; fi
        cat "$TMP_RC" > "$rc"      # keeps the file's permissions and any symlink
        rm -f "$TMP_RC"
        CLEANED=1
    fi
done
if [ "$CLEANED" = 1 ]; then
    ui_ok "Removed from PATH"
else
    ui_ok "Nothing to remove from PATH"
fi

# command links created by the installer
for dir in "$HOME/.local/bin" "$HOME/bin" /opt/homebrew/bin /usr/local/bin; do
    if [ -L "$dir/linkcatty" ]; then
        case "$(readlink "$dir/linkcatty")" in
            "$INSTALL_DIR"/*) rm -f "$dir/linkcatty" ;;
        esac
    fi
done
[ -f "$DESKTOP_FILE" ] && rm -f "$DESKTOP_FILE"
ui_ok "Shortcuts removed"

echo ""
printf "  %s┌ ✔ LINKCATTY IS UNINSTALLED%s\n" "$C_GR" "$C_RST"
printf "  %s│%s  %sOpen a new terminal so the change takes effect.%s\n" "$C_GR" "$C_RST" "$C_DIM" "$C_RST"
printf "  %s└%s\n" "$C_GR" "$C_RST"
echo ""
