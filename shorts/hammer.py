"""
"Drop hammer": a heavy hammer hangs on a chain inside a circle. It drops, smashes the balls
lying on the floor and is winched back up. Every ball it CRUSHES splits into 3 smaller balls
(1, 3, 9, 27 ...) until the circle is packed and bursts. Every crush plays the next note of a
famous public-domain tune.
"""
import math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, DT, text, note_freq, rounded
from . import fx, melodies

SUB = 3
CX, CY, RR = 540.0, 1000.0, 440.0
PW, PT = 340.0, 58.0                      # plate width / thickness (py = bottom face)
PY_TOP = CY - RR + 120.0
PY_LOW = CY + math.sqrt(RR * RR - (PW / 2) ** 2) - 6.0
G = 1500.0
R0, SHRINK, RMIN = 22.0, 0.87, 5.2
MAX_BALLS = 15000
MAX_T = 34.0
END_HOLD = 3.0
CELL = 12.0
GX0, GY0 = CX - RR - 24, CY - RR - 24
NX = NY = int((2 * RR + 48) / CELL) + 1
CYAN = (0.2, 0.85, 1.0)
EMBER = (1.0, 0.3, 0.12)


@dataclass
class Config:
    seed: int
    up: float
    pause: float
    h0: float
    cap: int
    melody_name: str
    melody: list


def make_config(seed):
    rng = random.Random(seed * 4421 + 9)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(560, 700), rng.uniform(0.12, 0.3), rng.random(),
                  rng.randint(6000, 9500), mel, melodies.MELODIES[mel])


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    x = np.array([CX + rng.uniform(-90, 90)]); y = np.array([CY + 150.0])
    vx = np.array([rng.choice([-1, 1]) * 120.0]); vy = np.array([-200.0])
    r = np.array([R0]); gen = np.zeros(1, int); imm = np.zeros(1)
    py, pv, phase, pause_t = PY_TOP, 0.0, "pause", -0.6
    t, t_end = 0.0, None
    crushes, slams, frames = [], [], []
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            vy += G * h
            x += vx * h; y += vy * h
            if t_end is not None:
                continue
            # hammer: free-fall drop, slow winch up, short pause
            if phase == "down":
                pv = min(1900.0, pv + 3400.0 * h)
                py += pv * h
                if py >= PY_LOW:
                    py, phase = PY_LOW, "up"
                    slams.append(tt)
            elif phase == "up":
                pv = -cfg.up
                py += pv * h
                if py <= PY_TOP:
                    py, phase, pause_t = PY_TOP, "pause", tt
            else:
                pv = 0.0
                if tt - pause_t > cfg.pause:
                    phase = "down"
            # crowding (cheap ball-ball contact)
            ix = np.clip(((x - GX0) / CELL).astype(int), 0, NX - 1)
            iy = np.clip(((y - GY0) / CELL).astype(int), 0, NY - 1)
            occ = np.bincount(iy * NX + ix, weights=math.pi * r * r, minlength=NX * NY)
            occ = occ.reshape(NY, NX) / (CELL * CELL)
            gyy, gxx = np.gradient(occ)
            vx -= 650.0 * gxx[iy, ix] * h * 60
            vy -= 650.0 * gyy[iy, ix] * h * 60
            # circle wall
            dx, dy = x - CX, y - CY
            d = np.hypot(dx, dy) + 1e-6
            m = d > RR - r
            if m.any():
                nx, ny = dx[m] / d[m], dy[m] / d[m]
                pen = d[m] - (RR - r[m])
                x[m] -= nx * pen; y[m] -= ny * pen
                vn = vx[m] * nx + vy[m] * ny
                k = np.where(vn > 0, 1.3 * vn, 0)
                vx[m] -= k * nx; vy[m] -= k * ny
            # hammer face
            under = (np.abs(x - CX) < PW / 2 + r * 0.5) & (y - r < py) & (y > py - PT)
            if under.any():
                hit = under & (pv > 0) & (imm < tt) & (len(x) < cfg.cap)
                idx = np.nonzero(hit)[0][: max(0, (cfg.cap - len(x)) // 2)]
                if len(idx):
                    crushes.append((tt, len(idx)))
                    nr = np.maximum(RMIN, r[idx] * SHRINK)
                    keep = np.ones(len(x), bool); keep[idx] = False
                    bx = np.repeat(x[idx], 3) + np.tile([-1.0, 0.0, 1.0], len(idx)) * np.repeat(r[idx], 3)
                    by = np.repeat(py + nr + 1.5, 3)
                    x = np.concatenate([x[keep], bx]); y = np.concatenate([y[keep], by])
                    vx = np.concatenate([vx[keep], rng.uniform(-140, 140, 3 * len(idx))])
                    vy = np.concatenate([vy[keep], rng.uniform(0, 120, 3 * len(idx))])
                    r = np.concatenate([r[keep], np.repeat(nr, 3)])
                    gen = np.concatenate([gen[keep], np.repeat(gen[idx] + 1, 3)])
                    imm = np.concatenate([imm[keep], np.full(3 * len(idx), tt + 0.35)])
                under = (np.abs(x - CX) < PW / 2 + r * 0.5) & (y - r < py) & (y > py - PT)
                y[under] = py + r[under]
                vy[under] = np.maximum(vy[under], pv)
            ontop = (np.abs(x - CX) < PW / 2) & (y + r > py - PT) & (y < py - PT / 2)
            y[ontop] = py - PT - r[ontop]
            vy[ontop] = np.minimum(vy[ontop], pv)
            vx[ontop] += np.sign(x[ontop] - CX + 1e-3) * 900.0 * h       # domed top: balls slide off
            vx *= 0.995; vy *= 0.997
            sp = np.hypot(vx, vy)
            fast = sp > 2200
            vx[fast] *= 2200 / sp[fast]; vy[fast] *= 2200 / sp[fast]
            if len(x) >= cfg.cap - 2 or (tt > 28 and phase == "pause"):
                t_end = tt
                ang = np.arctan2(y - CY, x - CX) + rng.uniform(-0.4, 0.4, len(x))
                spd = rng.uniform(500, 1500, len(x))
                vx = np.cos(ang) * spd; vy = np.sin(ang) * spd - 300
                break
        t += DT
        if record:
            frames.append(dict(t=t, x=x.astype(np.float32), y=y.astype(np.float32),
                               r=r.astype(np.float32), gen=gen.astype(np.int16), py=py,
                               n=len(x), t_end=t_end, slam=slams[-1] if slams else -9.0))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, crushes=crushes, t_end=t_end, n=len(x))


def is_good(res):
    return res["t_end"] is not None and 16 <= res["t_end"] <= 30 and res["n"] >= 4000


def _hammer(ctx, py, t, slam):
    top = CY - RR - 24
    # winch box on the rim
    ctx.set_source_rgb(0.13, 0.14, 0.16)
    rounded(ctx, CX - 58, top - 18, 116, 50, 8); ctx.fill()
    ctx.set_source_rgb(0.75, 0.78, 0.82); ctx.set_line_width(4)
    ctx.arc(CX, top + 7, 14, 0, 2 * math.pi); ctx.stroke()
    for k in range(6):
        a = k * math.pi / 3 + t * 6
        ctx.move_to(CX, top + 7); ctx.line_to(CX + 13 * math.cos(a), top + 7 + 13 * math.sin(a))
    ctx.stroke()
    # chain
    ctx.set_source_rgb(0.7, 0.72, 0.76); ctx.set_line_width(3)
    y = top + 32
    while y < py - PT:
        ctx.save(); ctx.translate(CX, y + 6); ctx.scale(0.55, 1)
        ctx.arc(0, 0, 7, 0, 2 * math.pi); ctx.restore(); ctx.stroke()
        y += 13
    # hammer head: dark plate with a curved bottom and a glowing edge
    x0, x1, yt = CX - PW / 2, CX + PW / 2, py - PT
    ctx.move_to(x0, yt); ctx.line_to(x1, yt); ctx.line_to(x1, yt + PT * 0.45)
    ctx.curve_to(x1 - 60, py + 8, x0 + 60, py + 8, x0, yt + PT * 0.45); ctx.close_path()
    g = cairo.LinearGradient(0, yt, 0, py)
    g.add_color_stop_rgb(0, 0.2, 0.21, 0.24); g.add_color_stop_rgb(1, 0.07, 0.07, 0.09)
    ctx.set_source(g); ctx.fill_preserve()
    glow = 0.5 + 0.5 * max(0.0, 1 - (t - slam) / 0.4)
    ctx.set_source_rgba(*EMBER, glow); ctx.set_line_width(5); ctx.stroke()
    ctx.set_source_rgba(0.6, 0.62, 0.66, 1); ctx.set_line_width(3)
    ctx.move_to(x0, yt); ctx.line_to(x1, yt); ctx.stroke()
    for bx in (x0 + 14, x1 - 14):
        ctx.arc(bx, yt + 12, 3.5, 0, 2 * math.pi); ctx.fill()
    ctx.set_source_rgb(0.95, 0.65, 0.2); ctx.set_line_width(5)
    for k in range(3):                           # chevrons pointing down
        yy = yt + 12 + k * 11
        ctx.move_to(CX - 18, yy); ctx.line_to(CX, yy + 10); ctx.line_to(CX + 18, yy)
    ctx.stroke()


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.rich_title(ctx, [[("Every ball the ", fx.WHITE), ("HAMMER", fx.RED), (" hits splits into 3", fx.WHITE)],
                        [("How many can the circle ", fx.WHITE), ("HOLD", fx.CYAN), ("?", fx.WHITE)]],
                  y=300, size=54)
    broken = fr["t_end"] is not None and t > fr["t_end"]
    if not broken:
        fx.glow_arc(ctx, CX, CY, RR + 6, 0, 2 * math.pi, CYAN, width=10)
    xs, ys, rs, gs = fr["x"], fr["y"], fr["r"], fr["gen"]
    for g in np.unique(gs):
        m = gs == g
        ctx.set_source_rgb(*fx.hsv(cfg.h0 + 0.13 * int(g), 0.75, 1.0))
        for x, y, r in zip(xs[m], ys[m], rs[m]):
            ctx.new_sub_path()
            ctx.arc(float(x), float(y), float(r), 0, 2 * math.pi)
        ctx.fill()
    if not broken:
        _hammer(ctx, fr["py"], t, fr["slam"])
        if 0 <= t - fr["slam"] < 0.25:          # sparks where the head hits the floor
            k = (t - fr["slam"]) / 0.25
            ctx.set_source_rgba(1, 0.75, 0.3, 1 - k); ctx.set_line_width(3)
            for j in range(10):
                a = math.pi + j * math.pi / 9
                bx = CX + (PW / 2 + 6) * (1 if j % 2 else -1)
                ctx.move_to(bx, PY_LOW - 4)
                ctx.line_to(bx + 40 * k * math.cos(a) * (1 if j % 2 else -1), PY_LOW - 4 + 60 * k * math.sin(a))
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
    return dict(template="hammer", n_final=res["n"], colors=[], t_end=round(res["t_end"], 2),
                melody=cfg.melody_name)
