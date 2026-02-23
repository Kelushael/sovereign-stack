#!/usr/bin/env python3
import subprocess, time, sys

last = ""

def speak(text):
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s: continue
        if s.startswith(('$','>>>','#','```','|','{','}')):continue
        if line.startswith('    '): continue
        lines.append(s)
    clean = ' '.join(lines)
    if len(clean) < 5: return
    # Use human-voice.sh for high-quality speech synthesis
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    human_voice_script = os.path.join(script_dir, 'human-voice.sh')
    subprocess.Popen([human_voice_script, clean])

def clip():
    try:
        return subprocess.run(['xsel','-b'],capture_output=True,text=True,timeout=2).stdout.strip()
    except: return ""

print("[VOICE] live — copy any text to hear it. Ctrl+C stops.")
while True:
    try:
        c = clip()
        if c and c != last:
            last = c
            speak(c)
        time.sleep(0.8)
    except KeyboardInterrupt:
        sys.exit(0)
    except: time.sleep(1)
