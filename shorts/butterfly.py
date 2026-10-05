"""
"Butterfly effect": 12-30 balls start at almost exactly the same spot (fractions of a pixel
apart). For a few seconds they move as ONE ball, then chaos splits them into a fan of
rainbow trails. Parts of the wall are lined with spikes — touch a spike and you pop.
The last ball alive wins. Every wall bounce plays the next note of a famous tune.
"""
import math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, DT, text, text_fit, note_freq
from . import fx, melodies

SUB = 10
CX, CY, R = 540, 960, 460
BALL_R = 17
G = 900.0
DEPTH = 46
MAX_T = 34.0
END_HOLD = 2.8
TRAIL = 22
PEG_X, PEG_Y, PEG_R = CX, CY + 90, 46     # a round peg: makes tiny differences grow fast
GAIN, VMAX = 1.03, 1900.0                 # bounces add a little energy -> balls climb higher

TITLES = ["The Butterfly Effect of a Bouncing Ball !...", "The Butterfly Effect",
          "{n} balls. Same start. Who survives?", "Which ball survives the spikes?"]


@dataclass
class Config:
    seed: int
    n: int
    zones: list          # [(a0, a1)] spike arcs (radians, screen angles: 0 = right, +pi/2 = down)
    vx0: float
    eps: float
    spike_col: tuple
    melody_name: str
    melody: list
    title: str
    labels: list = None  # optional display names (from the trend scout)


def make_config(seed, labels=None):
    rng = random.Random(seed * 7727 + 5)
    n = rng.choice([12, 16, 20, 24, 30])
    if labels:
        n = len(labels)
    # spike zones sit in the upper part of the wall: the balls can only reach them once the
    # bounces have pumped in enough energy, which is after they have split apart
    zones = []
    k = rng.choice([3, 4, 5])
    lo, hi = -math.pi + 0.3, -0.3            # screen angles: -pi/2 is the top
    for i in range(k):
        mid = lo + (hi - lo) * (i + 0.5) / k + rng.uniform(-0.12, 0.12)
        half = (hi - lo) / k * rng.uniform(0.28, 0.36)
        zones.append((mid - half, mid + half))
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, n, zones, rng.uniform(140, 320) * rng.choice([-1, 1]),
                  rng.choice([0.01, 0.02, 0.05]), rng.choice([(0.25, 1.0, 0.35), (1.0, 0.3, 0.4),
                                                              (1.0, 0.85, 0.2), (0.3, 0.85, 1.0)]),
                  mel, melodies.MELODIES[mel], rng.choice(TITLES).format(n=n), labels)


def _covers(zone, ang, pad=0.0):
    a0, a1 = zone
    rel = (ang - a0) % (2 * math.pi)
    return rel <= (a1 - a0) + pad or rel >= 2 * math.pi - pad


def in_spikes(zones, ang):
    return any(_covers(z, ang) for z in zones)


def simulate(cfg, record=False):
    n = cfg.n
    x = np.full(n, float(CX)) + np.arange(n) * cfg.eps
    y = np.full(n, CY - 20.0)
    vx = np.full(n, cfg.vx0)
    vy = np.zeros(n)
    alive = np.ones(n, bool)
    trails = [[] for _ in range(n)]
    deaths, bounce_t, events, frames = [], [], [], []
    t, t_end, split_t = 0.0, None, None
    inner = R - BALL_R
    depth = DEPTH

    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            if t > 24:      # guaranteed ending: spikes slowly grow longer
                depth = DEPTH + 18 * (t - 24)
            for s in range(SUB):
                h = DT / SUB
                tt = t + s * h
                vy += G * h
                x += vx * h
                y += vy * h
                dx, dy = x - CX, y - CY
                d = np.hypot(dx, dy)
                hit = alive & (d >= inner - 1e-9)
                for i in np.nonzero(hit)[0]:
                    ang = math.atan2(dy[i], dx[i])
                    if in_spikes(cfg.zones, ang):
                        continue  # handled below (spike tips sit further in)
                    nx, ny = dx[i] / d[i], dy[i] / d[i]
                    vn = vx[i] * nx + vy[i] * ny
                    if vn > 0:
                        vx[i] -= 2 * vn * nx
                        vy[i] -= 2 * vn * ny
                        sp = math.hypot(vx[i], vy[i])
                        k_ = min(GAIN, VMAX / max(sp, 1e-6))
                        vx[i] *= k_
                        vy[i] *= k_
                        bounce_t.append(tt)
                    pen = d[i] - inner
                    x[i] -= nx * pen
                    y[i] -= ny * pen
                px_, py_ = x - PEG_X, y - PEG_Y
                pd = np.hypot(px_, py_)
                for i in np.nonzero(alive & (pd < PEG_R + BALL_R))[0]:
                    nx, ny = px_[i] / pd[i], py_[i] / pd[i]
                    vn = vx[i] * nx + vy[i] * ny
                    if vn < 0:
                        vx[i] -= 2 * vn * nx
                        vy[i] -= 2 * vn * ny
                        bounce_t.append(tt)
                    pen = PEG_R + BALL_R - pd[i]
                    x[i] += nx * pen
                    y[i] += ny * pen
                near = alive & (d >= R - depth - BALL_R)
                for i in np.nonzero(near)[0]:
                    ang = math.atan2(dy[i], dx[i])
                    if in_spikes(cfg.zones, ang):
                        alive[i] = False
                        deaths.append((tt, int(i), float(x[i]), float(y[i])))
                        events.append((tt, "pop", int(i)))
                if alive.sum() <= 1:
                    t_end = tt
                    events.append((tt, "win", None))
                    break
            if split_t is None and alive.sum() >= 2:
                ax, ay = x[alive], y[alive]
                if max(ax.max() - ax.min(), ay.max() - ay.min()) > 45:
                    split_t = t
        t += DT
        for i in range(n):
            if alive[i]:
                trails[i].append((float(x[i]), float(y[i])))
                trails[i] = trails[i][-TRAIL:]
        if record:
            frames.append(dict(t=t, x=x.copy(), y=y.copy(), alive=alive.copy(), depth=depth,
                               trails=[list(tr) if alive[i] else [] for i, tr in enumerate(trails)],
                               deaths=[d_ for d_ in deaths if t - d_[0] < 1.0], t_end=t_end,
                               left=int(alive.sum())))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    win = int(np.nonzero(alive)[0][0]) if alive.sum() == 1 else None
    return dict(frames=frames, events=events, bounces=bounce_t, t_end=t_end, split_t=split_t,
                winner=win, deaths=[d_[0] for d_ in deaths])


def is_good(res):
    if res["t_end"] is None or res["winner"] is None or not (16 <= res["t_end"] <= 30):
        return False
    if res["split_t"] is None or not (2.0 <= res["split_t"] <= 7.0):
        return False
    d = sorted(res["deaths"])
    if not d or d[0] < res["split_t"]:           # nobody may die before the split
        return False
    return len(d) >= 2 and d[-1] - d[-2] >= 1.5        # a real final duel


def ball_color(cfg, i):
    return fx.hsv(i / cfg.n, 0.75, 1.0)


def ball_name(cfg, i):
    if cfg.labels:
        return cfg.labels[i]
    return f"BALL #{i + 1}"


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.neon_title(ctx, t, cfg.title)

    # wall + spikes
    ctx.set_line_width(5)
    ctx.set_source_rgba(1, 1, 1, 0.85)
    ctx.new_path()
    ctx.arc(CX, CY, R, 0, 2 * math.pi)
    ctx.stroke()
    depth = fr["depth"]
    for (a0, a1) in cfg.zones:
        nteeth = max(2, int((a1 - a0) / math.radians(5.5)))
        for k in range(nteeth):
            b0 = a0 + (a1 - a0) * k / nteeth
            b1 = a0 + (a1 - a0) * (k + 1) / nteeth
            bm = (b0 + b1) / 2
            ctx.move_to(CX + R * math.cos(b0), CY + R * math.sin(b0))
            ctx.line_to(CX + (R - depth) * math.cos(bm), CY + (R - depth) * math.sin(bm))
            ctx.line_to(CX + R * math.cos(b1), CY + R * math.sin(b1))
            ctx.close_path()
        ctx.set_source_rgb(*cfg.spike_col)
        ctx.fill()

    # peg
    g = cairo.RadialGradient(PEG_X - 12, PEG_Y - 12, 4, PEG_X, PEG_Y, PEG_R)
    g.add_color_stop_rgb(0, 1, 1, 1)
    g.add_color_stop_rgb(1, 0.55, 0.55, 0.6)
    ctx.set_source(g)
    ctx.new_path()
    ctx.arc(PEG_X, PEG_Y, PEG_R, 0, 2 * math.pi)
    ctx.fill()

    # trails then balls
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i, tr in enumerate(fr["trails"]):
        if len(tr) < 2:
            continue
        col = ball_color(cfg, i)
        for j in range(1, len(tr)):
            ctx.set_source_rgba(*col, 0.65 * j / len(tr))
            ctx.set_line_width(2 + 5 * j / len(tr))
            ctx.move_to(*tr[j - 1])
            ctx.line_to(*tr[j])
            ctx.stroke()
    for i in range(cfg.n):
        if fr["alive"][i]:
            fx.ball(ctx, fr["x"][i], fr["y"][i], BALL_R, ball_color(cfg, i), 0, (), glow=cfg.n <= 16)
    for (td, i, px, py) in fr["deaths"]:
        fx.burst(ctx, t, (td, px, py, ball_color(cfg, i), cfg.seed + i * 13, 26, 520, 0.9))

    if fr["t_end"] is None:
        text(ctx, f"{fr['left']} LEFT", 540, 1500, 56, (1, 1, 1), 0.9)
    fx.music_line(ctx)
    if fr["t_end"] is not None:
        wi = int(np.nonzero(fr["alive"])[0][0])
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"], f"{ball_name(cfg, wi)} SURVIVED!", ball_color(cfg, wi),
                  "Did you see it coming?")


AUDIO_MIN_GAP = 0.085


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck")
           for t, nm in melodies.track(res["bounces"], cfg.melody, AUDIO_MIN_GAP)]
    for t, kind, _ in res["events"]:
        out.append((t, 880.0, "pop") if kind == "pop" else (t, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="butterfly", n_balls=cfg.n, colors=[], labels=cfg.labels or [],
                t_end=round(res["t_end"], 2), melody=cfg.melody_name)
