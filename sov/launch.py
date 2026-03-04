#!/usr/bin/env python3
"""
sov/launch.py  —  Arcade boot sequence for the sovereign stack
"""
import sys, os, time, random, threading, shutil

# ── ANSI ──────────────────────────────────────────────────────────────────────
ORG  = "\033[38;2;255;120;0m"      # bright orange
ORG2 = "\033[38;2;255;180;0m"      # amber/gold
ORG3 = "\033[38;2;255;60;0m"       # deep orange
RED  = "\033[38;2;255;40;40m"
YEL  = "\033[38;2;255;240;0m"
WHT  = "\033[38;2;255;250;240m"
GRY  = "\033[38;2;80;50;20m"
DIM  = "\033[38;2;40;25;10m"
RST  = "\033[0m"
BOLD = "\033[1m"
BLINK= "\033[5m"
CLR  = "\033[2J\033[H"
UP   = lambda n: f"\033[{n}A"
ERAS = "\033[2K"

# ── terminal width ─────────────────────────────────────────────────────────────
W = min(shutil.get_terminal_size((80, 24)).columns, 100)

# ── static noise chars ────────────────────────────────────────────────────────
_STATIC = "░▒▓█▄▀■□▪▫◘◙◚◛▌▐▀▄╬╫╪┼╂╀┿╋╊╉╈╇╆╅╄╃"
_SPARK  = "⚡★✦✧✶✸✹✺❋❊❉❈✻✼✽✾✿❀❁❂❃"

def _noise_line(w=None):
    w = w or W
    return "".join(random.choice(_STATIC) for _ in range(w))

def _spark_line(w=None):
    w = w or W
    density = 0.25
    return "".join(
        random.choice(_SPARK) if random.random() < density else " "
        for _ in range(w)
    )

# ── ASCII logo (SOV) ──────────────────────────────────────────────────────────
_LOGO = [
    r" ███████╗ ██████╗ ██╗   ██╗",
    r" ██╔════╝██╔═══██╗██║   ██║",
    r" ███████╗██║   ██║██║   ██║",
    r" ╚════██║██║   ██║╚██╗ ██╔╝",
    r" ███████║╚██████╔╝ ╚████╔╝ ",
    r" ╚══════╝ ╚═════╝   ╚═══╝  ",
]

_TAGLINE = "SOVEREIGN  ·  ZERO-CONFIG  ·  AXIS MUNDI"
_VERSION  = "v0.1  —  AMALLO ENGINE"

# ── helpers ───────────────────────────────────────────────────────────────────
def _center(s, w=None):
    w = w or W
    pad = max(0, (w - len(s)) // 2)
    return " " * pad + s

def _bar(pct, w=30):
    filled = int(w * pct)
    empty  = w - filled
    return (
        f"{ORG}{'█' * filled}{GRY}{'░' * empty}{RST}"
    )

def _write(s):
    sys.stdout.write(s)
    sys.stdout.flush()

def _nl():
    _write("\n")

# ── static burst ─────────────────────────────────────────────────────────────
def _static_burst(rows=6, frames=12, speed=0.035):
    """Flash static noise across the terminal."""
    for f in range(frames):
        lines = []
        for r in range(rows):
            intensity = max(0, 1 - (f / frames))
            if intensity > 0.5:
                col = ORG3
            elif intensity > 0.2:
                col = GRY
            else:
                col = DIM
            lines.append(col + _noise_line() + RST)
        _write("\n".join(lines) + "\n")
        time.sleep(speed)
        _write(UP(rows))
        for _ in range(rows):
            _write(ERAS + "\n")
        _write(UP(rows))
    # clear burst area
    for _ in range(rows):
        _write(ERAS + "\n")
    _write(UP(rows))

# ── logo reveal ───────────────────────────────────────────────────────────────
def _logo_reveal():
    colors = [ORG3, ORG3, ORG, ORG, ORG2, YEL]
    for i, (line, col) in enumerate(zip(_LOGO, colors)):
        _write(f"{col}{BOLD}{_center(line)}{RST}\n")
        time.sleep(0.05)

    _nl()
    _write(f"{ORG2}{_center(_TAGLINE)}{RST}\n")
    time.sleep(0.04)
    _write(f"{GRY}{_center(_VERSION)}{RST}\n")
    _nl()

# ── spark scanline ────────────────────────────────────────────────────────────
def _scanline(rows=3, frames=8):
    for f in range(frames):
        lines = []
        for r in range(rows):
            fade = 1 - (f / frames)
            col = ORG if fade > 0.6 else ORG3 if fade > 0.3 else GRY
            lines.append(col + _spark_line() + RST)
        _write("\n".join(lines) + "\n")
        time.sleep(0.05)
        _write(UP(rows))
        for _ in range(rows):
            _write(ERAS + "\n")
        _write(UP(rows))
    for _ in range(rows):
        _write(ERAS + "\n")
    _write(UP(rows))

# ── boot checklist ────────────────────────────────────────────────────────────
_CHECKS = [
    ("AMALLO ENGINE",        "ONLINE"),
    ("AXIS MUNDI API",       "axismundi.fun"),
    ("TOOL SUITE",           "LOADED"),
    ("GUI GROUNDING",        "ACTIVE"),
    ("VIRTUAL INPUT LAYER",  "ARMED"),
    ("MESH NODE",            "LISTENING"),
    ("SANDBOX",              "READY"),
]

def _boot_checks():
    prefix = " " * 4
    for label, val in _CHECKS:
        dots = "." * (28 - len(label))
        _write(f"{prefix}{GRY}{label}{dots}{RST}")
        sys.stdout.flush()
        time.sleep(0.07 + random.random() * 0.08)
        # flicker
        for _ in range(random.randint(1, 3)):
            _write(f"{ORG3}?{RST}")
            sys.stdout.flush()
            time.sleep(0.03)
            _write("\b \b")
        _write(f"{ORG2}[ {YEL}{val}{ORG2} ]{RST}\n")
    _nl()

# ── loading bar ───────────────────────────────────────────────────────────────
def _loading_bar(label="BOOTING SOVEREIGN STACK", steps=30):
    prefix = " " * 4
    for i in range(steps + 1):
        pct = i / steps
        bar = _bar(pct, w=32)
        pct_str = f"{int(pct*100):3d}%"
        _write(f"\r{prefix}{ORG}{label}  {bar}  {ORG2}{pct_str}{RST}")
        sys.stdout.flush()
        time.sleep(0.025 + random.random() * 0.015)
    _write("\n\n")

# ── insert coin flash ─────────────────────────────────────────────────────────
def _insert_coin():
    msg = "★  PLAYER 1  ·  PRESS ENTER TO START  ★"
    _write(f"{BLINK}{ORG2}{BOLD}{_center(msg)}{RST}\n")
    _nl()

# ── full sequence ─────────────────────────────────────────────────────────────
def boot(skip_anim: bool = False):
    """
    Run the full arcade boot sequence.
    Set skip_anim=True for --fast / scripted mode.
    """
    if skip_anim or not sys.stdout.isatty():
        _logo_reveal()
        return

    _write(CLR)
    _nl()

    # 1. static burst
    _static_burst(rows=5, frames=10, speed=0.03)

    # 2. logo
    _logo_reveal()

    # 3. spark scanline
    _scanline(rows=2, frames=7)

    # 4. boot checks
    _boot_checks()

    # 5. loading bar
    _loading_bar()

    # 6. insert coin
    _insert_coin()


# ── inline CLI prompt styling ─────────────────────────────────────────────────
PROMPT = f"{ORG}▶{RST} {ORG2}amallo{RST}{GRY}@{RST}{ORG}sov{RST} {YEL}»{RST} "

def arcade_reply_header(model: str = "AMALLO"):
    """Print a styled reply header before each agent response."""
    bar = f"{ORG}{'─' * (W - 2)}{RST}"
    _write(f"\n{bar}\n")
    _write(f"  {ORG3}◈{RST}  {ORG2}{BOLD}{model}{RST}  {GRY}responding…{RST}\n")
    _write(f"{bar}\n\n")

def arcade_user_prompt():
    """Return the styled input prompt string."""
    return PROMPT


if __name__ == "__main__":
    boot()
