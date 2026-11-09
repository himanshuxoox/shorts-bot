"""
"Breakout": a ball in a box full of rainbow bricks, no paddle. Every brick it shatters makes it
a little FASTER, so it starts lazy and ends as a blur hunting the last bricks.
Speed counter, brick counter, and every brick plays the next note of a public-domain tune.
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, text, note_freq
from . import fx, melodies, refkit

X0, Y0, SIZE = 110, 570, 860          # the box
COLS = 14
TOP = 2                    # empty rows above the bricks: once the ball gets up there it goes wild
GAP = 4
MAX_T = 34.0
END_HOLD = 2.8
VMAX = 11000.0
HOME = 14                 # the last bricks: the ball is pulled towards them off the walls
CAPS = ["The ball speeds up every time | it SHATTERS a brick",
        "Every brick makes it FASTER | Can it break them ALL?",
        "Every brick it breaks | makes it FASTER"]


@dataclass
class Config:
    seed: int
    rows: int
    v0: float
    grow: float
    h0: float
    r: float
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 2851 + 17)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.choice([9, 10, 11]), rng.uniform(1300, 1600), rng.uniform(1.018, 1.024),
                  rng.random(), rng.uniform(12, 15), mel, melodies.MELODIES[mel], rng.choice(CAPS))


CELL = SIZE / COLS


def brick_rect(i, j):
    return X0 + j * CELL + GAP / 2, Y0 + (i + TOP) * CELL + GAP / 2, CELL - GAP, CELL - GAP


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    alive = [[True] * COLS for _ in range(cfg.rows)]
    left = cfg.rows * COLS
    r = cfg.r
    x, y = X0 + SIZE / 2 + rng.uniform(-150, 150), Y0 + SIZE - 60
    a = -math.pi / 2 + rng.uniform(-0.7, 0.7)
    v = cfg.v0
    vx, vy = v * math.cos(a), v * math.sin(a)
    t, t_end = 0.0, None
    frames, hits, walls, breaks, trail = [], [], [], [], []
    pulse = 0.0
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            sub = max(4, math.ceil(v * DT / 4))
            h = DT / sub
            for s in range(sub):
                tt = t + s * h
                x += vx * h
                y += vy * h
                # walls
                if x - r < X0 and vx < 0:
                    vx, x = -vx, X0 + r
                    walls.append(tt)
                if x + r > X0 + SIZE and vx > 0:
                    vx, x = -vx, X0 + SIZE - r
                    walls.append(tt)
                if y - r < Y0 and vy < 0:
                    vy, y = -vy, Y0 + r
                    walls.append(tt)
                if y + r > Y0 + SIZE and vy > 0:
                    vy, y = -vy, Y0 + SIZE - r
                    walls.append(tt)
                if walls and walls[-1] == tt:
                    if left <= max(HOME, cfg.rows * COLS // 4):                  # endgame: aim off the wall at a brick that is left
                        cand = [(i, j) for i in range(cfg.rows) for j in range(COLS) if alive[i][j]]
                        bi, bj = rng.choice(cand)
                        bx, by, bw, bh = brick_rect(bi, bj)
                        ang = math.atan2(by + bh / 2 - y, bx + bw / 2 - x) + rng.uniform(-0.05, 0.05)
                    else:                             # a little random spin: no endless loops
                        ang = math.atan2(vy, vx) + rng.uniform(-0.18, 0.18)
                    vx, vy = v * math.cos(ang), v * math.sin(ang)
                # bricks around the ball
                ci, cj = int((y - Y0) // CELL) - TOP, int((x - X0) // CELL)
                hit = None
                for i in range(ci - 1, ci + 2):
                    if not 0 <= i < cfg.rows:
                        continue
                    for j in range(cj - 1, cj + 2):
                        if not 0 <= j < COLS or not alive[i][j]:
                            continue
                        bx, by, bw, bh = brick_rect(i, j)
                        qx, qy = min(max(x, bx), bx + bw), min(max(y, by), by + bh)
                        dx, dy = x - qx, y - qy
                        d2 = dx * dx + dy * dy
                        if d2 < r * r and (hit is None or d2 < hit[0]):
                            hit = (d2, i, j, dx, dy)
                if hit:
                    _, i, j, dx, dy = hit
                    d = math.hypot(dx, dy)
                    if d < 1e-6:
                        nx, ny = (0.0, 1.0) if vy < 0 else (0.0, -1.0)
                    else:
                        nx, ny = dx / d, dy / d
                    vn = vx * nx + vy * ny
                    if vn < 0:
                        vx -= 2 * vn * nx
                        vy -= 2 * vn * ny
                    alive[i][j] = False
                    left -= 1
                    v = min(VMAX, v * cfg.grow)
                    # never get stuck going (almost) straight sideways or up-down
                    ux, uy = vx / math.hypot(vx, vy), vy / math.hypot(vx, vy)
                    if abs(uy) < 0.25:
                        uy = math.copysign(0.25, uy or 1.0)
                        ux = math.copysign(math.sqrt(1 - uy * uy), ux or 1.0)
                    elif abs(ux) < 0.25:
                        ux = math.copysign(0.25, ux or 1.0)
                        uy = math.copysign(math.sqrt(1 - ux * ux), uy or 1.0)
                    vx, vy = v * ux, v * uy
                    hits.append(tt)
                    breaks.append((i, j, tt))
                    pulse = 1.0
                    if left == 0:
                        t_end = tt
                        break
            trail.append((x, y))
            trail = trail[-8:]
        t += DT
        pulse = max(0.0, pulse - DT * 6)
        if record:
            frames.append(dict(t=t, ball=(x, y, r), v=v, left=left, n_breaks=len(breaks), pulse=pulse,
                               trail=list(trail), t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, walls=walls, breaks=breaks, t_end=t_end,
                bricks=cfg.rows * COLS, v_end=v)


def is_good(res):
    return res["t_end"] is not None and 16 <= res["t_end"] <= 28


_BR = {}


def prepare(res, cfg):
    _BR[cfg.seed] = res["breaks"]


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    ctx.set_source_rgba(1, 1, 1, 0.85)
    ctx.set_line_width(4)
    ctx.rectangle(X0 - 3, Y0 - 3, SIZE + 6, SIZE + 6)
    ctx.stroke()
    breaks = _BR.get(cfg.seed, [])
    gone = {(i, j): bt for i, j, bt in breaks[:fr["n_breaks"]]}
    for i in range(cfg.rows):
        col = fx.hsv(cfg.h0 + i / cfg.rows * 0.85, 0.72, 1.0)
        for j in range(COLS):
            bx, by, bw, bh = brick_rect(i, j)
            if (i, j) in gone:
                k = (t - gone[(i, j)]) / 0.35
                if k < 1:                       # quick shatter: the brick puffs out and fades
                    s = 1 + 0.6 * k
                    ctx.set_source_rgba(*col, 0.7 * (1 - k))
                    ctx.rectangle(bx + bw / 2 - bw * s / 2, by + bh / 2 - bh * s / 2, bw * s, bh * s)
                    ctx.fill()
                continue
            ctx.set_source_rgb(*col)
            ctx.rectangle(bx, by, bw, bh)
            ctx.fill()
            ctx.set_source_rgba(1, 1, 1, 0.25)
            ctx.rectangle(bx, by, bw, 5)
            ctx.fill()
    x, y, r = fr["ball"]
    tr = fr["trail"]
    for i in range(1, len(tr)):
        ctx.set_line_width(r * 1.7 * i / len(tr))
        ctx.set_source_rgba(1, 1, 1, 0.35 * i / len(tr))
        ctx.move_to(*tr[i - 1])
        ctx.line_to(*tr[i])
        ctx.stroke()
    fx.ball(ctx, x, y, r, (1, 1, 1), fr["pulse"])
    text(ctx, f"Speed: {fr['v']:,.0f} px/s", 540, 1525, 58, fx.GOLD, 0.95)
    text(ctx, f"Bricks left: {fr['left']}", 540, 1592, 44, (1, 1, 1), 0.85)
    fx.music_line(ctx, y=1652)
    if fr["t_end"] is not None:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.4, "ALL BRICKS GONE!", fx.GOLD,
                  f"{fr['v'] / cfg.v0:.0f}× faster than the start", dim=0.35)


AUDIO_MIN_GAP = 0.07


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    out += [(t, 1400.0, "click") for t in res["walls"]]
    if res["t_end"] is not None:
        out.append((res["t_end"], 523.25, "shatter"))
        out.append((res["t_end"] + 0.12, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="breakout", colors=[], melody=cfg.melody_name, n_final=res["bricks"],
                n_balls=res["bricks"], speedup=round(res["v_end"] / cfg.v0))
