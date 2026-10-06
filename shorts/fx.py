"""Shared drawing pieces for all simulation formats (backgrounds, balls, hook text,
particle bursts, scoreboards, the end banner)."""
import math, random

import cairo

from .common import W, H, text, text_fit, rounded

PALETTE = {
    "RED": (1.0, 0.23, 0.36), "BLUE": (0.22, 0.62, 1.0), "GREEN": (0.2, 0.95, 0.5),
    "YELLOW": (1.0, 0.85, 0.2), "PURPLE": (0.72, 0.4, 1.0), "ORANGE": (1.0, 0.55, 0.15),
    "PINK": (1.0, 0.45, 0.8), "CYAN": (0.2, 0.95, 0.95),
}
BGS = [(0.07, 0.05, 0.16), (0.03, 0.08, 0.14), (0.12, 0.04, 0.1), (0.04, 0.04, 0.06), (0.02, 0.1, 0.08)]
GOLD = (1.0, 0.85, 0.25)


def hsv(h, s=0.75, v=1.0):
    h = (h % 1.0) * 6
    i, f = int(h), h - int(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]


def background(ctx, hue, cx=540, cy=1010):
    g = cairo.RadialGradient(cx, cy, 50, cx, cy, 1300)
    g.add_color_stop_rgb(0, *hue)
    g.add_color_stop_rgb(1, 0.0, 0.0, 0.02)
    ctx.set_source(g)
    ctx.paint()


def ball(ctx, x, y, r, col, pulse=0.0, trail=(), glow=True):
    for i, (tx, ty, tr) in enumerate(trail[:-1]):
        k = (i + 1) / len(trail)
        ctx.set_source_rgba(*col, 0.18 * k)
        ctx.arc(tx, ty, tr * (0.5 + 0.5 * k), 0, 2 * math.pi)
        ctx.fill()
    if glow:
        rg = r * (1.6 + 0.6 * pulse) + 18
        g = cairo.RadialGradient(x, y, r * 0.6, x, y, rg)
        g.add_color_stop_rgba(0, *col, 0.5)
        g.add_color_stop_rgba(1, *col, 0.0)
        ctx.set_source(g)
        ctx.arc(x, y, rg, 0, 2 * math.pi)
        ctx.fill()
    b = cairo.RadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r)
    b.add_color_stop_rgb(0, *(min(1, c + 0.45) for c in col))
    b.add_color_stop_rgb(1, *col)
    ctx.set_source(b)
    ctx.arc(x, y, r * (1 + 0.08 * pulse), 0, 2 * math.pi)
    ctx.fill()


def glow_arc(ctx, cx, cy, r, a0, a1, col, width=14, alpha=1.0):
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for wdt, al in ((width * 4.2, 0.05), (width * 2.7, 0.08), (width * 1.7, 0.15), (width, 1.0)):
        ctx.set_line_width(wdt)
        c = col if al < 1 else tuple(min(1, x * 0.3 + 0.7) for x in col)
        ctx.set_source_rgba(*c, al * alpha)
        ctx.new_path()
        ctx.arc(cx, cy, r, a0, a1)
        ctx.stroke()


def hook(ctx, t, l1, l2, sub, y=250):
    """Hook text is fully visible on frame 0 (the feed preview); it lands with a small punch."""
    s = 1.0 + 0.1 * max(0.0, 1 - t / 0.25) ** 2
    ctx.save()
    ctx.translate(540, y + 50)
    ctx.scale(s, s)
    ctx.translate(-540, -(y + 50))
    text_fit(ctx, l1, 540, y, 92, 880)
    text_fit(ctx, l2, 540, y + 100, 92, 880, GOLD)
    ctx.restore()
    if sub:
        text(ctx, sub, 540, y + 170, 38, (1, 1, 1), 0.65, bold=False)


def burst(ctx, t, b):
    """b = (t0, x, y, col, seed, n, speed, life). Particles are computed analytically."""
    t0, x, y, col, seed, n, speed, life = b
    dt = t - t0
    if dt < 0 or dt > life:
        return
    rng = random.Random(seed)
    k = dt / life
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        v = speed * rng.uniform(0.35, 1.0)
        sz = rng.uniform(4, 10)
        px = x + math.cos(a) * v * dt
        py = y + math.sin(a) * v * dt + 700 * dt * dt
        ctx.set_source_rgba(*col, 1 - k)
        ctx.arc(px, py, sz * (1 - 0.6 * k), 0, 2 * math.pi)
        ctx.fill()


def ring_shatter(ctx, t, b):
    """Ring pieces flying outward: b = (t0, cx, cy, r, col, seed)."""
    t0, cx, cy, r, col, seed = b
    dt = t - t0
    life = 1.1
    if dt < 0 or dt > life:
        return
    rng = random.Random(seed)
    k = dt / life
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(28):
        a = 2 * math.pi * i / 28 + rng.uniform(-0.05, 0.05)
        out = rng.uniform(250, 650) * dt
        drop = 900 * dt * dt
        px, py = cx + math.cos(a) * (r + out), cy + math.sin(a) * (r + out) + drop
        spin = rng.uniform(-6, 6) * dt
        ln = 2 * math.pi * r / 28 * 0.7
        ctx.set_line_width(10 * (1 - 0.5 * k))
        ctx.set_source_rgba(*col, 1 - k)
        ctx.new_path()
        ctx.move_to(px - math.sin(a + spin) * ln / 2, py + math.cos(a + spin) * ln / 2)
        ctx.line_to(px + math.sin(a + spin) * ln / 2, py - math.cos(a + spin) * ln / 2)
        ctx.stroke()


def pills(ctx, items, y0=1470, label=None):
    """items: list of (text, color, dim). 2 or 3 per row."""
    n = len(items)
    cols = 2 if n in (2, 4) else 3
    pw, ph, gx = (370, 100, 40) if cols == 2 else (300, 92, 22)
    x0 = 540 - (cols * pw + (cols - 1) * gx) / 2
    for i, (s, col, dim) in enumerate(items):
        row, ci = divmod(i, cols)
        bx, by = x0 + ci * (pw + gx), y0 + row * (ph + 18)
        a = 0.35 if dim else 1.0
        rounded(ctx, bx, by, pw, ph, ph / 2)
        ctx.set_source_rgba(*col, 0.18 * a)
        ctx.fill_preserve()
        ctx.set_source_rgba(*col, 0.9 * a)
        ctx.set_line_width(4)
        ctx.stroke()
        text_fit(ctx, s, bx + pw / 2, by + ph / 2 + 17, 48, pw - 40, (1, 1, 1), a)
        if dim:
            ctx.set_source_rgba(1, 1, 1, 0.6)
            ctx.set_line_width(5)
            ctx.move_to(bx + 30, by + ph / 2)
            ctx.line_to(bx + pw - 30, by + ph / 2)
            ctx.stroke()
    if label:
        rows = (n + cols - 1) // cols
        text(ctx, label, 540, y0 + rows * (ph + 18) + 22, 30, (1, 1, 1), 0.5, bold=False)


def banner(ctx, t, t_end, line1, col, line2="Did you guess right?", y=980, dim=0.55):
    k = min(1.0, (t - t_end) / 0.35)
    if k <= 0:
        return
    ctx.set_source_rgba(0, 0, 0, dim * k)
    ctx.paint()
    s = 1.0 + 0.25 * (1 - k)
    ctx.save()
    ctx.translate(540, y)
    ctx.scale(s, s)
    text_fit(ctx, line1, 0, 0, 120, 980, col, k)
    if line2:
        text(ctx, line2, 0, 100, 54, (1, 1, 1), k)
    ctx.restore()


def confetti(ctx, t, t0, seed=7, n=90):
    dt = t - t0
    if dt < 0:
        return
    rng = random.Random(seed)
    for _ in range(n):
        x = rng.uniform(0, W)
        vy = rng.uniform(250, 600)
        y = -40 + vy * dt
        if y > H + 40:
            continue
        col = hsv(rng.random(), 0.7, 1.0)
        a = rng.uniform(0, 6.28) + dt * rng.uniform(-6, 6)
        ctx.save()
        ctx.translate(x + 40 * math.sin(dt * 3 + x), y)
        ctx.rotate(a)
        ctx.set_source_rgb(*col)
        ctx.rectangle(-9, -5, 18, 10)
        ctx.fill()
        ctx.restore()


# ------------------------------------------------------------------ "neon" style (black, minimal)
def black(ctx):
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()


def neon_title(ctx, t, s, y=300, size=64):
    """Question at the top, like a caption (up to 2 lines). Visible from frame 0."""
    from .common import _face
    _face(ctx, size, True)
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if ctx.text_extents(trial).width > 900 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    lines.append(cur)
    lines = lines[:2]
    k = 1.0 + 0.06 * max(0.0, 1 - t / 0.25) ** 2
    ctx.save()
    ctx.translate(540, y)
    ctx.scale(k, k)
    for j, ln in enumerate(lines):
        text_fit(ctx, ln, 0, (j - (len(lines) - 1) / 2) * size * 1.15, size, 940)
    ctx.restore()


def music_line(ctx, s="Did you recognize the music?", y=1575):
    text(ctx, s, 540, y, 40, (1, 1, 1), 0.85)


def big_count(ctx, n, y=1470, label="", col=(1, 1, 1)):
    text(ctx, f"{n:,}{label}", 540, y, 64, col, 0.95)


# ------------------------------------------------------------------ two-line caption with coloured words
CYAN = (0.25, 0.85, 1.0)
RED = (1.0, 0.3, 0.3)
WHITE = (1.0, 1.0, 1.0)


def rich_title(ctx, lines, y=290, size=60, max_w=960):
    """lines: [[(text, rgb), ...], ...]  e.g. Every bounce SHRINKS the ball."""
    from .common import _face
    _face(ctx, size, True)
    widths = [sum(ctx.text_extents(s).x_advance for s, _ in ln) for ln in lines]
    k = min(1.0, max_w / max(widths))
    _face(ctx, size * k, True)
    for j, ln in enumerate(lines):
        w = sum(ctx.text_extents(s).x_advance for s, _ in ln)
        x = 540 - w / 2
        yy = y + (j - (len(lines) - 1) / 2) * size * k * 1.18
        for s, col in ln:
            ctx.move_to(x, yy)
            ctx.set_source_rgb(*col)
            ctx.show_text(s)
            x += ctx.text_extents(s).x_advance
        ctx.new_path()
