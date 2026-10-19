"""
"Focus magic" (ellipse billiards). Balls fly out of one FOCUS of an ellipse, bounce off the
wall once and ALL pass through the other focus at the same moment (every focus -> wall ->
focus path has the same length, 2a). Every time they meet, more balls join: 1, 2, 3, 5, 8,
13 ... 377 (Fibonacci). The question at the top asks if they will all hit the same point.

Three variants (one format each):
  focus          a fixed ellipse
  focus_stretch  the shape is stretched / squashed (even a circle) every time they meet
  focus_3d       an ellipsoid in 3D that slowly turns; directions spread over a sphere

Everything is computed exactly (ray / ellipse intersections), not with small time steps,
so the balls really do meet at one point. Sound: a soft tick for every wall hit (hundreds
of them make a crackle) and the next note of a public-domain tune every time they meet.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import note_freq
from . import mathfx as M, melodies

CX, CY = 540, 1080
INTRO = 0.7
END_HOLD = 2.6
SPEED = 590.0
TAIL = 48.0
FIB = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]

QUESTIONS = {
    "plain": ["Will they all hit the same point?", "Will every ball meet at one spot?",
              "Do they ALL meet again?"],
    "stretch": ["Will they still meet if I stretch it?", "What if I stretch the shape?",
                "Still the same point if I stretch it?"],
    "3d": ["Does it work in 3D too?", "Will they all meet… in 3D?", "What about in 3D?"],
}
ANSWERS = ["Yes! All {n}, every time!", "Every single one! All {n}", "Yes! All {n} of them!"]


@dataclass
class Config:
    seed: int
    kind: str
    n_final: int
    shapes: list            # [(A, B)] per leg  (A = vertical semi-axis, B = horizontal)
    hue0: float
    hue_span: float
    tilt: float
    spin: float
    melody_name: str
    melody: list
    question: str
    answer: str
    pause: float = 0.0
    legs: int = 0


def make_config(seed, kind="plain"):
    rng = random.Random(seed * 7919 + {"plain": 1, "stretch": 2, "3d": 3}[kind])
    n_final = rng.choice([233, 377, 377]) if kind != "3d" else rng.choice([377, 610])
    k_last = FIB.index(n_final)
    legs = k_last + 2                                   # one extra lap after the last count
    if kind == "stretch":
        pool = [(330, 330), (400, 300), (470, 270), (540, 230), (580, 180), (300, 440), (460, 360),
                (360, 360), (560, 300), (500, 150), (420, 420), (590, 260), (260, 450)]
        first = pool[0]
        rest = pool[1:]
        rng.shuffle(rest)
        shapes = [first] + [rest[i % len(rest)] for i in range(legs - 1)]
        # never stretch twice into almost the same shape
        for i in range(1, len(shapes)):
            if abs(shapes[i][0] - shapes[i - 1][0]) + abs(shapes[i][1] - shapes[i - 1][1]) < 60:
                shapes[i] = (shapes[i][1] + 40, shapes[i][0] - 40) if shapes[i][0] > shapes[i][1] else (360, 300)
        pause = 0.55
    else:
        a = rng.uniform(470, 560) if kind == "plain" else rng.uniform(470, 520)
        b = rng.uniform(310, 380) if kind == "plain" else rng.uniform(330, 370)
        shapes = [(a, b)] * legs
        pause = 0.0
    mel = rng.choice(melodies.FAMOUS)
    n_str = f"{n_final:,}"
    return Config(seed, kind, n_final, shapes, rng.random(), 1.0,
                  rng.uniform(0.22, 0.32), rng.choice([-1, 1]) * rng.uniform(0.12, 0.2),
                  mel, melodies.MELODIES[mel], rng.choice(QUESTIONS[kind]),
                  rng.choice(ANSWERS).format(n=n_str), pause, legs)


# ===================================================================== geometry
def foci(A, B):
    """(top/left focus, bottom/right focus) as 3D points relative to the centre."""
    if A >= B:
        c = math.sqrt(A * A - B * B)
        return np.array([0.0, -c, 0.0]), np.array([0.0, c, 0.0])
    c = math.sqrt(B * B - A * A)
    return np.array([-c, 0.0, 0.0]), np.array([c, 0.0, 0.0])


def hit(P, D, A, B):
    """Ray P + s*D (D unit, P inside) against x²/B² + y²/A² + z²/B² = 1 -> (s, Q, reflected D)."""
    inv = np.array([1 / B ** 2, 1 / A ** 2, 1 / B ** 2])
    a = (D * D * inv).sum(-1)
    b = 2 * (P * D * inv).sum(-1)
    c = (P * P * inv).sum(-1) - 1
    s = (-b + np.sqrt(np.maximum(b * b - 4 * a * c, 0))) / (2 * a)
    Q = P + D * s[..., None]
    n = Q * inv
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    R = D - 2 * (D * n).sum(-1, keepdims=True) * n
    return s, Q, R


def _sphere(n, rng):
    """n directions spread evenly over a sphere (golden spiral), randomly rotated."""
    i = np.arange(n) + 0.5
    y = 1 - 2 * i / n
    r = np.sqrt(1 - y * y)
    th = math.pi * (3 - math.sqrt(5)) * i + rng.uniform(0, 2 * math.pi)
    v = np.stack([r * np.cos(th), y, r * np.sin(th)], 1)
    a, b = rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi)
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Rz = np.array([[math.cos(b), -math.sin(b), 0], [math.sin(b), math.cos(b), 0], [0, 0, 1]])
    return v @ (Rz @ Rx).T


# ===================================================================== simulation
def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    k_last = FIB.index(cfg.n_final)
    hue_legs = []
    legs = []
    t = INTRO
    start_focus = 0
    wall_hits, meets = [], []
    for j in range(cfg.legs + 1):                        # +1 = outro lap under the answer
        A, B = cfg.shapes[min(j, len(cfg.shapes) - 1)]
        if j > 0:
            t += cfg.pause
        n = FIB[min(j, k_last)]
        # every time they meet, ALL balls fan out again evenly (a fresh, wider "flower"),
        # coloured by direction so the wave front is a rainbow arc
        rot = rng.uniform(0, 2 * math.pi)
        if cfg.kind == "3d":
            dirs = _sphere(n, rng)
            hues = list((np.arctan2(dirs[:, 2], dirs[:, 0]) / (2 * math.pi)) % 1.0)
        else:
            angs = rot + 2 * math.pi * (np.arange(n) + 0.5) / n
            dirs = np.stack([np.cos(angs), np.sin(angs), np.zeros(n)], 1)
            hues = list(((angs - rot) / (2 * math.pi)) % 1.0)
        hue_legs.append(np.array(hues))
        P = foci(A, B)[start_focus]
        Ps = np.repeat(P[None], len(dirs), 0)
        s, Q, R = hit(Ps, dirs, A, B)
        dur = 2 * max(A, B) / SPEED
        legs.append(dict(t0=t, dur=dur, A=A, B=B, f=start_focus, P=P, D=dirs.copy(), Q=Q, R=R,
                         L1=s, n=len(dirs)))
        wall_hits += list(t + s / SPEED)
        t += dur
        if j < cfg.legs:
            meets.append((t, len(dirs)))
        start_focus = 1 - start_focus
    t_answer = meets[-1][0]
    total = t_answer + END_HOLD
    wall_hits = [w for w in wall_hits if w < total - 0.3]
    for L, h in zip(legs, hue_legs):
        L["hue"] = h
    res = dict(legs=legs, wall_hits=wall_hits, meets=meets, t_answer=t_answer, total=total)
    frames = []
    if record:
        from .common import FPS
        frames = [dict(t=i / FPS) for i in range(int(total * FPS))]
    res["frames"] = frames
    return res


def is_good(res):
    return True


# ===================================================================== drawing
_RES = {}


def prepare(res, cfg):
    _RES[cfg.seed, cfg.kind] = res


def _state(res, cfg, t):
    """-> (leg index, tau within leg or None during a pause, shape A, B)."""
    legs = res["legs"]
    if t < legs[0]["t0"]:
        return 0, 0.0, legs[0]["A"], legs[0]["B"]
    for j, L in enumerate(legs):
        if t < L["t0"]:                                    # in the pause before leg j: morph
            prev = legs[j - 1]
            u = (t - (prev["t0"] + prev["dur"])) / max(1e-6, cfg.pause)
            u = 0.5 - 0.5 * math.cos(math.pi * min(1, max(0, u)))
            return j, None, prev["A"] + (L["A"] - prev["A"]) * u, prev["B"] + (L["B"] - prev["B"]) * u
        if t < L["t0"] + L["dur"]:
            return j, t - L["t0"], L["A"], L["B"]
    L = legs[-1]
    return len(legs) - 1, min(t - L["t0"], L["dur"]), L["A"], L["B"]


_MESH = {}


def _mesh(res, cfg, j, view, colors):
    """Offscreen layer with the full paths of every finished lap before lap j (plain variant)."""
    import cairo
    from .common import W, H
    surf, done = _MESH.get(cfg.seed, (None, 0))
    if surf is None or j < done:
        surf, done = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H), 0
    c = cairo.Context(surf)
    c.set_line_width(1.2)
    for Lg in res["legs"][done:j]:
        cs = colors(Lg)
        a = 0.16 if Lg["n"] < 30 else 0.09 if Lg["n"] < 150 else 0.05
        for i in range(Lg["n"]):
            X, Y, _ = view.proj(np.array([Lg["P"], Lg["Q"][i], Lg["P"] * -1]))
            c.move_to(X[0], Y[0]); c.line_to(X[1], Y[1]); c.line_to(X[2], Y[2])
            c.set_source_rgba(*cs[i], a)
            c.stroke()
    surf.flush()
    _MESH[cfg.seed] = (surf, max(done, j))
    return surf


class _View:
    """2D: identity. 3D: slow spin around the vertical axis + a small tilt towards the camera."""

    def __init__(self, cfg, t):
        self.d3 = cfg.kind == "3d"
        self.phi = cfg.spin * t
        self.al = cfg.tilt

    def proj(self, p):
        p = np.asarray(p, float)
        if not self.d3:
            return p[..., 0] + CX, p[..., 1] + CY, np.zeros(p.shape[:-1])
        c, s = math.cos(self.phi), math.sin(self.phi)
        x = p[..., 0] * c + p[..., 2] * s
        z = -p[..., 0] * s + p[..., 2] * c
        ca, sa = math.cos(self.al), math.sin(self.al)
        y = p[..., 1] * ca - z * sa
        zz = p[..., 1] * sa + z * ca
        return x + CX, y + CY, zz


def _outline(ctx, A, B, view):
    if view.d3:
        a2 = math.sqrt((A * math.cos(view.al)) ** 2 + (B * math.sin(view.al)) ** 2)
        ctx.save(); ctx.translate(CX, CY); ctx.scale(B, a2); ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()
    else:
        ctx.save(); ctx.translate(CX, CY); ctx.scale(B, A); ctx.arc(0, 0, 1, 0, 2 * math.pi); ctx.restore()


def _grid(ctx, A, B, view):
    """Faint latitude / longitude lines so the ellipsoid reads as 3D."""
    ctx.set_line_width(1.3)
    for k in range(1, 6):                                   # parallels
        y = -A + 2 * A * k / 6
        r = B * math.sqrt(max(0, 1 - (y / A) ** 2))
        th = np.linspace(0, 2 * math.pi, 64)
        pts = np.stack([r * np.cos(th), np.full_like(th, y), r * np.sin(th)], 1)
        _poly_depth(ctx, view, pts)
    for k in range(6):                                      # meridians
        ph = k * math.pi / 6
        th = np.linspace(-math.pi / 2, math.pi / 2 * 3, 80)
        pts = np.stack([B * np.cos(th) * math.cos(ph), A * np.sin(th), B * np.cos(th) * math.sin(ph)], 1)
        _poly_depth(ctx, view, pts)


def _poly_depth(ctx, view, pts):
    X, Y, Z = view.proj(pts)
    for i in range(len(X) - 1):
        front = (Z[i] + Z[i + 1]) / 2 > 0
        ctx.set_source_rgba(0.45, 0.75, 1.0, 0.16 if front else 0.06)
        ctx.move_to(X[i], Y[i])
        ctx.line_to(X[i + 1], Y[i + 1])
        ctx.stroke()


def draw(ctx, fr, cfg):
    res = _RES[cfg.seed, cfg.kind]
    t = fr["t"]
    M.background(ctx)
    j, tau, A, B = _state(res, cfg, t)
    view = _View(cfg, t)
    legs = res["legs"]
    L = legs[j]

    if view.d3:
        _grid(ctx, A, B, view)
    F = foci(A, B)
    # focus markers pulse when the balls meet
    pulse = 0.0
    for tm, _n in res["meets"]:
        if 0 <= t - tm < 0.5:
            pulse = 1 - (t - tm) / 0.5
    meet_f = L["f"] if (tau is None or tau < L["dur"]) else 1 - L["f"]
    for i, Fi in enumerate(F):
        x, y, _ = view.proj(Fi)
        M.marker(ctx, float(x), float(y), 12, M.GOLD, 0.7, pulse if i == meet_f else 0.0)

    n = L["n"]
    colors = lambda Lg: [M.rainbow(cfg.hue0 + cfg.hue_span * h, 0.62, 1.0) for h in Lg["hue"]]
    col = colors(L)
    if cfg.kind == "plain":                       # every finished lap stays as a faint rainbow mesh
        ctx.set_source_surface(_mesh(res, cfg, j if tau is not None else j, view, colors), 0, 0)
        ctx.paint()
    ctx.set_line_width(1.6 if n < 150 else 1.1)

    # trails of the previous leg fade out, the current leg's trails stay until the next leg
    def leg_lines(Lg, upto, alpha, c=None):
        c = c or colors(Lg)
        P, Q, R, L1 = Lg["P"], Lg["Q"], Lg["R"], Lg["L1"]
        d = upto * SPEED
        for i in range(Lg["n"]):
            if d <= L1[i]:
                pts = [P, P + Lg["D"][i] * d]
            else:
                pts = [P, Q[i], Q[i] + R[i] * (d - L1[i])]
            X, Y, _ = view.proj(np.array(pts))
            ctx.move_to(X[0], Y[0])
            for x, y in zip(X[1:], Y[1:]):
                ctx.line_to(x, y)
            ctx.set_source_rgba(*c[i], alpha)
            ctx.stroke()

    a_base = 0.55 if n < 60 else 0.32 if n < 200 else 0.22
    if j > 0:
        prev = legs[j - 1]
        if cfg.kind == "stretch":           # old paths don't fit the new shape: fade them during the morph
            fade = 0.0 if tau is not None else max(0.0, 1 - (t - prev["t0"] - prev["dur"]) / 0.25)
        else:
            fade = 1.0 if tau is None else max(0.0, 1 - tau / (0.6 * L["dur"]))
        if fade > 0:
            leg_lines(prev, prev["dur"], a_base * 0.8 * fade)
    if tau is not None:
        leg_lines(L, tau, a_base)

    # balls
    P, Q, R, L1, D = L["P"], L["Q"], L["R"], L["L1"], L["D"]
    if tau is None:                     # paused at the meeting point (focus moves with the shape)
        Fm = foci(A, B)[1 - legs[j - 1]["f"]]
        pos = np.repeat(Fm[None], legs[j - 1]["n"], 0)
        vel = legs[j - 1]["R"]
        n_draw = legs[j - 1]["n"]
        col = colors(legs[j - 1])
        since = np.full(n_draw, 1e9)
    else:
        d = tau * SPEED
        first = d <= L1
        pos = np.where(first[:, None], P + D * d, Q + R * (d - L1)[:, None])
        vel = np.where(first[:, None], D, R)
        since = np.where(first, d, d - L1)
        n_draw = n
    X, Y, Z = view.proj(pos)
    X2, Y2, _ = view.proj(pos + vel * 10)
    r0 = 10.0 if n_draw < 30 else 8.0 if n_draw < 120 else 6.0 if n_draw < 300 else 5.0
    idx = np.argsort(Z) if view.d3 else range(n_draw)
    for i in idx:
        depth = float(Z[i]) / max(A, B) if view.d3 else 0.0
        r = r0 * (1 + 0.28 * depth)
        a = 1.0 if not view.d3 else 0.6 + 0.4 * (depth + 1) / 2
        M.comet(ctx, float(X[i]), float(Y[i]), float(X2[i] - X[i]), float(Y2[i] - Y[i]), col[i],
                r, min(TAIL, float(since[i])), a)

    # wall on top (neon tube)
    M.glow_stroke(ctx, lambda c: _outline(c, A, B, view), M.WALL, 9)

    # texts
    M.question(ctx, t, cfg.question, y=330)
    if t >= res["t_answer"]:
        k = min(1.0, (t - res["t_answer"]) / 0.25)
        M.answer(ctx, cfg.answer, y=425, size=52 + 6 * (1 - k), alpha=k)
    else:
        shown = n if (tau is not None) else legs[j - 1]["n"]
        M.counter(ctx, "balls: ", f"{shown:,}", y=425)


# ===================================================================== audio + metadata
AUDIO_MIN_GAP = 0.0


def audio_events(res, cfg):
    out = []
    rng = random.Random(cfg.seed + 5)
    hits = sorted(res["wall_hits"])
    # thin out extreme bursts a little (keeps it a crackle, not a roar)
    last = -1.0
    for th in hits:
        if th - last < 0.012:
            continue
        last = th
        out.append((th, rng.choice([1320, 1480, 1660, 1760, 1980]), "click"))
    notes = melodies.track([tm for tm, _ in res["meets"]], cfg.melody, 0.0)
    for tm, nm in notes:
        out.append((tm, note_freq(nm), "bell"))
    out.append((res["t_answer"], 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    tpl = {"plain": "focus", "stretch": "focus_stretch", "3d": "focus_3d"}[cfg.kind]
    return dict(template=tpl, n_final=cfg.n_final, n_balls=cfg.n_final, colors=[], melody=cfg.melody_name)


class _Format:
    AUDIO_MIN_GAP = AUDIO_MIN_GAP

    def __init__(self, kind, name):
        self.kind = kind
        self.__name__ = name

    def make_config(self, seed):
        return make_config(seed, self.kind)

    simulate = staticmethod(simulate)
    is_good = staticmethod(is_good)
    draw = staticmethod(draw)
    audio_events = staticmethod(audio_events)
    prepare = staticmethod(prepare)
    metadata_facts = staticmethod(metadata_facts)


focus = _Format("plain", "focus")
focus_stretch = _Format("stretch", "focus_stretch")
focus_3d = _Format("3d", "focus_3d")
