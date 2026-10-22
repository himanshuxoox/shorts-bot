"""
"Only circles. What will they draw?" — Fourier series epicycles (3Blue1Brown style).
A chain of spinning circles (each one turning at a whole-number speed) traces a closed
picture. First with only a few circles (a blob), then more, then ~100: the hidden shape
appears. Shapes: heart, π, Σ, a star, ∞, a music note… chosen per seed.
"""
import math

import numpy as np

from base import *

SHAPES = ["heart", "π", "Σ", "star", "∞", "S", "β", "ω", "&"]
NAMES = {"heart": "A heart", "π": "Pi (π)", "Σ": "Sigma (Σ)", "star": "A star", "∞": "Infinity (∞)",
         "S": "The letter S", "β": "Beta (β)", "ω": "Omega (ω)", "&": "An ampersand (&)"}


def shape_points(name, n=2048):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if name == "heart":
        x = 16 * np.sin(t) ** 3
        y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
        z = x + 1j * y
    elif name == "star":
        r = 1 + 0.45 * np.cos(5 * t)
        r = np.where(np.cos(5 * t) > 0, 1.0, 0.45)            # sharp 5-point star (polygon)
        k = np.arange(10)
        corners = np.where(k % 2 == 0, 1.0, 0.42) * np.exp(1j * (np.pi / 2 + k * np.pi / 5))
        seg = (t / (2 * np.pi) * 10)
        i = seg.astype(int) % 10
        f = seg - seg.astype(int)
        z = corners[i] * (1 - f) + corners[(i + 1) % 10] * f
    else:
        from matplotlib.textpath import TextPath
        from matplotlib.font_manager import FontProperties
        path = TextPath((0, 0), name, size=100, prop=FontProperties(family=FONT, weight="bold"))
        polys = path.to_polygons(closed_only=True)
        P = max(polys, key=lambda q: np.linalg.norm(np.diff(q, axis=0), axis=1).sum())   # outer outline
        P = P[:, 0] + 1j * P[:, 1]
        d = np.abs(np.diff(np.concatenate([P, P[:1]])))
        s_ = np.concatenate([[0], np.cumsum(d)])
        u = np.linspace(0, s_[-1], n, endpoint=False)
        Pc = np.concatenate([P, P[:1]])
        z = np.interp(u, s_, Pc.real) + 1j * np.interp(u, s_, Pc.imag)
    z = z - z.mean()
    z = z / np.abs(z).max()
    return z


def coefficients(z, K):
    n = len(z)
    ks = np.array([0] + [s * k for k in range(1, K + 1) for s in (1, -1)])
    t = np.arange(n) / n
    c = np.array([(z * np.exp(-2j * np.pi * k * t)).mean() for k in ks])
    order = np.argsort(-np.abs(c))
    order = np.concatenate([[0], [i for i in order if i != 0]])       # constant term first
    return ks[order], c[order]


class Fourier(ShortScene):
    def construct(self):
        rng = self.rng
        name = rng.choice(SHAPES)
        z = shape_points(name)
        hue = rng.choice([(GOLD, PINK), (CYAN, "#9B7BFF"), ("#FF8A3D", GOLD), ("#36D399", CYAN)])
        self.grid(0.09)
        self.question("Only circles. What will they draw?", 44, y=3.3)
        grp, num = self.counter("circles: ", 0, y=2.7, size=44)
        stages = [(rng.choice([2, 3]), 6.0), (rng.choice([12, 16, 20]), 7.0), (rng.choice([90, 120, 150]), 9.5)]
        SCALE = 1.75
        CENTER = DOWN * 0.15

        for si, (K_n, dur) in enumerate(stages):
            ks, cs = coefficients(z, (K_n + 1) // 2 + 1)
            ks, cs = ks[:K_n + 1], cs[:K_n + 1]
            num.set_value(K_n)
            circles = VGroup(*[Circle(radius=max(1e-3, abs(c) * SCALE)).set_stroke(WHITE, 1.4, 0.28)
                               for c in cs[1:]])
            chain = VMobject().set_stroke(WHITE, 2.2, 0.85)
            trail_glow = VMobject().set_stroke(hue[1], 14, 0.18)
            trail = VMobject().set_stroke(hue, 5)
            tip = Dot(radius=0.045, fill_color=WHITE)
            hist = []
            t0 = self.time

            def pts(u):
                terms = cs * np.exp(2j * np.pi * ks * u)
                acc = np.cumsum(terms) * SCALE
                return acc

            def upd(_m, dt=0):
                u = min(1.0, (self.time - t0) / dur)
                acc = pts(u)
                P = np.stack([acc.real, acc.imag, np.zeros(len(acc))], 1) + CENTER
                for i, c in enumerate(circles):
                    c.move_to(P[i])
                chain.set_points_as_corners(P)
                # dense trail sampling between frames
                last = hist[-1][0] if hist else 0.0
                for uu in np.linspace(last, u, max(2, int((u - last) * 1500)))[1:] if hist else [u]:
                    a = pts(uu)[-1]
                    hist.append((uu, np.array([a.real, a.imag, 0]) + CENTER))
                if len(hist) >= 2:
                    arr = np.array([h[1] for h in hist])
                    trail.set_points_as_corners(arr)
                    trail_glow.set_points_as_corners(arr)
                tip.move_to(P[-1])

            holder = Mobject()
            holder.add_updater(upd)
            upd(None)
            self.add(holder, circles, chain, trail_glow, trail, tip)
            if si == 0:
                self.wait(0.3)
            # a soft note every quarter turn keeps a pulse
            for q in range(1, 9):
                self.sfx("tick", [523.25, 659.25, 783.99, 1046.5][q % 4] * (1.0 if si < 2 else 1.0), at=t0 + dur * q / 8)
            self.wait(dur)
            holder.clear_updaters()
            if si < len(stages) - 1:
                verdict = T(["Just a blob…", "Getting closer…"][si], 40, WHITE_).move_to(DOWN * 3.15)
                self.play(FadeIn(verdict, shift=UP * 0.2), run_time=0.4)
                self.wait(0.6)
                self.play(FadeOut(VGroup(circles, chain, trail_glow, trail, tip, verdict)), run_time=0.45)
                self.remove(holder)
            else:
                self.sfx("win", 523.25)
                self.play(FadeOut(VGroup(circles, chain, tip)), trail.animate.set_stroke(width=7),
                          trail_glow.animate.set_stroke(opacity=0.35), run_time=0.6)
                self.payoff(f"{NAMES[name]}! Only circles.", 44, y=-3.15)
                self.wait(2.0)
        self.meta = dict(shape=name, circles=[s[0] for s in stages])
