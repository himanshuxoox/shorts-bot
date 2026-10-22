"""
"24 metronomes. Nobody touches them." — spontaneous synchronisation. Metronomes stand on a
board that can slide a little. Each one starts at a random moment (chaos of clicks); the
tiny push each one gives the board nudges all the others (Kuramoto model), and after a few
seconds they all tick together. Arm colour = phase, so the rainbow turns into ONE colour.
"""
import math

import numpy as np

from base import *

ROWS, COLS_ = 6, 4


class Metronomes(ShortScene):
    def construct(self):
        rng = self.rng
        n = ROWS * COLS_
        fps = self.camera.fps
        T_RUN = 22.0
        w0 = 2 * math.pi * rng.uniform(0.95, 1.1)                      # ~1 swing per second
        nprng = np.random.default_rng(SEED)
        w = w0 * (1 + nprng.normal(0, 0.012, n))
        th0 = nprng.uniform(0, 2 * math.pi, n)
        K_final = rng.uniform(0.9, 1.3)

        def K_at(t):                         # coupling switches on smoothly after 2 s
            return K_final * min(1.0, max(0.0, (t - 2.0) / 4.0))

        steps = int(T_RUN * fps)
        sub = 8
        dt = 1 / fps / sub
        TH = np.empty((steps + 1, n))
        th = th0.copy()
        TH[0] = th
        t = 0.0
        for i in range(steps):
            for _ in range(sub):
                z = np.exp(1j * th).mean()
                th = th + dt * (w + K_at(t) * np.abs(z) * np.sin(np.angle(z) - th))
                t += dt
            TH[i + 1] = th
        R = np.abs(np.exp(1j * TH).mean(1))
        t_sync = float(np.argmax(R > 0.97) / fps) if (R > 0.97).any() else T_RUN - 4

        self.grid(0.06)
        self.question("24 metronomes. Nobody touches them.", 46, y=3.35)
        grp, num = self.counter("in sync (%): ", 0, y=2.78, size=44)
        # board + metronome bodies
        board = RoundedRectangle(width=4.3, height=4.65, corner_radius=0.12).set_fill("#1a2240", 0.9) \
            .set_stroke(CYAN, 3).move_to(DOWN * 0.45)
        rollers = VGroup(*[Circle(radius=0.09).set_fill(GREY_B, 1).set_stroke(WHITE, 1)
                           .move_to(board.get_bottom() + RIGHT * x + DOWN * 0.1) for x in (-1.6, -0.5, 0.5, 1.6)])
        cell_w, cell_h = 4.3 / COLS_, 4.65 / ROWS
        bases, arms, bobs = [], VGroup(), VGroup()
        bodies = VGroup()
        for r in range(ROWS):
            for c in range(COLS_):
                cx = -2.15 + cell_w * (c + 0.5)
                cy = -0.45 + 2.325 - cell_h * (r + 0.5)
                base = np.array([cx, cy - cell_h * 0.36, 0])
                body = Polygon(base + LEFT * 0.26, base + RIGHT * 0.26, base + UP * 0.62 + RIGHT * 0.1,
                               base + UP * 0.62 + LEFT * 0.1).set_fill("#2b3866", 1).set_stroke(WHITE, 1, 0.5)
                bodies.add(body)
                bases.append(base + UP * 0.05)
                arms.add(Line(base, base + UP * 0.65).set_stroke(WHITE, 4))
                bobs.add(Square(0.09).set_fill(WHITE, 1).set_stroke(width=0))
        rig = VGroup(board, bodies, arms, bobs)
        self.add(rollers, rig)
        bases = np.array(bases)
        L = cell_h * 0.78
        AMP = 0.5
        t0 = self.time
        shift = dict(x=0.0)

        def upd(_m, dt_=0):
            t = self.time - t0
            i = min(steps, int(t * fps))
            phase = TH[i]
            ang = AMP * np.sin(phase)
            # the board rocks with the mean push of all arms (visible once they are in sync)
            push = 0.05 * np.sin(phase).mean()
            rig.shift(RIGHT * (push - shift["x"]))
            shift["x"] = push
            for k in range(n):
                b = bases[k] + RIGHT * push
                tip = b + L * np.array([math.sin(ang[k]), math.cos(ang[k]), 0])
                col = Color(hsl=((phase[k] % (2 * math.pi)) / (2 * math.pi), 0.95, 0.62))
                arms[k].put_start_and_end_on(b, tip).set_stroke(col, 4)
                bobs[k].move_to(b + 0.62 * (tip - b)).set_fill(col)
            num.set_value(int(round(100 * R[i])))

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # clicks: whenever an arm passes the middle (phase crosses k*pi)
        k_prev = np.floor(TH[0] / math.pi)
        for i in range(1, steps + 1):
            k_now = np.floor(TH[i] / math.pi)
            for j in np.nonzero(k_now > k_prev)[0]:
                self.sfx("clack", 1500.0, at=t0 + i / fps)
            k_prev = k_now
        lab = T("Pure chaos…", 46, WHITE_).move_to(DOWN * 3.3)
        self.play(FadeIn(lab), run_time=0.3)
        self.wait(max(0.5, t_sync * 0.45))
        lab2 = T("…wait for it", 46, GOLD).move_to(DOWN * 3.3)
        self.play(FadeTransform(lab, lab2), run_time=0.3)
        lab = lab2
        self.wait(max(0.3, t_sync - (self.time - t0)))
        self.sfx("win", 523.25)
        lab3 = T("PERFECT SYNC!", 54, PINK).move_to(DOWN * 3.3)
        self.play(FadeTransform(lab, lab3), run_time=0.3)
        self.wait(max(0.1, T_RUN - 3.0 - (self.time - t0)))
        self.play(FadeOut(lab3), run_time=0.3)
        self.payoff("They synced by themselves", 44, y=-3.3)
        self.wait(max(0.1, T_RUN - (self.time - t0)))
        holder.clear_updaters()
        self.wait(0.8)
        self.meta = dict(t_sync=t_sync)
