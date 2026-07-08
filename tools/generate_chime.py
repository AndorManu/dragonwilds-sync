"""Synthesize the ember chime — a soft, low two-note swell. Pure stdlib.

Run once:  .venv\\Scripts\\python.exe tools\\generate_chime.py
"""

import math
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "assets" / "chime.wav"
RATE = 44100
DURATION = 0.9


def tone(t, freq, amp):
    # a warm tone: fundamental + a whisper of the octave, slight detune shimmer
    return amp * (math.sin(2 * math.pi * freq * t)
                  + 0.35 * math.sin(2 * math.pi * freq * 2.003 * t)
                  + 0.15 * math.sin(2 * math.pi * freq * 0.5 * t))


def envelope(t, start, length):
    if t < start:
        return 0.0
    x = (t - start) / length
    if x >= 1.0:
        return 0.0
    attack = min(1.0, x * 14)
    decay = math.exp(-3.2 * x)
    return attack * decay


def main():
    frames = []
    n = int(RATE * DURATION)
    for i in range(n):
        t = i / RATE
        # D3 then A3 — a quiet, resolved fifth
        sample = (tone(t, 146.83, 0.30) * envelope(t, 0.00, 0.80)
                  + tone(t, 220.00, 0.24) * envelope(t, 0.12, 0.75))
        sample = max(-1.0, min(1.0, sample))
        frames.append(struct.pack("<h", int(sample * 32000)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(frames))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
