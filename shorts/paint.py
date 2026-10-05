"""
"Color takeover battle": 4 balls bounce inside a circle whose wall is split into segments.
Every wall segment a ball touches turns that ball's color (stealing it from whoever had it).
When the clock hits zero, the color with the most wall wins.
"""
import math, random
from dataclasses import dataclass

from .common import FPS, DT, W, text, text_fit, rounded, note_freq
from . import fx, melodies

SUB = 8
CX, CY, R = 540, 1000, 430
NSEG = 48
WALL_T = 26
BALL_R = 30
SPEED = (1050.0, 1250.0)
END_HOLD = 2.8

HOOKS = [
    ("PICK A COLOR", "BEFORE IT ENDS"),
    ("WHICH COLOR", "TAKES OVER?"),
    ("4 COLORS.", "{d} SECONDS."),
    ("WHO PAINTS", "THE MOST WALL?"),
]
SUBS = ["Comment your color before it ends", "Most wall when time runs out wins",
        "Lock in your pick now", "The lead changes fast"]


# four colors that are easy to tell apart on a phone
COMBOS = [("RED", "BLUE", "GREEN", "YELLOW"), ("RED", "CYAN", "YELLOW", "PURPLE"),
          ("ORANGE", "BLUE", "GREEN", "PINK"), ("PINK", "CYAN", "YELLOW", "GREEN"),
          ("RED", "BLUE", "YELLOW", "GREEN"), ("ORANGE", "PURPLE", "CYAN", "GREEN")]


@dataclass
class Config:
    seed: int
    names: list
    duration: float
    melody_name: str
    melody: list
    hook: tuple
    sub: str
    bg: tuple
    labels: list = None     # optional ball names from the trend scout


def make_config(seed, labels=None):
    rng = random.Random(seed * 5303 + 17)
    names = list(rng.choice(COMBOS))
    rng.shuffle(names)
    d = rng.choice([18, 20, 20, 22])
    mel = rng.choice(list(melodies.MELODIES))
    l1, l2 = rng.choice(HOOKS)
    if labels:
        l1, l2 = rng.choice([("WHICH ONE", "TAKES OVER?"), ("PICK ONE", "BEFORE IT ENDS")])
    return Config(seed, names, float(d), mel, melodies.MELODIES[mel],
                  (l1, l2.format(d=d)), ("Comment your pick before it ends" if labels else rng.choice(SUBS)), rng.choice(fx.BGS),
                  labels[:4] if labels else None)


def seg_of(th):
    return int(((th % (2 * math.pi)) / (2 * math.pi)) * NSEG) % NSEG


def label(cfg, i):
    return cfg.labels[i] if cfg.labels else cfg.names[i]


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed)
    balls = []
    for i in range(4):
        a0 = math.pi / 4 + i * math.pi / 2
        px, py = CX + 140 * math.cos(a0), CY + 140 * math.sin(a0)
        a = rng.uniform(0, 2 * math.pi)
        v = rng.uniform(*SPEED)
        balls.append([px, py, v * math.cos(a), v * math.sin(a), 0.0, []])  # x y vx vy pulse trail
    owner = [-1] * NSEG
    flash = [-9.0] * NSEG
    inner = R - WALL_T / 2
    t, t_end = 0.0, None
    events, frames = [], []
    leader, lead_changes = -1, 0

    for _f in range(int((cfg.duration + END_HOLD) * FPS) + 2):
        if t_end is None:
            for s in range(SUB):
                h = DT / SUB
                tt = t + s * h
                for bi, b in enumerate(balls):
                    b[0] += b[2] * h
                    b[1] += b[3] * h
                    dx, dy = b[0] - CX, b[1] - CY
                    d = math.hypot(dx, dy) or 1e-6
                    if d + BALL_R >= inner:
                        nx, ny = dx / d, dy / d
                        vn = b[2] * nx + b[3] * ny
                        if vn > 0:
                            b[2] -= 2 * vn * nx
                            b[3] -= 2 * vn * ny
                            kick = rng.uniform(-260, 260)
                            b[2] += -ny * kick
                            b[3] += nx * kick
                            spd = math.hypot(b[2], b[3])
                            v = min(max(spd, SPEED[0]), SPEED[1])
                            b[2], b[3] = b[2] / spd * v, b[3] / spd * v
                            b[4] = 1.0
                            sg = seg_of(math.atan2(dy, dx))
                            # the ball is wide: it paints the segment it hits and the neighbours it covers
                            span = max(1, round(BALL_R / (2 * math.pi * R / NSEG)))
                            for o in range(-(span // 2), span // 2 + 1):
                                q = (sg + o) % NSEG
                                prev = owner[q]
                                if prev != bi:
                                    owner[q] = bi
                                    flash[q] = tt
                                    events.append((tt, "steal" if prev >= 0 else "paint", bi))
                        pen = d + BALL_R - inner
                        b[0] -= nx * pen
                        b[1] -= ny * pen
                for i in range(4):
                    for j in range(i + 1, 4):
                        a_, c_ = balls[i], balls[j]
                        dx, dy = c_[0] - a_[0], c_[1] - a_[1]
                        d = math.hypot(dx, dy)
                        if 0 < d < 2 * BALL_R:
                            nx, ny = dx / d, dy / d
                            rv = (c_[2] - a_[2]) * nx + (c_[3] - a_[3]) * ny
                            if rv < 0:
                                a_[2] += rv * nx; a_[3] += rv * ny
                                c_[2] -= rv * nx; c_[3] -= rv * ny
                                events.append((tt, "clash", None))
                            ov = (2 * BALL_R - d) / 2
                            a_[0] -= nx * ov; a_[1] -= ny * ov
                            c_[0] += nx * ov; c_[1] += ny * ov
            t += DT
            if t >= cfg.duration:
                t_end = cfg.duration
                events.append((t_end, "win", None))
        else:
            t += DT
        counts = [owner.count(i) for i in range(4)]
        top = max(counts)
        if counts.count(top) == 1:
            ld = counts.index(top)
            if ld != leader:
                if leader >= 0:
                    lead_changes += 1
                leader = ld
        for b in balls:
            b[5].append((b[0], b[1], BALL_R))
            b[5] = b[5][-12:]
            b[4] = max(0.0, b[4] - DT * 5)
        if record:
            frames.append(dict(t=t, balls=[(b[0], b[1], b[4], list(b[5])) for b in balls],
                               owner=list(owner), flash=list(flash), counts=counts,
                               leader=leader, t_end=t_end))
        if t_end is not None and t - t_end > END_HOLD:
            break
    counts = [owner.count(i) for i in range(4)]
    order = sorted(range(4), key=lambda i: -counts[i])
    return dict(frames=frames, events=events, t_end=t_end, counts=counts,
                winner=cfg.names[order[0]], lead_changes=lead_changes,
                margin=counts[order[0]] - counts[order[1]])


def is_good(res):
    return 1 <= res["margin"] <= 3 and res["lead_changes"] >= 4 and sum(res["counts"]) >= NSEG - 4


def draw(ctx, fr, cfg):
    t = fr["t"]
    fx.background(ctx, cfg.bg, CX, CY)
    fx.hook(ctx, t, *cfg.hook, cfg.sub)
    cols = [fx.PALETTE[n] for n in cfg.names]
    left = max(0.0, cfg.duration - t)

    # big countdown behind the balls for the last 5 seconds
    if fr["t_end"] is None and left <= 5:
        k = left - math.floor(left)
        text(ctx, str(math.ceil(left)), CX, CY + 110, 330 + 60 * k, (1, 1, 1), 0.12 + 0.1 * k)

    seg = 2 * math.pi / NSEG
    ctx.set_line_cap(0)
    for q in range(NSEG):
        a0, a1 = q * seg + 0.012, (q + 1) * seg - 0.012
        o = fr["owner"][q]
        f = max(0.0, 1 - (t - fr["flash"][q]) / 0.3)
        if o < 0:
            ctx.set_source_rgba(1, 1, 1, 0.14)
            ctx.set_line_width(WALL_T)
        else:
            c = cols[o]
            ctx.set_source_rgba(*c, 0.25)
            ctx.set_line_width(WALL_T * 2.4 + 18 * f)
            ctx.new_path()
            ctx.arc(CX, CY, R, a0, a1)
            ctx.stroke()
            ctx.set_source_rgb(*(min(1, x + 0.35 * f) for x in c))
            ctx.set_line_width(WALL_T + 8 * f)
        ctx.new_path()
        ctx.arc(CX, CY, R, a0, a1)
        ctx.stroke()

    for i, (x, y, pulse, trail) in enumerate(fr["balls"]):
        fx.ball(ctx, x, y, BALL_R, cols[i], pulse, trail)

    text(ctx, f"{left:04.1f}s", 540, 500, 48, (1, 1, 1), 0.85)

    # share bar + one row of 4 score pills
    total = NSEG
    x0, bw, by = 90, 900, 1480
    rounded(ctx, x0, by, bw, 26, 13)
    ctx.set_source_rgba(1, 1, 1, 0.12)
    ctx.fill()
    xs = x0
    ctx.save()
    rounded(ctx, x0, by, bw, 26, 13)
    ctx.clip()
    for i in sorted(range(4), key=lambda i: -fr["counts"][i]):
        wv = bw * fr["counts"][i] / total
        ctx.rectangle(xs, by, wv, 26)
        ctx.set_source_rgb(*cols[i])
        ctx.fill()
        xs += wv
    ctx.restore()
    pw, ph, gx = 205, 84, 20
    px0 = 540 - (4 * pw + 3 * gx) / 2
    for i in range(4):
        bx, byy = px0 + i * (pw + gx), 1530
        lead = fr["leader"] == i
        rounded(ctx, bx, byy, pw, ph, ph / 2)
        ctx.set_source_rgba(*cols[i], 0.35 if lead else 0.15)
        ctx.fill_preserve()
        ctx.set_source_rgba(*(fx.GOLD if lead else cols[i]), 1.0 if lead else 0.8)
        ctx.set_line_width(6 if lead else 4)
        ctx.stroke()
        text_fit(ctx, f"{label(cfg, i)} {fr['counts'][i]}", bx + pw / 2, byy + ph / 2 + 15, 40,
                 pw - 30)

    if fr["t_end"] is not None:
        win = max(range(4), key=lambda i: fr["counts"][i])
        fx.confetti(ctx, t, fr["t_end"], cfg.seed)
        fx.banner(ctx, t, fr["t_end"], f"{label(cfg, win)} WINS!", cols[win], "Did you pick right?")


def audio_events(res, cfg):
    out, mi = [], 0
    for t, kind, bi in res["events"]:
        if kind == "paint":
            out.append((t, note_freq(cfg.melody[mi % len(cfg.melody)]), "pluck"))
            mi += 1
        elif kind == "steal":
            out.append((t, note_freq(cfg.melody[mi % len(cfg.melody)]) * 2, "steal"))
            mi += 1
        elif kind == "clash":
            out.append((t, 1046.5, "tick"))
        else:
            out.append((t, 523.25, "win"))
    return out


AUDIO_MIN_GAP = 0.06


def metadata_facts(res, cfg):
    return dict(template="paint", winner=res["winner"], colors=cfg.names, n_balls=4,
                labels=cfg.labels or [],
                counts=dict(zip(cfg.names, res["counts"])), duration=cfg.duration,
                melody=cfg.melody_name)
