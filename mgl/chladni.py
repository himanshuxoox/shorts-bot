"""
"Sand on a metal plate. Now add sound…" — Chladni patterns. The plate vibrates in one of its
modes; sand is shaken away from the moving parts and collects on the still lines (nodes).
Each time the pitch goes up, the sand jumps and draws a new, more detailed pattern.
Plate mode: u = cos(nπx)cos(mπy) − cos(mπx)cos(nπy) on a square plate.
"""
import math

import numpy as np

from base import *

HALF = 2.0
C = np.array([0, -0.35, 0])


def mode(n, m, x, y):
    # x, y in [-1, 1] -> plate coords [0, 1]
    X, Y = (x + 1) / 2, (y + 1) / 2
    return np.cos(n * np.pi * X) * np.cos(m * np.pi * Y) - np.cos(m * np.pi * X) * np.cos(n * np.pi * Y)


class Chladni(ShortScene):
    def construct(self):
        rng = self.rng
        nprng = np.random.default_rng(SEED)
        seqs = [[(1, 2), (1, 4), (2, 5), (3, 6), (4, 7)], [(1, 3), (2, 4), (1, 6), (3, 7), (5, 8)],
                [(1, 2), (2, 3), (3, 5), (2, 7), (5, 9)]]
        seq = rng.choice(seqs)
        N = 22000
        P = nprng.uniform(-1, 1, (N, 2))
        sand_col = rng.choice(["#FFE3A3", "#FFF1C9", "#A8EEFF", "#FFC2E2"])
        self.grid(0.06)
        self.question("Sand on a metal plate…", 52, y=3.35)
        grp, num = self.counter("sound (Hz): ", 0, y=2.8, size=46)
        hz = T(" Hz", 46 * 1.2, GOLD)
        plate = Square(2 * HALF).move_to(C).set_fill("#0b1020", 1).set_stroke(GREY_B, 3)
        rim = glow(Square(2 * HALF).move_to(C).set_stroke(CYAN, 3), CYAN, 3)
        bolt = Dot(C, radius=0.07, fill_color=GREY_B)
        sand = DotCloud(np.zeros((N, 3)), radius=0.0145, color=sand_col)
        sand.set_glow_factor(0.45)
        self.add(plate, rim, sand, bolt)
        state = dict(n=0, m=0, amp=0.0, f=0)
        fps = self.camera.fps

        def to_world(Q):
            return np.concatenate([Q * HALF, np.zeros((len(Q), 1))], 1) + C

        def upd(_m, dt=0):
            nonlocal P
            if state["n"]:
                u = np.abs(mode(state["n"], state["m"], P[:, 0], P[:, 1]))
                step = (0.09 * state["amp"] * u + 0.0015 * state["amp"])[:, None] * nprng.normal(0, 1, P.shape)
                P = P + step * (30 / fps)
                # bounce back inside the plate
                P = np.where(P > 1, 2 - P, P)
                P = np.where(P < -1, -2 - P, P)
            sand.set_points(to_world(P))
            # tiny shake of the plate while it sings
            jig = 0.006 * state["amp"] * math.sin(self.time * 90)
            sand.shift(UP * jig)

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        self.wait(1.0)
        q2 = T("Now add sound…", 46, GOLD).move_to(DOWN * 3.15)
        self.play(FadeIn(q2, scale=1.3), run_time=0.3)
        self.wait(0.5)
        self.remove(q2)
        stage_t = 3.6
        freqs = []
        for si, (n, m) in enumerate(seq):
            f = [220, 294, 392, 523, 659][si]                # the pitch you hear goes up every stage
            freqs.append(f)
            state.update(n=n, m=m, f=f)
            num.set_value(f)
            self.sfx("tone", f, at=self.time)
            # vibration: strong at first (sand jumps), then calmer so the lines get sharp
            amp = ValueTracker(1.6)
            amp.add_updater(lambda v: state.__setitem__("amp", v.get_value()))
            self.add(amp)
            self.play(amp.animate.set_value(0.35), run_time=stage_t, rate_func=lambda a: 1 - (1 - a) ** 2)
            self.remove(amp)
            if si == 1:
                lab = T("Higher pitch = more lines", 40, WHITE_).set_max_width(4.1).move_to(DOWN * 3.15)
                self.play(FadeIn(lab), run_time=0.25)
            if si == 3:
                self.play(FadeOut(lab), run_time=0.25)
        self.sfx("tone", 0.0, at=self.time)              # stop the tone
        state["amp"] = 0.0
        holder.clear_updaters()
        self.sfx("win", 523.25)
        self.payoff("Sound draws with sand!", 50, y=-3.15)
        self.wait(2.2)
        self.meta = dict(seq=seq, freqs=freqs)
