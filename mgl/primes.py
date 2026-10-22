"""
"Put every number n at angle n" — prime spirals (3Blue1Brown). Dot n sits at distance n and
angle n (radians). Zooming out: 6 rainbow spirals, then 44. Keep only the primes: only 20 of
the 44 arms survive. Zoom out to 1,000,000: the primes line up into 280 rays.
(44 rad ≈ 7 turns, 710 rad ≈ 113 turns; primes can only sit on arms coprime to 44 / 710.)
Dots are coloured by n mod 6 → mod 44 → mod 710, so every arm / ray gets its own colour.
"""
import math

import numpy as np

from base import *

VIEW = 2.08
C = DOWN * 0.15


def primes_upto(n):
    sieve = np.ones(n + 1, bool)
    sieve[:2] = False
    for p in range(2, int(n ** 0.5) + 1):
        if sieve[p]:
            sieve[p * p::p] = False
    return sieve


def hue_rgba(vals, period, h0, alpha=1.0):
    h = (h0 + (vals % period) / period) % 1.0
    # vectorised HSV -> RGB (s = 0.85, v = 1)
    s, v = 0.85, 1.0
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b, np.full(len(vals), alpha)], 1)


class Primes(ShortScene):
    def construct(self):
        rng = self.rng
        N_INT, N_PRIME = 30000, 1_500_000
        sieve = primes_upto(N_PRIME)
        ints = np.arange(1, N_INT + 1)
        comp = ints[~sieve[1:N_INT + 1]]
        prm = np.nonzero(sieve)[0]

        def polar(ns):
            ns = ns.astype(float)
            return np.stack([ns * np.cos(ns), ns * np.sin(ns), np.zeros(len(ns))], 1)

        PC, PP = polar(comp), polar(prm)
        h0 = rng.random()
        COL = {m: (hue_rgba(comp, m, h0), hue_rgba(prm, m, h0)) for m in (6, 44, 710)}

        self.grid(0.06)
        self.question("Put every number n at angle n", 46, y=3.3)
        grp, num = self.counter("up to ", 1, y=2.7, size=46)
        cloud_c = DotCloud(PC[:1], radius=0.03)
        cloud_p = DotCloud(PP[:1], radius=0.03)
        for c_ in (cloud_c, cloud_p):
            c_.set_glow_factor(0.35)
        newest = Dot(radius=0.07, fill_color=WHITE)
        ray = Line(C, C).set_stroke(WHITE, 2, 0.6)
        self.add(cloud_c, cloud_p, ray, newest)

        # (time, radius shown in n-units)  geometric zoom between keyframes
        keys = [(0, 16), (3.0, 16), (5.4, 95), (8.6, 1300), (10.8, 1300), (12.4, 6000), (14.2, 6000), (20.2, 1_250_000)]
        tk = np.array([a for a, _ in keys])
        rk = np.log(np.array([b for _, b in keys], float))
        # colour mode blend: (time, weights for mod 6 / mod 44 / mod 710)
        st = dict(prime_only=0.0)
        t0 = self.time

        def radius(t):
            u = np.clip(t, tk[0], tk[-1])
            i = min(len(tk) - 2, int(np.searchsorted(tk, u, side="right")) - 1)
            f = (u - tk[i]) / (tk[i + 1] - tk[i])
            f = f * f * (3 - 2 * f)
            return float(np.exp(rk[i] + (rk[i + 1] - rk[i]) * f))

        def mode_weights(R):
            # mod 6 until R~200, mod 44 until R~5000, then mod 710
            a = np.clip((math.log(R) - math.log(200)) / 1.0, 0, 1)
            b = np.clip((math.log(R) - math.log(8000)) / 1.2, 0, 1)
            return (1 - a), a * (1 - b), b

        def upd(_m, dt=0):
            t = self.time - t0
            R = radius(t)
            s = VIEW / R
            n_show = int(min(N_PRIME, 1 + (t / 2.8) ** 1.6 * 70)) if t < 2.8 else N_PRIME
            mc, mp = comp <= n_show, prm <= n_show
            nc, np_ = int(mc.sum()), int(mp.sum())
            w6, w44, w710 = mode_weights(R)
            cc = COL[6][0][:nc] * w6 + COL[44][0][:nc] * w44 + COL[710][0][:nc] * w710
            cp = COL[6][1][:np_] * w6 + COL[44][1][:np_] * w44 + COL[710][1][:np_] * w710
            cc[:, 3] = 1 - st["prime_only"]
            cloud_c.set_points(PC[:nc] * s + C if nc else C[None] * 1.0).set_rgba_array(cc if nc else np.zeros((1, 4)))
            cloud_p.set_points(PP[:np_] * s + C if np_ else C[None] * 1.0).set_rgba_array(cp if np_ else np.zeros((1, 4)))
            r = float(np.clip(0.8 / math.sqrt(R) * (1 + 0.6 * st["prime_only"]), 0.0095, 0.07))
            cloud_c.set_radius(r)
            cloud_p.set_radius(r)
            if t < 3.0:                                          # show the rule: a pointer to the newest dot
                p = polar(np.array([n_show]))[0] * s + C
                newest.move_to(p).set_opacity(1)
                ray.put_start_and_end_on(C, p + 1e-4).set_opacity(0.6)
            else:
                newest.set_opacity(0)
                ray.set_opacity(0)
            num.set_value(int(round(n_show if t < 2.8 else R)))

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        for q in range(1, 30):
            self.sfx("tick", 700 + 25 * q, at=t0 + 2.8 * (q / 30) ** (1 / 1.6))

        def say(s, col=GOLD, size=48):
            return T(s, size, col).set_max_width(4.1).move_to(DOWN * 3.05)

        lab = None
        script = [(5.4, "6 spirals", GOLD), (8.6, "44 spirals?!", GOLD), (9.4, "Now keep ONLY the primes", WHITE_),
                  (12.5, "only 20 of 44 arms survive", GOLD), (20.3, "280 RAYS!", PINK)]
        for at, text_, col in script:
            self.wait(max(0.0, at - (self.time - t0)))
            if lab is not None:
                self.remove(lab)
            lab = say(text_, col)
            self.sfx("bell" if col != PINK else "win", {GOLD: 523.25, WHITE_: 659.25, PINK: 523.25}[col])
            anims = [FadeIn(lab, scale=1.3)]
            if text_.startswith("Now keep"):
                fade = ValueTracker(0)
                fade.add_updater(lambda v: st.__setitem__("prime_only", v.get_value()))
                self.add(fade)
                anims.append(fade.animate.set_value(1.0))
                self.play(*anims, run_time=1.2)
            else:
                self.play(*anims, run_time=0.3)
        self.wait(1.4)
        holder.clear_updaters()
        self.remove(lab)
        self.payoff("Why do primes do this?", 48, y=-3.05)
        self.wait(2.2)
