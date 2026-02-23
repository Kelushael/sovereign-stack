#!/usr/bin/env bash
# install.sh — Sovereign Stack installer
# Usage: bash <(curl -s https://axismundi.fun/install.sh)
#    or: git clone https://github.com/Kelushael/sovereign-stack && cd sovereign-stack && bash install.sh

set -e
REPO="https://github.com/Kelushael/sovereign-stack"
BIN="$HOME/.local/bin"
CFG="$HOME/.config/amallo"
DATA="$HOME/.local/share/amallo"

bold() { printf "\033[1m$1\033[0m\n"; }
ok()   { printf "\033[32m  ✔\033[0m $1\n"; }
info() { printf "\033[36m  ·\033[0m $1\n"; }
warn() { printf "\033[33m  ⚠\033[0m $1\n"; }

bold "\n  ╔══════════════════════════════════╗"
bold "  ║  AMALLO SOVEREIGN STACK INSTALL  ║"
bold "  ╚══════════════════════════════════╝\n"

# Clone if not already in repo
if [ ! -f "axis" ]; then
  info "Cloning sovereign-stack..."
  git clone "$REPO" sovereign-stack
  cd sovereign-stack
fi

mkdir -p "$BIN" "$CFG" "$DATA"

# Install all tools
TOOLS="axis amallo-brain amallo-diffusion amallo-quant sovereign-copilot sovereign-copilot-chat sovereign-ai-assist sovereign-terminal-inject"
for t in $TOOLS; do
  if [ -f "$t" ]; then
    cp "$t" "$BIN/$t"
    chmod +x "$BIN/$t"
    ok "Installed $t → $BIN/$t"
  fi
done

# Ensure ~/.local/bin is in PATH
if ! echo "$PATH" | grep -q "$BIN"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
  warn "Added $BIN to PATH in .bashrc — run: source ~/.bashrc"
fi

# Generate key if none exists
if [ ! -f "$CFG/key" ]; then
  KEY="SOV-$(head -c4 /dev/urandom | xxd -p | tr '[:lower:]' '[:upper:]')-$(head -c4 /dev/urandom | xxd -p | tr '[:lower:]' '[:upper:]')-$(head -c4 /dev/urandom | xxd -p | tr '[:lower:]' '[:upper:]')-$(head -c4 /dev/urandom | xxd -p | tr '[:lower:]' '[:upper:]')"
  echo "$KEY" > "$CFG/key"
  ok "Generated SOV key: $KEY"
fi

# Keybinds (optional)
if command -v xbindkeys &>/dev/null; then
  if [ -f install-keybind.sh ]; then
    bash install-keybind.sh 2>/dev/null && ok "Keybinds installed (Ctrl+Shift+A/C/E/F/T)"
  fi
else
  warn "xbindkeys not found — skipping global keybinds (apt install xbindkeys)"
fi

# tmux copilot (optional)
if command -v tmux &>/dev/null; then
  if [ -f install-copilot.sh ]; then
    bash install-copilot.sh 2>/dev/null && ok "tmux copilot installed (Ctrl+Alt+Space)"
  fi
else
  warn "tmux not found — skipping copilot (apt install tmux)"
fi

bold "\n  ✔ Installation complete!\n"
info "Quick start:"
info "  axis \"hello sovereign node\""
info "  axis --model auto \"write a sorting function\""
info "  axis  (interactive REPL)"
info "  amallo-brain  (start MoE router on :8100)"
info "  amallo-diffusion  (start LLaDA server on :8200)"
info "  amallo-quant  (interactive GGUF quantizer)"
info ""
info "  Terminal: https://axismundi.fun/terminal.html"
info "  Docs:     https://github.com/Kelushael/sovereign-stack"
echo ""
