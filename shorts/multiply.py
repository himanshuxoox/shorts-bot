"""
"Multiply": one ball starts in the middle of three breakable rings. Every ring segment it
hits shatters (and plays the next note of a famous tune). Multiplier tokens (x2, x3, x5, x10)
copy whatever ball touches them, so 1 ball becomes hundreds. When every ring is gone the
final ball count is revealed. Hook: guess how many balls there will be.
"""
import math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, DT, text, text_fit, note_freq
from . import fx, melodies

SUB = 6
CX, CY, R_OUT = 540, 960, 465
RINGS = [170, 275, 380]
NSEG = 36
RING_T = 16
BALL_R = 11
G = 650.0
VMIN, VMAX = 650.0, 1300.0
MAX_BALLS = 1500
MAX_T = 32.0
END_HOLD = 3.0
TOK_R = 38
COOLDOWN = 0.35

TITLES = ["Will the Ball Multiply ?", "1 ball… how many at the end?",
          "Guess the final ball count!", "Will the balls break every ring?"]


@dataclass
class Config:
    seed: int
    tokens: list         # [(x, y, mult)]
    hp: list             # hits needed per ring
    ring_cols: list
    melody_name: str
    melody: list
    title: str


def make_config(seed):
    rng = random.Random(seed * 6007 + 41)
    tokens = []
    bands = [(85, RINGS[0] - 48, [2, 3]), (RINGS[0] + 48, RINGS[1] - 44, [3, 5]),
             (RINGS[1] + 48, RINGS[2] - 44, [5, 10]), (RINGS[2] + 48, R_OUT - 44, [3, 5])]
    for (r0, r1, mults), cnt in zip(bands, [2, 2, 2, 3]):
        a0 = rng.uniform(0, 2 * math.pi)
        for j in range(cnt):
            a = a0 + 2 * math.pi * j / cnt + rng.uniform(-0.3, 0.3)
            rr = rng.uniform(r0, r1)
            tokens.append((CX + rr * math.cos(a), CY + rr * math.sin(a), rng.choice(mults)))
    h0 = rng.random()
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, tokens, [2, rng.choice([18, 22]), 48],
                  [fx.hsv(h0 + 0.18 * k, 0.7, 1.0) for k in range(3)], mel,
                  melodies.MELODIES[mel], rng.choice(TITLES))


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    a = rng.uniform(0, 2 * np.pi)
    x = np.array([float(CX)]); y = np.array([float(CY)])
    vx = np.array([900 * math.cos(a)]); vy = np.array([900 * math.sin(a)])
    hue = np.array([rng.random()])
    seg_hp = [np.full(NSEG, cfg.hp[k]) for k in range(3)]
    tok_ready = np.zeros(len(cfg.tokens))           # time when each token is active again
    tok_x = np.array([tk[0] for tk in cfg.tokens]); tok_y = np.array([tk[1] for tk in cfg.tokens])
    t, t_end = 0.0, None
    hits, breaks, tok_hits, frames = [], [], [], []

    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            vy += G * h
            x += vx * h
            y += vy * h
            dx, dy = x - CX, y - CY
            d = np.hypot(dx, dy) + 1e-9
            nx, ny = dx / d, dy / d
            vr = vx * nx + vy * ny
            # outer wall
            m = (d + BALL_R >= R_OUT) & (vr > 0)
            if m.any():
                vx[m] -= 2 * vr[m] * nx[m]; vy[m] -= 2 * vr[m] * ny[m]
                kick = rng.uniform(-90, 90, m.sum())
                vx[m] += -ny[m] * kick; vy[m] += nx[m] * kick
                hits.extend([tt] * min(2, int(m.sum())))
            o = d + BALL_R > R_OUT
            x[o] -= nx[o] * (d[o] + BALL_R - R_OUT); y[o] -= ny[o] * (d[o] + BALL_R - R_OUT)
            # breakable rings
            if t_end is None:
                ang = np.arctan2(dy, dx)
                seg = ((ang % (2 * np.pi)) / (2 * np.pi) * NSEG).astype(int) % NSEG
                vr = vx * nx + vy * ny
                for k, Rk in enumerate(RINGS):
                    dk = d - Rk
                    near = np.abs(dk) < BALL_R + RING_T / 2
                    if not near.any():
                        continue
                    idx = np.nonzero(near)[0]
                    alive = seg_hp[k][seg[idx]] > 0
                    idx = idx[alive]
                    if not len(idx):
                        continue
                    toward = ((dk[idx] < 0) & (vr[idx] > 0)) | ((dk[idx] > 0) & (vr[idx] < 0))
                    j = idx[toward]
                    if len(j):
                        vx[j] -= 2 * vr[j] * nx[j]; vy[j] -= 2 * vr[j] * ny[j]
                        for sg in np.unique(seg[j]):
                            seg_hp[k][sg] -= 1
                            if seg_hp[k][sg] <= 0:
                                breaks.append((tt, k, int(sg)))
                    # push out of the ring band
                    side = np.sign(dk[idx]); side[side == 0] = -1
                    target = Rk + side * (BALL_R + RING_T / 2 + 0.5)
                    x[idx] = CX + nx[idx] * target; y[idx] = CY + ny[idx] * target
                # multiplier tokens
                for ti, (tx, ty, mult) in enumerate(cfg.tokens):
                    if tt < tok_ready[ti] or len(x) >= MAX_BALLS:
                        continue
                    dd = np.hypot(x - tx, y - ty)
                    c = np.nonzero(dd < TOK_R + BALL_R)[0]
                    if not len(c):
                        continue
                    i = c[0]
                    tok_ready[ti] = tt + COOLDOWN
                    tok_hits.append((tt, ti, mult))
                    add = min(mult - 1, MAX_BALLS - len(x))
                    sp = math.hypot(vx[i], vy[i])
                    base = math.atan2(vy[i], vx[i])
                    angs = base + rng.uniform(-1.4, 1.4, add)
                    x = np.concatenate([x, np.full(add, x[i])])
                    y = np.concatenate([y, np.full(add, y[i])])
                    vx = np.concatenate([vx, sp * np.cos(angs)])
                    vy = np.concatenate([vy, sp * np.sin(angs)])
                    hue = np.concatenate([hue, (hue[i] + rng.uniform(0.05, 0.3, add)) % 1])
            sp = np.hypot(vx, vy) + 1e-9
            k_ = np.clip(sp, VMIN, VMAX) / sp
            vx *= k_; vy *= k_
            if t_end is None and all((hp <= 0).all() for hp in seg_hp):
                t_end = tt
        t += DT
        if record:
            frames.append(dict(t=t, x=x.astype(np.float32), y=y.astype(np.float32),
                               hue=hue.astype(np.float32), hp=[hp.copy() for hp in seg_hp],
                               tok_ready=tok_ready.copy(), n=len(x), t_end=t_end,
                               breaks=[b for b in breaks if t - b[0] < 0.8],
                               toks=[th for th in tok_hits if t - th[0] < 0.7]))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    first_ring = next((b[0] for b in breaks if b[1] == 0), None)
    return dict(frames=frames, hits=hits, breaks=breaks, tok_hits=tok_hits, t_end=t_end,
                n=len(x), first_break=first_ring,
                first_tok=tok_hits[0][0] if tok_hits else None)


def is_good(res):
    return (res["t_end"] is not None and 13 <= res["t_end"] <= 26 and 150 <= res["n"] <= MAX_BALLS
            and res["first_break"] is not None and res["first_break"] >= 1.0
            and res["first_tok"] is not None and res["first_tok"] <= 2.5)   # action starts fast


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.black(ctx)
    fx.neon_title(ctx, t, cfg.title)
    ctx.set_line_width(5)
    ctx.set_source_rgba(1, 1, 1, 0.9)
    ctx.new_path()
    ctx.arc(CX, CY, R_OUT, 0, 2 * math.pi)
    ctx.stroke()

    seg = 2 * math.pi / NSEG
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    for k, Rk in enumerate(RINGS):
        col = cfg.ring_cols[k]
        for sgi in range(NSEG):
            hp = fr["hp"][k][sgi]
            if hp <= 0:
                continue
            a = 1.0 if hp >= cfg.hp[k] else 0.55          # cracked segments look weaker
            ctx.set_source_rgba(*col, 0.18 * a)
            ctx.set_line_width(RING_T * 2.6)
            ctx.new_path()
            ctx.arc(CX, CY, Rk, sgi * seg + 0.02, (sgi + 1) * seg - 0.02)
            ctx.stroke()
            ctx.set_source_rgba(*col, a)
            ctx.set_line_width(RING_T)
            ctx.new_path()
            ctx.arc(CX, CY, Rk, sgi * seg + 0.02, (sgi + 1) * seg - 0.02)
            ctx.stroke()
    for (tb, k, sgi) in fr["breaks"]:
        am = (sgi + 0.5) * seg
        fx.burst(ctx, t, (tb, CX + RINGS[k] * math.cos(am), CY + RINGS[k] * math.sin(am),
                          cfg.ring_cols[k], cfg.seed + k * 100 + sgi, 7, 300, 0.7))

    # tokens
    for ti, (tx, ty, mult) in enumerate(cfg.tokens):
        ready = t >= fr["tok_ready"][ti]
        a = 1.0 if ready else 0.25
        ctx.new_path()
        ctx.arc(tx, ty, TOK_R, 0, 2 * math.pi)
        ctx.set_source_rgba(0.05, 0.05, 0.08, 0.9)
        ctx.fill_preserve()
        ctx.set_source_rgba(*fx.GOLD, a)
        ctx.set_line_width(4)
        ctx.stroke()
        text_fit(ctx, f"x{mult}", tx, ty + 12, 36, TOK_R * 1.6, fx.GOLD, a)
    for (th, ti, mult) in fr["toks"]:
        k = (t - th) / 0.7
        tx, ty, _ = cfg.tokens[ti]
        text(ctx, f"x{mult}!", tx, ty - 40 - 60 * k, 54, fx.GOLD, 1 - k)

    # balls
    xs, ys, hs = fr["x"], fr["y"], fr["hue"]
    for i in range(fr["n"]):
        ctx.set_source_rgb(*fx.hsv(float(hs[i]), 0.7, 1.0))
        ctx.new_path()
        ctx.arc(float(xs[i]), float(ys[i]), BALL_R, 0, 2 * math.pi)
        ctx.fill()

    text(ctx, f"{fr['n']:,} BALL{'S' if fr['n'] != 1 else ''}", 540, 1500, 60, (1, 1, 1), 0.95)
    fx.music_line(ctx)
    if fr["t_end"] is not None:
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"] + 0.3, f"{fr['n']:,} BALLS!", fx.GOLD,
                  "How close was your guess?", dim=0.45)


AUDIO_MIN_GAP = 0.08


def audio_events(res, cfg):
    times = [b[0] for b in res["breaks"]]
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(times, cfg.melody, AUDIO_MIN_GAP)]
    last = -9
    for (t, ti, mult) in res["tok_hits"]:
        if t - last > 0.12:
            out.append((t, 1046.5 if mult >= 5 else 784.0, "chime"))
            last = t
    if res["t_end"] is not None:
        out.append((res["t_end"], 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="multiply", n_final=res["n"], colors=[],
                t_end=round(res["t_end"], 2), melody=cfg.melody_name)
