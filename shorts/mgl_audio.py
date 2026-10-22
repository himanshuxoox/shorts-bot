"""Sound for the ManimGL formats.

A scene records events [(time, freq, kind)] while it plays. This turns them into one WAV:
  * normal kinds (tick, pluck, bell, chime, win, shatter …) through common.build_audio
  * "clack": short wooden knocks (metronomes) — mixed separately so hundreds stay crisp
  * "tone": a sustained sine from that moment until the next tone event (freq 0 = silence)
  * a very quiet original pad (Am-F-C-G) so the Short never feels empty
All sound is synthesized here: nothing copyrighted.
"""
import json, os, wave

import numpy as np

from .common import SR, build_audio


def make_wav(events_json, wav_path):
    d = json.load(open(events_json))
    total = float(d["total"]) + 0.6
    events = [tuple(e) for e in d["events"]]
    normal = [(t, f, k) for t, f, k in events if k not in ("clack", "tone")]
    clacks = sorted(t for t, f, k in events if k == "clack")
    tones = sorted((t, f) for t, f, k in events if k == "tone")

    tmp = wav_path + ".base.wav"
    build_audio(normal or [(0.0, 440.0, "tick")], total, tmp)
    with wave.open(tmp) as w:
        base = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32767
    os.remove(tmp)
    n = len(base)
    t = np.arange(n) / SR

    # clacks
    clk = np.zeros(n)
    rng = np.random.default_rng(1)
    L = int(0.035 * SR)
    tt = np.arange(L) / SR
    last = -1.0
    for tc in clacks:
        if tc - last < 0.0025:
            continue
        last = tc
        i = int(tc * SR)
        if i >= n:
            break
        s = 0.5 * np.sin(2 * np.pi * 1850 * tt) * np.exp(-tt * 160) + 0.35 * rng.standard_normal(L) * np.exp(-tt * 260)
        clk[i:i + L] += s[: n - i]
    if np.abs(clk).max() > 0:
        clk = clk / max(1.0, np.abs(clk).max()) * 0.8

    # sustained tones
    tone = np.zeros(n)
    for (ta, fa), nxt in zip(tones, tones[1:] + [(total, 0.0)]):
        if fa <= 0:
            continue
        a, b = int(ta * SR), min(n, int(nxt[0] * SR))
        x = t[a:b] - ta
        env = np.minimum(1, x / 0.05) * np.minimum(1, (nxt[0] - ta - x) / 0.08).clip(0)
        tone[a:b] += env * (0.16 * np.sin(2 * np.pi * fa * x) + 0.05 * np.sin(2 * np.pi * 2 * fa * x))

    # quiet pad
    pad = np.zeros(n)
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    seg = 4.0
    for ci in range(int(total / seg) + 1):
        a, b = int(ci * seg * SR), int(min(n, (ci + 1) * seg * SR + 0.5 * SR))
        if a >= n:
            break
        x = t[a:b] - ci * seg
        env = np.minimum(1, x / 0.8) * np.minimum(1, (seg + 0.5 - x) / 0.8).clip(0)
        for fq in chords[ci % 4]:
            pad[a:b] += np.sin(2 * np.pi * fq * x) * env * 0.05 + np.sin(2 * np.pi * fq * 2.003 * x) * env * 0.012
    if tones:
        pad *= 0.4
    fade = np.minimum(1, t / 1.0) * np.minimum(1, (total - t) / 1.2).clip(0)

    mix = base * 0.85 + clk * 0.75 + pad * fade + tone
    mix = mix / max(1e-9, np.abs(mix).max()) * 0.9
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    return d.get("meta", {}), total
