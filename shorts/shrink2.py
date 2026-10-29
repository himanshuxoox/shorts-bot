"""
Two new variants of the channel's hit "shrink" format (every bounce SHRINKS the ball and GROWS the
wall right where it hit, drawn as dense spokes):

  shrink_duo    TWO balls share the arena. Each bounce shrinks the ball that hit and grows the
                wall in THAT ball's colour. A ball that shrinks to a dot is OUT. Pick a colour!
  shrink_shape  one ball, but the arena is a HEXAGON / SQUARE / FLOWER / TRIANGLE, and the
                spokes are a rainbow. The free space turns into a shrinking star of that shape.

Every bounce plays the next note of a public-domain tune (as in the original).
"""
import math, random
from dataclasses import dataclass, field

import cairo
import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 8
CX, CY, R = 540, 980, 450
K = 720
SPOKES = 320
SPEED = 930.0
MAX_T = 34.0
END_HOLD = 2.8
SHAPES = ["hexagon", "square", "flower", "triangle"]
DUO = [("RED", (1.0, 0.3, 0.42), (1.0, 0.85, 0.88)), ("BLUE", (0.25, 0.6, 1.0), (0.85, 0.93, 1.0)),
       ("GREEN", (0.3, 0.95, 0.5), (0.88, 1.0, 0.9)), ("YELLOW", (1.0, 0.82, 0.2), (1.0, 0.96, 0.8)),
       ("PURPLE", (0.72, 0.45, 1.0), (0.93, 0.88, 1.0))]


@dataclass
class Config:
    seed: int
    kind: str
    shape: str
    rot: float
    r0: float
    shrink: float
    amp: float
    width: float
    teams: list
    hue0: float
    melody_name: str
    melody: list


def make_config(seed, kind):
    rng = random.Random(seed * 7177 + (11 if kind == "duo" else 23))
    mel = rng.choice(melodies.FAMOUS)
    teams = rng.sample(DUO, 2) if kind == "duo" else [rng.choice(DUO)]
    shape = "circle" if kind == "duo" else rng.choice(SHAPES)
    return Config(seed, kind, shape, rng.uniform(0, 2 * math.pi) if shape != "triangle" else -math.pi / 2,
                  rng.uniform(32, 40), rng.uniform(0.962, 0.974) if kind == "duo" else rng.uniform(0.968, 0.978),
                  rng.uniform(62, 80), math.radians(rng.uniform(10, 14)), teams, rng.random(), mel,
                  melodies.MELODIES[mel])


def base_radius(cfg, th):
    """outer wall radius for the arena shape at angle th (vectorised)."""
    th = np.asarray(th, float)
    if cfg.shape == "circle":
        return np.full(th.shape, R)
    if cfg.shape == "flower":
        return R * (0.86 + 0.14 * np.cos(6 * (th - cfg.rot)))
    n = {"hexagon": 6, "square": 4, "triangle": 3}[cfg.shape]
    ap = R * math.cos(math.pi / n) * (1.0 if n > 3 else 1.12)       # apothem (triangle a bit bigger)
    a = (th - cfg.rot) % (2 * math.pi / n) - math.pi / n
    return np.minimum(ap / np.cos(a), R * 1.08)


class _Arena:
    def __init__(self, cfg):
        self.cfg = cfg
        self.bins = np.arange(K) * 2 * math.pi / K
        self.base = base_radius(cfg, self.bins)
        self.depth = np.zeros(K)
        self.owner = np.full(K, -1)          # which team grew this bin last
        self.grown = np.full(K, -9.0)

    def rho(self, th):
        f = (th % (2 * math.pi)) / (2 * math.pi) * K
        i = int(f) % K
        j = (i + 1) % K
        a = f - int(f)
        b = self.base[i] * (1 - a) + self.base[j] * a
        return b - (self.depth[i] * (1 - a) + self.depth[j] * a)


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    ar = _Arena(cfg)
    n = len(cfg.teams)
    balls = []
    for k in range(n):
        a = rng.uniform(0, 2 * math.pi)
        off = (k - (n - 1) / 2) * 140
        balls.append(dict(x=CX + off, y=CY + rng.uniform(-40, 40), vx=SPEED * math.cos(a), vy=SPEED * math.sin(a),
                          r=cfg.r0, alive=True, bounces=0, trail=[], out_t=None))
    t, t_end = 0.0, None
    hits, frames, events = [], [], []
    winner = None
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            for s in range(SUB):
                h = DT / SUB
                tt = t + s * h
                for bi, b in enumerate(balls):
                    if not b["alive"]:
                        continue
                    b["x"] += b["vx"] * h
                    b["y"] += b["vy"] * h
                    dx, dy = b["x"] - CX, b["y"] - CY
                    d = math.hypot(dx, dy) or 1e-6
                    th = math.atan2(dy, dx)
                    rho = ar.rho(th)
                    if d + b["r"] >= rho:
                        eps = 2 * math.pi / K
                        drho = (ar.rho(th + eps) - ar.rho(th - eps)) / (2 * eps)
                        ux, uy = dx / d, dy / d
                        tx, ty = -uy, ux
                        nx, ny = rho * ux - drho * tx, rho * uy - drho * ty
                        nl = math.hypot(nx, ny) or 1.0
                        nx, ny = nx / nl, ny / nl
                        vn = b["vx"] * nx + b["vy"] * ny
                        if vn > 0:
                            b["vx"] -= 2 * vn * nx
                            b["vy"] -= 2 * vn * ny
                            kick = rng.uniform(-160, 160)
                            b["vx"] += -ny * kick
                            b["vy"] += nx * kick
                            sp = math.hypot(b["vx"], b["vy"])
                            b["vx"], b["vy"] = b["vx"] / sp * SPEED, b["vy"] / sp * SPEED
                            dth = (ar.bins - th + math.pi) % (2 * math.pi) - math.pi
                            bump = cfg.amp * np.exp(-(dth / cfg.width) ** 2)
                            ar.depth = np.minimum(ar.depth + bump, ar.base - 6)
                            mask = bump > 6
                            ar.grown[mask] = tt
                            ar.owner[mask] = bi
                            b["r"] = max(2.0, b["r"] * cfg.shrink)
                            b["bounces"] += 1
                            hits.append((tt, bi))
                        pen = d + b["r"] - ar.rho(th)
                        if pen > 0:
                            b["x"] -= ux * pen
                            b["y"] -= uy * pen
                    if b["r"] <= 3.2 and n > 1:
                        b["alive"] = False
                        b["out_t"] = tt
                        events.append((tt, "out", bi))
                # ball-ball collisions (equal mass, elastic)
                if n > 1 and balls[0]["alive"] and balls[1]["alive"]:
                    A, B = balls
                    dx, dy = B["x"] - A["x"], B["y"] - A["y"]
                    dist = math.hypot(dx, dy) or 1e-6
                    if dist < A["r"] + B["r"]:
                        nx, ny = dx / dist, dy / dist
                        rel = (A["vx"] - B["vx"]) * nx + (A["vy"] - B["vy"]) * ny
                        if rel > 0:
                            A["vx"] -= rel * nx; A["vy"] -= rel * ny
                            B["vx"] += rel * nx; B["vy"] += rel * ny
                            events.append((tt, "clash", -1))
                        over = A["r"] + B["r"] - dist
                        A["x"] -= nx * over / 2; A["y"] -= ny * over / 2
                        B["x"] += nx * over / 2; B["y"] += ny * over / 2
                alive = [i for i, b in enumerate(balls) if b["alive"]]
                inner = (ar.base - ar.depth).mean()
                if n > 1 and len(alive) == 1:
                    winner = alive[0]
                    t_end = tt
                    break
                if n == 1 and (balls[0]["r"] <= 3.0 or inner < 60):
                    t_end = tt
                    break
                if n > 1 and inner < 60:                       # wall closed: biggest ball wins
                    winner = max(alive, key=lambda i: balls[i]["r"])
                    t_end = tt
                    break
        t += DT
        for b in balls:
            b["trail"].append((b["x"], b["y"], b["r"]))
            b["trail"] = b["trail"][-10:]
        if record:
            frames.append(dict(t=t, balls=[(b["x"], b["y"], b["r"], b["alive"], list(b["trail"]), b["bounces"])
                                           for b in balls],
                               depth=ar.depth.copy(), grown=ar.grown.copy(), owner=ar.owner.copy(), t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, t_end=t_end, winner=winner, events=events, n=n,
                bounces=sum(b["bounces"] for b in balls), base=ar.base)


def is_good(res):
    if res["t_end"] is None or not (16 <= res["t_end"] <= 30) or res["bounces"] < 60:
        return False
    return res["n"] == 1 or res["winner"] is not None


def _spoke_col(cfg, fr, i, t):
    fresh = max(0.0, 1 - (t - fr["grown"][i]) / 0.6)
    if cfg.kind == "duo":
        own = fr["owner"][i]
        _n, col, hi = cfg.teams[own if own >= 0 else 0]
    else:
        col = fx.hsv(cfg.hue0 + i / K, 0.75, 1.0)
        hi = (1, 1, 1)
    return tuple(a + (b - a) * fresh * 0.8 for a, b in zip(col, hi))


_BASE = {}


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    if cfg.kind == "duo":
        (n1, c1, _), (n2, c2, _) = cfg.teams
        fx.rich_title(ctx, [[("Every bounce ", fx.WHITE), ("SHRINKS", fx.CYAN), (" the ball", fx.WHITE)],
                            [(n1.title(), c1), (" vs ", fx.WHITE), (n2.title(), c2), (" — who lasts?", fx.WHITE)]])
    else:
        fx.rich_title(ctx, [[("Every bounce ", fx.WHITE), ("SHRINKS", fx.CYAN), (" the ball", fx.WHITE)],
                            [("and ", fx.WHITE), ("GROWS", fx.GOLD), (f" the {cfg.shape}", fx.WHITE)]])
    base = _BASE.get((cfg.seed, cfg.kind))
    if base is None:
        base = base_radius(cfg, np.arange(K) * 2 * math.pi / K)
        _BASE[(cfg.seed, cfg.kind)] = base
    depth = fr["depth"]
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    ctx.set_line_width(2.6)
    for k in range(SPOKES):
        i = k * K // SPOKES
        if depth[i] < 1.5:
            continue
        th = i * 2 * math.pi / K
        c, s = math.cos(th), math.sin(th)
        ctx.set_source_rgb(*_spoke_col(cfg, fr, i, t))
        ctx.move_to(CX + base[i] * c, CY + base[i] * s)
        ctx.line_to(CX + (base[i] - depth[i]) * c, CY + (base[i] - depth[i]) * s)
        ctx.stroke()
    # outer wall
    ctx.set_line_width(6)
    wall_col = (1, 1, 1) if cfg.kind == "duo" else fx.hsv(cfg.hue0, 0.6, 1.0)
    ctx.set_source_rgb(*wall_col)
    ctx.new_path()
    for i in range(K + 1):
        th = (i % K) * 2 * math.pi / K
        x, y = CX + base[i % K] * math.cos(th), CY + base[i % K] * math.sin(th)
        (ctx.move_to if i == 0 else ctx.line_to)(x, y)
    ctx.close_path()
    ctx.stroke()
    for bi, (x, y, r, alive, trail, nb) in enumerate(fr["balls"]):
        col = cfg.teams[bi][1]
        if not alive:
            continue
        for i, (tx, ty, tr) in enumerate(trail[:-1]):
            ctx.set_source_rgba(*col, 0.12 * (i + 1) / len(trail))
            ctx.new_path()
            ctx.arc(tx, ty, tr, 0, 2 * math.pi)
            ctx.fill()
        fx.ball(ctx, x, y, r, col, 0, (), glow=True)
    if cfg.kind == "duo":
        items = []
        for bi, (x, y, r, alive, trail, nb) in enumerate(fr["balls"]):
            name, col, _ = cfg.teams[bi]
            items.append((name if alive else f"{name} OUT", col, f"{r:4.1f}" if alive else "×"))
        for j, (lab, col, val) in enumerate(items):
            text(ctx, lab, 540 + (j - 0.5) * 420, 1555, 50, col, 0.95)
    else:
        text(ctx, f"{sum(b[5] for b in fr['balls'])} BOUNCES", 540, 1555, 56, (1, 1, 1), 0.9)
    fx.music_line(ctx, y=1640)
    if fr["t_end"] is not None:
        if cfg.kind == "duo":
            res_w = _RES.get((cfg.seed, cfg.kind))
            name, col, _ = cfg.teams[res_w]
            fx.banner(ctx, t, fr["t_end"] + 0.2, f"{name} WINS!", col, "Did you pick it?", dim=0.35)
        else:
            nb = sum(b[5] for b in fr["balls"])
            fx.banner(ctx, t, fr["t_end"] + 0.2, f"{cfg.shape.upper()} WINS!", wall_col,
                      f"after {nb} bounces", dim=0.35)


_RES = {}


def prepare(res, cfg):
    _RES[(cfg.seed, cfg.kind)] = res["winner"]


AUDIO_MIN_GAP = 0.075


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track([h[0] for h in res["hits"]], cfg.melody,
                                                                    AUDIO_MIN_GAP)]
    for t, kind, _bi in res["events"]:
        if kind == "out":
            out.append((t, 330.0, "out"))
        elif kind == "clash":
            out.append((t, 880.0, "steal"))
    if res["t_end"] is not None:
        out.append((res["t_end"], 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    tpl = "shrink_duo" if cfg.kind == "duo" else "shrink_shape"
    cols = [n for n, _c, _h in cfg.teams] if cfg.kind == "duo" else []
    return dict(template=tpl, bounces=res["bounces"], colors=cols, t_end=round(res["t_end"], 2),
                melody=cfg.melody_name, shape=cfg.shape)


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


shrink_duo = _Format("duo", "shrink_duo")
shrink_shape = _Format("shape", "shrink_shape")
