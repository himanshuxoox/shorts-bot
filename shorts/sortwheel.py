"""
"Sort wheel": a colour wheel cut into 120 slices, shuffled. A real sorting algorithm (shaker,
insertion, quick, heap, shell or comb sort) swaps them back one pair at a time; every swap plays
a tone whose pitch is the colour's place in the rainbow ("the sound of sorting"). At the end a
check sweep runs round the finished wheel. Counters: swaps and % sorted.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import DT, text
from . import fx, refkit

CX, CY = 540, 1000
R_IN, R_OUT = 120, 445
START = 0.8                    # hold the shuffled wheel for a moment
VERIFY = 1.8
END_HOLD = 2.8
ALGOS = {"shaker": "SHAKER SORT", "insertion": "INSERTION SORT", "quick": "QUICK SORT",
         "heap": "HEAP SORT", "shell": "SHELL SORT", "comb": "COMB SORT"}
CAPS = ["Sorting algorithm | Wait for the perfect GRADIENT",
        "{A} vs a shuffled color wheel | Wait for the perfect GRADIENT",
        "Can {A} fix the RAINBOW? | Turn the SOUND on"]


def _swaps(a, algo):
    a = list(a)
    ops = []

    def sw(i, j):
        a[i], a[j] = a[j], a[i]
        ops.append((i, j))

    n = len(a)
    if algo == "shaker":
        lo, hi, moved = 0, n - 1, True
        while moved:
            moved = False
            for i in range(lo, hi):
                if a[i] > a[i + 1]:
                    sw(i, i + 1); moved = True
            hi -= 1
            for i in range(hi, lo, -1):
                if a[i - 1] > a[i]:
                    sw(i - 1, i); moved = True
            lo += 1
    elif algo == "insertion":
        for i in range(1, n):
            j = i
            while j > 0 and a[j - 1] > a[j]:
                sw(j - 1, j); j -= 1
    elif algo == "quick":
        def qs(lo, hi):
            if lo >= hi:
                return
            p = a[hi]; i = lo
            for j in range(lo, hi):
                if a[j] < p:
                    if i != j:
                        sw(i, j)
                    i += 1
            if i != hi:
                sw(i, hi)
            qs(lo, i - 1); qs(i + 1, hi)
        qs(0, n - 1)
    elif algo == "heap":
        def down(s, end):
            while 2 * s + 1 <= end:
                c = 2 * s + 1
                if c + 1 <= end and a[c] < a[c + 1]:
                    c += 1
                if a[s] < a[c]:
                    sw(s, c); s = c
                else:
                    return
        for s in range(n // 2 - 1, -1, -1):
            down(s, n - 1)
        for end in range(n - 1, 0, -1):
            sw(0, end); down(0, end - 1)
    elif algo == "shell":
        gap = n // 2
        while gap:
            for i in range(gap, n):
                j = i
                while j >= gap and a[j - gap] > a[j]:
                    sw(j - gap, j); j -= gap
            gap //= 2
    elif algo == "comb":
        gap, done = n, False
        while not done:
            gap = max(1, int(gap / 1.3))
            done = gap == 1
            for i in range(n - gap):
                if a[i] > a[i + gap]:
                    sw(i, i + gap); done = False
    assert a == sorted(a)
    return ops


@dataclass
class Config:
    seed: int
    n: int
    algo: str
    t_sort: float
    h0: float
    caption: str


def make_config(seed):
    rng = random.Random(seed * 1931 + 31)
    algo = rng.choice(list(ALGOS))
    return Config(seed, rng.choice([96, 120, 144]), algo, rng.uniform(17, 21), rng.random(),
                  rng.choice(CAPS).replace("{A}", ALGOS[algo]))


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    arr = list(range(cfg.n))
    rng.shuffle(arr)
    ops = _swaps(arr, cfg.algo)
    rate = len(ops) / cfg.t_sort
    t_sorted = START + len(ops) / rate
    t_end = t_sorted + VERIFY
    frames, events = [], []
    a = np.array(arr)
    k = 0
    t = 0.0
    while t < t_end + END_HOLD:
        t += DT
        hi = []
        target = min(len(ops), max(0, int((t - START) * rate)))
        while k < target:
            i, j = ops[k]
            a[i], a[j] = a[j], a[i]
            events.append((START + k / rate, int(a[j])))
            hi = [i, j]
            k += 1
        if record:
            frames.append(dict(t=t, a=a.astype(np.int16), hi=hi, swaps=k,
                               ok=int((a == np.arange(cfg.n)).sum()), t_sorted=t_sorted, t_end=t_end))
    return dict(frames=frames, events=events, swaps=len(ops), t_sorted=t_sorted, t_end=t_end)


def is_good(res):
    return res["swaps"] >= 150


def _hue(cfg, v):
    return cfg.h0 + v / cfg.n


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    n = cfg.n
    step = 2 * math.pi / n
    hi = set(fr["hi"])
    sweep = (t - fr["t_sorted"]) / VERIFY if t >= fr["t_sorted"] else -1
    for i, v in enumerate(fr["a"]):
        a0 = -math.pi / 2 + i * step
        col = fx.hsv(_hue(cfg, int(v)), 0.85, 1.0)
        if i in hi:
            col = (1, 1, 1)
        ctx.new_path()
        ctx.arc(CX, CY, R_OUT, a0, a0 + step + 0.004)
        ctx.arc_negative(CX, CY, R_IN, a0 + step + 0.004, a0)
        ctx.close_path()
        ctx.set_source_rgb(*col)
        ctx.fill()
        if 0 <= sweep and i / n <= sweep:      # the check sweep: a white sheen running round
            ctx.new_path()
            ctx.arc(CX, CY, R_OUT, a0, a0 + step + 0.004)
            ctx.arc_negative(CX, CY, R_IN, a0 + step + 0.004, a0)
            ctx.close_path()
            ctx.set_source_rgba(1, 1, 1, 0.35 * max(0.0, 1 - (sweep - i / n) * 4))
            ctx.fill()
    ctx.new_path()
    ctx.arc(CX, CY, R_OUT + 14, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 1, 1, 0.8)
    ctx.set_line_width(4)
    ctx.stroke()
    text(ctx, ALGOS[cfg.algo], 540, 1520, 56, fx.GOLD, 0.95)
    text(ctx, f"Swaps: {fr['swaps']:,}      Sorted: {100 * fr['ok'] / n:.1f}%", 540, 1590, 42, (1, 1, 1), 0.85)
    text(ctx, "Turn the sound on", 540, 1650, 38, (1, 1, 1), 0.7, bold=False)
    if t >= fr["t_end"]:
        fx.banner(ctx, t, fr["t_end"], "SORTED!", fx.GOLD, f"{fr['swaps']:,} swaps", dim=0.3)


AUDIO_MIN_GAP = 0.0


def audio_events(res, cfg):
    out, last = [], -1.0
    gap = 0.045
    for t, v in res["events"]:
        if t - last >= gap:
            out.append((t, 220.0 * 2 ** (3.0 * v / cfg.n), "tick"))
            last = t
    # check sweep: a quick rising run
    for q in range(24):
        out.append((res["t_sorted"] + VERIFY * q / 24, 220.0 * 2 ** (3.0 * q / 24), "tick"))
    out.append((res["t_end"], 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="sortwheel", colors=[], melody="", n_final=res["swaps"], n_balls=cfg.n,
                algo=ALGOS[cfg.algo].title())
