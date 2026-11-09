"""
"Sides": a ball bounces inside a triangle and every bounce adds a SIDE. Triangle, square,
pentagon … 48 sides, then it becomes a CIRCLE. Each bounce leaves a thin chord from the last
bounce point, so a web of lines builds up inside. Notes follow a famous public-domain tune.
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, text, note_freq
from . import fx, melodies, refkit

SUB = 10
CX, CY, R = 540, 1000, 440          # circumradius of the polygon
G = 1100.0
VMIN, VMAX = 1050.0, 1500.0
MAX_T = 34.0
END_HOLD = 2.8
TARGET = 48
CAPS = ["Every bounce adds a SIDE | Can the triangle become a CIRCLE?",
        "Every bounce adds a SIDE | 3 → 48 → CIRCLE?",
        "One more SIDE every bounce | When does it become a CIRCLE?"]


@dataclass
class Config:
    seed: int
    r: float
    h0: float
    rot: float
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 7717 + 3)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(42, 56), rng.random(), rng.uniform(0, 2 * math.pi), mel,
                  melodies.MELODIES[mel], rng.choice(CAPS))


def apothem(n):
    return R * math.cos(math.pi / n)


def poly_pts(n, rot):
    return [(CX + R * math.cos(rot + 2 * math.pi * k / n - math.pi / 2),
             CY + R * math.sin(rot + 2 * math.pi * k / n - math.pi / 2)) for k in range(n)]


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    a = rng.uniform(0, 2 * math.pi)
    v = rng.uniform(1100, 1300)
    x, y = CX + rng.uniform(-50, 50), CY - 60
    vx, vy = v * math.cos(a), v * math.sin(a)
    n, r = 3, cfg.r
    t, t_end = 0.0, None
    frames, hits, chords = [], [], []
    last_hit = None
    pulse = 0.0
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            for s in range(SUB):
                h = DT / SUB
                tt = t + s * h
                vy += G * h
                x += vx * h
                y += vy * h
                # nearest edge = sector the ball is in (plus its neighbours)
                ang = math.atan2(y - CY, x - CX) - (cfg.rot - math.pi / 2)
                step = 2 * math.pi / n
                k0 = math.floor(ang / step)
                ap = apothem(n)
                best = None
                for k in (k0 - 1, k0, k0 + 1):
                    na = cfg.rot - math.pi / 2 + (k + 0.5) * step
                    nx, ny = math.cos(na), math.sin(na)
                    d = (x - CX) * nx + (y - CY) * ny
                    pen = d + r - ap
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
                        kick = rng.uniform(-140, 140)
                        vx += -ny * kick
                        vy += nx * kick
                        spd = math.hypot(vx, vy)
                        q = min(max(spd, VMIN), VMAX) / spd
                        vx, vy = vx * q, vy * q
                        hp = (x + nx * r, y + ny * r)
                        if last_hit:
                            chords.append((last_hit, hp, n))
                        last_hit = hp
                        hits.append(tt)
                        pulse = 1.0
                        n += 1
                        if n >= TARGET:
                            t_end = tt
                            break
        t += DT
        pulse = max(0.0, pulse - DT * 5)
        if record:
            frames.append(dict(t=t, ball=(x, y, r), n=n, n_chords=len(chords), pulse=pulse, t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, chords=chords, t_end=t_end, bounces=len(hits))


def is_good(res):
    return res["t_end"] is not None and 16 <= res["t_end"] <= 28


_CH = {}


def prepare(res, cfg):
    _CH[cfg.seed] = res["chords"]


def draw(ctx, fr, cfg):
    t, n = fr["t"], fr["n"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    done = fr["t_end"] is not None
    col = fx.hsv(cfg.h0 + n * 0.012, 0.65, 1.0)
    # chord web
    ctx.set_line_width(2)
    for (p, q, k) in _CH.get(cfg.seed, [])[:fr["n_chords"]]:
        c = fx.hsv(cfg.h0 + k * 0.02, 0.7, 1.0)
        ctx.set_source_rgba(*c, 0.33)
        ctx.move_to(*p)
        ctx.line_to(*q)
        ctx.stroke()
    # the polygon (a circle at the end)
    if done:
        k = min(1.0, (t - fr["t_end"]) / 0.5)
        fx.glow_arc(ctx, CX, CY, R, 0, 2 * math.pi, fx.GOLD, 10 + 6 * (1 - k))
    else:
        pts = poly_pts(n, cfg.rot)
        for w, a in ((22, 0.12), (12, 0.25), (6, 1.0)):
            ctx.set_line_width(w)
            ctx.set_source_rgba(*col, a)
            ctx.move_to(*pts[0])
            for p in pts[1:]:
                ctx.line_to(*p)
            ctx.close_path()
            ctx.stroke()
        if n <= 30:
            for (px, py) in pts:
                ctx.new_path()
                ctx.arc(px, py, 9, 0, 2 * math.pi)
                ctx.set_source_rgb(0, 0, 0)
                ctx.fill_preserve()
                ctx.set_source_rgb(*col)
                ctx.set_line_width(4)
                ctx.stroke()
    x, y, r = fr["ball"]
    fx.ball(ctx, x, y, r, fx.hsv(cfg.h0 + 0.5, 0.6, 1.0), fr["pulse"])
    name = "CIRCLE" if done else refkit.polygon_name(n)
    text(ctx, name, 540, 1520, 64 if len(name) < 14 else 50, fx.GOLD, 0.95)
    text(ctx, f"Sides: {min(n, TARGET)} / {TARGET}", 540, 1590, 46, (1, 1, 1), 0.85)
    fx.music_line(ctx, y=1652)
    if done:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.6, "IT'S A CIRCLE!", fx.GOLD, f"{TARGET - 3} bounces later", dim=0.35)


AUDIO_MIN_GAP = 0.07


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"] + 0.02, 523.25, "shatter"))
        out.append((res["t_end"] + 0.14, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="sides", bounces=res["bounces"], colors=[], melody=cfg.melody_name,
                n_final=TARGET, t_full=round(res["t_end"] or 0, 2))
