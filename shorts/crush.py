"""
"Crusher": one ball drops into a bucket under a hydraulic press. Every ball the press
CRUSHES splits into 3 SMALLER balls, so the count explodes: 1, 3, 9, 27 … thousands,
until the bucket can't hold any more and bursts. Every crush plays the next note of a
famous public-domain tune.
"""
import math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 3
LEFT, RIGHT, FLOOR, CHAMF = 150.0, 930.0, 1400.0, 1250.0
FL0, FL1 = 290.0, 790.0                       # flat floor ends (after the chamfers)
TOP = 560.0
PCX, PW, PT = 540.0, 560.0, 34.0              # press plate centre x, width, thickness
PRESS_TOP = 640.0
G = 1500.0
R0, SHRINK, RMIN = 34.0, 0.75, 3.4
MAX_BALLS = 16000
MAX_T = 32.0
END_HOLD = 3.0
CELL = 12.0
GX0, GY0 = LEFT - 24, 300.0
NX, NY = int((RIGHT - LEFT + 48) / CELL) + 1, int((FLOOR - GY0 + 24) / CELL) + 1
GREEN = (0.55, 1.0, 0.2)
STRIPE = (1.0, 0.8, 0.1)


def _walls():
    out = []
    for (ax, ay), (bx, by) in [((LEFT, TOP - 400), (LEFT, CHAMF)), ((LEFT, CHAMF), (FL0, FLOOR)),
                               ((FL0, FLOOR), (FL1, FLOOR)), ((FL1, FLOOR), (RIGHT, CHAMF)),
                               ((RIGHT, CHAMF), (RIGHT, TOP - 400))]:
        dx, dy = bx - ax, by - ay
        nx, ny = dy, -dx                   # inward normal for clockwise order (screen coords)
        l = math.hypot(nx, ny)
        nx, ny = nx / l, ny / l
        if nx * (540 - ax) + ny * (900 - ay) < 0:
            nx, ny = -nx, -ny
        out.append((ax, ay, nx, ny))
    return out


WALLS = _walls()


@dataclass
class Config:
    seed: int
    down: float
    up: float
    pause: float
    h0: float
    cap: int
    melody_name: str
    melody: list


def make_config(seed):
    rng = random.Random(seed * 3313 + 77)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(380, 460), rng.uniform(650, 800), rng.uniform(0.25, 0.45),
                  rng.random(), rng.randint(11000, MAX_BALLS), mel, melodies.MELODIES[mel])


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    x = np.array([PCX - 120.0]); y = np.array([TOP + 330.0])
    vx = np.array([160.0]); vy = np.array([0.0])
    r = np.array([R0]); gen = np.zeros(1, int); imm = np.zeros(1)
    py, phase, pause_t = PRESS_TOP, "down", 0.0      # py = bottom face of the plate
    t, t_end = 0.0, None
    crushes, frames = [], []
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            vy += G * h
            x += vx * h; y += vy * h
            if t_end is not None:
                continue
            # press motion
            if phase == "down":
                pv = cfg.down
                py += pv * h
                if py >= FLOOR - 22:
                    py, phase = FLOOR - 22, "up"
            elif phase == "up":
                pv = -cfg.up
                py += pv * h
                if py <= PRESS_TOP:
                    py, phase, pause_t = PRESS_TOP, "pause", tt
            else:
                pv = 0.0
                if tt - pause_t > cfg.pause:
                    phase = "down"
            # crowding: push balls away from dense cells (cheap stand-in for ball-ball contact)
            ix = np.clip(((x - GX0) / CELL).astype(int), 0, NX - 1)
            iy = np.clip(((y - GY0) / CELL).astype(int), 0, NY - 1)
            occ = np.bincount(iy * NX + ix, weights=math.pi * r * r, minlength=NX * NY)
            occ = occ.reshape(NY, NX) / (CELL * CELL)
            gyy, gxx = np.gradient(occ)
            k = 650.0
            vx -= k * gxx[iy, ix] * h * 60
            vy -= k * gyy[iy, ix] * h * 60
            # bucket walls (convex: half-planes)
            for ax, ay, nx, ny in WALLS:
                sd = nx * (x - ax) + ny * (y - ay)
                m = sd < r
                if m.any():
                    x[m] += (r[m] - sd[m]) * nx; y[m] += (r[m] - sd[m]) * ny
                    vn = vx[m] * nx + vy[m] * ny
                    neg = vn < 0
                    vx[m] -= np.where(neg, 1.25 * vn * nx, 0); vy[m] -= np.where(neg, 1.25 * vn * ny, 0)
            # press plate
            under = (np.abs(x - PCX) < PW / 2 + r * 0.5) & (y - r < py) & (y > py - PT)
            if under.any():
                hit = under & (pv > 0) & (imm < tt) & (len(x) < cfg.cap)
                idx = np.nonzero(hit)[0][: max(0, (cfg.cap - len(x)) // 2)]
                if len(idx):
                    crushes.append((tt, len(idx)))
                    nr = np.maximum(RMIN, r[idx] * SHRINK)
                    keep = np.ones(len(x), bool); keep[idx] = False
                    bx = np.repeat(x[idx], 3) + np.tile([-1.0, 0.0, 1.0], len(idx)) * np.repeat(r[idx], 3)
                    by = np.repeat(py + nr + 1.5, 3)
                    bvx = rng.uniform(-150, 150, 3 * len(idx))
                    bvy = rng.uniform(40, 200, 3 * len(idx))
                    x = np.concatenate([x[keep], bx]); y = np.concatenate([y[keep], by])
                    vx = np.concatenate([vx[keep], bvx]); vy = np.concatenate([vy[keep], bvy])
                    r = np.concatenate([r[keep], np.repeat(nr, 3)])
                    gen = np.concatenate([gen[keep], np.repeat(gen[idx] + 1, 3)])
                    imm = np.concatenate([imm[keep], np.full(3 * len(idx), tt + 0.35)])
                under = (np.abs(x - PCX) < PW / 2 + r * 0.5) & (y - r < py) & (y > py - PT)
                y[under] = py + r[under]
                vy[under] = np.maximum(vy[under], pv)
            # balls resting on top of the plate
            ontop = (np.abs(x - PCX) < PW / 2) & (y + r > py - PT) & (y < py - PT / 2)
            y[ontop] = py - PT - r[ontop]
            vy[ontop] = np.minimum(vy[ontop], pv)
            vx *= 0.99; vy *= 0.995
            y = np.maximum(y, 470 + r)          # invisible lid below the caption
            sp = np.hypot(vx, vy)
            fast = sp > 2200
            vx[fast] *= 2200 / sp[fast]; vy[fast] *= 2200 / sp[fast]
            if len(x) >= cfg.cap - 2 or (tt > 26 and phase == "pause"):
                t_end = tt
                # the bucket bursts
                ang = rng.uniform(0, 2 * np.pi, len(x))
                spd = rng.uniform(300, 1300, len(x))
                vx = np.cos(ang) * spd; vy = np.sin(ang) * spd - 500
                break
        t += DT
        if record:
            frames.append(dict(t=t, x=x.astype(np.float32), y=y.astype(np.float32),
                               r=r.astype(np.float32), gen=gen.astype(np.int16), py=py,
                               n=len(x), t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, crushes=crushes, t_end=t_end, n=len(x))


def is_good(res):
    return res["t_end"] is not None and 18 <= res["t_end"] <= 30 and res["n"] >= 5000


def _stripes(ctx, x0, y0, w, h, phase=0.0):
    ctx.save()
    ctx.rectangle(x0, y0, w, h)
    ctx.clip()
    ctx.set_source_rgb(0.1, 0.1, 0.1)
    ctx.paint()
    ctx.set_source_rgb(*STRIPE)
    step = h * 2.2
    xx = x0 - h + (phase % step)
    while xx < x0 + w:
        ctx.move_to(xx, y0 + h); ctx.line_to(xx + h, y0); ctx.line_to(xx + h + step / 2.4, y0)
        ctx.line_to(xx + step / 2.4, y0 + h); ctx.close_path()
        xx += step
    ctx.fill()
    ctx.restore()


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.rich_title(ctx, [[("Every ball ", fx.WHITE), ("CRUSHED", fx.RED), (" splits into 3 ", fx.WHITE),
                         ("SMALLER", fx.GOLD), (" ones", fx.WHITE)],
                        [("How many can it ", fx.WHITE), ("HANDLE", fx.RED), ("?", fx.WHITE)]], y=300, size=54)
    broken = fr["t_end"] is not None and t > fr["t_end"]
    if not broken:
        ctx.set_line_width(8)
        ctx.set_source_rgb(*GREEN)
        ctx.move_to(LEFT, TOP); ctx.line_to(LEFT, CHAMF); ctx.line_to(FL0, FLOOR)
        ctx.line_to(FL1, FLOOR); ctx.line_to(RIGHT, CHAMF); ctx.line_to(RIGHT, TOP)
        ctx.stroke()
        _stripes(ctx, FL0 - 60, FLOOR + 6, FL1 - FL0 + 120, 22)
    # balls, one fill per generation colour
    xs, ys, rs, gs = fr["x"], fr["y"], fr["r"], fr["gen"]
    for g in np.unique(gs):
        m = gs == g
        ctx.set_source_rgb(*fx.hsv(cfg.h0 + 0.11 * int(g), 0.75, 1.0))
        for x, y, r in zip(xs[m], ys[m], rs[m]):
            ctx.new_sub_path()
            ctx.arc(float(x), float(y), float(r), 0, 2 * math.pi)
        ctx.fill()
    if not broken:
        py = fr["py"]
        ctx.set_source_rgb(0.22, 0.22, 0.24)
        ctx.rectangle(PCX - 18, 430, 36, max(0, py - PT - 430))
        ctx.fill()
        ctx.rectangle(PCX - 60, 418, 120, 16)
        ctx.fill()
        ctx.set_source_rgb(*GREEN)
        ctx.rectangle(PCX - PW / 2 - 8, py - PT - 8, PW + 16, 8)
        ctx.fill()
        _stripes(ctx, PCX - PW / 2, py - PT, PW, PT, phase=t * 40)
    text(ctx, f"Balls: {fr['n']:,}", 540, 1500, 58, (1, 1, 1), 0.95)
    fx.music_line(ctx)
    if fr["t_end"] is not None:
        fx.banner(ctx, t, fr["t_end"] + 0.5, f"{fr['n']:,} BALLS!", fx.GOLD,
                  "How close was your guess?", dim=0.3)


AUDIO_MIN_GAP = 0.07


def audio_events(res, cfg):
    times = [t for t, k in res["crushes"]]
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(times, cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"], 196.0, "shatter"))
        out.append((res["t_end"] + 0.15, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="crush", n_final=res["n"], colors=[], t_end=round(res["t_end"], 2),
                melody=cfg.melody_name)
