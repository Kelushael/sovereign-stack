#!/usr/bin/env bash
# install.sh — Sovereign Stack installer
# The doctor. Examines your system. Prescribes exactly what fits.
# Usage: bash <(curl -s https://axismundi.fun/install.sh)
#    or: git clone https://github.com/Kelushael/sovereign-stack && cd sovereign-stack && bash install.sh

set -e
REPO="https://github.com/Kelushael/sovereign-stack"
BIN="$HOME/.local/bin"
CFG="$HOME/.config/axis-mundi"
DATA="$HOME/.local/share/amallo"

bold()  { printf "\033[1m$1\033[0m\n"; }
ok()    { printf "\033[32m  ✓\033[0m $1\n"; }
info()  { printf "\033[36m  ·\033[0m $1\n"; }
warn()  { printf "\033[33m  ⚠\033[0m $1\n"; }
rx()    { printf "\033[35m  ℞\033[0m $1\n"; }
skip()  { printf "\033[90m  ✗\033[0m $1\n"; }

bold "\n  ╔════════════════════════════════════════╗"
bold "  ║   SOVEREIGN STACK — SYSTEM DIAGNOSIS   ║"
bold "  ╚════════════════════════════════════════╝\n"

# ── EXAMINE ─────────────────────────────────────────────────────────
info "Examining your system..."

RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024)}' || echo 4000000)
RAM_GB=$(( RAM_KB / 1024 / 1024 ))
[ "$RAM_GB" -lt 1 ] && RAM_GB=1

CPU_CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)

DISK_FREE_KB=$(df "$HOME" 2>/dev/null | tail -1 | awk '{print $4}' || echo 10000000)
DISK_FREE_GB=$(( DISK_FREE_KB / 1024 / 1024 ))

# GPU detection
GPU_VRAM=0
GPU_NAME="none"
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "NVIDIA (unknown)")
    GPU_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo 0)
    GPU_VRAM=$(( GPU_VRAM / 1024 ))  # MB → GB
elif command -v rocm-smi &>/dev/null; then
    GPU_NAME="AMD ROCm GPU"
    GPU_VRAM=8
elif [ -d /proc/driver/nvidia ]; then
    GPU_NAME="NVIDIA (detected)"
    GPU_VRAM=4
fi

OS_NAME=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d'"' -f2 || uname -s)
ARCH=$(uname -m)

printf "\n"
info "  RAM:    ${RAM_GB}GB"
info "  CPU:    ${CPU_CORES} cores  (${ARCH})"
info "  DISK:   ${DISK_FREE_GB}GB free"
if [ "$GPU_NAME" != "none" ]; then
info "  GPU:    ${GPU_NAME}  (${GPU_VRAM}GB VRAM)"
else
info "  GPU:    none (CPU inference)"
fi
info "  OS:     ${OS_NAME}"
printf "\n"

# ── PRESCRIBE ────────────────────────────────────────────────────────
bold "  PRESCRIPTION:\n"

# Model selection based on RAM + GPU
INSTALL_OLLAMA=false
PRIMARY_MODEL=""
SECONDARY_MODEL=""
INSTALL_VISION=false
INSTALL_DIFFUSION=false
INSTALL_QUANT=false
INFERENCE_BACKEND="cpu"

if [ "$GPU_VRAM" -ge 24 ]; then
    INFERENCE_BACKEND="gpu"
    PRIMARY_MODEL="dolphin-mistral"
    SECONDARY_MODEL="glm4"
    INSTALL_VISION=true
    INSTALL_DIFFUSION=true
    INSTALL_QUANT=true
    rx "Primary:    dolphin-mistral (full, GPU-accelerated)"
    rx "Secondary:  glm4 (vision capable)"
    rx "Diffusion:  enabled (${GPU_VRAM}GB VRAM)"
    rx "Quantizer:  enabled"
elif [ "$GPU_VRAM" -ge 8 ]; then
    INFERENCE_BACKEND="gpu"
    PRIMARY_MODEL="dolphin-mistral"
    INSTALL_VISION=true
    rx "Primary:    dolphin-mistral (GPU-accelerated)"
    rx "Vision:     enabled (glm4)"
    skip "Diffusion:  skipped (needs 24GB+ VRAM)"
elif [ "$RAM_GB" -ge 32 ]; then
    PRIMARY_MODEL="dolphin-mistral"
    SECONDARY_MODEL="glm4"
    INSTALL_VISION=true
    INSTALL_QUANT=true
    rx "Primary:    dolphin-mistral (32GB RAM — CPU viable)"
    rx "Secondary:  glm4 (vision)"
    rx "Quantizer:  enabled"
    skip "Diffusion:  skipped (GPU required)"
elif [ "$RAM_GB" -ge 16 ]; then
    PRIMARY_MODEL="dolphin-mistral"
    rx "Primary:    dolphin-mistral (16GB RAM)"
    skip "Vision:     skipped (needs 32GB+ or GPU)"
    skip "Diffusion:  skipped (GPU required)"
elif [ "$RAM_GB" -ge 8 ]; then
    PRIMARY_MODEL="phi4"
    rx "Primary:    phi4 (8GB RAM — lightweight)"
    skip "Vision:     skipped (not enough RAM)"
    skip "Diffusion:  skipped"
else
    PRIMARY_MODEL="deepseek-coder:1.3b"
    rx "Primary:    deepseek-coder:1.3b (minimal — ${RAM_GB}GB RAM)"
    warn "Low RAM detected — only nano model recommended"
    skip "Vision, diffusion, quantizer: all skipped"
fi

INSTALL_OLLAMA=true
rx "Runtime:    Ollama + amallo_controller"
rx "Interface:  axis CLI"
rx "Ports:      8200 (amallo)  8201 (vision-ws)"

if [ "$DISK_FREE_GB" -lt 10 ]; then
    warn "Low disk space (${DISK_FREE_GB}GB) — model downloads may fail"
fi

printf "\n"

# ── INSTALL ──────────────────────────────────────────────────────────
bold "  INSTALLING YOUR STACK...\n"

# Clone if not already in repo
if [ ! -f "axis" ]; then
  info "Cloning sovereign-stack..."
  git clone "$REPO" sovereign-stack
  cd sovereign-stack
fi

mkdir -p "$BIN" "$CFG" "$DATA"

# Install all tools
TOOLS="axis amallo-brain amallo-diffusion amallo-quant amallo-sms amallo-mesh sovereign-copilot sovereign-copilot-chat sovereign-ai-assist sovereign-terminal-inject"
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
info "  axis                              # interactive REPL"
info "  axis \"hello sovereign node\"       # one-shot"
info "  axis --model auto \"write a sort\"  # brain-routed"
info "  /chain                            # toggle 3-step auto macro"
info "  /                                 # command palette"
info "  /addcmd describe what it does     # add custom command"
info ""
info "  amallo-brain       → MoE router   :8100"
info "  amallo-diffusion   → LLaDA server :8200"
info "  amallo-quant       → GGUF quantizer"
info "  amallo-discord     → Discord bot  (needs DISCORD_BOT_TOKEN)"
info "  amallo-sms         → SMS gateway / terminal via text message"
info "  amallo-mesh        → WebSocket IM mesh with terminal room"
info ""
info "  Discord bot setup:"
info "    export DISCORD_BOT_TOKEN=your_token"
info "    python3 ~/.local/bin/amallo-discord"
info ""
info "  SMS TERMINAL (via Twilio):"
info "    export TWILIO_ACCOUNT_SID=ACxxx TWILIO_AUTH_TOKEN=xxx TWILIO_PHONE_NUMBER=+1xxx"
info "    amallo-sms"
info "    Set Twilio webhook → https://axismundi.fun/sms/inbound"
info "    Text commands: /run <bash> | /chat <msg> | /models | /status"
info ""
info "  MESH IM:"
info "    amallo-mesh"
info "    Open https://axismundi.fun/mesh.html"
info "    Join with handle + shared secret (default: amallo)"
info ""
info "  Terminal: https://axismundi.fun/terminal.html"
info "  Docs:     https://github.com/Kelushael/sovereign-stack"
echo ""
