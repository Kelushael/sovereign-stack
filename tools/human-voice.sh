#!/bin/bash
# Human-quality voice synthesis with fallback chain
# Usage: human-voice.sh "text to speak"
# Fallback chain: piper → espeak-ng → spd-say

TEXT="$1"
[ -z "$TEXT" ] && exit 1

# Create temp file for audio output
AUDIO_FILE=$(mktemp /tmp/voice-XXXXXX.wav)
trap "rm -f $AUDIO_FILE" EXIT 2>/dev/null

# Try 1: Piper (best human quality, neural TTS)
if command -v piper &>/dev/null && [ -f ~/.local/share/piper-tts/en_US-john-medium.onnx ]; then
    if echo "$TEXT" | piper \
        --model ~/.local/share/piper-tts/en_US-john-medium.onnx \
        --output-file "$AUDIO_FILE" 2>/dev/null; then
        # Try to play the audio (silently fail if no audio hardware)
        if command -v aplay &>/dev/null; then
            aplay "$AUDIO_FILE" 2>/dev/null &
            pid=$!
            wait $pid 2>/dev/null || true
        elif command -v paplay &>/dev/null; then
            paplay "$AUDIO_FILE" 2>/dev/null &
            pid=$!
            wait $pid 2>/dev/null || true
        elif command -v ffplay &>/dev/null; then
            timeout 2 ffplay -nodisp -autoexit "$AUDIO_FILE" 2>/dev/null &
            pid=$!
            wait $pid 2>/dev/null || true
        fi
        exit 0
    fi
fi

# Try 2: espeak-ng (good quality, phonetic TTS)
if command -v espeak-ng &>/dev/null; then
    espeak-ng -v en-us -s 150 "$TEXT" 2>/dev/null &
    pid=$!
    wait $pid 2>/dev/null || true
    exit 0
fi

# Try 3: spd-say (fallback, basic speech)
if command -v spd-say &>/dev/null; then
    spd-say -r 20 "$TEXT" 2>/dev/null &
    pid=$!
    wait $pid 2>/dev/null || true
    exit 0
fi

exit 1
