# 🎬 Sovereign AI Copilot - Live Demo Script

## Demo 1: Basic Toggle (10 seconds)
```bash
$ tmux                           # Start tmux
$ # Press Ctrl+Alt+Space         # AI pane opens at bottom
$ # Press Ctrl+Alt+Space again   # AI pane closes
```

## Demo 2: Command Generation (20 seconds)
```bash
$ tmux
$ # Ctrl+Alt+Space               # Open AI
You > find large files over 100MB
AI > find . -type f -size +100M -exec ls -lh {} \;
     [Press 'x' to execute in main pane]
$ # Press 'x'                    # Command types into terminal
$ # Press Enter                  # Execute
```

## Demo 3: Error Debugging (30 seconds)
```bash
$ python3 -c "import pandas"
ModuleNotFoundError: No module named 'pandas'

$ # Ctrl+Alt+Space               # Open AI
$ # Press Enter (no text)        # Auto-detects error
AI > Debug this error: ModuleNotFoundError: No module named 'pandas'
     Install with: pip install pandas
     [Press 'x' to execute]
$ # Press 'x'
$ pip install pandas             # Installs
$ python3 -c "import pandas"     # Works!
```

## Demo 4: Context-Aware Help (25 seconds)
```bash
$ docker ps
CONTAINER ID   IMAGE     STATUS
abc123         nginx     Up 2 hours

$ # Ctrl+Alt+Space
$ # Press Enter                  # AI reads docker ps output
AI > You have nginx running (abc123)
     Common commands:
     - docker logs abc123
     - docker exec -it abc123 bash  
     - docker restart abc123
```

## Demo 5: Multi-Turn Conversation (40 seconds)
```bash
$ # Ctrl+Alt+Space
You > compress video to 720p
AI > ffmpeg -i input.mp4 -vf scale=-1:720 -crf 23 output.mp4

You > also reduce audio bitrate to 128k
AI > ffmpeg -i input.mp4 -vf scale=-1:720 -crf 23 -b:a 128k output.mp4
     [Press 'c' to copy]
$ # Press 'c'                    # Copied to clipboard
```

## 🎥 Screen Recording Script
```bash
# Install asciinema
sudo apt install asciinema

# Record demo
asciinema rec sovereign-copilot-demo.cast

# Upload
asciinema upload sovereign-copilot-demo.cast

# Or convert to GIF
docker run --rm -v $PWD:/data asciinema/asciicast2gif \
  sovereign-copilot-demo.cast sovereign-copilot-demo.gif
```
