"""
"Will they line up again?" — a pendulum wave. 14-22 pendulums hang from one bar (seen almost
end-on, so it looks like a short vertical rod). Pendulum k makes exactly n0 + k full swings in
T seconds (the lengths follow the real pendulum law, L ~ 1/f²), so they drift into snakes,
spirals and split groups — and at exactly T seconds they ALL line up again. The video starts
and ends lined up, so the Short loops perfectly.

Sound: every pendulum plays its own note (pentatonic, short = high) each time it turns at the
right side, so the music is chaos in the middle and a big chord when they line up.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import FPS
from . import mathfx as M

PIVOT = (540, 690)
INTRO = 0.6
AFTER = 2.2
PENTA = [0, 2, 4, 7, 9]


@dataclass
class Config:
    seed: int
    n: int
    n0: int
    T: float
    amp: float
    elev: float
    yaw: float
    spacing: float
    L_max: float
    hue0: float
    hue_dir: int
    question: str


QUESTIONS = ["Will they line up again?", "Will they ever line up again?", "Wait for them to line up…"]


def make_config(seed):
    rng = random.Random(seed * 4241 + 3)
    n = rng.choice([14, 16, 18, 20, 22])
    T = rng.choice([22.0, 24.0, 25.0, 26.0])
    n0 = rng.choice([12, 14, 15, 16])
    return Config(seed, n, n0, T, rng.uniform(0.33, 0.38), rng.uniform(0.74, 0.86), rng.uniform(-0.2, 0.2),
                  rng.uniform(17, 21), rng.uniform(1300, 1380), rng.random(), rng.choice([-1, 1]),
                  rng.choice(QUESTIONS))


def freqs(cfg):
    return (cfg.n0 + np.arange(cfg.n)) / cfg.T          # index 0 = slowest = longest


def lengths(cfg):
    f = freqs(cfg)
    return cfg.L_max * (f[0] / f) ** 2


def simulate(cfg, record=False):
    f = freqs(cfg)
    total = INTRO + cfg.T + AFTER
    # right-side turning points: theta = +amp at t = m / f
    turns = []
    for k in range(cfg.n):
        m = 0
        while True:
            t = INTRO + m / f[k]
            if t > total - 0.3:
                break
            turns.append((t, k))
            m += 1
    res = dict(turns=turns, total=total, t_line=INTRO + cfg.T)
    res["frames"] = [dict(t=i / FPS) for i in range(int(total * FPS))] if record else []
    return res


def is_good(res):
    return True


def _angles(cfg, t):
    tt = max(0.0, t - INTRO)
    return cfg.amp * np.cos(2 * math.pi * freqs(cfg) * tt)


def _project(cfg, x, y, z):
    """x = sideways swing, y = down, z = along the bar (depth). Camera looks down the bar."""
    cy, sy = math.cos(cfg.yaw), math.sin(cfg.yaw)
    x2 = x * cy + z * sy
    z2 = -x * sy + z * cy
    ce, se = math.cos(cfg.elev), math.sin(cfg.elev)
    y2 = y * ce + z2 * se
    depth = -y * se + z2 * ce
    return PIVOT[0] + x2, PIVOT[1] + y2 * 0.98, depth


def _positions(cfg, t):
    L = lengths(cfg)
    th = _angles(cfg, t)
    # longest pendulum hangs from the far end of the bar, shortest from the near end
    z = (np.arange(cfg.n)[::-1] - (cfg.n - 1) / 2) * cfg.spacing
    x = L * np.sin(th)
    y = L * np.cos(th)
    return _project(cfg, x, y, z), _project(cfg, np.zeros(cfg.n), np.zeros(cfg.n), z)


def _color(cfg, k):
    return M.rainbow(cfg.hue0 + cfg.hue_dir * 0.75 * k / max(1, cfg.n - 1), 0.62, 1.0)


def draw(ctx, fr, cfg):
    import cairo
    t = fr["t"]
    M.background(ctx)
    (bx, by, bd), (px, py, _pd) = _positions(cfg, t)
    order = np.argsort(bd)[::-1]                        # far first

    # the bar (seen end-on) and its glow
    top, bot = int(np.argmin(py)), int(np.argmax(py))
    M.glow_stroke(ctx, lambda c: (c.move_to(px[top], py[top] - 30), c.line_to(px[bot], py[bot] + 30)),
                  M.WALL, 6)

    # motion trails: the last 0.3 s of each ball as a tapered ribbon
    steps = 26
    hist = [_positions(cfg, t - i * 0.012)[0] for i in range(steps)]
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    for k in order:
        col = _color(cfg, k)
        for i in range(steps - 1):
            a = (1 - i / steps) ** 1.6
            ctx.set_line_width(20 * a + 3)
            ctx.set_source_rgba(*col, 0.45 * a)
            ctx.move_to(hist[i][0][k], hist[i][1][k])
            ctx.line_to(hist[i + 1][0][k], hist[i + 1][1][k])
            ctx.stroke()
    # strings
    ctx.set_line_width(1.4)
    for k in order:
        ctx.set_source_rgba(0.75, 0.9, 1.0, 0.28)
        ctx.move_to(px[k], py[k])
        ctx.line_to(bx[k], by[k])
        ctx.stroke()
    # balls
    prev = hist[2]
    for k in order:
        M.comet(ctx, float(bx[k]), float(by[k]), float(bx[k] - prev[0][k]), float(by[k] - prev[1][k]),
                _color(cfg, k), 12, 0)

    M.question(ctx, t, cfg.question, y=330)
    t_line = INTRO + cfg.T
    if t >= t_line - 0.05:
        a = min(1.0, (t - t_line + 0.05) / 0.3)
        M.answer(ctx, f"YES! All {cfg.n} line up at {cfg.T:.0f} seconds", y=425, size=50, alpha=a)
        # flash on the line-up
        if t - t_line < 0.6:
            g = 1 - (t - t_line) / 0.6
            ctx.set_source_rgba(1, 1, 1, 0.12 * g)
            ctx.paint()
    else:
        M.counter(ctx, "time: ", f"{max(0.0, t - INTRO):04.1f} s", y=425)


AUDIO_MIN_GAP = 0.0


def audio_events(res, cfg):
    base = 261.63 * 2 ** (-12 / 12)            # C3
    out = []
    for t, k in res["turns"]:
        step = cfg.n - 1 - k                    # shortest pendulum = highest note
        semi = 12 * (step // 5) + PENTA[step % 5]
        out.append((t, base * 2 ** (semi / 12), "tick"))
    out.append((res["t_line"], 523.25, "chime"))
    return out


def metadata_facts(res, cfg):
    return dict(template="pendulum", n_balls=cfg.n, T=cfg.T, colors=[], melody="")
