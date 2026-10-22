"""
"What does × 2 draw?" — 240 dots on a circle; dot n is joined to dot (n × k) mod 240.
Guess-and-reveal: ×2 draws a heart (cardioid), ×3 → 2 petals, ×4 → 3, ×5 → 4 …
"So ×10 = ?" (3-2-1) → 9 petals. Then k flows on through stars and flowers while the whole
pattern slowly turns. All lines are drawn as ONE glowing path (fast to render).
"""
import math

import numpy as np

from base import *

N = 240
R = 1.95
C = DOWN * 0.3


def segments_path(A, B):
    """points for many separate straight lines in ONE VMobject (ManimGL path-break encoding)."""
    n = len(A)
    M = (A + B) / 2
    pts = np.empty((4 * n - 1, 3))
    pts[0::4] = A
    pts[1::4] = M
    pts[2::4] = B
    pts[3::4] = B[:-1]
    return pts


class TimesTable(ShortScene):
    def construct(self):
        rng = self.rng
        self.grid(0.07)
        q = self.question("What does × 2 draw?", 54, y=3.3)
        grp, num = self.counter("k = ", 2.0, y=2.68, size=50, decimals=2)
        ring = glow(Circle(radius=R).move_to(C).set_stroke(CYAN, 4), CYAN, 4)
        h0 = rng.random()
        base_rgba = np.array([[*Color(hsl=((h0 + i / N) % 1, 0.95, 0.62)).get_rgb(), 0.85] for i in range(N)])
        rgba = np.repeat(base_rgba, 4, axis=0)[: 4 * N - 1]
        glow_rgba = rgba.copy()
        glow_rgba[:, 3] = 0.13
        lines = VMobject().set_stroke(WHITE, 1.7)
        halo = VMobject().set_stroke(WHITE, 7)
        dots = DotCloud(np.zeros((N, 3)), radius=0.011, color=WHITE).set_opacity(0.85)
        self.add(halo, lines, ring, dots)

        # big k values that suddenly make clean pictures (N = 240): an eye, a ring, graph paper,
        # and 239 (= -1) where every single line is flat
        hops = rng.choice([[61, 81, 119, 239], [61, 121, 119, 239], [81, 61, 119, 239]])
        k_end = hops[-1]
        spin = 0.0
        # (time, k) keyframes — pauses on the "petal" numbers, then a long flow to k_end
        keys = [(0.0, 2.0), (3.6, 2.0), (4.6, 3.0), (5.8, 3.0), (6.8, 4.0), (8.0, 4.0), (9.0, 5.0),
                (12.3, 5.0), (13.3, 10.0), (15.0, 10.0), (16.4, hops[0]), (17.9, hops[0]),
                (19.1, hops[1]), (20.5, hops[1]), (21.8, hops[2]), (23.6, hops[2]), (24.9, hops[3])]
        tk = np.array([a for a, _ in keys])
        kv = np.array([b for _, b in keys])
        t0 = self.time
        state = dict(drawn=0.0)

        def kval(t):
            u = np.clip(t, tk[0], tk[-1])
            i = min(len(tk) - 2, int(np.searchsorted(tk, u, side="right")) - 1)
            f = (u - tk[i]) / (tk[i + 1] - tk[i])
            f = f * f * (3 - 2 * f)
            return kv[i] + (kv[i + 1] - kv[i]) * f

        def upd(_m, dt=0):
            t = self.time - t0
            k = kval(t)
            num.set_value(k)
            rot = spin * max(0.0, t - 13.0)
            ang = np.pi / 2 - 2 * np.pi * np.arange(N) / N + rot
            P = np.stack([R * np.cos(ang), R * np.sin(ang), np.zeros(N)], 1) + C
            a2 = np.pi / 2 - 2 * np.pi * ((np.arange(N) * k) % N) / N + rot
            Q = np.stack([R * np.cos(a2), R * np.sin(a2), np.zeros(N)], 1) + C
            same = np.linalg.norm(P - Q, axis=1) < 1e-3
            Q[same] += np.array([1e-3, 0, 0])
            m = max(2, int(N * min(1.0, t / 2.4)))           # lines appear one by one at the start
            Q[m:] = P[m:] + np.array([1e-3, 0, 0])
            pts = segments_path(P, Q)
            lines.set_points(pts)
            halo.set_points(pts)
            lines.set_rgba_array(rgba[: len(pts)], name="stroke_rgba")
            halo.set_rgba_array(glow_rgba[: len(pts)], name="stroke_rgba")
            dots.set_points(P)

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        for i in range(12):                                  # drawing-in ticks
            self.sfx("tick", 700 + 40 * i, at=t0 + 0.2 * i)

        def say(s, col=GOLD, size=46):
            lab = T(s, size, col).set_max_width(4.1).move_to(DOWN * 3.05)
            return lab

        self.wait(2.7)
        lab = say("A heart! (cardioid)")
        self.sfx("bell", 523.25)
        self.play(FadeIn(lab, scale=1.4), run_time=0.3)
        q_new = T("Join dot n to dot n × k", 50).set_max_width(4.1).move_to(q)
        self.play(FadeTransform(q, q_new), run_time=0.4)
        self.wait(1.2)
        for kk, at in ((3, 4.6), (4, 6.8), (5, 9.0)):
            self.wait(max(0.0, at - (self.time - t0)))
            new = say(f"× {kk}  →  {kk - 1} petals")
            self.sfx("bell", 523.25 * 2 ** ([0, 4, 7, 12][kk - 2] / 12))
            self.play(Transform(lab, new), run_time=0.25)
        self.wait(max(0.0, 9.8 - (self.time - t0)))
        guess = say("So × 10 = ? petals", WHITE_)
        self.play(Transform(lab, guess), run_time=0.25)
        for j, s in enumerate(["3", "2", "1"]):
            c = VGroup(Circle(radius=0.55).set_fill(BG, 0.85).set_stroke(GOLD, 4), T(s, 100, GOLD)).move_to(C)
            self.sfx("tick", 880.0)
            self.play(FadeIn(c, scale=1.6), run_time=0.15)
            self.wait(0.5)
            self.remove(c)
        self.wait(max(0.0, 13.3 - (self.time - t0)))
        ans = say("9 petals!")
        self.sfx("win", 659.25)
        self.play(Transform(lab, ans), run_time=0.25)
        self.wait(1.2)
        last = [10]

        def notes(_m, dt=0):
            ki = int(math.floor(kval(self.time - t0) + 1e-6))
            if ki > last[0] + 3:                                   # fast morphs: a quick run of notes
                self.sfx("tick", 700 + 4 * ki)
                last[0] = ki
        holder.add_updater(notes)
        names = {61: "an eye?", 81: "a ring", 121: "a star burst", 119: "GRAPH PAPER?!", 239: "every line FLAT?!"}
        for kk, at in zip(hops, (16.4, 19.1, 21.8, 24.9)):
            self.wait(max(0.0, at - (self.time - t0)))
            new = say(f"× {kk}  →  {names[kk]}", GOLD if kk != 239 else PINK)
            self.sfx("bell" if kk != 239 else "win", 523.25 * 2 ** ([0, 4, 7, 12][hops.index(kk)] / 12))
            self.remove(lab)
            lab = new
            self.play(FadeIn(lab, scale=1.3), run_time=0.25)
        self.wait(1.6)
        holder.clear_updaters()
        self.play(FadeOut(lab), run_time=0.25)
        self.payoff("Why?! Tell me below", 50, y=-3.05)
        self.wait(2.0)
        self.meta = dict(k_end=k_end)
