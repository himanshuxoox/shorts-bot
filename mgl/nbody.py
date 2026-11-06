"""
"9 suns. Pick a color!" — the N-body problem (6, 8 or 9 suns). The suns start almost at rest
and fall together under Newton's gravity. Close encounters fling suns out of the cluster one by
one: a sun that is thrown out is OUT. The last ones still inside win.

Who is "out" is decided carefully (the old three-body version named the wrong star):
only the sun FARTHEST from the centre of the suns still inside can be out, and only when
  * it is far away (more than ESC_R from that centre),
  * it is moving away, and
  * it is unbound: its kinetic energy relative to the rest beats their pull on it (E > 0).
"""
import math, random, zlib

import numpy as np
from scipy.integrate import solve_ivp

from base import *

COLORS = [("RED", "#FF3B4E"), ("ORANGE", "#FF8A2A"), ("YELLOW", "#FFE14D"), ("GREEN", "#3BE37A"),
          ("CYAN", "#3FE6F0"), ("BLUE", "#3F7BFF"), ("PURPLE", "#A15BFF"), ("PINK", "#FF5FC8"),
          ("WHITE", "#F2F2F2")]
EPS = 0.08          # gravitational softening (sim units)
ESC_R = 3.0         # far from every other sun (sim units; the cluster starts ~3 across)


def accel_fn(m):
    def f(t, y):
        n = len(m)
        p = y[:2 * n].reshape(n, 2)
        d = p[None, :, :] - p[:, None, :]                       # d[i, j] = p_j - p_i
        r2 = (d ** 2).sum(-1) + EPS ** 2
        np.fill_diagonal(r2, np.inf)
        a = (m[None, :, None] * d / r2[..., None] ** 1.5).sum(1)
        return np.concatenate([y[2 * n:], a.ravel()])
    return f


def check_out(m, p, v, inside):
    """index of a sun that is thrown out right now (or None).
    Out = it is far from EVERY sun still inside (> ESC_R), moving away from them, and unbound:
    its kinetic energy (relative to the others' centre of mass) beats the exact pull of each one."""
    idx = np.array(sorted(inside))
    if len(idx) <= 2:
        return None
    for i in idx:
        rest = idx[idx != i]
        dists = np.linalg.norm(p[rest] - p[i], axis=1)
        if dists.min() < ESC_R:
            continue
        Mr = m[rest].sum()
        cr = (m[rest, None] * p[rest]).sum(0) / Mr
        vr = (m[rest, None] * v[rest]).sum(0) / Mr
        dp, dv = p[i] - cr, v[i] - vr
        if dp @ dv <= 0:
            continue
        mu = m[i] * Mr / (m[i] + Mr)
        E = 0.5 * mu * float(dv @ dv) - float((m[i] * m[rest] / dists).sum())
        if E > 0:
            return int(i)
    return None


def _scan(m, sol, t_end, n, step=0.025):
    inside, outs = set(range(n)), []
    for t in np.arange(step, t_end, step):
        y = sol.sol(t)
        P, V = y[:2 * n].reshape(n, 2), y[2 * n:].reshape(n, 2)
        while True:
            w = check_out(m, P, V, inside)
            if w is None:
                break
            inside.discard(w)
            outs.append((float(t), w))
        if len(inside) <= 2:
            break
    return outs, inside


def plan(seed, n):
    """search a start where at least 3 suns get thrown out, spread over ~20 s of video."""
    rng = random.Random(seed * 104729 + n)
    m = np.ones(n)
    T_SIM = 45.0
    for _try in range(120):
        ang = np.array([rng.uniform(0, 2 * math.pi) for _ in range(n)])
        rad = np.array([1.6 * math.sqrt(rng.uniform(0.15, 1)) for _ in range(n)])
        p = np.stack([rad * np.cos(ang), rad * np.sin(ang)], 1)
        spin = rng.uniform(0.0, 0.14) * rng.choice([-1, 1])
        v = spin * np.stack([-p[:, 1], p[:, 0]], 1) + np.array([[rng.gauss(0, 0.04), rng.gauss(0, 0.04)] for _ in range(n)])
        p -= p.mean(0)
        v -= v.mean(0)
        y0 = np.concatenate([p.ravel(), v.ravel()])
        # ONE trajectory for both the OUT checks and the picture (the motion is chaotic: integrating
        # again with other settings would give a different dance and the labels would be wrong)
        sol = solve_ivp(accel_fn(m), (0, T_SIM + 12), y0, method="DOP853", rtol=1e-8, atol=1e-8, dense_output=True)
        if not sol.success:
            continue
        outs, _inside = _scan(m, sol, T_SIM, n)
        if len(outs) < (2 if n == 6 else 3):
            continue
        t_last = outs[-1][0]
        k = 17.0 / (t_last + 1.0)                     # last OUT at ~17 s of video
        if outs[0][0] * k < 2.0 or k > 2.5:
            continue
        shown = []
        for t, _w in outs:                            # flashes at least 0.8 s apart on screen
            shown.append(max(t * k, (shown[-1] + 0.8) if shown else 0))
        if max(np.diff([0] + shown)) > 7.5 or shown[-1] > 19.0:
            continue
        T = t_last + 1.0 + 3.6 / k
        if T > T_SIM + 12:
            continue
        inside = sorted(set(range(n)) - {w for _t, w in outs})
        return dict(m=m, sol=sol, outs=outs, shown=shown, inside=inside, k=k, T=T)
    raise RuntimeError("no good N-body start found")


class NBody(ShortScene):
    def construct(self):
        rng = self.rng
        n = rng.choice([6, 8, 8, 9, 9])
        cols = COLORS[:]
        rng.shuffle(cols)
        cols = cols[:n]
        P_ = plan(SEED, n)
        m, sol, outs, k = P_["m"], P_["sol"], P_["outs"], P_["k"]
        fps = self.camera.fps
        VID = P_["T"] * k
        ts = np.linspace(0, P_["T"], int(VID * fps) + 2)
        Y = sol.sol(ts)
        POS = Y[:2 * n].T.reshape(-1, n, 2)
        out_at = {w: tv for (_t, w), tv in zip(outs, P_["shown"])}       # video time of each OUT flash

        self.grid(0.06)
        self.question(f"{n} suns. Pick a color!", 54, y=3.38)
        sub = T("Thrown out = OUT. Will yours survive?", 36, GOLD).set_max_width(4.2).move_to(UP * 2.86)
        self.add(sub)
        # legend: colour chips with names, 3 per row
        chips = VGroup()
        for i, (name, col) in enumerate(cols):
            dot = Dot(radius=0.075, fill_color=col)
            lab = T(name, 24, col)
            chips.add(VGroup(dot, lab).arrange(RIGHT, buff=0.08))
        chips.arrange_in_grid(n_rows=math.ceil(n / 3), n_cols=3, h_buff=0.32, v_buff=0.16).move_to(DOWN * 2.95)
        if chips.get_width() > 4.2:
            chips.set_width(4.2)
        self.add(chips)
        crosses = {}

        stars = VGroup()
        for i, (name, col) in enumerate(cols):
            halo = Dot(radius=0.13, fill_color=col).set_opacity(0.25)
            body = Dot(radius=0.065, fill_color=col)
            shine = Dot(radius=0.022, fill_color=WHITE).set_opacity(0.85).shift(UL * 0.02)
            stars.add(VGroup(halo, body, shine))
        trails = VGroup(*[VMobject().set_stroke(c, 4) for _, c in cols])
        self.add(trails, stars)
        view = dict(scale=0.75, center=np.zeros(2))
        TRAIL = int(1.4 * fps)
        CY = 0.2
        t0 = self.time
        gone = set()

        def to_screen(q):
            s = (q - view["center"]) * view["scale"]
            return np.stack([s[..., 0], s[..., 1] + CY, np.zeros(s.shape[:-1])], -1)

        def upd(_m, dt=0):
            t = self.time - t0
            i = min(len(POS) - 1, int(t * fps))
            p = POS[i]
            alive = [j for j in range(n) if not (j in out_at and t >= out_at[j])]
            fade_of = {j: max(0.0, 1 - (t - out_at[j]) / 1.6) for j in out_at if t >= out_at[j]}
            q = p[alive]
            com = q.mean(0)
            ext = np.abs(q - com).max() + 0.5
            target = min(1.05, 1.9 / ext)
            view["scale"] += (target - view["scale"]) * 0.06
            view["center"] = view["center"] + (com - view["center"]) * 0.08
            for j in range(n):
                stars[j].move_to(to_screen(p[j]))
                seg = POS[max(0, i - TRAIL): i + 1, j]
                if len(seg) > 1:
                    trails[j].set_points_as_corners(to_screen(seg))
                    npts = len(trails[j].get_points())
                    fade = fade_of.get(j, 1.0)
                    trails[j].set_stroke(cols[j][1], width=np.linspace(0.3, 6, npts).tolist(),
                                         opacity=(np.linspace(0, 1, npts) * fade).tolist())
                stars[j].set_opacity(fade_of.get(j, 1.0))

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # sound: a pluck at every close pass, a falling "out" at every ejection
        dmin = np.full(len(POS), np.inf)
        for a in range(n):
            for b in range(a + 1, n):
                dmin = np.minimum(dmin, np.linalg.norm(POS[:, a] - POS[:, b], axis=1))
        for i in range(1, len(dmin) - 1):
            if dmin[i] < dmin[i - 1] and dmin[i] < dmin[i + 1] and dmin[i] < 0.35:
                self.sfx("pluck", 392.0 * 2 ** (rng.choice([0, 3, 5, 7, 10, 12]) / 12), at=t0 + i / fps)
        order = 0
        for (t_sim, w), tv in zip(outs, P_["shown"]):
            self.wait(max(0.0, tv - (self.time - t0)))
            order += 1
            name, col = cols[w]
            self.sfx("out", 440.0)
            flash = T(f"{name} is OUT!", 58, col).move_to(UP * 1.95)
            chip = chips[w]
            x = Line(chip.get_left() + LEFT * 0.02, chip.get_right() + RIGHT * 0.02).set_stroke(WHITE, 3)
            crosses[w] = x
            self.play(FadeIn(flash, scale=1.5), chip.animate.set_opacity(0.3), ShowCreation(x), run_time=0.3)
            self.play(FadeOut(flash), run_time=0.35, rate_func=lambda a: max(0.0, (a - 0.5) * 2))
        self.wait(max(0.0, VID - 3.2 - (self.time - t0)))
        holder.clear_updaters()
        winners = [w for w in range(n) if w not in out_at]
        names = " + ".join(cols[w][0] for w in winners)
        self.sfx("win", 523.25)
        boxes = VGroup(*[SurroundingRectangle(chips[w], buff=0.06).set_stroke(GOLD, 3) for w in winners])
        win = T(f"{len(winners)} SURVIVED!", 54, GOLD).move_to(UP * 1.95)
        self.play(FadeIn(win, scale=1.4), ShowCreation(boxes), run_time=0.5)
        self.payoff("Did your color survive?", 40, y=-3.75, color=WHITE_)
        self.wait(1.8)
        self.meta = dict(n=n, outs=[cols[w][0] for _, w in outs], winners=[cols[w][0] for w in winners])
