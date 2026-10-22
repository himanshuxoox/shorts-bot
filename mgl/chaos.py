"""
"Chaos" — 60 double pendulums released at almost exactly the same angle (each 0.0001° apart).
For a few seconds they move as ONE rainbow pendulum… then they suddenly explode into chaos.
Real double-pendulum equations, RK4. A soft note while together, a crash when they split.
"""
import math

import numpy as np

from base import *

G = 9.81
PIVOT = UP * 0.05
L_DRAW = 1.05


def derivs(s):
    """s: (n, 4) = th1, th2, w1, w2 for equal masses / lengths (L = 1, m = 1)."""
    t1, t2, w1, w2 = s.T
    d = t1 - t2
    den = 3 - np.cos(2 * d)
    a1 = (-3 * G * np.sin(t1) - G * np.sin(t1 - 2 * t2) - 2 * np.sin(d) * (w2 ** 2 + w1 ** 2 * np.cos(d))) / den
    a2 = (2 * np.sin(d) * (2 * w1 ** 2 + 2 * G * np.cos(t1) + w2 ** 2 * np.cos(d))) / den
    return np.stack([w1, w2, a1, a2], 1)


def integrate(s0, T, fps, sub=40, speed=1.0):
    dt = speed / fps / sub
    out = [s0.copy()]
    s = s0.copy()
    for _ in range(int(T * fps)):
        for _ in range(sub):
            k1 = derivs(s); k2 = derivs(s + dt / 2 * k1); k3 = derivs(s + dt / 2 * k2); k4 = derivs(s + dt * k3)
            s = s + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        out.append(s.copy())
    return np.array(out)


class Chaos(ShortScene):
    def construct(self):
        rng = self.rng
        n = rng.choice([40, 60, 80])
        fps = self.camera.fps
        # pick start angles + spacing so the pendulums split after 6.5-9.5 s (with a tiny spacing)
        for _try in range(60):
            th1 = rng.uniform(1.9, 2.6) * rng.choice([-1, 1])
            th2 = th1 + rng.uniform(-0.6, 0.6)
            eps = rng.choice([1e-3, 1e-4, 1e-5])
            probe = np.zeros((2, 4))
            probe[:, 0] = [th1, th1 + eps * (n - 1) * math.pi / 180]
            probe[:, 1] = th2
            tr = integrate(probe, 12, 30, sub=40, speed=0.85)
            xx = np.sin(tr[:, :, 0]) + np.sin(tr[:, :, 1])
            yy = -np.cos(tr[:, :, 0]) - np.cos(tr[:, :, 1])
            d = np.hypot(xx[:, 0] - xx[:, 1], yy[:, 0] - yy[:, 1])
            ts = np.argmax(d > 0.6) / 30 if (d > 0.6).any() else 99
            if 6.5 <= ts <= 9.5:
                break
        s0 = np.zeros((n, 4))
        s0[:, 0] = th1 + eps * np.arange(n) * math.pi / 180      # eps degrees apart
        s0[:, 1] = th2
        T_run = 27.0
        traj = integrate(s0, T_run, fps, sub=max(8, int(1200 / fps)), speed=0.85)
        # moment they visibly split: spread of the second bob > 0.25
        x2 = np.sin(traj[:, :, 0]) + np.sin(traj[:, :, 1])
        y2 = -np.cos(traj[:, :, 0]) - np.cos(traj[:, :, 1])
        spread = np.hypot(x2.std(1), y2.std(1))
        split_i = int(np.argmax(spread > 0.25)) if (spread > 0.25).any() else len(spread) - 1
        t_split = split_i / fps

        self.grid(0.07)
        self.question(f"{n} pendulums, {eps:.{int(round(-math.log10(eps)))}f}° apart", 46, y=3.3)
        grp, num = self.counter("time: ", 0.0, y=2.7, size=44, decimals=1)
        h0 = rng.random()
        cols = [Color(hsl=((h0 + 0.8 * i / n) % 1, 0.95, 0.6)) for i in range(n)]
        arms = VGroup(*[VMobject().set_stroke(cols[i], 3.2, 0.55) for i in range(n)])
        tails = VGroup(*[VMobject().set_stroke(cols[i], 2.4, 0.45) for i in range(n)])
        bobs = DotCloud(np.zeros((n, 3)), radius=0.05)
        bobs.set_color(cols)
        bobs.set_glow_factor(0.6)
        pivot = Dot(PIVOT, radius=0.05, fill_color=WHITE)
        self.add(tails, arms, bobs, pivot)
        t0 = self.time
        TAIL = int(0.5 * fps)

        def pts_at(i):
            s = traj[min(i, len(traj) - 1)]
            p1 = PIVOT + L_DRAW * np.stack([np.sin(s[:, 0]), -np.cos(s[:, 0]), np.zeros(n)], 1)
            p2 = p1 + L_DRAW * np.stack([np.sin(s[:, 1]), -np.cos(s[:, 1]), np.zeros(n)], 1)
            return p1, p2

        hist = []

        def upd(_m, dt=0):
            t = self.time - t0
            i = int(round(t * fps))
            num.set_value(t)
            p1, p2 = pts_at(i)
            hist.append(p2)
            del hist[:-TAIL]
            H = np.array(hist)
            for k in range(n):
                arms[k].set_points_as_corners([PIVOT, p1[k], p2[k]])
                if len(H) > 1:
                    tails[k].set_points_as_corners(H[:, k])
            bobs.set_points(p2)

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # sound: soft ticks while together, a crash + chaos plucks after the split
        for q in np.arange(0.5, t_split, 0.5):
            self.sfx("tick", 659.25, at=t0 + q)
        self.sfx("shatter", 392.0, at=t0 + t_split)
        for q in np.arange(t_split + 0.25, T_run - 1, 0.25):
            self.sfx("tick", float(rng.choice([523.25, 587.33, 659.25, 783.99, 880.0, 1046.5])), at=t0 + q)
        self.wait(t_split)
        boom = T("CHAOS!", 64, PINK).move_to(DOWN * 2.6)
        self.play(FadeIn(boom, scale=1.8), run_time=0.25)
        self.wait(1.2)
        self.play(FadeOut(boom), run_time=0.3)
        self.wait(max(0.1, T_run - 3.2 - (self.time - t0)))
        self.payoff("Tiny difference. Total chaos.", 44, y=-3.15, color=WHITE_)
        self.wait(2.2)
        holder.clear_updaters()
        self.meta = dict(n=n, eps=eps, t_split=t_split)
