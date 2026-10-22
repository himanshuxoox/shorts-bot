"""
"The butterfly effect" — 4,000 points start inside a tiny ball (almost the same starting point)
and follow the Lorenz equations (a simple weather model). They stretch into a ribbon and then
fill a 3D butterfly, while the camera slowly turns around it. RK4, 3D in ManimGL.
"""
import math

import numpy as np

from base import *

SIGMA, RHO, BETA = 10.0, 28.0, 8.0 / 3.0


def f(p):
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    return np.stack([SIGMA * (y - x), x * (RHO - z) - y, x * y - BETA * z], 1)


class Lorenz(ShortScene):
    def construct(self):
        rng = self.rng
        n = 4000
        fps = self.camera.fps
        T_run = 25.0
        speed = 0.6                                       # model time per video second
        nprng = np.random.default_rng(SEED)
        # pick a start whose dots split after 5-9 s and fill the butterfly by ~14 s (probe 200 dots)
        for _try in range(40):
            start = np.array([rng.uniform(-12, 12), rng.uniform(-12, 12), rng.uniform(15, 35)])
            r0 = rng.choice([0.01, 0.02])
            pr = start + nprng.normal(0, r0, (200, 3))
            dtp = speed / 30 / 4
            sp = []
            for _i in range(16 * 30):
                for _ in range(4):
                    k1 = f(pr); k2 = f(pr + dtp / 2 * k1); k3 = f(pr + dtp / 2 * k2); k4 = f(pr + dtp * k3)
                    pr = pr + dtp / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
                sp.append(np.linalg.norm(pr.std(0)))
            sp = np.array(sp)
            ts = np.argmax(sp > 1.0) / 30 if (sp > 1.0).any() else 99
            if 5.0 <= ts <= 9.0 and sp[-1] > 12:
                break
        pts = start + nprng.normal(0, r0, (n, 3))
        steps = int(T_run * fps)
        sub = 6
        dt = speed / fps / sub
        traj = np.empty((steps + 1, n, 3), np.float32)
        traj[0] = pts
        p = pts.copy()
        for i in range(steps):
            for _ in range(sub):
                k1 = f(p); k2 = f(p + dt / 2 * k1); k3 = f(p + dt / 2 * k2); k4 = f(p + dt * k3)
                p = p + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            traj[i + 1] = p

        SC = 0.072
        CEN = np.array([0, 0, 25.0])

        view = dict(a=0.0)

        def to_world(q):
            """turn the model about its vertical (z) axis by view['a'], then look from the front"""
            q = (q - CEN) * SC
            ca, sa = math.cos(view["a"]), math.sin(view["a"])
            X = q[..., 0] * ca + q[..., 1] * sa
            D = -q[..., 0] * sa + q[..., 1] * ca
            return np.stack([X, q[..., 2] - 0.2 + 0.0 * D, D * 0.0], -1)

        h0 = rng.random()
        dirv = nprng.normal(0, 1, 3)
        order = np.argsort((pts - start) @ dirv)          # colour bands across the tiny ball
        cols = np.empty(n, object)
        for j, i in enumerate(order):
            cols[i] = Color(hsl=((h0 + 0.85 * j / n) % 1, 0.95, 0.62))
        cloud = DotCloud(to_world(traj[0]), radius=0.018)
        cloud.set_color(list(cols))
        cloud.set_glow_factor(0.5)
        tail_clouds = [DotCloud(to_world(traj[0]), radius=0.010) for _ in range(3)]
        for k, tcl in enumerate(tail_clouds):
            tcl.set_color(list(cols)).set_opacity(0.35 - 0.1 * k)
        self.add(*tail_clouds, cloud)

        self.grid(0.06)
        q = self.question("4,000 dots. Almost the same start.", 44, y=3.3)
        grp, num = self.counter("time: ", 0.0, y=2.7, size=44, decimals=1)
        t0 = self.time
        yaw0 = rng.uniform(-40, 40)
        spin = rng.choice([-1, 1]) * 9.0

        spread_all = np.linalg.norm(traj.std(1), axis=1)
        smax = spread_all.max()

        def upd(_m, dt_=0):
            t = self.time - t0
            i = min(steps, int(t * fps))
            view["a"] = math.radians(30 + 15 * math.sin(t / 5.0 + yaw0 / 40))  # sway; ~45° = wings widest apart
            cloud.set_points(to_world(traj[i]))
            u = min(1.0, spread_all[i] / (0.5 * smax))
            cloud.set_radius(0.06 * (1 - u) + 0.02 * u)
            cloud.set_glow_factor(1.2 * (1 - u) + 0.6 * u)
            for k, tcl in enumerate(tail_clouds):
                tcl.set_points(to_world(traj[max(0, i - 2 * (k + 1))]))
            num.set_value(t)

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # spread of the cloud -> moments for labels / sounds
        spread = np.linalg.norm(traj.std(1), axis=1)
        t_split = float(np.argmax(spread > 1.0) / fps)
        t_fill = float(np.argmax(spread > 0.7 * spread.max()) / fps)
        for qq in np.arange(0.5, T_run, 0.5):
            lvl = min(1.0, spread[min(steps, int(qq * fps))] / 8)
            self.sfx("tick", 440 * 2 ** (round(lvl * 12) / 12), at=t0 + qq)
        self.wait(max(0.5, t_split))
        lab = T("…they split apart", 44, WHITE_).set_max_width(4.1).move_to(DOWN * 3.05)
        self.sfx("bell", 523.25)
        self.play(FadeIn(lab, scale=1.3), run_time=0.3)
        self.wait(max(0.5, t_fill - (self.time - t0)))
        lab2 = T("…and draw a BUTTERFLY", 44, GOLD).set_max_width(4.1).move_to(DOWN * 3.05)
        self.sfx("win", 523.25)
        self.play(Transform(lab, lab2), run_time=0.35)
        self.wait(max(0.1, T_run - 2.8 - (self.time - t0)))
        self.play(FadeOut(lab), run_time=0.3)
        self.payoff("The butterfly effect", 50, y=-3.05)
        self.wait(2.2)
        holder.clear_updaters()
        self.meta = dict(t_split=t_split, t_fill=t_fill)
