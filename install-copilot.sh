#!/bin/bash
# Install Sovereign AI Copilot - Split Pane Mode

set -e

echo "🚀 Installing Sovereign AI Copilot (Split Pane Mode)..."
echo ""

# ── Check tmux ─────────────────────────────────────────────────
if ! command -v tmux >/dev/null; then
    echo "📦 Installing tmux..."
    sudo apt update && sudo apt install -y tmux
fi

# ── Install scripts ────────────────────────────────────────────
echo "📁 Installing scripts..."
cp sovereign-copilot ~/.local/bin/
cp sovereign-copilot-chat ~/.local/bin/
chmod +x ~/.local/bin/sovereign-copilot
chmod +x ~/.local/bin/sovereign-copilot-chat
echo "  ✓ Installed to ~/.local/bin/"

# ── Configure tmux ─────────────────────────────────────────────
echo "⚙️  Configuring tmux..."

if [[ ! -f ~/.tmux.conf ]]; then
    touch ~/.tmux.conf
fi

# Check if already configured
if ! grep -q "sovereign-copilot" ~/.tmux.conf; then
    cat >> ~/.tmux.conf << 'EOF'

# ── Sovereign AI Copilot ──────────────────────────────────────
# Ctrl+Alt+Space: Toggle AI assistant in split pane
bind-key -n C-M-Space run-shell "~/.local/bin/sovereign-copilot toggle"

# Ctrl+Alt+H: Show help
bind-key -n C-M-h display-message "Copilot: Ctrl+Alt+Space=toggle | Type in AI pane for help"
EOF
    echo "  ✓ Added keybinds to ~/.tmux.conf"
else
    echo "  ⚠ Keybinds already in ~/.tmux.conf"
fi

# Reload tmux config if in session
if [[ -n "$TMUX" ]]; then
    tmux source-file ~/.tmux.conf
    echo "  ✓ Reloaded tmux config"
fi

# ── API Key ────────────────────────────────────────────────────
echo "🔑 Checking API key..."
if [[ -f ~/.config/amallo/key ]]; then
    API_KEY=$(cat ~/.config/amallo/key)
    echo "  ✓ Found key: ${API_KEY:0:20}..."
else
    echo "  ⚠ No API key found"
    echo "  Creating one now..."
    
    KEY_RESP=$(curl -s -X POST https://axismundi.fun/amallo/keys/create \
        -H "Content-Type: application/json" \
        -d '{"identity":"copilot-user","role":"user"}')
    API_KEY=$(echo "$KEY_RESP" | jq -r '.key')
    
    mkdir -p ~/.config/amallo
    echo "$API_KEY" > ~/.config/amallo/key
    chmod 600 ~/.config/amallo/key
    echo "  ✓ Created: $API_KEY"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ SOVEREIGN AI COPILOT INSTALLED                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 USAGE:"
echo ""
echo "1. Start tmux (if not already in it):"
echo "   $ tmux"
echo ""
echo "2. Toggle AI copilot pane:"
echo "   Press: Ctrl+Alt+Space"
echo ""
echo "3. Interact with AI:"
echo "   - Type in the AI pane (bottom)"
echo "   - Press Enter with no text = auto-detect from terminal"
echo "   - Commands get offered to copy/execute"
echo ""
echo "4. Close AI pane:"
echo "   Press: Ctrl+Alt+Space again"
echo ""
echo "📋 SPECIAL COMMANDS (in AI pane):"
echo "   /clear    - Clear chat"
echo "   /history  - Show conversation"
echo "   /exit     - Close copilot"
echo ""
echo "🎨 FEATURES:"
echo "   ✓ Split pane interface (like VS Code copilot)"
echo "   ✓ Context-aware (reads your terminal)"
echo "   ✓ Auto-detects errors and offers fixes"
echo "   ✓ Command completion"
echo "   ✓ Can copy/execute AI responses"
echo "   ✓ Chat history saved"
echo "   ✓ Persistent across terminal sessions"
echo ""
echo "🧪 TEST IT NOW:"
echo "   1. $ tmux"
echo "   2. Ctrl+Alt+Space (AI pane appears)"
echo "   3. Type: \"how do I find large files?\""
echo "   4. Press 'x' to execute command in main pane"
echo ""
echo "🔧 Configuration:"
echo "   Tmux config: ~/.tmux.conf"
echo "   API Key: ~/.config/amallo/key"
echo "   Chat history: ~/.local/share/amallo/copilot-chat.jsonl"
echo ""
