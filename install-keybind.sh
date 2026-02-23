#!/bin/bash
# Install Sovereign AI Keybind System
set -e

echo "🔧 Installing Sovereign AI Keybind..."
echo ""

# Check dependencies
MISSING=""
for cmd in xbindkeys xdotool xsel jq curl; do
    if ! command -v $cmd >/dev/null; then
        MISSING="$MISSING $cmd"
    fi
done

if [[ -n "$MISSING" ]]; then
    echo "📦 Installing missing dependencies:$MISSING"
    sudo apt update
    sudo apt install -y xbindkeys xdotool xsel jq curl libnotify-bin
fi

# Install script
mkdir -p ~/.local/bin
cp sovereign-ai-assist ~/.local/bin/
chmod +x ~/.local/bin/sovereign-ai-assist

echo "✓ Installed sovereign-ai-assist to ~/.local/bin/"

# Setup config directory
mkdir -p ~/.config/amallo

# Prompt for API key if not exists
if [[ ! -f ~/.config/amallo/key ]]; then
    echo ""
    echo "🔑 API Key Setup"
    echo "  Option 1: Use existing SOV key"
    echo "  Option 2: Create new key at https://axismundi.fun/terminal.html"
    echo "  Option 3: Leave blank to set later"
    echo ""
    read -p "Enter SOV API key (or press Enter to skip): " api_key
    
    if [[ -n "$api_key" ]]; then
        echo "$api_key" > ~/.config/amallo/key
        chmod 600 ~/.config/amallo/key
        echo "✓ API key saved to ~/.config/amallo/key"
    else
        echo "⚠ No API key set. You can add it later:"
        echo "  echo 'SOV-XXXX-XXXX-XXXX-XXXX' > ~/.config/amallo/key"
    fi
fi

# Configure xbindkeys
if [[ ! -f ~/.xbindkeysrc ]]; then
    cat > ~/.xbindkeysrc << 'EOF'
# Sovereign AI Keybinds

# Ctrl+Shift+A: General AI assist
"~/.local/bin/sovereign-ai-assist general"
  Control+Shift+a

# Ctrl+Shift+C: Code review
"~/.local/bin/sovereign-ai-assist code"
  Control+Shift+c

# Ctrl+Shift+T: Terminal command generator
"~/.local/bin/sovereign-ai-assist terminal"
  Control+Shift+t

# Ctrl+Shift+E: Explain selected text
"~/.local/bin/sovereign-ai-assist explain"
  Control+Shift+e

# Ctrl+Shift+F: Fix grammar/spelling
"~/.local/bin/sovereign-ai-assist fix"
  Control+Shift+f
EOF
    echo "✓ Created ~/.xbindkeysrc"
else
    echo "⚠ ~/.xbindkeysrc already exists, skipping"
    echo "  Add these lines manually:"
    echo '  "~/.local/bin/sovereign-ai-assist general"'
    echo "    Control+Shift+a"
fi

# Start xbindkeys
killall xbindkeys 2>/dev/null || true
xbindkeys

echo ""
echo "✅ Installation complete!"
echo ""
echo "📋 Keybinds:"
echo "  Ctrl+Shift+A - General AI assist"
echo "  Ctrl+Shift+C - Code review"
echo "  Ctrl+Shift+T - Terminal command"
echo "  Ctrl+Shift+E - Explain text"
echo "  Ctrl+Shift+F - Fix grammar"
echo ""
echo "🎯 Usage:"
echo "  1. Highlight any text"
echo "  2. Press keybind"
echo "  3. Response copied to clipboard"
echo "  4. Paste with Ctrl+V"
echo ""
echo "🔧 Configuration:"
echo "  API Key: ~/.config/amallo/key"
echo "  History: ~/.local/share/amallo/history.jsonl"
echo "  Keybinds: ~/.xbindkeysrc"
echo ""
echo "🚀 Test it now:"
echo "  1. Highlight this text: 'explain quantum computing'"
echo "  2. Press Ctrl+Shift+A"
echo "  3. Wait 2-5 seconds"
echo "  4. Check notification and clipboard"
echo ""
