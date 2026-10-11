"""
Game-poster style thumbnail for the Ball Battle Royale (1280x720), made fresh for every video:

  "9 BALLS FIGHT!" (big, slanted, fire burst) · "LAST ONE SURVIVES!" brush banner + arrow
  -> a mystery "?" ball with a crown ("WINNER?") · arena floor in perspective · two hero
  balls clashing in the middle · every other ball with name + HP bar + speed trails ·
  the ball that really went out first has X-eyes and a dust cloud.

Never reveals the winner: the winner is never a hero and never looks like it is winning.
Uses the fonts in fonts/ (Inter Black Italic for the poster text).
"""
import math, os, random

import cairo
from PIL import Image

from . import fx
from .royale import COLS, draw_sprite, draw_icon, _crown

TW, TH = 1280, 720
POSTER = "Inter Black"
SLOTS = [  # x, y, r  (the first two are the heroes)
    (455, 470, 128), (735, 515, 118),
    (175, 435, 66), (165, 625, 76), (1045, 420, 66), (1205, 565, 60), (1000, 640, 70),
    (600, 292, 46), (850, 300, 54), (585, 668, 44),
]
BANNERS = [("LAST ONE", "SURVIVES!"), ("ONLY ONE", "WINS!"), ("WHO", "SURVIVES?")]


def _poster_text(c, s, x, y, size, fill, outline=(0, 0, 0), ow=14, glow=None, gw=26, rot=0.0,
                 align="left"):
    c.save()
    c.translate(x, y)
    c.rotate(rot)
    c.select_font_face(POSTER, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(size)
    ext = c.text_extents(s)
    dx = {"left": -ext.x_bearing, "center": -(ext.width / 2 + ext.x_bearing),
          "right": -(ext.width + ext.x_bearing)}[align]
    c.move_to(dx, 0)
    c.text_path(s)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    if glow:
        c.set_source_rgb(*glow); c.set_line_width(gw); c.stroke_preserve()
    c.set_source_rgb(*outline); c.set_line_width(ow); c.stroke_preserve()
    if isinstance(fill, tuple):
        c.set_source_rgb(*fill)
    else:
        g = cairo.LinearGradient(0, -size * 0.75, 0, 0)
        for k, col in enumerate(fill):
            g.add_color_stop_rgb(k / (len(fill) - 1), *col)
        c.set_source(g)
    c.fill()
    w = ext.x_advance
    c.restore()
    return w


def _burst(c, x, y, r0, r1, n, col, alpha, rng):
    c.move_to(x + r1, y)
    for j in range(1, 2 * n + 1):
        a = j * math.pi / n
        rr = (r1 * rng.uniform(0.7, 1.15)) if j % 2 == 0 else r0 * rng.uniform(0.8, 1.1)
        c.line_to(x + rr * math.cos(a), y + rr * math.sin(a))
    c.close_path()
    c.set_source_rgba(*col, alpha)
    c.fill()


def _floor(c):
    sky = cairo.LinearGradient(0, 0, 0, TH)
    sky.add_color_stop_rgb(0, 0.03, 0.04, 0.12)
    sky.add_color_stop_rgb(0.4, 0.06, 0.07, 0.2)
    sky.add_color_stop_rgb(1, 0.02, 0.03, 0.1)
    c.set_source(sky); c.paint()
    hy, vx, vy = 250, 640, 40                   # floor edge, vanishing point
    c.move_to(-200, TH); c.line_to(140, hy); c.line_to(TW - 60, hy - 25); c.line_to(TW + 300, TH)
    c.close_path()
    g = cairo.LinearGradient(0, hy, 0, TH)
    g.add_color_stop_rgb(0, 0.05, 0.08, 0.25)
    g.add_color_stop_rgb(1, 0.02, 0.03, 0.12)
    c.set_source(g); c.fill_preserve()
    c.save(); c.clip()
    c.set_source_rgba(0.35, 0.5, 1.0, 0.22); c.set_line_width(2)
    for k in range(-14, 15):
        x = 640 + k * 150
        c.move_to(vx + (x - vx) * 0.12, hy); c.line_to(x + (x - vx) * 1.4, TH + 40)
    y, step = hy + 8, 16
    while y < TH + 20:
        c.move_to(0, y); c.line_to(TW, y)
        y += step; step *= 1.22
    c.stroke()
    c.restore()
    # neon edge of the arena
    for w_, a in ((14, 0.25), (5, 0.9)):
        c.set_source_rgba(0.6, 0.35, 1.0, a); c.set_line_width(w_)
        c.move_to(140, hy); c.line_to(TW - 60, hy - 25); c.stroke()


def _trail(c, x, y, r, col, ang, rng):
    """Speed streaks behind a ball (ang = direction it is moving)."""
    ux, uy = -math.cos(ang), -math.sin(ang)
    px, py = -uy, ux
    for _ in range(9):
        off = rng.uniform(-0.8, 0.8) * r
        L = rng.uniform(1.2, 2.6) * r
        sx, sy = x + px * off + ux * r * 0.6, y + py * off + uy * r * 0.6
        g = cairo.LinearGradient(sx, sy, sx + ux * L, sy + uy * L)
        g.add_color_stop_rgba(0, *col, 0.75)
        g.add_color_stop_rgba(1, *col, 0.0)
        c.set_source(g)
        c.set_line_width(rng.uniform(3, 9))
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.move_to(sx, sy); c.line_to(sx + ux * L, sy + uy * L); c.stroke()


def _label(c, name, x, y, r, hp):
    col = COLS[name]
    bw = max(90, r * 1.5)
    by = y - r - 18
    c.save()
    c.translate(x, by)
    c.rotate(-0.06)
    c.set_source_rgba(0, 0, 0, 0.85)
    c.rectangle(-bw / 2 - 4, -4, bw + 8, 18); c.fill()
    g = cairo.LinearGradient(-bw / 2, 0, bw / 2, 0)
    g.add_color_stop_rgb(0, 0.2, 0.95, 0.3)
    g.add_color_stop_rgb(0.55, 1.0, 0.85, 0.2)
    g.add_color_stop_rgb(1, 1.0, 0.2, 0.2)
    c.set_source(g)
    c.rectangle(-bw / 2, 0, bw * hp, 10); c.fill()
    c.restore()
    _poster_text(c, name.upper(), x, by - 10, max(24, r * 0.36), col, ow=7, rot=-0.06, align="center")


def _mystery(c, x, y, r):
    rng = random.Random(3)
    for k in range(18):                        # golden rays
        a = k * math.pi / 9 + rng.uniform(-0.05, 0.05)
        c.move_to(x, y)
        c.arc(x, y, 330, a - 0.06, a + 0.06)
        c.close_path()
    g = cairo.RadialGradient(x, y, 20, x, y, 330)
    g.add_color_stop_rgba(0, 1, 0.85, 0.4, 0.55)
    g.add_color_stop_rgba(1, 1, 0.85, 0.4, 0.0)
    c.set_source(g); c.fill()
    g = cairo.RadialGradient(x, y, 10, x, y, r * 2.2)
    g.add_color_stop_rgba(0, 1, 0.9, 0.5, 0.9)
    g.add_color_stop_rgba(1, 1, 0.8, 0.3, 0.0)
    c.set_source(g); c.arc(x, y, r * 2.2, 0, 6.29); c.fill()
    # pedestal
    c.save(); c.translate(x, y + r * 1.05); c.scale(1, 0.28)
    c.set_source_rgba(0.95, 0.75, 0.25, 0.9); c.set_line_width(10); c.arc(0, 0, r * 1.5, 0, 6.29); c.stroke()
    c.set_source_rgba(0.2, 0.15, 0.05, 0.9); c.arc(0, 0, r * 1.45, 0, 6.29); c.fill()
    c.restore()
    g = cairo.RadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r)
    g.add_color_stop_rgb(0, 0.35, 0.35, 0.4)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.04)
    c.set_source(g); c.arc(x, y, r, 0, 6.29); c.fill()
    _poster_text(c, "?", x, y + r * 0.42, r * 1.25, (1, 1, 1), ow=8, align="center")
    _crown(c, x, y - r - 26, r * 1.2)


def _fit_banner(c, s, x, y, fill, max_w=300, size=60):
    c.select_font_face(POSTER, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(size)
    w = c.text_extents(s).x_advance
    _poster_text(c, s, x, y, size * min(1.0, max_w / w), fill, ow=10, rot=-0.06)


def _brush_banner(c, x0, y0, x1, y1, rng):
    pts_top = [(x0 + (x1 - x0) * k / 12, y0 + rng.uniform(-8, 8)) for k in range(13)]
    pts_bot = [(x0 + (x1 - x0) * k / 12 + 30, y1 + rng.uniform(-8, 8)) for k in range(12, -1, -1)]
    c.move_to(*pts_top[0])
    for p in pts_top[1:] + pts_bot:
        c.line_to(*p)
    c.close_path()
    c.set_source_rgba(0, 0, 0, 0.88)
    c.fill()


def _arrow(c, x0, y0, x1, y1):
    a = math.atan2(y1 - y0, x1 - x0)
    L = math.hypot(x1 - x0, y1 - y0)
    c.save(); c.translate(x0, y0); c.rotate(a)
    c.move_to(0, -11); c.line_to(L - 40, -11); c.line_to(L - 40, -30); c.line_to(L, 0)
    c.line_to(L - 40, 30); c.line_to(L - 40, 11); c.line_to(0, 11); c.close_path()
    c.set_source_rgb(0, 0, 0); c.set_line_width(8); c.stroke_preserve()
    c.set_source_rgb(0.95, 0.12, 0.12); c.fill()
    c.restore()


def save_thumbnail(cfg, path, res=None):
    rng = random.Random(cfg.seed * 5 + 1)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, TW, TH)
    c = cairo.Context(surf)
    _floor(c)
    _mystery(c, 1140, 205, 72)
    _poster_text(c, "WINNER?", 1140, 72, 46, fx.GOLD, ow=10, glow=(0.6, 0.25, 0.0), gw=18, rot=-0.05,
                 align="center")

    winner = res.get("winner") if res else None
    first_out = res["feed"][0][3] if res and res.get("feed") else None
    names = cfg.names[:]
    rng.shuffle(names)
    heroes = [n for n in names if n != winner and n != first_out][:2]
    rest = [n for n in names if n not in heroes]
    order = heroes + rest
    slots = SLOTS[:len(order)]
    # first-out ball goes to the "knocked out" spot (index 6) when there is one
    if first_out in order and len(order) > 6:
        i, j = order.index(first_out), 6
        order[i], order[j] = order[j], order[i]
    faces = ["shocked", "scared", "nervous", "angry", "crying", "determined", "shocked", "scared"]

    # draw back to front (smaller y first)
    items = sorted(zip(order, slots, range(len(order))), key=lambda it: it[1][1] - it[1][2] * 0.2)
    for name, (x, y, r), idx in items:
        col = COLS[name]
        if idx == 0:
            face, ang = "angry", 0.0
        elif idx == 1:
            face, ang = "crying", math.pi
        elif name == first_out:
            face, ang = "defeated", None
        else:
            face, ang = faces[idx % len(faces)], math.atan2(y - 470, x - 590)
        if name == winner:
            face = rng.choice(["nervous", "scared", "shocked"])  # don't hint who wins
        c.set_source_rgba(0, 0, 0, 0.45)
        c.save(); c.translate(x, y + r * 0.92); c.scale(1, 0.25); c.arc(0, 0, r * 0.95, 0, 6.29); c.restore()
        c.fill()
        if ang is not None:
            _trail(c, x, y, r, col, ang, random.Random(idx * 7 + cfg.seed))
        else:  # dust cloud
            for k in range(9):
                c.set_source_rgba(0.75, 0.65, 0.55, 0.55)
                c.arc(x - r + k * r * 0.25, y + r * 0.7 + rng.uniform(-10, 10), r * rng.uniform(0.25, 0.4), 0, 6.29)
                c.fill()
        if idx == 1:  # impact burst between the two heroes, under the second hero
            hx, hy = (SLOTS[0][0] + SLOTS[1][0]) / 2 + 10, (SLOTS[0][1] + SLOTS[1][1]) / 2 - 10
            _burst(c, hx, hy, 50, 190, 14, (1.0, 0.55, 0.1), 0.85, rng)
            _burst(c, hx, hy, 30, 120, 12, (1.0, 0.95, 0.6), 0.95, rng)
        draw_sprite(c, name, face, x, y, r)
        if name == first_out:
            for k in range(3):
                a = -2.2 + k * 0.9
                fx_ = x + math.cos(a) * r * 1.15; fy_ = y + math.sin(a) * r * 1.15
                draw_icon(c, "bump", fx_, fy_, 14)
        hp = {0: 0.55, 1: 0.25}.get(idx, rng.uniform(0.25, 0.85))
        if name == first_out:
            hp = 0.03
        _label(c, name, x, y, r, hp)

    # title block (top-left)
    _burst(c, 210, 140, 90, 230, 16, (1.0, 0.35, 0.05), 0.55, rng)
    c.save(); c.translate(36, 175); c.rotate(-0.09)
    if len(cfg.names) >= 10:                    # two digits: keep clear of the banner
        c.translate(0, -14); c.scale(0.86, 0.86)
    w = _poster_text(c, str(len(cfg.names)), 0, 0, 190, [(1, 0.95, 0.4), (1, 0.7, 0.05)], ow=16,
                     glow=(0.8, 0.1, 0.05), gw=30)
    _poster_text(c, "BALLS", w + 6, -8, 108, [(1, 1, 1), (0.82, 0.86, 0.95)], ow=14, glow=(0.8, 0.1, 0.05), gw=26)
    _poster_text(c, "FIGHT!", 40, 118, 130, [(1, 0.75, 0.1), (1, 0.25, 0.05), (0.85, 0.05, 0.05)], ow=16,
                 glow=(1, 0.85, 0.3), gw=26)
    c.restore()
    # banner + arrow
    l1, l2 = BANNERS[0] if rng.random() < 0.6 else rng.choice(BANNERS[1:])
    _brush_banner(c, 585, 40, 905, 196, rng)
    _fit_banner(c, l1, 610, 108, [(1, 0.95, 0.4), (1, 0.75, 0.1)])
    _fit_banner(c, l2, 610, 180, (1, 1, 1))
    _arrow(c, 925, 150, 1052, 186)

    tmp = path + ".png"
    surf.write_to_png(tmp)
    Image.open(tmp).convert("RGB").save(path, "JPEG", quality=90)
    os.remove(tmp)
