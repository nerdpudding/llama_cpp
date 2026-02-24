#!/bin/bash
# Install claude-local: copies config files and wrapper script to the right places.
# Run this after cloning the repo on a new machine.
#
# What it does:
#   1. Checks prerequisites (claude, bubblewrap, socat)
#   2. Copies home/ contents to ~/.claude-local/
#   3. Creates IDE symlink (~/.claude-local/ide → ~/.claude/ide) for VS Code integration
#   4. Copies bin/claude-local to ~/bin/ and ensures ~/bin is in PATH
#
# Re-run this script after updating files in the repo to sync changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_HOME="$HOME/.claude-local"
TARGET_BIN="$HOME/bin"

echo "=== claude-local installer ==="
echo ""

# Check prerequisites
MISSING=()
command -v claude >/dev/null 2>&1 || MISSING+=("claude (Claude Code CLI)")
command -v bwrap >/dev/null 2>&1 || MISSING+=("bubblewrap (sudo apt install bubblewrap)")
command -v socat >/dev/null 2>&1 || MISSING+=("socat (sudo apt install socat)")

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "Missing prerequisites:"
    for m in "${MISSING[@]}"; do
        echo "  - $m"
    done
    echo ""
    echo "Install the missing packages and try again."
    exit 1
fi

# Copy home/ contents to ~/.claude-local/
echo "Copying config files to $TARGET_HOME/ ..."
mkdir -p "$TARGET_HOME/skills/project-setup"
cp "$SCRIPT_DIR/home/CLAUDE.md" "$TARGET_HOME/CLAUDE.md"
cp "$SCRIPT_DIR/home/settings.json" "$TARGET_HOME/settings.json"
cp "$SCRIPT_DIR/home/skills/project-setup/SKILL.md" "$TARGET_HOME/skills/project-setup/SKILL.md"
echo "  Done."

# Create IDE symlink for VS Code integration
# The VS Code extension writes lock files to ~/.claude/ide/ (hardcoded).
# With CLAUDE_CONFIG_DIR, Claude Code looks for them in ~/.claude-local/ide/.
# Without this symlink, /ide detection fails and diffs open in terminal instead
# of VS Code. See: https://github.com/anthropics/claude-code/issues/4739
if [ ! -e "$TARGET_HOME/ide" ]; then
    if [ -d "$HOME/.claude/ide" ]; then
        echo "Creating IDE symlink ($TARGET_HOME/ide → $HOME/.claude/ide) ..."
        ln -s "$HOME/.claude/ide" "$TARGET_HOME/ide"
        echo "  Done."
    else
        echo "Creating IDE directory symlink (will activate when VS Code extension runs) ..."
        mkdir -p "$HOME/.claude/ide"
        ln -s "$HOME/.claude/ide" "$TARGET_HOME/ide"
        echo "  Done."
    fi
else
    echo "IDE symlink already exists, skipping."
fi

# Copy wrapper script to ~/bin/
echo "Copying claude-local to $TARGET_BIN/ ..."
mkdir -p "$TARGET_BIN"
cp "$SCRIPT_DIR/bin/claude-local" "$TARGET_BIN/claude-local"
chmod +x "$TARGET_BIN/claude-local"
echo "  Done."

# Check if ~/bin is in PATH
if [[ ":$PATH:" != *":$TARGET_BIN:"* ]]; then
    echo ""
    echo "WARNING: $TARGET_BIN is not in your PATH."
    echo "Add this to your ~/.bashrc or ~/.zshrc:"
    echo ""
    echo "  export PATH=\"\$HOME/bin:\$PATH\""
    echo ""
    echo "Then restart your shell or run: source ~/.bashrc"
fi

echo ""
echo "Installation complete."
echo "Start a local Claude Code session with: claude-local"
echo "Make sure llama-server is running on localhost:8080 first."
