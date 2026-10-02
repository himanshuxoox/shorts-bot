"""
"Ball Escape" template — neon balls bounce inside a rotating ring with a gap.
Every bounce plays the next note of a public-domain melody and grows the ball.
First ball through the gap wins.

Everything (colours, ball count, melody, hook text, spin) is derived from the
seed, so every seed is a different, reproducible video.
"""
import math, random
from dataclasses import dataclass, field

import cairo

from .common import W, H, FPS, DT, text_fit, text, rounded, note_freq
from . import melodies

SUB = 8
CX, CY, R = 540, 1010, 400
RING_T = 14
G = 1100.0
VMIN, VMAX = 950.0, 1800.0
MAX_T = 50.0
END_HOLD = 3.0

PALETTE = {
    "RED": (1.0, 0.23, 0.36), "BLUE": (0.22, 0.62, 1.0), "GREEN": (0.2, 0.95, 0.5),
    "YELLOW": (1.0, 0.85, 0.2), "PURPLE": (0.72, 0.4, 1.0), "ORANGE": (1.0, 0.55, 0.15),
    "PINK": (1.0, 0.45, 0.8), "CYAN": (0.2, 0.95, 0.95),
}

HOOKS = [
    ("WHICH BALL", "ESCAPES FIRST?"),
    ("WHO GETS", "OUT FIRST?"),
    ("PICK A COLOR", "BEFORE IT ENDS"),
    ("ONLY ONE", "ESCAPES"),
    ("WHO WINS", "THIS RACE?"),
]
SUBS = [
    "Comment your pick before it ends",
    "Lock in your answer in the comments",
    "Most people pick wrong",
    "Watch till the end",
]


@dataclass
class Config:
    seed: int
    names: list
    melody_name: str
    melody: list
    hook: tuple
    sub: str
    spin: float
    gap0: float
    grow: float
    rmax: float
    r0: float
    bg_hue: tuple
    ring_hue: tuple


def make_config(seed: int) -> Config:
    rng = random.Random(seed * 7919 + 13)
    n = rng.choices([2, 3, 4], weights=[60, 25, 15])[0]
    names = rng.sample(list(PALETTE), n)
    mel_name = rng.choice(list(melodies.MELODIES))
    # more balls -> slightly smaller gap so the race lasts long enough
    gap = math.radians({2: 18, 3: 13.5, 4: 14}[n] + rng.uniform(-0.7, 0.7))
    bg = rng.choice([(0.07, 0.05, 0.16), (0.03, 0.08, 0.14), (0.12, 0.04, 0.1), (0.04, 0.04, 0.06)])
    ring = rng.choice([(0.75, 0.45, 1.0), (0.3, 0.9, 1.0), (1.0, 0.5, 0.75), (1.0, 0.8, 0.35)])
    return Config(
        seed=seed, names=names, melody_name=mel_name, melody=melodies.MELODIES[mel_name],
        hook=rng.choice(HOOKS), sub=rng.choice(SUBS),
        spin=rng.uniform(0.65, 1.05) * rng.choice([-1, 1]),
        gap0=gap, grow=rng.uniform(0.8, 1.2), rmax=rng.uniform(50, 58) if n == 2 else rng.uniform(40, 44),
        r0={2: 30, 3: 27, 4: 25}[n], bg_hue=bg, ring_hue=ring)


class Ball:
    def __init__(self, x, y, vx, vy, r, name):
        self.x, self.y, self.vx, self.vy, self.r = x, y, vx, vy, r
        self.name, self.color = name, PALETTE[name]
        self.bounces, self.passing, self.trail, self.pulse = 0, False, [], 0.0


def simulate(cfg: Config, record=False):
    rng = random.Random(cfg.seed)
    n = len(cfg.names)
    balls = []
    for i, name in enumerate(cfg.names):
        ang = rng.uniform(0, 2 * math.pi)
        sp = rng.uniform(700, 1100)
        px = CX + (i - (n - 1) / 2) * 120
        balls.append(Ball(px, CY - 120 + rng.uniform(-40, 40),
                          sp * math.cos(ang), sp * math.sin(ang), cfg.r0, name))
    ring_ang = rng.uniform(0, 2 * math.pi)
    gap = cfg.gap0
    t = 0.0
    events, frames, ripples = [], [], []
    winner, t_esc = None, None
    inner = R - RING_T / 2

    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if winner is None:
            for k in range(SUB):
                h = DT / SUB
                tt = t + k * h
                if tt > 34:  # guarantee an ending: gap slowly opens late in the video
                    gap = min(cfg.gap0 + math.radians(4) * (tt - 34), math.radians(120))
                ring_ang = (ring_ang + cfg.spin * h) % (2 * math.pi)
                for b in balls:
                    b.vy += G * h
                    b.x += b.vx * h
                    b.y += b.vy * h
                    dx, dy = b.x - CX, b.y - CY
                    d = math.hypot(dx, dy)
                    if b.passing:
                        if d - b.r > R + RING_T and winner is None:
                            winner, t_esc = b, tt
                            events.append((tt, "win", b.name))
                        continue
                    if d + b.r >= inner:
                        th = math.atan2(dy, dx)
                        rel = (th - ring_ang + math.pi) % (2 * math.pi) - math.pi
                        if abs(rel) < gap / 2 - math.asin(min(1.0, b.r / R)):
                            b.passing = True
                            continue
                        nx, ny = dx / d, dy / d
                        vn = b.vx * nx + b.vy * ny
                        if vn > 0:
                            b.vx -= 2 * vn * nx
                            b.vy -= 2 * vn * ny
                            kick = rng.uniform(-120, 120)
                            b.vx += -ny * kick
                            b.vy += nx * kick
                            sp = math.hypot(b.vx, b.vy)
                            if sp < VMIN:
                                b.vx, b.vy = b.vx / sp * VMIN, b.vy / sp * VMIN
                            elif sp > VMAX:
                                b.vx, b.vy = b.vx / sp * VMAX, b.vy / sp * VMAX
                            b.r = min(cfg.rmax, b.r + cfg.grow)
                            b.bounces += 1
                            b.pulse = 1.0
                            events.append((tt, "bounce", b.name))
                            ripples.append([CX + nx * inner, CY + ny * inner, tt, b.color])
                        pen = d + b.r - inner
                        b.x -= nx * pen
                        b.y -= ny * pen
                for i in range(n):
                    for j in range(i + 1, n):
                        a, c = balls[i], balls[j]
                        if a.passing or c.passing:
                            continue
                        dx, dy = c.x - a.x, c.y - a.y
                        d = math.hypot(dx, dy)
                        if 0 < d < a.r + c.r:
                            nx, ny = dx / d, dy / d
                            rv = (c.vx - a.vx) * nx + (c.vy - a.vy) * ny
                            if rv < 0:
                                a.vx += rv * nx; a.vy += rv * ny
                                c.vx -= rv * nx; c.vy -= rv * ny
                                events.append((tt, "clash", None))
                            ov = (a.r + c.r - d) / 2
                            a.x -= nx * ov; a.y -= ny * ov
                            c.x += nx * ov; c.y += ny * ov
            t += DT
        else:
            winner.vy += G * DT
            winner.x += winner.vx * DT
            winner.y += winner.vy * DT
            t += DT
            if t - t_esc > END_HOLD:
                break

        for b in balls:
            b.trail.append((b.x, b.y, b.r))
            b.trail = b.trail[-14:]
            b.pulse = max(0.0, b.pulse - DT * 5)
        ripples = [rp for rp in ripples if t - rp[2] < 0.45]

        if record:
            frames.append(dict(
                t=t, ring=ring_ang, gap=gap,
                balls=[(b.x, b.y, b.r, b.color, b.name, b.bounces, list(b.trail), b.pulse) for b in balls],
                ripples=[list(rp) for rp in ripples],
                winner=winner.name if winner else None,
                wcolor=winner.color if winner else None, t_esc=t_esc))
        if winner is None and t >= MAX_T:
            break

    return dict(frames=frames, events=events, winner=winner.name if winner else None,
                t_esc=t_esc, bounces={b.name: b.bounces for b in balls})


def is_good(res):
    """A 'good' video: ends between 22-36s and the race is close."""
    if not res["winner"] or not (22 <= res["t_esc"] <= 36):
        return False
    b = sorted(res["bounces"].values())
    return b[-1] - b[-2] <= max(3, int(0.10 * b[-1]))  # top two neck and neck


def draw(ctx, fr, cfg: Config):
    t = fr["t"]
    bg = cairo.RadialGradient(CX, CY, 50, CX, CY, 1300)
    bg.add_color_stop_rgb(0, *cfg.bg_hue)
    bg.add_color_stop_rgb(1, 0.0, 0.0, 0.02)
    ctx.set_source(bg)
    ctx.paint()

    text_fit(ctx, cfg.hook[0], 540, 250, 92, 960)
    text_fit(ctx, cfg.hook[1], 540, 350, 92, 960, (1.0, 0.85, 0.25))
    text(ctx, cfg.sub, 540, 420, 38, (1, 1, 1), 0.65, bold=False)

    a0 = fr["ring"] + fr["gap"] / 2
    a1 = fr["ring"] - fr["gap"] / 2 + 2 * math.pi
    for wdt, al in ((60, 0.05), (38, 0.08), (24, 0.15), (RING_T, 1.0)):
        ctx.set_line_width(wdt)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        col = cfg.ring_hue if al < 1 else tuple(min(1, c * 0.3 + 0.7) for c in cfg.ring_hue)
        ctx.set_source_rgba(*col, al)
        ctx.arc(CX, CY, R, a0, a1)
        ctx.stroke()

    for x, y, t0, col in fr["ripples"]:
        k = (t - t0) / 0.45
        ctx.set_line_width(6 * (1 - k) + 1)
        ctx.set_source_rgba(*col, 0.8 * (1 - k))
        ctx.arc(x, y, 10 + 90 * k, 0, 2 * math.pi)
        ctx.stroke()

    for (x, y, r, col, name, nb, trail, pulse) in fr["balls"]:
        for i, (tx, ty, tr) in enumerate(trail[:-1]):
            k = (i + 1) / len(trail)
            ctx.set_source_rgba(*col, 0.18 * k)
            ctx.arc(tx, ty, tr * (0.5 + 0.5 * k), 0, 2 * math.pi)
            ctx.fill()
        glow = cairo.RadialGradient(x, y, r * 0.6, x, y, r * (2.2 + pulse))
        glow.add_color_stop_rgba(0, *col, 0.55)
        glow.add_color_stop_rgba(1, *col, 0.0)
        ctx.set_source(glow)
        ctx.arc(x, y, r * (2.2 + pulse), 0, 2 * math.pi)
        ctx.fill()
        body = cairo.RadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r)
        body.add_color_stop_rgb(0, *(min(1, c + 0.45) for c in col))
        body.add_color_stop_rgb(1, *col)
        ctx.set_source(body)
        ctx.arc(x, y, r * (1 + 0.08 * pulse), 0, 2 * math.pi)
        ctx.fill()

    # scoreboard — layout adapts to 2/3/4 balls, kept above the Shorts bottom UI
    n = len(fr["balls"])
    cols = 2 if n in (2, 4) else 3
    pw, ph, gapx = (370, 100, 40) if cols == 2 else (290, 96, 25)
    x0 = 540 - (cols * pw + (cols - 1) * gapx) / 2
    for i, (x, y, r, col, name, nb, *_r) in enumerate(fr["balls"]):
        row, ci = divmod(i, cols)
        bx, by = x0 + ci * (pw + gapx), 1470 + row * (ph + 20)
        rounded(ctx, bx, by, pw, ph, ph / 2)
        ctx.set_source_rgba(*col, 0.18)
        ctx.fill_preserve()
        ctx.set_source_rgba(*col, 0.9)
        ctx.set_line_width(4)
        ctx.stroke()
        text_fit(ctx, f"{name}  {nb}", bx + pw / 2, by + ph / 2 + 18, 50, pw - 40)
    rows = (n + cols - 1) // cols
    text(ctx, "bounces", 540, 1470 + rows * (ph + 20) + 22, 30, (1, 1, 1), 0.5, bold=False)

    secs = fr["t_esc"] if fr["winner"] else t
    text(ctx, f"{secs:05.2f}s", 540, 540, 44, (1, 1, 1), 0.8)

    if fr["winner"]:
        k = min(1.0, (t - fr["t_esc"]) / 0.35)
        ctx.set_source_rgba(0, 0, 0, 0.55 * k)
        ctx.paint()
        s = 1.0 + 0.25 * (1 - k)
        ctx.save()
        ctx.translate(540, 980)
        ctx.scale(s, s)
        text_fit(ctx, f"{fr['winner']} ESCAPED!", 0, 0, 120, 980, fr["wcolor"], k)
        text(ctx, "Did you guess right?", 0, 100, 54, (1, 1, 1), k)
        ctx.restore()


def audio_events(res, cfg: Config):
    """Turn sim events into (time, freq, kind) for the synth."""
    out, mi = [], 0
    for t, kind, _ in res["events"]:
        if kind == "bounce":
            out.append((t, note_freq(cfg.melody[mi % len(cfg.melody)]), "pluck"))
            mi += 1
        elif kind == "clash":
            out.append((t, 1046.5, "tick"))
        else:
            out.append((t, 523.25, "win"))
    return out


def metadata_facts(res, cfg: Config):
    return dict(template="escape", winner=res["winner"], colors=cfg.names,
                n_balls=len(cfg.names), t_escape=round(res["t_esc"], 2),
                bounces=res["bounces"], melody=cfg.melody_name)
