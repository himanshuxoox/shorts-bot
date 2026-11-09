"""
"Spiral": a ball zig-zags down a spiral groove lined with spikes. Every wall hit makes it 1%
faster, so it starts slow and is a blur by the time it hits the glowing CENTER. Speed counter
in px/s, and the groove lights up behind it. Notes follow a famous public-domain tune.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies, refkit

CX, CY = 540, 1000
R_OUT, R_IN = 440.0, 62.0
PITCH = 66.0
GROOVE = 46.0
BR = 13.0                       # ball radius
MAX_T = 34.0
END_HOLD = 2.8
CAPS = ["It gets FASTER | until it hits the CENTER",
        "Every bounce makes it FASTER | How fast at the CENTER?",
        "It speeds up on EVERY bounce | Wait for the CENTER"]
B = PITCH / (2 * math.pi)
PHI_END = (R_OUT - R_IN) / B


def _table():
    phi = np.linspace(0, PHI_END, 6000)
    r = R_OUT - B * phi
    ds = np.sqrt(r ** 2 + B ** 2) * (phi[1] - phi[0])
    s = np.concatenate([[0], np.cumsum(ds[:-1])])
    return phi, s


PHI_T, S_T = _table()
LENGTH = float(S_T[-1])


def at(s, u, rot):
    """Point on the groove: arc length s along the centre line, u = sideways offset (+ outward)."""
    phi = float(np.interp(s, S_T, PHI_T))
    r = R_OUT - B * phi + u
    a = rot + phi
    return CX + r * math.cos(a), CY + r * math.sin(a)


@dataclass
class Config:
    seed: int
    v0: float
    grow: float
    alpha: float
    h0: float
    rot: float
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 5413 + 9)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(150, 210), rng.uniform(1.009, 1.012), math.radians(rng.uniform(36, 46)),
                  rng.random(), rng.uniform(0, 2 * math.pi), mel, melodies.MELODIES[mel], rng.choice(CAPS))


def simulate(cfg, record=False):
    s, u, d = 0.0, 0.0, 1
    v = cfg.v0
    umax = GROOVE / 2 - BR
    t, t_end = 0.0, None
    frames, hits, trail = [], [], []
    pulse = 0.0
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            left = DT
            while left > 0:
                vs, vu = v * math.cos(cfg.alpha), v * math.sin(cfg.alpha) * d
                tw = (umax * d - u) / vu
                te = (LENGTH - s) / vs
                if te <= min(tw, left):
                    t_end = t + (DT - left) + te
                    s = LENGTH
                    break
                if tw <= left:
                    s += vs * tw
                    u = umax * d
                    left -= tw
                    d = -d
                    v *= cfg.grow
                    hits.append(t + DT - left)
                    pulse = 1.0
                else:
                    s += vs * left
                    u += vu * left
                    left = 0
        t += DT
        pulse = max(0.0, pulse - DT * 6)
        if record:
            trail.append((s, u))
            trail = trail[-10:]
            frames.append(dict(t=t, s=s, u=u, v=v, trail=list(trail), pulse=pulse, t_end=t_end,
                               bounces=len(hits)))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, t_end=t_end, bounces=len(hits), v_end=v)


def is_good(res):
    return res["t_end"] is not None and 16 <= res["t_end"] <= 28


_LAYER = {}


def _walls(cfg):
    """The spiked walls never change: drawn once."""
    import cairo
    from .common import W, H
    if cfg.seed in _LAYER:
        return _LAYER[cfg.seed]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ss = np.linspace(-40, LENGTH + 30, 2600)
    for side in (-1, 1):
        pts = [at(max(0.0, x), side * GROOVE / 2, cfg.rot) for x in ss]
        for w, a in ((9, 0.18), (3, 1.0)):
            ctx.set_line_width(w)
            for c0 in range(0, len(pts) - 1, 40):
                seg = pts[c0:c0 + 41]
                ctx.set_source_rgba(*fx.hsv(cfg.h0 + 0.75 * c0 / len(pts), 0.75, 1.0), a)
                ctx.move_to(*seg[0])
                for p in seg[1:]:
                    ctx.line_to(*p)
                ctx.stroke()
        # spikes pointing into the groove
        for x in np.arange(10, LENGTH, 17.0):
            p0 = at(x - 6, side * GROOVE / 2, cfg.rot)
            p1 = at(x + 6, side * GROOVE / 2, cfg.rot)
            tip = at(x, side * (GROOVE / 2 - 10), cfg.rot)
            ctx.set_source_rgba(*fx.hsv(cfg.h0 + 0.75 * x / LENGTH, 0.7, 1.0), 0.95)
            ctx.move_to(*p0)
            ctx.line_to(*tip)
            ctx.line_to(*p1)
            ctx.close_path()
            ctx.fill()
    surf.flush()
    _LAYER[cfg.seed] = surf
    return surf


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    done = fr["t_end"] is not None
    # lit groove behind the ball
    ss = np.linspace(0, fr["s"], max(2, int(fr["s"] / 8)))
    if len(ss) > 2:
        ctx.set_line_width(GROOVE - 20)
        ctx.set_source_rgba(1, 1, 1, 0.13)
        ctx.move_to(*at(ss[0], 0, cfg.rot))
        for x in ss[1:]:
            ctx.line_to(*at(x, 0, cfg.rot))
        ctx.stroke()
    ctx.set_source_surface(_walls(cfg), 0, 0)
    ctx.paint()
    # the centre target
    pul = 0.5 + 0.5 * math.sin(t * 6)
    core = fx.GOLD if done else fx.hsv(cfg.h0 + 0.5, 0.6, 1.0)
    for rr, a in ((46, 0.15 + 0.1 * pul), (30, 0.35), (18, 1.0)):
        ctx.new_path()
        ctx.arc(CX, CY, rr * (1.6 if done else 1.0), 0, 2 * math.pi)
        ctx.set_source_rgba(*core, a)
        ctx.fill()
    if not done:
        tr = [at(s, u, cfg.rot) for s, u in fr["trail"]]
        for i in range(1, len(tr)):
            ctx.set_line_width(BR * 1.8 * i / len(tr))
            ctx.set_source_rgba(1, 1, 1, 0.4 * i / len(tr))
            ctx.move_to(*tr[i - 1])
            ctx.line_to(*tr[i])
            ctx.stroke()
        x, y = at(fr["s"], fr["u"], cfg.rot)
        fx.ball(ctx, x, y, BR, (1, 1, 1), fr["pulse"])
    else:
        k = (t - fr["t_end"]) / 0.8
        if k < 1:
            ctx.new_path()
            ctx.arc(CX, CY, 40 + 500 * k, 0, 2 * math.pi)
            ctx.set_source_rgba(*fx.GOLD, 0.8 * (1 - k))
            ctx.set_line_width(14 * (1 - k) + 2)
            ctx.stroke()
    v = fr["v"]
    text(ctx, f"{v:,.0f} px/s", 540, 1522, 64, fx.GOLD, 0.95)
    # speed bar
    k = min(1.0, math.log(v / cfg.v0) / math.log(25))
    from .common import rounded
    rounded(ctx, 290, 1548, 500, 16, 8)
    ctx.set_source_rgba(1, 1, 1, 0.15)
    ctx.fill()
    rounded(ctx, 290, 1548, max(16, 500 * k), 16, 8)
    ctx.set_source_rgb(*fx.hsv(0.33 - 0.33 * k, 0.8, 1.0))
    ctx.fill()
    text(ctx, f"Bounces: {fr['bounces']}", 540, 1604, 40, (1, 1, 1), 0.8)
    fx.music_line(ctx, y=1652)
    if done:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.5, f"{v:,.0f} px/s!", fx.GOLD,
                  f"{v / cfg.v0:.0f}× faster than the start", dim=0.35)


AUDIO_MIN_GAP = 0.075


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"], 523.25, "shatter"))
        out.append((res["t_end"] + 0.12, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="spiral", bounces=res["bounces"], colors=[], melody=cfg.melody_name,
                n_final=int(res["v_end"]), speedup=round(res["v_end"] / cfg.v0))
