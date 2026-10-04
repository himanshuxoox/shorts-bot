"""
"Multi-ring escape": one ball starts inside 6-9 nested, spinning rings. Each ring has a gap;
when the ball slips through, that ring shatters. Every bounce plays the next note of a
public-domain melody. Hook: guess how long it takes to break every ring.
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, text, text_fit, note_freq
from . import fx, melodies

SUB = 8
CX, CY = 540, 1000
R_IN, R_OUT = 125, 450
RING_T = 12
BALL_R = 24
G = 1000.0
VMIN, VMAX = 900.0, 1650.0
MAX_T = 34.0
END_HOLD = 2.6

HOOKS = [
    ("CAN IT ESCAPE", "ALL {n} RINGS?"),
    ("HOW LONG TO", "BREAK {n} RINGS?"),
    ("GUESS THE TIME", "TO ESCAPE"),
    ("{n} RINGS.", "ONE BALL."),
]
SUBS = ["Guess the time in the comments", "Most people guess too low",
        "Comment your guess before it ends", "Watch the last ring"]


@dataclass
class Config:
    seed: int
    n: int
    radii: list
    gaps: list
    spins: list
    hues: list
    color: tuple
    color_name: str
    melody_name: str
    melody: list
    hook: tuple
    sub: str
    bg: tuple


def make_config(seed):
    rng = random.Random(seed * 6271 + 3)
    n = rng.choice([6, 7, 7, 8, 8, 9])
    radii = [R_IN + (R_OUT - R_IN) * i / (n - 1) for i in range(n)]
    base = rng.uniform(46, 54)
    gaps = [math.radians(base + rng.uniform(-3, 3) - 4 * i / (n - 1)) for i in range(n)]
    direction = rng.choice([-1, 1])
    sp = rng.uniform(0.8, 1.15)
    spins = [direction * (-1) ** i * sp * (1.25 - 0.45 * i / (n - 1)) for i in range(n)]
    h0 = rng.random()
    hues = [fx.hsv(h0 + 0.8 * i / n, 0.65, 1.0) for i in range(n)]
    cname = rng.choice(list(fx.PALETTE))
    mel = rng.choice(list(melodies.MELODIES))
    l1, l2 = rng.choice(HOOKS)
    return Config(seed, n, radii, gaps, spins, hues, fx.PALETTE[cname], cname, mel,
                  melodies.MELODIES[mel], (l1.format(n=n), l2.format(n=n)), rng.choice(SUBS),
                  rng.choice(fx.BGS))


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    a = rng.uniform(0, 2 * math.pi)
    v = rng.uniform(1100, 1400)
    x, y = CX + rng.uniform(-20, 20), CY + rng.uniform(-20, 20)
    vx, vy = v * math.cos(a), v * math.sin(a)
    ang = [rng.uniform(0, 2 * math.pi) for _ in range(cfg.n)]
    gaps = list(cfg.gaps)
    k, passing = 0, False
    t, t_end = 0.0, None
    events, frames, breaks, shatters, trail = [], [], [], [], []
    pulse = 0.0
    bounces = 0

    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            for i in range(cfg.n):
                ang[i] = (ang[i] + cfg.spins[i] * h) % (2 * math.pi)
            if tt > 25:  # guaranteed ending: remaining gaps slowly open
                for i in range(k, cfg.n):
                    gaps[i] = min(cfg.gaps[i] + math.radians(5) * (tt - 25), math.radians(150))
            vy += G * h
            x += vx * h
            y += vy * h
            if t_end is not None:
                continue
            R = cfg.radii[k]
            inner = R - RING_T / 2
            dx, dy = x - CX, y - CY
            d = math.hypot(dx, dy)
            if passing:
                if d - BALL_R > R + RING_T:
                    passing = False
                    breaks.append(tt)
                    shatters.append((tt, CX, CY, R, cfg.hues[k], cfg.seed * 31 + k))
                    events.append((tt, "break", k))
                    k += 1
                    if k == cfg.n:
                        t_end = tt
                        events.append((tt, "win", None))
                continue
            if d + BALL_R >= inner:
                th = math.atan2(dy, dx)
                rel = (th - ang[k] + math.pi) % (2 * math.pi) - math.pi
                if abs(rel) < gaps[k] / 2 - math.asin(min(1.0, BALL_R / R)):
                    passing = True
                    continue
                nx, ny = dx / d, dy / d
                vn = vx * nx + vy * ny
                if vn > 0:
                    vx -= 2 * vn * nx
                    vy -= 2 * vn * ny
                    kick = rng.uniform(-140, 140)
                    vx += -ny * kick
                    vy += nx * kick
                    spd = math.hypot(vx, vy)
                    if spd < VMIN:
                        vx, vy = vx / spd * VMIN, vy / spd * VMIN
                    elif spd > VMAX:
                        vx, vy = vx / spd * VMAX, vy / spd * VMAX
                    bounces += 1
                    pulse = 1.0
                    events.append((tt, "bounce", k))
                pen = d + BALL_R - inner
                x -= nx * pen
                y -= ny * pen
        t += DT
        trail.append((x, y, BALL_R))
        trail = trail[-14:]
        pulse = max(0.0, pulse - DT * 5)
        if record:
            frames.append(dict(t=t, k=k, ang=list(ang), gaps=list(gaps), ball=(x, y),
                               trail=list(trail), pulse=pulse, shatters=list(shatters[-4:]),
                               t_end=t_end, bounces=bounces))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, events=events, t_end=t_end, breaks=breaks, bounces=bounces)


def is_good(res):
    if res["t_end"] is None or not (15 <= res["t_end"] <= 28):
        return False
    b = [0.0] + res["breaks"]
    steps = [b2 - b1 for b1, b2 in zip(b, b[1:])]
    return steps[0] >= 0.8 and max(steps) < 8.5


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.background(ctx, cfg.bg, CX, CY)
    fx.hook(ctx, t, *cfg.hook, cfg.sub)
    for i in range(fr["k"], cfg.n):
        a0 = fr["ang"][i] + fr["gaps"][i] / 2
        a1 = fr["ang"][i] - fr["gaps"][i] / 2 + 2 * math.pi
        fx.glow_arc(ctx, CX, CY, cfg.radii[i], a0, a1, cfg.hues[i], RING_T,
                    1.0 if i == fr["k"] else 0.55)
    for sh in fr["shatters"]:
        fx.ring_shatter(ctx, t, sh)
    x, y = fr["ball"]
    fx.ball(ctx, x, y, BALL_R, cfg.color, fr["pulse"], fr["trail"])

    secs = fr["t_end"] if fr["t_end"] is not None else t
    text(ctx, f"{secs:05.2f}s", 540, 500, 48, (1, 1, 1), 0.85)
    left = cfg.n - fr["k"]
    fx.pills(ctx, [(f"RINGS LEFT  {left}", cfg.hues[min(fr['k'], cfg.n - 1)], False),
                   (f"BOUNCES  {fr['bounces']}", cfg.color, False)], y0=1510)
    if fr["t_end"] is not None:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"], f"ESCAPED IN {fr['t_end']:.1f}s!", fx.GOLD,
                  "How close was your guess?")


def audio_events(res, cfg):
    out, mi = [], 0
    for t, kind, _ in res["events"]:
        if kind == "bounce":
            out.append((t, note_freq(cfg.melody[mi % len(cfg.melody)]), "pluck"))
            mi += 1
        elif kind == "break":
            out.append((t, 523.25 * 2 ** (min(_, 12) / 12), "shatter"))
        else:
            out.append((t, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="rings", n_rings=cfg.n, color=cfg.color_name, colors=[cfg.color_name],
                t_escape=round(res["t_end"], 2), bounces=res["bounces"], melody=cfg.melody_name)
