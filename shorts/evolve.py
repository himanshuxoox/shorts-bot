"""
"Evolve": a white ball bounces in a circle and grows on every bounce. Each bounce leaves a
permanent rainbow disc behind it, so the circle slowly fills with a layered rainbow
sculpture until the ball fills the whole circle. Notes follow a famous public-domain tune.
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 10
CX, CY, R = 540, 960, 455
G = 1000.0
VMIN, VMAX = 950.0, 1500.0
MAX_T = 34.0
END_HOLD = 2.8
FULL_GAP = 6.0

TITLES = ["With every bounce, the ball evolves !...", "Every bounce makes it bigger…",
          "Will the ball fill the circle?", "Guess how many bounces to fill it"]


@dataclass
class Config:
    seed: int
    r0: float
    grow: float
    h0: float
    hstep: float
    melody_name: str
    melody: list
    title: str


def make_config(seed):
    rng = random.Random(seed * 9133 + 23)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(14, 20), rng.uniform(5.0, 7.0), rng.random(),
                  rng.choice([0.06, 0.075, 0.09, -0.075]), mel, melodies.MELODIES[mel],
                  rng.choice(TITLES))


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    a = rng.uniform(0, 2 * math.pi)
    v = rng.uniform(1000, 1300)
    x, y, r = CX + rng.uniform(-40, 40), CY - 120, cfg.r0
    vx, vy = v * math.cos(a), v * math.sin(a)
    t, t_end = 0.0, None
    frames, stamps, hits = [], [], []
    bounces = 0
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
                if d + r >= R:
                    nx, ny = dx / d, dy / d
                    vn = vx * nx + vy * ny
                    if vn > 0:
                        vx -= 2 * vn * nx
                        vy -= 2 * vn * ny
                        kick = rng.uniform(-110, 110)
                        vx += -ny * kick
                        vy += nx * kick
                        spd = math.hypot(vx, vy)
                        k = min(max(spd, VMIN), VMAX) / spd
                        vx, vy = vx * k, vy * k
                        r = min(R - FULL_GAP, r + cfg.grow)
                        bounces += 1
                        hits.append(tt)
                    pen = d + r - R
                    x -= nx * pen
                    y -= ny * pen
                    if r >= R - FULL_GAP - 0.01:
                        t_end = tt
                        x, y = CX, CY
                        break
        t += DT
        if t_end is None and r < 0.62 * R:     # the last huge stamps would cover the whole sculpture
            stamps.append((x, y, r, fx.hsv(cfg.h0 + bounces * cfg.hstep, 0.8, 1.0)))
        if record:
            frames.append(dict(t=t, ball=(x, y, r), n_stamps=len(stamps), bounces=bounces,
                               t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, stamps=stamps, hits=hits, t_end=t_end, bounces=bounces)


def is_good(res):
    return res["t_end"] is not None and 15 <= res["t_end"] <= 27


_STAMPS = {}
_LAYER = {}


def _layer(cfg, n):
    """Stamps are permanent, so they are drawn once onto an offscreen layer and reused."""
    import cairo
    from .common import W, H
    surf, done = _LAYER.get(cfg.seed, (None, 0))
    if surf is None or n < done:
        surf, done = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H), 0
    ctx = cairo.Context(surf)
    ctx.new_path()
    ctx.arc(CX, CY, R - 2, 0, 2 * math.pi)
    ctx.clip()
    for (sx, sy, sr, col) in _STAMPS[cfg.seed][done:n]:
        ctx.new_path()
        ctx.arc(sx, sy, sr, 0, 2 * math.pi)
        ctx.set_source_rgb(*col)
        ctx.fill_preserve()
        ctx.set_source_rgba(0, 0, 0, 0.45)
        ctx.set_line_width(1.6)
        ctx.stroke()
    surf.flush()
    _LAYER[cfg.seed] = (surf, n)
    return surf


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.neon_title(ctx, t, cfg.title)
    ctx.set_line_width(4)
    ctx.set_source_rgba(1, 1, 1, 0.9)
    ctx.new_path()
    ctx.arc(CX, CY, R, 0, 2 * math.pi)
    ctx.stroke()
    ctx.set_source_surface(_layer(cfg, fr["n_stamps"]), 0, 0)
    ctx.paint()
    ctx.save()
    ctx.new_path()
    ctx.arc(CX, CY, R - 2, 0, 2 * math.pi)
    ctx.clip()
    x, y, r = fr["ball"]
    a = 1.0 if fr["t_end"] is None else max(0.0, 1 - (t - fr["t_end"]) / 0.6)   # reveal the art
    if a > 0:
        ctx.new_path()
        ctx.arc(x, y, r, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, a)
        ctx.fill_preserve()
        ctx.set_source_rgba(0, 0, 0, 0.6 * a)
        ctx.set_line_width(3)
        ctx.stroke()
    ctx.restore()
    text(ctx, f"{fr['bounces']} BOUNCES", 540, 1500, 56, (1, 1, 1), 0.9)
    fx.music_line(ctx)
    if fr["t_end"] is not None:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.9, f"FULL IN {fr['bounces']} BOUNCES!", fx.GOLD,
                  "How close was your guess?", dim=0.3)


def prepare(res, cfg):
    """Called once before drawing: share the stamp list instead of copying it per frame."""
    _STAMPS[cfg.seed] = res["stamps"]
    _LAYER.pop(cfg.seed, None)


AUDIO_MIN_GAP = 0.075


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck")
           for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"], 523.25, "shatter"))
        out.append((res["t_end"] + 0.12, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="evolve", bounces=res["bounces"], colors=[],
                t_full=round(res["t_end"], 2), melody=cfg.melody_name)
