"""
Three new 3D formats in the style of the channel's 3D hits (focus_3d, focus, golden):
navy background, neon wireframe that slowly turns, rainbow comet balls, a question on top.

  dish_3d      A satellite-dish (paraboloid). Balls rain straight down, bounce once and ALL pass
               through the focus at the same moment, then fly back up together. 1, 2, 3, 5 … 233.
  sphere_star  Balls bounce inside a sphere, each turning by the golden angle every bounce, each in
               its own plane. 1 ball draws a star; dozens draw a ball with a perfectly HOLLOW core.
  torus_knot   A ball rolls round a donut: 2 laps one way for every 3 the other ties a trefoil
               KNOT, 3:5 and 5:8 tie bigger knots — and the golden ratio never closes, it covers
               the whole donut.

Everything is exact geometry (ray / surface intersections, closed-form curves), drawn with cairo.
"""
import math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, note_freq, text
from . import mathfx as M, melodies

CX, CY = 540, 1060
PHI = (1 + 5 ** 0.5) / 2
FIB = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]


# ===================================================================== 3D view
class View:
    def __init__(self, yaw, tilt, cy=CY):
        self.cy = cy
        self.cu, self.su = math.cos(yaw), math.sin(yaw)
        self.ce, self.se = math.cos(tilt), math.sin(tilt)

    def proj(self, P):
        """world (x, y, z), z = up -> screen X, Y and depth (bigger = nearer the viewer)."""
        P = np.asarray(P, float)
        x = P[..., 0] * self.cu - P[..., 1] * self.su
        y = P[..., 0] * self.su + P[..., 1] * self.cu
        z = P[..., 2]
        up = z * self.ce + y * self.se
        depth = -y * self.ce + z * self.se
        return CX + x, self.cy - up, depth


def poly3d(ctx, view, pts, col, width=1.4, a_front=0.22, a_back=0.07):
    X, Y, Z = view.proj(pts)
    ctx.set_line_width(width)
    for i in range(len(X) - 1):
        a = a_front if (Z[i] + Z[i + 1]) > 0 else a_back
        ctx.set_source_rgba(*col, a)
        ctx.move_to(X[i], Y[i])
        ctx.line_to(X[i + 1], Y[i + 1])
        ctx.stroke()


def _spin(seed, t):
    return 0.35 * math.sin(t / 7.0 + seed) + 0.12 * t


# ===================================================================== dish_3d
@dataclass
class DishCfg:
    seed: int
    f: float
    rim: float
    z0: float
    n_final: int
    hue0: float
    tilt: float
    question: str
    melody_name: str
    melody: list


def dish_config(seed):
    rng = random.Random(seed * 5011 + 3)
    mel = rng.choice(melodies.FAMOUS)
    return DishCfg(seed, rng.uniform(140, 175), 420.0, 0.0, rng.choice([89, 144]), rng.random(),
                   math.radians(rng.uniform(24, 32)),
                   rng.choice(["Will they all hit the same point?", "Can a dish catch them all at once?",
                               "Do they ALL meet at one spot?"]), mel, melodies.MELODIES[mel])


def _dish_hit(P, D, f):
    """ray P + s D against z = (x² + y²) / 4f  (first hit with s > 1e-6)"""
    a = D[..., 0] ** 2 + D[..., 1] ** 2
    b = 2 * (P[..., 0] * D[..., 0] + P[..., 1] * D[..., 1]) - 4 * f * D[..., 2]
    c = P[..., 0] ** 2 + P[..., 1] ** 2 - 4 * f * P[..., 2]
    disc = np.sqrt(np.maximum(b * b - 4 * a * c, 0))
    with np.errstate(divide="ignore", invalid="ignore"):
        s1 = np.where(np.abs(a) > 1e-9, (-b - disc) / (2 * a), -c / b)
        s2 = np.where(np.abs(a) > 1e-9, (-b + disc) / (2 * a), np.inf)
    s1 = np.where(s1 > 1e-6, s1, np.inf)
    s2 = np.where(s2 > 1e-6, s2, np.inf)
    return np.minimum(s1, s2)


def dish_simulate(cfg, record=False):
    f = cfg.f
    depth = cfg.rim ** 2 / (4 * f)
    z0 = depth + 210
    cfg.z0 = z0
    F = np.array([0, 0, f])
    rng = random.Random(cfg.seed)
    k_last = FIB.index(cfg.n_final)
    laps, t = [], 0.6
    speed = 760.0
    for j in range(k_last + 2):
        n = FIB[min(j, k_last)]
        i = np.arange(n) + 0.5
        rr = cfg.rim * 0.93 * np.sqrt(i / max(n, 1)) if n > 1 else np.array([cfg.rim * 0.55])
        th = i * 2 * math.pi / PHI ** 2 + rng.uniform(0, 2 * math.pi)
        P0 = np.stack([rr * np.cos(th), rr * np.sin(th), np.full(n, z0)], 1)
        down = np.tile([0, 0, -1.0], (n, 1))
        s1 = _dish_hit(P0, down, f)
        Q1 = P0 + down * s1[:, None]
        d2 = F - Q1
        L2 = np.linalg.norm(d2, axis=1)
        d2 /= L2[:, None]
        s3 = _dish_hit(F + 0 * d2, d2, f)
        Q2 = F + d2 * s3[:, None]
        P3 = np.stack([Q2[:, 0], Q2[:, 1], np.full(n, z0)], 1)
        seg = np.stack([s1, L2, s3, z0 - Q2[:, 2]], 1)          # 4 straight pieces per ball
        lap_len = (seg[:, 0] + seg[:, 1]).max() + (seg[:, 2] + seg[:, 3]).max()
        laps.append(dict(t0=t, n=n, P=[P0, Q1, np.repeat(F[None], n, 0), Q2, P3], seg=seg,
                         T=lap_len / speed, meet=t + (seg[0, 0] + seg[0, 1]) / speed,
                         hue=(i / n) % 1.0))
        t += lap_len / speed + 0.15
    total = laps[-1]["meet"] + 2.6
    res = dict(laps=laps, total=total, speed=speed, t_answer=laps[-2]["meet"])
    res["frames"] = [dict(t=k / FPS) for k in range(int(total * FPS))] if record else []
    return res


def _dish_mesh(cfg):
    pts = []
    for k in range(1, 7):
        r = cfg.rim * k / 6
        th = np.linspace(0, 2 * math.pi, 72)
        pts.append(np.stack([r * np.cos(th), r * np.sin(th), np.full(72, r * r / (4 * cfg.f))], 1))
    for k in range(12):
        a = k * math.pi / 6
        r = np.linspace(0, cfg.rim, 30)
        pts.append(np.stack([r * math.cos(a), r * math.sin(a), r * r / (4 * cfg.f)], 1))
    return pts


_DRES = {}


def dish_prepare(res, cfg):
    _DRES[cfg.seed] = res


def _pos_on(P, seg, d):
    """position at distance d along the 4-piece path (vectorised)"""
    out = P[0].copy()
    acc = np.zeros(len(seg))
    for k in range(4):
        L = seg[:, k]
        f = np.clip((d - acc) / np.maximum(L, 1e-9), 0, 1)[:, None]
        on = (d >= acc)[:, None]
        out = np.where(on, P[k] + (P[k + 1] - P[k]) * f, out)
        acc = acc + L
    return out


def dish_draw(ctx, fr, cfg):
    res = _DRES[cfg.seed]
    t = fr["t"]
    M.background(ctx)
    view = View(_spin(cfg.seed, t), cfg.tilt, cy=CY + 250)
    for pts in _dish_mesh(cfg):
        poly3d(ctx, view, pts, M.WALL, 1.3, 0.22, 0.08)
    th = np.linspace(0, 2 * math.pi, 120)
    rimp = np.stack([cfg.rim * np.cos(th), cfg.rim * np.sin(th), np.full(120, cfg.rim ** 2 / (4 * cfg.f))], 1)
    X, Y, _ = view.proj(rimp)
    M.glow_stroke(ctx, lambda c: [c.move_to(X[0], Y[0])] + [c.line_to(x, y) for x, y in zip(X[1:], Y[1:])], M.WALL, 7)
    lap = None
    for L in res["laps"]:
        if t >= L["t0"]:
            lap = L
    fx_, fy_, _ = view.proj(np.array([0, 0, cfg.f]))
    pulse = max([0.0] + [1 - (t - L["meet"]) / 0.5 for L in res["laps"] if 0 <= t - L["meet"] < 0.5])
    M.marker(ctx, float(fx_), float(fy_), 13, M.GOLD, 0.85, pulse)
    if lap is not None:
        d = (t - lap["t0"]) * res["speed"]
        P, seg = lap["P"], lap["seg"]
        cur = _pos_on(P, seg, d)
        prev = _pos_on(P, seg, d - 12)
        cols = [M.rainbow(cfg.hue0 + h, 0.65, 1.0) for h in lap["hue"]]
        # trails of this lap
        ctx.set_line_width(1.1 if lap["n"] > 50 else 1.6)
        a = 0.5 if lap["n"] < 30 else 0.28 if lap["n"] < 100 else 0.18
        for i in range(lap["n"]):
            pts = [P[0][i]]
            acc = 0
            for k in range(4):
                if d > acc + seg[i, k]:
                    pts.append(P[k + 1][i])
                acc += seg[i, k]
            pts.append(cur[i])
            X, Y, _ = view.proj(np.array(pts))
            ctx.move_to(X[0], Y[0])
            for x, y in zip(X[1:], Y[1:]):
                ctx.line_to(x, y)
            ctx.set_source_rgba(*cols[i], a)
            ctx.stroke()
        X, Y, Z = view.proj(cur)
        X2, Y2, _ = view.proj(prev)
        r0 = 9 if lap["n"] < 30 else 6.5 if lap["n"] < 100 else 5
        for i in np.argsort(Z):
            M.comet(ctx, float(X[i]), float(Y[i]), float(X[i] - X2[i]), float(Y[i] - Y2[i]), cols[i], r0,
                    min(40.0, d), 1.0)
    M.question(ctx, t, cfg.question, y=330)
    if t >= res["t_answer"]:
        k = min(1.0, (t - res["t_answer"]) / 0.3)
        M.answer(ctx, f"YES! All {cfg.n_final}, every time!", y=425, size=52, alpha=k)
        text(ctx, "That's how a satellite dish works", 540, 1700, 42, (1, 1, 1), 0.85 * k)
    else:
        M.counter(ctx, "balls: ", f"{lap['n'] if lap else 1:,}", y=425)


def dish_audio(res, cfg):
    out = []
    last = -1
    for L in res["laps"]:
        hits = L["t0"] + L["seg"][:, 0] / res["speed"]
        for h in sorted(hits):
            if h - last > 0.012:
                out.append((float(h), 1500.0, "click"))
                last = h
    for (tm, nm) in melodies.track([L["meet"] for L in res["laps"]], cfg.melody, 0.0):
        out.append((tm, note_freq(nm), "bell"))
    out.append((res["t_answer"], 523.25, "win"))
    return out


# ===================================================================== sphere_star
@dataclass
class SphereCfg:
    seed: int
    Rs: float
    frac: float
    label: str
    hue0: float
    tilt: float
    melody_name: str
    melody: list


def sphere_config(seed):
    rng = random.Random(seed * 3313 + 9)
    frac, label = rng.choice([(1 / PHI ** 2, "golden angle"), (1 / PHI ** 2, "golden angle"),
                              (1 / math.pi, "1/π turn"), (2 ** -0.5 - 0.5, "irrational turn")])
    mel = rng.choice(melodies.FAMOUS)
    return SphereCfg(seed, 420.0, frac, label, rng.random(), math.radians(rng.uniform(15, 25)), mel,
                     melodies.MELODIES[mel])


def sphere_simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    waves = [(0.5, 1), (5.0, 2), (8.0, 5), (11.0, 12), (14.0, 30), (17.0, 60)]
    balls = []
    alpha = 2 * math.pi * cfg.frac
    for t_start, n in waves:
        for _ in range(n):
            nrm = rng.normal(size=3)
            nrm /= np.linalg.norm(nrm)
            e1 = np.cross(nrm, [0.3, 0.5, 0.8])
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(nrm, e1)
            ph = rng.uniform(0, 2 * math.pi)
            rate = rng.uniform(2.4, 3.2) + (n > 10) * 2.0          # chords per second
            balls.append(dict(t0=t_start + rng.uniform(0, 0.6), e1=e1, e2=e2, ph=ph, rate=rate,
                              hue=rng.uniform(0, 0.75)))
    total = 23.5
    res = dict(balls=balls, alpha=alpha, total=total, t_answer=20.0)
    res["frames"] = [dict(t=k / FPS) for k in range(int(total * FPS))] if record else []
    return res


_SRES = {}


def sphere_prepare(res, cfg):
    _SRES[cfg.seed] = res


def _sp_pt(b, k, R, alpha):
    a = b["ph"] + k * alpha
    return R * (math.cos(a) * b["e1"] + math.sin(a) * b["e2"])


def sphere_draw(ctx, fr, cfg):
    res = _SRES[cfg.seed]
    t = fr["t"]
    M.background(ctx)
    view = View(_spin(cfg.seed, t), cfg.tilt)
    R = cfg.Rs
    # wire sphere
    for k in range(1, 6):
        z = -R + 2 * R * k / 6
        r = math.sqrt(max(0, R * R - z * z))
        th = np.linspace(0, 2 * math.pi, 64)
        poly3d(ctx, view, np.stack([r * np.cos(th), r * np.sin(th), np.full(64, z)], 1), M.WALL, 1.2, 0.14, 0.05)
    for k in range(6):
        a = k * math.pi / 6
        th = np.linspace(0, 2 * math.pi, 64)
        poly3d(ctx, view, np.stack([R * np.cos(th) * math.cos(a), R * np.cos(th) * math.sin(a), R * np.sin(th)], 1),
               M.WALL, 1.2, 0.14, 0.05)
    nballs = 0
    chords = 0
    heads = []
    for b in res["balls"]:
        if t < b["t0"]:
            continue
        nballs += 1
        s = (t - b["t0"]) * b["rate"]
        kmax = int(s)
        chords += kmax
        col = M.rainbow(cfg.hue0 + b["hue"], 0.55, 1.0)
        pts = np.array([_sp_pt(b, k, R, res["alpha"]) for k in range(kmax + 2)])
        X, Y, Z = view.proj(pts)
        ctx.set_line_width(1.6 if nballs < 10 else 1.1)
        a = 0.6 if len(res["balls"]) < 10 else 0.32
        for k in range(kmax):
            ctx.set_source_rgba(*col, a * (1.0 if Z[k] + Z[k + 1] > 0 else 0.55))
            ctx.move_to(X[k], Y[k])
            ctx.line_to(X[k + 1], Y[k + 1])
            ctx.stroke()
        f = s - kmax
        hx, hy = X[kmax] + (X[kmax + 1] - X[kmax]) * f, Y[kmax] + (Y[kmax + 1] - Y[kmax]) * f
        ctx.set_source_rgba(*col, 0.9)
        ctx.move_to(X[kmax], Y[kmax])
        ctx.line_to(hx, hy)
        ctx.stroke()
        heads.append((hx, hy, X[kmax + 1] - X[kmax], Y[kmax + 1] - Y[kmax], col))
    for hx, hy, dx, dy, col in heads:
        M.comet(ctx, hx, hy, dx, dy, col, 8 if nballs < 10 else 5.5, 30)
    M.glow_stroke(ctx, lambda c: c.arc(CX, CY, R, 0, 2 * math.pi), M.WALL, 7)
    rin = R * math.cos(res["alpha"] / 2) if math.cos(res["alpha"] / 2) > 0 else R * abs(math.cos(res["alpha"] / 2))
    if t >= res["t_answer"]:
        k = min(1.0, (t - res["t_answer"]) / 0.5)
        M.glow_stroke(ctx, lambda c: c.arc(CX, CY, rin, 0, 2 * math.pi), M.GOLD, 5, alpha=k)
        M.answer(ctx, "NEVER! A perfect hollow ball stays inside", y=425, size=42, alpha=k)
    else:
        M.counter(ctx, "balls: ", f"{nballs}", y=425)
    M.question(ctx, t, "Will the bounces ever fill the ball?" if t > 4.8 else "Each bounce turns by the golden angle…",
               y=330, size=50)
    text(ctx, f"bounces: {chords:,}", 540, 1650, 44, (1, 1, 1), 0.85)


def sphere_audio(res, cfg):
    times = []
    for b in res["balls"][:3]:
        k = 1
        while b["t0"] + k / b["rate"] < res["t_answer"]:
            times.append(b["t0"] + k / b["rate"])
            k += 1
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(sorted(times), cfg.melody, 0.09)]
    rng = random.Random(cfg.seed)
    for b in res["balls"][3:]:
        k = 1
        while b["t0"] + k / b["rate"] < res["t_answer"]:
            if rng.random() < 0.15:
                out.append((b["t0"] + k / b["rate"], 1400.0, "click"))
            k += 1
    out.append((res["t_answer"], 523.25, "win"))
    return out


# ===================================================================== torus_knot
@dataclass
class TorusCfg:
    seed: int
    stages: list
    hue0: float
    tilt: float
    melody_name: str
    melody: list


def torus_config(seed):
    rng = random.Random(seed * 2903 + 5)
    first = rng.choice([[(2, 3), (3, 5), (5, 8)], [(2, 3), (2, 5), (3, 7)], [(3, 2), (5, 3), (8, 5)]])
    mel = rng.choice(melodies.FAMOUS)
    return TorusCfg(seed, first + [("φ", "φ")], rng.random(), math.radians(rng.uniform(38, 50)), mel,
                    melodies.MELODIES[mel])


R0, r0 = 300.0, 125.0


def torus_pt(u, v):
    return np.stack([(R0 + r0 * np.cos(v)) * np.cos(u), (R0 + r0 * np.cos(v)) * np.sin(u), r0 * np.sin(v)], -1)


def torus_simulate(cfg, record=False):
    plan, t = [], 0.6
    for p, q in cfg.stages:
        dur = 4.6 if p != "φ" else 8.5
        plan.append(dict(p=p, q=q, t0=t, dur=dur))
        t += dur + 1.4
    total = t + 1.4
    res = dict(plan=plan, total=total, t_answer=plan[-1]["t0"] + plan[-1]["dur"])
    res["frames"] = [dict(t=k / FPS) for k in range(int(total * FPS))] if record else []
    return res


_TRES = {}


def torus_prepare(res, cfg):
    _TRES[cfg.seed] = res


def _uv(st, s):
    """parameter s in [0, 1] of the stage -> (u, v) arrays"""
    if st["p"] == "φ":
        S = s * 2 * math.pi * 34                         # 34 laps around the tube
        return S / PHI, S
    return st["p"] * s * 2 * math.pi, st["q"] * s * 2 * math.pi


def torus_draw(ctx, fr, cfg):
    res = _TRES[cfg.seed]
    t = fr["t"]
    M.background(ctx)
    view = View(_spin(cfg.seed, t) * 0.8, cfg.tilt, cy=CY - 20)
    for k in range(10):                                   # torus wireframe
        v = k * 2 * math.pi / 10
        u = np.linspace(0, 2 * math.pi, 90)
        poly3d(ctx, view, torus_pt(u, np.full(90, v)), M.WALL, 1.4, 0.22, 0.07)
    for k in range(18):
        u = k * 2 * math.pi / 18
        v = np.linspace(0, 2 * math.pi, 40)
        poly3d(ctx, view, torus_pt(np.full(40, u), v), M.WALL, 1.4, 0.22, 0.07)
    st = None
    for s_ in res["plan"]:
        if t >= s_["t0"]:
            st = s_
    lab = "Will it ever come back?"
    if st is not None:
        s = min(1.0, (t - st["t0"]) / st["dur"])
        n = 900 if st["p"] != "φ" else 6000
        ss = np.linspace(0, s, max(2, int(n * s)))
        u, v = _uv(st, ss)
        P = torus_pt(u, v)
        X, Y, Z = view.proj(P)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        wide = st["p"] != "φ"
        for i in range(len(X) - 1):
            col = M.rainbow(cfg.hue0 + 0.8 * i / max(1, len(X)), 0.65, 1.0)
            front = Z[i] > -0.2 * R0
            if wide:
                ctx.set_line_width(14)
                ctx.set_source_rgba(*col, 0.12 if front else 0.04)
                ctx.move_to(X[i], Y[i]); ctx.line_to(X[i + 1], Y[i + 1]); ctx.stroke()
            ctx.set_line_width(4.5 if wide else 1.6)
            ctx.set_source_rgba(*col, (0.95 if front else 0.35) * (1 if wide else 0.7))
            ctx.move_to(X[i], Y[i]); ctx.line_to(X[i + 1], Y[i + 1]); ctx.stroke()
        if s < 1:
            M.comet(ctx, float(X[-1]), float(Y[-1]), float(X[-1] - X[-2]), float(Y[-1] - Y[-2]),
                    M.rainbow(cfg.hue0 + 0.8, 0.6, 1.0), 10, 40)
        if st["p"] == "φ":
            ratio = "golden ratio φ"
            if s >= 1:
                lab = "NEVER closes — it covers the whole donut!"
        else:
            ratio = f"{st['p']} : {st['q']}"
            if s >= 1:
                lab = "Back to the start: a KNOT!"
        M.counter(ctx, "turns  ", ratio, y=425)
    M.question(ctx, t, "A ball circles a donut…", y=330, size=56)
    if lab:
        col = M.GOLD if "KNOT" in lab or "NEVER" in lab else (1, 1, 1)
        from .common import text_fit
        text_fit(ctx, lab, 540, 1660, 46, 980, col, 0.95)


def torus_audio(res, cfg):
    out = []
    times = []
    for st in res["plan"]:
        laps = st["p"] if st["p"] != "φ" else 22
        for k in range(1, int(laps * 3) + 1):
            times.append(st["t0"] + st["dur"] * k / (laps * 3))
        out.append((st["t0"] + st["dur"], 659.25 if st["p"] != "φ" else 523.25, "win" if st["p"] == "φ" else "chime"))
    out += [(t, note_freq(nm), "pluck") for t, nm in melodies.track(times, cfg.melody, 0.1)]
    return out


# ===================================================================== module-like objects
class _F:
    AUDIO_MIN_GAP = 0.0

    def __init__(self, name, cfg_fn, sim, draw, prep, audio, facts):
        self.__name__ = name
        self.make_config = cfg_fn
        self.simulate = sim
        self.draw = draw
        self.prepare = prep
        self.audio_events = audio
        self.metadata_facts = facts

    @staticmethod
    def is_good(res):
        return True


dish_3d = _F("dish_3d", dish_config, dish_simulate, dish_draw, dish_prepare, dish_audio,
             lambda res, cfg: dict(template="dish_3d", n_final=cfg.n_final, n_balls=cfg.n_final, colors=[],
                                   melody=cfg.melody_name))
sphere_star = _F("sphere_star", sphere_config, sphere_simulate, sphere_draw, sphere_prepare, sphere_audio,
                 lambda res, cfg: dict(template="sphere_star", n_balls=len(res["balls"]), colors=[],
                                       melody=cfg.melody_name))
torus_knot = _F("torus_knot", torus_config, torus_simulate, torus_draw, torus_prepare, torus_audio,
                lambda res, cfg: dict(template="torus_knot", colors=[], melody=cfg.melody_name))
