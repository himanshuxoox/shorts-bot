"""
"Where will 1,500 balls land?" — a Galton board. Every ball hits 12 pegs and bounces left or
right at random (50/50). Each single ball is unpredictable, but together they always pile up
into the same shape: the bell curve (normal distribution), drawn over the bins at the end.
"""
import math

import numpy as np

from base import *

ROWS = 12
TOP = 1.75
DY = 0.17
DX = 0.3
BALL_R = 0.026
FLOOR = -3.0
ROW_T = 0.085                       # seconds per peg row


class Galton(ShortScene):
    def construct(self):
        rng = self.rng
        nprng = np.random.default_rng(SEED)
        N = rng.choice([1200, 1500, 1800])
        p_right = 0.5
        bins = ROWS + 1
        steps = (nprng.random((N, ROWS)) < p_right).astype(int)
        pos_idx = np.cumsum(steps, axis=1)                         # rights taken after each row
        final = pos_idx[:, -1]
        # release schedule: slow first balls, then a stream
        rel = np.concatenate([[0.0, 0.6, 1.1, 1.5], 1.8 + np.cumsum(np.full(N - 4, 13.0 / (N - 4)))])
        fall_t = ROWS * ROW_T
        bin_x = (np.arange(bins) - ROWS / 2) * DX
        y_rows = TOP - DY * np.arange(ROWS + 1)
        stack_top = y_rows[-1] - 0.25
        # stacking position inside each bin
        cols_per_bin = max(1, int((DX * 0.92) / (2 * BALL_R)))
        land_t = rel + fall_t + 0.0
        order = np.argsort(land_t)
        level = np.zeros(bins, int)
        stack_pos = np.zeros((N, 3))
        land_y = np.zeros(N)
        for i in order:
            b = final[i]
            k = level[b]
            level[b] += 1
            col = k % cols_per_bin
            row = k // cols_per_bin
            x = bin_x[b] + (col - (cols_per_bin - 1) / 2) * 2 * BALL_R
            y = FLOOR + BALL_R + row * 2 * BALL_R * 0.95
            stack_pos[i] = [x, y, 0]
            land_y[i] = y
        drop_t = np.sqrt(np.maximum(0, stack_top - land_y) / 9.0) * 1.6       # time to fall into the bin
        done_t = land_t + drop_t

        self.grid(0.06)
        self.question(f"Where will {N:,} balls land?", 50, y=3.35)
        grp, num = self.counter("balls: ", 0, y=2.8, size=44)
        # pegs
        peg_pts = []
        for r in range(ROWS):
            for j in range(r + 1):
                peg_pts.append([(j - r / 2) * DX, y_rows[r] - DY * 0.5, 0])
        pegs = DotCloud(np.array(peg_pts), radius=0.03, color=GREY_A)
        pegs.set_glow_factor(0.3)
        walls = VGroup()
        for x in np.concatenate([bin_x - DX / 2, [bin_x[-1] + DX / 2]]):
            walls.add(Line([x, FLOOR, 0], [x, stack_top + 0.05, 0]).set_stroke(CYAN, 2, 0.6))
        floor = glow(Line([bin_x[0] - DX / 2, FLOOR, 0], [bin_x[-1] + DX / 2, FLOOR, 0]).set_stroke(CYAN, 4), CYAN, 4)
        funnel = VGroup(Line([-0.9, TOP + 0.55, 0], [-0.08, TOP + 0.12, 0]), Line([0.9, TOP + 0.55, 0], [0.08, TOP + 0.12, 0]))
        funnel.set_stroke(CYAN, 4)
        self.add(walls, floor, funnel, pegs)
        h0 = rng.random()
        rgba = np.array([[*Color(hsl=((h0 + 0.8 * final[i] / ROWS) % 1, 0.9, 0.62)).get_rgb(), 1.0]
                         for i in range(N)])
        moving = DotCloud(np.zeros((1, 3)), radius=BALL_R)
        stacked = DotCloud(np.zeros((1, 3)), radius=BALL_R)
        moving.set_glow_factor(0.5)
        self.add(stacked, moving)
        order_done = np.argsort(done_t)
        done_sorted = done_t[order_done]
        t0 = self.time

        def ball_xy(idx, tau):
            """position of balls idx at time tau since their release (vectorised)"""
            r = np.clip((tau / ROW_T).astype(int), 0, ROWS)
            f = np.clip(tau / ROW_T - r, 0, 1)
            prev = np.where(r > 0, pos_idx[idx, np.clip(r - 1, 0, ROWS - 1)], 0)
            nxt = pos_idx[idx, np.clip(r, 0, ROWS - 1)]
            x0 = (prev - r / 2) * DX
            x1 = (nxt - (r + 1) / 2) * DX
            x = x0 + (x1 - x0) * f
            y = y_rows[np.clip(r, 0, ROWS)] - DY * f + 0.06 * np.sin(np.pi * f) * (r < ROWS)
            in_board = tau < fall_t
            # after the board: drop straight into the bin
            u = np.clip((tau - fall_t) / np.maximum(drop_t[idx], 1e-6), 0, 1)
            xs = stack_pos[idx, 0]
            ys = stack_top + (land_y[idx] - stack_top) * u ** 2
            X = np.where(in_board, x, bin_x[final[idx]] + (xs - bin_x[final[idx]]) * u)
            Y = np.where(in_board, y, ys)
            return np.stack([X, Y, np.zeros(len(idx))], 1)

        def upd(_m, dt=0):
            t = self.time - t0
            n_done = int(np.searchsorted(done_sorted, t, side="right"))
            ids_done = order_done[:n_done]
            if n_done:
                stacked.set_points(stack_pos[ids_done]).set_rgba_array(rgba[ids_done])
            act = np.nonzero((rel <= t) & (done_t > t))[0]
            if len(act):
                moving.set_points(ball_xy(act, t - rel[act])).set_rgba_array(rgba[act])
            else:
                moving.set_points(np.array([[0, 9, 0]]))
            num.set_value(int((rel <= t).sum()))

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # peg clicks (thinned) and a soft thud per landing for the first balls
        for i in range(N):
            if i < 30 or i % 6 == 0:
                for r in range(0, ROWS, 1 if i < 4 else 3):
                    self.sfx("tick", 1200 + 60 * (pos_idx[i, r] - r / 2), at=t0 + rel[i] + r * ROW_T)
        T_END = float(done_t.max()) + 0.3
        lab = T("Every bounce is 50 / 50…", 40, WHITE_).set_max_width(4.1).move_to(DOWN * 3.5)
        self.wait(2.2)
        self.play(FadeIn(lab), run_time=0.3)
        self.wait(max(0.1, T_END - (self.time - t0)))
        holder.clear_updaters()
        # bell curve over the bins
        counts = np.bincount(final, minlength=bins)
        sigma = math.sqrt(ROWS * p_right * (1 - p_right))
        xs = np.linspace(-ROWS / 2 - 0.5, ROWS / 2 + 0.5, 200)
        pdf = N / (sigma * math.sqrt(2 * math.pi)) * np.exp(-xs ** 2 / (2 * sigma ** 2))
        rows_needed = pdf / cols_per_bin
        curve_pts = np.stack([xs * DX, FLOOR + BALL_R + rows_needed * 2 * BALL_R * 0.95 + 0.03, np.zeros(len(xs))], 1)
        bell = VMobject().set_points_smoothly(curve_pts[::4].tolist()).set_stroke(GOLD, 6)
        self.sfx("win", 523.25)
        self.play(ShowCreation(glow(bell, GOLD, 6)), FadeOut(lab), run_time=1.0)
        self.payoff("…together: the BELL CURVE", 44, y=-3.5)
        self.wait(2.2)
        self.meta = dict(N=N, counts=counts.tolist())
