"""
ASMR sound for the 3D videos, made from the physics: every impact the renderer recorded
(time, kind, strength) becomes a short synthesized knock. Many impacts in the same instant are
merged (louder, not a wall of noise). A very soft warm pad sits underneath so it is never silent.
"""
import wave

import numpy as np

SR = 44100


def _env(n, decay):
    t = np.arange(n) / SR
    return np.exp(-t * decay) * np.minimum(1.0, t / 0.0015)


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def _bandpass(x, f0, q=4.0):
    """simple resonant filter (biquad band-pass)"""
    w0 = 2 * np.pi * f0 / SR
    alpha = np.sin(w0) / (2 * q)
    b0, b2 = alpha, -alpha
    a0, a1, a2 = 1 + alpha, -2 * np.cos(w0), 1 - alpha
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        y0 = (b0 * x[i] + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1 = x1, x[i]
        y2, y1 = y1, y0
        y[i] = y0
    return y


_CACHE = {}


def _voice(kind, variant):
    """a few pre-made variants of each sound; picked at random so repeats don't sound robotic"""
    key = (kind, variant)
    if key in _CACHE:
        return _CACHE[key]
    rng = np.random.default_rng(variant * 31 + len(kind))
    if kind == "clack":                       # plastic / wooden block
        n = int(SR * 0.09)
        f = rng.uniform(900, 1700)
        x = _bandpass(_noise(n, variant), f, 6) * 3.0 + 0.4 * np.sin(2 * np.pi * f * 0.5 * np.arange(n) / SR)
        x *= _env(n, 55)
    elif kind == "tick":                      # small ball
        n = int(SR * 0.05)
        f = rng.uniform(2200, 3800)
        x = _bandpass(_noise(n, variant + 7), f, 8) * 3.0 * _env(n, 90)
    elif kind == "wood":
        n = int(SR * 0.14)
        f = rng.uniform(380, 620)
        x = (_bandpass(_noise(n, variant + 3), f, 5) * 2.5 + 0.6 * np.sin(2 * np.pi * f * np.arange(n) / SR)) * _env(n, 32)
    elif kind == "thud":                      # heavy ball
        n = int(SR * 0.35)
        f = rng.uniform(70, 110)
        t = np.arange(n) / SR
        x = np.sin(2 * np.pi * f * t * (1 + 0.6 * np.exp(-t * 30))) * _env(n, 13)
        x += 0.5 * _bandpass(_noise(n, variant + 11), 300, 1.5) * _env(n, 30)
    elif kind == "squish":                    # jelly
        n = int(SR * 0.25)
        t = np.arange(n) / SR
        f = rng.uniform(140, 220)
        x = np.sin(2 * np.pi * f * t * (1 - 0.35 * t / 0.25)) * np.sin(np.pi * np.minimum(1, t / 0.25)) ** 2
        x += 0.25 * _bandpass(_noise(n, variant + 5), 600, 2) * _env(n, 18)
    else:                                     # swish (cloth)
        n = int(SR * 0.4)
        t = np.arange(n) / SR
        x = _bandpass(_noise(n, variant + 13), 900, 1.2) * np.sin(np.pi * t / 0.4) ** 2 * 0.8
    x = x / (np.abs(x).max() + 1e-9)
    _CACHE[key] = x
    return x


def pad(seconds, seed=0, vol=0.035):
    """soft warm chord, slowly breathing"""
    n = int(SR * seconds)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in (130.81, 196.0, 246.94, 329.63):            # C3 G3 B3 E4: Cmaj7, calm
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (0.05 + 0.01 * f / 100) * t + f)
        out += np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.2 * t)) * lfo
    fade = np.minimum(1.0, np.minimum(t / 2.0, (seconds - t) / 2.0))
    return out / 4 * vol * np.clip(fade, 0, 1)


def track(events, seconds, seed=0, window=0.012, max_per_window=6):
    """events: [(t, kind, strength 0..1)] -> mono float array"""
    rng = np.random.default_rng(seed)
    buf = np.zeros(int(SR * (seconds + 1)))
    bins = {}
    for t, kind, s in events:
        if t >= seconds:
            continue
        bins.setdefault((int(t / window), kind), []).append(s)
    for (b, kind), ss in bins.items():
        ss = sorted(ss, reverse=True)[:max_per_window]
        for j, s in enumerate(ss):
            x = _voice(kind, int(rng.integers(6)))
            amp = (0.15 + 0.85 * s) * (0.55 if j else 1.0) * {"thud": 1.0, "clack": 0.55, "tick": 0.35,
                                                                   "wood": 0.6, "squish": 0.8, "swish": 0.5}[kind]
            i = int((b * window + rng.uniform(0, window)) * SR)
            seg = x[: len(buf) - i] * amp
            buf[i:i + len(seg)] += seg
    return buf[: int(SR * seconds)]


def write(path, mono):
    peak = np.abs(mono).max()
    if peak > 0.95:
        mono = np.tanh(mono / peak * 1.5) * 0.9           # soft limiter
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mono, -1, 1) * 32767).astype(np.int16).tobytes())
