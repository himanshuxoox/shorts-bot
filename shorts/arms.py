"""
"Arms": a ball flies around inside a cage of swinging arms (straight bars tangent to a circle).
Every bounce adds one more arm and makes the ball a bit faster, so the cage goes triangle ->
square -> … -> a 200-sided glowing ring, with its Greek name on screen (DIHECTAKAIDODECAGON).
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, text, note_freq
from . import fx, melodies, refkit

CX, CY = 540, 1000
A = 350.0                 # distance of every arm from the centre
EXT = 250.0               # arms are long bars: they cross into a star / sunburst
VMAX = 9000.0
MAX_T = 32.0
END_HOLD = 2.8
CAPS = ["Every bounce adds a SWINGING arm | How many can it take?",
        "Every bounce adds an ARM | and makes the ball FASTER",
        "One more ARM every bounce | Watch it turn into a RING"]


@dataclass
class Config:
    seed: int
    target: int
    v0: float
    grow: float
    swing: float
    wsw: float
    spin: float
    h0: float
    r: float
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 6151 + 5)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.choice([100, 120, 144, 160, 180, 212]), rng.uniform(950, 1150),
                  rng.uniform(1.026, 1.034), rng.uniform(0.25, 0.45), rng.uniform(0.6, 0.9),
                  rng.choice([-1, 1]) * rng.uniform(0.15, 0.3), rng.random(), rng.uniform(18, 24),
                  mel, melodies.MELODIES[mel], rng.choice(CAPS))


def theta(cfg, t):
    return cfg.spin * t + cfg.swing * math.sin(cfg.wsw * t)


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    a = rng.uniform(0, 2 * math.pi)
    v = cfg.v0
    x, y = CX + rng.uniform(-60, 60), CY + rng.uniform(-60, 60)
    vx, vy = v * math.cos(a), v * math.sin(a)
    n, r = 4, cfg.r            # a triangle's corners would be off screen
    t, t_end = 0.0, None
    frames, hits, trail = [], [], []
    pulse = 0.0
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            sub = max(4, math.ceil(v * DT / 6))
            h = DT / sub
            for s in range(sub):
                tt = t + s * h
                x += vx * h
                y += vy * h
                th = theta(cfg, tt)
                step = 2 * math.pi / n
                k0 = round((math.atan2(y - CY, x - CX) - th) / step)
                best = None
                for k in (k0 - 1, k0, k0 + 1):
                    na = th + k * step
                    nx, ny = math.cos(na), math.sin(na)
                    pen = (x - CX) * nx + (y - CY) * ny + r - A
                    if pen > 0 and (best is None or pen > best[0]):
                        best = (pen, nx, ny)
                if best:
                    pen, nx, ny = best
                    x -= nx * pen
                    y -= ny * pen
                    vn = vx * nx + vy * ny
                    if vn > 0:
                        vx -= 2 * vn * nx
                        vy -= 2 * vn * ny
                        ang = math.atan2(vy, vx) + rng.uniform(-0.12, 0.12)
                        v = min(VMAX, v * cfg.grow)
                        vx, vy = v * math.cos(ang), v * math.sin(ang)
                        hits.append(tt)
                        pulse = 1.0
                        n += 1
                        if n >= cfg.target:
                            t_end = tt
                            break
                if s % max(1, sub // 4) == 0:
                    trail.append((x, y))
        t += DT
        trail = trail[-14:]
        pulse = max(0.0, pulse - DT * 6)
        if record:
            frames.append(dict(t=t, ball=(x, y, r), n=n, v=v, trail=list(trail), pulse=pulse, t_end=t_end,
                               th=theta(cfg, min(t, t_end or t))))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, t_end=t_end, bounces=len(hits), n=n)


def is_good(res):
    return res["t_end"] is not None and 16 <= res["t_end"] <= 28


def draw(ctx, fr, cfg):
    t, n, th = fr["t"], fr["n"], fr["th"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    done = fr["t_end"] is not None
    half = min(A * math.tan(math.pi / n) + EXT, 385.0)      # ends stay inside r = 520
    lw = max(1.4, min(7.0, 700 / n))
    a1 = min(0.95, 0.25 + 30.0 / n)
    for w, al in ((lw * 4, 0.10 * a1), (lw, a1)):
        ctx.set_line_width(w)
        for k in range(n):
            na = th + 2 * math.pi * k / n
            c, s = math.cos(na), math.sin(na)
            px, py = CX + A * c, CY + A * s
            ctx.set_source_rgba(*fx.hsv(cfg.h0 + k / n, 0.6, 1.0), al)
            ctx.move_to(px - s * half, py + c * half)
            ctx.line_to(px + s * half, py - c * half)
            ctx.stroke()
    x, y, r = fr["ball"]
    tr = fr["trail"]
    for i in range(1, len(tr)):
        ctx.set_line_width(r * 1.6 * i / len(tr))
        ctx.set_source_rgba(1, 1, 1, 0.35 * i / len(tr))
        ctx.move_to(*tr[i - 1])
        ctx.line_to(*tr[i])
        ctx.stroke()
    fx.ball(ctx, x, y, r, (1, 1, 1), fr["pulse"])
    name = refkit.polygon_name(n)
    text(ctx, name, 540, 1520, 64 if len(name) < 14 else 46 if len(name) < 20 else 40, fx.GOLD, 0.95)
    text(ctx, f"Arms: {n}      Speed: {fr['v']:,.0f} px/s", 540, 1590, 42, (1, 1, 1), 0.85)
    fx.music_line(ctx, y=1652)
    if done:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.6, f"{n} ARMS!", fx.GOLD, "Did you see the ring coming?", dim=0.35)


AUDIO_MIN_GAP = 0.075


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"] + 0.02, 523.25, "shatter"))
        out.append((res["t_end"] + 0.14, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="arms", bounces=res["bounces"], colors=[], melody=cfg.melody_name,
                n_final=res["n"], name=refkit.polygon_name(res["n"]).title())
