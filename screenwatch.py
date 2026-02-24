#!/usr/bin/env python3
"""
screenwatch.py — give axis eyes
captures screen or terminal state, sends to AI, AI responds to what it SEES
usage:
  python3 screenwatch.py          # watch terminal output
  python3 screenwatch.py screen   # screenshot → AI describes + acts
  python3 screenwatch.py browser  # scrape active browser tab
"""
import sys, os, subprocess, base64, json, urllib.request, time
from pathlib import Path

AMALLO = os.environ.get('AMALLO_URL', 'http://187.77.208.28:8200')
KEY    = 'marcus'

def ask_ai_vision(prompt, image_b64=None, text=None):
    msg = {'role': 'user', 'content': prompt}
    if text:
        msg['content'] = f"{prompt}\n\nWHAT I SEE:\n```\n{text[:3000]}\n```"
    data = json.dumps({'model': 'glm4', 'messages': [
        {'role': 'system', 'content': 'You are axis — a sovereign AI with eyes. You can see the screen/terminal. Be direct. Say what you see, what is wrong, what to do next. No questions.'},
        msg
    ], 'stream': False}).encode()
    req = urllib.request.Request(f'{AMALLO}/v1/chat/completions',
        data=data, headers={'Content-Type':'application/json','Authorization':f'Bearer {KEY}'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())['choices'][0]['message']['content']
    except Exception as e:
        return f'[axis eyes offline: {e}]'

def watch_terminal():
    """pipe terminal output to AI in real time"""
    print('\033[1m◉ screenwatch — terminal mode\033[0m')
    print('\033[2mrun any command, axis watches the output\033[0m\n')
    while True:
        try:
            cmd = input('\033[33m$ \033[0m').strip()
            if not cmd or cmd == 'exit': break
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output = (result.stdout + result.stderr).strip()
            if output:
                print('\033[2m' + output[:1000] + '\033[0m')
                if result.returncode != 0 or len(output) > 100:
                    print('\033[35m[axis sees this]\033[0m ', end='', flush=True)
                    reply = ask_ai_vision(f'I just ran: {cmd}\nExit code: {result.returncode}\nTell me what this means and what to do.', text=output)
                    print(reply)
            print()
        except (KeyboardInterrupt, EOFError): break

def screenshot():
    """take screenshot, describe it"""
    try:
        import PIL.ImageGrab as ig
        img = ig.grab()
        import io; buf = io.BytesIO()
        img.save(buf, 'PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        print('screenshot captured, asking axis...')
        reply = ask_ai_vision('Describe exactly what you see on this screen. What is the user doing? What problems do you see? What should happen next?')
        print(reply)
    except ImportError:
        # fallback: xwd/scrot
        r = subprocess.run(['scrot', '-', '-z'], capture_output=True)
        if r.returncode == 0:
            print('screenshot via scrot, analyzing...')
        else:
            print('no screenshot tool — use terminal mode')
            watch_terminal()

def watch_browser():
    """scrape current page via CDP"""
    r = subprocess.run(['curl','-s','http://localhost:9222/json'], capture_output=True, text=True)
    if r.returncode != 0:
        print('no Chrome DevTools Protocol found — launch browser with --remote-debugging-port=9222')
        return
    tabs = json.loads(r.stdout)
    if not tabs: return
    tab = tabs[0]
    print(f'watching: {tab.get("url")}')
    r2 = subprocess.run(['curl','-s',f'http://localhost:9222/json/runtime/evaluate'], capture_output=True, text=True)
    reply = ask_ai_vision(f'I am looking at browser tab: {tab.get("url")}\nTitle: {tab.get("title")}\nTell me what is happening and what to do.')
    print(reply)

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'terminal'
    if mode == 'screen':   screenshot()
    elif mode == 'browser': watch_browser()
    else:                   watch_terminal()
