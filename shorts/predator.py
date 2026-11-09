"""
"Predator": 500 prey dots run around a circle. ONE predator hunts them, and every prey it
catches BECOMES a predator too, so the hunters double and double until nobody is left.
Counter of predators; ends with "ALL 500 CAUGHT in 21.4 s". Notes follow a public-domain tune.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies, refkit

CX, CY, R = 540, 1000, 450
MAX_T = 34.0
END_HOLD = 2.8
SUB = 2
CATCH = 9.0
SENSE = 240.0
REST = 0.45                # a predator that just ate (or was just born) rests this long
CAPS = ["Every prey they catch | BECOMES a predator",
        "Every catch makes a NEW predator | How long until ALL are caught?",
        "1 predator. 500 prey | Every catch JOINS the hunt"]
PREY_COLS = [(1.0, 0.86, 0.2), (0.35, 1.0, 0.55), (0.3, 0.85, 1.0)]
PRED_COL = (1.0, 0.22, 0.45)


@dataclass
class Config:
    seed: int
    n: int
    v_prey: float
    v_pred: float
    prey_col: tuple
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 3907 + 13)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.choice([400, 500, 500, 600]), rng.uniform(135, 145), rng.uniform(192, 206),
                  rng.choice(PREY_COLS), mel, melodies.MELODIES[mel], rng.choice(CAPS))


def _keep_inside(p, v):
    d = p - (CX, CY)
    r = np.hypot(d[:, 0], d[:, 1])
    out = r > R - 6
    if out.any():
        n = d[out] / r[out, None]
        p[out] = (CX, CY) + n * (R - 6)
        vn = (v[out] * n).sum(1)
        v[out] -= np.maximum(vn, 0)[:, None] * n * 1.6        # slide along the wall, bounce a bit


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    a = rng.uniform(0, 2 * np.pi, cfg.n)
    rr = R * 0.95 * np.sqrt(rng.uniform(0.02, 1, cfg.n))
    prey = np.stack([CX + rr * np.cos(a), CY + rr * np.sin(a)], 1)
    pv = rng.normal(0, 1, (cfg.n, 2)) * 50
    k = int(rng.integers(cfg.n))
    pred = prey[k:k + 1].copy()
    prey = np.delete(prey, k, 0)
    pv = np.delete(pv, k, 0)
    qv = np.zeros((1, 2))
    rest = np.zeros(1)
    t, t_end = 0.0, None
    frames, hits = [], []
    sparks = []
    h = DT / SUB
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            for s in range(SUB):
                tt = t + s * h
                d = prey[:, None, :] - pred[None, :, :]                 # prey x pred
                dist = np.hypot(d[..., 0], d[..., 1]) + 1e-6
                j = dist.argmin(1)
                dn = dist[np.arange(len(prey)), j]
                away = d[np.arange(len(prey)), j] / dn[:, None]
                # prey: flee if a predator is close, else wander
                wander = pv + rng.normal(0, 1, pv.shape) * 260 * h
                ws = np.hypot(wander[:, 0], wander[:, 1])[:, None] + 1e-6
                wander = wander / ws * np.minimum(ws, 55)
                scared = dn < SENSE
                pv = np.where(scared[:, None], away * cfg.v_prey, wander)
                # predators: chase the nearest prey, keep a little apart from each other
                i = dist.argmin(0)
                tgt = prey[i] - pred
                tn = np.hypot(tgt[:, 0], tgt[:, 1])[:, None] + 1e-6
                qv = tgt / tn * cfg.v_pred * (rest <= 0)[:, None]
                rest -= h
                if len(pred) > 1:
                    dq = pred[:, None, :] - pred[None, :, :]
                    dd = np.hypot(dq[..., 0], dq[..., 1]) + 1e-6
                    push = np.where((dd < 22)[..., None], dq / dd[..., None] ** 2 * 900, 0).sum(1)
                    qv = qv + push
                prey = prey + pv * h
                pred = pred + qv * h
                _keep_inside(prey, pv)
                _keep_inside(pred, qv)
                # each predator that is not resting eats at most its nearest prey
                d2 = prey[:, None, :] - pred[None, :, :]
                dist2 = np.hypot(d2[..., 0], d2[..., 1])
                dist2[:, rest > 0] = np.inf
                near = dist2.argmin(0)
                ok = dist2[near, np.arange(len(pred))] < CATCH
                if ok.any():
                    eaters = np.flatnonzero(ok)
                    idx, first = np.unique(near[eaters], return_index=True)
                    eaters = eaters[first]
                    for c in idx:
                        hits.append(tt)
                        sparks.append((float(prey[c, 0]), float(prey[c, 1]), tt))
                    rest[eaters] = REST
                    pred = np.concatenate([pred, prey[idx]])
                    rest = np.concatenate([rest, np.full(len(idx), REST)])
                    prey = np.delete(prey, idx, 0)
                    pv = np.delete(pv, idx, 0)
                    if len(prey) == 0:
                        t_end = tt
                        break
        t += DT
        if record:
            sparks = [sp for sp in sparks if t - sp[2] < 0.5][-60:]
            frames.append(dict(t=t, prey=prey.astype(np.float32), pred=pred.astype(np.float32),
                               sparks=list(sparks), t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, t_end=t_end, n=cfg.n)


def is_good(res):
    return res["t_end"] is not None and 15 <= res["t_end"] <= 28


def _dots(ctx, pts, r, col, a=1.0):
    ctx.set_source_rgba(*col, a)
    for x, y in pts:
        ctx.new_sub_path()
        ctx.arc(float(x), float(y), r, 0, 2 * math.pi)
    ctx.fill()


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    ctx.new_path()
    ctx.arc(CX, CY, R, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 1, 1, 0.75)
    ctx.set_line_width(4)
    ctx.stroke()
    _dots(ctx, fr["prey"], 5.0, cfg.prey_col)
    _dots(ctx, fr["pred"], 13.0, PRED_COL, 0.13)
    _dots(ctx, fr["pred"], 6.0, PRED_COL)
    for (x, y, st) in fr["sparks"]:
        k = (t - st) / 0.5
        ctx.new_path()
        ctx.arc(x, y, 6 + 26 * k, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.7 * (1 - k))
        ctx.set_line_width(3)
        ctx.stroke()
    npred = len(fr["pred"])
    text(ctx, f"Predators: {npred:,}", 540, 1525, 62, PRED_COL, 0.95)
    text(ctx, f"Prey left: {len(fr['prey']):,}", 540, 1592, 44, cfg.prey_col, 0.9)
    fx.music_line(ctx, y=1652)
    if fr["t_end"] is not None:
        fx.banner(ctx, t, fr["t_end"] + 0.4, f"ALL {cfg.n} CAUGHT!", PRED_COL,
                  f"in {fr['t_end']:.1f} seconds", dim=0.35)


AUDIO_MIN_GAP = 0.07


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"] + 0.05, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="predator", colors=[], melody=cfg.melody_name, n_balls=cfg.n, n_final=cfg.n,
                t_full=round(res["t_end"] or 0, 1))
