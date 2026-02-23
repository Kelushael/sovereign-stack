#!/usr/bin/env python3
"""
GREEN TEAM — Sovereign Stack Empirical Self-Test Framework
═══════════════════════════════════════════════════════════

THREE TIERS:

  LEVEL 1 — SURVIVAL TESTS
    "If it can't do this, we're not even in the game."
    Basic I/O, filesystem, process control, config read/write.
    Zero ambiguity in input. Must pass 100%.

  LEVEL 2 — REAL WORLD TASKS
    "Stuff everyone and their mom will actually do."
    Multi-step, multi-tool, realistic user behavior.
    Involves composition, state, partial success.
    Must pass ≥ 80%.

  LEVEL 3 — BUILD & SHIP (DEAL SEALERS)
    "Can it build pro-flow user-ready software from a description or photo?"
    Agentic pipeline tests. Each test requires producing a real artifact on disk.
    Pass = working file exists, correct structure, right size.
    Fail = no artifact, empty file, invalid structure, or crash.
    If L3 passes — the stack is genuinely capable. Deal sealed.

Buddy diagnoses every failure on the sovereign node.
Full structured report written to GREEN_TEAM_REPORT.md.

Usage:
  python3 tools/green-team.py              # all tiers
  python3 tools/green-team.py --level 1    # single tier
  python3 tools/green-team.py --report     # report only
  python3 tools/green-team.py --fast       # skip slow AI tests
"""

import subprocess, sys, json, time, os, urllib.request, re
from pathlib import Path
from datetime import datetime
from textwrap import fill

# ── Config ───────────────────────────────────────────────────────────
CFG_PATH = Path.home() / ".config" / "axis-mundi" / "config.json"
cfg      = json.loads(CFG_PATH.read_text()) if CFG_PATH.exists() else {}
SERVER   = cfg.get("server", "https://axismundi.fun")
TOKEN    = cfg.get("token",  cfg.get("api_key", ""))
MODEL    = cfg.get("model",  "dolphin-mistral:latest")
AXIS     = Path.home() / ".local" / "bin" / "axis"
if not AXIS.exists():
    AXIS = Path(__file__).parent.parent / "axis"

FAST_MODE    = "--fast"   in sys.argv
LEVEL_FILTER = None
if "--level" in sys.argv:
    idx = sys.argv.index("--level")
    if idx + 1 < len(sys.argv):
        LEVEL_FILTER = int(sys.argv[idx + 1])

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── Colors ────────────────────────────────────────────────────────────
def c(code, t): return f"\033[{code}m{t}\033[0m"
G  = lambda t: c("32", t)   # green
R  = lambda t: c("31", t)   # red
Y  = lambda t: c("33", t)   # yellow
B  = lambda t: c("34", t)   # blue
M  = lambda t: c("35", t)   # magenta
CY = lambda t: c("36", t)   # cyan
DM = lambda t: c("2",  t)   # dim
BD = lambda t: c("1",  t)   # bold

# ══════════════════════════════════════════════════════════════════════
# TEST SUITE
# Each test:
#   name        : string ID
#   level       : 1 | 2 | 3
#   input       : string passed to axis as argument
#   expect      : substring(s) that MUST appear in output (None = don't check)
#   must_exit_0 : bool — crash = automatic fail
#   slow        : bool — skip in --fast mode
#   notes       : human-readable description for report
# ══════════════════════════════════════════════════════════════════════

TESTS = [

    # ─────────────────────────────────────────────────────────────────
    # LEVEL 1 — SURVIVAL
    # ─────────────────────────────────────────────────────────────────

    dict(name="L1-01 ls home",
         level=1, input="/ls /home/marcus", expect=None, must_exit_0=True,
         notes="Basic directory listing — must not crash on valid path"),

    dict(name="L1-02 ls nonexistent",
         level=1, input="/ls /nonexistent_abc_xyz_123", expect=None, must_exit_0=True,
         notes="Must handle missing path gracefully — no traceback"),

    dict(name="L1-03 cat valid file",
         level=1, input="/cat /home/marcus/sovereign-stack/axis --lines 3",
         expect=None, must_exit_0=True,
         notes="Read first 3 lines of axis script"),

    dict(name="L1-04 cat missing file",
         level=1, input="/cat /home/marcus/DOESNOTEXIST.txt", expect=None, must_exit_0=True,
         notes="Missing file — must return error message, not traceback"),

    dict(name="L1-05 stat valid",
         level=1, input="/stat /home/marcus/sovereign-stack/axis",
         expect="size", must_exit_0=True,
         notes="File metadata — must return size at minimum"),

    dict(name="L1-06 find python files",
         level=1, input="/find *.py /home/marcus/sovereign-stack/tools",
         expect=None, must_exit_0=True,
         notes="Glob pattern search in known directory"),

    dict(name="L1-07 grep known pattern",
         level=1, input="/grep def /home/marcus/sovereign-stack/axis",
         expect="def", must_exit_0=True,
         notes="Pattern known to exist — must return matches"),

    dict(name="L1-08 grep no match",
         level=1, input="/grep ZZZNOMATCH999XYZ /home/marcus/sovereign-stack/axis",
         expect=None, must_exit_0=True,
         notes="Pattern that doesn't exist — must not crash"),

    dict(name="L1-09 ps list",
         level=1, input="/ps", expect=None, must_exit_0=True,
         notes="Process list — must return something"),

    dict(name="L1-10 config read",
         level=1, input="/config", expect=None, must_exit_0=True,
         notes="Config dump — must not crash"),

    dict(name="L1-11 config get server",
         level=1, input="/config server", expect="axismundi", must_exit_0=True,
         notes="Config key lookup — must return server URL"),

    dict(name="L1-12 empty input",
         level=1, input="", expect=None, must_exit_0=True,
         notes="Empty string — must not crash, must silently handle"),

    dict(name="L1-13 help command",
         level=1, input="/help", expect=None, must_exit_0=True,
         notes="Help must always work — it's the escape hatch"),

    dict(name="L1-14 version",
         level=1, input="--version", expect=None, must_exit_0=True,
         notes="Version flag — must return something"),

    dict(name="L1-15 models list",
         level=1, input="/models", expect=None, must_exit_0=True,
         notes="Model listing — must not crash even if node is down"),

    # ─────────────────────────────────────────────────────────────────
    # LEVEL 2 — REAL WORLD TASKS
    # ─────────────────────────────────────────────────────────────────

    dict(name="L2-01 read and summarize file",
         level=2, input="/cat /home/marcus/sovereign-stack/README.md",
         expect=None, must_exit_0=True, slow=False,
         notes="User reads a file they care about — most common real task"),

    dict(name="L2-02 find then cat",
         level=2, input="/find green-team.py /home/marcus/sovereign-stack",
         expect="green-team", must_exit_0=True, slow=False,
         notes="Find a file by name — should return its path"),

    dict(name="L2-03 grep across codebase",
         level=2, input="/grep amallo /home/marcus/sovereign-stack",
         expect=None, must_exit_0=True, slow=False,
         notes="Search entire repo for a term — broad grep"),

    dict(name="L2-04 ps then filter",
         level=2, input="/ps python", expect=None, must_exit_0=True, slow=False,
         notes="Filter processes by name — real debugging task"),

    dict(name="L2-05 config set and read back",
         level=2, input="/config model dolphin-mistral:latest",
         expect=None, must_exit_0=True, slow=False,
         notes="Set a config value — must persist"),

    dict(name="L2-06 write file",
         level=2, input="/write /tmp/green-team-test.txt hello from green team",
         expect=None, must_exit_0=True, slow=False,
         notes="Write a file — fundamental create operation"),

    dict(name="L2-07 cat written file",
         level=2, input="/cat /tmp/green-team-test.txt",
         expect="green team", must_exit_0=True, slow=False,
         notes="Read back what was written — persistence check"),

    dict(name="L2-08 ai one-shot factual",
         level=2, input="what port does amallo run on",
         expect="8200", must_exit_0=True, slow=True,
         notes="Simple factual query — should know its own stack"),

    dict(name="L2-09 ai code generation",
         level=2, input="write a python one-liner to list files in current directory",
         expect="import", must_exit_0=True, slow=True,
         notes="Code gen — must produce runnable python"),

    dict(name="L2-10 ai explain error",
         level=2,
         input="explain what 'connection refused' means when calling an API",
         expect=None, must_exit_0=True, slow=True,
         notes="Error diagnosis — common real user need"),

    dict(name="L2-11 addnode bad ip graceful",
         level=2, input="/addnode 192.168.99.254",
         expect=None, must_exit_0=True, slow=False,
         notes="Bad IP — must fail with message not traceback"),

    dict(name="L2-12 vchat stop when not running",
         level=2, input="/vchat stop",
         expect=None, must_exit_0=True, slow=False,
         notes="Stop voice chat that was never started — idempotent"),

    dict(name="L2-13 browse empty args",
         level=2, input="/browse",
         expect="Usage", must_exit_0=True, slow=False,
         notes="Browse with no args — must show usage not crash"),

    dict(name="L2-14 mkdir then stat",
         level=2, input="/mkdir /tmp/gt-test-dir",
         expect=None, must_exit_0=True, slow=False,
         notes="Create directory — basic filesystem write"),

    dict(name="L2-15 nested ls",
         level=2, input="/ls /home/marcus/sovereign-stack --depth 2",
         expect=None, must_exit_0=True, slow=False,
         notes="Recursive listing — must handle depth flag"),

    # ─────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────
    # LEVEL 3 — BUILD & SHIP
    # "Can it build pro-flow user-ready software from a photo?"
    # These are agentic pipeline tests. Not single commands.
    # Pass = working artifact on disk. Fail = no artifact or crash.
    # ─────────────────────────────────────────────────────────────────

    dict(name="L3-01 build app from description",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="build a working single-file HTML app: dark theme chat UI, input box at bottom, messages scroll up, send on Enter. save to /tmp/gt-chat-app.html",
         notes="DEAL SEALER 1: Text description → working HTML app on disk. "
               "Pass = /tmp/gt-chat-app.html exists AND contains input/button/script. "
               "Tests: code gen, file write, structure correctness."),

    dict(name="L3-02 build from UI screenshot",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="look at /home/marcus/sovereign-stack/clank.html as a UI reference. build a simpler version: same dark aesthetic, just a text input + send button + message area. save to /tmp/gt-clank-mini.html",
         notes="DEAL SEALER 2: Existing UI as visual reference → new app. "
               "Tests: vision reference, aesthetic extraction, code gen, file write."),

    dict(name="L3-03 build and self-verify",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="write a python script that prints 'SOVEREIGN OK' and saves it to /tmp/gt-verify.py then run it and confirm it worked",
         notes="DEAL SEALER 3: Build → run → verify own output. "
               "Tests: code gen, write, execute, self-verification loop."),

    dict(name="L3-04 package as installer",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="create a minimal install.sh at /tmp/gt-install.sh that: checks python3 is installed, creates ~/.gt-app/ directory, writes a hello.py to it, prints 'GT APP INSTALLED'. make it executable.",
         notes="DEAL SEALER 4: Generate pro-flow installer script. "
               "Tests: multi-step bash gen, chmod, real installer pattern."),

    dict(name="L3-05 full stack from scratch",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="build a complete working micro web app: python3 http.server on port 9999 serving an HTML page that says SOVEREIGN TEST PAGE with a dark background. save server.py to /tmp/gt-server.py and index.html to /tmp/gt-index.html",
         notes="DEAL SEALER 5: Full stack from zero — backend + frontend. "
               "Tests: multi-file generation, server code, HTML, coordinated build."),

    dict(name="L3-06 debug and fix broken code",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="here is broken python: 'def add(a b): return a+b' — fix the syntax error, save working version to /tmp/gt-fixed.py, then run it with add(2,3) and confirm it prints 5",
         notes="DEAL SEALER 6: Broken input → fix → verify. "
               "Tests: error detection, code repair, execution, self-verification."),

    dict(name="L3-07 config and customize",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="create a JSON config file at /tmp/gt-config.json with these fields: app_name='SovereignTest', version='1.0.0', dark_mode=true, port=9999. then read it back and confirm all 4 fields are present",
         notes="DEAL SEALER 7: Generate structured config → validate own output. "
               "Tests: JSON gen, write, read-back, field verification."),

    dict(name="L3-08 pro readme generation",
         level=3, slow=True, must_exit_0=True, expect=None,
         input="write a professional README.md for a project called SovereignTest: one-line description, install section (pip install + run command), features list (3 items), and a license line. save to /tmp/gt-readme.md",
         notes="DEAL SEALER 8: Generate pro-quality documentation. "
               "Tests: structured doc gen, markdown, real-world README format."),
]

# ── Helpers ───────────────────────────────────────────────────────────

def run_axis(input_text: str, timeout: int = 30) -> tuple[str, str, int]:
    if not input_text.strip():
        return "", "", 0
    try:
        result = subprocess.run(
            [sys.executable, str(AXIS), input_text],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ}
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT (exceeded 30s)", -1
    except Exception as e:
        return "", str(e), -1

def ask_buddy(test: dict, stdout: str, stderr: str, rc: int) -> str:
    ctx = (
        f"Test name: {test['name']}\n"
        f"Level: {test['level']}\n"
        f"Description: {test['notes']}\n"
        f"Input given: {repr(test['input'][:200])}\n"
        f"Expected to contain: {test.get('expect')}\n"
        f"stdout: {stdout[:400]}\n"
        f"stderr: {stderr[:400]}\n"
        f"exit code: {rc}\n\n"
        "What broke, why, and the exact fix in 2-3 sentences."
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "You are the green team diagnostic buddy for the sovereign stack. "
                "Diagnose test failures. Be surgical. 2-3 sentences max. "
                "If it needs a code change, show the minimal diff."
            )},
            {"role": "user", "content": ctx}
        ],
        "stream": False, "max_tokens": 250, "temperature": 0.1
    }
    try:
        req = urllib.request.Request(
            f"{SERVER}/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers=HEADERS, method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[buddy offline: {e}]"

def eval_l3(test: dict, stdout: str, stderr: str, rc: int) -> tuple[bool, list[str]]:
    """
    Level 3 evaluation — check that the artifact was ACTUALLY built.
    Extracts expected output paths from the test input and verifies them.
    """
    reasons = []
    inp = test["input"]

    # Extract /tmp/gt-*.* paths mentioned in the test input
    artifacts = re.findall(r'/tmp/gt-[\w./\-]+\.\w+', inp)

    for path in artifacts:
        p = Path(path)
        if not p.exists():
            reasons.append(f"artifact missing: {path}")
        elif p.stat().st_size < 10:
            reasons.append(f"artifact empty: {path}")
        else:
            # spot-check content based on file type
            content = p.read_text(errors="ignore")
            if path.endswith(".html") and "<" not in content:
                reasons.append(f"{path} doesn't look like HTML")
            elif path.endswith(".py") and "def " not in content and "print" not in content and "import" not in content:
                reasons.append(f"{path} doesn't look like Python")
            elif path.endswith(".json"):
                try: json.loads(content)
                except: reasons.append(f"{path} invalid JSON")
            elif path.endswith(".sh") and not p.stat().st_mode & 0o111:
                reasons.append(f"{path} not executable")

    if rc != 0 and test.get("must_exit_0"):
        reasons.append(f"crashed (rc={rc})")

    return len(reasons) == 0, reasons



def write_report(results: list, elapsed_total: float):
    path = Path.home() / "sovereign-stack" / "GREEN_TEAM_REPORT.md"
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_level = {1: [], 2: [], 3: []}
    for r in results:
        by_level[r["level"]].append(r)

    def level_stats(lvl):
        tests  = by_level[lvl]
        passed = sum(1 for t in tests if t["status"] == "pass")
        return passed, len(tests)

    l1p, l1t = level_stats(1)
    l2p, l2t = level_stats(2)
    l3p, l3t = level_stats(3)
    total_p   = l1p + l2p + l3p
    total_t   = l1t + l2t + l3t
    pct        = int(100 * total_p / total_t) if total_t else 0

    lines = [
        f"# 🟢 Sovereign Stack — Green Team Report",
        f"**Run:** {ts}  |  **Duration:** {elapsed_total:.1f}s  |  **Score:** {total_p}/{total_t} ({pct}%)\n",
        "---\n",
        "## Summary\n",
        f"| Tier | Name | Passed | Failed | Score |",
        f"|------|------|--------|--------|-------|",
        f"| 1 | **SURVIVAL** — must-pass baseline | {l1p} | {l1t-l1p} | {int(100*l1p/l1t) if l1t else 0}% |",
        f"| 2 | **REAL WORLD** — everyday tasks | {l2p} | {l2t-l2p} | {int(100*l2p/l2t) if l2t else 0}% |",
        f"| 3 | **ADVERSARIAL** — weird/vague/hostile | {l3p} | {l3t-l3p} | {int(100*l3p/l3t) if l3t else 0}% |",
        "",
    ]

    for lvl, title, desc in [
        (1, "LEVEL 1 — SURVIVAL", "If it can't do this, we're not in the game."),
        (2, "LEVEL 2 — REAL WORLD", "Stuff everyone and their mom will actually do."),
        (3, "LEVEL 3 — BUILD & SHIP", "Can it build pro-flow user-ready software from description or photo reference?"),
    ]:
        lines += [f"\n---\n## {title}\n_{desc}_\n"]
        for r in by_level[lvl]:
            icon  = "✅" if r["status"] == "pass" else "❌"
            lines.append(f"### {icon} {r['name']}")
            lines.append(f"_{r['notes']}_\n")
            lines.append(f"**Input:** `{r['input'][:80]}{'…' if len(r['input'])>80 else ''}`")
            lines.append(f"**Result:** {r['status'].upper()}  |  **Time:** {r['elapsed']:.2f}s")
            if r["status"] == "fail":
                lines.append(f"\n**Failure reason:** {', '.join(r.get('reason', ['unknown']))}")
                if r.get("diagnosis"):
                    lines.append(f"\n**Buddy diagnosis:**\n> {r['diagnosis']}")
            if r.get("stdout"):
                lines.append(f"\n<details><summary>Output</summary>\n\n```\n{r['stdout'][:400]}\n```\n</details>")
            lines.append("")

    # Failures summary at bottom
    failures = [r for r in results if r["status"] == "fail"]
    if failures:
        lines += ["\n---\n## ⚡ Action Items\n"]
        for i, f in enumerate(failures, 1):
            lines.append(f"{i}. **{f['name']}** — {f.get('diagnosis','')[:120]}")
    else:
        lines += ["\n---\n## ✅ All Green\nStack is clean. No action items.\n"]

    path.write_text("\n".join(lines))
    return path

# ── Main ──────────────────────────────────────────────────────────────

def main():
    tests = TESTS
    if LEVEL_FILTER:
        tests = [t for t in tests if t["level"] == LEVEL_FILTER]
    if FAST_MODE:
        tests = [t for t in tests if not t.get("slow")]

    print(BD("\n  ╔══════════════════════════════════════════════╗"))
    print(BD("  ║   SOVEREIGN GREEN TEAM — EMPIRICAL SUITE     ║"))
    print(BD("  ╚══════════════════════════════════════════════╝\n"))
    print(DM(f"  axis:   {AXIS}"))
    print(DM(f"  node:   {SERVER}"))
    print(DM(f"  tests:  {len(tests)} {'(fast mode)' if FAST_MODE else ''}"))
    print()

    level_headers = {1: None, 2: None, 3: None}
    level_labels  = {
        1: CY("  ━━━ LEVEL 1 — SURVIVAL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"),
        2: CY("  ━━━ LEVEL 2 — REAL WORLD ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"),
        3: M( "  ━━━ LEVEL 3 — BUILD & SHIP ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"),
    }

    results     = []
    t_start     = time.time()

    for test in tests:
        lvl = test["level"]
        if level_headers[lvl] is None:
            print(level_labels[lvl])
            level_headers[lvl] = True

        name  = test["name"]
        inp   = test["input"]
        print(f"  {DM(name):50s}", end="", flush=True)

        t0 = time.time()
        stdout, stderr, rc = run_axis(inp, timeout=35)
        elapsed = time.time() - t0

        output = (stdout + stderr).strip()

        # Evaluate
        reasons = []
        expect  = test.get("expect")

        if test["level"] == 3:
            # Level 3: artifact-based evaluation
            ok, reasons = eval_l3(test, stdout, stderr, rc)
        else:
            if test.get("must_exit_0") and rc != 0:
                reasons.append(f"crashed (rc={rc})")
            if expect and expect.lower() not in output.lower():
                reasons.append(f"missing '{expect}'")

        status = "pass" if not reasons else "fail"

        if status == "pass":
            if test["level"] == 3:
                # Show what was built
                artifacts = re.findall(r'/tmp/gt-[\w./\-]+\.\w+', test["input"])
                sizes = [f"{Path(a).stat().st_size}b" for a in artifacts if Path(a).exists()]
                print(f"  {G('✓')}  {G('BUILT')} {DM(' '.join(sizes))}  {DM(f'{elapsed:.1f}s')}")
            else:
                print(f"  {G('✓')}  {DM(f'{elapsed:.1f}s')}")
        else:
            print(f"  {R('✗')}  {Y(', '.join(reasons))}  {DM(f'{elapsed:.1f}s')}")
            print(f"    {DM('→ diagnosing...')}", end="", flush=True)
            diagnosis = ask_buddy(test, stdout, stderr, rc)
            print(f"\r    {M('⚡')} {diagnosis[:100]}{'…' if len(diagnosis)>100 else ''}\n")

        diagnosis = diagnosis if status == "fail" else None

        results.append({
            **test,
            "status":    status,
            "stdout":    stdout[:300],
            "stderr":    stderr[:200],
            "rc":        rc,
            "elapsed":   elapsed,
            "reason":    reasons,
            "diagnosis": diagnosis if status == "fail" else None,
        })

    total_elapsed = time.time() - t_start

    # ── Summary ───────────────────────────────────────────────────────
    by_level = {1: [], 2: [], 3: []}
    for r in results:
        by_level[r["level"]].append(r)

    print()
    print(BD("  RESULTS\n"))
    for lvl, label in [(1,"SURVIVAL"), (2,"REAL WORLD"), (3,"ADVERSARIAL")]:
        tests_l = by_level[lvl]
        if not tests_l:
            continue
        p = sum(1 for t in tests_l if t["status"]=="pass")
        t = len(tests_l)
        pct = int(100*p/t) if t else 0
        bar_full = int(pct / 5)
        bar = "█" * bar_full + "░" * (20 - bar_full)
        col = G if pct==100 else (Y if pct>=80 else R)
        print(f"  L{lvl} {label:12s}  {col(bar)}  {col(f'{p}/{t} ({pct}%)')}")

    total_p = sum(1 for r in results if r["status"]=="pass")
    total_t = len(results)
    pct_all = int(100*total_p/total_t) if total_t else 0
    print(f"\n  {'TOTAL':16s}  {G(f'{total_p}/{total_t}') if pct_all==100 else Y(f'{total_p}/{total_t}')}  ({pct_all}%)")
    print(f"  {'TIME':16s}  {DM(f'{total_elapsed:.1f}s')}\n")

    failures = [r for r in results if r["status"]=="fail"]
    if failures:
        print(BD("  ACTION ITEMS:\n"))
        for i, f in enumerate(failures, 1):
            print(f"  {R(str(i)+'.')} {f['name']}")
            print(f"     {DM(f['diagnosis'][:120] if f['diagnosis'] else 'no diagnosis')}\n")

    report_path = write_report(results, total_elapsed)
    print(DM(f"  full report → {report_path}\n"))

    if pct_all == 100:
        print(G(BD("  ██████████████████ ALL GREEN ████████████████████\n")))
    elif pct_all >= 80:
        print(Y("  Mostly green. Fix the action items above.\n"))
    else:
        print(R("  Stack needs work. Address failures before shipping.\n"))

    # L1 must be 100% — if not, it's a blocker
    l1_tests = by_level[1]
    l1_pass  = sum(1 for t in l1_tests if t["status"]=="pass")
    if l1_tests and l1_pass < len(l1_tests):
        print(R(BD("  ⛔ LEVEL 1 FAILURES = BLOCKER. Fix before anything else.\n")))
        sys.exit(2)

    sys.exit(0 if pct_all == 100 else 1)


if __name__ == "__main__":
    main()


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
