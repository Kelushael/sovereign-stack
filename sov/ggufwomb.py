#!/usr/bin/env python3
"""
sov-ggufwomb  →  GGUF Model Lifecycle Manager
Spawns / manages llama-server or llama-cpp-python instances.
Wraps gguf_server.py with a branded boot sequence.
"""
import sys, os

PINK = "\033[38;2;255;105;180m"
CYAN = "\033[38;2;0;220;255m"
LIME = "\033[38;2;57;255;100m"
GOLD = "\033[38;2;255;200;50m"
GRAY = "\033[38;2;85;85;105m"
RST  = "\033[0m"
BOLD = "\033[1m"

BANNER = f"""
{PINK}{BOLD}  ╔══════════════════════════════════════════════╗
  ║  SOV-GGUFWOMB  ·  MODEL LIFECYCLE SERVER    ║
  ╚══════════════════════════════════════════════╝{RST}

  {CYAN}Scanning for GGUF models …{RST}
  {GRAY}~/models/gguf  |  port 8300  |  OpenAI-compat API{RST}
"""

def main():
    print(BANNER)

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)

    try:
        import uvicorn
        from gguf_server import app, PORT, MODELS_DIR
        print(f"  {LIME}✓{RST} Models dir : {MODELS_DIR}")
        print(f"  {LIME}✓{RST} Listening  : http://0.0.0.0:{PORT}")
        print(f"  {LIME}✓{RST} Endpoint   : /v1/chat/completions\n")
        uvicorn.run(
            "gguf_server:app",
            host="0.0.0.0",
            port=PORT,
            log_level="info",
            reload=False,
        )
    except ImportError as e:
        print(f"\n  [sov-ggufwomb] Missing dependency: {e}")
        print(f"  Run: pip install fastapi uvicorn llama-cpp-python huggingface-hub httpx")
        sys.exit(1)


if __name__ == "__main__":
    main()
