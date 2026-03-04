#!/usr/bin/env python3
"""
sov --cli  →  Sovereign CLI agent
Thin wrapper that imports and runs sovereign.py's main()
"""
import sys, os

def main():
    # Add sovereign-stack root to path so sovereign.py is importable
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if here not in sys.path:
        sys.path.insert(0, here)

    try:
        import sovereign
        sovereign.main()
    except ImportError as e:
        print(f"[sov-cli] Could not import sovereign.py: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
