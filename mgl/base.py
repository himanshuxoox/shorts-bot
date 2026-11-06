"""Shared look + helpers for the ManimGL (3b1b/manim) Shorts formats.

Every scene is 1080x1920 (frame 4.5 x 8 units), deep-navy background, a question at the top
(visible on frame 0), a gold counter under it, and a payoff line at the end. Scenes record sound
events in self.events = [(time, freq, kind)] which the renderer turns into audio afterwards
(shorts.common.build_audio), so the clicks line up with the picture exactly.
"""
import json, os, random, zlib

from manimlib import *

BG = "#060a17"
GOLD = "#FFD24A"
CYAN = "#5CE6FF"
PINK = "#FF5FA2"
WHITE_ = "#FFFFFF"
FONT = os.environ.get("SHORTS_FONT", "Inter")
SEED = int(os.environ.get("MGL_SEED", "1"))
EVENTS_OUT = os.environ.get("MGL_EVENTS", "")


def glow(mob, color, width=6, layers=((5, 0.06), (3, 0.12), (1.8, 0.25))):
    """Neon look: wide faint copies of the outline behind the shape."""
    g = VGroup()
    for k, a in layers:
        g.add(mob.copy().set_fill(opacity=0).set_stroke(color, width * k, a))
    g.add(mob)
    return g


def melody(seed):
    """(name, [note names]) of a public-domain tune from shorts/melodies.py, picked by seed."""
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from shorts import melodies as _m
    name = random.Random(seed * 31 + 5).choice(_m.FAMOUS)
    return name, _m.MELODIES[name]


def note_hz(name):
    import re
    semi = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)
    mm = re.fullmatch(r"([A-G])([#b]?)(\d)", name)
    k = semi[mm.group(1)] + {"#": 1, "b": -1, "": 0}[mm.group(2)]
    return 440.0 * 2 ** ((12 * (int(mm.group(3)) + 1) + k - 69) / 12)


def T(s, size=40, color=WHITE_, weight=BOLD, **kw):
    return Text(s, font=FONT, font_size=size, color=color, weight=weight, **kw)


class GridSurface(Surface):
    """A surface given directly as a grid of points P (nu, nv, 3); update it every frame with
    set_grid(P) (same shape) and colour it per vertex with set_vertex_colors(rgba (nu*nv, 4))."""

    def __init__(self, P, **kw):
        self._P = np.asarray(P, float)
        nu, nv = self._P.shape[:2]
        super().__init__(resolution=(nu, nv), **kw)

    def init_points(self):
        nu, nv = self.get_resolution()
        self.set_points(self._P.reshape(nu * nv, 3))

    def set_grid(self, P):
        nu, nv = self.get_resolution()
        self.set_points(np.asarray(P, float).reshape(nu * nv, 3))
        return self

    def set_vertex_colors(self, rgba):
        self.set_rgba_array(np.asarray(rgba, np.float32))
        return self


def hsl_rgba(h, s=0.9, l=0.6, a=1.0):
    """vectorised HSL -> RGBA array, h in [0, 1)"""
    h = np.asarray(h, float) % 1.0
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - np.abs((h * 6) % 2 - 1))
    m = l - c / 2
    i = np.floor(h * 6).astype(int) % 6
    z = np.zeros_like(h)
    r = np.choose(i, [c + z, x, z, z, x, c + z])
    g = np.choose(i, [x, c + z, c + z, x, z, z])
    b = np.choose(i, [z, z, x, c + z, c + z, x])
    return np.stack([r + m, g + m, b + m, np.full_like(h, a)], -1)


class ShortScene(Scene):
    default_camera_config = dict(background_color=BG)
    HUD_FIXED = False          # 3D scenes: texts / grid stay put while the camera moves

    def hud(self, mob):
        if self.HUD_FIXED:
            mob.fix_in_frame()
        return mob

    def setup(self):
        self.rng = random.Random(SEED * 7919 + zlib.crc32(type(self).__name__.encode()) % 1000)
        self.events = []

    # ---- sound
    def sfx(self, kind, freq=880.0, at=None):
        self.events.append((float(self.time if at is None else at), float(freq), kind))

    def tear_down(self):
        if EVENTS_OUT:
            with open(EVENTS_OUT, "w") as f:
                json.dump(dict(events=self.events, total=float(self.time), meta=getattr(self, "meta", {})), f)
        super().tear_down()

    # ---- look
    def grid(self, opacity=0.13, step=0.5):
        """Faint 3b1b-style grid over the whole frame."""
        lines = VGroup()
        for x in np.arange(-2.5, 2.51, step):
            lines.add(Line(UP * 4.2 + RIGHT * x, DOWN * 4.2 + RIGHT * x))
        for y in np.arange(-4.0, 4.01, step):
            lines.add(Line(LEFT * 2.5 + UP * y, RIGHT * 2.5 + UP * y))
        lines.set_stroke(CYAN, 1.2, opacity)
        self.hud(lines)
        self.add(lines)
        return lines

    # ---- texts
    def question(self, s, size=46, y=3.25):
        q = T(s, size)
        if q.get_width() > 4.1:
            q.set_width(4.1)
        q.move_to(UP * y)
        self.hud(q)
        self.add(q)
        return q

    def counter(self, label, value=0, y=2.72, size=40, color=GOLD, decimals=0):
        lab = T(label, size)
        tc = dict(font=FONT, weight=BOLD)
        num = Integer(value, font_size=size * 1.2, color=color, text_config=tc) if decimals == 0 else \
            DecimalNumber(value, num_decimal_places=decimals, font_size=size * 1.2, color=color, text_config=tc)
        grp = VGroup(lab, num).arrange(RIGHT, buff=0.12, aligned_edge=DOWN)
        grp.move_to(UP * y)

        def recenter(g):
            g.arrange(RIGHT, buff=0.12, aligned_edge=DOWN).move_to(UP * y)
        grp.add_updater(recenter)
        self.hud(grp)
        self.add(grp)
        return grp, num

    def payoff(self, s, size=44, y=-3.2, color=GOLD, run_time=0.6):
        p = T(s, size, color)
        if p.get_width() > 4.05:
            p.set_width(4.05)
        p.move_to(UP * y)
        self.hud(p)
        self.play(FadeIn(p, scale=1.4), run_time=run_time)
        return p
