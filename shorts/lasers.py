"""
"Lasers vs Doubling": pink balls bounce in a circle and every ball keeps splitting in two.
Laser turrets sit on the rim. Each laser zaps a ball every few seconds, and every ball a
laser hits turns into a NEW laser on the rim. Exponential vs exponential: can the lasers
stop the doubling? Every zap plays the next note of a famous public-domain tune.
"""
import bisect, math, random
from dataclasses import dataclass

import cairo
import numpy as np

from .common import FPS, DT, text, note_freq
from . import fx, melodies

SUB = 2
CX, CY, RR = 540.0, 1000.0, 430.0
BR = 9.0                                   # ball radius
V0 = 260.0
BCAP = 1400                                # balls win if they reach this
MAX_T = 40.0
END_HOLD = 3.2
PINK = (1.0, 0.25, 0.5)
LCYAN = (0.25, 0.85, 1.0)
BEAM_LIFE = 0.28


@dataclass
class Config:
    seed: int
    td: float          # ball doubling time (empty circle)
    crowd: float       # doubling slows down as the circle fills
    cd: float          # laser recharge time
    melody_name: str
    melody: list


def make_config(seed):
    rng = random.Random(seed * 9137 + 21)
    mel = rng.choice(melodies.FAMOUS)
    return Config(seed, rng.uniform(1.1, 1.3), rng.uniform(95, 190), rng.uniform(2.5, 3.1),
                  mel, melodies.MELODIES[mel])


def simulate(cfg, record=False):
    rng = np.random.default_rng(cfg.seed)
    prng = random.Random(cfg.seed)
    a = rng.uniform(0, 2 * np.pi)
    x = np.array([CX + 120 * math.cos(a)]); y = np.array([CY + 120 * math.sin(a)])
    vx = np.array([V0 * math.cos(a + 2)]); vy = np.array([V0 * math.sin(a + 2)])
    nsplit = np.array([cfg.td * 0.5])
    la = [-math.pi / 2]                     # laser angles on the rim
    lborn = [0.0]
    lnext = [2.2]
    beams, zaps, splits, frames = [], [], [], []
    t, t_end, winner, final_t, final_target = 0.0, None, None, None, None
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            x += vx * h; y += vy * h
            if t_end is not None:
                continue
            # walls
            dx, dy = x - CX, y - CY
            d = np.hypot(dx, dy) + 1e-6
            m = d > RR - BR - 6
            if m.any():
                nx, ny = dx[m] / d[m], dy[m] / d[m]
                x[m] = CX + nx * (RR - BR - 6); y[m] = CY + ny * (RR - BR - 6)
                vn = vx[m] * nx + vy[m] * ny
                k = np.where(vn > 0, 2 * vn, 0)
                vx[m] -= k * nx; vy[m] -= k * ny
            # doubling
            due = np.nonzero(nsplit <= tt)[0]
            if len(due) and len(x) < BCAP:
                due = due[: BCAP - len(x)]
                ang = np.arctan2(vy[due], vx[due])
                turn = rng.uniform(0.5, 1.2, len(due))
                slow = 1 + len(x) / cfg.crowd
                nxt = tt + cfg.td * slow * rng.uniform(0.8, 1.2, len(due))
                x = np.concatenate([x, x[due]]); y = np.concatenate([y, y[due]])
                vx[due] = V0 * np.cos(ang - turn); vy[due] = V0 * np.sin(ang - turn)
                vx = np.concatenate([vx, V0 * np.cos(ang + turn)])
                vy = np.concatenate([vy, V0 * np.sin(ang + turn)])
                nsplit[due] = nxt
                nsplit = np.concatenate([nsplit, nxt + rng.uniform(0, 0.3, len(due))])
                splits.append((tt, len(due)))
            if len(x) >= BCAP:
                t_end, winner = tt, "balls"
                ang = np.arctan2(y - CY, x - CX) + rng.uniform(-0.4, 0.4, len(x))
                spd = rng.uniform(500, 1400, len(x))
                vx = np.cos(ang) * spd; vy = np.sin(ang) * spd
                break
            # final shot: the last ball gets hit by every laser at once
            if len(x) == 1 and final_t is None and len(la) > 15:
                final_t = tt + 0.9
                vx *= 0.15; vy *= 0.15
            if final_t is not None:
                if tt >= final_t:
                    bx, by = float(x[0]), float(y[0])
                    for ang in la:
                        beams.append((tt, CX + RR * math.cos(ang), CY + RR * math.sin(ang), bx, by, 1))
                    zaps.append(tt)
                    x, y, vx, vy, nsplit = x[:0], y[:0], vx[:0], vy[:0], nsplit[:0]
                    t_end, winner = tt, "lasers"
                continue
            # lasers fire
            dead = set()
            n = len(x)
            for i in range(len(la)):
                if lnext[i] > tt:
                    continue
                if n - len(dead) <= 1:                 # the last ball is saved for the final shot
                    break
                j = prng.randrange(n)
                tries = 0
                while j in dead and tries < 8:
                    j = prng.randrange(n); tries += 1
                if j in dead:
                    continue
                dead.add(j)
                lx, ly = CX + RR * math.cos(la[i]), CY + RR * math.sin(la[i])
                beams.append((tt, lx, ly, float(x[j]), float(y[j]), 0))
                zaps.append(tt)
                na = math.atan2(y[j] - CY, x[j] - CX)
                la.append(na); lborn.append(tt); lnext.append(tt + 0.5 + cfg.cd * prng.uniform(0.6, 1.0))
                lnext[i] = tt + cfg.cd * prng.uniform(0.85, 1.15)
            if dead:
                keep = np.ones(n, bool); keep[list(dead)] = False
                x, y, vx, vy, nsplit = x[keep], y[keep], vx[keep], vy[keep], nsplit[keep]
            if len(x) == 0:
                t_end, winner = tt, "lasers"
        t += DT
        if record:
            frames.append(dict(t=t, x=x.astype(np.float32), y=y.astype(np.float32),
                               vx=vx.astype(np.float32), vy=vy.astype(np.float32),
                               nb=len(x), nl=len(la), t_end=t_end, winner=winner, final_t=final_t))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    peak = max((f["nb"] for f in frames), default=0)
    return dict(frames=frames, beams=beams, zaps=zaps, splits=splits, la=la, lborn=lborn,
                t_end=t_end, winner=winner, nl=len(la), peak=peak)


def is_good(res):
    return res["t_end"] is not None and 20 <= res["t_end"] <= 33


def prepare(res, cfg):
    res["beam_t"] = [b[0] for b in res["beams"]]
    peak = 0
    for f in res["frames"]:
        peak = max(peak, f["nb"])
    res["peak"] = peak
    for f in res["frames"]:
        f["res"] = res


def _mix(a, b, k):
    return tuple(p + (q - p) * k for p, q in zip(a, b))


def draw(ctx, fr, cfg):
    res = fr["res"]
    t = fr["t"]
    nb, nl = fr["nb"], fr["nl"]
    fx.black(ctx)
    fx.rich_title(ctx, [[("Every ball the lasers hit turns into a ", fx.WHITE), ("LASER", LCYAN)],
                        [("Can they stop the ", fx.WHITE), ("DOUBLING", PINK), ("?", fx.WHITE)]],
                  y=300, size=54)
    share = nl / max(1, nb + nl)
    broken = fr["winner"] == "balls" and t > fr["t_end"]
    if not broken:
        fx.glow_arc(ctx, CX, CY, RR, 0, 2 * math.pi, _mix(PINK, LCYAN, share ** 1.5), width=8)
    # beams
    bt = res["beam_t"]
    i0 = bisect.bisect_left(bt, t - BEAM_LIFE)
    i1 = bisect.bisect_right(bt, t)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for b in res["beams"][i0:i1]:
        k = 1 - (t - b[0]) / BEAM_LIFE
        for wdt, al, c in ((9, 0.25, LCYAN), (3, 0.95, (0.85, 1, 1))):
            ctx.set_source_rgba(*c, al * k)
            ctx.set_line_width(wdt)
            ctx.move_to(b[1], b[2]); ctx.line_to(b[3], b[4]); ctx.stroke()
        if t - b[0] < 0.2:                     # hit ring
            ctx.set_source_rgba(1, 1, 1, k)
            ctx.set_line_width(2.5)
            ctx.arc(b[3], b[4], BR + 30 * (t - b[0]) / 0.2, 0, 2 * math.pi); ctx.stroke()
    # balls with short comet tails
    xs, ys, vxs, vys = fr["x"], fr["y"], fr["vx"], fr["vy"]
    if len(xs):
        ctx.set_source_rgba(*PINK, 0.25)
        ctx.set_line_width(BR * 1.4)
        for x, y, vx, vy in zip(xs, ys, vxs, vys):
            ctx.move_to(float(x), float(y)); ctx.line_to(float(x - vx * 0.07), float(y - vy * 0.07))
        ctx.stroke()
        ctx.set_source_rgba(*PINK, 0.25)
        for x, y in zip(xs, ys):
            ctx.new_sub_path(); ctx.arc(float(x), float(y), BR * 1.8, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(1.0, 0.35, 0.58)
        for x, y in zip(xs, ys):
            ctx.new_sub_path(); ctx.arc(float(x), float(y), BR, 0, 2 * math.pi)
        ctx.fill()
    # laser turrets on the rim
    if not broken:
        for ang, born in zip(res["la"][:nl], res["lborn"][:nl]):
            k = min(1.0, (t - born) / 0.2)
            lx, ly = CX + RR * math.cos(ang), CY + RR * math.sin(ang)
            ctx.set_source_rgba(*LCYAN, 0.9 * k)
            ctx.set_line_width(3)
            ctx.arc(lx, ly, 8 * (1.6 - 0.6 * k), 0, 2 * math.pi); ctx.stroke()
            ctx.move_to(lx, ly); ctx.line_to(lx - 14 * math.cos(ang), ly - 14 * math.sin(ang)); ctx.stroke()
    # score bar
    x0, w, y0 = 240, 600, 1500
    pw = w * nb / max(1, nb + nl)
    ctx.set_source_rgb(*PINK); ctx.rectangle(x0, y0, pw, 14); ctx.fill()
    ctx.set_source_rgb(*LCYAN); ctx.rectangle(x0 + pw, y0, w - pw, 14); ctx.fill()
    _face = __import__("shorts.common", fromlist=["_face"])._face
    _face(ctx, 46, True)
    s1 = f"{nb:,} ball" + ("" if nb == 1 else "s")
    s2, s3 = "  vs  ", f"{nl:,} laser" + ("" if nl == 1 else "s")
    ws = [ctx.text_extents(s).x_advance for s in (s1, s2, s3)]
    xx = 540 - sum(ws) / 2
    for s_, wv, col in ((s1, ws[0], PINK), (s2, ws[1], (0.8, 0.8, 0.8)), (s3, ws[2], LCYAN)):
        ctx.move_to(xx, 1575); ctx.set_source_rgb(*col); ctx.show_text(s_); xx += wv
    ctx.new_path()
    fx.music_line(ctx, y=1640)
    if fr["t_end"] is not None:
        if fr["winner"] == "lasers":
            fx.banner(ctx, t, fr["t_end"] + 0.4, "LASERS WIN!", LCYAN, "Did you think they'd make it?", dim=0.3)
        else:
            fx.banner(ctx, t, fr["t_end"] + 0.4, "THE BALLS WIN!", PINK, "Did you think they'd make it?", dim=0.3)


AUDIO_MIN_GAP = 0.08


def audio_events(res, cfg):
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(res["zaps"], cfg.melody, AUDIO_MIN_GAP)]
    if res["t_end"] is not None:
        out.append((res["t_end"], 196.0, "shatter"))
        out.append((res["t_end"] + 0.15, 523.25, "win"))
    return out


def metadata_facts(res, cfg):
    return dict(template="lasers", n_final=res["nl"], colors=[], t_end=round(res["t_end"], 2),
                winner=res["winner"], peak=res.get("peak", 0), melody=cfg.melody_name)
