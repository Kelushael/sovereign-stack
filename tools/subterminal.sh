#!/bin/bash
# subterminal — persistent side chat panel that never disappears
SESSION="sovereign"

if [ "$1" = "attach" ] || [ "$1" = "a" ]; then
  tmux attach-session -t $SESSION
  exit 0
fi

# already running? just attach
if tmux has-session -t $SESSION 2>/dev/null; then
  tmux attach-session -t $SESSION
  exit 0
fi

# chat FULL SCREEN — code/work hidden in background window
tmux new-session -d -s $SESSION -x 220 -y 50
tmux rename-window -t $SESSION chat
tmux send-keys -t $SESSION:chat "axis" Enter
# background window for builds/code — invisible until needed
tmux new-window -t $SESSION -n work
tmux select-window -t $SESSION:chat
# Shift+Right = peek work window | Shift+Left = back to chat
tmux bind -n S-Right select-window -t $SESSION:work
tmux bind -n S-Left  select-window -t $SESSION:chat
tmux attach-session -t $SESSION
