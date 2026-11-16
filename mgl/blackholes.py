"""
"1,200 stars vs 2 black holes. How many survive?" A disk of stars circles a pair of black holes.
The pair spirals inward the way real merging black holes do (separation ~ (1 - t/T)^(1/4), so the
orbit speeds up: the "chirp"), sending out a gravitational-wave ripple every half orbit, which you
can also HEAR as a rising tick. Stars that come too close are swallowed or flung out of the system.
Then the two holes MERGE in a flash, and the survivors are counted. Shown in 3D (tilted, turning).
"""
import math

import numpy as np

from base import *

N = 1200
A0 = 2.0               # starting separation of the two black holes (they sweep through the disk)
TM = 60.0              # merger time (sim units)
A_MERGE = 0.13
RH = 0.09              # a star closer than this to a hole is swallowed
EPS = 0.05
SIM_PER_S = 3.4        # sim time per video second during the inspiral
HOLD = 5.0             # video seconds after the merger
ESC = 9.0              # flung out beyond this radius


def binary(t):
    """separation, angle of the pair at sim time t (before the merger)"""
    u = min(t / TM, 1.0)
    return A0 * max(1 - u, 1e-9) ** 0.25


def simulate(seed, fps):
    rng = np.random.default_rng(seed)
    r = np.sqrt(rng.uniform(0.8 ** 2, 4.4 ** 2, N))
    a = rng.uniform(0, 2 * np.pi, N)
    z = rng.normal(0, 0.05, N) * r
    p = np.stack([r * np.cos(a), r * np.sin(a), z], 1)
    vc = np.sqrt(1.0 / r) * rng.normal(1.0, 0.03, N)
    v = np.stack([-np.sin(a) * vc, np.cos(a) * vc, rng.normal(0, 0.01, N)], 1)
    alive = np.ones(N, bool)
    fate = np.zeros(N, int)                      # 0 = here, 1 = swallowed, 2 = flung out
    phase, t = 0.0, 0.0
    frames, bh_pos, swallowed, flung, ripples = [], [], [], [], []
    last_ripple = 0.0
    merged_at = None
    dt_frame = SIM_PER_S / fps
    total_frames = int((TM / SIM_PER_S + HOLD) * fps)
    for f in range(total_frames):
        sub = 14
        h = dt_frame / sub
        for _s in range(sub):
            if merged_at is None:
                sep = binary(t)
                if sep <= A_MERGE:
                    merged_at = t
                om = math.sqrt(1.0 / sep ** 3)
                phase += om * h
                if phase - last_ripple >= math.pi / 2:
                    last_ripple = phase
                    ripples.append((f / fps, sep))
                c, s = math.cos(phase), math.sin(phase)
                holes = np.array([[sep / 2 * c, sep / 2 * s, 0.0], [-sep / 2 * c, -sep / 2 * s, 0.0]])
                masses = (0.5, 0.5)
                rh = RH
            else:
                holes = np.zeros((1, 3))
                masses = (1.0,)
                rh = RH * 2.2
            acc = np.zeros_like(p)
            for hp, m in zip(holes, masses):
                d = hp - p
                r2 = (d ** 2).sum(1) + EPS ** 2
                acc += m * d / r2[:, None] ** 1.5
                close = alive & (np.sqrt(r2) < rh)
                fate[close] = 1
                alive &= ~close
            v += acc * h
            p += v * h
            t += h
        far = alive & (np.linalg.norm(p, axis=1) > ESC)
        fate[far] = 2
        alive &= ~far
        q = p.astype(np.float32).copy()
        q[fate == 1] = np.nan
        frames.append(q)
        bh_pos.append(holes.copy() if merged_at is None else np.zeros((2, 3)))
        swallowed.append(int((fate == 1).sum()))
        flung.append(int((fate == 2).sum()))
    return dict(frames=frames, bh=bh_pos, swallowed=swallowed, flung=flung, ripples=ripples,
                merge_frame=int(merged_at / SIM_PER_S * fps) if merged_at else len(frames) - 1,
                r0=r)


class BlackHoles(ShortScene):
    def construct(self):
        rng = self.rng
        fps = self.camera.fps
        R = simulate(SEED, fps)
        F = R["frames"]
        mf = R["merge_frame"]
        SC = 0.46
        elev = math.radians(rng.uniform(48, 58))
        yaw0 = rng.uniform(0, 2 * math.pi)
        spin = rng.choice([-1, 1]) * 0.07
        CY = -0.15
        view = dict(yaw=yaw0)

        def proj(q):
            ca, sa = math.cos(view["yaw"]), math.sin(view["yaw"])
            x1 = q[..., 0] * ca - q[..., 1] * sa
            y1 = q[..., 0] * sa + q[..., 1] * ca
            Y = y1 * math.sin(elev) + q[..., 2] * math.cos(elev)
            return np.stack([x1 * SC, Y * SC + CY, np.zeros_like(x1)], -1)

        h0 = rng.choice([0.55, 0.62, 0.75])
        cols = [Color(hsl=((0.08 + (h0 - 0.08) * min(1, (rr - 0.8) / 3.4)) % 1, 1.0,
                           0.68 + 0.08 * math.sin(rr * 7))) for rr in R["r0"]]

        def pts(i):
            q = F[i].copy()
            q[np.isnan(q[:, 0])] = 100.0                # swallowed stars: far off screen
            return proj(q)

        cloud = DotCloud(pts(0), radius=0.026)
        cloud.set_color(cols)
        cloud.set_glow_factor(1.0)
        tails = [DotCloud(pts(0), radius=0.016) for _ in range(3)]       # short motion streaks
        for k, tcl in enumerate(tails):
            tcl.set_color(cols).set_opacity(0.45 - 0.12 * k)
        ripples = [VMobject().set_stroke(CYAN, 2.5, 0) for _ in range(14)]
        holes = Group(*[Group(GlowDot(radius=0.5, color="#FF9A3D"), Dot(radius=0.05, fill_color=BLACK))
                        for _ in range(2)])
        self.add(*ripples, *tails, cloud, holes)
        self.grid(0.05)
        self.question(f"{N:,} stars vs 2 black holes", 48, y=3.38)
        sub = T("How many survive the crash?", 36, GOLD).set_max_width(4.2).move_to(UP * 2.88)
        self.add(sub)
        g1, n_sw = self.counter("swallowed: ", 0, y=-2.75, size=36, color="#FF7A45")
        g2, n_fl = self.counter("flung out: ", 0, y=-3.25, size=36, color=CYAN)
        t0 = self.time
        circ = np.linspace(0, 2 * np.pi, 72)
        rp = R["ripples"]

        def upd(_m, dt=0):
            t = self.time - t0
            i = min(len(F) - 1, int(t * fps))
            view["yaw"] = yaw0 + spin * t
            cloud.set_points(pts(i))
            for k, tcl in enumerate(tails):
                tcl.set_points(pts(max(0, i - 2 * (k + 1))))
            for k, hole in enumerate(holes):
                hole.move_to(proj(R["bh"][i][k])) if i < mf else hole.move_to(proj(np.zeros(3)))
            if i >= mf:
                holes[1].set_opacity(0)
                holes[0][0].set_radius(0.5)
            recent = [e for e in rp if e[0] <= t][-len(ripples):]
            for k, rip in enumerate(ripples):
                if k < len(recent):
                    rr = 0.3 + (t - recent[k][0]) * 2.2
                    a = max(0.0, 0.55 * (1 - rr / 5.0))
                    ring = np.stack([rr * np.cos(circ), rr * np.sin(circ), np.zeros_like(circ)], 1)
                    rip.set_points_as_corners(proj(ring))
                    rip.set_stroke(opacity=a)
                else:
                    rip.set_stroke(opacity=0)
            n_sw.set_value(R["swallowed"][i])
            n_fl.set_value(R["flung"][i])

        holder = Mobject()
        holder.add_updater(upd)
        upd(None)
        self.add(holder)
        # sound: the chirp — a tick every half orbit (one per ripple), pitch rising as they speed up
        last = -1.0
        for (te, sep) in rp:
            if te - last >= 0.06:
                self.sfx("tick", 220.0 * (A0 / sep) ** 0.9, at=t0 + te)
                last = te
        prev = 0
        for i, s_ in enumerate(R["swallowed"][:mf]):
            if s_ > prev and i % 4 == 0:
                self.sfx("pluck", 196.0 * 2 ** (rng.choice([0, 3, 7, 10]) / 12), at=t0 + i / fps)
                prev = s_
        t_merge = mf / fps
        self.wait(max(0.1, t_merge - 2.0))
        lab = T("They are about to MERGE…", 40, WHITE_).set_max_width(4.2).move_to(UP * 2.3)
        self.play(FadeIn(lab, shift=UP * 0.2), run_time=0.4)
        self.wait(max(0.0, t_merge - (self.time - t0)))
        self.sfx("shatter", 261.63)
        flash = GlowDot(ORIGIN, radius=3.5, color=WHITE).move_to(UP * CY)
        self.add(flash)
        self.play(FadeOut(flash, scale=2.0), FadeOut(lab), run_time=1.0)
        self.wait(1.4)
        last_i = len(F) - 1
        surv = N - R["swallowed"][last_i] - R["flung"][last_i]
        self.sfx("win", 523.25)
        self.payoff(f"{surv:,} stars SURVIVED!", 48, y=2.3)
        self.wait(max(0.5, len(F) / fps - (self.time - t0)))
        holder.clear_updaters()
        self.meta = dict(n=N, survived=surv, swallowed=R["swallowed"][last_i], flung=R["flung"][last_i])
