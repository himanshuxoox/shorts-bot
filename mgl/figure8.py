"""
"3 suns in a perfect figure 8… then a 4th sun arrives." The figure-eight orbit (Chenciner &
Montgomery, 2000): three equal suns chase each other along ONE figure-8 path forever. It loops twice,
drawing a perfect ∞. Then a 4th sun flies in, the dance breaks into chaos, and suns are thrown out.
Pick a color: who survives? Who is OUT is decided with the same careful test as the N-body game
(far from every other sun, moving away, and unbound), on the exact trajectory that is shown.
"""
import math, random

import numpy as np
from scipy.integrate import solve_ivp

from base import *
from nbody import COLORS, check_out

# the figure-eight initial conditions (G = m = 1), period ~6.3259
P8 = np.array([[0.97000436, -0.24308753], [-0.97000436, 0.24308753], [0.0, 0.0]])
V3 = np.array([-0.93240737, -0.86473146])
V8 = np.array([-V3 / 2, -V3 / 2, V3])
PERIOD = 6.32591398
EPS2 = 0.05                     # softening once the 4th sun has joined


def accel(m, eps):
    def f(t, y):
        n = len(m)
        p = y[:2 * n].reshape(n, 2)
        d = p[None, :, :] - p[:, None, :]
        r2 = (d ** 2).sum(-1) + eps ** 2
        np.fill_diagonal(r2, np.inf)
        a = (m[None, :, None] * d / r2[..., None] ** 1.5).sum(1)
        return np.concatenate([y[2 * n:], a.ravel()])
    return f


def plan(seed):
    rng = random.Random(seed * 7741 + 3)
    loops = 2
    T1 = loops * PERIOD
    s1 = solve_ivp(accel(np.ones(3), 0.0), (0, T1), np.concatenate([P8.ravel(), V8.ravel()]),
                   method="DOP853", rtol=1e-10, atol=1e-10, dense_output=True)
    y1 = s1.y[:, -1]
    p3, v3 = y1[:6].reshape(3, 2), y1[6:].reshape(3, 2)
    m = np.ones(4)
    for _try in range(400):
        phi = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(3.2, 3.8)
        u = -np.array([math.cos(phi), math.sin(phi)])
        b = rng.uniform(-0.6, 0.6)
        speed = rng.uniform(0.8, 1.25)
        p4 = -u * d
        v4 = speed * u + b * np.array([-u[1], u[0]]) * 0.3
        p = np.vstack([p3, p4])
        v = np.vstack([v3, v4])
        y0 = np.concatenate([p.ravel(), v.ravel()])
        T2 = 34.0
        s2 = solve_ivp(accel(m, EPS2), (0, T2), y0, method="DOP853", rtol=1e-9, atol=1e-9, dense_output=True)
        if not s2.success:
            continue
        inside, outs = set(range(4)), []
        for t in np.arange(0.025, T2 - 6, 0.025):
            y = s2.sol(t)
            P, V = y[:8].reshape(4, 2), y[8:].reshape(4, 2)
            w = check_out(m, P, V, inside)
            if w is not None:
                inside.discard(w)
                outs.append((float(t), w))
            if len(inside) <= 2:
                break
        if len(outs) < 2:
            continue
        k2 = 13.0 / (outs[-1][0] + 1.5)              # last OUT at ~13 s after the 4th sun appears
        if not 0.45 <= k2 <= 1.3 or outs[0][0] * k2 < 3.0:
            continue
        if (outs[1][0] - outs[0][0]) * k2 < 1.0:
            continue
        return dict(s1=s1, s2=s2, T1=T1, outs=outs, k2=k2, T2=outs[-1][0] + 1.5 + 3.5 / k2)
    raise RuntimeError("no good 4th-sun start found")


class Figure8(ShortScene):
    def construct(self):
        rng = self.rng
        cols = COLORS[:8]
        rng.shuffle(cols)
        cols = cols[:4]
        P_ = plan(SEED)
        fps = self.camera.fps
        K1 = 4.6 / PERIOD                             # one loop of the 8 takes 4.6 s on screen
        S1 = P_["T1"] * K1                            # stage 1 length (video s)
        k2 = P_["k2"]
        S2 = P_["T2"] * k2
        n1 = int(S1 * fps)
        Y1 = P_["s1"].sol(np.linspace(0, P_["T1"], n1, endpoint=False))
        POS1 = np.concatenate([Y1[:6].T.reshape(-1, 3, 2), np.full((n1, 1, 2), np.nan)], 1)
        n2 = int(S2 * fps) + 2
        Y2 = P_["s2"].sol(np.linspace(0, P_["T2"], n2))
        POS2 = Y2[:8].T.reshape(-1, 4, 2)
        POS = np.concatenate([POS1, POS2])
        out_at = {w: S1 + t * k2 for t, w in P_["outs"]}

        self.grid(0.06)
        q = self.question("3 suns. ONE path. A perfect 8…", 50, y=3.38)
        sub = T("Watch what a 4th sun does", 36, GOLD).set_max_width(4.2).move_to(UP * 2.86)
        self.add(sub)
        chips = VGroup()
        for name, col in cols:
            chips.add(VGroup(Dot(radius=0.075, fill_color=col), T(name, 24, col)).arrange(RIGHT, buff=0.08))
        chips.arrange_in_grid(n_rows=2, n_cols=2, h_buff=0.5, v_buff=0.16).move_to(DOWN * 2.95)
        chips[3].set_opacity(0.0)

        stars = VGroup()
        for name, col in cols:
            stars.add(VGroup(Dot(radius=0.14, fill_color=col).set_opacity(0.25), Dot(radius=0.07, fill_color=col),
                             Dot(radius=0.024, fill_color=WHITE).set_opacity(0.85).shift(UL * 0.02)))
        trails = VGroup(*[VMobject().set_stroke(c, 4) for _, c in cols])
        eight = VMobject().set_stroke(WHITE, 2, 0.0)                     # the 8 drawn so far (stage 1)
        self.add(eight, trails, stars, chips)
        view = dict(scale=1.55, center=np.zeros(2))
        CY = 0.15
        t0 = self.time
        TR1, TR2 = int(1.6 * fps), int(1.2 * fps)

        def to_screen(qq):
            s = (qq - view["center"]) * view["scale"]
            return np.stack([s[..., 0], s[..., 1] + CY, np.zeros(s.shape[:-1])], -1)

        def upd(_m, dt=0):
            t = self.time - t0
            i = min(len(POS) - 1, int(t * fps))
            p = POS[i]
            stage2 = i >= n1
            alive = [j for j in range(4) if not np.isnan(p[j, 0]) and not (j in out_at and t >= out_at[j])]
            fade_of = {j: max(0.0, 1 - (t - out_at[j]) / 1.6) for j in out_at if t >= out_at[j]}
            if stage2:
                qq = p[alive]
                com = qq.mean(0)
                ext = np.abs(qq - com).max() + 0.5
                target = min(1.55, 1.9 / ext)
                view["scale"] += (target - view["scale"]) * 0.05
                view["center"] = view["center"] + (com - view["center"]) * 0.06
            for j in range(4):
                if np.isnan(p[j, 0]):
                    stars[j].set_opacity(0)
                    continue
                stars[j].move_to(to_screen(p[j]))
                lo = max(n1 if (stage2 and j == 3) else 0, i - (TR2 if stage2 else TR1))
                seg = POS[lo: i + 1, j]
                seg = seg[~np.isnan(seg[:, 0])]
                if len(seg) > 1:
                    trails[j].set_points_as_corners(to_screen(seg))
                    npts = len(trails[j].get_points())
                    fade = fade_of.get(j, 1.0)
                    trails[j].set_stroke(cols[j][1], width=np.linspace(0.3, 6, npts).tolist(),
                                         opacity=(np.linspace(0, 1, npts) * fade).tolist())
                stars[j].set_opacity(fade_of.get(j, 1.0))
            # the 8: the path of sun 0 so far, as a faint guide (stays during stage 1, fades in stage 2)
            if not stage2 and i > 2:
                eight.set_points_as_corners(to_screen(POS[:i + 1, 0]))
                eight.set_stroke(WHITE, 2, 0.35)
            elif stage2:
                eight.set_stroke(opacity=max(0.0, 0.35 - (t - S1) * 0.25))

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # sound: stage 1 = a soft note each time the suns pass the crossing of the 8
        for i in range(1, n1):
            if np.sign(POS[i - 1, 2, 0]) != np.sign(POS[i, 2, 0]):
                self.sfx("bell", 523.25 * 2 ** (rng.choice([0, 4, 7, 12]) / 12), at=t0 + i / fps)
        dmin = np.full(n2, np.inf)
        for a in range(4):
            for b in range(a + 1, 4):
                dmin = np.minimum(dmin, np.linalg.norm(POS2[:, a] - POS2[:, b], axis=1))
        for i in range(1, n2 - 1):
            if dmin[i] < dmin[i - 1] and dmin[i] < dmin[i + 1] and dmin[i] < 0.35:
                self.sfx("pluck", 392.0 * 2 ** (rng.choice([0, 3, 5, 7, 10, 12]) / 12), at=t0 + S1 + i / fps)

        self.wait(S1 - 0.4)
        # the 4th sun arrives
        new_q = T("Now a 4th sun arrives… pick a color!", 40).set_max_width(4.2).move_to(q)
        self.sfx("chime", 659.25)
        self.play(FadeOut(q), FadeIn(new_q), FadeOut(sub), chips[3].animate.set_opacity(1.0), run_time=0.4)
        for t_sim, w in P_["outs"]:
            self.wait(max(0.0, out_at[w] - (self.time - t0)))
            name, col = cols[w]
            self.sfx("out", 440.0)
            flash = T(f"{name} is OUT!", 58, col).move_to(UP * 1.95)
            chip = chips[w]
            x = Line(chip.get_left() + LEFT * 0.02, chip.get_right() + RIGHT * 0.02).set_stroke(WHITE, 3)
            self.play(FadeIn(flash, scale=1.5), chip.animate.set_opacity(0.3), ShowCreation(x), run_time=0.3)
            self.play(FadeOut(flash), run_time=0.35, rate_func=lambda a: max(0.0, (a - 0.5) * 2))
        self.wait(max(0.0, S1 + S2 - 3.0 - (self.time - t0)))
        holder.clear_updaters()
        winners = [w for w in range(4) if w not in out_at]
        self.sfx("win", 523.25)
        boxes = VGroup(*[SurroundingRectangle(chips[w], buff=0.06).set_stroke(GOLD, 3) for w in winners])
        win = T(" + ".join(cols[w][0] for w in winners) + " SURVIVED!", 46, GOLD).set_max_width(4.2).move_to(UP * 1.95)
        self.play(FadeIn(win, scale=1.4), ShowCreation(boxes), run_time=0.5)
        self.payoff("The perfect 8 never came back", 36, y=-3.75, color=WHITE_)
        self.wait(1.8)
        self.meta = dict(n=4, outs=[cols[w][0] for _, w in P_["outs"]], winners=[cols[w][0] for w in winners])
