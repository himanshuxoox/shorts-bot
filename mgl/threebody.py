"""
"3 suns. One gets thrown out. Pick a color!" — the three-body problem. Three stars start at
rest (zero total momentum) and pull on each other with Newton's gravity. They dance, swap
partners, almost collide… until one of them is flung out into space and the other two pair
up. High-accuracy integration (DOP853). The camera zooms out to follow the escape.
"""
import math

import numpy as np
from scipy.integrate import solve_ivp

from base import *

NAMES = [("RED", "#FF4D6D"), ("BLUE", "#4D8DFF"), ("GOLD", "#FFD24A")]


def deriv(m):
    def f(t, y):
        p = y[:6].reshape(3, 2)
        a = np.zeros((3, 2))
        for i in range(3):
            for j in range(3):
                if i != j:
                    d = p[j] - p[i]
                    r = math.sqrt(d @ d + 1e-6)
                    a[i] += m[j] * d / r ** 3
        return np.concatenate([y[6:], a.ravel()])
    return f


def escaped(m, y):
    """index of a body that is unbound and far from the other two, else None"""
    p, v = y[:6].reshape(3, 2), y[6:].reshape(3, 2)
    for i in range(3):
        j, k = [q for q in range(3) if q != i]
        M = m[j] + m[k]
        cp = (m[j] * p[j] + m[k] * p[k]) / M
        cv = (m[j] * v[j] + m[k] * v[k]) / M
        d = np.linalg.norm(p[i] - cp)
        mu = m[i] * M / (m[i] + M)
        E = 0.5 * mu * np.sum((v[i] - cv) ** 2) - m[i] * M / d
        if d > 6.0 and E > 0:
            return i
    return None


class ThreeBody(ShortScene):
    def construct(self):
        rng = self.rng
        for _try in range(80):
            m = np.array(rng.sample([3.0, 4.0, 5.0], 3))
            pts = np.array([[rng.uniform(-2, 2), rng.uniform(-2.5, 2.5)] for _ in range(3)])
            pts -= (m[:, None] * pts).sum(0) / m.sum()
            # avoid starts where two stars sit almost on top of each other
            if min(np.linalg.norm(pts[i] - pts[j]) for i in range(3) for j in range(i)) < 1.4:
                continue
            y0 = np.concatenate([pts.ravel(), np.zeros(6)])
            sol = solve_ivp(deriv(m), (0, 80), y0, method="DOP853", rtol=1e-10, atol=1e-10, dense_output=True)
            tt = np.linspace(0, 80, 1601)
            esc_t, who = None, None
            for t in tt:
                w = escaped(m, sol.sol(t))
                if w is not None:
                    esc_t, who = t, w
                    break
            if esc_t is not None and 22 <= esc_t <= 65:
                break
        T_SIM = esc_t + 6.0
        VID = 21.0                                  # video seconds for the whole simulation
        fps = self.camera.fps
        ts = np.linspace(0, T_SIM, int(VID * fps) + 1)
        Y = sol.sol(ts)
        P = Y[:6].T.reshape(-1, 3, 2)

        self.grid(0.06)
        self.question("3 suns. One gets thrown out.", 46, y=3.35)
        self.add(T("Pick a color!", 46, GOLD).move_to(UP * 2.8))
        legend = VGroup(*[T(n, 34, c) for n, c in NAMES]).arrange(RIGHT, buff=0.45).move_to(UP * 2.3)
        self.add(legend)
        cols = [c for _, c in NAMES]
        stars = VGroup()
        for i in range(3):
            r = 0.035 + 0.011 * m[i]
            core = Dot(radius=r, fill_color=WHITE)
            halo = Dot(radius=r * 2.6, fill_color=cols[i]).set_opacity(0.25)
            halo2 = Dot(radius=r * 1.6, fill_color=cols[i]).set_opacity(0.6)
            stars.add(VGroup(halo, halo2, core))
        trails = VGroup(*[VMobject().set_stroke(cols[i], 4) for i in range(3)])
        glows = VGroup(*[VMobject().set_stroke(cols[i], 14, 0.12) for i in range(3)])
        mass_lab = VGroup(*[VMobject() for i in range(3)])
        self.add(glows, trails, stars)
        view = dict(scale=0.8, center=np.zeros(2))
        t0 = self.time
        TRAIL = int(3.2 * fps)

        def to_screen(p2):
            q = (p2 - view["center"]) * view["scale"]
            return np.array([q[..., 0], q[..., 1] - 0.35, np.zeros(q.shape[:-1])]).T if p2.ndim == 1 else \
                np.stack([q[..., 0], q[..., 1] - 0.35, np.zeros(q.shape[:-1])], -1)

        def upd(_m, dt=0):
            i = min(len(P) - 1, int((self.time - t0) * fps))
            p = P[i]
            # camera: keep everything in view, smoothly
            com = (m[:, None] * p).sum(0) / m.sum()
            ext = np.abs(p - com).max() + 0.6
            target = min(0.85, 1.95 / ext)
            view["scale"] += (target - view["scale"]) * 0.08
            view["center"] = view["center"] + (com - view["center"]) * 0.08
            for k in range(3):
                pos = to_screen(p[k])
                stars[k].move_to(pos)
                seg = P[max(0, i - TRAIL): i + 1, k]
                if len(seg) > 1:
                    S = to_screen(seg)
                    trails[k].set_points_as_corners(S)
                    npts = len(trails[k].get_points())
                    trails[k].set_stroke(cols[k], width=np.linspace(0.3, 7, npts).tolist(),
                                         opacity=np.linspace(0.0, 1.0, npts).tolist())
                    glows[k].set_points(trails[k].get_points())
                    glows[k].set_stroke(cols[k], width=np.linspace(1, 22, npts).tolist(),
                                        opacity=np.linspace(0.0, 0.14, npts).tolist())

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # sound: a soft whoosh tick at every close encounter
        d = np.min(np.stack([np.linalg.norm(P[:, a] - P[:, b], axis=1) for a, b in ((0, 1), (0, 2), (1, 2))], 1), 1)
        for i in range(1, len(d) - 1):
            if d[i] < d[i - 1] and d[i] < d[i + 1] and d[i] < 1.2:
                self.sfx("pluck", 392.0 * 2 ** (rng.choice([0, 3, 5, 7, 10, 12]) / 12), at=t0 + i / fps)
        t_esc_video = esc_t / T_SIM * VID
        self.sfx("shatter", 330.0, at=t0 + t_esc_video)
        self.wait(t_esc_video)
        name, col = NAMES[who]
        out = T(f"{name} got thrown out!", 50, col).set_max_width(4.1).move_to(DOWN * 2.9)
        self.play(FadeIn(out, scale=1.5), run_time=0.3)
        self.wait(max(0.1, VID - t_esc_video - 0.3))
        holder.clear_updaters()
        self.sfx("win", 523.25)
        self.payoff("Did you pick the right one?", 44, y=-3.45, color=WHITE_)
        self.wait(2.0)
        self.meta = dict(masses=m.tolist(), esc_t=esc_t, who=name)
