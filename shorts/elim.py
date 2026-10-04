"""
"Elimination": 5-6 balls bounce inside a spinning ring with a gap. Any ball that falls out
is ELIMINATED; every elimination starts a faster round. The last ball left inside wins.
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, text, text_fit, note_freq
from . import fx, melodies

SUB = 8
CX, CY, R = 540, 1000, 420
RING_T = 14
BALL_R = 27
G = 1050.0
VMIN, VMAX = 950.0, 1700.0
MAX_T = 34.0
END_HOLD = 2.8
ORD = {1: "1st", 2: "2nd", 3: "3rd"}

HOOKS = [
    ("LAST BALL INSIDE", "WINS"),
    ("PICK A COLOR", "LAST ONE WINS"),
    ("WHO SURVIVES", "TILL THE END?"),
    ("{n} BALLS.", "ONLY 1 SURVIVES."),
]
SUBS = ["Fall out and you're eliminated", "Comment your pick before it ends",
        "Every round gets faster", "Most people pick wrong"]


@dataclass
class Config:
    seed: int
    names: list
    gap0: float
    spin: float
    ring_hue: tuple
    melody_name: str
    melody: list
    hook: tuple
    sub: str
    bg: tuple


def make_config(seed):
    rng = random.Random(seed * 3571 + 29)
    n = rng.choice([5, 6, 6])
    names = rng.sample(list(fx.PALETTE), n)
    mel = rng.choice(list(melodies.MELODIES))
    l1, l2 = rng.choice(HOOKS)
    return Config(seed, names, math.radians(rng.uniform(17, 21)),
                  rng.uniform(0.7, 1.0) * rng.choice([-1, 1]),
                  rng.choice([(0.75, 0.45, 1.0), (0.3, 0.9, 1.0), (1.0, 0.5, 0.75), (1.0, 0.8, 0.35)]),
                  mel, melodies.MELODIES[mel], (l1.format(n=n), l2.format(n=n)),
                  rng.choice(SUBS), rng.choice(fx.BGS))


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    n = len(cfg.names)
    balls = []
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a = rng.uniform(0, 2 * math.pi)
        v = rng.uniform(900, 1200)
        balls.append(dict(x=CX + 150 * math.cos(a0), y=CY + 150 * math.sin(a0),
                          vx=v * math.cos(a), vy=v * math.sin(a), state="in", place=None,
                          pulse=0.0, trail=[], t_out=None, ox=0, oy=0))
    ring, spin, gap = rng.uniform(0, 2 * math.pi), cfg.spin, cfg.gap0
    inner = R - RING_T / 2
    t, t_end = 0.0, None
    events, frames, outs = [], [], []
    rnd = 1

    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            ring = (ring + spin * h) % (2 * math.pi)
            if t_end is None and tt > 24:
                gap = max(gap, cfg.gap0 + math.radians(5) * (tt - 24))
            g_eff = gap * min(1.0, tt / 1.5)        # the exit "opens" during the first 1.5 s
            live = [b for b in balls if b["state"] != "gone"]
            for b in live:
                b["vy"] += G * h
                b["x"] += b["vx"] * h
                b["y"] += b["vy"] * h
                if b["state"] == "out":
                    if b["y"] > 2300:
                        b["state"] = "gone"
                    continue
                dx, dy = b["x"] - CX, b["y"] - CY
                d = math.hypot(dx, dy) or 1e-6
                if b["state"] == "passing":
                    if d - BALL_R > R + RING_T and t_end is None:
                        b["state"] = "out"
                        left = sum(1 for o in balls if o["state"] in ("in", "passing"))
                        b["place"] = left + 1
                        b["t_out"], b["ox"], b["oy"] = tt, b["x"], b["y"]
                        outs.append(tt)
                        events.append((tt, "out", b["place"]))
                        rnd += 1
                        spin *= 1.08
                        gap = max(math.radians(13), gap * 0.95)
                        if left == 1:
                            t_end = tt
                            events.append((tt, "win", None))
                            for o in balls:
                                if o["state"] in ("in", "passing"):
                                    o["place"] = 1
                    elif b["state"] == "passing" and d - BALL_R > R + RING_T:
                        b["state"] = "out"
                    continue
                if d + BALL_R >= inner:
                    th = math.atan2(dy, dx)
                    rel = (th - ring + math.pi) % (2 * math.pi) - math.pi
                    if t_end is None and abs(rel) < g_eff / 2 - math.asin(min(1.0, BALL_R / R)):
                        b["state"] = "passing"
                        continue
                    nx, ny = dx / d, dy / d
                    vn = b["vx"] * nx + b["vy"] * ny
                    if vn > 0:
                        b["vx"] -= 2 * vn * nx
                        b["vy"] -= 2 * vn * ny
                        kick = rng.uniform(-140, 140)
                        b["vx"] += -ny * kick
                        b["vy"] += nx * kick
                        spd = math.hypot(b["vx"], b["vy"])
                        v = min(max(spd, VMIN), VMAX)
                        b["vx"], b["vy"] = b["vx"] / spd * v, b["vy"] / spd * v
                        b["pulse"] = 1.0
                        if t_end is None:
                            events.append((tt, "bounce", None))
                    pen = d + BALL_R - inner
                    b["x"] -= nx * pen
                    b["y"] -= ny * pen
            inside = [b for b in balls if b["state"] == "in"]
            for i in range(len(inside)):
                for j in range(i + 1, len(inside)):
                    a_, c_ = inside[i], inside[j]
                    dx, dy = c_["x"] - a_["x"], c_["y"] - a_["y"]
                    d = math.hypot(dx, dy)
                    if 0 < d < 2 * BALL_R:
                        nx, ny = dx / d, dy / d
                        rv = (c_["vx"] - a_["vx"]) * nx + (c_["vy"] - a_["vy"]) * ny
                        if rv < 0:
                            a_["vx"] += rv * nx; a_["vy"] += rv * ny
                            c_["vx"] -= rv * nx; c_["vy"] -= rv * ny
                            if t_end is None:
                                events.append((tt, "clash", None))
                        ov = (2 * BALL_R - d) / 2
                        a_["x"] -= nx * ov; a_["y"] -= ny * ov
                        c_["x"] += nx * ov; c_["y"] += ny * ov
        t += DT
        for b in balls:
            b["trail"].append((b["x"], b["y"], BALL_R))
            b["trail"] = b["trail"][-12:]
            b["pulse"] = max(0.0, b["pulse"] - DT * 5)
        if record:
            frames.append(dict(t=t, ring=ring, gap=gap * min(1.0, t / 1.5), rnd=rnd, t_end=t_end,
                               balls=[(b["x"], b["y"], b["state"], b["place"], b["pulse"],
                                       list(b["trail"]), b["t_out"], b["ox"], b["oy"]) for b in balls]))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    winner = next((cfg.names[i] for i, b in enumerate(balls) if b["place"] == 1), None)
    return dict(frames=frames, events=events, t_end=t_end, outs=outs, winner=winner,
                places={cfg.names[i]: b["place"] for i, b in enumerate(balls)})


def is_good(res):
    if res["t_end"] is None or not (15 <= res["t_end"] <= 28):
        return False
    o = res["outs"]
    steps = [b - a for a, b in zip([0.0] + o, o)]
    return steps[0] >= 1.5 and min(steps) >= 0.6 and steps[-1] >= 2.5 and max(steps) <= 9


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.background(ctx, cfg.bg, CX, CY)
    fx.hook(ctx, t, *cfg.hook, cfg.sub)
    a0 = fr["ring"] + fr["gap"] / 2
    a1 = fr["ring"] - fr["gap"] / 2 + 2 * math.pi
    fx.glow_arc(ctx, CX, CY, R, a0, a1, cfg.ring_hue, RING_T)
    cols = [fx.PALETTE[n] for n in cfg.names]

    for i, (x, y, st, place, pulse, trail, t_out, ox, oy) in enumerate(fr["balls"]):
        if st == "gone":
            continue
        if st == "out":
            fx.ball(ctx, x, y, BALL_R, tuple(c * 0.55 for c in cols[i]), 0, (), glow=False)
        else:
            fx.ball(ctx, x, y, BALL_R, cols[i], pulse, trail)
    for i, (x, y, st, place, pulse, trail, t_out, ox, oy) in enumerate(fr["balls"]):
        if t_out is not None and 0 <= t - t_out < 1.3:
            k = (t - t_out) / 1.3
            fx.burst(ctx, t, (t_out, ox, oy, cols[i], i * 97 + cfg.seed, 22, 520, 0.9))
            tx = min(860, max(220, ox))
            ty = min(1380, max(620, oy)) - 60 * k
            text_fit(ctx, f"{cfg.names[i]} OUT!", tx, ty, 64, 420, cols[i], 1 - k * k)

    alive = sum(1 for b in fr["balls"] if b[2] in ("in", "passing"))
    if fr["t_end"] is None:
        text(ctx, f"ROUND {fr['rnd']}  ·  {alive} LEFT", 540, 500, 46, (1, 1, 1), 0.85)
    items = []
    for i, b in enumerate(fr["balls"]):
        place = b[3]
        out = b[2] in ("out", "gone")
        label = cfg.names[i] if not out else f"{cfg.names[i]}  {ORD.get(place, f'{place}th')}"
        items.append((label, cols[i], out))
    fx.pills(ctx, items, y0=1490)
    if fr["t_end"] is not None:
        wi = next(i for i, b in enumerate(fr["balls"]) if b[3] == 1)
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"], f"{cfg.names[wi]} SURVIVES!", cols[wi], "Did you pick right?")


def audio_events(res, cfg):
    out, mi = [], 0
    for t, kind, _ in res["events"]:
        if kind == "bounce":
            out.append((t, note_freq(cfg.melody[mi % len(cfg.melody)]), "pluck"))
            mi += 1
        elif kind == "clash":
            out.append((t, 1046.5, "tick"))
        elif kind == "out":
            out.append((t, 440.0, "out"))
        else:
            out.append((t, 523.25, "win"))
    return out


AUDIO_MIN_GAP = 0.05


def metadata_facts(res, cfg):
    return dict(template="elim", winner=res["winner"], colors=cfg.names, n_balls=len(cfg.names),
                t_end=round(res["t_end"], 2), places=res["places"], melody=cfg.melody_name)
