"""
"Turn by the same angle every seed. Which angle makes a sunflower?" Seed n sits at distance √n
and angle n × (angle). 90° gives 4 straight arms, 137° gives spiral arms with gaps… and the
golden angle 137.5° packs them PERFECTLY. Then the flat sunflower lifts into a 3D dome (a pine
cone) and the camera circles it.
"""
import math

import numpy as np

from base import *

N = 1400
GOLDEN = 360 * (1 - 1 / ((1 + 5 ** 0.5) / 2))         # 137.5077…°


class Sunflower3D(ShortScene):
    HUD_FIXED = True

    def construct(self):
        rng = self.rng
        h0 = rng.random()
        n_idx = np.arange(1, N + 1)
        rad = 2.0 * np.sqrt(n_idx / N)
        rgba = hsl_rgba(h0 + 0.7 * n_idx / N, 0.9, 0.6)
        frame = self.frame
        frame.set_height(8.0)
        self.grid(0.06)
        self.question("Turn every seed by the same angle…", 44, y=3.38)
        sub = self.hud(T("Which angle makes a sunflower?", 40, GOLD).set_max_width(4.2).move_to(UP * 2.86))
        self.add(sub)
        grp, num = self.counter("angle = ", 90.0, y=2.36, size=46, decimals=1)
        deg = self.hud(T("°", 50, GOLD))
        deg.add_updater(lambda m: m.next_to(num, RIGHT, buff=0.04, aligned_edge=UP))
        self.add(deg)
        dots = DotCloud(np.zeros((N, 3)), radius=0.045)
        dots.set_glow_factor(0.5)
        self.add(dots)
        ang = ValueTracker(90.0)
        shown = ValueTracker(2.0)
        lift = ValueTracker(0.0)
        C = DOWN * 0.15

        def layout():
            a = math.radians(ang.get_value())
            th = n_idx * a
            x, y = rad * np.cos(th), rad * np.sin(th)
            L = lift.get_value()
            z = L * 1.9 * (1 - (rad / 2.0) ** 2)                 # dome
            return np.stack([x, y, z], 1) + C

        def upd(_m, dt=0):
            k = int(min(N, shown.get_value()))
            P = layout()
            P[k:] = P[k - 1] if k > 0 else C
            dots.set_points(P)
            col = rgba.copy()
            col[k:, 3] = 0.0
            dots.set_rgba_array(col)
            num.set_value(ang.get_value())
            r = 0.045 * (1 - 0.35 * lift.get_value())
            dots.set_radius(r)

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder, ang, shown, lift)

        def say(s, col=WHITE_, size=46):
            return self.hud(T(s, size, col).set_max_width(4.2).move_to(DOWN * 3.2))

        # 1) 90°: seeds appear one by one -> 4 straight arms
        for q in range(16):
            self.sfx("tick", 700 + 30 * q, at=self.time + 0.15 * q)
        self.play(shown.animate.set_value(N), run_time=2.6, rate_func=lambda a: a ** 1.6)
        lab = say("90° → just 4 lines")
        self.sfx("bell", 440.0)
        self.play(FadeIn(lab), run_time=0.25)
        self.wait(0.6)
        # 2) sweep to 137°: arms twist into spirals with gaps
        self.remove(lab)
        lab = say("137°…", GOLD)
        self.add(lab)
        self.sfx("chime", 523.25)
        self.play(ang.animate.set_value(137.0), run_time=3.2, rate_func=smooth)
        lab2 = say("137° → spirals with GAPS")
        self.remove(lab)
        lab = lab2
        self.play(FadeIn(lab), run_time=0.25)
        self.wait(0.7)
        # 3) the golden angle
        self.remove(lab)
        self.sfx("chime", 659.25)
        self.play(ang.animate.set_value(GOLDEN), run_time=1.6, rate_func=smooth)
        lab = say("137.5° → PERFECT sunflower!", GOLD, 44)
        self.sfx("win", 523.25)
        self.play(FadeIn(lab, scale=1.3), run_time=0.3)
        self.wait(1.2)
        # 4) 3D: lift into a dome, circle it
        self.remove(lab)
        lab = say("…and in 3D it's a pine cone")
        self.play(FadeIn(lab), run_time=0.3)
        self.play(lift.animate.set_value(1.0), frame.animate.reorient(-20, 62, 0), run_time=2.4, rate_func=smooth)
        self.play(frame.animate.increment_theta(1.4), run_time=3.2, rate_func=linear)
        self.remove(lab)
        self.payoff("The GOLDEN angle", 54, y=-3.15)
        sub2 = self.hud(T("That's how sunflowers grow", 36, WHITE_).set_max_width(4.2).move_to(DOWN * 3.65))
        self.play(FadeIn(sub2), frame.animate.increment_theta(0.3), run_time=0.5, rate_func=linear)
        self.play(frame.animate.increment_theta(0.8), run_time=1.8, rate_func=linear)
        holder.clear_updaters()
        self.meta = dict(n=N)
