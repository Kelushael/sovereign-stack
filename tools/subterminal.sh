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

# fresh: main shell left | axis chat right
tmux new-session -d -s $SESSION -x 220 -y 50
tmux split-window -t $SESSION -h -p 60
tmux send-keys -t $SESSION:0.1 "axis" Enter
tmux select-pane -t $SESSION:0.0
tmux bind -n S-Right select-pane -t $SESSION:0.1
tmux bind -n S-Left  select-pane -t $SESSION:0.0
tmux attach-session -t $SESSION
