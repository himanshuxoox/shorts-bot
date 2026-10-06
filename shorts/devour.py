"""
"Devour": a circle full of pellets. A tiny swarm of glowing critters eats the pellets and
every few pellets each critter SPLITS in two, so the swarm explodes. A small black hole
roams the circle eating critters, and every critter it eats makes it BIGGER — until it
swallows the entire swarm. (Same idea as the viral "eater vs swarm" videos, with our own
original characters: no game characters are used.)
"""
import math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 3
CX, CY, R = 540, 960, 455
SPACING = 18
CRIT_R = 10.0
SPLIT_AFTER = 2            # pellets a critter eats before it splits
MAX_CRIT = 1600
CRIT_SPEED = 140.0
HOLE_R0 = 16.0
MAX_T = 34.0
END_HOLD = 2.6
CRIT_COLS = [(1.0, 0.35, 0.45), (0.3, 0.85, 1.0), (1.0, 0.6, 0.85), (0.65, 0.45, 1.0),
             (1.0, 0.7, 0.25), (0.35, 1.0, 0.6)]


@dataclass
class Config:
    seed: int
    hole_speed: float
    grow: float
    pull: float
    ring: tuple
    melody_name: str
    melody: list


def make_config(seed):
    rng = random.Random(seed * 2851 + 9)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(80, 105), rng.uniform(50, 70), rng.uniform(1.0, 1.6),
                  rng.choice([(1.0, 0.55, 0.15), (0.6, 0.4, 1.0), (0.2, 0.8, 1.0)]),
                  mel, melodies.MELODIES[mel])


def _pellets():
    xs = np.arange(CX - R + SPACING, CX + R, SPACING)
    ys = np.arange(CY - R + SPACING, CY + R, SPACING)
    gx, gy = np.meshgrid(xs, ys)
    inside = np.hypot(gx - CX, gy - CY) < R - 14
    return gx, gy, inside


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    gx, gy, alive = _pellets()
    x0 = gx[0, 0]; y0 = gy[0, 0]
    # swarm: 2 critters near the edge, hole in the middle
    a = rng.uniform(0, 2 * np.pi, 2)
    cx = CX + 300 * np.cos(a); cy = CY + 300 * np.sin(a)
    head = rng.uniform(0, 2 * np.pi, 2)
    full = np.zeros(2, int)
    col = rng.integers(0, len(CRIT_COLS), 2)
    hx, hy, hr = float(CX), float(CY), HOLE_R0
    hvx, hvy = cfg.hole_speed, 0.0
    t, t_end = 0.0, None
    peak, eaten = 2, 0
    eats, frames = [], []
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            for s in range(SUB):
                h = DT / SUB
                tt = t + s * h
                n = len(cx)
                # critters wander, avoid the wall, and are pulled toward the hole when close
                head += rng.normal(0, 2.2, n) * math.sqrt(h)
                vx = CRIT_SPEED * np.cos(head); vy = CRIT_SPEED * np.sin(head)
                dxh, dyh = hx - cx, hy - cy
                dh = np.hypot(dxh, dyh) + 1e-6
                near = dh < hr * 3.2
                pull = cfg.pull * CRIT_SPEED * (hr * 3.2 - dh[near]) / (hr * 3.2)
                vx[near] += dxh[near] / dh[near] * pull
                vy[near] += dyh[near] / dh[near] * pull
                cx += vx * h; cy += vy * h
                dc = np.hypot(cx - CX, cy - CY)
                out = dc > R - CRIT_R
                if out.any():
                    cx[out] = CX + (cx[out] - CX) / dc[out] * (R - CRIT_R)
                    cy[out] = CY + (cy[out] - CY) / dc[out] * (R - CRIT_R)
                    head[out] = np.arctan2(CY - cy[out], CX - cx[out]) + rng.uniform(-1, 1, out.sum())
                # eat pellets (grid lookup)
                ix = np.rint((cx - x0) / SPACING).astype(int)
                iy = np.rint((cy - y0) / SPACING).astype(int)
                ok = (ix >= 0) & (iy >= 0) & (ix < gx.shape[1]) & (iy < gx.shape[0])
                ix, iy = np.where(ok, ix, 0), np.where(ok, iy, 0)
                got = ok & alive[iy, ix]
                if got.any():
                    alive[iy[got], ix[got]] = False
                    full[got] += 1
                # split
                sp = np.nonzero(full >= SPLIT_AFTER)[0]
                if len(sp) and len(cx) < MAX_CRIT:
                    sp = sp[: MAX_CRIT - len(cx)]
                    full[sp] = 0
                    cx = np.concatenate([cx, cx[sp] + 3]); cy = np.concatenate([cy, cy[sp] + 3])
                    head = np.concatenate([head, head[sp] + np.pi * rng.uniform(0.5, 1.5, len(sp))])
                    full = np.concatenate([full, np.zeros(len(sp), int)])
                    col = np.concatenate([col, rng.integers(0, len(CRIT_COLS), len(sp))])
                # the hole roams, steering toward the crowd
                if len(cx):
                    j = np.argsort(np.hypot(cx - hx, cy - hy))[:40]
                    tx, ty = cx[j].mean() - hx, cy[j].mean() - hy
                    tl = math.hypot(tx, ty) or 1.0
                    # the hole wakes up slowly, so the swarm has time to explode first
                    sp_h = cfg.hole_speed * min(1.0, 0.1 + tt / 14) * (1 + 0.6 * (hr / R))
                    hvx += (tx / tl * sp_h - hvx) * 1.5 * h
                    hvy += (ty / tl * sp_h - hvy) * 1.5 * h
                hx += hvx * h; hy += hvy * h
                dd = math.hypot(hx - CX, hy - CY)
                if dd > R - hr:
                    nx, ny = (hx - CX) / dd, (hy - CY) / dd
                    hx, hy = CX + nx * (R - hr), CY + ny * (R - hr)
                    vn = hvx * nx + hvy * ny
                    if vn > 0:
                        hvx -= 2 * vn * nx; hvy -= 2 * vn * ny
                # the hole eats critters (and pellets) it covers
                dh = np.hypot(cx - hx, cy - hy)
                gone = dh < hr
                k = int(gone.sum())
                if k:
                    keep = ~gone
                    cx, cy, head, full, col = cx[keep], cy[keep], head[keep], full[keep], col[keep]
                    hr = min(R, math.sqrt(hr * hr + cfg.grow * k))
                    eaten += k
                    eats.append((tt, k))
                pm = alive & (np.hypot(gx - hx, gy - hy) < hr)
                if pm.any():
                    alive[pm] = False
                peak = max(peak, len(cx))
                if len(cx) == 0 or hr >= R - 4:
                    t_end = tt
                    break
        t += DT
        if record:
            frames.append(dict(t=t, cx=cx.astype(np.float32), cy=cy.astype(np.float32),
                               col=col.astype(np.int8), alive=alive.copy(), hole=(hx, hy, hr),
                               n=len(cx), eaten=eaten, t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, eats=eats, t_end=t_end, peak=peak, eaten=eaten)


def is_good(res):
    return (res["t_end"] is not None and 13 <= res["t_end"] <= 30 and res["peak"] >= 300)


def _draw_hole(ctx, x, y, r, ring, t):
    g = cairo.RadialGradient(x, y, r * 0.75, x, y, r * 1.35 + 10)
    g.add_color_stop_rgba(0, *ring, 0.95)
    g.add_color_stop_rgba(0.35, *ring, 0.45)
    g.add_color_stop_rgba(1, *ring, 0.0)
    ctx.set_source(g)
    ctx.new_path()
    ctx.arc(x, y, r * 1.35 + 10, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgb(0, 0, 0)
    ctx.new_path()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill()
    # spinning swirl lines inside the rim
    ctx.set_line_width(max(1.5, r * 0.03))
    for k in range(3):
        a0 = t * 2.5 + k * 2.1
        ctx.set_source_rgba(*ring, 0.55)
        ctx.new_path()
        ctx.arc(x, y, r * (0.86 - 0.12 * k), a0, a0 + 1.4)
        ctx.stroke()


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.rich_title(ctx, [[("Every ", fx.WHITE), ("BALL", fx.RED), (" it eats makes", fx.WHITE)],
                        [("the ", fx.WHITE), ("BLACK HOLE", cfg.ring), (" BIGGER", fx.CYAN)]])
    ctx.set_line_width(4)
    ctx.set_source_rgb(0.25, 0.35, 1.0)
    ctx.new_path()
    ctx.arc(CX, CY, R, 0, 2 * math.pi)
    ctx.stroke()
    gx, gy, _ = _PELLETS
    ys, xs = np.nonzero(fr["alive"])
    ctx.set_source_rgba(0.6, 0.6, 0.62, 0.9)
    for i, j in zip(ys, xs):
        ctx.rectangle(gx[i, j] - 2.5, gy[i, j] - 2.5, 5, 5)
    ctx.fill()
    for c in range(len(CRIT_COLS)):
        m = fr["col"] == c
        if not m.any():
            continue
        ctx.set_source_rgb(*CRIT_COLS[c])
        for x, y in zip(fr["cx"][m], fr["cy"][m]):
            ctx.new_sub_path()
            ctx.arc(float(x), float(y), CRIT_R, 0, 2 * math.pi)
        ctx.fill()
    if fr["n"] <= 400:      # little eyes while there are few enough to see them
        ctx.set_source_rgb(1, 1, 1)
        for x, y in zip(fr["cx"], fr["cy"]):
            for ex in (-3, 3):
                ctx.new_sub_path()
                ctx.arc(float(x) + ex, float(y) - 2, 2.2, 0, 2 * math.pi)
        ctx.fill()
    hx, hy, hr = fr["hole"]
    if fr["t_end"] is not None:          # finale: the hole swallows the whole circle
        k = min(1.0, (t - fr["t_end"]) / 0.8)
        k = 1 - (1 - k) ** 3
        hx, hy, hr = hx + (CX - hx) * k, hy + (CY - hy) * k, hr + (R - hr) * k
    _draw_hole(ctx, hx, hy, hr, cfg.ring, t)
    text(ctx, f"SWARM: {fr['n']:,}", 540, 1500, 56, (1, 1, 1), 0.92)
    fx.music_line(ctx)
    if fr["t_end"] is not None:
        fx.banner(ctx, t, fr["t_end"] + 0.9, f"ATE ALL {fr['eaten']:,}!", cfg.ring,
                  "Did you think it could?", dim=0.35)


_PELLETS = _pellets()


AUDIO_MIN_GAP = 0.08


def audio_events(res, cfg):
    times = [t for t, k in res["eats"]]
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(times, cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"], 261.6, "shatter"))
        out.append((res["t_end"] + 0.1, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="devour", peak=res["peak"], eaten=res["eaten"], colors=[],
                t_end=round(res["t_end"], 2), melody=cfg.melody_name)
