#!/usr/bin/env python3
"""
ORACLE — Sovereign Siri-like voice assistant
Super+H or `oracle` command → floating overlay → speak → AI responds → speaks back
"""

import os, sys, json, queue, threading, subprocess, requests, re
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

MODEL_PATH = os.path.expanduser("~/.local/share/vosk/vosk-model-small-en-us-0.15")
AMALLO_URL = os.environ.get("AMALLO_URL", "http://187.77.208.28:8200")
SAMPLE_RATE = 16000

CSS = b"""
window {
    background: rgba(10, 10, 20, 0.88);
    border-radius: 20px;
    border: 2px solid rgba(100, 200, 255, 0.5);
}
#orb {
    color: #64c8ff;
    font-size: 48px;
}
#status {
    color: rgba(150, 200, 255, 0.8);
    font-size: 13px;
    font-family: 'JetBrains Mono', monospace;
}
#transcript {
    color: #ffffff;
    font-size: 15px;
    font-weight: bold;
}
#response {
    color: #a0ffa0;
    font-size: 13px;
}
"""

class Oracle(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_default_size(480, 200)

        # transparent window
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # CSS
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # center bottom of screen
        display = screen.get_width()
        self.move(display // 2 - 240, screen.get_height() - 280)

        # layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(24)
        box.set_margin_end(24)
        self.add(box)

        self.orb = Gtk.Label(label="🎙")
        self.orb.set_name("orb")
        box.pack_start(self.orb, False, False, 0)

        self.status_label = Gtk.Label(label="Listening...")
        self.status_label.set_name("status")
        box.pack_start(self.status_label, False, False, 0)

        self.transcript_label = Gtk.Label(label="")
        self.transcript_label.set_name("transcript")
        self.transcript_label.set_line_wrap(True)
        self.transcript_label.set_max_width_chars(50)
        box.pack_start(self.transcript_label, False, False, 0)

        self.response_label = Gtk.Label(label="")
        self.response_label.set_name("response")
        self.response_label.set_line_wrap(True)
        self.response_label.set_max_width_chars(50)
        box.pack_start(self.response_label, False, False, 0)

        self.show_all()

        # voice engine
        self.model = Model(MODEL_PATH)
        self.q = queue.Queue()
        self.listening = True
        self.pulse_timer = None

        # start pulse animation
        self._pulse_orb()

        # start listening thread
        t = threading.Thread(target=self._listen, daemon=True)
        t.start()

    def _pulse_orb(self):
        frames = ["🎙", "🔵", "🎙", "⚪"]
        self._frame = getattr(self, '_frame', 0)
        if self.listening:
            self.orb.set_text(frames[self._frame % len(frames)])
            self._frame += 1
        GLib.timeout_add(300, self._pulse_orb)

    def _set_status(self, text):
        GLib.idle_add(self.status_label.set_text, text)

    def _set_transcript(self, text):
        GLib.idle_add(self.transcript_label.set_text, text)

    def _set_response(self, text):
        GLib.idle_add(self.response_label.set_text, text)

    def _set_orb(self, text):
        GLib.idle_add(self.orb.set_text, text)

    def _listen(self):
        rec = KaldiRecognizer(self.model, SAMPLE_RATE)

        def callback(indata, frames, time, status):
            self.q.put(bytes(indata))

        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000,
                               dtype='int16', channels=1, callback=callback):
            while True:
                data = self.q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if text and len(text) > 2:
                        self._set_transcript(f'"{text}"')
                        self._set_status("Thinking...")
                        self._set_orb("💭")
                        self.listening = False
                        threading.Thread(target=self._ask_ai, args=(text,), daemon=True).start()
                else:
                    partial = json.loads(rec.PartialResult()).get("partial", "")
                    if partial:
                        self._set_transcript(partial + "…")

    def _ask_ai(self, text):
        # check for system commands first
        cmd_result = self._try_system_cmd(text)
        if cmd_result:
            self._speak(cmd_result)
            self._set_response(cmd_result[:120])
            self._set_status("Done. Listening...")
            self._set_orb("🎙")
            self.listening = True
            return

        # send to amallo
        try:
            r = requests.post(f"{AMALLO_URL}/v1/chat/completions",
                json={"model": "default", "messages": [
                    {"role": "system", "content": "You are Oracle, a concise voice assistant. Reply in 1-2 sentences max."},
                    {"role": "user", "content": text}
                ], "stream": False},
                timeout=15)
            reply = r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            reply = f"Can't reach AI: {e}"

        self._speak(reply)
        self._set_response(reply[:120])
        self._set_status("Listening...")
        self._set_orb("🎙")
        self.listening = True

    def _try_system_cmd(self, text):
        t = text.lower()
        if re.search(r'\bopen\s+(firefox|browser|chrome)', t):
            subprocess.Popen(['firefox'])
            return "Opening browser."
        if re.search(r'\bopen\s+terminal', t):
            subprocess.Popen(['wezterm'])
            return "Opening terminal."
        if re.search(r'\bvolume\s+(up|louder)', t):
            subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '+10%'])
            return "Volume up."
        if re.search(r'\bvolume\s+(down|quieter|lower)', t):
            subprocess.run(['pactl', 'set-sink-volume', '@DEFAULT_SINK@', '-10%'])
            return "Volume down."
        if re.search(r'\b(mute|silence)', t):
            subprocess.run(['pactl', 'set-sink-mute', '@DEFAULT_SINK@', 'toggle'])
            return "Muted."
        if re.search(r'\bwhat time', t):
            import datetime
            return datetime.datetime.now().strftime("It's %I:%M %p.")
        if re.search(r'\b(close|quit|exit|stop)', t):
            GLib.idle_add(Gtk.main_quit)
            return "Closing Oracle."
        if re.search(r'\baxis\b', t) and re.search(r'\b(run|open|launch)', t):
            subprocess.Popen(['wezterm', 'start', '--', 'axis'])
            return "Launching Axis."
        return None

    def _speak(self, text):
        clean = re.sub(r'[^\w\s.,!?]', '', text)[:200]
        subprocess.Popen(['spd-say', '-r', '-10', '-p', '10', clean])


def main():
    Gtk.init(sys.argv)
    win = Oracle()
    win.connect("destroy", Gtk.main_quit)
    # ESC to close
    win.connect("key-press-event", lambda w, e: Gtk.main_quit() if e.keyval == Gdk.KEY_Escape else None)
    Gtk.main()

if __name__ == "__main__":
    main()
