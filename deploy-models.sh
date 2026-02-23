#!/bin/bash
# Deploy GGUFs to your sovereign Amallo node
# Run FROM your machine: bash deploy-models.sh
# Or SSH in and run directly on the node

NODE="root@187.77.208.28"
MODELS_DIR="/root/axis-mundi/models"

# ── PICK YOUR LOAD OUT ────────────────────────────────────────
# Comment out what you don't want
# 32GB RAM budget:
#   7B  Q5 = ~5GB   ← run 4 of these simultaneously
#   14B Q5 = ~10GB  ← run 2 simultaneously
#   32B Q5 = ~22GB  ← fills most of RAM
#   70B Q3 = ~28GB  ← one big boy at a time

declare -A MODELS

# ── FAST / ALWAYS-ON (small, quick) ──────────────────────────
MODELS["llama3-3b"]="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q5_K_M.gguf"
MODELS["llama3-3b-uncensored"]="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-uncensored-GGUF/resolve/main/Llama-3.2-3B-Instruct-uncensored-Q5_K_M.gguf"

# ── WORKHORSE 7-9B (daily use) ────────────────────────────────
MODELS["llama3-8b"]="https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf"
MODELS["mistral-7b"]="https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3-Q5_K_M.gguf"
MODELS["qwen-7b"]="https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q5_K_M.gguf"
MODELS["gemma2-9b"]="https://huggingface.co/bartowski/gemma-2-9b-it-GGUF/resolve/main/gemma-2-9b-it-Q5_K_M.gguf"

# ── REASONING (14B) ───────────────────────────────────────────
MODELS["deepseek-r1-14b"]="https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-14B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-14B-Q5_K_M.gguf"
MODELS["glm4-flash"]="https://huggingface.co/bartowski/zai-org_GLM-4.7-Flash-GGUF/resolve/main/zai-org_GLM-4.7-Flash-Q5_K_M.gguf"

# ── CODER ─────────────────────────────────────────────────────
MODELS["qwen-coder-7b"]="https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-7B-Instruct-Q5_K_M.gguf"
# MODELS["qwen-coder-32b"]="https://huggingface.co/bartowski/Qwen2.5-Coder-32B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf"  # ~22GB alone

# ── BIG BOY (70B — basically GPT-4) ──────────────────────────
# MODELS["llama3-70b"]="https://huggingface.co/bartowski/Llama-3.3-70B-Instruct-GGUF/resolve/main/Llama-3.3-70B-Instruct-Q3_K_M/Llama-3.3-70B-Instruct-Q3_K_M-00001-of-00002.gguf"

# ── DEPLOY ────────────────────────────────────────────────────
echo "🚀 Deploying GGUF models to Amallo node"
echo "   Target: $NODE:$MODELS_DIR"
echo ""

for NAME in "${!MODELS[@]}"; do
    URL="${MODELS[$NAME]}"
    FILENAME=$(basename "$URL")
    echo "📦 $NAME"
    echo "   File: $FILENAME"

    # If running ON the node directly
    if [[ "$(hostname -I | awk '{print $1}')" == "187.77.208.28" ]]; then
        echo "   Downloading directly..."
        wget -q --show-progress -P "$MODELS_DIR" "$URL" && echo "   ✓ Done" || echo "   ✗ Failed"
    else
        # SSH and download on the node (node downloads from HuggingFace directly)
        echo "   Downloading on node..."
        ssh "$NODE" "mkdir -p $MODELS_DIR && wget -q --show-progress -P $MODELS_DIR '$URL' && echo '✓ $NAME'" &
    fi
    echo ""
done

# Wait for all background SSH downloads
wait

echo ""
echo "✅ All downloads complete"
echo ""
echo "Check models on node:"
echo "  ssh $NODE 'ls -lh $MODELS_DIR'"
echo ""
echo "Restart amallo_server:"
echo "  ssh $NODE 'systemctl restart amallo'"
echo ""
echo "Verify via axis:"
echo "  axis /models"
