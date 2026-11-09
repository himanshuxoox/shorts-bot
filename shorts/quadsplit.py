"""
"Quad split": one ball bounces inside one big box. Every bounce fills the box a bit; when it is
full it SPLITS into 4 smaller boxes, each with its own ball. Small boxes fill faster, so it
explodes: 1 -> 4 -> 16 -> 64 -> 256 -> 1,024 -> 4,096 boxes, ending as a rainbow mosaic.
"""
import math, random
from dataclasses import dataclass

import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies, refkit

X0, Y0, SIZE = 110, 570, 860
DEPTH = 6                       # 2^6 = 64 boxes per side at the end
UNIT = SIZE / 2 ** DEPTH
MAX_T = 34.0
END_HOLD = 3.0
P = 0.6                         # a box half as big has a ball 2^-0.6 = 66% as fast
CAPS = ["Every box it fills SPLITS into 4 | How SMALL can they get?",
        "When a box is FULL it SPLITS into 4 | How many boxes at the end?",
        "Every full box SPLITS into 4 | 1 → 4 → 16 → … ?"]


@dataclass
class Config:
    seed: int
    v: float
    k: int                  # bounces to fill a box at depth 0; one more per level
    h0: float
    hspan: float
    melody_name: str
    melody: list
    caption: str


def make_config(seed):
    rng = random.Random(seed * 4637 + 21)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(370, 430), 2, rng.random(), rng.uniform(0.5, 0.9),
                  mel, melodies.MELODIES[mel], rng.choice(CAPS))


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    # boxes in UNIT cells: ix, iy, size (cells), depth; one ball per unfinished box
    ix = np.array([0]); iy = np.array([0]); dep = np.array([0])
    cnt = np.array([0])
    done = np.array([False])
    a = rng.uniform(0, 2 * np.pi)
    px = np.array([X0 + SIZE * rng.uniform(0.35, 0.65)]); py = np.array([Y0 + SIZE * rng.uniform(0.35, 0.65)])
    vx = np.array([cfg.v * math.cos(a)]); vy = np.array([cfg.v * math.sin(a)])
    t, t_end = 0.0, None
    frames, hits = [], []
    flash = []
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        if t_end is None:
            size_c = 2 ** (DEPTH - dep)
            sub = max(2, math.ceil(cfg.v * DT / (UNIT * 0.3)))
            h = DT / sub
            for s in range(sub):
                tt = t + s * h
                live = ~done
                bs = size_c * UNIT
                x0 = X0 + ix * UNIT
                y0 = Y0 + iy * UNIT
                r = np.maximum(1.6, bs * 0.09)
                px = px + vx * h * live
                py = py + vy * h * live
                b1 = live & (px - r < x0) & (vx < 0)
                b2 = live & (px + r > x0 + bs) & (vx > 0)
                b3 = live & (py - r < y0) & (vy < 0)
                b4 = live & (py + r > y0 + bs) & (vy > 0)
                vx = np.where(b1 | b2, -vx, vx)
                vy = np.where(b3 | b4, -vy, vy)
                cnt = cnt + b1 + b2 + b3 + b4
                full = live & (cnt >= cfg.k + dep)
                if full.any():
                    leaf = full & (dep == DEPTH)
                    done = done | leaf
                    for q in np.flatnonzero(leaf):
                        flash.append((int(ix[q]), int(iy[q]), int(dep[q]), tt))
                    sp = np.flatnonzero(full & (dep < DEPTH))
                    if len(sp):
                        hits.extend([tt] * len(sp))
                        keep = np.ones(len(ix), bool)
                        keep[sp] = False
                        half = 2 ** (DEPTH - dep[sp] - 1)
                        nx = np.concatenate([ix[sp], ix[sp] + half, ix[sp], ix[sp] + half])
                        ny = np.concatenate([iy[sp], iy[sp], iy[sp] + half, iy[sp] + half])
                        nd = np.tile(dep[sp] + 1, 4)
                        nh = np.tile(half, 4) * UNIT
                        ang = rng.uniform(0, 2 * np.pi, len(nx))
                        for q in sp:
                            flash.append((int(ix[q]), int(iy[q]), int(dep[q]), tt))
                        ix = np.concatenate([ix[keep], nx])
                        iy = np.concatenate([iy[keep], ny])
                        dep = np.concatenate([dep[keep], nd])
                        cnt = np.concatenate([cnt[keep], np.zeros(len(nx), int)])
                        done = np.concatenate([done[keep], np.zeros(len(nx), bool)])
                        px = np.concatenate([px[keep], X0 + nx * UNIT + nh * rng.uniform(0.3, 0.7, len(nx))])
                        py = np.concatenate([py[keep], Y0 + ny * UNIT + nh * rng.uniform(0.3, 0.7, len(nx))])
                        vv = cfg.v * (nh / SIZE) ** P
                        vx = np.concatenate([vx[keep], vv * np.cos(ang)])
                        vy = np.concatenate([vy[keep], vv * np.sin(ang)])
                        size_c = 2 ** (DEPTH - dep)
                    if done.all():
                        t_end = tt
                        break
        t += DT
        if record:
            flash = [f for f in flash if t - f[3] < 0.4][-300:]
            frames.append(dict(t=t, ix=ix.astype(np.int16), iy=iy.astype(np.int16), dep=dep.astype(np.int8),
                               cnt=cnt.astype(np.int8), done=done.copy(),
                               px=px.astype(np.float32), py=py.astype(np.float32), flash=list(flash),
                               t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    return dict(frames=frames, hits=hits, t_end=t_end, n_final=int(len(ix)))


def is_good(res):
    return res["t_end"] is not None and 16 <= res["t_end"] <= 28


def _hue(cfg, cx, cy):
    return cfg.h0 + cfg.hspan * ((cx - X0) + (cy - Y0)) / (2 * SIZE)


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    refkit.caption(ctx, cfg.caption)
    ix, iy, dep, cnt, done = fr["ix"], fr["iy"], fr["dep"], fr["cnt"], fr["done"]
    n = len(ix)
    sz = (2.0 ** (DEPTH - dep.astype(float))) * UNIT
    x0 = X0 + ix * UNIT
    y0 = Y0 + iy * UNIT
    for q in range(n):
        s = float(sz[q])
        col = fx.hsv(_hue(cfg, x0[q] + s / 2, y0[q] + s / 2), 0.72, 1.0)
        f = 1.0 if done[q] else cnt[q] / (cfg.k + dep[q])
        ctx.set_source_rgba(*col, 0.14)                     # empty box: faint tint
        ctx.rectangle(float(x0[q]), float(y0[q]), s, s)
        ctx.fill()
        if f > 0:                                           # it fills up from the bottom like water
            ctx.set_source_rgba(*col, 0.95)
            ctx.rectangle(float(x0[q]), float(y0[q]) + s * (1 - f), s, s * f)
            ctx.fill()
    # grid lines (skip at the very end: the mosaic looks better clean)
    lw = 2.0 if n < 300 else 1.0
    ctx.set_line_width(lw)
    ctx.set_source_rgba(0, 0, 0, 0.75)
    for q in range(n):
        s = float(sz[q])
        ctx.rectangle(float(x0[q]), float(y0[q]), s, s)
    ctx.stroke()
    for (bx, by, d, ft) in fr["flash"]:
        k = (t - ft) / 0.4
        s = 2 ** (DEPTH - d) * UNIT
        ctx.set_source_rgba(1, 1, 1, 0.35 * (1 - k))
        ctx.rectangle(X0 + bx * UNIT, Y0 + by * UNIT, s, s)
        ctx.fill()
    # balls
    live = ~done
    r = np.maximum(1.6, sz * 0.09)
    ctx.set_source_rgb(1, 1, 1)
    for q in np.flatnonzero(live):
        ctx.new_sub_path()
        ctx.arc(float(fr["px"][q]), float(fr["py"][q]), float(r[q]), 0, 2 * math.pi)
    ctx.fill()
    ctx.set_source_rgba(1, 1, 1, 0.9)
    ctx.set_line_width(4)
    ctx.rectangle(X0 - 2, Y0 - 2, SIZE + 4, SIZE + 4)
    ctx.stroke()
    text(ctx, f"Boxes: {n:,}", 540, 1525, 62, fx.GOLD, 0.95)
    text(ctx, f"Smallest box: {float(sz.min()):.0f} px", 540, 1592, 44, (1, 1, 1), 0.85)
    fx.music_line(ctx, y=1652)
    if fr["t_end"] is not None:
        fx.banner(ctx, t, fr["t_end"] + 0.5, f"{n:,} BOXES!", fx.GOLD, "All from ONE box", dim=0.35)


AUDIO_MIN_GAP = 0.07


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["hits"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"] + 0.02, 523.25, "shatter"))
        out.append((res["t_end"] + 0.14, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="quadsplit", colors=[], melody=cfg.melody_name, n_final=res["n_final"],
                n_balls=res["n_final"])
