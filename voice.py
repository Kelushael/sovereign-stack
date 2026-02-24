#!/usr/bin/env python3
"""
axis voice relay — press ENTER to start recording, ENTER again to stop + transcribe
pipes transcribed text straight to axis stdin (or prints it for piping)
usage:
  python3 voice.py           # interactive STT loop
  python3 voice.py | axis    # pipe directly into axis
"""
import sys, os, tempfile, numpy as np, sounddevice as sd, soundfile as sf
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "tiny.en"  # tiny.en = 39MB, fast, English. change to "base.en" for better accuracy

def load_model():
    print("⚡ loading whisper tiny.en (39MB, runs fast)...", file=sys.stderr)
    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

def record_until_enter():
    print("\n🎙  RECORDING — press ENTER to stop", file=sys.stderr)
    frames = []
    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32', callback=callback)
    stream.start()
    input()  # block until enter
    stream.stop()
    stream.close()
    if not frames:
        return None
    audio = np.concatenate(frames, axis=0).flatten()
    return audio

def transcribe(model, audio):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio, SAMPLE_RATE)
        fname = f.name
    segments, _ = model.transcribe(fname, beam_size=1, language="en", vad_filter=True)
    os.unlink(fname)
    text = " ".join(s.text.strip() for s in segments).strip()
    return text

def main():
    model = load_model()
    print("✅ voice ready — ENTER to record, ENTER again to stop\n", file=sys.stderr)
    while True:
        try:
            input("[ press ENTER to speak ]")
        except (EOFError, KeyboardInterrupt):
            print("\n👋 bye", file=sys.stderr)
            break
        audio = record_until_enter()
        if audio is None or len(audio) < SAMPLE_RATE * 0.3:
            print("(too short, try again)", file=sys.stderr)
            continue
        print("🔄 transcribing...", file=sys.stderr)
        text = transcribe(model, audio)
        if text:
            print(f"📝 {text}", file=sys.stderr)
            print(text, flush=True)  # this is what gets piped to axis
        else:
            print("(nothing detected)", file=sys.stderr)

if __name__ == "__main__":
    main()
