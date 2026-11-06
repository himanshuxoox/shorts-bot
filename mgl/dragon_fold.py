"""
"Fold a strip 10 times… then open every fold to 90°." A paper ribbon stands on its edge. Each
step copies the whole ribbon and swings the copy 90° around the end (exactly what opening one
more fold does). 1, 2, 4, 8 … 1,024 pieces, and the paper draws the DRAGON CURVE. Every swing
gets its own colour; the camera slowly circles the 3D ribbon.
"""
import math

import numpy as np

from base import *

FOLDS = 10


def unfold(pts):
    """dragon step: append a copy of the path rotated +90° about its last point (reversed)."""
    end = pts[-1]
    rel = pts[::-1] - end
    rot = np.stack([-rel[:, 1], rel[:, 0]], 1)
    return np.concatenate([pts, (rot + end)[1:]])


class DragonFold(ShortScene):
    HUD_FIXED = True

    def construct(self):
        rng = self.rng
        h0 = rng.random()
        sign = rng.choice([-1, 1])
        mel_name, mel = melody(SEED)
        frame = self.frame
        frame.reorient(-20, 55, 0)
        self.grid(0.06)
        self.question("Fold a strip 10 times…", 54, y=3.35)
        sub = self.hud(T("…then open every fold to 90°", 36, GOLD).set_max_width(4.2).move_to(UP * 2.85))
        self.add(sub)
        grp, num = self.counter("folds opened: ", 0, y=2.38, size=40)

        pts = np.array([[0.0, 0.0], [1.0, 0.0]])
        gen = np.array([0])                                   # colour generation of each segment
        state = dict(size=1.0)

        def ribbon(P, gens, height, angle=0.0, n_old=None):
            """grid (n+1 along, 2 high) for the path; the last part (from n_old) is swung by `angle`."""
            P = P.copy()
            if n_old is not None and angle:
                end = P[n_old - 1]
                rel = P[n_old - 1:] - end
                c, s_ = math.cos(angle), math.sin(angle)
                P[n_old - 1:] = np.stack([rel[:, 0] * c - rel[:, 1] * s_, rel[:, 0] * s_ + rel[:, 1] * c], 1) + end
            ctr = (P.max(0) + P.min(0)) / 2
            Q = P - ctr
            n = len(Q)
            G = np.zeros((n, 2, 3))
            G[:, 0, :2] = Q
            G[:, 1, :2] = Q
            G[:, 1, 2] = height
            # vertex colours: segment colour (a vertex takes the colour of the segment before it)
            g = np.concatenate([[gens[0]], gens])
            col = hsl_rgba(h0 + 0.085 * g, 0.85, 0.6)
            rgba = np.repeat(col, 2, axis=0)
            return G, rgba, Q

        surf = None
        edge = VMobject().set_stroke(WHITE, 2, 0.8)
        self.add(edge)

        def show(G, rgba, Q, height):
            nonlocal surf
            if surf is None or surf.get_resolution()[0] != G.shape[0]:
                if surf is not None:
                    self.remove(surf)
                surf = GridSurface(G, shading=(0.35, 0.25, 0.3))
                self.add(surf)
            surf.set_grid(G).set_vertex_colors(rgba)
            top = np.concatenate([Q, np.full((len(Q), 1), height)], 1)
            edge.set_points_as_corners(top)
            edge.set_stroke(width=max(0.8, 2.6 - 0.2 * math.log2(len(Q))))

        H = 0.35
        G, rgba, Q = ribbon(pts, gen, H)
        show(G, rgba, Q, H)
        frame.set_height(5.5)
        self.wait(0.6)
        t_total = 0.0
        swing_t = [1.3, 1.2, 1.1, 1.0, 0.95, 0.9, 0.85, 0.85, 0.9, 1.0]
        for k in range(FOLDS):
            n_old = len(pts)
            new_pts = unfold(pts)                           # final positions after this swing
            new_gen = np.concatenate([gen, np.full(len(gen), k + 1)])
            size_now = max(np.ptp(pts, axis=0))
            size_new = max(np.ptp(new_pts, axis=0))
            dur = swing_t[k]
            # build the swinging path: old path + copy at angle 0 (on top of the old one, reversed)
            end = pts[-1]
            copy0 = pts[::-1][1:]                            # reversed copy, not yet rotated
            P_swing = np.concatenate([pts, copy0])
            tr = ValueTracker(0.0)
            h_now = max(H, 0.055 * size_now)
            h_new = max(H, 0.055 * size_new)

            def upd(_m, dt=0, P_swing=P_swing, n_old=n_old, new_gen=new_gen, h_now=h_now, h_new=h_new):
                a = tr.get_value()
                hh = h_now + (h_new - h_now) * a
                G, rgba, Q = ribbon(P_swing, new_gen, hh, angle=sign * a * math.pi / 2, n_old=n_old)
                show(G, rgba, Q, hh)

            if sign < 0:
                new_pts = np.concatenate([pts, (np.stack([(pts[::-1] - end)[:, 1], -(pts[::-1] - end)[:, 0]], 1) + end)[1:]])
            holder = Mobject()
            holder.add_updater(upd)
            self.add(holder, tr)
            fh = frame.get_height()
            ext = np.ptp(new_pts, axis=0)
            target_h = max(5.5, ext[1] * 1.75, ext[0] * 1.78 * 1.2) + 1.0
            self.sfx("pluck", note_hz(mel[k % len(mel)]))
            num.set_value(k + 1)
            self.play(tr.animate.set_value(1.0), frame.animate.set_height(target_h).increment_theta(sign * 0.25),
                      run_time=dur, rate_func=smooth)
            holder.clear_updaters()
            self.remove(holder, tr)
            pts, gen = new_pts, new_gen
            if k == 2:
                lab = self.hud(T("Looks like nothing…", 40, WHITE_).move_to(DOWN * 3.2))
                self.play(FadeIn(lab), run_time=0.25)
            if k == 6:
                self.play(FadeOut(lab), run_time=0.25)
        # reveal: look straight down, then tilt back and circle the 3D ribbon
        self.sfx("win", 523.25)
        self.play(frame.animate.reorient(0, 15, 0), run_time=1.2)
        pay = self.payoff("The DRAGON curve!", 58, y=-3.15)
        self.wait(1.2)
        sub2 = self.hud(T(f"{2 ** FOLDS:,} pieces of paper", 36, WHITE_).move_to(DOWN * 3.65))
        self.play(FadeIn(sub2), run_time=0.3)
        self.play(frame.animate.reorient(sign * 30, 40, 0), run_time=3.0, rate_func=smooth)
        self.wait(1.0)
        self.meta = dict(folds=FOLDS, melody=mel_name)
