"""
"Red ring": balls fall inside a ring made of 72 blue segments. A ball that hits a BLUE segment
paints it RED; a ball that hits a RED segment spawns +3 new balls. It snowballs until the whole
ring is red. Ball counter, "+3" pop-ups, and a melody note on every new red segment.
"""
import math, random
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from .common import FPS, DT, text, note_freq
from . import fx, melodies, refkit

CX, CY, R = 540, 1000, 450
SEG = 72
G = 1000.0
BR = 13.0
SUB = 4
MAX_T = 34.0
END_HOLD = 2.8
COOL = 0.8                    # a ball can spawn +3 at most once every COOL s
HIT_V = 220.0                 # slower touches (balls resting in the pile) don't count
CAPS = ["Every RED RING bounce spawns 3 | until the whole ring is RED",
        "BLUE turns RED. RED spawns 3 balls | How many balls at the end?",
        "Hit BLUE: it turns RED | Hit RED: +3 BALLS"]
BLUE = (0.25, 0.55, 1.0)
RED = (1.0, 0.18, 0.32)


@dataclass
class Config:
    seed: int
    cap: int
    h_ball: float
    rest: float
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 8317 + 29)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.choice([300, 350, 400]), rng.choice([0.12, 0.15, 0.3, 0.38]), rng.uniform(0.82, 0.9),
                  mel, melodies.MELODIES[mel], rng.choice(CAPS))


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    red = np.zeros(SEG, bool)
    p = np.array([[CX + rng.uniform(-80, 80), CY - 150.0]])
    a = rng.uniform(0, 2 * np.pi)
    v = np.array([[1100 * math.cos(a), 1100 * math.sin(a)]])
    cool = np.zeros(1)
    t, t_end = 0.0, None
    frames, paints, spawns, pops = [], [], [], []
    h = DT / SUB
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            for s in range(SUB):
                tt = t + s * h
                v[:, 1] += G * h
                cool -= h
                p += v * h
                # ring
                d = p - (CX, CY)
                dist = np.hypot(d[:, 0], d[:, 1]) + 1e-9
                n = d / dist[:, None]
                out = dist + BR > R
                if out.any():
                    vn = (v * n).sum(1)
                    hit = out & (vn > 0)
                    p[out] -= n[out] * (dist[out] + BR - R)[:, None]
                    v[hit] -= 2 * vn[hit, None] * n[hit]
                    strong = np.flatnonzero(hit & (vn > HIT_V))
                    new = []
                    for i in strong:
                        k = int((math.atan2(n[i, 1], n[i, 0]) % (2 * math.pi)) / (2 * math.pi) * SEG) % SEG
                        if not red[k]:
                            red[k] = True
                            paints.append((tt, k))
                        else:
                            # red is BOUNCY: the ball is thrown back in hard (keeps the top of the ring in play)
                            ang = math.atan2(-n[i, 1], -n[i, 0]) + rng.uniform(-0.5, 0.5)
                            sp = rng.uniform(1250, 1500)
                            v[i] = (sp * math.cos(ang), sp * math.sin(ang))
                        if red[k] and paints[-1:] != [(tt, k)] and len(p) + len(new) < cfg.cap and cool[i] <= 0:
                            cool[i] = COOL
                            # +3: launched back into the ring from the hit point
                            for _ in range(3):
                                ang = math.atan2(-n[i, 1], -n[i, 0]) + rng.uniform(-0.6, 0.6)
                                sp = rng.uniform(1250, 1500)
                                new.append((p[i, 0] - n[i, 0] * 3 * BR, p[i, 1] - n[i, 1] * 3 * BR,
                                            sp * math.cos(ang), sp * math.sin(ang)))
                            spawns.append(tt)
                            pops.append((float(p[i, 0] - n[i, 0] * 50), float(p[i, 1] - n[i, 1] * 50), tt))
                    if new:
                        arr = np.array(new)
                        p = np.vstack([p, arr[:, :2]])
                        v = np.vstack([v, arr[:, 2:]])
                        cool = np.concatenate([cool, np.full(len(arr), COOL)])
                    if red.all():
                        t_end = tt
                        break
                # balls bump into each other (soft, a bit of energy lost -> they pile up)
                if len(p) > 1:
                    pairs = cKDTree(p).query_pairs(2 * BR, output_type="ndarray")
                    if len(pairs):
                        i, j = pairs[:, 0], pairs[:, 1]
                        dd = p[i] - p[j]
                        dl = np.hypot(dd[:, 0], dd[:, 1]) + 1e-9
                        nn = dd / dl[:, None]
                        corr = (2 * BR - dl)[:, None] * nn * 0.5
                        np.add.at(p, i, corr)
                        np.add.at(p, j, -corr)
                        rv = ((v[i] - v[j]) * nn).sum(1)
                        app = rv < 0
                        imp = (-(1 + cfg.rest) * rv * 0.5 * app)[:, None] * nn
                        np.add.at(v, i, imp)
                        np.add.at(v, j, -imp)
        t += DT
        if record:
            pops = [q for q in pops if t - q[2] < 0.7][-40:]
            frames.append(dict(t=t, p=p.astype(np.float32), n_red=int(red.sum()), red=red.copy(),
                               pops=list(pops), t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, paints=paints, spawns=spawns, t_end=t_end, balls=len(p))


def is_good(res):
    return res["t_end"] is not None and 16 <= res["t_end"] <= 28 and res["balls"] >= 60


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption, colors=dict(RED=RED, BLUE=BLUE))
    red = fr["red"]
    step = 2 * math.pi / SEG
    for k in range(SEG):
        col = RED if red[k] else BLUE
        for w, a in ((30, 0.18), (14, 1.0)):
            ctx.new_path()
            ctx.arc(CX, CY, R + 8, k * step + 0.006, (k + 1) * step - 0.006)
            ctx.set_source_rgba(*col, a)
            ctx.set_line_width(w)
            ctx.stroke()
    ball = fx.hsv(cfg.h_ball, 0.75, 1.0)
    ctx.set_source_rgb(*ball)
    for x, y in fr["p"]:
        ctx.new_sub_path()
        ctx.arc(float(x), float(y), BR, 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.35)
    for x, y in fr["p"]:
        ctx.new_sub_path()
        ctx.arc(float(x) - 3.5, float(y) - 3.5, 3.5, 0, 2 * math.pi)
    ctx.fill()
    for (x, y, st) in fr["pops"]:
        k = (t - st) / 0.7
        text(ctx, "+3", x, y - 40 * k, 40, (1, 1, 1), 1 - k)
    n = len(fr["p"])
    text(ctx, f"BALLS: {n}", 540, 1532, 70, (1, 1, 1), 0.95)
    text(ctx, f"Red: {fr['n_red']} / {SEG}", 540, 1598, 44, RED, 0.95)
    fx.music_line(ctx, y=1652)
    if fr["t_end"] is not None:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.4, "THE RING IS RED!", RED, f"{n} balls", dim=0.35)


AUDIO_MIN_GAP = 0.07


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck")
           for t, nm in melodies.track([q[0] for q in res["paints"]], cfg.melody, AUDIO_MIN_GAP)]
    last = -1.0
    for t in res["spawns"]:
        if t - last > 0.09:
            out.append((t, 1046.5, "pop"))
            last = t
    if res["t_end"] is not None:
        out.append((res["t_end"] + 0.02, 523.25, "shatter"))
        out.append((res["t_end"] + 0.14, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="redring", colors=[], melody=cfg.melody_name, n_final=res["balls"],
                n_balls=res["balls"])
