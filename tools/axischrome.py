#!/usr/bin/env python3
"""
AXISCHROME — Sovereign AI Browser
Three primitives. That's it.

  screenshot()   → AI's eyes
  click(x, y)    → one mouse press
  key(k)         → one keypress  (type = key() repeated)

Everything else in a browser derives from these three.

Usage:
  axischrome.py "find GGUF models on huggingface"
  axischrome.py https://example.com "what does this page say"
  axischrome.py https://example.com          # just summarize

Future: plug in cam feed as alternate screenshot source — same loop.
"""

import sys, json, time, base64, urllib.request, urllib.parse
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────
cfg = {}
_cfg_path = Path.home() / ".config" / "axis-mundi" / "config.json"
if _cfg_path.exists():
    cfg = json.loads(_cfg_path.read_text())

SERVER = cfg.get("server", "https://axismundi.fun")
TOKEN  = cfg.get("token",  cfg.get("api_key", ""))
MODEL  = cfg.get("model",  "dolphin-mistral:latest")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "AXISCHROME/1.0"
}

MAX_STEPS = 12   # max action loop iterations
DDG       = "https://duckduckgo.com/html/?q={}"

# ── Playwright setup ─────────────────────────────────────────────────
try:
    from playwright.sync_api import sync_playwright
    _pw_ctx  = sync_playwright().__enter__()
    _browser = _pw_ctx.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    )
    _page = _browser.new_page(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AXISCHROME/1.0",
        extra_http_headers={"DNT": "1"}
    )
    HAS_BROWSER = True
except Exception as _e:
    HAS_BROWSER = False
    print(f"[axischrome] browser unavailable: {_e}", file=sys.stderr)

# ── THREE PRIMITIVES ─────────────────────────────────────────────────

def screenshot() -> bytes:
    """AI's eyes. Returns PNG bytes."""
    if HAS_BROWSER:
        return _page.screenshot(full_page=False)
    return b""

def click(x: int, y: int):
    """One mouse click."""
    if HAS_BROWSER:
        _page.mouse.click(x, y)

def key(k: str):
    """
    One keypress or combo.
    key("Enter")    key("ctrl+a")    key("t")
    For typing text, call key() once per character — or use key("type:hello")
    as a shorthand that sends each character via keyboard.press().
    """
    if not HAS_BROWSER:
        return
    if k.startswith("type:"):
        for ch in k[5:]:
            _page.keyboard.press(ch if ch != " " else "Space")
    else:
        _page.keyboard.press(k)

# ── Navigation helper (derived from primitives) ─────────────────────

def goto(url: str):
    """Navigate to URL — uses playwright navigate, not a primitive,
    but could be: click address bar + type URL + Enter."""
    if HAS_BROWSER:
        _page.goto(url, wait_until="domcontentloaded", timeout=20000)
        _page.wait_for_timeout(1200)

# ── Vision: screenshot → text (for non-vision models) ───────────────

def _page_text() -> str:
    """Extract readable text from current page."""
    if not HAS_BROWSER:
        return ""
    try:
        return _page.evaluate("""() => {
            document.querySelectorAll('script,style,nav,footer,aside,head').forEach(e=>e.remove());
            return (document.body||document.documentElement).innerText;
        }""")[:6000]
    except:
        return ""

# ── Amallo: send vision state + task → get next action ──────────────

SYSTEM = """You are AXISCHROME, a sovereign browser AI with three actions:
  click    → {"a":"click","x":N,"y":N}
  key      → {"a":"key","k":"Enter"}   or  {"a":"key","k":"type:your text"}
  done     → {"a":"done","r":"result text"}
  fail     → {"a":"fail","r":"reason"}

You are shown the current page text. Choose the single next action to complete the user task.
Respond with ONLY valid JSON — no markdown, no explanation."""

def next_action(task: str, page_text: str, step: int) -> dict:
    """Ask amallo: given this page, what's the next action for this task?"""
    user_msg = (
        f"TASK: {task}\n"
        f"STEP: {step}/{MAX_STEPS}\n\n"
        f"PAGE:\n{page_text}\n\n"
        "Next action JSON:"
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": user_msg}
        ],
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 120
    }
    req = urllib.request.Request(
        f"{SERVER}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        raw = data["choices"][0]["message"]["content"].strip()
        # strip markdown fences if present
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        return json.loads(raw)
    except Exception as e:
        return {"a": "fail", "r": str(e)}

# ── Stream final answer to user ──────────────────────────────────────

def stream_answer(task: str, result_text: str):
    """Stream the final answer from amallo."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content":
                "You are AXISCHROME. The browser completed a task and found the following content. "
                "Answer the user's original task clearly and directly using this content."},
            {"role": "user", "content": f"TASK: {task}\n\nFOUND:\n{result_text}"}
        ],
        "stream": True,
        "temperature": 0.3
    }
    req = urllib.request.Request(
        f"{SERVER}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            for raw in r:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    token = json.loads(chunk)["choices"][0]["delta"].get("content","")
                    if token:
                        print(token, end="", flush=True)
                except:
                    pass
        print()
    except Exception as e:
        print(f"\n[axischrome] stream error: {e}")

# ── Main loop ────────────────────────────────────────────────────────

def run(task: str, url: str = None):
    if not HAS_BROWSER:
        print("[axischrome] no browser — falling back to text fetch")
        # minimal urllib fallback
        target = url or DDG.format(urllib.parse.quote_plus(task))
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "AXISCHROME/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                import re
                html = r.read().decode("utf-8", errors="ignore")
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text)[:5000]
        except Exception as e:
            print(f"[axischrome] fetch error: {e}")
            return
        print("\n")
        stream_answer(task, text)
        return

    # navigate to start
    target = url or DDG.format(urllib.parse.quote_plus(task))
    print(f"[axischrome] 🌐 {target}", file=sys.stderr)
    goto(target)

    # action loop — screenshot → think → act → repeat
    for step in range(1, MAX_STEPS + 1):
        text = _page_text()
        print(f"[axischrome] step {step} — {len(text)} chars", file=sys.stderr)

        action = next_action(task, text, step)
        a = action.get("a", "fail")

        if a == "done":
            print(f"\n", file=sys.stderr)
            stream_answer(task, action.get("r", text))
            return

        if a == "fail":
            print(f"[axischrome] ✗ {action.get('r','unknown')}")
            return

        if a == "click":
            click(int(action.get("x", 0)), int(action.get("y", 0)))
            _page.wait_for_timeout(800)

        elif a == "key":
            key(action.get("k", ""))
            _page.wait_for_timeout(600)

        else:
            print(f"[axischrome] unknown action: {action}")
            break

    # exhausted steps — return whatever is on screen
    print("\n", file=sys.stderr)
    stream_answer(task, _page_text())


def main():
    args = sys.argv[1:]
    if not args:
        prompt = sys.stdin.read().strip()
        if not prompt:
            print("Usage: axischrome.py <url or search query> [task]")
            sys.exit(1)
        args = [prompt]

    if args[0].startswith("http://") or args[0].startswith("https://"):
        url  = args[0]
        task = " ".join(args[1:]) or "Summarize the main content of this page."
    else:
        url  = None
        task = " ".join(args)

    run(task, url)

    if HAS_BROWSER:
        _browser.close()
        _pw_ctx.__exit__(None, None, None)

if __name__ == "__main__":
    main()
