"""
"Will this pattern ever close?" A ball bounces around inside a circle; every bounce moves it
the same angle further round the wall (a fixed fraction of a full turn). Every path is drawn,
so a star pattern grows. If the angle is an irrational fraction of a turn (1/φ², 1/π, 1/√2…)
the ball NEVER lands on its start point again and the pattern never closes. Twist (some
seeds): the angle is 55/144 of a turn — it looks exactly like the golden angle, but it DOES
close after exactly 144 bounces.

The ball speeds up as it goes, so the pattern fills in. Bounces play a public-domain tune.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import FPS, note_freq
from . import mathfx as M, melodies

CX, CY, R = 540, 1090, 430
INTRO = 0.6
END_HOLD = 2.8

PHI = (1 + 5 ** 0.5) / 2
ANGLES = {    # name -> (turn fraction, numerator label, denominator label, closes after)
    "phi2": (1 / PHI ** 2, "1", "φ²", None),
    "phi1": (1 / PHI, "1", "φ", None),
    "pi": (1 / math.pi, "1", "π", None),
    "sqrt2": (1 / 2 ** 0.5, "1", "√2", None),
    "e": (1 / math.e, "1", "e", None),
    "f144": (55 / 144, "55", "144", 144),
    "f89": (34 / 89, "34", "89", 89),
    "f233": (89 / 233, "89", "233", 233),
}
QUESTIONS = ["Will this pattern ever close?", "Will the ball ever get back to the start?",
             "Will it EVER repeat itself?"]
PALETTES = [
    [(0.25, 0.8, 1.0), (0.35, 0.5, 1.0), (0.62, 0.42, 1.0), (1.0, 0.45, 0.8), (1.0, 0.75, 0.6), (1, 1, 1)],
    [(0.3, 1.0, 0.7), (0.2, 0.75, 1.0), (0.45, 0.45, 1.0), (0.85, 0.4, 1.0), (1.0, 0.6, 0.85), (1, 1, 1)],
    [(1.0, 0.75, 0.3), (1.0, 0.45, 0.4), (0.9, 0.35, 0.75), (0.55, 0.4, 1.0), (0.4, 0.75, 1.0), (1, 1, 1)],
]


@dataclass
class Config:
    seed: int
    angle: str
    frac: float
    num: str
    den: str
    closes: int
    n_total: int
    d0: float
    q: float
    start: float
    palette: list
    question: str
    melody_name: str
    melody: list


def _solve_q(d0, n, T):
    """chord k lasts d0 * q^k; pick q so that n chords take T seconds."""
    lo, hi = 0.5, 1.0
    for _ in range(80):
        q = (lo + hi) / 2
        s = d0 * (1 - q ** n) / (1 - q)
        lo, hi = (lo, q) if s > T else (q, hi)
    return q


def make_config(seed):
    rng = random.Random(seed * 6151 + 11)
    pool = ["phi2"] * 4 + ["pi", "sqrt2", "e", "phi1", "f144", "f144", "f89", "f233"]
    name = rng.choice(pool)
    frac, num, den, closes = ANGLES[name]
    if closes:
        n_total, T = closes, rng.uniform(21.0, 24.0)
    else:
        n_total, T = rng.choice([380, 460, 540]), rng.uniform(24.0, 26.5)
    d0 = rng.uniform(0.45, 0.55)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, name, frac, num, den, closes, n_total, d0, _solve_q(d0, n_total, T),
                  rng.uniform(0, 2 * math.pi), rng.choice(PALETTES), rng.choice(QUESTIONS),
                  mel, melodies.MELODIES[mel])


def simulate(cfg, record=False):
    k = np.arange(cfg.n_total + 1)
    dur = cfg.d0 * cfg.q ** k[:-1]
    times = INTRO + np.concatenate([[0], np.cumsum(dur)])          # time of bounce k (k=0 = start)
    angs = cfg.start - 2 * math.pi * cfg.frac * k                    # clockwise around the wall
    t_end = float(times[-1])
    res = dict(times=times, angs=angs, t_end=t_end, total=t_end + END_HOLD)
    res["frames"] = [dict(t=i / FPS) for i in range(int(res["total"] * FPS))] if record else []
    return res


def is_good(res):
    return True


def _col(cfg, u):
    p = cfg.palette
    x = min(0.999, max(0.0, u)) * (len(p) - 1)
    i = int(x)
    f = x - i
    return tuple(p[i][c] + (p[i + 1][c] - p[i][c]) * f for c in range(3))


_RES, _LAYER = {}, {}


def prepare(res, cfg):
    _RES[cfg.seed] = res
    _LAYER.pop(cfg.seed, None)


def _u(res, k):
    """0..1 progress of chord k in TIME (so the colour drifts evenly through the video)."""
    T = res["times"]
    return (T[min(k, len(T) - 1)] - T[0]) / (T[-1] - T[0])


def _pt(a):
    return CX + R * math.cos(a), CY + R * math.sin(a)


def _layer(res, cfg, n):
    """All finished chords (0..n-1) drawn once on an offscreen layer."""
    import cairo
    from .common import W, H
    surf, done = _LAYER.get(cfg.seed, (None, 0))
    if surf is None or n < done:
        surf, done = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H), 0
    c = cairo.Context(surf)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    for k in range(done, n):
        u = _u(res, k)
        c.set_line_width(2.6 - 1.4 * u)
        c.set_source_rgba(*_col(cfg, u), 0.85 - 0.45 * u)
        c.move_to(*_pt(res["angs"][k]))
        c.line_to(*_pt(res["angs"][k + 1]))
        c.stroke()
    surf.flush()
    _LAYER[cfg.seed] = (surf, n)
    return surf


def draw(ctx, fr, cfg):
    res = _RES[cfg.seed]
    t = fr["t"]
    times, angs = res["times"], res["angs"]
    M.background(ctx)
    k = int(np.searchsorted(times, t, side="right")) - 1        # last bounce that happened
    k = max(0, min(k, cfg.n_total))
    done = res["t_end"] <= t
    ctx.set_source_surface(_layer(res, cfg, min(k, cfg.n_total)), 0, 0)
    ctx.paint()

    # the ball on its current chord (or resting on the start point at the end)
    if not done and t >= times[0]:
        u = (t - times[k]) / (times[k + 1] - times[k])
        x0, y0 = _pt(angs[k])
        x1, y1 = _pt(angs[k + 1])
        x, y = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        col = _col(cfg, _u(res, k))
        ctx.set_line_width(2.4)
        ctx.set_source_rgba(*col, 0.9)
        ctx.move_to(x0, y0)
        ctx.line_to(x, y)
        ctx.stroke()
        tail = min(70.0, math.hypot(x - x0, y - y0))
        M.comet(ctx, x, y, x1 - x0, y1 - y0, col, 11, tail)
    else:
        x, y = _pt(angs[min(k, cfg.n_total)] if t >= times[0] else angs[0])
        M.comet(ctx, x, y, 0, 0, _col(cfg, 1.0 if done else 0.0), 11, 0)

    # white flashes on the wall where it bounced recently
    j = k
    while j >= 1 and t - times[j] < 0.35:
        a = 1 - (t - times[j]) / 0.35
        bx, by = _pt(angs[j])
        ctx.arc(bx, by, 7 + 6 * a, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.85 * a)
        ctx.fill()
        j -= 1

    # start point marker (pulses when the pattern closes)
    sx, sy = _pt(angs[0])
    pulse = 0.0
    if cfg.closes and done:
        pulse = max(0.0, 1 - (t - res["t_end"]) / 1.2)
    M.marker(ctx, sx, sy, 14, M.GOLD, 0.9, pulse)

    M.glow_stroke(ctx, lambda c: c.arc(CX, CY, R, 0, 2 * math.pi), M.WALL, 9)

    M.question(ctx, t, cfg.question, y=330)
    if done:
        a = min(1.0, (t - res["t_end"]) / 0.3)
        if cfg.closes:
            M.answer(ctx, f"YES! Back to the start after {cfg.closes} bounces", y=430, size=48, alpha=a)
        else:
            M.answer(ctx, "NEVER! It can't — the angle is irrational", y=430, size=46, alpha=a)
        M.counter(ctx, "angle = ", f"{cfg.num}/{cfg.den} turn", y=1650, size=44, alpha=a)
    else:
        M.fraction_label(ctx, "angle = ", cfg.num, cfg.den, " turn", y=445, size=50)
    from .common import text
    text(ctx, f"bounces: {min(k, cfg.n_total):,}", 540, 1640 if not done else 1580, 46, (1, 1, 1), 0.85)


AUDIO_MIN_GAP = 0.09


def audio_events(res, cfg):
    times = list(res["times"][1:])
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(times, cfg.melody, AUDIO_MIN_GAP)]
    used = {round(t, 4) for t, _f, _k in out}
    last = -1.0
    for t in times:
        if round(t, 4) not in used and t - last > 0.02:
            out.append((t, 1500.0, "click"))
            last = t
    out.append((res["t_end"], 523.25, "win" if cfg.closes else "chime"))
    return out


def metadata_facts(res, cfg):
    return dict(template="golden", angle=cfg.angle, angle_label=f"{cfg.num}/{cfg.den}",
                closes=cfg.closes or 0, n_balls=1, colors=[], melody=cfg.melody_name)
