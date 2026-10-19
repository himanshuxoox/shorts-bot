"""
"Why doesn't this orbit close?" A planet orbits a star, but gravity here is a tiny bit stronger
close to the star than Newton's 1/r² (an extra 1/r³ pull). So every lap the ellipse turns a
little further round, and the path draws a ROSETTE flower. (Mercury's real orbit turns the same
way, only much slower — that's one of the clues for Einstein's general relativity.)

The orbit is integrated numerically (RK4). Time speeds up as the video goes, the counter shows
"years". Every closest pass (perihelion) rings the next note of a public-domain tune.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import FPS, note_freq, text
from . import mathfx as M, melodies

STAR = (540, 1090)
R_MAX = 440.0
INTRO = 0.5
END_HOLD = 3.0
VIDEO_T = 26.0

QUESTIONS = ["Why doesn't this orbit close?", "What is a rosette orbit?",
             "What if gravity was a bit stronger up close?"]
ANSWERS = ["A rosette! Mercury's orbit does this too", "It turns a little every lap — a rosette!",
           "Mercury's orbit turns like this too (slowly)"]


@dataclass
class Config:
    seed: int
    ecc: float
    laps: int
    beta: float
    tilt: float
    years_per_lap: float
    hue0: float
    hue_span: float
    question: str
    answer: str
    melody_name: str
    melody: list


def make_config(seed):
    rng = random.Random(seed * 3331 + 17)
    laps = rng.choice([12, 14, 16, 18])
    # turn per lap so that `laps` laps make (almost) one full extra turn
    prec = 2 * math.pi / laps * rng.uniform(0.92, 1.08)
    beta = 1 / (1 + prec / (2 * math.pi))
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(0.45, 0.62), laps, beta, rng.uniform(0, 2 * math.pi),
                  rng.choice([88, 225, 365, 687, 1200]) * rng.uniform(0.9, 1.1), rng.random(),
                  rng.uniform(0.55, 0.85), rng.choice(QUESTIONS), rng.choice(ANSWERS), mel,
                  melodies.MELODIES[mel])


def _orbit(cfg):
    """Exact rosette: r(θ) = p / (1 + e·cos(βθ)) is the orbit for a 1/r² + 1/r³ pull.
    Time comes from the angular momentum law dθ/dt = h / r². -> (samples (s, x, y), perihelion times, lap period)"""
    e, beta = cfg.ecc, cfg.beta
    th_end = cfg.laps * 2 * math.pi / beta
    th = np.linspace(0, th_end, int(cfg.laps * 2600))
    r = 1.0 / (1 + e * np.cos(beta * th))
    dth = np.diff(th)
    rm = (r[1:] + r[:-1]) / 2
    s = np.concatenate([[0], np.cumsum(dth * rm * rm)])           # h = 1
    arr = np.stack([s, r * np.cos(th), r * np.sin(th)], 1)
    peri_th = [m * 2 * math.pi / beta for m in range(1, cfg.laps + 1)]
    peri = list(np.interp(peri_th, th, s))
    return arr, peri, s[-1] / cfg.laps


def _warp(tau, total_s):
    """video seconds -> simulation time; slow start, fast finish."""
    u = min(1.0, max(0.0, tau / VIDEO_T))
    return total_s * (0.35 * u + 0.65 * u ** 2.4)


def simulate(cfg, record=False):
    arr, peri, period = _orbit(cfg)
    total_s = arr[-1, 0]
    r = np.hypot(arr[:, 1], arr[:, 2]).max()
    res = dict(arr=arr, period=period, scale=R_MAX / r, total_s=total_s,
               t_end=INTRO + VIDEO_T, total=INTRO + VIDEO_T + END_HOLD)
    # perihelion passes -> video times (invert the warp numerically)
    taus = np.linspace(0, VIDEO_T, 4000)
    ss = np.array([_warp(t, total_s) for t in taus])
    res["peri_t"] = [INTRO + float(np.interp(p, ss, taus)) for p in peri]
    res["frames"] = [dict(t=i / FPS) for i in range(int(res["total"] * FPS))] if record else []
    return res


def is_good(res):
    return True


_RES, _LAYER = {}, {}


def prepare(res, cfg):
    _RES[cfg.seed] = res
    _LAYER.pop(cfg.seed, None)


def _xy(res, cfg, i):
    a = res["arr"]
    c, s = math.cos(cfg.tilt), math.sin(cfg.tilt)
    x, y = a[i, 1] * res["scale"], a[i, 2] * res["scale"]
    return STAR[0] + x * c - y * s, STAR[1] + x * s + y * c


def _col(cfg, res, i):
    u = i / len(res["arr"])
    return M.rainbow(cfg.hue0 + cfg.hue_span * u, 0.55, 1.0)


def _layer(res, cfg, n):
    import cairo
    from .common import W, H
    surf, done = _LAYER.get(cfg.seed, (None, 0))
    if surf is None or n < done:
        surf, done = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H), 0
    c = cairo.Context(surf)
    c.set_line_width(2.0)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    step = 6
    i = max(0, done - (done % step))
    while i + step <= n:
        c.set_source_rgba(*_col(cfg, res, i), 0.55)
        c.move_to(*_xy(res, cfg, i))
        for j in range(i + 1, i + step + 1):
            c.line_to(*_xy(res, cfg, j))
        c.stroke()
        i += step
    surf.flush()
    _LAYER[cfg.seed] = (surf, i)
    return surf, i


def draw(ctx, fr, cfg):
    import cairo
    res = _RES[cfg.seed]
    t = fr["t"]
    M.background(ctx)
    s = _warp(t - INTRO, res["total_s"])
    arr = res["arr"]
    i = int(np.searchsorted(arr[:, 0], s))
    i = min(max(i, 1), len(arr) - 1)

    surf, upto = _layer(res, cfg, i)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint()
    # the newest bit of path (bright)
    ctx.set_line_width(3.0)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(*_xy(res, cfg, max(0, upto - 1)))
    for j in range(max(0, upto - 1), i + 1):
        ctx.line_to(*_xy(res, cfg, j))
    ctx.set_source_rgba(*_col(cfg, res, i), 0.9)
    ctx.stroke()

    # star
    g = cairo.RadialGradient(*STAR, 4, *STAR, 120)
    g.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.9)
    g.add_color_stop_rgba(0.25, 1, 0.75, 0.25, 0.35)
    g.add_color_stop_rgba(1, 1, 0.6, 0.1, 0)
    ctx.set_source(g)
    ctx.arc(*STAR, 120, 0, 2 * math.pi)
    ctx.fill()
    ctx.arc(*STAR, 26, 0, 2 * math.pi)
    ctx.set_source_rgb(1, 0.93, 0.6)
    ctx.fill()

    # planet
    x, y = _xy(res, cfg, i)
    px, py = _xy(res, cfg, max(0, i - 30))
    M.comet(ctx, x, y, x - px, y - py, _col(cfg, res, i), 12, min(70, math.hypot(x - px, y - py) * 2))

    M.question(ctx, t, cfg.question, y=330)
    years = s / res["period"] * cfg.years_per_lap
    if t >= res["t_end"]:
        a = min(1.0, (t - res["t_end"]) / 0.3)
        M.answer(ctx, cfg.answer, y=425, size=48, alpha=a)
        text(ctx, f"{years:,.0f} years", 540, 1680, 44, (1, 1, 1), 0.8 * a)
    else:
        M.counter(ctx, "years: ", f"{int(years // 100 * 100):,}", y=425)


AUDIO_MIN_GAP = 0.12


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "bell") for t, nm in melodies.track(res["peri_t"], cfg.melody, AUDIO_MIN_GAP)
           if t < res["t_end"]]
    out.append((res["t_end"], 523.25, "chime"))
    return out


def metadata_facts(res, cfg):
    return dict(template="rosette", laps=cfg.laps, n_balls=1, colors=[], melody=cfg.melody_name)
