"""
"Sunlight + a mirror. Can it light the MATCH?" Rays of sunlight fall straight down on a mirror and
bounce. A match sits at the focus of the parabola. Three tries:
  1. FLAT mirror: every ray goes straight back up — the match stays cold.
  2. ROUND mirror (part of a circle): the rays nearly meet, but spread out ("spherical aberration")
     — the match gets warm… ALMOST.
  3. PARABOLA: every ray goes through ONE point — the match lights.
Exact reflection off each curve (normal from the curve's slope). Heat rises with every ray that hits
the match head and cools a little all the time, so the round mirror levels off below 100%.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import DT, text, note_freq, rounded
from . import fx, melodies, refkit

CX, VY = 540, 1430            # vertex of the mirror (screen)
F = 270.0                     # focal length (px)
HALF = 430.0                  # half width of the mirror
SUN_Y = 560                   # rays start here
V = 1500.0                    # light speed (px/s, slowed down a lot)
HEAD = 15.0                   # match head radius
RATE = 26.0                   # rays per second
STAGES = [("FLAT", 5.0), ("ROUND", 8.0), ("PARABOLA", 9.0)]
MORPH = 0.9                   # seconds to bend the mirror into the next shape
END_HOLD = 3.2
DECAY = 0.55                  # heat lost per second (fraction)
CAPS = ["Sunlight + a MIRROR | Can it light the MATCH?",
        "Can a MIRROR light a match? | Watch the 3rd one",
        "Same sunlight. 3 MIRRORS | Which one lights the MATCH?"]


def shape(kind, X):
    """mirror height above the vertex (math coords, y up) at horizontal offset X"""
    if kind == "FLAT":
        return np.zeros_like(X)
    if kind == "ROUND":
        R0 = 2 * F
        return R0 - np.sqrt(np.maximum(R0 ** 2 - X ** 2, 0))
    return X ** 2 / (4 * F)


@dataclass
class Config:
    seed: int
    inc: float
    sun_col: tuple
    ray_col: tuple
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 3313 + 41)
    mel = rng.choice(melodies.FAMOUS)
    pal = rng.choice([((1.0, 0.85, 0.3), (1.0, 0.8, 0.35)), ((1.0, 0.6, 0.2), (1.0, 0.72, 0.3)),
                      ((1.0, 0.9, 0.5), (0.4, 0.9, 1.0))])
    return Config(seed, 0.0, pal[0], pal[1], mel, melodies.MELODIES[mel], rng.choice(CAPS))


def trace(kind, X):
    """one ray straight down at offset X -> hit height Y, reflected unit direction, and whether
    (and how far along) the reflected ray passes through the match head at (0, F)."""
    Y = float(shape(kind, np.array([X]))[0])
    e = 0.5
    slope = float((shape(kind, np.array([X + e])) - shape(kind, np.array([X - e])))[0] / (2 * e))
    n = np.array([-slope, 1.0]) / math.hypot(slope, 1.0)
    d = np.array([0.0, -1.0])
    r = d - 2 * (d @ n) * n
    p = np.array([X, Y])
    c = np.array([0.0, F])
    s = (c - p) @ r
    if s > 0 and np.linalg.norm(p + s * r - c) < HEAD:
        return Y, r, s - math.sqrt(max(0.0, HEAD ** 2 - float(np.linalg.norm(p + s * r - c)) ** 2))
    return Y, r, None


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    rays = []
    t = 0.6
    stage_t = []
    for kind, dur in STAGES:
        stage_t.append((kind, t, t + dur))
        t += dur + MORPH
    # rays: emitted at random x (never right behind the match head)
    for kind, a, b in stage_t:
        tt = a
        while tt < b - 0.4:
            X = rng.uniform(-HALF + 8, HALF - 8)
            if abs(X) > HEAD + 6:
                Y, r, s = trace(kind, X)
                t_mirror = tt + (VY - SUN_Y - Y) / V
                rays.append(dict(t0=tt, X=X, Y=Y, r=r, s=s, t1=t_mirror,
                                 t_hit=None if s is None else t_mirror + s / V, kind=kind))
            tt += rng.expovariate(RATE)
    # heat: every ray that reaches the head adds cfg.inc %, it cools by DECAY per second
    hits = sorted(r["t_hit"] for r in rays if r["t_hit"] is not None)
    frac = {k: np.mean([r["s"] is not None for r in rays if r["kind"] == k]) for k, _ in STAGES}
    inc = 1.6 * DECAY * 100 / (RATE * max(frac["PARABOLA"], 1e-6))   # parabola would level off at 160 %, the round one ~70 %
    heat, frames, t, k, t_end = 0.0, [], 0.0, 0, None
    peak_round = 0.0
    total = stage_t[-1][2] + END_HOLD
    while t < total:
        t += DT
        while k < len(hits) and hits[k] <= t:
            if t_end is None:
                heat += inc
            k += 1
        heat = max(0.0, heat - heat * DECAY * DT)
        cur = next((kind for kind, a, b in stage_t if a - MORPH <= t < b + 0.01), stage_t[-1][0])
        if cur == "ROUND":
            peak_round = max(peak_round, heat)
        if t_end is None and heat >= 100:
            t_end = t
            heat = 100.0
        if t_end is not None:
            heat = 100.0
            if t > t_end + END_HOLD:
                break
        if record:
            frames.append(dict(t=t, heat=heat, t_end=t_end))
    res = dict(frames=frames, rays=rays, stages=stage_t, hits=hits, t_end=t_end, frac=frac,
               peak_round=peak_round, mirror_hits=sorted(r["t1"] for r in rays))
    return res


def is_good(res):
    # the round mirror must get warm but NOT light it; the parabola lights it
    return (res["t_end"] is not None and res["t_end"] > res["stages"][2][1]
            and 45 <= res["peak_round"] <= 92 and res["frac"]["FLAT"] == 0)


_R = {}


def prepare(res, cfg):
    _R[cfg.seed] = res


def to_screen(X, Y):
    return CX + X, VY - Y


def _mirror_kind(res, t):
    """(shape a, shape b, blend) of the mirror at time t (it bends between stages)"""
    st = res["stages"]
    for i, (kind, a, b) in enumerate(st):
        if t < b:
            if i > 0 and t < a:
                return st[i - 1][0], kind, (t - (a - MORPH)) / MORPH
            return kind, kind, 0.0
    return st[-1][0], st[-1][0], 0.0


def draw(ctx, fr, cfg):
    t = fr["t"]
    res = _R[cfg.seed]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    # the sun
    for rr, a in ((70, 0.10), (48, 0.22), (30, 1.0)):
        ctx.new_path()
        ctx.arc(CX, SUN_Y - 70, rr, 0, 2 * math.pi)
        ctx.set_source_rgba(*cfg.sun_col, a)
        ctx.fill()
    # rays: the whole path of rays that are still in flight (and fading for 0.5 s after)
    ctx.save()
    ctx.rectangle(0, SUN_Y - 40, 1080, VY - SUN_Y + 120)          # keep rays off the caption
    ctx.clip()
    ctx.set_line_width(2.2)
    for r in res["rays"]:
        if r["t0"] > t:
            continue
        x0, _ = to_screen(r["X"], 0)
        y_top = SUN_Y
        if t < r["t1"]:
            y_now = y_top + (t - r["t0"]) * V
            ctx.set_source_rgba(*cfg.ray_col, 0.55)
            ctx.move_to(x0, y_top)
            ctx.line_to(x0, y_now)
            ctx.stroke()
            continue
        L = 1800.0 if r["s"] is None else r["s"]
        out = (t - r["t1"]) * V
        age = out - L
        if age > V * 0.5:
            continue
        a = 0.55 * (1 - max(0.0, age) / (V * 0.5))
        hx, hy = to_screen(r["X"], r["Y"])
        ctx.set_source_rgba(*cfg.ray_col, a * 0.5)
        ctx.move_to(x0, y_top)
        ctx.line_to(hx, hy)
        ctx.stroke()
        far = min(out, L)
        ex, ey = hx + r["r"][0] * far, hy - r["r"][1] * far
        ctx.set_source_rgba(*cfg.ray_col, a)
        ctx.move_to(hx, hy)
        ctx.line_to(ex, ey)
        ctx.stroke()
    ctx.restore()
    # the mirror (bending between stages)
    ka, kb, w = _mirror_kind(res, t)
    X = np.linspace(-HALF, HALF, 120)
    Y = (1 - w) * shape(ka, X) + w * shape(kb, X)
    for lw, a in ((16, 0.15), (7, 1.0)):
        ctx.set_line_width(lw)
        ctx.set_source_rgba(0.85, 0.92, 1.0, a)
        ctx.move_to(*to_screen(X[0], Y[0]))
        for xx, yy in zip(X[1:], Y[1:]):
            ctx.line_to(*to_screen(xx, yy))
        ctx.stroke()
    # the match: a stick and a red head at the focus
    hx, hy = to_screen(0, F)
    ctx.set_source_rgb(0.85, 0.65, 0.4)
    ctx.rectangle(hx - 5, hy, 10, 120)
    ctx.fill()
    heat = fr["heat"] / 100
    lit = fr["t_end"] is not None
    ctx.new_path()
    ctx.arc(hx, hy, HEAD, 0, 2 * math.pi)
    ctx.set_source_rgb(0.75 + 0.25 * heat, 0.12 + 0.5 * heat ** 2, 0.1)
    ctx.fill()
    if heat > 0.2 and not lit:
        ctx.new_path()
        ctx.arc(hx, hy, HEAD + 14 * heat, 0, 2 * math.pi)
        ctx.set_source_rgba(1.0, 0.55, 0.15, 0.25 * heat)
        ctx.fill()
    if lit:
        _fire(ctx, t - fr["t_end"], hx, hy, cfg.seed)
    # stage label
    ka2 = kb if w > 0 else ka
    label = {"FLAT": "1. FLAT mirror", "ROUND": "2. ROUND mirror", "PARABOLA": "3. PARABOLA mirror"}[ka2]
    text(ctx, label, 540, 470 - 40, 50, fx.CYAN, 0.95)
    # heat bar
    text(ctx, f"Heat: {fr['heat']:.0f}%", 540, 1560, 56, fx.GOLD if not lit else (1, 0.5, 0.2), 0.95)
    rounded(ctx, 290, 1590, 500, 18, 9)
    ctx.set_source_rgba(1, 1, 1, 0.15)
    ctx.fill()
    rounded(ctx, 290, 1590, max(18, 500 * heat), 18, 9)
    ctx.set_source_rgb(1.0, 0.75 - 0.45 * heat, 0.2)
    ctx.fill()
    if not lit and ka2 == "ROUND" and fr["heat"] > 40 and t > res["stages"][1][2] - 2.5:
        text(ctx, "ALMOST…", 540, 1660, 46, (1, 1, 1), 0.85)
    if lit:
        fx.banner(ctx, t, fr["t_end"] + 0.5, "IT LIT!", (1.0, 0.55, 0.15),
                  "Every ray meets at ONE point", y=880, dim=0.3)


def _fire(ctx, dt, x, y, seed):
    rng = random.Random(seed)
    grow = min(1.0, dt / 0.5)
    for i in range(46):
        ph = rng.uniform(0, 1)
        life = (dt * rng.uniform(1.4, 2.2) + ph) % 1.0
        h = 150 * grow * life
        px = x + rng.uniform(-14, 14) * (1 - life) + 10 * math.sin(dt * 7 + i)
        py = y - h
        rr = (22 * (1 - life) + 4) * grow
        col = (1.0, 0.85 - 0.6 * life, 0.25 * (1 - life))
        ctx.new_path()
        ctx.arc(px, py, rr, 0, 2 * math.pi)
        ctx.set_source_rgba(*col, 0.55 * (1 - life))
        ctx.fill()
    ctx.new_path()
    ctx.arc(x, y - 10 * grow, 18 * grow, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 0.95, 0.7, 0.9)
    ctx.fill()


AUDIO_MIN_GAP = 0.0


def audio_events(res, cfg):
    out = []
    last = -1.0
    end = (res["t_end"] + END_HOLD - 0.3) if res["t_end"] is not None else res["stages"][-1][2]
    for t, nm in melodies.track([m for m in res["mirror_hits"] if m < end], cfg.melody, 0.16):
        out.append((t, note_freq(nm), "pluck"))
    for t in res["hits"]:
        if res["t_end"] is not None and t > res["t_end"]:
            break
        if t - last > 0.07:
            out.append((t, 1760.0, "tick"))
            last = t
    if res["t_end"] is not None:
        out.append((res["t_end"], 523.25, "shatter"))
        out.append((res["t_end"] + 0.12, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="mirror", colors=[], melody=cfg.melody_name,
                t_full=round(res["t_end"] or 0, 1), n_final=int(round(res["peak_round"])))
