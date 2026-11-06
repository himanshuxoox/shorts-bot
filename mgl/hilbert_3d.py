"""
"Can ONE line fill a whole cube?" The 3D Hilbert curve: 8 corners, then every corner splits into
its own little curve: 64, 512, 4,096 corners — always ONE line that never crosses itself and
visits every spot in the cube. Rainbow along its length, inside a glowing wire cube that turns.
"""
import math

import numpy as np

from base import *


def hilbert_points(order, dims=3):
    """Skilling's algorithm: Hilbert index -> coordinates, all 2^(order*dims) points in order."""
    n = 2 ** (order * dims)
    pts = np.zeros((n, dims), int)
    for idx in range(n):
        # index -> transposed form
        X = [0] * dims
        for b in range(order):
            for d in range(dims):
                bit = (idx >> (b * dims + (dims - 1 - d))) & 1
                X[d] |= bit << b
        # transpose -> axes (Skilling)
        N = 2 << (order - 1)
        t = X[dims - 1] >> 1
        for i in range(dims - 1, 0, -1):
            X[i] ^= X[i - 1]
        X[0] ^= t
        Q = 2
        while Q != N:
            P = Q - 1
            for i in range(dims - 1, -1, -1):
                if X[i] & Q:
                    X[0] ^= P
                else:
                    t = (X[0] ^ X[i]) & P
                    X[0] ^= t
                    X[i] ^= t
            Q <<= 1
        pts[idx] = X
    return pts


def centred(order, size=2.6):
    p = hilbert_points(order).astype(float)
    m = 2 ** order
    return (p + 0.5) / m * size - size / 2


class Hilbert3D(ShortScene):
    HUD_FIXED = True

    def construct(self):
        rng = self.rng
        h0 = rng.random()
        SIZE = 2.6
        frame = self.frame
        frame.reorient(-35, 65, 0)
        frame.set_height(8.0)
        frame.move_to(DOWN * 0.2 + OUT * 0)
        self.grid(0.05)
        self.question("Can ONE line fill a whole cube?", 50, y=3.38)
        grp, num = self.counter("corners: ", 8, y=2.82, size=46)
        cube = VCube(side_length=SIZE).set_fill(opacity=0).set_stroke(CYAN, 2.5, 0.55)
        self.add(cube)
        orders = [1, 2, 3, 4]
        P = {o: centred(o, SIZE) for o in orders}
        line = VMobject()
        glowl = VMobject()
        self.add(glowl, line)

        def colorize(n):
            k = max(2, min(n, 64))
            return [Color(rgb=tuple(c[:3])) for c in hsl_rgba(h0 + 0.85 * np.linspace(0, 1, k), 0.9, 0.6)]

        widths = {1: 9, 2: 7, 3: 4.5, 4: 2.6}
        spin = rng.choice([-1, 1])
        # order 1 drawn in
        line.set_points_as_corners(P[1]).set_stroke(colorize(8), widths[1])
        glowl.set_points_as_corners(P[1]).set_stroke(colorize(8), widths[1] * 4, 0.15)
        for q in range(8):
            self.sfx("pluck", 392.0 * 2 ** ([0, 2, 4, 5, 7, 9, 11, 12][q] / 12), at=self.time + 0.2 * q)
        self.play(ShowCreation(line), ShowCreation(glowl), frame.animate.increment_theta(spin * 0.3),
                  run_time=1.8, rate_func=linear)
        lab = self.hud(T("8 corners. Easy.", 44, WHITE_).move_to(DOWN * 3.2))
        self.play(FadeIn(lab), frame.animate.increment_theta(spin * 0.1), run_time=0.3)
        texts = {2: "Every corner splits into 8…", 3: "…and again…", 4: "…and again!"}
        for o in orders[1:]:
            # split: each new point starts at its parent corner, then moves to its place
            new = P[o]
            parent = np.repeat(P[o - 1], 8, axis=0)
            tr = ValueTracker(0.0)

            def upd(_m, dt=0, new=new, parent=parent, o=o):
                a = tr.get_value()
                Q = parent + (new - parent) * a
                line.set_points_as_corners(Q)
                glowl.set_points_as_corners(Q)

            holder = Mobject()
            holder.add_updater(upd)
            self.add(holder, tr)
            self.remove(lab)
            lab = self.hud(T(texts[o], 42, WHITE_).set_max_width(4.2).move_to(DOWN * 3.2))
            self.add(lab)
            line.set_stroke(colorize(len(new)), widths[o])
            glowl.set_stroke(colorize(len(new)), widths[o] * 4, 0.12)
            self.sfx("shatter", 392.0 * 2 ** ((o - 1) * 4 / 12))
            num.set_value(len(new))
            self.play(tr.animate.set_value(1.0), frame.animate.increment_theta(spin * 0.6),
                      run_time=2.4 if o < 4 else 3.0, rate_func=smooth)
            holder.clear_updaters()
            self.remove(holder, tr)
            self.play(frame.animate.increment_theta(spin * 0.35), run_time=1.0, rate_func=linear)
        self.remove(lab)
        self.sfx("win", 523.25)
        pay = self.payoff("YES! One line, 4,096 corners", 46, y=-3.15)
        sub = self.hud(T("It never crosses itself", 36, GOLD).move_to(DOWN * 3.65))
        self.play(FadeIn(sub), frame.animate.increment_theta(spin * 0.3), run_time=0.5, rate_func=linear)
        self.play(frame.animate.increment_theta(spin * 1.0).set_phi(50 * DEG), run_time=3.0, rate_func=smooth)
        self.meta = dict(order=4)
