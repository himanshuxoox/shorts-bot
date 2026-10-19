"""Shared look for the "math / physics" formats (focus, golden, pendulum, rosette):
deep navy background, glowing cyan walls, comet balls with tails, a question at the top
and a counter line under it ("balls: 13") with the number in gold."""
import math

import cairo

from .common import W, H, _face, text_fit

GOLD = (1.0, 0.82, 0.28)
WALL = (0.35, 0.9, 1.0)
WHITE = (1.0, 1.0, 1.0)

_BG = {}


def background(ctx, tint=(0.03, 0.05, 0.11)):
    """Navy gradient + soft vignette, rendered once and reused every frame."""
    key = tuple(round(c, 3) for c in tint)
    surf = _BG.get(key)
    if surf is None:
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        c = cairo.Context(surf)
        g = cairo.LinearGradient(0, 0, 0, H)
        g.add_color_stop_rgb(0, *(x * 1.15 for x in tint))
        g.add_color_stop_rgb(0.55, *tint)
        g.add_color_stop_rgb(1, *(x * 0.35 for x in tint))
        c.set_source(g)
        c.paint()
        r = cairo.RadialGradient(W / 2, H * 0.52, 200, W / 2, H * 0.52, 1250)
        r.add_color_stop_rgba(0, 0, 0, 0, 0)
        r.add_color_stop_rgba(1, 0, 0, 0, 0.55)
        c.set_source(r)
        c.paint()
        _BG[key] = surf
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint()


def glow_stroke(ctx, path_fn, col=WALL, width=7, alpha=1.0):
    """Stroke the path made by path_fn(ctx) as a neon tube (wide faint passes + bright core)."""
    ctx.save()
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for wd, al, c in ((width * 5, 0.05, col), (width * 3, 0.10, col), (width * 1.8, 0.28, col),
                      (width, 0.95, tuple(0.55 + 0.45 * x for x in col)), (width * 0.4, 0.9, (1, 1, 1))):
        ctx.new_path()
        path_fn(ctx)
        ctx.set_line_width(wd)
        ctx.set_source_rgba(*c, al * alpha)
        ctx.stroke()
    ctx.restore()


def comet(ctx, x, y, dx, dy, col, r=9.0, tail=46.0, alpha=1.0):
    """Ball with a tapered tail behind it. (dx, dy) = direction of motion (any length)."""
    d = math.hypot(dx, dy)
    if d > 1e-9 and tail > 0:
        ux, uy = dx / d, dy / d
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for k, (f0, f1, w, a) in enumerate(((0.0, 1.0, 0.55, 0.25), (0.0, 0.6, 0.85, 0.45), (0.0, 0.3, 1.2, 0.6))):
            ctx.new_path()
            ctx.move_to(x - ux * tail * f0, y - uy * tail * f0)
            ctx.line_to(x - ux * tail * f1, y - uy * tail * f1)
            ctx.set_line_width(r * w * 2)
            ctx.set_source_rgba(*col, a * alpha)
            ctx.stroke()
    ctx.new_path()
    ctx.arc(x, y, r * 2.1, 0, 2 * math.pi)
    ctx.set_source_rgba(*col, 0.22 * alpha)
    ctx.fill()
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source_rgba(*col, alpha)
    ctx.fill()
    ctx.arc(x - r * 0.25, y - r * 0.25, r * 0.5, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 1, 1, 0.85 * alpha)
    ctx.fill()


def marker(ctx, x, y, r=11, col=GOLD, alpha=0.75, pulse=0.0):
    """Small hollow ring that marks a special point (a focus, the start point...)."""
    ctx.new_path()
    ctx.arc(x, y, r * (1 + 0.6 * pulse), 0, 2 * math.pi)
    ctx.set_line_width(2.5)
    ctx.set_source_rgba(*col, alpha)
    ctx.stroke()
    if pulse > 0:
        g = cairo.RadialGradient(x, y, 0, x, y, r * 6 * pulse + 1)
        g.add_color_stop_rgba(0, 1, 1, 1, 0.55 * pulse)
        g.add_color_stop_rgba(1, *col, 0)
        ctx.set_source(g)
        ctx.arc(x, y, r * 6 * pulse + 1, 0, 2 * math.pi)
        ctx.fill()


def question(ctx, t, s, y=330, size=62):
    k = 1.0 + 0.06 * max(0.0, 1 - t / 0.25) ** 2      # lands with a tiny punch, readable on frame 0
    ctx.save()
    ctx.translate(540, y)
    ctx.scale(k, k)
    text_fit(ctx, s, 0, 0, size, 980)
    ctx.restore()


def counter(ctx, label, value, y=420, size=52, col=GOLD, alpha=1.0):
    """'label value' centered, the value in gold:  balls: 13"""
    _face(ctx, size, True)
    lw = ctx.text_extents(label).x_advance
    vw = ctx.text_extents(value).x_advance
    x = 540 - (lw + vw) / 2
    ctx.move_to(x, y)
    ctx.set_source_rgba(1, 1, 1, alpha)
    ctx.show_text(label)
    ctx.move_to(x + lw, y)
    ctx.set_source_rgba(*col, alpha)
    ctx.show_text(value)
    ctx.new_path()


def answer(ctx, s, y=420, size=52, alpha=1.0):
    ctx.save()
    text_fit(ctx, s, 540, y, size, 980, GOLD, alpha)
    ctx.restore()


def fraction_label(ctx, prefix, num, den, suffix, y=430, size=50):
    """prefix  num/den  suffix  with a real stacked fraction (num over den) in gold."""
    _face(ctx, size, True)
    pw = ctx.text_extents(prefix).x_advance
    sw = ctx.text_extents(suffix).x_advance
    fs = size * 0.8
    _face(ctx, fs, True)
    fw = max(ctx.text_extents(num).x_advance, ctx.text_extents(den).x_advance) + 12
    x = 540 - (pw + fw + sw + 16) / 2
    _face(ctx, size, True)
    ctx.set_source_rgb(1, 1, 1)
    ctx.move_to(x, y)
    ctx.show_text(prefix)
    fx0 = x + pw + 8
    mid = y - size * 0.33
    _face(ctx, fs, True)
    ctx.set_source_rgb(*GOLD)
    for s_, yy in ((num, mid - 9), (den, mid + fs * 0.82 + 6)):
        e = ctx.text_extents(s_)
        ctx.move_to(fx0 + fw / 2 - e.x_advance / 2, yy)
        ctx.show_text(s_)
    ctx.new_path()
    ctx.set_line_width(3.5)
    ctx.move_to(fx0, mid)
    ctx.line_to(fx0 + fw, mid)
    ctx.stroke()
    _face(ctx, size, True)
    ctx.set_source_rgb(1, 1, 1)
    ctx.move_to(fx0 + fw + 8, y)
    ctx.show_text(suffix)
    ctx.new_path()


def rainbow(h, s=0.65, v=1.0):
    from .fx import hsv
    return hsv(h, s, v)
