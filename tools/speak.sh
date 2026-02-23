#!/bin/bash
# Alt+R — read clipboard aloud with human-quality voice
TEXT=$(xsel --clipboard --output 2>/dev/null)
[ -z "$TEXT" ] && TEXT=$(xsel --primary --output 2>/dev/null)
if [ -n "$TEXT" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    if [ -x "$SCRIPT_DIR/human-voice.sh" ]; then
        "$SCRIPT_DIR/human-voice.sh" "$TEXT" &
    else
        spd-say -r 30 "$TEXT" &
    fi
fi
