"""
"Shrink vs wall": a ball bounces inside a circle. Every bounce makes the ball a little
SMALLER and makes the wall GROW inward right where it hit, drawn as dense radial spokes.
The empty space turns into a shrinking star until the wall closes in. Every bounce plays
the next note of a famous public-domain tune, and the bounces speed up as space runs out.
"""
import math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 8
CX, CY, R = 540, 960, 455
K = 720                       # wall resolution (bins around the circle)
SPOKES = 300
SPEED = 950.0
MAX_T = 32.0
END_HOLD = 2.6

PALETTES = [((1.0, 0.62, 0.1), (1.0, 0.93, 0.75)), ((0.2, 0.85, 1.0), (0.85, 1.0, 1.0)),
            ((1.0, 0.3, 0.55), (1.0, 0.85, 0.9)), ((0.55, 1.0, 0.35), (0.9, 1.0, 0.85))]


@dataclass
class Config:
    seed: int
    r0: float
    shrink: float
    amp: float
    width: float
    col: tuple
    hi: tuple
    melody_name: str
    melody: list


def make_config(seed):
    rng = random.Random(seed * 4987 + 61)
    col, hi = rng.choice(PALETTES)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(34, 44), rng.uniform(0.968, 0.978), rng.uniform(70, 92),
                  math.radians(rng.uniform(11, 16)), col, hi, mel, melodies.MELODIES[mel])


def _rho(depth, th):
    """Inner wall radius at angle th (linear interpolation over the bins)."""
    f = (th % (2 * math.pi)) / (2 * math.pi) * K
    i = int(f) % K
    j = (i + 1) % K
    a = f - int(f)
    return R - (depth[i] * (1 - a) + depth[j] * a)


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    a = rng.uniform(0, 2 * math.pi)
    x, y, r = CX + rng.uniform(-30, 30), CY + rng.uniform(-30, 30), cfg.r0
    vx, vy = SPEED * math.cos(a), SPEED * math.sin(a)
    depth = np.zeros(K)
    grown = np.full(K, -9.0)          # last time each bin grew (for the bright highlight)
    bins = np.arange(K) * 2 * math.pi / K
    t, t_end = 0.0, None
    hits, frames = [], []
    bounces = 0
    trail = []
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            for s in range(SUB):
                h = DT / SUB
                tt = t + s * h
                x += vx * h
                y += vy * h
                dx, dy = x - CX, y - CY
                d = math.hypot(dx, dy) or 1e-6
                th = math.atan2(dy, dx)
                rho = _rho(depth, th)
                if d + r >= rho:
                    # wall normal from the local slope of the boundary
                    eps = 2 * math.pi / K
                    drho = (_rho(depth, th + eps) - _rho(depth, th - eps)) / (2 * eps)
                    ux, uy = dx / d, dy / d                   # radial
                    tx, ty = -uy, ux                          # tangential
                    nx, ny = rho * ux - drho * tx, rho * uy - drho * ty
                    nl = math.hypot(nx, ny) or 1.0
                    nx, ny = nx / nl, ny / nl
                    vn = vx * nx + vy * ny
                    if vn > 0:
                        vx -= 2 * vn * nx
                        vy -= 2 * vn * ny
                        kick = rng.uniform(-160, 160)
                        vx += -ny * kick
                        vy += nx * kick
                        sp = math.hypot(vx, vy)
                        vx, vy = vx / sp * SPEED, vy / sp * SPEED
                        # the wall grows where it was hit, the ball shrinks
                        dth = (bins - th + math.pi) % (2 * math.pi) - math.pi
                        bump = cfg.amp * np.exp(-(dth / cfg.width) ** 2)
                        depth = np.minimum(depth + bump, R - 6)
                        grown[bump > 6] = tt
                        r = max(2.5, r * cfg.shrink)
                        bounces += 1
                        hits.append(tt)
                    # push back inside along the radius
                    pen = d + r - _rho(depth, th)
                    if pen > 0:
                        x -= ux * pen
                        y -= uy * pen
                inner = R - depth
                if r <= 3.0 or inner.mean() < 60:
                    t_end = tt
                    break
        t += DT
        trail.append((x, y, r))
        trail = trail[-10:]
        if record:
            frames.append(dict(t=t, ball=(x, y, r), depth=depth.copy(), grown=grown.copy(),
                               trail=list(trail), bounces=bounces, t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, t_end=t_end, bounces=bounces)


def is_good(res):
    return res["t_end"] is not None and 17 <= res["t_end"] <= 30 and res["bounces"] >= 60


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.rich_title(ctx, [[("Every bounce ", fx.WHITE), ("SHRINKS", fx.CYAN), (" the ball", fx.WHITE)],
                        [("and ", fx.WHITE), ("GROWS", fx.GOLD), (" the wall", fx.WHITE)]])
    depth, grown = fr["depth"], fr["grown"]
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    ctx.set_line_width(2.6)
    for k in range(SPOKES):
        i = k * K // SPOKES
        if depth[i] < 1.5:
            continue
        th = i * 2 * math.pi / K
        c, s = math.cos(th), math.sin(th)
        fresh = max(0.0, 1 - (t - grown[i]) / 0.6)
        col = tuple(a + (b - a) * fresh for a, b in zip(cfg.col, cfg.hi))
        ctx.set_source_rgb(*col)
        ctx.move_to(CX + R * c, CY + R * s)
        ctx.line_to(CX + (R - depth[i]) * c, CY + (R - depth[i]) * s)
        ctx.stroke()
    ctx.set_line_width(6)
    ctx.set_source_rgb(*cfg.col)
    ctx.new_path()
    ctx.arc(CX, CY, R, 0, 2 * math.pi)
    ctx.stroke()
    x, y, r = fr["ball"]
    for i, (tx, ty, tr) in enumerate(fr["trail"][:-1]):
        ctx.set_source_rgba(*cfg.col, 0.12 * (i + 1) / len(fr["trail"]))
        ctx.new_path()
        ctx.arc(tx, ty, tr, 0, 2 * math.pi)
        ctx.fill()
    fx.ball(ctx, x, y, r, cfg.col, 0, (), glow=True)
    text(ctx, f"{fr['bounces']} BOUNCES", 540, 1500, 56, (1, 1, 1), 0.9)
    fx.music_line(ctx)
    if fr["t_end"] is not None:
        fx.banner(ctx, t, fr["t_end"] + 0.2, "THE WALL WON!", cfg.col,
                  f"after {fr['bounces']} bounces", dim=0.35)


AUDIO_MIN_GAP = 0.075


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"], 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="shrink", bounces=res["bounces"], colors=[], t_end=round(res["t_end"], 2),
                melody=cfg.melody_name)
