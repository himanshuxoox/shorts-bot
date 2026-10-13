"""
"Squeeze": four bars on springs sit around the inside of a circle. Every cycle they snap
towards the middle (making a square, a # or a +) and squash any ball in their way. Every
ball they CRUSH splits into 3 smaller balls, until the circle is packed and bursts.
Every crush plays the next note of a famous public-domain tune.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 3
CX, CY, RR = 540.0, 1000.0, 440.0
BL, BT = 230.0, 14.0                       # bar length / thickness
D_OUT = RR - 48.0
DIRS = [(0.0, -1.0), (0.0, 1.0), (-1.0, 0.0), (1.0, 0.0)]
PATTERNS = {"square": BL / 2, "hash": 62.0, "cross": 12.0}
V0 = 330.0
R0, SHRINK, RMIN = 16.0, 0.9, 5.0
MAX_T = 36.0
END_HOLD = 3.0
CELL = 12.0
GX0, GY0 = CX - RR - 24, CY - RR - 24
NX = NY = int((2 * RR + 48) / CELL) + 1
PURPLE = (0.6, 0.38, 1.0)


@dataclass
class Config:
    seed: int
    t_in: float
    t_out: float
    rest: float
    cycle: list
    h0: float
    cap: int
    melody_name: str
    melody: list


def make_config(seed):
    rng = random.Random(seed * 7717 + 5)
    mel = rng.choice(melodies.FAMOUS)
    pats = list(PATTERNS)
    cyc = [rng.choice(pats) for _ in range(40)]
    return Config(seed, rng.uniform(0.38, 0.5), rng.uniform(0.45, 0.6), rng.uniform(0.5, 0.85), cyc,
                  rng.random(), rng.randint(5000, 7500), mel, melodies.MELODIES[mel])


def bar_depth(cfg, t):
    """Distance of every bar from the centre at time t (+ its velocity)."""
    per = cfg.t_in + 0.12 + cfg.t_out + cfg.rest
    k = int(t // per)
    u = t - k * per
    d_in = PATTERNS[cfg.cycle[k % len(cfg.cycle)]]
    if u < cfg.t_in:                                  # snap in (ease-in: accelerates)
        q = u / cfg.t_in
        return D_OUT + (d_in - D_OUT) * q * q, (d_in - D_OUT) * 2 * q / cfg.t_in, k
    u -= cfg.t_in
    if u < 0.12:
        return d_in, 0.0, k
    u -= 0.12
    if u < cfg.t_out:                                 # spring back (ease-out)
        q = u / cfg.t_out
        e = 1 - (1 - q) ** 2
        return d_in + (D_OUT - d_in) * e, (D_OUT - d_in) * 2 * (1 - q) / cfg.t_out, k
    return D_OUT, 0.0, k


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    a0 = rng.uniform(0, 2 * np.pi)
    x = np.array([CX + 60 * math.cos(a0)]); y = np.array([CY + 60 * math.sin(a0)])
    vx = np.array([V0 * math.cos(a0 + 1.3)]); vy = np.array([V0 * math.sin(a0 + 1.3)])
    r = np.array([R0]); gen = np.zeros(1, int); imm = np.zeros(1)
    t, t_end = 0.0, None
    crushes, frames = [], []
    d, dv = D_OUT, 0.0
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            x += vx * h; y += vy * h
            if t_end is not None:
                continue
            d, dv, _k = bar_depth(cfg, max(0.0, tt - 0.6))
            # keep the balls lively: relax every speed towards V0
            sp = np.hypot(vx, vy) + 1e-6
            f = 1 + (V0 / sp - 1) * min(1.0, 1.5 * h)
            vx *= f; vy *= f
            # crowding
            ix = np.clip(((x - GX0) / CELL).astype(int), 0, NX - 1)
            iy = np.clip(((y - GY0) / CELL).astype(int), 0, NY - 1)
            occ = np.bincount(iy * NX + ix, weights=math.pi * r * r, minlength=NX * NY)
            occ = occ.reshape(NY, NX) / (CELL * CELL)
            gyy, gxx = np.gradient(occ)
            vx -= 650.0 * gxx[iy, ix] * h * 60
            vy -= 650.0 * gyy[iy, ix] * h * 60
            # circle wall
            dx, dy = x - CX, y - CY
            dd = np.hypot(dx, dy) + 1e-6
            m = dd > RR - r
            if m.any():
                nx, ny = dx[m] / dd[m], dy[m] / dd[m]
                pen = dd[m] - (RR - r[m])
                x[m] -= nx * pen; y[m] -= ny * pen
                vn = vx[m] * nx + vy[m] * ny
                k = np.where(vn > 0, 2 * vn, 0)
                vx[m] -= k * nx; vy[m] -= k * ny
            # bars
            for ux, uy in DIRS:
                px, py = -uy, ux
                bx, by = CX + ux * d, CY + uy * d
                a = (x - bx) * ux + (y - by) * uy           # >0: outside (rim side), <0: centre side
                b = (x - bx) * px + (y - by) * py
                hit = (np.abs(b) < BL / 2 + r * 0.6) & (np.abs(a) < BT / 2 + r)
                if not hit.any():
                    continue
                crush = hit & (a < 0) & (dv < -40) & (imm < tt) & (len(x) < cfg.cap)
                idx = np.nonzero(crush)[0][: max(0, (cfg.cap - len(x)) // 2)]
                if len(idx):
                    crushes.append((tt, len(idx)))
                    nr = np.maximum(RMIN, r[idx] * SHRINK)
                    keep = np.ones(len(x), bool); keep[idx] = False
                    off = np.tile([-1.0, 0.0, 1.0], len(idx)) * np.repeat(r[idx] * 1.1, 3)
                    cx_ = np.repeat(x[idx], 3) + px * off
                    cy_ = np.repeat(y[idx], 3) + py * off
                    ang = rng.uniform(0, 2 * np.pi, 3 * len(idx))
                    nvx = np.cos(ang) * V0 + ux * dv * 0.8
                    nvy = np.sin(ang) * V0 + uy * dv * 0.8
                    x = np.concatenate([x[keep], cx_]); y = np.concatenate([y[keep], cy_])
                    vx = np.concatenate([vx[keep], nvx]); vy = np.concatenate([vy[keep], nvy])
                    r = np.concatenate([r[keep], np.repeat(nr, 3)])
                    gen = np.concatenate([gen[keep], np.repeat(gen[idx] + 1, 3)])
                    imm = np.concatenate([imm[keep], np.full(3 * len(idx), tt + 0.4)])
                    a = (x - bx) * ux + (y - by) * uy
                    b = (x - bx) * px + (y - by) * py
                    hit = (np.abs(b) < BL / 2 + r * 0.6) & (np.abs(a) < BT / 2 + r)
                # push out of the bar on the side the ball is on, bounce off its moving face
                side = np.where(a < 0, -1.0, 1.0)
                push = (BT / 2 + r - np.abs(a)) * side
                x[hit] += ux * push[hit]; y[hit] += uy * push[hit]
                rel = (vx * ux + vy * uy) - dv
                bad = hit & (rel * side < 0)
                vx[bad] -= 2 * rel[bad] * ux; vy[bad] -= 2 * rel[bad] * uy
            if len(x) >= cfg.cap - 2:
                t_end = tt
                ang = np.arctan2(y - CY, x - CX) + rng.uniform(-0.5, 0.5, len(x))
                spd = rng.uniform(500, 1500, len(x))
                vx = np.cos(ang) * spd; vy = np.sin(ang) * spd
                break
        t += DT
        if record:
            frames.append(dict(t=t, x=x.astype(np.float32), y=y.astype(np.float32),
                               r=r.astype(np.float32), gen=gen.astype(np.int16), d=d,
                               n=len(x), t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, crushes=crushes, t_end=t_end, n=len(x))


def is_good(res):
    return res["t_end"] is not None and 18 <= res["t_end"] <= 32


def _spring(ctx, x0, y0, x1, y1, n=14, amp=9):
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1
    px, py = -dy / L, dx / L
    ctx.move_to(x0, y0)
    for k in range(1, n):
        s = k / n
        w = amp * (1 if k % 2 else -1)
        ctx.line_to(x0 + dx * s + px * w, y0 + dy * s + py * w)
    ctx.line_to(x1, y1)
    ctx.stroke()


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.rich_title(ctx, [[("Every ball caught in the ", fx.WHITE), ("SQUEEZE", fx.RED), (" splits into 3", fx.WHITE)],
                        [("Can the circle ", fx.WHITE), ("HOLD", fx.CYAN), (" them all?", fx.WHITE)]],
                  y=300, size=54)
    broken = fr["t_end"] is not None and t > fr["t_end"]
    if not broken:
        fx.glow_arc(ctx, CX, CY, RR + 6, 0, 2 * math.pi, PURPLE, width=9)
    xs, ys, rs, gs = fr["x"], fr["y"], fr["r"], fr["gen"]
    for g in np.unique(gs):
        m = gs == g
        ctx.set_source_rgb(*fx.hsv(cfg.h0 + 0.09 * int(g), 0.75, 1.0))
        for x, y, r in zip(xs[m], ys[m], rs[m]):
            ctx.new_sub_path()
            ctx.arc(float(x), float(y), float(r), 0, 2 * math.pi)
        ctx.fill()
    if not broken:
        d = fr["d"]
        ctx.set_source_rgba(0.75, 0.75, 0.8, 0.85)
        ctx.set_line_width(2.5)
        for ux, uy in DIRS:
            _spring(ctx, CX + ux * (RR + 4), CY + uy * (RR + 4), CX + ux * (d + BT / 2), CY + uy * (d + BT / 2))
        ctx.set_source_rgb(1, 1, 1)
        ctx.set_line_width(BT)
        ctx.set_line_cap(1)
        for ux, uy in DIRS:
            px, py = -uy, ux
            bx, by = CX + ux * d, CY + uy * d
            ctx.move_to(bx - px * BL / 2, by - py * BL / 2)
            ctx.line_to(bx + px * BL / 2, by + py * BL / 2)
            ctx.stroke()
    text(ctx, f"Balls: {fr['n']:,}", 540, 1525, 58, (1, 1, 1), 0.95)
    fx.music_line(ctx, y=1600)
    if fr["t_end"] is not None:
        fx.banner(ctx, t, fr["t_end"] + 0.5, f"{fr['n']:,} BALLS!", fx.GOLD, "How close was your guess?", dim=0.3)


AUDIO_MIN_GAP = 0.07


def audio_events(res, cfg):
    times = [t for t, k in res["crushes"]]
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(times, cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"], 196.0, "shatter"))
        out.append((res["t_end"] + 0.15, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="squeeze", n_final=res["n"], colors=[], t_end=round(res["t_end"], 2),
                melody=cfg.melody_name)
