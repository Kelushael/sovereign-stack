#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# AMALLO QUANTIZER — Build your own GGUF from ANY HuggingFace model
# Run this ON the sovereign node (187.77.208.28)
#
# What this does:
#   HuggingFace model (safetensors/pytorch) 
#     → convert to F16 GGUF (lossless intermediate)
#       → quantize to Q4/Q5/Q8 (your size target)
#         → drop into /root/axis-mundi/models/
#           → axis /models sees it immediately
#
# Usage:
#   bash quantize.sh mistralai/Mistral-7B-Instruct-v0.3
#   bash quantize.sh meta-llama/Llama-3.2-3B-Instruct Q4_K_M
#   bash quantize.sh Qwen/Qwen2.5-7B-Instruct Q5_K_M,Q8_0
# ═══════════════════════════════════════════════════════════════

set -e

MODEL_ID="${1:?Usage: bash quantize.sh <hf-model-id> [quant_types]}"
QUANTS="${2:-Q4_K_M,Q5_K_M}"   # comma-separated, default both
MODELS_OUT="/root/axis-mundi/models"
WORK_DIR="/root/amallo-quant"
LLAMA_DIR="$WORK_DIR/llama.cpp"
HF_CACHE="$WORK_DIR/hf-cache"

mkdir -p "$WORK_DIR" "$MODELS_OUT" "$HF_CACHE"

echo "═══════════════════════════════════════════════════"
echo "  AMALLO QUANTIZER"
echo "  Model:  $MODEL_ID"
echo "  Quants: $QUANTS"
echo "  Output: $MODELS_OUT"
echo "═══════════════════════════════════════════════════"
echo ""

# ── STEP 1: Build llama.cpp if not already built ────────────
if [[ ! -f "$LLAMA_DIR/build/bin/llama-quantize" ]]; then
    echo "🔨 Building llama.cpp..."

    # Dependencies
    apt-get update -qq
    apt-get install -y -qq git cmake build-essential python3-pip python3-venv curl wget

    # Clone
    if [[ ! -d "$LLAMA_DIR" ]]; then
        git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
    fi

    cd "$LLAMA_DIR"
    cmake -B build -DLLAMA_CURL=ON 2>/dev/null
    cmake --build build --config Release -j$(nproc) --target llama-quantize llama-gguf-split 2>/dev/null
    echo "  ✓ llama-quantize built"
    echo "  ✓ llama-gguf-split built"
else
    echo "  ✓ llama.cpp already built"
fi

QUANTIZE_BIN="$LLAMA_DIR/build/bin/llama-quantize"

# ── STEP 2: Python env for conversion ───────────────────────
VENV="$WORK_DIR/venv"
if [[ ! -d "$VENV" ]]; then
    echo ""
    echo "🐍 Setting up Python env..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q \
        torch --index-url https://download.pytorch.org/whl/cpu \
        transformers \
        sentencepiece \
        protobuf \
        huggingface_hub \
        gguf
    echo "  ✓ Python env ready"
fi

PYTHON="$VENV/bin/python3"

# ── STEP 3: Download model from HuggingFace ─────────────────
MODEL_SLUG=$(echo "$MODEL_ID" | tr '/' '_' | tr '[:upper:]' '[:lower:]')
MODEL_DIR="$HF_CACHE/$MODEL_SLUG"

if [[ ! -d "$MODEL_DIR" ]]; then
    echo ""
    echo "⬇  Downloading $MODEL_ID from HuggingFace..."
    "$VENV/bin/python3" << PYEOF
from huggingface_hub import snapshot_download
import os

local_dir = snapshot_download(
    repo_id="$MODEL_ID",
    local_dir="$MODEL_DIR",
    ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "rust_model*"],
)
print(f"  ✓ Downloaded to {local_dir}")
PYEOF
else
    echo "  ✓ Already downloaded: $MODEL_DIR"
fi

# ── STEP 4: Convert to F16 GGUF (lossless base) ─────────────
F16_FILE="$WORK_DIR/${MODEL_SLUG}-F16.gguf"

if [[ ! -f "$F16_FILE" ]]; then
    echo ""
    echo "🔄 Converting to F16 GGUF (lossless intermediate)..."
    "$PYTHON" "$LLAMA_DIR/convert_hf_to_gguf.py" \
        "$MODEL_DIR" \
        --outfile "$F16_FILE" \
        --outtype f16
    echo "  ✓ F16 GGUF: $F16_FILE"
    ls -lh "$F16_FILE"
else
    echo "  ✓ F16 already exists: $F16_FILE"
fi

# ── STEP 5: Quantize to target formats ──────────────────────
echo ""
echo "🗜  Quantizing..."

IFS=',' read -ra QUANT_LIST <<< "$QUANTS"
for QUANT in "${QUANT_LIST[@]}"; do
    QUANT=$(echo "$QUANT" | tr -d ' ')
    OUT_FILE="$MODELS_OUT/${MODEL_SLUG}-${QUANT}.gguf"
    
    echo ""
    echo "  Target: $QUANT"
    
    if [[ -f "$OUT_FILE" ]]; then
        echo "  ✓ Already exists: $OUT_FILE"
        continue
    fi

    START=$(date +%s)
    "$QUANTIZE_BIN" "$F16_FILE" "$OUT_FILE" "$QUANT" $(nproc)
    END=$(date +%s)
    ELAPSED=$((END - START))
    
    SIZE=$(ls -lh "$OUT_FILE" | awk '{print $5}')
    F16_SIZE=$(ls -lh "$F16_FILE" | awk '{print $5}')
    
    echo "  ✓ $OUT_FILE"
    echo "    Size: $SIZE (from $F16_SIZE F16)"
    echo "    Time: ${ELAPSED}s"
done

# ── STEP 6: Register in Amallo ───────────────────────────────
echo ""
echo "📋 Models now in $MODELS_OUT:"
ls -lh "$MODELS_OUT"/*.gguf 2>/dev/null | awk '{print "  "$5, $9}'

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ QUANTIZATION COMPLETE"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Axis sees them immediately:"
echo "  axis /models"
echo ""
echo "  Switch to your new model:"
echo "  axis /model ${MODEL_SLUG}-${QUANT_LIST[0]}"
echo ""

# Optionally clean up F16 (large intermediate)
read -p "  Delete F16 intermediate? ($F16_FILE) [y/N]: " clean
if [[ "$clean" == "y" ]]; then
    rm "$F16_FILE"
    echo "  ✓ Cleaned up F16"
fi
