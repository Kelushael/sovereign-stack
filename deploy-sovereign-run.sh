#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  Deploy sovereign-run to the model node + patch axis-model service
#  to use current.gguf symlink so hot-swaps are zero-config.
#
#  Run from your machine: bash sovereign-stack/deploy-sovereign-run.sh
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

MODEL_NODE="root@187.77.208.28"
MODEL_DIR="/root/axis-mundi/models"
SERVER_BIN="/usr/local/bin/llama-server"
CURRENT_LINK="$MODEL_DIR/current.gguf"
SERVICE="axis-model"
PORT=8181

LIME='\033[38;2;57;255;100m'
CYAN='\033[38;2;0;220;255m'
GOLD='\033[38;2;255;200;50m'
RED='\033[38;2;255;70;70m'
RST='\033[0m'

ok()  { echo -e "${LIME}✓  $*${RST}"; }
inf() { echo -e "${CYAN}→  $*${RST}"; }
hdr() { echo -e "${GOLD}$*${RST}"; }

hdr "\n  DEPLOY: sovereign-run → $MODEL_NODE\n"

# ── 1. Copy sovereign-run script ────────────────────────────────────────────
inf "copying sovereign-run..."
scp sovereign-stack/sovereign-run "$MODEL_NODE:/usr/local/bin/sovereign-run"
ssh "$MODEL_NODE" "chmod +x /usr/local/bin/sovereign-run"
ok "sovereign-run installed at /usr/local/bin/sovereign-run"

# ── 2. Patch axis-model.service to always load current.gguf ─────────────────
inf "patching axis-model.service to use current.gguf symlink..."
ssh "$MODEL_NODE" bash << REMOTE
set -euo pipefail

mkdir -p $MODEL_DIR

# Rewrite the service — ExecStart always points to current.gguf
# sovereign-run manages the symlink; service config never changes on swap
cat > /etc/systemd/system/$SERVICE.service << 'SVCEOF'
[Unit]
Description=Axis Mundi Sovereign Model — loaded via current.gguf
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
Environment=HOME=/root

ExecStart=$SERVER_BIN \\
  --model $CURRENT_LINK \\
  --host 127.0.0.1 \\
  --port $PORT \\
  --ctx-size 16384 \\
  --n-predict -1 \\
  --threads \$(nproc) \\
  --timeout 0 \\
  --parallel 4 \\
  --cont-batching \\
  --flash-attn \\
  --alias axis-model

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
echo "service patched"
REMOTE
ok "axis-model.service patched — always loads current.gguf"

# ── 3. If no current.gguf yet — set one from whatever model exists ───────────
inf "checking for existing model to set as current..."
ssh "$MODEL_NODE" bash << REMOTE
set -euo pipefail
mkdir -p $MODEL_DIR

if [[ ! -L "$CURRENT_LINK" ]]; then
    FIRST_GGUF=\$(ls -1 $MODEL_DIR/*.gguf 2>/dev/null | head -1 || true)
    if [[ -n "\$FIRST_GGUF" ]]; then
        ln -sf "\$FIRST_GGUF" "$CURRENT_LINK"
        echo "  linked: current.gguf → \$(basename \$FIRST_GGUF)"
    else
        echo "  no GGUFs found yet — run: sovereign-run <model-name>"
    fi
else
    echo "  current.gguf already set → \$(readlink -f $CURRENT_LINK | xargs basename)"
fi
REMOTE

# ── 4. Verify ────────────────────────────────────────────────────────────────
echo ""
inf "verifying sovereign-run..."
ssh "$MODEL_NODE" "sovereign-run list"

echo ""
ok "deploy complete"
echo ""
echo "  Now you can do from the glm-bridge shell:"
echo ""
echo "    /run qwen-7b"
echo "    /run deepseek-r1-14b"
echo "    /run llama3-8b"
echo ""
echo "  Or directly on the model node:"
echo ""
echo "    sovereign-run list"
echo "    sovereign-run qwen-7b"
echo ""
