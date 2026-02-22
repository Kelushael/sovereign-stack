# Sovereign Stack — Axis Mundi

Fully sovereign AI infrastructure. Zero cloud dependency.

## Live
- **https://axismundi.fun** — Landing page
- **https://axismundi.fun/terminal.html** — Sovereign Terminal (TTS/STT, model selector, script downloads)
- **https://axismundi.fun/amallo/health** — Inference node

## Features
- Amallo: OpenAI-compatible sovereign GGUF/Ollama inference server
- SOV-XXXX API key system
- Web terminal with matrix rain, TTS/STT, model selector (↑↓ Enter)
- `/addcmd` custom command shortcuts
- Download any AI response as a script with one click
- Axis Relay: dispatches to all nodes in parallel
- IDE3: Sovereign Visual Bridge

## Stack
- Controller: 187.77.208.28 — 8 cores / 32GB RAM / 400GB
- Backend: Ollama (dolphin-mistral, glm4)
- Nginx + Let's Encrypt SSL
- systemd services: amallo, axis-relay, axis-ide3

## Install
```bash
curl -sSL https://axismundi.fun/install.sh | bash
```

Built by Marcus (Kelushael) × Claude × Amallo Cloud Term
