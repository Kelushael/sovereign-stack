#!/usr/bin/env python3
"""
marshal.py — orange tarmac wand orchestrator
one agent per task. each finished piece integrates immediately.
the system gets more complete with every landing, not waiting for all.

usage:
  python3 marshal.py             # run all queued tasks
  python3 marshal.py add         # add a new task interactively
  python3 marshal.py status      # show fleet status
  python3 marshal.py do <id>     # run one specific task
"""

import sys, os, json, subprocess, time, threading, queue
from pathlib import Path
from datetime import datetime

# ── colors ────────────────────────────────────────────────────────────────────
R='\x1b[0m'; BOLD='\x1b[1m'; DIM='\x1b[2m'
ORANGE='\x1b[38;5;208m'; GREEN='\x1b[32m'; CYAN='\x1b[36m'
YELLOW='\x1b[33m'; RED='\x1b[31m'; PURPLE='\x1b[35m'

TASKS_FILE = Path.home() / '.config/amallo/fleet_tasks.json'
TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)

STATUS_ICON = {
    'queued':   f'{YELLOW}◌{R}',
    'running':  f'{ORANGE}◉{R}',
    'done':     f'{GREEN}✓{R}',
    'failed':   f'{RED}✗{R}',
    'blocked':  f'{DIM}⊘{R}',
}

def load_tasks():
    try: return json.loads(TASKS_FILE.read_text())
    except: return []

def save_tasks(tasks):
    TASKS_FILE.write_text(json.dumps(tasks, indent=2))

def wand(msg):
    """orange tarmac wand speaks"""
    print(f'{ORANGE}{BOLD}[marshal]{R} {msg}', flush=True)

def agent_log(agent, msg, color=CYAN):
    print(f'  {color}[{agent}]{R} {msg}', flush=True)

# ── built-in agents ────────────────────────────────────────────────────────────
def agent_bash(task):
    """runs a bash command, captures output"""
    cmd = task.get('cmd', '')
    if not cmd:
        return False, 'no cmd defined'
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    out = (r.stdout + r.stderr).strip()
    agent_log(task['agent'], out[:300] if out else '(no output)')
    return r.returncode == 0, out

def agent_file(task):
    """writes content to output_path"""
    path = task.get('output_path')
    content = task.get('content', '')
    if not path:
        return False, 'no output_path'
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content)
    agent_log(task['agent'], f'wrote {len(content)} bytes → {path}')
    return True, f'written: {path}'

def agent_ollama(task):
    """asks ollama a question and saves the answer"""
    import requests
    model = task.get('model', 'glm4:latest')
    prompt = task.get('prompt', task.get('cmd', ''))
    try:
        r = requests.post('http://localhost:11434/api/generate',
            json={'model': model, 'prompt': prompt, 'stream': False}, timeout=60)
        answer = r.json().get('response', '').strip()
        agent_log(task['agent'], answer[:200])
        out_path = task.get('output_path')
        if out_path:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_text(answer)
        return True, answer
    except Exception as e:
        return False, str(e)

AGENTS = {
    'bash':    agent_bash,
    'file':    agent_file,
    'ollama':  agent_ollama,
}

# ── marshal core ───────────────────────────────────────────────────────────────
def run_task(task, tasks, idx):
    """run one task, integrate result immediately"""
    agent_fn_name = task.get('agent', 'bash')
    # map named agents to bash runner
    agent_fn = AGENTS.get(agent_fn_name, agent_bash)

    wand(f'{ORANGE}◉ landing:{R} {BOLD}{task["title"]}{R}  [{task["id"]}]')
    tasks[idx]['status'] = 'running'
    tasks[idx]['started_at'] = datetime.now().isoformat()
    save_tasks(tasks)

    try:
        success, result = agent_fn(task)
    except Exception as e:
        success, result = False, str(e)

    tasks[idx]['status'] = 'done' if success else 'failed'
    tasks[idx]['result'] = result[:500] if result else ''
    tasks[idx]['completed_at'] = datetime.now().isoformat()
    save_tasks(tasks)

    icon = STATUS_ICON['done'] if success else STATUS_ICON['failed']
    wand(f'{icon} {BOLD}{task["title"]}{R} {"integrated ✓" if success else "FAILED"}')
    return success

def run_all():
    tasks = load_tasks()
    if not tasks:
        wand('no tasks. add one: marshal.py add')
        return

    queued = [t for t in tasks if t['status'] == 'queued']
    wand(f'{BOLD}{len(queued)} tasks queued{R}, {len([t for t in tasks if t["status"]=="done"])} done\n')

    for task in queued:
        idx = next(i for i,t in enumerate(tasks) if t['id'] == task['id'])
        # check deps
        deps = task.get('deps', [])
        for dep in deps:
            dep_task = next((t for t in tasks if t['id'] == dep), None)
            if dep_task and dep_task['status'] != 'done':
                wand(f'{DIM}⊘ skipping {task["id"]} — waiting on {dep}{R}')
                continue
        run_task(task, tasks, idx)
        time.sleep(0.5)  # brief pause between landings

    # final status
    tasks = load_tasks()
    done  = len([t for t in tasks if t['status']=='done'])
    total = len(tasks)
    wand(f'\n{BOLD}fleet: {done}/{total} complete{R}')

def show_status():
    tasks = load_tasks()
    if not tasks:
        print('no tasks yet')
        return
    print(f'\n{BOLD}{ORANGE}◉ marshal fleet status{R}\n')
    print(f'  {"id":20s} {"status":10s} {"title"}')
    print(f'  {"─"*20} {"─"*10} {"─"*30}')
    for t in tasks:
        icon = STATUS_ICON.get(t['status'], '?')
        result_preview = f'  {DIM}{t.get("result","")[:50]}{R}' if t.get('result') else ''
        print(f'  {t["id"]:20s} {icon} {t["status"]:8s} {t["title"]}{result_preview}')
    print()

def add_task():
    tasks = load_tasks()
    print(f'\n{ORANGE}add new task{R}')
    tid   = input('  id (short, no spaces): ').strip()
    title = input('  title: ').strip()
    agent = input('  agent [bash/file/ollama] (default: bash): ').strip() or 'bash'
    cmd   = input('  cmd/prompt: ').strip()
    out   = input('  output_path (optional): ').strip()
    deps  = input('  depends on (comma-sep ids, optional): ').strip()

    task = {
        'id': tid, 'title': title, 'agent': agent,
        'cmd': cmd, 'status': 'queued',
        'output_path': out or None,
        'deps': [d.strip() for d in deps.split(',') if d.strip()],
        'created_at': datetime.now().isoformat()
    }
    tasks.append(task)
    save_tasks(tasks)
    wand(f'task {BOLD}{tid}{R} queued ✓')

def do_one(task_id):
    tasks = load_tasks()
    idx = next((i for i,t in enumerate(tasks) if t['id'] == task_id), None)
    if idx is None:
        wand(f'task not found: {task_id}')
        return
    run_task(tasks[idx], tasks, idx)

# ── entry ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'run'

    print(f'\n{ORANGE}{BOLD}◉ marshal{R} — orange tarmac wand\n')

    if cmd == 'status':   show_status()
    elif cmd == 'add':    add_task()
    elif cmd == 'do':     do_one(sys.argv[2] if len(sys.argv) > 2 else '')
    else:                 run_all()
