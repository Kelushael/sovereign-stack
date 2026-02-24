#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════╗
# ║  SOVEREIGN STACK — ONE LINE INSTALL                  ║
# ║  curl -fsSL https://raw.githubusercontent.com/       ║
# ║  Kelushael/sovereign-stack/main/install.sh | bash    ║
# ╚══════════════════════════════════════════════════════╝
set -e
REPO="https://github.com/Kelushael/sovereign-stack"
INSTALL_DIR="$HOME/.sovereign"
BIN_DIR="$HOME/.local/bin"

echo "⚡ Sovereign Stack installer"
echo "────────────────────────────"

# deps
OS=$(uname -s)
if [[ "$OS" == "Linux" ]]; then
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y -qq git python3 python3-pip curl ollama 2>/dev/null || true
  fi
fi

# clone or update
if [[ -d "$INSTALL_DIR" ]]; then
  echo "↻  Updating existing install..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "↓  Cloning sovereign-stack..."
  git clone "$REPO" "$INSTALL_DIR"
fi

# install python deps
pip3 install -q vosk sounddevice requests faster-whisper --break-system-packages 2>/dev/null || \
pip3 install -q vosk sounddevice requests faster-whisper 2>/dev/null || true

# link all commands
mkdir -p "$BIN_DIR"
for cmd in axis amallo oracle nexus marshal screenwatch voice; do
  src="$INSTALL_DIR/$cmd"
  [[ -f "$src" ]] && chmod +x "$src" && ln -sfn "$src" "$BIN_DIR/$cmd" && echo "  ✓ $cmd"
done

# PATH
if ! grep -q "$BIN_DIR" "$HOME/.bashrc" 2>/dev/null; then
  echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$HOME/.bashrc"
fi
if ! grep -q "$BIN_DIR" "$HOME/.zshrc" 2>/dev/null; then
  echo "export PATH=\"$BIN_DIR:\$PATH\"" >> "$HOME/.zshrc" 2>/dev/null || true
fi

echo ""
echo "✅ Done. Run: axis"
echo "   Restart shell or: source ~/.bashrc"
