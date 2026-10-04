"""
"Growing ball": a ball bounces inside a circle and grows a little on every bounce, so the
bounces get faster and faster (and the melody speeds up) until the ball fills the circle.
Hook: guess how many bounces it takes.
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 10
CX, CY, R = 540, 1000, 430
RING_T = 12
G = 1000.0
VMIN, VMAX = 900.0, 1500.0
MAX_T = 34.0
END_HOLD = 2.6
FULL_GAP = 7.0      # "full" when this little room is left

HOOKS = [
    ("WILL IT FILL", "THE CIRCLE?"),
    ("GUESS THE", "BOUNCE COUNT"),
    ("HOW MANY BOUNCES", "TO FILL IT?"),
    ("IT GROWS", "EVERY BOUNCE"),
]
SUBS = ["Comment your guess before it ends", "Most people guess too low",
        "Lock in your number now", "Wait for the last second"]


@dataclass
class Config:
    seed: int
    r0: float
    grow: float
    h0: float
    ring_h: float
    melody_name: str
    melody: list
    hook: tuple
    sub: str
    bg: tuple


def make_config(seed):
    rng = random.Random(seed * 4241 + 11)
    mel = rng.choice(list(melodies.MELODIES))
    return Config(seed, rng.uniform(16, 22), rng.uniform(5.2, 7.2), rng.random(), rng.random(),
                  mel, melodies.MELODIES[mel], rng.choice(HOOKS), rng.choice(SUBS),
                  rng.choice(fx.BGS))


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    a = rng.uniform(0, 2 * math.pi)
    v = rng.uniform(1000, 1300)
    x, y, r = CX + rng.uniform(-40, 40), CY - 100, cfg.r0
    vx, vy = v * math.cos(a), v * math.sin(a)
    inner = R - RING_T / 2
    t, t_end = 0.0, None
    events, frames, stamps = [], [], []
    bounces, pulse = 0, 0.0

    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            for s in range(SUB):
                h = DT / SUB
                tt = t + s * h
                vy += G * h
                x += vx * h
                y += vy * h
                dx, dy = x - CX, y - CY
                d = math.hypot(dx, dy) or 1e-6
                if d + r >= inner:
                    nx, ny = dx / d, dy / d
                    vn = vx * nx + vy * ny
                    if vn > 0:
                        vx -= 2 * vn * nx
                        vy -= 2 * vn * ny
                        kick = rng.uniform(-120, 120)
                        vx += -ny * kick
                        vy += nx * kick
                        spd = math.hypot(vx, vy)
                        if spd < VMIN:
                            vx, vy = vx / spd * VMIN, vy / spd * VMIN
                        elif spd > VMAX:
                            vx, vy = vx / spd * VMAX, vy / spd * VMAX
                        r = min(inner - FULL_GAP, r + cfg.grow)
                        bounces += 1
                        pulse = 1.0
                        events.append((tt, "bounce", bounces))
                        stamps.append((x, y, r, fx.hsv(cfg.h0 + bounces * 0.035, 0.7, 1.0), tt))
                    pen = d + r - inner
                    x -= nx * pen
                    y -= ny * pen
                    if r >= inner - FULL_GAP - 0.01:
                        t_end = tt
                        events.append((tt, "win", None))
                        x, y = CX, CY
                        break
        t += DT
        pulse = max(0.0, pulse - DT * 5)
        stamps = [st for st in stamps if t - st[4] < 1.2][-40:]
        if record:
            frames.append(dict(t=t, ball=(x, y, r), pulse=pulse, stamps=list(stamps),
                               bounces=bounces, t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, events=events, t_end=t_end, bounces=bounces)


def is_good(res):
    return res["t_end"] is not None and 15 <= res["t_end"] <= 28


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.background(ctx, cfg.bg, CX, CY)
    fx.hook(ctx, t, *cfg.hook, cfg.sub)
    full = fr["t_end"] is not None
    ring_col = fx.hsv(cfg.ring_h + t * 0.05, 0.55, 1.0)
    if not full or t - fr["t_end"] < 0.05:
        fx.glow_arc(ctx, CX, CY, R, 0, 2 * math.pi, ring_col, RING_T)
    else:
        fx.ring_shatter(ctx, t, (fr["t_end"], CX, CY, R, ring_col, cfg.seed))

    # fading outlines left at each bounce
    for (sx, sy, sr, col, st) in fr["stamps"]:
        k = (t - st) / 1.2
        ctx.set_line_width(4)
        ctx.set_source_rgba(*col, 0.55 * (1 - k))
        ctx.new_path()
        ctx.arc(sx, sy, sr, 0, 2 * math.pi)
        ctx.stroke()

    x, y, r = fr["ball"]
    col = fx.hsv(cfg.h0 + fr["bounces"] * 0.035, 0.7, 1.0)
    fx.ball(ctx, x, y, r, col, fr["pulse"])
    inner = R - RING_T / 2
    pct = min(100, round(100 * (r / (inner - FULL_GAP)) ** 2))
    text(ctx, f"{min(t, fr['t_end'] or t):05.2f}s", 540, 500, 48, (1, 1, 1), 0.85)
    fx.pills(ctx, [(f"BOUNCES  {fr['bounces']}", col, False), (f"SIZE  {pct}%", ring_col, False)],
             y0=1500)
    if full:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.15, f"FULL IN {fr['bounces']} BOUNCES!", fx.GOLD,
                  "How close was your guess?")


def audio_events(res, cfg):
    out = []
    for t, kind, n in res["events"]:
        if kind == "bounce":
            out.append((t, note_freq(cfg.melody[(n - 1) % len(cfg.melody)]), "pluck"))
        else:
            out.append((t, 523.25, "shatter"))
            out.append((t + 0.12, 523.25, "win"))
    return out


AUDIO_MIN_GAP = 0.07


def metadata_facts(res, cfg):
    return dict(template="grow", bounces=res["bounces"], t_full=round(res["t_end"], 2),
                colors=[], melody=cfg.melody_name)
