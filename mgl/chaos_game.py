"""
"Pick a random corner. Jump halfway. Repeat." — the Chaos Game. Every dot is placed by pure
chance, yet after thousands of jumps a perfect fractal appears: the Sierpinski triangle,
a pentagon snowflake, a square "no-repeat" fractal or a hexagon flake (chosen per seed).
Dots are coloured by the corner they jumped towards, so the fractal comes out in rainbow.
"""
import math

import numpy as np

from base import *

C = DOWN * 0.25
R = 2.05

VARIANTS = {
    # sides, jump fraction (towards the corner), rule, name
    "triangle": (3, 0.5, None, "the Sierpinski triangle"),
    "pentagon": (5, 0.618, None, "a pentagon snowflake"),
    "square": (4, 0.5, "no_repeat", "a square fractal"),
    "hexagon": (6, 0.667, None, "a hexagon snowflake"),
}


def play_game(n_sides, frac, rule, n, rng):
    ang = np.pi / 2 + 2 * np.pi * np.arange(n_sides) / n_sides
    V = np.stack([R * np.cos(ang), R * np.sin(ang), np.zeros(n_sides)], 1)
    if n_sides == 3:
        V[:, 1] -= 0.35                                    # optical centring of the triangle
    P = np.empty((n, 3))
    K = np.empty(n, int)
    p = np.array([rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), 0.0])
    last = -1
    for i in range(n):
        k = rng.randrange(n_sides)
        while rule == "no_repeat" and k == last:
            k = rng.randrange(n_sides)
        p = p + (V[k] - p) * frac
        P[i] = p
        K[i] = k
        last = k
    return V + C, P + C, K


class ChaosGame(ShortScene):
    def construct(self):
        rng = self.rng
        kind = rng.choice(["triangle", "triangle", "pentagon", "square", "hexagon"])
        n_sides, frac, rule, name = VARIANTS[kind]
        N = 90000
        V, P, K = play_game(n_sides, frac, rule, N, rng)
        h0 = rng.random()
        corner_cols = [Color(hsl=((h0 + i / n_sides) % 1, 0.95, 0.62)) for i in range(n_sides)]
        rgba = np.array([[*c.get_rgb(), 1.0] for c in corner_cols])[K]

        self.grid(0.07)
        jump = "halfway" if abs(frac - 0.5) < 1e-6 else f"{round(frac * 100)}% of the way"
        rule_txt = " (never the same corner twice)" if rule else ""
        self.question("Pick a random corner.", 50, y=3.42)
        q2 = T(f"Jump {jump}. Repeat.", 44, WHITE_).set_max_width(4.1).move_to(UP * 2.92)
        self.add(q2)
        grp, num = self.counter("dots: ", 0, y=2.38, size=44)
        corners = VGroup(*[glow(Dot(V[i], radius=0.075, fill_color=corner_cols[i]), corner_cols[i], 2)
                           for i in range(n_sides)])
        self.add(corners)
        if rule:
            note = T("never the same corner twice", 30, GOLD).move_to(DOWN * 2.75)
            self.add(note)

        cloud = DotCloud(P[:1], radius=0.03)
        cloud.set_glow_factor(0.4)
        self.add(cloud)

        # --- phase 1: slow, show each jump (arrow from the current point to the chosen corner)
        cur = Dot(P[0] - (P[0] - (P[0] - (V[K[0]] - P[0]) * frac / (1 - frac))) * 0, radius=0.06, fill_color=WHITE)
        start_pt = (P[0] - V[K[0]] * frac) / (1 - frac)           # where the very first jump started
        cur.move_to(start_pt)
        self.add(cur)
        shown = 0
        for i in range(7):
            k = K[i]
            flash = Circle(radius=0.2).move_to(V[k]).set_stroke(corner_cols[k], 6)
            line = DashedLine(cur.get_center(), V[k], dash_length=0.06).set_stroke(corner_cols[k], 3, 0.8)
            self.sfx("pluck", 392.0 * 2 ** ([0, 4, 7, 12, 16, 19][k % 6] / 12))
            self.play(FadeIn(line), ShowCreationThenFadeOut(flash), run_time=0.3)
            self.play(cur.animate.move_to(P[i]), run_time=0.35)
            shown = i + 1
            cloud.set_points(P[:shown]).set_rgba_array(rgba[:shown]).set_radius(0.05)
            num.set_value(shown)
            self.remove(line)
        self.remove(cur)

        # --- phase 2+3: accelerate; dots appear faster and faster, the fractal shows up
        t0 = self.time
        DUR = 15.0
        say = {}

        def count_at(t):
            if t < 5.0:                                    # still looks random: 7 -> 250 dots
                return int(7 + 243 * (t / 5.0) ** 1.5)
            u = min(1.0, (t - 5.0) / (DUR - 5.0))           # then the fractal pours in
            return int(250 * (N / 250) ** (u ** 0.8))

        def upd(_m, dt=0):
            t = self.time - t0
            n = max(7, count_at(t))
            cloud.set_points(P[:n]).set_rgba_array(rgba[:n])
            cloud.set_radius(float(np.clip(0.05 / (1 + n / 600) ** 0.4, 0.012, 0.05)))
            num.set_value(n)

        holder = Mobject()
        holder.add_updater(upd)
        self.add(holder)
        # ticks: one per new dot while slow, then a rising whoosh of ticks
        last = 7
        for f in range(1, int(DUR * 30)):
            n = count_at(f / 30)
            if n > last:
                self.sfx("tick", 600 + 900 * f / (DUR * 30), at=t0 + f / 30)
                last = n
        lab = T("Looks random…", 44, WHITE_).move_to(DOWN * 3.2)
        self.play(FadeIn(lab), run_time=0.3)
        self.wait(4.4)
        lab2 = T("…or is it?", 44, GOLD).move_to(DOWN * 3.2)
        self.play(Transform(lab, lab2), run_time=0.3)
        self.wait(max(0.1, DUR - (self.time - t0)))
        holder.clear_updaters()
        self.play(FadeOut(lab), run_time=0.3)
        self.sfx("win", 523.25)
        self.play(cloud.animate.set_glow_factor(0.9), corners.animate.set_opacity(0.4), run_time=0.6)
        self.payoff("Pure chance drew THIS", 46, y=-3.05)
        sub = T(name, 32, WHITE_).set_max_width(4.0).move_to(DOWN * 3.55)
        self.play(FadeIn(sub), run_time=0.3)
        self.wait(2.2)
        self.meta = dict(kind=kind)
