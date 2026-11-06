"""
"100 spinning circles draw in 3D… what will you see from the TOP?" The Fourier circles (the
channel's #1 format) spin while their pen slowly RISES, so from the side the drawing is a
tangled 3D spring. At the end the camera swings over the top and the spring turns out to be a
picture (heart, π, Σ, star, ∞ …).
"""
import math

import numpy as np

from base import *
from fourier import SHAPES, NAMES, shape_points, coefficients


class Fourier3D(ShortScene):
    HUD_FIXED = True

    def construct(self):
        rng = self.rng
        name = rng.choice(SHAPES)
        z = shape_points(name)
        K_n = rng.choice([80, 100, 120])
        ks, cs = coefficients(z, K_n // 2 + 1)
        ks, cs = ks[:K_n + 1], cs[:K_n + 1]
        h0 = rng.random()
        SCALE = 1.8
        RISE = 1.6                              # how far the pen wanders up and down
        harm = [(m, rng.uniform(0.5, 1.0) / (1 + 0.3 * j), rng.uniform(0, 2 * math.pi))
                for j, m in enumerate(rng.sample([2, 3, 4, 5, 7], 3))]
        norm = sum(a for _m, a, _p in harm)

        def zf(u):
            u = np.asarray(u, float)
            return RISE * sum(a * np.sin(2 * math.pi * m * u + ph) for m, a, ph in harm) / norm
        DUR = 12.0
        frame = self.frame
        frame.reorient(-25, 72, 0)
        frame.set_height(7.0)
        frame.move_to(ORIGIN)
        self.grid(0.06)
        self.question("Spinning circles draw in 3D…", 50, y=3.35)
        sub = self.hud(T("What will you see from the TOP?", 38, GOLD).set_max_width(4.2).move_to(UP * 2.85))
        self.add(sub)
        grp, num = self.counter("circles: ", K_n, y=2.38, size=40)

        circles = VGroup(*[Circle(radius=max(1e-3, abs(c) * SCALE)).set_stroke(WHITE, 1.6, 0.45) for c in cs[1:]])
        chain = VMobject().set_stroke(WHITE, 2.0, 0.85)
        trail_glow = VMobject().set_stroke(WHITE, 12, 0.15)
        trail = VMobject().set_stroke(WHITE, 4.5)
        tip = Sphere(radius=0.06, color=WHITE)
        floor_ring = Circle(radius=SCALE * 1.05).set_stroke(CYAN, 2, 0.35)
        self.add(floor_ring, circles, chain, trail_glow, trail, tip)
        hist = []
        squash = ValueTracker(1.0)              # 1 = full spring height, 0 = flat drawing
        t0 = self.time

        def pts(u):
            return np.cumsum(cs * np.exp(2j * np.pi * ks * u)) * SCALE

        def path_colors(n):
            return [Color(rgb=tuple(c[:3])) for c in hsl_rgba(h0 + 0.85 * np.linspace(0, 1, max(2, min(n, 40))), 0.85, 0.6)]

        def upd(_m, dt=0):
            u = min(1.0, (self.time - t0) / DUR)
            k = squash.get_value()
            zc = float(zf(u)) * k
            acc = pts(u)
            P = np.stack([acc.real, acc.imag, zc * np.linspace(0, 1, len(acc))], 1)
            for i, c in enumerate(circles):
                c.move_to(P[i])
            chain.set_points_as_corners(P)
            last = hist[-1][0] if hist else 0.0
            for uu in (np.linspace(last, u, max(2, int((u - last) * 1800)))[1:] if hist else [u]):
                a = pts(uu)[-1]
                hist.append((uu, a))
            if len(hist) >= 2:
                us = np.array([h[0] for h in hist])
                arr = np.stack([[h[1].real for h in hist], [h[1].imag for h in hist], zf(us) * k], 1)
                trail.set_points_as_corners(arr)
                trail_glow.set_points_as_corners(arr)
                cols = path_colors(len(arr))
                trail.set_stroke(cols)
                trail_glow.set_stroke(cols, opacity=0.15)
            tip.move_to(P[-1])
            floor_ring.move_to(OUT * 0)

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder, squash)
        for q in range(1, 25):
            self.sfx("tick", [523.25, 659.25, 783.99, 1046.5][q % 4], at=t0 + DUR * q / 24)
        # slow orbit while drawing
        self.play(frame.animate.increment_theta(0.9), run_time=DUR * 0.45, rate_func=linear)
        lab = self.hud(T("Just a tangled 3D knot…?", 40, WHITE_).set_max_width(4.2).move_to(DOWN * 3.25))
        self.play(FadeIn(lab), frame.animate.increment_theta(0.15), run_time=0.4, rate_func=linear)
        self.play(frame.animate.increment_theta(0.8), run_time=DUR * 0.55 - 0.4, rate_func=linear)
        holder.clear_updaters()
        # swing over the top and flatten the spring
        self.play(FadeOut(Group(circles, chain, tip)), FadeOut(lab), run_time=0.4)
        holder.add_updater(upd)
        self.sfx("chime", 659.25)
        self.play(frame.animate.reorient(0, 0, 0).move_to(ORIGIN).set_height(7.6), squash.animate.set_value(0.0),
                  run_time=2.4, rate_func=smooth)
        holder.clear_updaters()
        self.sfx("win", 523.25)
        self.play(trail.animate.set_stroke(width=7), trail_glow.animate.set_stroke(opacity=0.35), run_time=0.4)
        self.payoff(f"{NAMES[name]}! Only circles.", 46, y=-3.2)
        self.wait(2.0)
        self.meta = dict(shape=name, circles=K_n)
