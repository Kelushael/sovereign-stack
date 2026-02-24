#!/usr/bin/env python3
"""
sovereign — Axis Mundi terminal
================================
Type sovereign. You're in your stack.

Zero config. Zero local compute.
Token read from ~/.axis-token automatically.
All inference, all tools run on axismundi.fun.

Usage:
  sovereign              # interactive shell
  sovereign "do this"    # one-shot
  sovereign list         # list available models
"""
import os, sys, json, re, time, threading, itertools
import requests

# ── DEFAULTS (zero config required) ─────────────────────────────────────────
SERVER    = "https://axismundi.fun"
MODEL_API = f"{SERVER}/v1"
MODEL     = "axis-model"            # whatever is loaded via current.gguf

# ── PERSISTENCE (auto-created on first use) ──────────────────────────────────
_cfg_dir     = os.path.expanduser("~/.config/axis-mundi")
CMD_REGISTRY = f"{_cfg_dir}/commands.json"
TOOL_REGISTRY= f"{_cfg_dir}/tools.json"
SELF         = os.path.abspath(__file__)   # this file — model can propose edits

# ── ANSI ─────────────────────────────────────────────────────────────────────
PINK = "\033[38;2;255;105;180m"
LIME = "\033[38;2;57;255;100m"
CYAN = "\033[38;2;0;220;255m"
GOLD = "\033[38;2;255;200;50m"
GRAY = "\033[38;2;85;85;105m"
RED  = "\033[38;2;255;70;70m"
RST  = "\033[0m"
BOLD = "\033[1m"

BANNER = f"""
{PINK}{BOLD}  ╔══════════════════════════════════════════╗
  ║  SOVEREIGN  ·  AXIS MUNDI               ║
  ║  zero local compute  ·  your cloud      ║
  ╚══════════════════════════════════════════╝{RST}"""

# ── SPINNER ──────────────────────────────────────────────────────────────────
class Spin:
    def __init__(self, msg=""):
        self.msg = msg; self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
    def _run(self):
        for f in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if self._stop: break
            sys.stdout.write(f"\r  {CYAN}{f}{RST}  {self.msg}   ")
            sys.stdout.flush(); time.sleep(0.1)
    def __enter__(self): self._t.start(); return self
    def __exit__(self, *_):
        self._stop = True; self._t.join()
        sys.stdout.write("\r" + " " * (len(self.msg) + 12) + "\r")
        sys.stdout.flush()

# ── TOKEN (zero config) ───────────────────────────────────────────────────────
def load_token():
    """Read token from ~/.axis-token, then fallback to config.json. No setup needed."""
    # 1. ~/.axis-token  (set by axis --marcus, axismundi.fun auth)
    token_file = os.path.expanduser("~/.axis-token")
    if os.path.exists(token_file):
        t = open(token_file).read().strip()
        if t: return t

    # 2. ~/.config/axis-mundi/config.json
    cfg_file = f"{_cfg_dir}/config.json"
    if os.path.exists(cfg_file):
        try:
            t = json.load(open(cfg_file)).get("token", "")
            if t: return t
        except Exception:
            pass

    # 3. Env var
    return os.environ.get("AXIS_TOKEN", "")

# ── REGISTRIES ────────────────────────────────────────────────────────────────
def _load(path):
    try:
        return json.load(open(path))
    except Exception:
        return {}

def _save(path, data):
    os.makedirs(_cfg_dir, exist_ok=True)
    json.dump(data, open(path, "w"), indent=2)

# ── /addcmd ───────────────────────────────────────────────────────────────────
def handle_addcmd(line, cmds):
    m = re.match(r'^/addcmd\s+"([^"]+)"\s+"([^"]+)"$', line.strip())
    if not m:
        print(f'\n  {RED}usage:{RST}  /addcmd "name" "what it does"\n')
        return cmds
    name, desc = m.group(1).lower(), m.group(2)
    cmds[name] = desc
    _save(CMD_REGISTRY, cmds)
    print(f"\n  {LIME}✓  /{name}{RST}  →  {desc}  {GRAY}(saved){RST}\n")
    return cmds

def expand_cmd(line, cmds):
    """If /name matches a registered cmd, return its expansion. Else None."""
    m = re.match(r'^/(\w[\w-]*)(\s+.*)?$', line.strip())
    if not m: return None
    name = m.group(1).lower()
    if name not in cmds: return None
    extra = (m.group(2) or "").strip()
    expanded = f"{cmds[name]}{': ' + extra if extra else ''}"
    print(f"  {GRAY}↳  /{name}  →  {expanded}{RST}\n")
    return expanded

# ── /addtool ──────────────────────────────────────────────────────────────────
def handle_addtool(line, tools):
    """
    /addtool "name" "describe what it does" "shell command — {input} = model arg"
    Tools with {input}: model passes one string argument.
    Tools without {input}: model calls with no args (fixed command).
    """
    m = re.match(r'^/addtool\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"$', line.strip())
    if not m:
        print(f'\n  {RED}usage:{RST}  /addtool "name" "describe" "shell cmd ({{input}} = arg)"\n')
        return tools
    name, desc, cmd = m.group(1).lower(), m.group(2), m.group(3)
    tools[name] = {"description": desc, "command": cmd, "has_input": "{input}" in cmd}
    _save(TOOL_REGISTRY, tools)
    print(f"\n  {LIME}✓  tool:{RST} {CYAN}{name}{RST}  →  {desc}")
    print(f"  {GRAY}cmd: {cmd}  (saved){RST}\n")
    return tools

# ── TOOL SCHEMA ───────────────────────────────────────────────────────────────
def make_tools(custom_tools):
    """Hardcoded sovereign tools + any user-added tools from tools.json."""
    core = [
        {
            "type": "function",
            "function": {
                "name": "exec",
                "description": "Run a shell command on axismundi.fun. Returns stdout/stderr.",
                "parameters": {"type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file on the cloud server.",
                "parameters": {"type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write a file on the cloud server.",
                "parameters": {"type": "object",
                    "properties": {
                        "path":    {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "List a directory on the cloud server.",
                "parameters": {"type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "http_get",
                "description": "HTTP GET from the cloud server.",
                "parameters": {"type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "axis_chat",
                "description": (
                    "Delegate a complex task to the Axis Mundi cloud daemon — "
                    "it has full memory, filesystem access, and self-modification."
                ),
                "parameters": {"type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "axis_status",
                "description": "Check Axis Mundi daemon status — uptime, model, memory.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
    ]

    # Append user-defined tools (exec wrappers)
    for name, t in custom_tools.items():
        has_input = t.get("has_input", False)
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": t["description"],
                "parameters": {
                    "type": "object",
                    "properties": {"input": {"type": "string", "description": "Argument to pass."}} if has_input else {},
                    "required": ["input"] if has_input else []
                }
            }
        }
        core.append(schema)

    return core

# ── CALL TOOL ─────────────────────────────────────────────────────────────────
def call_tool(token, tool_name, args, custom_tools):
    """Route to Axis MCP for core tools; wrap custom tools as exec calls."""

    # Custom tool → exec wrapper
    if tool_name in custom_tools:
        t = custom_tools[tool_name]
        cmd = t["command"]
        if t.get("has_input") and "input" in args:
            cmd = cmd.replace("{input}", str(args["input"]))
        return call_tool(token, "exec", {"command": cmd}, custom_tools={})

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"name": tool_name, "arguments": args}
    try:
        r = requests.post(f"{SERVER}/mcp/tools/call", json=payload,
                          headers=headers, timeout=120)
        return r.json() if r.ok else {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

# ── CALL MODEL (VPS inference) ────────────────────────────────────────────────
def call_model(messages, tools, token):
    """Send to VPS model API. Entry node does zero inference."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"model": MODEL, "messages": messages, "tools": tools, "stream": False}
    try:
        r = requests.post(f"{MODEL_API}/chat/completions", json=payload,
                          headers=headers, timeout=300)
    except requests.exceptions.ConnectionError:
        return None, f"cannot reach {MODEL_API} — is the VPS up?"
    if not r.ok:
        return None, f"model API {r.status_code}: {r.text[:300]}"
    choice = r.json()["choices"][0]
    return choice["message"], choice.get("finish_reason")

# ── /run <model> swap ─────────────────────────────────────────────────────────
def run_model_swap(token, model_name):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"name": "exec", "arguments": {"command": f"sovereign-run {model_name}"}}
    try:
        r = requests.post(f"{SERVER}/mcp/tools/call", json=payload,
                          headers=headers, timeout=300)
        return r.json() if r.ok else {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

# ── AGENTIC LOOP ──────────────────────────────────────────────────────────────
def run_agent(user_msg, token, custom_tools, history=None):
    tools    = make_tools(custom_tools)
    messages = list(history or []) + [{"role": "user", "content": user_msg}]

    for round_n in range(12):
        label = f"{MODEL} thinking..." if round_n == 0 else f"{MODEL} (round {round_n+1})..."
        with Spin(label):
            msg, finish = call_model(messages, tools, token)

        if msg is None:
            print(f"\n{RED}  error: {finish}{RST}\n")
            return messages, None

        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls or finish == "stop":
            return messages, (msg.get("content") or "").strip()

        for tc in tool_calls:
            fn   = tc["function"]["name"]
            args = tc["function"].get("arguments", {})
            if isinstance(args, str):
                try:    args = json.loads(args)
                except: args = {}

            print(f"\n  {GOLD}⚙{RST}  {CYAN}{fn}{RST}  {GRAY}{json.dumps(args)[:80]}{RST}")
            with Spin(fn):
                result = call_tool(token, fn, args, custom_tools)
            result_str = json.dumps(result) if isinstance(result, dict) else str(result)
            print(f"  {LIME}↩  {result_str[:140]}{RST}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", fn),
                "name": fn,
                "content": result_str,
            })

    return messages, "(max rounds reached)"

# ── FORMATTER ─────────────────────────────────────────────────────────────────
def fmt(text):
    out, in_code = [], False
    for ln in text.split('\n'):
        if ln.startswith('```'):
            in_code = not in_code
            out.append(f"{GRAY}{ln}{RST}")
        elif in_code:
            out.append(f"{CYAN}{ln}{RST}")
        elif ln.startswith('#'):
            out.append(f"{LIME}{BOLD}{ln}{RST}")
        else:
            out.append(f"\033[38;2;200;220;255m{ln}{RST}")
    return '\n'.join(out)

# ── SHELL ─────────────────────────────────────────────────────────────────────
def shell(token):
    global MODEL
    cmds         = _load(CMD_REGISTRY)
    custom_tools = _load(TOOL_REGISTRY)

    print(BANNER)
    print(f"\n  {GRAY}cloud:{RST}  {CYAN}{SERVER}{RST}   {GRAY}model:{RST}  {LIME}{MODEL}{RST}")

    # Show registered custom cmds + tools in one line if any exist
    all_shortcuts = list(cmds.keys()) + list(custom_tools.keys())
    if all_shortcuts:
        items = "  ".join(f"{LIME}/{k}{RST}" for k in all_shortcuts)
        print(f"  {GRAY}yours:{RST}  {items}")

    print(f"  {GRAY}meta:{RST}   /run <model>  /addcmd  /addtool  /list  exit\n")

    system_prompt = (
        "You are a sovereign AI running on Axis Mundi (axismundi.fun). "
        "The user's entry terminal is zero-compute — all inference is you, on the VPS. "
        "Use exec to run commands on the server. Use read_file/write_file for files. "
        "axis_chat delegates to the full cloud daemon (memory, self-modification). "
        f"Your bridge source lives locally at: {SELF} — propose edits there to evolve the system. "
        "Be direct. When asked to do something, do it. Don't explain, act."
    )

    history = [{"role": "system", "content": system_prompt}]

    try: import readline
    except: pass

    while True:
        try:
            prompt = f"{PINK}{BOLD}sovereign{RST}{GRAY}@axis ›{RST} "
            msg = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GRAY}  ✦  sovereign out{RST}\n"); break

        if not msg: continue
        if msg.lower() in ("exit", "quit", "q"):
            print(f"\n{GRAY}  ✦  sovereign out{RST}\n"); break
        if msg.lower() == "clear":
            print("\033[2J\033[H", end=""); print(BANNER); continue

        # ── meta commands ──
        if msg.lower().startswith("/run "):
            model_name = msg[5:].strip()
            if model_name:
                print(f"\n  {GOLD}⟳  swapping to {model_name}...{RST}")
                with Spin(f"sovereign-run {model_name}"):
                    res = run_model_swap(token, model_name)
                if "error" not in str(res):
                    MODEL = model_name
                    print(f"  {LIME}✓  active: {MODEL}{RST}\n")
                else:
                    print(f"  {RED}✗  {res}{RST}\n")
            continue

        if msg.startswith("/addcmd"):
            cmds = handle_addcmd(msg, cmds); continue

        if msg.startswith("/addtool"):
            custom_tools = handle_addtool(msg, custom_tools); continue

        if msg.lower() in ("/list", "/listcmds", "/listtools"):
            print()
            if cmds:
                for k, v in cmds.items():
                    print(f"  {LIME}/{k}{RST}  {GRAY}cmd →{RST}  {v}")
            if custom_tools:
                for k, t in custom_tools.items():
                    print(f"  {CYAN}/{k}{RST}  {GRAY}tool →{RST}  {t['description']}")
            if not cmds and not custom_tools:
                print(f"  {GRAY}nothing registered yet{RST}")
            print(); continue

        # ── expand registered /shortcut ──
        expanded = expand_cmd(msg, cmds)
        if expanded is not None:
            msg = expanded

        history, reply = run_agent(msg, token, custom_tools, history)
        print(f"\n{fmt(reply)}\n" if reply else f"\n{RED}  no response{RST}\n")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    token = load_token()
    if not token:
        print(f"{RED}  no token found{RST}")
        print(f"  run:  {CYAN}bash ~/axismundi.fun{RST}  to authenticate")
        print(f"  or:   {CYAN}export AXIS_TOKEN=your-token{RST}")
        sys.exit(1)

    args = sys.argv[1:]

    if args and args[0] == "list":
        print(f"\n  {GRAY}asking VPS for available models...{RST}")
        res = call_tool(token, "exec", {"command": "sovereign-run list"}, {})
        print(res.get("output", res)); return

    if args:
        custom_tools = _load(TOOL_REGISTRY)
        _, reply = run_agent(" ".join(args), token, custom_tools)
        print(fmt(reply) if reply else f"{RED}no response{RST}")
    else:
        shell(token)

if __name__ == "__main__":
    main()
