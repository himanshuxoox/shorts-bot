"""
"Ball Escape Race": four balls (red, blue, green, yellow) bounce through a level towards the
exit flag while a hazard closes in behind them. First ball out wins; a ball the hazard
touches is OUT. Every seed generates a new level. Four level types (one format each):

  race_lava    maze + lava creeping through the corridors
  race_flood   rooms with doorways, flooding room by room
  race_crush   a tall hall with a crusher block going up and down (hide in the side alcoves!)
               while lava rises from the bottom
  race_shrink  the balls start too BIG for the exit gap; shrink pads make them small enough

The hazard spreads along a distance field from the exit (farthest tiles first), so it always
chases the balls towards the exit. Bounces play a famous public-domain tune.
"""
import math, random
from collections import deque
from dataclasses import dataclass, field

import cairo
import numpy as np

from .common import FPS, DT, text, note_freq, rounded
from . import fx, melodies

SUB = 4
T = 40                                    # tile size (px)
NX, NY = 25, 28
X0, Y0 = 40, 440
SPEED = 340.0
MAX_T = 70.0
HAZ_DELAY = 4.0                           # seconds before the hazard starts moving
END_HOLD = 3.2
NAMES = ["RED", "BLUE", "GREEN", "YELLOW"]
COLS = [(1.0, 0.22, 0.25), (0.2, 0.45, 1.0), (0.15, 0.75, 0.3), (1.0, 0.85, 0.1)]

STYLE = {
    "lava":   dict(floor=(0.95, 0.95, 0.96), wall=(0.12, 0.45, 0.9), haz=((1.0, 0.55, 0.05), (1.0, 0.8, 0.25)),
                   bg=((0.05, 0.25, 0.08), (0.02, 0.12, 0.04)), hazname="LAVA"),
    "flood":  dict(floor=(0.86, 0.86, 0.88), wall=(0.86, 0.6, 0.43), haz=((0.05, 0.35, 0.95), (0.4, 0.8, 1.0)),
                   bg=((0.55, 0.55, 0.55), (0.45, 0.45, 0.45)), hazname="WATER"),
    "crush":  dict(floor=(0.88, 0.82, 0.6), wall=(0.0, 0.55, 0.75), haz=((0.9, 0.2, 0.05), (1.0, 0.55, 0.1)),
                   bg=((0.25, 0.1, 0.03), (0.18, 0.07, 0.02)), hazname="LAVA"),
    "shrink": dict(floor=(0.22, 0.06, 0.3), wall=(0.05, 0.55, 0.1), haz=((1.0, 0.55, 0.25), (1.0, 0.7, 0.4)),
                   bg=((0.0, 0.35, 0.4), (0.05, 0.05, 0.05)), hazname="FIRE"),
}
TITLES = {
    "lava": [[("Escape the ", fx.WHITE), ("LAVA", (1.0, 0.55, 0.1)), ("!", fx.WHITE)],
             [("First ball to the ", fx.WHITE), ("FLAG", (0.4, 1.0, 0.5)), (" wins", fx.WHITE)]],
    "flood": [[("The rooms are ", fx.WHITE), ("FLOODING", (0.35, 0.75, 1.0)), ("!", fx.WHITE)],
              [("Which ball ", fx.WHITE), ("ESCAPES", (0.4, 1.0, 0.5)), (" first?", fx.WHITE)]],
    "crush": [[("Dodge the ", fx.WHITE), ("CRUSHER", (1.0, 0.55, 0.1)), (", outrun the lava", fx.WHITE)],
              [("First ball to the ", fx.WHITE), ("TOP", (0.4, 1.0, 0.5)), (" wins", fx.WHITE)]],
    "shrink": [[("Too ", fx.WHITE), ("BIG", fx.RED), (" for the exit!", fx.WHITE)],
               [("Touch a pad to ", fx.WHITE), ("SHRINK", (0.4, 1.0, 0.5)), (" — race to escape", fx.WHITE)]],
}


# ===================================================================== level generators
def _blank():
    g = np.ones((NY, NX), np.int8)
    return g


def gen_lava(rng):
    g = _blank()
    ci, cj = 8, 9                                   # maze cells (2-tile corridors, 1-tile walls)

    def cell(i, j):
        return 1 + 3 * i, 1 + 3 * j

    for i in range(ci):
        for j in range(cj):
            x, y = cell(i, j)
            g[y:y + 2, x:x + 2] = 0
    seen = {(0, 0)}
    stack = [(0, 0)]
    while stack:
        i, j = stack[-1]
        nb = [(i + di, j + dj) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))
              if 0 <= i + di < ci and 0 <= j + dj < cj and (i + di, j + dj) not in seen]
        if not nb:
            stack.pop(); continue
        a, b = rng.choice(nb)
        x, y = cell(i, j)
        if a != i:
            g[y:y + 2, x + (2 if a > i else -1)] = 0
        else:
            g[y + (2 if b > j else -1), x:x + 2] = 0
        seen.add((a, b)); stack.append((a, b))
    # braid: knock out extra walls so there are loops (fewer dead ends)
    for _ in range(26):
        i, j = rng.randrange(ci), rng.randrange(cj)
        x, y = cell(i, j)
        if rng.random() < 0.5 and i < ci - 1:
            g[y:y + 2, x + 2] = 0
        elif j < cj - 1:
            g[y + 2, x:x + 2] = 0
    goal = (1, 1, 2, 2)                             # tile rect x, y, w, h
    return g, goal, []


def gen_flood(rng):
    g = _blank()
    xs = [(1, 7), (9, 15), (17, 23)]
    ys = [(1, 5), (7, 12), (14, 19), (21, 26)]
    for x0, x1 in xs:
        for y0, y1 in ys:
            g[y0:y1 + 1, x0:x1 + 1] = 0
    rooms = [(a, b) for a in range(3) for b in range(4)]
    edges = []
    for a, b in rooms:
        if a < 2: edges.append(((a, b), (a + 1, b)))
        if b < 3: edges.append(((a, b), (a, b + 1)))
    rng.shuffle(edges)
    parent = {r: r for r in rooms}

    def find(r):
        while parent[r] != r:
            r = parent[r]
        return r
    chosen = []
    for e in edges:
        ra, rb = find(e[0]), find(e[1])
        if ra != rb:
            parent[ra] = rb; chosen.append(e)
        elif rng.random() < 0.3:
            chosen.append(e)
    for (a, b), (c, d) in chosen:
        if a != c:                                   # vertical wall between columns
            wx = xs[a][1] + 1
            y0, y1 = ys[b]
            y = rng.randint(y0, y1 - 1)
            g[y:y + 2, wx] = 0
        else:
            wy = ys[b][1] + 1
            x0, x1 = xs[a]
            x = rng.randint(x0, x1 - 1)
            g[wy, x:x + 2] = 0
    # pillars
    for _ in range(7):
        a, b = rng.randrange(3), rng.randrange(4)
        x0, x1 = xs[a]; y0, y1 = ys[b]
        x, y = rng.randint(x0 + 2, x1 - 2), rng.randint(y0 + 1, y1 - 2)
        if (a, b) != (0, 0):
            g[y, x] = 1
    return g, (1, 1, 2, 2), []


def gen_crush(rng):
    g = _blank()
    c0, c1 = 9, 15                                   # corridor columns (7 wide)
    g[1:NY - 1, c0:c1 + 1] = 0
    g[NY - 5:NY - 1, 3:NX - 3] = 0                   # start hall at the bottom
    y = 4
    side = rng.choice([-1, 1])
    while y < NY - 7:
        if rng.random() < 0.85:
            h = 3
            if side < 0:
                g[y:y + h, c0 - 3:c0] = 0
            else:
                g[y:y + h, c1 + 1:c1 + 4] = 0
            if rng.random() < 0.35:                  # both sides sometimes
                if side < 0:
                    g[y:y + h, c1 + 1:c1 + 4] = 0
                else:
                    g[y:y + h, c0 - 3:c0] = 0
        side = -side
        y += 4
    g[1:3, 3:c0] = 0                                 # side passage at the very top to the goal
    goal = (1, 1, 2, 2)
    g[1:3, 1:3] = 0
    return g, goal, []


def gen_shrink(rng):
    g = _blank()
    g[1:NY - 1, 1:NX - 1] = 0
    # goal room top-left with a 1-tile door
    g[1:7, 6:8] = 1
    g[6:8, 1:8] = 1
    door = rng.choice([("v", rng.randint(2, 4)), ("h", rng.randint(2, 4))])
    if door[0] == "v":
        g[door[1], 6:8] = 0
    else:
        g[6:8, door[1]] = 0
    # obstacles
    for _ in range(rng.randint(4, 6)):
        w, h = rng.randint(2, 5), rng.randint(2, 4)
        x, y = rng.randint(2, NX - 2 - w), rng.randint(9, NY - 3 - h)
        g[y:y + h, x:x + w] = 1
    return g, (1, 1, 2, 2), []


GEN = dict(lava=gen_lava, flood=gen_flood, crush=gen_crush, shrink=gen_shrink)


def distance_field(g, goal):
    gx, gy, gw, gh = goal
    dist = np.full(g.shape, -1, np.int32)
    q = deque()
    for y in range(gy, gy + gh):
        for x in range(gx, gx + gw):
            dist[y, x] = 0; q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = x + dx, y + dy
            if 0 <= a < NX and 0 <= b < NY and g[b, a] == 0 and dist[b, a] < 0:
                dist[b, a] = dist[y, x] + 1; q.append((a, b))
    return dist


# ===================================================================== simulation
@dataclass
class Config:
    seed: int
    kind: str
    grid: np.ndarray
    goal: tuple
    pads: list
    dist: np.ndarray
    rate: float              # hazard speed (tiles / s)
    steer: list
    melody_name: str
    melody: list
    block_period: float = 5.0
    reflex: list = field(default_factory=lambda: [2.0] * 4)


def make_config(seed, kind):
    rng = random.Random(seed * 6151 + sum(map(ord, kind)))
    g, goal, pads = GEN[kind](rng)
    dist = distance_field(g, goal)
    g[(dist < 0) & (g == 0)] = 1                      # seal unreachable pockets
    maxd = int(dist.max())
    if kind == "shrink":                              # only 2 shrink pads, halfway along the route
        cand = [(x, y) for y in range(NY) for x in range(NX) if g[y, x] == 0 and 0.3 * maxd <= dist[y, x] <= 0.6 * maxd]
        rng.shuffle(cand)
        for x, y in cand:
            if len(pads) == 2:
                break
            if all(abs(x - a) + abs(y - b) > 8 for a, b in pads):
                pads.append((x, y))
    mel = rng.choice(melodies.FAMOUS)
    slow = {"crush": 1.6, "shrink": 1.3}.get(kind, 1.0)
    return Config(seed, kind, g, goal, pads, dist, maxd / rng.uniform(56, 70) / slow,
                  [rng.uniform(0.8, 2.2) * {"crush": 0.55, "shrink": 2.0}.get(kind, 1.0) for _ in range(4)],
                  mel, melodies.MELODIES[mel], rng.uniform(5.0, 6.5), [rng.uniform(0.6, 3.0) for _ in range(4)])


def tile_rect(x, y):
    return X0 + x * T, Y0 + y * T


def _haz_D(cfg, t):
    """Tiles with dist > D are covered by the hazard (fractional part = front tile progress)."""
    maxd = int(cfg.dist.max())
    return maxd + 1.5 - cfg.rate * max(0.0, t - HAZ_DELAY)


def _block(cfg, t):
    """Crusher block (crush levels): returns rect x0, y0, x1, y1 and vertical velocity."""
    if cfg.kind != "crush":
        return None
    top, bot = Y0 + 4 * T, Y0 + (NY - 4) * T       # slams onto the start-hall floor
    hgt = 3 * T
    p = cfg.block_period
    t = max(0.0, t - 3.0)                              # waits at the top for the first 3 s
    u = (t % p) / p
    k = 0.5 - 0.5 * math.cos(2 * math.pi * u)        # smooth ping-pong
    y0 = top + (bot - top) * k
    vy = (bot - top) * math.pi / p * math.sin(2 * math.pi * u)
    return (X0 + 9 * T, y0, X0 + 16 * T, y0 + hgt), vy


def simulate(cfg, record=False):
    rng = random.Random(cfg.seed * 31 + 5)
    g, dist = cfg.grid, cfg.dist
    maxd = int(dist.max())
    # start: 2x2 cluster on far tiles, just ahead of the hazard
    cand = [(x, y) for y in range(NY) for x in range(NX) if g[y, x] == 0 and maxd - 4 <= dist[y, x] <= maxd - 1]
    if cfg.kind == "crush":
        cand = [(x, y) for y in range(NY - 3, NY - 1) for x in list(range(4, 8)) + list(range(17, 21)) if g[y, x] == 0]
    sx, sy = rng.choice(cand)
    r0 = 29.0 if cfg.kind == "shrink" else 17.0
    balls = []
    for k in range(4):
        a = rng.uniform(0, 2 * math.pi)
        px, py = tile_rect(sx, sy)
        balls.append(dict(x=px + T / 2 + (k % 2 - 0.5) * 2.2 * r0, y=py + T / 2 + (k // 2 - 0.5) * 2.2 * r0,
                          vx=SPEED * math.cos(a), vy=SPEED * math.sin(a), r=r0, alive=True, done=False,
                          trail=[]))
    events, bounces, frames = [], [], []
    t, t_end, winner = 0.0, None, None
    used_pads = set()
    finish = []
    for _f in range(int((MAX_T + END_HOLD) * FPS)):
        for s in range(SUB):
            h = DT / SUB
            tt = t + s * h
            if t_end is not None:
                break
            D = _haz_D(cfg, tt)
            blk = _block(cfg, tt)
            for i, b in enumerate(balls):
                if not b["alive"]:
                    continue
                # steer gently towards the exit (each ball has its own "skill")
                tx, ty = int((b["x"] - X0) // T), int((b["y"] - Y0) // T)
                best = None
                if 0 <= tx < NX and 0 <= ty < NY and dist[ty, tx] >= 0:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        a_, b_ = tx + dx, ty + dy
                        if 0 <= a_ < NX and 0 <= b_ < NY and 0 <= dist[b_, a_] < dist[ty, tx]:
                            best = (dx, dy)
                gain = 1.0
                free = [p for k, p in enumerate(cfg.pads) if k not in used_pads]
                if free and b["r"] > 20:                    # too big: head for the nearest shrink pad first
                    px_, py_ = min(free, key=lambda p: (tile_rect(*p)[0] - b["x"]) ** 2 + (tile_rect(*p)[1] - b["y"]) ** 2)
                    rx, ry = tile_rect(px_, py_)
                    dx, dy = rx + T / 2 - b["x"], ry + T / 2 - b["y"]
                    L = math.hypot(dx, dy) or 1
                    best = (dx / L, dy / L)
                    gain = 0.7
                if blk:                                     # crusher coming: dodge sideways
                    (bx0, by0, bx1, by1), bvy = blk
                    if bx0 - 10 < b["x"] < bx1 + 10:
                        gap = (b["y"] - by1) if b["y"] > by1 else (by0 - b["y"])
                        toward = (b["y"] > by1 and bvy > 0) or (b["y"] < by0 and bvy < 0)
                        if toward and gap < 260:
                            best = (-1 if b["x"] < (bx0 + bx1) / 2 else 1, 0)
                            gain = cfg.reflex[i]
                if best:
                    ang = math.atan2(b["vy"], b["vx"])
                    want = math.atan2(best[1], best[0])
                    d = (want - ang + math.pi) % (2 * math.pi) - math.pi
                    ang += max(-1, min(1, d)) * cfg.steer[i] * gain * h
                    b["vx"], b["vy"] = SPEED * math.cos(ang), SPEED * math.sin(ang)
                b["x"] += b["vx"] * h; b["y"] += b["vy"] * h
                r = b["r"]
                # walls
                hit = False
                for yy in range(int((b["y"] - r - Y0) // T), int((b["y"] + r - Y0) // T) + 1):
                    for xx in range(int((b["x"] - r - X0) // T), int((b["x"] + r - X0) // T) + 1):
                        if not (0 <= xx < NX and 0 <= yy < NY) or g[yy, xx] == 1:
                            rx, ry = tile_rect(xx, yy)
                            cx = min(max(b["x"], rx), rx + T); cy = min(max(b["y"], ry), ry + T)
                            dx, dy = b["x"] - cx, b["y"] - cy
                            dd = math.hypot(dx, dy)
                            if dd < r:
                                if dd < 1e-6:
                                    dx, dy, dd = -b["vx"], -b["vy"], SPEED
                                nx, ny = dx / dd, dy / dd
                                b["x"] += nx * (r - dd); b["y"] += ny * (r - dd)
                                vn = b["vx"] * nx + b["vy"] * ny
                                if vn < 0:
                                    b["vx"] -= 2 * vn * nx; b["vy"] -= 2 * vn * ny
                                    hit = True
                lo_x, hi_x = X0 + T + r, X0 + (NX - 1) * T - r       # never leave the arena
                lo_y, hi_y = Y0 + T + r, Y0 + (NY - 1) * T - r
                if not (lo_x <= b["x"] <= hi_x):
                    b["x"] = min(max(b["x"], lo_x), hi_x); b["vx"] = -b["vx"]; hit = True
                if not (lo_y <= b["y"] <= hi_y):
                    b["y"] = min(max(b["y"], lo_y), hi_y); b["vy"] = -b["vy"]; hit = True
                if hit:
                    ang = math.atan2(b["vy"], b["vx"]) + rng.uniform(-0.12, 0.12)
                    b["vx"], b["vy"] = SPEED * math.cos(ang), SPEED * math.sin(ang)
                    bounces.append((tt, i))
                # crusher block
                if blk:
                    (bx0, by0, bx1, by1), bvy = blk
                    cx = min(max(b["x"], bx0), bx1); cy = min(max(b["y"], by0), by1)
                    dx, dy = b["x"] - cx, b["y"] - cy
                    dd = math.hypot(dx, dy)
                    if dd < r:
                        in_hall = bx0 + r * 0.5 < b["x"] < bx1 - r * 0.5
                        face = abs(dy) >= abs(dx)
                        moving_in = (dy > 0 and bvy > 30) or (dy < 0 and bvy < -30)
                        if in_hall and face and moving_in:
                            # pinned between the block and a wall -> crushed, otherwise shoved along
                            sgn = 1 if dy > 0 else -1
                            ty_ = int((b["y"] + sgn * (r + 6) - Y0) // T)
                            tx_ = int((b["x"] - X0) // T)
                            if not (0 <= ty_ < NY) or g[ty_, tx_] == 1:
                                b["alive"] = False
                                events.append((tt, "crush", i, b["x"], b["y"]))
                                continue
                            b["y"] = (by1 + r) if sgn > 0 else (by0 - r)
                            b["vy"] = sgn * abs(b["vy"]) + bvy
                            sp = math.hypot(b["vx"], b["vy"])
                            b["vx"] *= SPEED / sp; b["vy"] *= SPEED / sp
                            continue
                        if dd < 1e-6:
                            dx, dy, dd = 0.0, (1.0 if bvy > 0 else -1.0), 1.0
                        nx, ny = dx / dd, dy / dd
                        b["x"] += nx * (r - dd); b["y"] += ny * (r - dd)
                        rel = (b["vx"] * nx + (b["vy"] - bvy) * ny)
                        if rel < 0:
                            b["vx"] -= 2 * rel * nx; b["vy"] -= 2 * rel * ny
                            sp = math.hypot(b["vx"], b["vy"])
                            b["vx"] *= SPEED / sp; b["vy"] *= SPEED / sp
                # shrink pads
                if cfg.pads and b["r"] > 20:
                    for pi, (px_, py_) in enumerate(cfg.pads):
                        if pi in used_pads:
                            continue
                        rx, ry = tile_rect(px_, py_)
                        if abs(b["x"] - rx - T / 2) < T / 2 + r * 0.6 and abs(b["y"] - ry - T / 2) < T / 2 + r * 0.6:
                            b["r"] = 15.0
                            used_pads.add(pi)                    # every pad works only once
                            events.append((tt, "shrink", i, b["x"], b["y"], pi))
                            break
                # hazard
                tx, ty = int((b["x"] - X0) // T), int((b["y"] - Y0) // T)
                dead = False
                for yy in range(int((b["y"] - r * 0.7 - Y0) // T), int((b["y"] + r * 0.7 - Y0) // T) + 1):
                    for xx in range(int((b["x"] - r * 0.7 - X0) // T), int((b["x"] + r * 0.7 - X0) // T) + 1):
                        if 0 <= xx < NX and 0 <= yy < NY and dist[yy, xx] >= 0 and dist[yy, xx] > D + 0.5:
                            dead = True
                if dead:
                    b["alive"] = False
                    events.append((tt, "out", i, b["x"], b["y"]))
                    continue
                # goal
                gx, gy, gw, gh = cfg.goal
                rx, ry = tile_rect(gx, gy)
                if rx < b["x"] < rx + gw * T and ry < b["y"] < ry + gh * T:
                    b["done"], b["alive"] = True, False     # escaped! (the race goes on for the others)
                    finish.append(i)
                    if winner is None:
                        winner = i
                    events.append((tt, "win", i, b["x"], b["y"], len(finish)))
                    continue
            # ball-ball
            al = [b for b in balls if b["alive"]]
            for a in range(len(al)):
                for c in range(a + 1, len(al)):
                    p, q = al[a], al[c]
                    dx, dy = q["x"] - p["x"], q["y"] - p["y"]
                    dd = math.hypot(dx, dy)
                    if 1e-6 < dd < p["r"] + q["r"]:
                        nx, ny = dx / dd, dy / dd
                        ov = (p["r"] + q["r"] - dd) / 2
                        p["x"] -= nx * ov; p["y"] -= ny * ov; q["x"] += nx * ov; q["y"] += ny * ov
                        rv = (p["vx"] - q["vx"]) * nx + (p["vy"] - q["vy"]) * ny
                        if rv > 0:
                            p["vx"] -= rv * nx; p["vy"] -= rv * ny; q["vx"] += rv * nx; q["vy"] += rv * ny
            if not any(b["alive"] for b in balls) and t_end is None:
                t_end = tt
        t += DT
        for b in balls:
            if b["alive"]:
                b["trail"] = (b["trail"] + [(b["x"], b["y"])])[-8:]
        if record:
            frames.append(dict(t=t, balls=[(b["x"], b["y"], b["r"], b["alive"], tuple(b["trail"])) for b in balls],
                               t_end=t_end, winner=winner, finish=list(finish)))
        if t_end is not None and t - t_end > END_HOLD:
            break
        if t_end is None and t >= MAX_T:
            break
    outs = [e for e in events if e[1] in ("out", "crush")]
    return dict(frames=frames, events=events, bounces=bounces, t_end=t_end, winner=winner, outs=len(outs), kind=cfg.kind,
                finish=[NAMES[i] for i in finish],
                out_order=[NAMES[e[2]] for e in outs])


def is_good(res):
    if res["winner"] is None or res["t_end"] is None:
        return False
    lo = 15 if res.get("kind") == "crush" else 18
    return lo <= res["t_end"] <= 55 and 1 <= res["outs"] <= 3


# ===================================================================== drawing
_CACHE = {}


def _level_surface(cfg):
    key = (cfg.kind, cfg.seed)
    if key in _CACHE:
        return _CACHE[key]
    st = STYLE[cfg.kind]
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1080, 1920)
    c = cairo.Context(surf)
    # checker background
    c.set_source_rgb(*st["bg"][1]); c.paint()
    c.set_source_rgb(*st["bg"][0])
    for y in range(0, 1920, 30):
        for x in range(0, 1080, 30):
            if (x // 30 + y // 30) % 2 == 0:
                c.rectangle(x, y, 30, 30)
    c.fill()
    c.set_source_rgb(0, 0, 0)
    c.rectangle(X0 - 6, Y0 - 6, NX * T + 12, NY * T + 12); c.fill()
    c.set_source_rgb(*st["floor"])
    c.rectangle(X0, Y0, NX * T, NY * T); c.fill()
    if cfg.kind == "shrink":                       # star field floor
        rng = random.Random(cfg.seed)
        c.set_source_rgba(1, 1, 1, 0.8)
        for _ in range(500):
            c.rectangle(X0 + rng.uniform(0, NX * T), Y0 + rng.uniform(0, NY * T), 2, 2)
        c.fill()
    c.set_source_rgb(*st["wall"])
    g = cfg.grid
    for y in range(NY):
        for x in range(NX):
            if g[y, x]:
                rx, ry = tile_rect(x, y)
                c.rectangle(rx - 0.5, ry - 0.5, T + 1, T + 1)
    c.fill()
    # goal: green square with a chequered flag strip
    gx, gy, gw, gh = cfg.goal
    rx, ry = tile_rect(gx, gy)
    gr = cairo.RadialGradient(rx + gw * T / 2, ry + gh * T / 2, 5, rx + gw * T / 2, ry + gh * T / 2, gw * T)
    gr.add_color_stop_rgb(0, 0.6, 1.0, 0.6); gr.add_color_stop_rgb(1, 0.15, 0.75, 0.25)
    c.set_source(gr); c.rectangle(rx, ry, gw * T, gh * T); c.fill()
    for k in range(int(gh * T / 10)):
        for j in range(2):
            c.set_source_rgb(*((1, 1, 1) if (k + j) % 2 else (0, 0, 0)))
            c.rectangle(rx + gw * T + j * 8, ry + k * 10, 8, 10); c.fill()
    _CACHE[key] = surf
    return surf


def _hazard(ctx, cfg, t):
    st = STYLE[cfg.kind]
    D = _haz_D(cfg, t)
    dist = cfg.dist
    full = np.argwhere(dist > D + 1)
    front = np.argwhere((dist > D) & (dist <= D + 1))
    g = cairo.LinearGradient(0, Y0, 0, Y0 + NY * T)
    g.add_color_stop_rgb(0, *st["haz"][1]); g.add_color_stop_rgb(1, *st["haz"][0])
    ctx.set_source(g)
    for y, x in full:
        rx, ry = tile_rect(x, y)
        ctx.rectangle(rx - 0.5, ry - 0.5, T + 1, T + 1)
    ctx.fill()
    # front tiles grow in from the side of their filled neighbour
    ctx.set_source(g)
    for y, x in front:
        k = min(1.0, max(0.0, dist[y, x] - D))
        rx, ry = tile_rect(x, y)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = x + dx, y + dy
            if 0 <= a < NX and 0 <= b < NY and dist[b, a] > dist[y, x]:
                if dx == 1: ctx.rectangle(rx + T * (1 - k), ry, T * k, T)
                elif dx == -1: ctx.rectangle(rx, ry, T * k, T)
                elif dy == 1: ctx.rectangle(rx, ry + T * (1 - k), T, T * k)
                else: ctx.rectangle(rx, ry, T, T * k)
                break
    ctx.fill()


def _ball(ctx, x, y, r, col, trail, alpha=1.0):
    if len(trail) > 1:
        for j in range(1, len(trail)):
            k = j / len(trail)
            ctx.set_source_rgba(*col, 0.35 * k * alpha)
            ctx.set_line_width(r * 1.6 * k)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.move_to(*trail[j - 1]); ctx.line_to(*trail[j]); ctx.stroke()
    ctx.set_source_rgba(0, 0, 0, alpha)
    ctx.arc(x, y, r + 2.5, 0, 2 * math.pi); ctx.fill()
    gr = cairo.RadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r)
    gr.add_color_stop_rgba(0, *[min(1, v + 0.45) for v in col], alpha)
    gr.add_color_stop_rgba(1, *col, alpha)
    ctx.set_source(gr); ctx.arc(x, y, r, 0, 2 * math.pi); ctx.fill()


def draw(ctx, fr, cfg):
    t = fr["t"]
    ctx.set_source_surface(_level_surface(cfg), 0, 0)
    ctx.paint()
    ctx.set_source_rgba(0, 0, 0, 0.55)
    rounded(ctx, 20, 200, 1040, 200, 22); ctx.fill()
    fx.rich_title(ctx, TITLES[cfg.kind], y=300, size=54)
    # shrink pads
    gone = {ev[5]: ev[0] for ev in fr["res"]["events"] if ev[1] == "shrink"}
    for pi, (px_, py_) in enumerate(cfg.pads):
        if pi in gone and t > gone[pi]:
            continue
        rx, ry = tile_rect(px_, py_)
        ctx.set_source_rgb(0.55, 0.55, 0.58); ctx.rectangle(rx + 3, ry + 3, T - 6, T - 6); ctx.fill()
        ctx.set_source_rgb(0.3, 0.3, 0.33); ctx.set_line_width(2.5)
        ctx.rectangle(rx + 9, ry + 9, T - 18, T - 18); ctx.stroke()
        p = 0.5 + 0.5 * math.sin(t * 5)
        ctx.set_source_rgba(1, 1, 1, 0.5 * p); ctx.arc(rx + T / 2, ry + T / 2, 4, 0, 2 * math.pi); ctx.fill()
    _hazard(ctx, cfg, t)
    blk = _block(cfg, t)
    if blk:
        (bx0, by0, bx1, by1), _ = blk
        ctx.set_source_rgb(0, 0, 0); ctx.rectangle(bx0 - 3, by0 - 3, bx1 - bx0 + 6, by1 - by0 + 6); ctx.fill()
        ctx.set_source_rgb(0.95, 0.5, 0.1); ctx.rectangle(bx0, by0, bx1 - bx0, by1 - by0); ctx.fill()
        ctx.set_source_rgba(0, 0, 0, 0.35); ctx.set_line_width(4)
        for k in range(8):
            xx = bx0 + 20 + k * 36
            ctx.move_to(xx, by0 + 8); ctx.line_to(xx - 20, by1 - 8)
        ctx.stroke()
    # balls
    for i, (x, y, r, alive, trail) in enumerate(fr["balls"]):
        if alive:
            _ball(ctx, x, y, r, COLS[i], trail)
    res = fr["res"]
    for ev in res["events"]:
        te, kind, i, x, y = ev[:5]
        dt = t - te
        if kind in ("out", "crush") and 0 <= dt < 1.0:
            rng = random.Random(int(te * 1000))
            for _ in range(14):
                a = rng.uniform(0, 2 * math.pi); v = rng.uniform(120, 420)
                ctx.set_source_rgba(*COLS[i], 1 - dt)
                ctx.arc(x + math.cos(a) * v * dt, y + math.sin(a) * v * dt + 300 * dt * dt, 6 * (1 - dt), 0, 2 * math.pi)
                ctx.fill()
            text(ctx, "CRUSHED!" if kind == "crush" else "OUT!", x, y - 30 - 40 * dt, 44, COLS[i], 1 - dt)
        elif kind == "win" and 0 <= dt < 1.4:
            place = ev[5]
            text(ctx, f"{NAMES[i]} ESCAPED!" if place == 1 else f"{NAMES[i]} #{place}", 540, 1000, 80 if place == 1 else 60,
                 COLS[i], min(1.0, (1.4 - dt) / 0.3))
        elif kind == "shrink" and 0 <= dt < 0.6:
            ctx.set_source_rgba(1, 1, 1, 1 - dt / 0.6); ctx.set_line_width(4)
            ctx.arc(x, y, 14 + 60 * dt, 0, 2 * math.pi); ctx.stroke()
    # status row
    ys = 1640
    for i, nm in enumerate(NAMES):
        cx = 160 + i * 255
        alive = fr["balls"][i][3]
        fin = fr["finish"]
        ok = alive or i in fin
        _ball(ctx, cx - 92, ys - 13, 17, COLS[i], (), 1.0 if ok else 0.35)
        lab = ["1st!", "2nd", "3rd", "4th"][fin.index(i)] if i in fin else ("OUT" if not alive else nm)
        text(ctx, lab, cx + 12, ys, 34, COLS[i] if ok else (0.6, 0.6, 0.6))
    text(ctx, "Pick a color before they start!", 540, 1730, 42, (1, 1, 1), 0.9)
    if fr["t_end"] is not None and t > fr["t_end"]:
        w = fr["winner"]
        if w is not None:
            fx.banner(ctx, t, fr["t_end"] + 0.2, f"{NAMES[w]} WINS!", COLS[w], "Did your color win?", y=1000, dim=0.45)
            fx.confetti(ctx, t, fr["t_end"] + 0.2, seed=cfg.seed)
        else:
            fx.banner(ctx, t, fr["t_end"] + 0.2, "NOBODY ESCAPED!", fx.RED, "", y=1000, dim=0.45)


AUDIO_MIN_GAP = 0.11


def audio_events(res, cfg):
    times = [t for t, i in res["bounces"]]
    out = [(t, note_freq(nm), "pluck") for t, nm in melodies.track(times, cfg.melody, AUDIO_MIN_GAP)]
    for ev in res["events"]:
        te, kind = ev[0], ev[1]
        if kind in ("out", "crush"):
            out.append((te, 330.0, "out"))
        elif kind == "shrink":
            out.append((te, 880.0, "pop"))
        elif kind == "win":
            out.append((te, 523.25 if ev[5] == 1 else 392.0, "win" if ev[5] == 1 else "chime"))
    return out


def prepare(res, cfg):
    for f in res["frames"]:
        f["res"] = res


# ===================================================================== one module-like object per level type
class _Format:
    AUDIO_MIN_GAP = AUDIO_MIN_GAP

    def __init__(self, kind):
        self.kind = kind
        self.__name__ = f"race_{kind}"

    def make_config(self, seed):
        return make_config(seed, self.kind)

    simulate = staticmethod(simulate)
    is_good = staticmethod(is_good)
    draw = staticmethod(draw)
    audio_events = staticmethod(audio_events)
    prepare = staticmethod(prepare)

    def metadata_facts(self, res, cfg):
        return dict(template=f"race_{self.kind}", colors=list(NAMES), winner=NAMES[res["winner"]],
                    out_order=res["out_order"], t_end=round(res["t_end"], 2), melody=cfg.melody_name,
                    n_balls=4)


race_lava, race_flood, race_crush, race_shrink = (_Format(k) for k in ("lava", "flood", "crush", "shrink"))
