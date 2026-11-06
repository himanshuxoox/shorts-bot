"""
"Every bounce SHRINKS the ball and GROWS the wall… in 3D." The channel's shrink format inside a
SPHERE: a glowing ball bounces around; every bounce makes it smaller and pushes the wall inward
where it hit, drawn as thousands of rainbow spikes (like a sea urchin) that close in on the ball.
The camera slowly circles the sphere. Ends when the wall wins.
"""
import math

import numpy as np

from base import *

R = 1.9
NDIR = 1800            # spike directions (Fibonacci sphere)


def fib_sphere(n):
    i = np.arange(n) + 0.5
    z = 1 - 2 * i / n
    r = np.sqrt(1 - z * z)
    th = math.pi * (3 - math.sqrt(5)) * i
    return np.stack([r * np.cos(th), r * np.sin(th), z], 1)


def spikes_path(D, depth, cam=None):
    """one VMobject point list with a break between spikes (start, mid, end, end).
    Spikes on the half facing the camera are left out, so we look INTO the sphere at the ball."""
    A = D * R
    B = D * (R - depth)[:, None]
    keep = depth > 0.008
    if cam is not None:
        keep &= (D @ cam) < 0.15
    A, B = A[keep], B[keep]
    if len(A) == 0:
        return None, keep
    M = (A + B) / 2
    n = len(A)
    pts = np.empty((4 * n - 1, 3))
    pts[0::4], pts[1::4], pts[2::4] = A, M, B
    pts[3::4] = B[:-1]
    return pts, keep


def simulate(D, nprng, fps, amp, width, shrink, speed, T_MAX=28.0):
    """ball bouncing inside the sphere; returns per-frame (pos, radius, depth, fresh), hit times, end time"""
    depth = np.zeros(len(D))
    fresh = np.full(len(D), -9.0)
    p = np.array([0.1, -0.2, 0.15])
    v = nprng.normal(size=3)
    v *= speed / np.linalg.norm(v)
    r = 0.26
    t, SUB = 0.0, 10
    frames, hits = [], []
    while t < T_MAX:
        for _ in range(SUB):
            dt = 1 / fps / SUB
            p = p + v * dt
            d = np.linalg.norm(p)
            u = p / max(d, 1e-9)
            cosang = D @ u
            w = np.exp((cosang - 1) / 0.004)                  # wall radius in the ball's direction
            rho = R - (w * depth).sum() / max(w.sum(), 1e-9)
            if d + r >= rho and v @ u > 0:
                v = v - 2 * (v @ u) * u
                kick = nprng.normal(size=3)
                kick -= (kick @ u) * u
                v = v + 0.55 * kick
                v *= speed / np.linalg.norm(v)
                ang = np.arccos(np.clip(cosang, -1, 1))
                bump = amp * np.exp(-(ang / width) ** 2)
                depth = np.minimum(depth + bump, R - 0.02)
                fresh[bump > 0.6 * amp] = t
                r = max(0.012, r * shrink)
                hits.append(t)
                p = u * (rho - r - 1e-3)
        t += 1 / fps
        frames.append((p.copy(), r, depth.copy(), fresh.copy()))
        if r <= 0.03 or (R - depth).mean() < 0.45:
            break
    return frames, hits, t


class ShrinkSphere(ShortScene):
    HUD_FIXED = True

    def construct(self):
        rng = self.rng
        nprng = np.random.default_rng(SEED)
        mel_name, mel = melody(SEED)
        D = fib_sphere(NDIR)
        h0 = rng.random()
        base_rgba = hsl_rgba(h0 + 0.5 * (D[:, 2] + 1) / 2 + 0.25 * np.arctan2(D[:, 1], D[:, 0]) / math.pi, 0.85, 0.6)
        width = math.radians(rng.uniform(28, 32))
        amp = rng.uniform(0.3, 0.34)
        shrink = rng.uniform(0.982, 0.986)
        speed = rng.uniform(5.2, 5.8)
        fps = self.camera.fps
        frames, hits, t_end = simulate(D, nprng, fps, amp, width, shrink, speed)
        frame = self.frame
        frame.reorient(-30, 68, 0)
        frame.set_height(8.2)
        frame.move_to(DOWN * 0.15)
        self.grid(0.05)
        q = self.question("Every bounce SHRINKS the ball", 46, y=3.38)
        sub = self.hud(T("and GROWS the wall… in 3D", 42, GOLD).set_max_width(4.2).move_to(UP * 2.88))
        self.add(sub)
        grp, num = self.counter("bounces: ", 0, y=2.38, size=40)
        shell = SurfaceMesh(Sphere(radius=R), resolution=(18, 10)).set_stroke(CYAN, 1, 0.18)
        rim = Sphere(radius=R, color=CYAN).set_opacity(0.05)
        spikes = VMobject().set_stroke(WHITE, 2.2)
        ball = Sphere(radius=1.0, color=WHITE).set_color(Color(rgb=tuple(hsl_rgba(h0 + 0.5)[:3])))
        ball_glow = GlowDot(radius=0.6, color=WHITE)
        self.add(rim, shell, spikes, ball_glow, ball)
        t0 = self.time

        def upd(_m, dt=0):
            i = min(len(frames) - 1, int((self.time - t0) * fps))
            pp, rr, dep, fr = frames[i]
            ball.set_width(2 * rr).move_to(pp)
            ball_glow.move_to(pp).set_radius(rr * 3.2)
            cam = frame.get_implied_camera_location()
            cam = cam / max(np.linalg.norm(cam), 1e-9)
            pts, keep = spikes_path(D, dep, cam)
            if pts is not None:
                spikes.set_points(pts)
                age = (self.time - t0) - fr[keep]
                hot = 0.8 * np.clip(1 - age / 0.4, 0, 1)[:, None]
                col = base_rgba[keep].copy()
                col[:, :3] = col[:, :3] * (1 - hot) + hot
                n = len(col)
                rgba = np.repeat(col, 4, axis=0)[: 4 * n - 1]
                spikes.set_rgba_array(rgba, name="stroke_rgba")
                spikes.set_stroke(width=3.0)
            num.set_value(int(np.searchsorted(hits, (self.time - t0), side="right")))

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        for k, (th, nm) in enumerate(zip(hits, (mel * 100)[: len(hits)])):
            if k == 0 or th - hits[k - 1] > 0.075:
                self.sfx("pluck", note_hz(nm), at=t0 + th)
        self.play(frame.animate.increment_theta(1.6), run_time=t_end, rate_func=linear)
        holder.clear_updaters()
        self.sfx("win", 523.25)
        self.play(FadeOut(Group(ball, ball_glow)), run_time=0.3)
        pay = self.payoff("THE WALL WON!", 60, y=-3.15)
        self.hud(pay)
        sub2 = self.hud(T(f"after {len(hits)} bounces", 38, WHITE_).move_to(DOWN * 3.65))
        self.play(FadeIn(sub2), frame.animate.increment_theta(0.25), run_time=0.4)
        self.play(frame.animate.increment_theta(0.6), run_time=2.0, rate_func=linear)
        self.meta = dict(bounces=len(hits), melody=mel_name)
