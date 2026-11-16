"""
"Only circles. Can they paint a FAMOUS painting?" — Fourier epicycles drawing a famous painting:
the Mona Lisa (Leonardo, c. 1503-1519), The Starry Night (Van Gogh, 1889) or The Scream (Munch, 1893),
all public domain. Each painting was traced once into ONE continuous line (mgl/data/<key>.npy: edges
of the picture, joined by the shortest bridges and walked so the pen retraces itself instead of
jumping). Then a chain of spinning circles redraws that line: ~20 circles = a blob, ~150 = a scribble,
1,500 = the painting. At the end the real painting fades in exactly under the line.
"""
import os

import numpy as np

from base import *

HERE = os.path.dirname(os.path.abspath(__file__))
ART = {"monalisa": "THE MONA LISA!", "starrynight": "THE STARRY NIGHT!", "scream": "THE SCREAM!"}


def coefficients(z, K):
    """the K biggest Fourier terms (frequency, coefficient), constant term first."""
    N = len(z)
    C = np.fft.fft(z) / N
    k = np.fft.fftfreq(N, 1 / N).astype(int)
    order = np.argsort(-np.abs(C))
    order = np.concatenate([[0], [i for i in order[:K + 1] if i != 0]])[:K + 1]
    return k[order], C[order]


class FourierArt(ShortScene):
    def construct(self):
        rng = self.rng
        key = rng.choice(sorted(ART))
        name = ART[key]
        P = np.load(os.path.join(HERE, "data", key + ".npy")).astype(float)
        z = P[:, 0] + 1j * P[:, 1]
        hue = rng.choice([(GOLD, PINK), (CYAN, "#9B7BFF"), ("#FF8A3D", GOLD), (GOLD, "#FF8A3D")])
        self.grid(0.08)
        self.question(rng.choice(["Only circles. Can they paint a FAMOUS painting?",
                                  "Spinning circles are painting something… guess it!",
                                  "Only circles. Guess the painting before it ends"]), 40, y=3.3)
        grp, num = self.counter("circles: ", 0, y=2.72, size=42)
        SCALE = min(2.0 / np.abs(z.real).max(), 2.3 / np.abs(z.imag).max())     # fill the frame (painting fits too)
        CENTER = DOWN * 0.3
        stages = [(rng.choice([16, 20, 24]), 5.0), (rng.choice([120, 150]), 6.5), (1500, 13.0)]
        notes = melody(SEED)[1]

        for si, (K_n, dur) in enumerate(stages):
            ks, cs = coefficients(z, K_n)
            num.set_value(K_n)
            n_vis = min(K_n, 70)                              # only the biggest circles are drawn
            circles = VGroup(*[Circle(radius=max(1e-3, abs(c) * SCALE)).set_stroke(WHITE, 1.2, 0.25)
                               for c in cs[1:n_vis + 1]])
            chain = VMobject().set_stroke(WHITE, 1.8, 0.7)
            trail_glow = VMobject().set_stroke(hue[1], 9, 0.14)
            trail = VMobject().set_stroke(hue, 2.6 if si == 2 else 3.6)
            tip = Dot(radius=0.04, fill_color=WHITE)
            hist = []
            t0 = self.time

            def tips(us, ks=ks, cs=cs):
                return np.exp(2j * np.pi * np.outer(us, ks)) @ cs * SCALE

            def upd(_m, dt=0, ks=ks, cs=cs, n_vis=n_vis, t0=t0, dur=dur):
                u = min(1.0, (self.time - t0) / dur)
                acc = np.cumsum(cs * np.exp(2j * np.pi * ks * u)) * SCALE
                Q = np.stack([acc.real, acc.imag, np.zeros(len(acc))], 1) + CENTER
                for i, c in enumerate(circles):
                    c.move_to(Q[i])
                chain.set_points_as_corners(Q[: n_vis + 2])
                last = hist[-1][0] if hist else 0.0
                us = np.linspace(last, u, max(2, int((u - last) * len(z) * 1.1)))[1:] if hist else np.array([u])
                if len(us):
                    a = tips(us)
                    hist.extend(zip(us, np.stack([a.real, a.imag, np.zeros(len(a))], 1) + CENTER))
                if len(hist) >= 2:
                    arr = np.array([h[1] for h in hist])
                    trail.set_points_as_corners(arr)
                    trail_glow.set_points_as_corners(arr)
                tip.move_to(Q[-1])

            holder = Mobject()
            holder.add_updater(upd)
            upd(None)
            self.add(holder, circles, chain, trail_glow, trail, tip)
            if si == 0:
                self.wait(0.3)
            step = 0.36 if si == 2 else 0.5
            for q in range(int(dur / step)):
                self.sfx("pluck", note_hz(notes[q % len(notes)]), at=t0 + q * step)
            self.wait(dur)
            holder.clear_updaters()
            if si < len(stages) - 1:
                verdict = T(["Just a blob…", "A face? Keep watching…"][si], 40, WHITE_).move_to(DOWN * 3.3)
                self.play(FadeIn(verdict, shift=UP * 0.2), run_time=0.4)
                self.wait(0.6)
                self.play(FadeOut(VGroup(circles, chain, trail_glow, trail, tip, verdict)), run_time=0.45)
                self.remove(holder)
            else:
                self.sfx("win", 523.25)
                art = ImageMobject(os.path.join(HERE, "data", key + ".jpg"))
                art.set_opacity(0)
                self.play(FadeOut(VGroup(circles, chain, tip)), trail.animate.set_stroke(width=3.2),
                          trail_glow.animate.set_stroke(opacity=0.3), run_time=0.6)
                self.payoff(name, 50, y=-3.2)
                self.art_reveal(art, key, SCALE, CENTER, trail)
                self.wait(2.0)
        self.meta = dict(art=key, name=name.strip("!").title(), circles=[s[0] for s in stages])

    def art_reveal(self, art, key, SCALE, CENTER, trail):
        """the real painting fades in exactly under the line drawing"""
        # the line was normalised: (pixel - mean) / scale, y flipped (fit = [mean_x, mean_y, scale, W, H])
        mx, my, s, W, H = np.load(os.path.join(HERE, "data", key + "_fit.npy"))
        art.set_width(W * SCALE / s)
        cx = (W / 2 - mx) / s * SCALE
        cy = -(H / 2 - my) / s * SCALE
        art.move_to(np.array([cx, cy, 0]) + CENTER)
        self.add(art)
        self.bring_to_back(art)
        self.play(art.animate.set_opacity(0.55), trail.animate.set_stroke(opacity=0.85), run_time=1.6)
