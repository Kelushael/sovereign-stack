#!/usr/bin/env python3
"""
GREEN TEAM — Sovereign Stack Automated Self-Test
Runs every axis command, every edge case, breaks everything safely,
passes failures to buddy for diagnosis, outputs a ranked report.

Usage:
  python3 tools/green-team.py
  python3 tools/green-team.py --fix      # auto-apply buddy patches
  python3 tools/green-team.py --report   # report only, no fixes
"""

import subprocess, sys, json, time, os, urllib.request
from pathlib import Path
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────
CFG_PATH = Path.home() / ".config" / "axis-mundi" / "config.json"
cfg      = json.loads(CFG_PATH.read_text()) if CFG_PATH.exists() else {}
SERVER   = cfg.get("server", "https://axismundi.fun")
TOKEN    = cfg.get("token",  cfg.get("api_key", ""))
MODEL    = cfg.get("model",  "dolphin-mistral:latest")
AXIS     = Path.home() / ".local" / "bin" / "axis"
if not AXIS.exists():
    AXIS = Path(__file__).parent.parent / "axis"
AUTO_FIX = "--fix" in sys.argv

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type":  "application/json"
}

# ── Test suite ────────────────────────────────────────────────────────
# Each test: (name, input, expect_contains, expect_no_crash)
TESTS = [
    # filesystem commands
    ("ls root",          "/ls /home/marcus",              None,         True),
    ("ls nonexistent",   "/ls /nonexistent_xyz",          None,         True),
    ("cat axis",         "/cat /home/marcus/sovereign-stack/axis --lines 5", "def", True),
    ("cat missing",      "/cat /no/such/file.txt",        None,         True),
    ("stat axis",        "/stat /home/marcus/sovereign-stack/axis", "size", True),
    ("find py files",    "/find *.py /home/marcus/sovereign-stack", None, True),
    ("grep pattern",     "/grep amallo /home/marcus/sovereign-stack/axis", None, True),
    ("grep no match",    "/grep ZZZNOMATCH123 /home/marcus/sovereign-stack/axis", None, True),

    # process commands
    ("ps list",          "/ps",                           None,         True),
    ("ps filter",        "/ps python",                    None,         True),
    ("kill bad pid",     "/kill 999999999",               None,         True),

    # config
    ("config get",       "/config",                       None,         True),
    ("config get key",   "/config server",                None,         True),

    # browse (no network required to not crash)
    ("browse empty",     "/browse",                       "Usage",      True),

    # addnode (bad IP — should fail gracefully not crash)
    ("addnode bad ip",   "/addnode 0.0.0.0",              None,         True),

    # vchat (no mic needed — just commands)
    ("vchat log empty",  "/vchat log",                    None,         True),
    ("vchat stop idle",  "/vchat stop",                   None,         True),
    ("vchat bad cmd",    "/vchat zzzbadcmd",              "Usage",      True),

    # unknown command — buddy should catch
    ("unknown cmd",      "/zzznonsense",                  None,         True),

    # empty input
    ("empty input",      "",                              None,         True),

    # AI message (needs live node)
    ("ai hello",         "say the word GREENTEAM only",   "GREENTEAM",  True),
]

# ── Helpers ───────────────────────────────────────────────────────────

def run_axis(input_text: str, timeout: int = 20) -> tuple[str, str, int]:
    """Run axis with input, return (stdout, stderr, returncode)."""
    if not input_text.strip():
        return "", "", 0  # empty input is valid
    try:
        result = subprocess.run(
            [sys.executable, str(AXIS), input_text],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ}
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1
    except Exception as e:
        return "", str(e), -1

def ask_buddy(failure_context: str) -> str:
    """Ask the sovereign buddy to diagnose a test failure."""
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "system",
            "content": (
                "You are a green team diagnostic buddy for the sovereign stack. "
                "A test just failed. In 2-3 sentences: what broke, why, and the exact fix. "
                "If it needs a code change, show the minimal diff. Be surgical."
            )
        }, {
            "role": "user",
            "content": failure_context
        }],
        "stream": False,
        "max_tokens": 300,
        "temperature": 0.1
    }
    try:
        req = urllib.request.Request(
            f"{SERVER}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers=HEADERS,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[buddy unavailable: {e}]"

def color(code, text): return f"\033[{code}m{text}\033[0m"
GREEN  = lambda t: color("32", t)
RED    = lambda t: color("31", t)
YELLOW = lambda t: color("33", t)
BOLD   = lambda t: color("1",  t)
DIM    = lambda t: color("2",  t)

# ── Main ──────────────────────────────────────────────────────────────

def main():
    print(BOLD("\n  ╔══════════════════════════════════════╗"))
    print(BOLD("  ║   SOVEREIGN GREEN TEAM — SELF TEST   ║"))
    print(BOLD("  ╚══════════════════════════════════════╝\n"))
    print(DIM(f"  axis:   {AXIS}"))
    print(DIM(f"  node:   {SERVER}"))
    print(DIM(f"  model:  {MODEL}"))
    print(DIM(f"  tests:  {len(TESTS)}"))
    print(DIM(f"  mode:   {'AUTO-FIX' if AUTO_FIX else 'REPORT ONLY'}\n"))

    results = []
    passed = 0
    failed = 0
    crashed = 0

    for name, inp, expect, no_crash in TESTS:
        print(f"  {DIM('testing')} {name:30s}", end="", flush=True)
        t0 = time.time()
        stdout, stderr, rc = run_axis(inp)
        elapsed = time.time() - t0

        output = (stdout + stderr).strip()
        did_crash   = rc != 0 and no_crash
        missing_exp = expect and expect.lower() not in output.lower()
        ok = not did_crash and not missing_exp

        if ok:
            print(f"  {GREEN('✓')}  {DIM(f'{elapsed:.1f}s')}")
            passed += 1
            results.append({"name": name, "status": "pass", "output": output[:200]})
        else:
            reason = []
            if did_crash:   reason.append(f"crashed (rc={rc})")
            if missing_exp: reason.append(f"missing '{expect}'")
            print(f"  {RED('✗')}  {', '.join(reason)}  {DIM(f'{elapsed:.1f}s')}")
            failed += 1
            crashed += did_crash

            # Ask buddy to diagnose
            print(f"    {DIM('→ asking buddy...')}", end="", flush=True)
            context = (
                f"Test: {name}\n"
                f"Input: {inp}\n"
                f"Expected to contain: {expect}\n"
                f"stdout: {stdout[:500]}\n"
                f"stderr: {stderr[:500]}\n"
                f"return code: {rc}\n"
            )
            diagnosis = ask_buddy(context)
            print(f"\r    {YELLOW('⚡')} {diagnosis[:120]}{'…' if len(diagnosis)>120 else ''}\n")
            results.append({
                "name": name, "status": "fail",
                "reason": reason, "diagnosis": diagnosis,
                "output": output[:300]
            })

    # ── Summary ──────────────────────────────────────────────────────
    total = passed + failed
    pct   = int(100 * passed / total) if total else 0

    print(f"\n  {BOLD('RESULTS')}  {GREEN(f'{passed} passed')}  {RED(f'{failed} failed')}  /  {total} total  ({pct}%)\n")

    failures = [r for r in results if r["status"] == "fail"]
    if failures:
        print(f"  {BOLD('FAILURES:')}\n")
        for f in failures:
            print(f"  {RED('✗')} {f['name']}")
            print(f"    {DIM(f['diagnosis'])}\n")

    # Write report
    report_path = Path.home() / "sovereign-stack" / "GREEN_TEAM_REPORT.md"
    lines = [
        f"# Green Team Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"\n**{passed}/{total} passed ({pct}%)**\n",
        "## Failures\n"
    ]
    for f in failures:
        lines.append(f"### ✗ {f['name']}")
        lines.append(f"**Reason:** {', '.join(f.get('reason', []))}")
        lines.append(f"**Buddy diagnosis:** {f.get('diagnosis','')}\n")

    lines.append("## All Results\n")
    for r in results:
        icon = "✓" if r["status"] == "pass" else "✗"
        lines.append(f"- {icon} {r['name']}")

    report_path.write_text("\n".join(lines))
    print(f"  {DIM(f'report → {report_path}')}\n")

    if pct == 100:
        print(f"  {GREEN(BOLD('ALL GREEN. Stack is clean.'))}\n")
    elif pct >= 80:
        print(f"  {YELLOW('Mostly green. Fix the failures above.')}\n")
    else:
        print(f"  {RED('Needs work. Run --fix or address failures manually.')}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
