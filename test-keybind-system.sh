#!/bin/bash
# Test Sovereign AI Keybind System
# Tests: Selection → AI → Clipboard/Injection → Verification

set -e

echo "=========================================="
echo "🧪 SOVEREIGN AI KEYBIND TEST SUITE"
echo "=========================================="
echo ""

# ── TEST 1: Dependencies ───────────────────────────────────────
echo "1️⃣  Testing Dependencies..."
DEPS_OK=true
for cmd in xsel xdotool jq curl; do
    if command -v $cmd >/dev/null; then
        echo "  ✓ $cmd"
    else
        echo "  ✗ $cmd MISSING"
        DEPS_OK=false
    fi
done

if [[ "$DEPS_OK" == "false" ]]; then
    echo ""
    echo "Install missing deps: sudo apt install xbindkeys xdotool xsel jq curl"
    exit 1
fi
echo ""

# ── TEST 2: Amallo Connection ──────────────────────────────────
echo "2️⃣  Testing Amallo Connection..."

# Try local first
if curl -s --max-time 2 http://localhost:8200/health >/dev/null 2>&1; then
    AMALLO_URL="http://localhost:8200"
    LOCAL_STATUS=$(curl -s http://localhost:8200/health | jq -r '.status')
    LOCAL_NODE=$(curl -s http://localhost:8200/health | jq -r '.node')
    echo "  ✓ Local: $LOCAL_NODE ($LOCAL_STATUS)"
else
    echo "  ⚠ Local amallo not running"
fi

# Try remote
if curl -s --max-time 2 https://axismundi.fun/health >/dev/null 2>&1; then
    REMOTE_STATUS=$(curl -s https://axismundi.fun/health | jq -r '.status')
    REMOTE_NODE=$(curl -s https://axismundi.fun/health | jq -r '.node')
    echo "  ✓ Remote: $REMOTE_NODE ($REMOTE_STATUS)"
    AMALLO_URL="https://axismundi.fun"
else
    echo "  ✗ Remote amallo unreachable"
fi

if [[ -z "$AMALLO_URL" ]]; then
    echo "  ✗ No Amallo server available!"
    exit 1
fi
echo ""

# ── TEST 3: API Key ────────────────────────────────────────────
echo "3️⃣  Testing API Key..."

if [[ -f ~/.config/amallo/key ]]; then
    API_KEY=$(cat ~/.config/amallo/key)
    echo "  ✓ Found key: ${API_KEY:0:15}..."
else
    echo "  ⚠ No key found, creating one..."
    KEY_RESP=$(curl -s -X POST $AMALLO_URL/amallo/keys/create \
        -H "Content-Type: application/json" \
        -d '{"identity":"test-keybind","role":"user"}')
    API_KEY=$(echo "$KEY_RESP" | jq -r '.key')
    mkdir -p ~/.config/amallo
    echo "$API_KEY" > ~/.config/amallo/key
    chmod 600 ~/.config/amallo/key
    echo "  ✓ Created key: $API_KEY"
fi

# Validate key works
if curl -s -X POST $AMALLO_URL/v1/chat/completions \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen","messages":[{"role":"user","content":"test"}],"max_tokens":5}' \
    | jq -e '.choices[0].message.content' >/dev/null 2>&1; then
    echo "  ✓ API key validated"
else
    echo "  ✗ API key invalid"
    exit 1
fi
echo ""

# ── TEST 4: Clipboard Operations ──────────────────────────────
echo "4️⃣  Testing Clipboard Operations..."

# Save current clipboard
OLD_CLIP=$(xsel -ob 2>/dev/null || echo "")

# Test write
echo "test-content-$(date +%s)" | xsel -ib
if xsel -ob | grep -q "test-content"; then
    echo "  ✓ Clipboard write works"
else
    echo "  ✗ Clipboard write failed"
fi

# Restore
echo "$OLD_CLIP" | xsel -ib 2>/dev/null || true
echo ""

# ── TEST 5: AI Response ────────────────────────────────────────
echo "5️⃣  Testing AI Response..."

TEST_INPUT="list files in current directory"
echo "  Input: $TEST_INPUT"

START=$(date +%s)
RESPONSE=$(curl -s --max-time 30 -X POST $AMALLO_URL/v1/chat/completions \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"qwen\",
        \"messages\": [{\"role\":\"user\",\"content\":\"Convert to bash command (output ONLY the command): $TEST_INPUT\"}],
        \"max_tokens\": 50,
        \"temperature\": 0.3
    }")
END=$(date +%s)
ELAPSED=$((END - START))

CONTENT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content' 2>/dev/null || echo "")
CONTENT=$(echo "$CONTENT" | sed 's/```bash//g' | sed 's/```//g' | sed 's/<|end of response|>//g' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

if [[ -n "$CONTENT" ]]; then
    echo "  ✓ Response: $CONTENT"
    echo "  ✓ Time: ${ELAPSED}s"
else
    echo "  ✗ No response"
    echo "  Debug: $RESPONSE"
    exit 1
fi
echo ""

# ── TEST 6: Terminal Detection ─────────────────────────────────
echo "6️⃣  Testing Terminal Detection..."

TERM_NAME=$(ps -p $$ -o comm=)
echo "  ✓ Running in: $TERM_NAME"

# Check window manager
if command -v wmctrl >/dev/null; then
    ACTIVE_WINDOW=$(wmctrl -l | grep -i terminal | head -1 || echo "")
    if [[ -n "$ACTIVE_WINDOW" ]]; then
        echo "  ✓ Terminal window detected"
    fi
fi
echo ""

# ── TEST 7: Script Installation ────────────────────────────────
echo "7️⃣  Testing Script Installation..."

if [[ -x ~/.local/bin/sovereign-ai-assist ]]; then
    echo "  ✓ sovereign-ai-assist installed"
else
    echo "  ⚠ sovereign-ai-assist not found in ~/.local/bin/"
fi

if [[ -x ~/.local/bin/sovereign-terminal-inject ]]; then
    echo "  ✓ sovereign-terminal-inject installed"
else
    echo "  ⚠ sovereign-terminal-inject not found"
fi
echo ""

# ── TEST 8: Keybind Configuration ──────────────────────────────
echo "8️⃣  Testing Keybind Configuration..."

if [[ -f ~/.xbindkeysrc ]]; then
    echo "  ✓ ~/.xbindkeysrc exists"
    if grep -q "sovereign-ai-assist" ~/.xbindkeysrc; then
        echo "  ✓ Keybinds configured"
    else
        echo "  ⚠ Keybinds not configured"
    fi
else
    echo "  ⚠ ~/.xbindkeysrc not found"
fi

if pgrep -x xbindkeys >/dev/null; then
    echo "  ✓ xbindkeys running"
else
    echo "  ⚠ xbindkeys not running"
    echo "    Start with: xbindkeys"
fi
echo ""

# ── TEST 9: Simulated Keybind ──────────────────────────────────
echo "9️⃣  Testing Simulated Keybind Flow..."

# Simulate selection
TEST_TEXT="show disk usage"
echo "$TEST_TEXT" | xsel -ip
echo "  ✓ Simulated selection: '$TEST_TEXT'"

# Call AI assist directly
if [[ -x ~/.local/bin/sovereign-ai-assist ]]; then
    RESULT=$(~/.local/bin/sovereign-ai-assist terminal 2>&1 || echo "failed")
    if echo "$RESULT" | grep -qi "error"; then
        echo "  ⚠ Script ran but reported errors:"
        echo "    $RESULT"
    else
        echo "  ✓ Script executed successfully"
        CLIP_RESULT=$(xsel -ob 2>/dev/null)
        echo "  ✓ Clipboard result: $CLIP_RESULT"
    fi
else
    echo "  ⚠ Cannot test - script not installed"
fi
echo ""

# ── TEST 10: Safety Check ──────────────────────────────────────
echo "🔟  Safety Check..."

echo "  ⚠ AUTO_EXECUTE is DANGEROUS!"
echo "  ⚠ AI-generated commands will run automatically"
echo ""
echo "  Safe mode: AUTO_EXECUTE=false (just types, no Enter)"
echo "  YOLO mode: AUTO_EXECUTE=true (auto-executes)"
echo ""
read -p "  Enable AUTO_EXECUTE? (yes/NO): " answer
if [[ "$answer" == "yes" ]]; then
    echo "export AUTO_EXECUTE=true" >> ~/.bashrc
    echo "  ✓ AUTO_EXECUTE enabled (restart terminal)"
else
    echo "  ✓ AUTO_EXECUTE disabled (safe mode)"
fi
echo ""

# ── SUMMARY ────────────────────────────────────────────────────
echo "=========================================="
echo "✅ TEST SUMMARY"
echo "=========================================="
echo ""
echo "Amallo Server: $AMALLO_URL"
echo "API Key: ${API_KEY:0:20}..."
echo "Response Time: ${ELAPSED}s"
echo ""
echo "🎯 READY TO USE!"
echo ""
echo "Usage:"
echo "  1. Highlight text: 'list docker containers'"
echo "  2. Press: Ctrl+Shift+T"
echo "  3. Watch AI generate: 'docker ps'"
echo "  4. Command auto-types into terminal"
echo ""
echo "Keybinds:"
echo "  Ctrl+Shift+A - General AI assist (clipboard)"
echo "  Ctrl+Shift+T - Terminal command (auto-type)"
echo "  Ctrl+Shift+C - Code review"
echo ""
echo "Configuration:"
echo "  API Key: ~/.config/amallo/key"
echo "  Keybinds: ~/.xbindkeysrc"
echo "  History: ~/.local/share/amallo/"
echo ""
