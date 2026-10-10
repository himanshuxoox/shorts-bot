"""
"Ball Battle Royale": 8-10 ball characters (each with its own face that reacts to what
happens) fight in a full-screen arena. Weapons drop in — sword, blaster, hammer, laser,
bomb — plus heal / shield / speed / GIANT power-ups. After about a minute the electrified
walls start closing in. Last ball standing wins.

2-3 minutes at 30 fps, landscape 1920x1080: uploaded as a normal YouTube video (not a Short),
with its own 1280x720 thumbnail.
Faces come from assets/balls/<color>/<emotion>.png (see tools/extract_sprites.py);
weapons, effects, music and SFX are all drawn / synthesized in code.
"""
import math, os, random, subprocess
from dataclasses import dataclass

import cairo
import numpy as np
from PIL import Image

from .common import text, text_fit, rounded, _face
from . import fx, royale_audio

FPS = 30
DT = 1.0 / FPS
SUB = 2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets", "balls")

W, H = 1920, 1080                                     # landscape: a normal video, not a Short
AX0, AY0, AX1, AY1 = 392.0, 112.0, 1892.0, 1056.0      # arena (right of the roster panel)
ACX, ACY = (AX0 + AX1) / 2, (AY0 + AY1) / 2
R = 62.0
HPMAX = 100.0
T_START = 2.1                 # 3-2-1-FIGHT
MAX_T = 190.0
END_HOLD = 5.5
FINAL_W, FINAL_H = 640.0, 520.0

COLS = {
    "red": (1.0, 0.27, 0.27), "blue": (0.25, 0.58, 1.0), "purple": (0.72, 0.42, 1.0),
    "green": (0.33, 0.92, 0.33), "yellow": (1.0, 0.88, 0.2), "orange": (1.0, 0.58, 0.16),
    "pink": (1.0, 0.48, 0.78), "cyan": (0.3, 0.92, 1.0), "white": (0.95, 0.95, 0.95),
    "black": (0.62, 0.62, 0.7),
}
KINDS = ["sword", "blaster", "hammer", "laser", "bomb", "heal", "shield", "speed", "giant"]
WEIGHTS = [3.0, 2.4, 2.0, 1.4, 2.0, 2.0, 1.4, 1.3, 0.5]
KCOL = dict(sword=(0.8, 0.9, 1.0), blaster=(0.3, 1.0, 0.6), hammer=(1.0, 0.62, 0.2),
            laser=(1.0, 0.25, 0.45), bomb=(1.0, 0.4, 0.15), heal=(0.3, 1.0, 0.4),
            shield=(0.3, 0.85, 1.0), speed=(1.0, 0.95, 0.2), giant=(1.0, 0.8, 0.2),
            bump=(1.0, 1.0, 1.0), wall=(1.0, 0.9, 0.2), storm=(1.0, 0.3, 0.3))
WEAPON_DUR = dict(sword=9.0, blaster=7.0, hammer=9.0, laser=2.4)
LABEL = dict(sword="SWORD!", blaster="BLASTER!", hammer="HAMMER!", laser="LASER!", bomb="BOMB!",
             heal="+HEAL", shield="SHIELD!", speed="SPEED!", giant="GIANT!")
WEAPON_FACE = dict(sword="angry", hammer="angry", blaster="focused", laser="determined")


@dataclass
class Config:
    seed: int
    names: list
    cruise: list
    t_close: float
    close_dur: float
    fcx: float
    fcy: float
    spawn_every: float
    target: float = 140.0


def make_config(seed):
    rng = random.Random(seed * 7919 + 13)
    n = rng.choice([8, 9, 10, 10])
    names = rng.sample(list(COLS), n)
    end = rng.uniform(134, 165)             # roughly when the game should end (2:15-2:50)
    target = end / 0.76                     # the director's schedule (games finish ~24% early)
    return Config(seed, names, [rng.uniform(300, 360) for _ in names], end * rng.uniform(0.45, 0.52),
                  end * 0.45, rng.uniform(AX0 + FINAL_W / 2 + 60, AX1 - FINAL_W / 2 - 60),
                  rng.uniform(AY0 + FINAL_H / 2 + 80, AY1 - FINAL_H / 2 - 80), rng.uniform(2.0, 2.6), target)


# ===================================================================== simulation
class Ball:
    def __init__(self, i, name, x, y, cruise, rng):
        self.i, self.name, self.col = i, name, COLS[name]
        self.x, self.y, self.vx, self.vy = x, y, 0.0, 0.0
        self.r, self.hp, self.alive = R, HPMAX, True
        self.cruise = cruise
        self.weapon = None
        self.shield_until = self.speed_until = self.giant_until = -9.0
        self.flash_until = -9.0
        self.face, self.face_until = "happy", -9.0
        self.last_by, self.last_kind, self.last_t = None, None, -99.0
        self.pending, self.last_num = 0.0, -9.0
        self.wall_cd = -9.0
        self.kills, self.death_t = 0, None
        self.ph = rng.uniform(0, 6.28)
        self.side = rng.choice([-1, 1])
        self.trail = []
        self.pre_face = rng.choice(["determined", "focused", "teasing", "excited", "proud"])


def _ang(dx, dy):
    return math.atan2(dy, dx)


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L)) if L else 0.0
    cx, cy = ax + u * dx, ay + u * dy
    return math.hypot(px - cx, py - cy), cx, cy


def _ray_box(x, y, ux, uy, box):
    x0, y0, x1, y1 = box
    ts = []
    if ux > 1e-6: ts.append((x1 - x) / ux)
    if ux < -1e-6: ts.append((x0 - x) / ux)
    if uy > 1e-6: ts.append((y1 - y) / uy)
    if uy < -1e-6: ts.append((y0 - y) / uy)
    t = max(0.0, min(ts)) if ts else 0.0
    return x + ux * t, y + uy * t


class Game:
    def __init__(self, cfg, record):
        self.cfg, self.record = cfg, record
        self.rng = random.Random(cfg.seed * 104729 + 1)
        n = len(cfg.names)
        self.balls = []
        for i, nm in enumerate(cfg.names):
            a = -math.pi / 2 + 2 * math.pi * i / n
            self.balls.append(Ball(i, nm, ACX + 560 * math.cos(a), ACY + 320 * math.sin(a),
                                   cfg.cruise[i], self.rng))
        self.box = [AX0, AY0, AX1, AY1]
        self.pickups, self.bolts, self.bombs = [], [], []
        self.effects, self.feed, self.sounds, self.frames = [], [], [], []
        self.kill_times, self.killers = [], set()
        self.next_spawn = T_START + 1.2
        self.t_end, self.winner, self.sudden = None, None, False
        self.pair_cd = {}
        self.last_sound = {}
        self.last_ann = -9.0
        self.started = False
        self.closing_announced = False
        self.pid = 0
        self.dir = 1.0
        self.finish = 0.0

    # ---------------------------------------------------------------- helpers
    def sound(self, t, kind, gap=0.06):
        if t - self.last_sound.get(kind, -9) >= gap:
            self.last_sound[kind] = t
            self.sounds.append((t, kind))

    def eff(self, *e):
        self.effects.append(e)

    def announce(self, t, s, col=fx.GOLD, snd="rise"):
        t0 = max(t, self.last_ann + 1.25)
        self.last_ann = t0
        self.eff("ann", t0, s, col)
        if snd:
            self.sound(t0, snd, 0)

    def alive(self):
        return [b for b in self.balls if b.alive]

    def mul(self, t):
        return self.dir * (1.0 + 0.4 * min(1.0, max(0.0, (t - self.cfg.t_close) / self.cfg.close_dur)))

    def direct(self, t, h):
        """Hidden game director: speeds damage up / slows it down so the eliminations are spread
        over the whole video instead of all happening at once."""
        n = len(self.balls)
        u = min(1.0, max(0.0, (t - T_START) / (self.cfg.target - T_START)))
        want = n * (1 - u) + 0.45 * u                # total HP left (in "balls"), drains steadily
        pool = sum(b.hp for b in self.alive()) / HPMAX
        err = (pool - want) / max(0.6, 0.12 * n)     # > 0: behind schedule
        goal = min(3.5, max(0.2, 1.8 ** err))
        want_alive = n - (n - 1) * max(0.0, (t - T_START - 4) / (self.cfg.target - T_START - 4)) ** 0.85
        self.finish = min(2.0, max(0.0, len(self.alive()) - want_alive))   # behind on eliminations
        self.dir += (goal - self.dir) * min(1.0, 0.8 * h)

    def set_face(self, b, face, t, dur, prio=1):
        if t >= b.face_until or prio >= getattr(b, "face_prio", 0):
            b.face, b.face_until, b.face_prio = face, t + dur, prio

    def nearest(self, b, pool):
        best, bd = None, 1e18
        for o in pool:
            if o is b:
                continue
            d = (o.x - b.x) ** 2 + (o.y - b.y) ** 2
            if d < bd:
                best, bd = o, d
        return best, math.sqrt(bd)

    # ---------------------------------------------------------------- damage
    def damage(self, v, amt, src, kind, t, knock=(0.0, 0.0)):
        if not v.alive or self.t_end is not None:
            return
        if t < v.shield_until and kind != "storm":
            if t - getattr(v, "last_block", -9) > 0.25:
                v.last_block = t
                self.eff("block", t, v.i)
                self.sound(t, "block", 0.1)
            v.vx += knock[0] * 0.5; v.vy += knock[1] * 0.5
            return
        amt *= self.mul(t) * (1 + 3.0 * self.finish * (1 - v.hp / HPMAX))
        v.hp -= amt
        v.vx += knock[0]; v.vy += knock[1]
        if kind not in ("laser", "storm"):
            v.flash_until = t + 0.12
        if src is not None:
            v.last_by, v.last_kind, v.last_t = src, kind, t
            if kind not in ("bump",):
                self.set_face(src, self.rng.choice(["laughing", "teasing"]), t, 0.6, 1)
        v.pending += amt
        if t - v.last_num > 0.22 or v.hp <= 0:
            self.eff("num", t, v.x, v.y - v.r, f"-{max(1, round(v.pending))}", (1, 0.35, 0.3))
            v.pending, v.last_num = 0.0, t
        self.set_face(v, "crying" if v.hp < 35 else "shocked", t, 0.7 if v.hp < 35 else 0.45, 2)
        if v.hp <= 0:
            self.kill(v, t)

    def kill(self, v, t):
        if len(self.alive()) <= 1:
            v.hp = 1.0
            return
        v.alive, v.hp, v.death_t = False, 0.0, t
        v.weapon = None
        killer = v.last_by if (v.last_by is not None and v.last_by.alive and t - v.last_t < 5.0) else None
        kind = v.last_kind if killer else "wall"
        self.feed.append((t, killer.name if killer else None, kind, v.name))
        self.kill_times.append(t)
        self.eff("ko", t, v.x, v.y, v.col, self.rng.randrange(1 << 30), v.name, v.r)
        self.eff("shake", t, 18.0)
        self.sound(t, "ko", 0)
        self.sound(t, "crack", 0)
        left = len(self.alive())
        prev_kill = getattr(killer, "last_kill_t", -99) if killer else -99
        if killer:
            killer.kills += 1
            killer.last_kill_t = t
            self.killers.add(killer.name)
            self.set_face(killer, "laughing", t, 1.4, 3)
        if len(self.kill_times) == 1:
            self.announce(t, "FIRST BLOOD!", fx.RED)
        elif killer and t - prev_kill < 6.0:
            self.announce(t, f"DOUBLE KILL! {killer.name.upper()}", killer.col)
        elif left == 3:
            self.announce(t, "FINAL 3!", fx.GOLD)
        elif left == 2:
            self.announce(t, "FINAL DUEL!", fx.GOLD)
        elif left == len(self.balls) // 2:
            self.announce(t, f"{left} LEFT!", fx.WHITE)
        for o in self.alive():                       # everyone nearby is shocked
            if math.hypot(o.x - v.x, o.y - v.y) < 360 and o is not killer:
                self.set_face(o, "shocked", t, 0.6, 1)
        if left == 1:
            self.t_end = t
            self.winner = self.alive()[0]
            self.winner.weapon = None
            self.bolts.clear()
            self.sound(t + 0.5, "fanfare", 0)

    # ---------------------------------------------------------------- pickups
    def spawn_pickup(self, t):
        x0, y0, x1, y1 = self.box
        for _ in range(30):
            x = self.rng.uniform(x0 + 70, x1 - 70)
            y = self.rng.uniform(y0 + 70, y1 - 70)
            if all(math.hypot(b.x - x, b.y - y) > 170 for b in self.alive()) and \
                    all(math.hypot(p["x"] - x, p["y"] - y) > 150 for p in self.pickups):
                break
        kinds, wts = KINDS[:], WEIGHTS[:]
        if t < 40:
            wts[KINDS.index("giant")] = 0
        kind = self.rng.choices(kinds, wts)[0]
        self.pid += 1
        self.pickups.append(dict(kind=kind, x=x, y=y, t0=t, id=self.pid))
        self.sound(t, "teleport", 0.2)

    def take(self, b, p, t):
        k = p["kind"]
        self.eff("label", t, b.i, LABEL[k], KCOL[k])
        self.set_face(b, "hyped", t, 0.8, 1)
        if k in WEAPON_DUR:
            b.weapon = dict(kind=k, t0=t, until=t + WEAPON_DUR[k], ang=self.rng.uniform(0, 6.28),
                            next_fire=t + 0.2, cd={}, aim=0.0)
            if k == "laser":
                tgt, _ = self.nearest(b, self.alive())
                b.weapon["aim"] = _ang(tgt.x - b.x, tgt.y - b.y) if tgt else 0.0
                self.sound(t, "charge", 0)
            else:
                self.sound(t, "pickup", 0.05)
        elif k == "bomb":
            tgt, _ = self.nearest(b, self.alive())
            if tgt:
                x0, y0, x1, y1 = self.box
                tx = min(max(tgt.x + tgt.vx * 0.5, x0 + 40), x1 - 40)
                ty = min(max(tgt.y + tgt.vy * 0.5, y0 + 40), y1 - 40)
                self.bombs.append(dict(x0=b.x, y0=b.y, x1=tx, y1=ty, t0=t, t_land=t + 0.7,
                                       t_boom=t + 1.3, owner=b))
                self.sound(t, "whoosh", 0)
        elif k == "heal":
            b.hp = min(HPMAX, b.hp + 35)
            self.eff("heal", t, b.i)
            self.eff("num", t, b.x, b.y - b.r, "+35", (0.35, 1, 0.45))
            self.sound(t, "heal", 0)
        elif k == "shield":
            b.shield_until = t + 6.0
            self.sound(t, "block", 0)
        elif k == "speed":
            b.speed_until = t + 5.0
            self.sound(t, "pickup", 0.05)
        elif k == "giant":
            b.giant_until = t + 8.0
            self.announce(t, f"GIANT {b.name.upper()}!", b.col)

    # ---------------------------------------------------------------- one physics step
    def step(self, t, h):
        cfg = self.cfg
        alive = self.alive()
        # walls closing in
        if t >= cfg.t_close:
            k = min(1.0, (t - cfg.t_close) / cfg.close_dur)
            k = k * k * (3 - 2 * k)
            fin = (cfg.fcx - FINAL_W / 2, cfg.fcy - FINAL_H / 2, cfg.fcx + FINAL_W / 2, cfg.fcy + FINAL_H / 2)
            full = (AX0, AY0, AX1, AY1)
            self.box = [a + (b - a) * k for a, b in zip(full, fin)]
            if not self.closing_announced:
                self.closing_announced = True
                self.announce(t, "WALLS CLOSING IN!", fx.RED, "rise")
        x0, y0, x1, y1 = self.box
        electric = t >= cfg.t_close
        if t > cfg.t_close + cfg.close_dur + 18 and not self.sudden and self.t_end is None:
            self.sudden = True
            self.announce(t, "SUDDEN DEATH!", fx.RED)

        if self.t_end is not None:                 # winner walks to the middle
            w = self.winner
            cx, cy = ACX, ACY + 10
            w.x += (cx - w.x) * min(1, 3 * h); w.y += (cy - w.y) * min(1, 3 * h)
            w.vx = w.vy = 0.0
            w.r += (R * 1.9 - w.r) * min(1, 3 * h)
            self.set_face(w, "victory", t, 1.0, 9)
            self._update_bombs(t, h)
            return

        self.direct(t, h)
        # spawn pickups
        if t >= self.next_spawn:
            if len(self.pickups) < 4:
                self.spawn_pickup(t)
            self.next_spawn = t + cfg.spawn_every * self.rng.uniform(0.75, 1.25) * (0.8 if electric else 1.0)
        self.pickups = [p for p in self.pickups if x0 + 30 < p["x"] < x1 - 30 and y0 + 30 < p["y"] < y1 - 30
                        and t - p["t0"] < 14]

        for b in alive:
            # buffs
            gr = R * 1.45 if t < b.giant_until else R
            b.r += (gr - b.r) * min(1.0, 6 * h)
            if b.weapon and t > b.weapon["until"]:
                b.weapon = None
            # steering
            w = b.weapon["kind"] if b.weapon else None
            tgt, d = self.nearest(b, alive)
            want = None
            turn = 2.2
            if w in ("sword", "hammer") or t < b.speed_until or t < b.giant_until:
                want, turn = _ang(tgt.x - b.x, tgt.y - b.y), 2.6
            elif w in ("blaster", "laser"):
                a = _ang(tgt.x - b.x, tgt.y - b.y)
                want = a + (math.pi * 0.7 if d < 330 else 0.45) * b.side
            else:
                p = min(self.pickups, key=lambda p: (p["x"] - b.x) ** 2 + (p["y"] - b.y) ** 2, default=None)
                if p is not None and math.hypot(p["x"] - b.x, p["y"] - b.y) < 650 and t - p["t0"] > 0.3:
                    want = _ang(p["x"] - b.x, p["y"] - b.y)
                elif b.hp < 35:
                    armed = [o for o in alive if o is not b and o.weapon]
                    if armed:
                        o, _ = self.nearest(b, armed)
                        want = _ang(b.x - o.x, b.y - o.y)
            sp = math.hypot(b.vx, b.vy)
            hd = _ang(b.vx, b.vy) if sp > 1 else b.ph
            if want is not None:
                dif = _wrap(want - hd)
                hd += max(-turn * h, min(turn * h, dif))
            hd += 0.7 * math.sin(t * 0.9 + b.ph) * h
            target = b.cruise * (1.7 if t < b.speed_until else 1.0) * (0.85 if t < b.giant_until else 1.0)
            if w == "laser":
                target *= 0.4
            sp += (target - sp) * min(1.0, 1.6 * h)
            b.vx, b.vy = sp * math.cos(hd), sp * math.sin(hd)
            b.x += b.vx * h; b.y += b.vy * h
            # walls
            hit_wall = False
            if b.x - b.r < x0: b.x, b.vx, hit_wall = x0 + b.r, abs(b.vx), True
            if b.x + b.r > x1: b.x, b.vx, hit_wall = x1 - b.r, -abs(b.vx), True
            if b.y - b.r < y0: b.y, b.vy, hit_wall = y0 + b.r, abs(b.vy), True
            if b.y + b.r > y1: b.y, b.vy, hit_wall = y1 - b.r, -abs(b.vy), True
            if hit_wall and electric and t - b.wall_cd > 0.45:
                b.wall_cd = t
                self.eff("spark", t, b.x, b.y, (1, 0.95, 0.3), self.rng.randrange(1 << 30))
                self.sound(t, "zap", 0.08)
                self.damage(b, 2.0, None, "wall", t)
            if self.sudden and b.alive:
                self.damage(b, 4.0 * h, None, "storm", t)
            # pickups
            for p in list(self.pickups):
                if t - p["t0"] > 0.45 and math.hypot(p["x"] - b.x, p["y"] - b.y) < b.r + 30:
                    self.pickups.remove(p)
                    self.take(b, p, t)

        alive = self.alive()
        # ball-ball contact
        for ai in range(len(alive)):
            a = alive[ai]
            for bj in range(ai + 1, len(alive)):
                b = alive[bj]
                dx, dy = b.x - a.x, b.y - a.y
                d = math.hypot(dx, dy)
                if d >= a.r + b.r or d < 1e-6:
                    continue
                nx, ny = dx / d, dy / d
                ov = a.r + b.r - d
                ma, mb = a.r * a.r, b.r * b.r
                a.x -= nx * ov * mb / (ma + mb); a.y -= ny * ov * mb / (ma + mb)
                b.x += nx * ov * ma / (ma + mb); b.y += ny * ov * ma / (ma + mb)
                vn = (a.vx - b.vx) * nx + (a.vy - b.vy) * ny
                if vn > 0:
                    j = 2 * vn / (ma + mb)
                    a.vx -= j * mb * nx; a.vy -= j * mb * ny
                    b.vx += j * ma * nx; b.vy += j * ma * ny
                    key = (a.i, b.i)
                    if vn > 180 and t - self.pair_cd.get(key, -9) > 0.3:
                        self.pair_cd[key] = t
                        self.eff("spark", t, a.x + nx * a.r, a.y + ny * a.r, (1, 1, 1), self.rng.randrange(1 << 30))
                        self.sound(t, "punch", 0.1)
                        for s, v, sgn in ((a, b, 1), (b, a, -1)):
                            dmg = 1.0
                            kb = 0.0
                            if t < s.giant_until:
                                dmg, kb = 12.0, 700.0
                            elif t < s.speed_until:
                                dmg = 8.0
                            self.damage(v, dmg, s if dmg > 1.0 else None, "giant" if t < s.giant_until else
                                        ("speed" if t < s.speed_until else "bump"), t,
                                        (sgn * nx * kb, sgn * ny * kb))
                            if dmg <= 1.0 and v.alive:
                                v.last_by, v.last_kind, v.last_t = s, "bump", t
                        if t < a.shield_until or t < b.shield_until:
                            self.sound(t, "block", 0.1)

        # weapons
        for b in self.alive():
            if not b.weapon:
                continue
            wp = b.weapon
            k = wp["kind"]
            enemies = [o for o in self.alive() if o is not b]
            if not enemies:
                break
            tgt, d = self.nearest(b, enemies)
            if k == "sword":
                wp["ang"] += 7.5 * h
                ux, uy = math.cos(wp["ang"]), math.sin(wp["ang"])
                ax, ay = b.x + ux * (b.r + 4), b.y + uy * (b.r + 4)
                ex, ey = b.x + ux * (b.r + 84), b.y + uy * (b.r + 84)
                if t - wp.get("swish", -9) > 0.55:
                    wp["swish"] = t
                    self.sound(t, "whoosh", 0.2)
                for e in enemies:
                    dd, cx, cy = _seg_dist(e.x, e.y, ax, ay, ex, ey)
                    if dd < e.r and t - wp["cd"].get(e.i, -9) > 0.35:
                        wp["cd"][e.i] = t
                        nx, ny = (e.x - b.x) / max(1, d), (e.y - b.y) / max(1, d)
                        self.eff("spark", t, cx, cy, (0.85, 0.95, 1), self.rng.randrange(1 << 30))
                        self.sound(t, "slash", 0.05)
                        self.damage(e, 7.0, b, "sword", t, (nx * 260, ny * 260))
            elif k == "hammer":
                hd = _ang(b.vx, b.vy)
                wp["ang"] = hd + 1.35 * math.sin(t * 8.0 + b.ph)
                ux, uy = math.cos(wp["ang"]), math.sin(wp["ang"])
                hx, hy = b.x + ux * (b.r + 62), b.y + uy * (b.r + 62)
                for e in enemies:
                    if math.hypot(e.x - hx, e.y - hy) < e.r + 30 and t - wp["cd"].get(e.i, -9) > 0.7:
                        wp["cd"][e.i] = t
                        nx, ny = e.x - b.x, e.y - b.y
                        L = max(1.0, math.hypot(nx, ny))
                        self.eff("spark", t, hx, hy, (1, 0.7, 0.3), self.rng.randrange(1 << 30))
                        self.eff("shake", t, 12.0)
                        self.sound(t, "heavy", 0.05)
                        self.damage(e, 12.0, b, "hammer", t, (nx / L * 850, ny / L * 850))
            elif k == "blaster":
                wp["aim"] = _ang(tgt.x - b.x, tgt.y - b.y)
                if t >= wp["next_fire"] and d < 950:
                    wp["next_fire"] = t + 0.42
                    ux, uy = math.cos(wp["aim"]), math.sin(wp["aim"])
                    self.bolts.append([b.x + ux * (b.r + 30), b.y + uy * (b.r + 30), ux * 1050, uy * 1050, b])
                    self.sound(t, "pew", 0.05)
            elif k == "laser":
                want = _ang(tgt.x - b.x, tgt.y - b.y)
                firing = t >= wp["t0"] + 0.9
                rate = 1.1 if firing else 3.0
                wp["aim"] += max(-rate * h, min(rate * h, _wrap(want - wp["aim"])))
                if firing:
                    if not wp.get("fired"):
                        wp["fired"] = True
                        self.sound(t, "laser", 0)
                    ux, uy = math.cos(wp["aim"]), math.sin(wp["aim"])
                    for e in enemies:
                        px, py = e.x - b.x, e.y - b.y
                        along = px * ux + py * uy
                        perp = abs(px * uy - py * ux)
                        if along > 0 and perp < e.r * 0.85 + 14:
                            self.damage(e, 30.0 * h, b, "laser", t, (ux * 900 * h, uy * 900 * h))
                            if self.rng.random() < 0.3:
                                self.eff("spark", t, e.x - ux * e.r, e.y - uy * e.r, (1, 0.4, 0.5),
                                        self.rng.randrange(1 << 30))
                    if self.rng.random() < 0.15:
                        self.eff("shake", t, 4.0)

        # bolts
        keep = []
        for bl in self.bolts:
            bl[0] += bl[2] * h; bl[1] += bl[3] * h
            hit = False
            if not (x0 < bl[0] < x1 and y0 < bl[1] < y1):
                continue
            for e in self.alive():
                if e is bl[4]:
                    continue
                if math.hypot(e.x - bl[0], e.y - bl[1]) < e.r + 8:
                    sp = math.hypot(bl[2], bl[3])
                    self.eff("spark", t, bl[0], bl[1], (0.4, 1, 0.6), self.rng.randrange(1 << 30))
                    self.sound(t, "punch", 0.08)
                    self.damage(e, 4.0, bl[4], "blaster", t, (bl[2] / sp * 140, bl[3] / sp * 140))
                    hit = True
                    break
            if not hit:
                keep.append(bl)
        self.bolts = keep
        self._update_bombs(t, h)

    def _update_bombs(self, t, h):
        keep = []
        for bm in self.bombs:
            if t >= bm["t_boom"]:
                self.eff("boom", t, bm["x1"], bm["y1"])
                self.eff("shake", t, 24.0)
                self.sound(t, "boom", 0)
                for e in self.alive():
                    if e is bm["owner"]:
                        continue
                    d = math.hypot(e.x - bm["x1"], e.y - bm["y1"])
                    if d < 240 + e.r * 0.5:
                        dmg = max(8.0, 26.0 - 16.0 * d / 240)
                        L = max(1.0, d)
                        kb = 950 * max(0.3, 1 - d / 300)
                        self.damage(e, dmg, bm["owner"] if bm["owner"].alive else None, "bomb", t,
                                    ((e.x - bm["x1"]) / L * kb, (e.y - bm["y1"]) / L * kb))
            else:
                keep.append(bm)
        self.bombs = keep

    # ---------------------------------------------------------------- faces + snapshot
    def face_of(self, b, t):
        if not b.alive:
            return "defeated"
        if self.winner is b:
            return "victory"
        if t < T_START:
            return b.pre_face
        if t < b.face_until:
            return b.face
        if b.weapon:
            return WEAPON_FACE[b.weapon["kind"]]
        if t < b.giant_until:
            return "proud"
        if t < b.speed_until:
            return "excited"
        if t < b.shield_until:
            return "proud"
        if b.hp < 30:
            return "scared" if (t + b.ph) % 4 < 2 else "nervous"
        return "happy"

    def snapshot(self, t):
        balls = []
        for b in self.balls:
            if b.alive and t < b.speed_until:
                b.trail = (b.trail + [(b.x, b.y)])[-5:]
            else:
                b.trail = []
            wp = b.weapon
            balls.append(dict(
                name=b.name, x=b.x, y=b.y, r=b.r, hp=max(0.0, b.hp), alive=b.alive, face=self.face_of(b, t),
                flash=t < b.flash_until, death_t=b.death_t, kills=b.kills,
                w=wp["kind"] if wp else None, wang=(wp["ang"] if wp and wp["kind"] in ("sword", "hammer")
                                                     else (wp["aim"] if wp else 0.0)),
                wt0=wp["t0"] if wp else 0.0, wuntil=wp["until"] if wp else 0.0,
                shield=max(0.0, b.shield_until - t), speed=t < b.speed_until, giant=t < b.giant_until,
                trail=list(b.trail), ph=b.ph))
        return dict(t=t, box=tuple(self.box), balls=balls,
                    bolts=[(bl[0], bl[1], bl[2], bl[3], bl[4].col) for bl in self.bolts],
                    bombs=[(bm["x0"], bm["y0"], bm["x1"], bm["y1"], bm["t0"], bm["t_land"], bm["t_boom"])
                           for bm in self.bombs],
                    pickups=[(p["kind"], p["x"], p["y"], p["t0"]) for p in self.pickups],
                    alive=len(self.alive()), t_end=self.t_end,
                    winner=self.winner.i if self.winner else None, sudden=self.sudden)

    def run(self):
        t = 0.0
        for k, s in enumerate(["3", "2", "1"]):
            self.eff("count", k * 0.7, s)
            self.sounds.append((k * 0.7, "beep"))
        self.eff("ann", T_START, "FIGHT!", fx.GOLD)
        self.last_ann = T_START
        self.sounds.append((T_START, "go"))
        nmax = int((MAX_T + END_HOLD) * FPS)
        for _f in range(nmax):
            for s in range(SUB):
                tt = t + s * DT / SUB
                if tt >= T_START:
                    if not self.started:
                        self.started = True
                        for b in self.balls:
                            a = _ang(b.x - ACX, b.y - ACY) + self.rng.uniform(-0.5, 0.5)
                            b.vx, b.vy = b.cruise * math.cos(a), b.cruise * math.sin(a)
                    self.step(tt, DT / SUB)
            t += DT
            if self.record:
                self.frames.append(self.snapshot(t))
            if self.t_end is not None and t - self.t_end > END_HOLD:
                break
        return dict(frames=self.frames, effects=self.effects, feed=self.feed, sounds=self.sounds,
                    t_end=self.t_end, kill_times=self.kill_times, killers=len(self.killers),
                    winner=self.winner.name if self.winner else None, n=len(self.balls),
                    sudden=self.sudden, total=t)


def simulate(cfg, record=False):
    return Game(cfg, record).run()


def is_good(res):
    te, kt = res["t_end"], res["kill_times"]
    if te is None or res["sudden"] or not 122 <= te <= 172:
        return False
    if not 8 <= kt[0] <= 42:
        return False
    gaps = np.diff([T_START] + kt)
    if gaps.max() > 38:
        return False
    if te - kt[-2] < 6:                  # the final duel should last a bit
        return False
    return res["killers"] >= 3


# ===================================================================== drawing
_SPR = {}


def sprite(name, emo, size):
    key = (name, emo, size)
    if key not in _SPR:
        im = Image.open(os.path.join(ASSETS, name, emo + ".png")).convert("RGBA").resize((size, size), Image.LANCZOS)
        a = np.asarray(im).astype(np.float32)
        al = a[..., 3:4] / 255.0
        bgra = np.concatenate([a[..., 2:3] * al, a[..., 1:2] * al, a[..., 0:1] * al, a[..., 3:4]], axis=2)
        stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, size)
        buf = np.zeros((size, stride // 4, 4), np.uint8)
        buf[:, :size] = np.clip(bgra + 0.5, 0, 255).astype(np.uint8)
        surf = cairo.ImageSurface.create_for_data(memoryview(buf), cairo.FORMAT_ARGB32, size, size, stride)
        _SPR[key] = (surf, buf)
    return _SPR[key][0]


def draw_sprite(ctx, name, emo, x, y, r, sx=1.0, sy=1.0, alpha=1.0):
    size = 2 * r * 1.04
    base = 132 if size < 150 else (200 if size < 240 else 300)
    s = sprite(name, emo, base)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(size / base * sx, size / base * sy)
    ctx.set_source_surface(s, -base / 2, -base / 2)
    if alpha < 1:
        ctx.paint_with_alpha(alpha)
    else:
        ctx.paint()
    ctx.restore()


_BG = {}


def _background():
    if "bg" not in _BG:
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        c = cairo.Context(s)
        c.set_source_rgb(0.02, 0.02, 0.04)
        c.paint()
        g = cairo.LinearGradient(0, AY0, 0, AY1)
        g.add_color_stop_rgb(0, 0.05, 0.06, 0.14)
        g.add_color_stop_rgb(1, 0.03, 0.03, 0.08)
        c.rectangle(AX0, AY0, AX1 - AX0, AY1 - AY0)
        c.set_source(g)
        c.fill()
        c.set_line_width(1.5)
        c.set_source_rgba(0.3, 0.5, 1.0, 0.10)
        x = AX0
        while x <= AX1:
            c.move_to(x, AY0); c.line_to(x, AY1); x += 56
        y = AY0
        while y <= AY1:
            c.move_to(AX0, y); c.line_to(AX1, y); y += 56
        c.stroke()
        # hazard stripes (shown outside the closing walls)
        hz = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        hc = cairo.Context(hz)
        hc.set_source_rgba(0.35, 0.02, 0.04, 0.85)
        hc.paint()
        hc.set_source_rgba(0.9, 0.15, 0.1, 0.22)
        for k in range(-40, 80):
            x = k * 60
            hc.move_to(x, 0); hc.line_to(x + 30, 0); hc.line_to(x + 30 - H, H); hc.line_to(x - H, H)
            hc.close_path()
        hc.fill()
        _BG["bg"], _BG["hz"] = s, hz
    return _BG["bg"], _BG["hz"]


def _hp_col(f):
    if f > 0.6:
        return (0.3, 0.95, 0.4)
    if f > 0.3:
        return (1.0, 0.85, 0.2)
    return (1.0, 0.3, 0.25)


def draw_icon(ctx, kind, x, y, s, rot=0.0):
    """Small weapon / power-up icon (pickups and the kill feed). s ~ icon radius."""
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    c = KCOL.get(kind, (1, 1, 1))
    if kind == "sword":
        ctx.rotate(-math.pi / 4)
        ctx.set_source_rgb(0.85, 0.92, 1.0)
        ctx.move_to(-s * 0.13, s * 0.3); ctx.line_to(-s * 0.13, -s * 0.75); ctx.line_to(0, -s)
        ctx.line_to(s * 0.13, -s * 0.75); ctx.line_to(s * 0.13, s * 0.3); ctx.close_path(); ctx.fill()
        ctx.set_source_rgb(1, 0.8, 0.2); ctx.rectangle(-s * 0.4, s * 0.3, s * 0.8, s * 0.13); ctx.fill()
        ctx.set_source_rgb(0.55, 0.32, 0.15); ctx.rectangle(-s * 0.09, s * 0.43, s * 0.18, s * 0.45); ctx.fill()
    elif kind == "blaster":
        ctx.set_source_rgb(0.25, 0.3, 0.38)
        rounded(ctx, -s * 0.8, -s * 0.35, s * 1.5, s * 0.5, s * 0.15); ctx.fill()
        ctx.rectangle(-s * 0.55, s * 0.1, s * 0.35, s * 0.6); ctx.fill()
        ctx.set_source_rgb(*c); ctx.rectangle(s * 0.55, -s * 0.28, s * 0.3, s * 0.36); ctx.fill()
        ctx.rectangle(-s * 0.55, -s * 0.2, s * 0.9, s * 0.08); ctx.fill()
    elif kind == "hammer":
        ctx.rotate(-math.pi / 5)
        ctx.set_source_rgb(0.55, 0.32, 0.15); ctx.rectangle(-s * 0.09, -s * 0.3, s * 0.18, s * 1.2); ctx.fill()
        ctx.set_source_rgb(0.6, 0.62, 0.7); rounded(ctx, -s * 0.6, -s * 0.8, s * 1.2, s * 0.55, s * 0.1); ctx.fill()
        ctx.set_source_rgb(*c); ctx.rectangle(-s * 0.6, -s * 0.8, s * 0.18, s * 0.55); ctx.fill()
        ctx.rectangle(s * 0.42, -s * 0.8, s * 0.18, s * 0.55); ctx.fill()
    elif kind == "laser":
        ctx.set_source_rgba(*c, 0.35); ctx.set_line_width(s * 0.5)
        ctx.move_to(-s * 0.2, 0); ctx.line_to(s, 0); ctx.stroke()
        ctx.set_source_rgb(1, 1, 1); ctx.set_line_width(s * 0.16)
        ctx.move_to(-s * 0.2, 0); ctx.line_to(s, 0); ctx.stroke()
        ctx.set_source_rgb(0.3, 0.3, 0.4); ctx.arc(-s * 0.45, 0, s * 0.42, 0, 6.29); ctx.fill()
        ctx.set_source_rgb(*c); ctx.arc(-s * 0.45, 0, s * 0.22, 0, 6.29); ctx.fill()
    elif kind == "bomb":
        ctx.set_source_rgb(0.12, 0.12, 0.15); ctx.arc(0, s * 0.12, s * 0.7, 0, 6.29); ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.35); ctx.arc(-s * 0.25, -s * 0.12, s * 0.18, 0, 6.29); ctx.fill()
        ctx.set_source_rgb(0.5, 0.5, 0.55); ctx.rectangle(-s * 0.18, -s * 0.72, s * 0.36, s * 0.2); ctx.fill()
        ctx.set_source_rgb(0.9, 0.8, 0.6); ctx.set_line_width(s * 0.09)
        ctx.move_to(0, -s * 0.72); ctx.curve_to(s * 0.1, -s * 0.95, s * 0.4, -s * 0.9, s * 0.45, -s * 1.0); ctx.stroke()
        ctx.set_source_rgb(1, 0.6, 0.1); ctx.arc(s * 0.47, -s * 1.02, s * 0.14, 0, 6.29); ctx.fill()
    elif kind == "heal":
        ctx.set_source_rgb(*c)
        ctx.rectangle(-s * 0.22, -s * 0.75, s * 0.44, s * 1.5); ctx.fill()
        ctx.rectangle(-s * 0.75, -s * 0.22, s * 1.5, s * 0.44); ctx.fill()
    elif kind == "shield":
        ctx.set_source_rgb(*c)
        ctx.move_to(0, -s * 0.85); ctx.line_to(s * 0.7, -s * 0.55); ctx.line_to(s * 0.6, s * 0.2)
        ctx.line_to(0, s * 0.85); ctx.line_to(-s * 0.6, s * 0.2); ctx.line_to(-s * 0.7, -s * 0.55)
        ctx.close_path(); ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.5)
        ctx.move_to(0, -s * 0.6); ctx.line_to(0, s * 0.55); ctx.set_line_width(s * 0.1); ctx.stroke()
    elif kind in ("speed", "wall", "storm"):
        ctx.set_source_rgb(*c)
        ctx.move_to(s * 0.2, -s * 0.9); ctx.line_to(-s * 0.5, s * 0.1); ctx.line_to(-s * 0.02, s * 0.1)
        ctx.line_to(-s * 0.25, s * 0.9); ctx.line_to(s * 0.5, -s * 0.15); ctx.line_to(s * 0.02, -s * 0.15)
        ctx.close_path(); ctx.fill()
    elif kind == "giant":
        _crown(ctx, 0, s * 0.15, s * 1.5)
    else:                                   # bump: an impact star
        ctx.set_source_rgb(*c)
        for j in range(16):
            a = j * math.pi / 8
            rr = s * (0.85 if j % 2 == 0 else 0.4)
            (ctx.move_to if j == 0 else ctx.line_to)(rr * math.cos(a), rr * math.sin(a))
        ctx.close_path(); ctx.fill()
    ctx.restore()


def _crown(ctx, x, y, w):
    ctx.save()
    ctx.translate(x, y)
    h = w * 0.62
    ctx.move_to(-w / 2, h / 2); ctx.line_to(-w / 2, -h / 2); ctx.line_to(-w / 4, 0); ctx.line_to(0, -h / 2 - h * 0.15)
    ctx.line_to(w / 4, 0); ctx.line_to(w / 2, -h / 2); ctx.line_to(w / 2, h / 2); ctx.close_path()
    ctx.set_source_rgb(*fx.GOLD)
    ctx.fill_preserve()
    ctx.set_source_rgb(0.75, 0.5, 0.05)
    ctx.set_line_width(max(1.5, w * 0.05))
    ctx.stroke()
    ctx.set_source_rgb(1, 0.25, 0.35)
    for px in (-w / 4, 0, w / 4):
        ctx.arc(px, h * 0.22, w * 0.07, 0, 6.29)
        ctx.fill()
    ctx.restore()


def _outlined(ctx, s, x, y, size, col, a=1.0, outline=6, max_w=None):
    _face(ctx, size, True)
    ext = ctx.text_extents(s)
    if max_w and ext.width > max_w:
        size *= max_w / ext.width
        _face(ctx, size, True)
        ext = ctx.text_extents(s)
    ctx.move_to(x - (ext.width / 2 + ext.x_bearing), y)
    ctx.text_path(s)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_source_rgba(0, 0, 0, a)
    ctx.set_line_width(outline)
    ctx.stroke_preserve()
    ctx.set_source_rgba(*col, a)
    ctx.fill()


def _draw_weapon(ctx, b, t):
    k, x, y, r, a = b["w"], b["x"], b["y"], b["r"], b["wang"]
    if k == "sword":
        ux, uy = math.cos(a), math.sin(a)
        # motion trail
        for j in range(1, 6):
            aa = a - j * 0.09
            ctx.set_source_rgba(0.7, 0.85, 1.0, 0.16 * (6 - j) / 5)
            ctx.set_line_width(14)
            ctx.move_to(x + math.cos(aa) * (r + 20), y + math.sin(aa) * (r + 20))
            ctx.line_to(x + math.cos(aa) * (r + 84), y + math.sin(aa) * (r + 84))
            ctx.stroke()
        ctx.save()
        ctx.translate(x + ux * (r + 46), y + uy * (r + 46))
        ctx.rotate(a + math.pi / 2)
        ctx.set_source_rgb(0.88, 0.94, 1.0)
        ctx.move_to(-8, 30); ctx.line_to(-8, -30); ctx.line_to(0, -42); ctx.line_to(8, -30); ctx.line_to(8, 30)
        ctx.close_path(); ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.8); ctx.rectangle(-2, -30, 4, 58); ctx.fill()
        ctx.set_source_rgb(1, 0.8, 0.2); ctx.rectangle(-20, 30, 40, 8); ctx.fill()
        ctx.set_source_rgb(0.55, 0.32, 0.15); ctx.rectangle(-5, 38, 10, 16); ctx.fill()
        ctx.restore()
    elif k == "hammer":
        ux, uy = math.cos(a), math.sin(a)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgb(0.55, 0.32, 0.15)
        ctx.set_line_width(10)
        ctx.move_to(x + ux * (r - 6), y + uy * (r - 6)); ctx.line_to(x + ux * (r + 62), y + uy * (r + 62))
        ctx.stroke()
        ctx.save()
        ctx.translate(x + ux * (r + 62), y + uy * (r + 62))
        ctx.rotate(a)
        ctx.set_source_rgb(0.62, 0.64, 0.72)
        rounded(ctx, -22, -34, 44, 68, 8); ctx.fill()
        ctx.set_source_rgb(*KCOL["hammer"])
        ctx.rectangle(-22, -34, 44, 10); ctx.fill(); ctx.rectangle(-22, 24, 44, 10); ctx.fill()
        ctx.restore()
    elif k == "blaster":
        ux, uy = math.cos(a), math.sin(a)
        ctx.save()
        ctx.translate(x + ux * (r + 6), y + uy * (r + 6))
        ctx.rotate(a)
        if abs(_wrap(a)) > math.pi / 2:
            ctx.scale(1, -1)
        ctx.set_source_rgb(0.25, 0.3, 0.38)
        rounded(ctx, -4, -11, 46, 20, 5); ctx.fill()
        ctx.rectangle(0, 6, 12, 18); ctx.fill()
        ctx.set_source_rgb(*KCOL["blaster"])
        ctx.rectangle(38, -9, 10, 16); ctx.fill()
        ctx.restore()
    elif k == "laser":
        ux, uy = math.cos(a), math.sin(a)
        ex, ey = x + ux * (r + 10), y + uy * (r + 10)
        firing = t >= b["wt0"] + 0.9
        ctx.set_source_rgb(0.3, 0.3, 0.4)
        ctx.arc(ex, ey, 16, 0, 6.29); ctx.fill()
        ctx.set_source_rgb(*KCOL["laser"])
        ctx.arc(ex, ey, 9 + (3 * math.sin(t * 40) if not firing else 4), 0, 6.29); ctx.fill()


def _laser_beam(ctx, b, t, box):
    if b["w"] != "laser":
        return
    a = b["wang"]
    ux, uy = math.cos(a), math.sin(a)
    sx, sy = b["x"] + ux * (b["r"] + 10), b["y"] + uy * (b["r"] + 10)
    ex, ey = _ray_box(sx, sy, ux, uy, box)
    firing = t >= b["wt0"] + 0.9
    col = KCOL["laser"]
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    if not firing:
        if int(t * 16) % 2 == 0:
            ctx.set_source_rgba(*col, 0.7)
            ctx.set_line_width(3)
            ctx.set_dash([18, 12])
            ctx.move_to(sx, sy); ctx.line_to(ex, ey); ctx.stroke()
            ctx.set_dash([])
        return
    left = b["wuntil"] - t
    k = min(1.0, (t - b["wt0"] - 0.9) / 0.08) * min(1.0, left / 0.15)
    wob = 1 + 0.12 * math.sin(t * 60)
    for wdt, al, c in ((60, 0.18, col), (34, 0.4, col), (16, 0.95, col), (7, 1.0, (1, 1, 1))):
        ctx.set_source_rgba(*c, al * k)
        ctx.set_line_width(wdt * wob * k)
        ctx.move_to(sx, sy); ctx.line_to(ex, ey); ctx.stroke()
    ctx.set_source_rgba(1, 1, 1, 0.9 * k)
    ctx.arc(ex, ey, 18 * wob, 0, 6.29); ctx.fill()


def _particles(ctx, t, t0, x, y, col, seed, n=10, spd=420, life=0.4, size=5):
    dt = t - t0
    if dt < 0 or dt > life:
        return
    rng = random.Random(seed)
    k = dt / life
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for _ in range(n):
        a = rng.uniform(0, 6.28)
        v = rng.uniform(0.4, 1.0) * spd
        px, py = x + math.cos(a) * v * dt, y + math.sin(a) * v * dt
        ctx.set_source_rgba(*col, 1 - k)
        ctx.set_line_width(size * (1 - k) + 1)
        ctx.move_to(px, py)
        ctx.line_to(px - math.cos(a) * 14 * (1 - k), py - math.sin(a) * 14 * (1 - k))
        ctx.stroke()


def draw(ctx, fr, cfg, res):
    t = fr["t"]
    balls = fr["balls"]
    bg, hz = _background()
    # screen shake
    shake = 0.0
    for e in res["eff_shake"]:
        if 0 <= t - e[1] < 0.35:
            shake = max(shake, e[2] * (1 - (t - e[1]) / 0.35))
    sx = sy = 0.0
    if shake:
        rr = random.Random(int(t * 1000))
        sx, sy = rr.uniform(-shake, shake), rr.uniform(-shake, shake)

    ctx.set_source_surface(bg, 0, 0)
    ctx.paint()
    ctx.save()
    ctx.translate(sx, sy)
    x0, y0, x1, y1 = fr["box"]
    closing = (x0, y0, x1, y1) != (AX0, AY0, AX1, AY1)
    if closing:
        ctx.save()
        ctx.rectangle(AX0, AY0, AX1 - AX0, AY1 - AY0)
        ctx.rectangle(x1, y0, x0 - x1, y1 - y0)          # reversed = hole
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.clip()
        ctx.set_source_surface(hz, 0, 0)
        ctx.paint()
        ctx.restore()
    # arena walls
    if closing:
        fl = 0.6 + 0.4 * math.sin(t * 30)
        ctx.set_source_rgba(1.0, 0.85, 0.2, 0.25 * fl)
        ctx.set_line_width(26)
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0); ctx.stroke()
        ctx.set_source_rgb(1.0, 0.9, 0.35)
        ctx.set_line_width(7)
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0); ctx.stroke()
        # little lightning zigzags running along the walls
        rr = random.Random(int(t * 15))
        ctx.set_source_rgba(1, 1, 0.8, 0.9)
        ctx.set_line_width(3)
        for _ in range(6):
            side = rr.randrange(4)
            u = rr.random()
            px, py = [(x0 + u * (x1 - x0), y0), (x1, y0 + u * (y1 - y0)), (x0 + u * (x1 - x0), y1),
                      (x0, y0 + u * (y1 - y0))][side]
            ctx.move_to(px, py)
            for j in range(4):
                ctx.line_to(px + rr.uniform(-18, 18), py + rr.uniform(-18, 18))
            ctx.stroke()
    else:
        ctx.set_source_rgba(0.3, 0.75, 1.0, 0.25)
        ctx.set_line_width(22)
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0); ctx.stroke()
        ctx.set_source_rgb(0.4, 0.85, 1.0)
        ctx.set_line_width(6)
        ctx.rectangle(x0, y0, x1 - x0, y1 - y0); ctx.stroke()

    # pickups
    for kind, px, py, t0 in fr["pickups"]:
        k = min(1.0, (t - t0) / 0.45)
        drop = (1 - k) ** 2 * 260
        sc = 0.6 + 0.4 * k
        bob = 5 * math.sin(t * 4 + px)
        col = KCOL[kind]
        ctx.save()
        ctx.translate(px, py - drop + bob)
        ctx.scale(sc, sc)
        ctx.set_source_rgba(*col, 0.25 + 0.1 * math.sin(t * 6))
        ctx.arc(0, 0, 46, 0, 6.29); ctx.fill()
        ctx.set_source_rgb(0.08, 0.08, 0.13)
        rounded(ctx, -30, -30, 60, 60, 12); ctx.fill()
        ctx.set_source_rgb(*col)
        ctx.set_line_width(4)
        rounded(ctx, -30, -30, 60, 60, 12); ctx.stroke()
        draw_icon(ctx, kind, 0, 2, 20)
        ctx.restore()

    # bombs in flight / on the ground
    for bx0, by0, bx1, by1, t0, tl, tb in fr["bombs"]:
        if t < tl:
            k = (t - t0) / (tl - t0)
            bx, by = bx0 + (bx1 - bx0) * k, by0 + (by1 - by0) * k
            z = 4 * k * (1 - k) * 170
            ctx.set_source_rgba(0, 0, 0, 0.35)
            ctx.save(); ctx.translate(bx, by + 20); ctx.scale(1, 0.4); ctx.arc(0, 0, 22, 0, 6.29); ctx.restore()
            ctx.fill()
            draw_icon(ctx, "bomb", bx, by - z, 26, rot=k * 8)
        else:
            k = (t - tl) / (tb - tl)
            ctx.set_source_rgba(1, 0.2, 0.1, 0.25 + 0.25 * (int(t * 12) % 2))
            ctx.arc(bx1, by1, 240 * (0.3 + 0.7 * k), 0, 6.29); ctx.fill()
            ctx.set_source_rgba(1, 0.3, 0.2, 0.7)
            ctx.set_line_width(3)
            ctx.arc(bx1, by1, 240, 0, 6.29); ctx.stroke()
            draw_icon(ctx, "bomb", bx1, by1, 26 * (1 + 0.15 * (int(t * 12) % 2)))

    # shadows, trails
    for b in balls:
        if not b["alive"]:
            continue
        for j, (tx, ty) in enumerate(b["trail"][:-1]):
            draw_sprite(ctx, b["name"], b["face"], tx, ty, b["r"], alpha=0.12 + 0.08 * j)
    # laser beams under the balls
    for b in balls:
        if b["alive"]:
            _laser_beam(ctx, b, t, fr["box"])
    # balls
    for b in balls:
        if not b["alive"]:
            continue
        x, y, r = b["x"], b["y"], b["r"]
        if b["giant"]:
            ctx.set_source_rgba(1, 0.8, 0.2, 0.25 + 0.1 * math.sin(t * 10))
            ctx.arc(x, y, r + 14, 0, 6.29); ctx.fill()
        if b["w"] in ("sword", "hammer", "blaster", "laser"):
            col = KCOL[b["w"]]
            ctx.set_source_rgba(*col, 0.22)
            ctx.arc(x, y, r + 8, 0, 6.29); ctx.fill()
        sq = 1.0
        if b["flash"]:
            sq = 0.88
        wob = 1 + 0.025 * math.sin(t * 7 + b["ph"])
        draw_sprite(ctx, b["name"], b["face"], x, y, r, sx=wob / sq ** 0.5, sy=sq * (2 - wob))
        if b["flash"]:
            ctx.set_source_rgba(1, 1, 1, 0.45)
            ctx.arc(x, y, r * 0.98, 0, 6.29); ctx.fill()
        if b["w"]:
            _draw_weapon(ctx, b, t)
        if b["shield"] > 0:
            a = min(1.0, b["shield"] / 0.6) * (0.75 if b["shield"] > 1.5 or int(t * 10) % 2 else 0.3)
            ctx.set_source_rgba(0.3, 0.85, 1.0, 0.18 * a)
            ctx.arc(x, y, r + 20, 0, 6.29); ctx.fill()
            ctx.set_source_rgba(0.5, 0.95, 1.0, 0.9 * a)
            ctx.set_line_width(4)
            ctx.arc(x, y, r + 20, 0, 6.29); ctx.stroke()
            ctx.set_source_rgba(1, 1, 1, 0.6 * a)
            ctx.arc(x, y, r + 14, -2.4 + t, -1.6 + t); ctx.stroke()
        if fr["winner"] is None:
            # name + HP bar above the ball
            bw = 104
            by = y - r - 20
            col = COLS[b["name"]]
            _outlined(ctx, b["name"].upper(), x, by - 10, 24, col, 1, 5)
            ctx.set_source_rgba(0, 0, 0, 0.75)
            rounded(ctx, x - bw / 2 - 3, by - 3, bw + 6, 14, 5); ctx.fill()
            f = b["hp"] / HPMAX
            ctx.set_source_rgb(*_hp_col(f))
            ctx.rectangle(x - bw / 2, by, bw * f, 8); ctx.fill()

    # bolts
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for bx, by, vx, vy, col in fr["bolts"]:
        sp = math.hypot(vx, vy)
        ux, uy = vx / sp, vy / sp
        for wdt, al, c in ((16, 0.3, KCOL["blaster"]), (7, 1.0, (1, 1, 1))):
            ctx.set_source_rgba(*c, al)
            ctx.set_line_width(wdt)
            ctx.move_to(bx, by); ctx.line_to(bx - ux * 34, by - uy * 34); ctx.stroke()

    # effects
    for e in res["eff_world"]:
        kind, t0 = e[0], e[1]
        dt = t - t0
        if dt < 0:
            continue
        if kind == "spark":
            _particles(ctx, t, t0, e[2], e[3], e[4], e[5], n=9, spd=480, life=0.3)
        elif kind == "boom" and dt < 0.9:
            k = dt / 0.9
            ctx.set_source_rgba(1, 0.95, 0.7, max(0, 0.9 - 3 * k))
            ctx.arc(e[2], e[3], 240 * min(1, k * 4), 0, 6.29); ctx.fill()
            ctx.set_source_rgba(1, 0.5, 0.1, 0.8 * (1 - k))
            ctx.arc(e[2], e[3], 140 + 160 * k, 0, 6.29); ctx.fill()
            ctx.set_source_rgba(1, 0.85, 0.3, 1 - k)
            ctx.set_line_width(14 * (1 - k) + 2)
            ctx.arc(e[2], e[3], 80 + 260 * k, 0, 6.29); ctx.stroke()
            _particles(ctx, t, t0, e[2], e[3], (1, 0.6, 0.2), int(t0 * 1000), n=26, spd=700, life=0.8, size=9)
        elif kind == "ko" and dt < 1.1:
            x, y, col, seed, r = e[2], e[3], e[4], e[5], e[7]
            k = dt / 1.1
            if dt < 0.5:
                draw_sprite(ctx, e[6], "defeated", x, y, r * (1 + 0.5 * dt), alpha=1 - dt / 0.5)
            rng = random.Random(seed)
            for _ in range(16):
                a = rng.uniform(0, 6.28); v = rng.uniform(250, 650)
                px = x + math.cos(a) * v * dt; py = y + math.sin(a) * v * dt + 500 * dt * dt
                ctx.save(); ctx.translate(px, py); ctx.rotate(a + dt * 8)
                ctx.set_source_rgba(*col, 1 - k)
                s = rng.uniform(8, 16)
                ctx.move_to(-s, -s * 0.6); ctx.line_to(s, -s * 0.2); ctx.line_to(-s * 0.2, s); ctx.close_path()
                ctx.fill(); ctx.restore()
            ctx.set_source_rgba(1, 1, 1, max(0, 0.8 - 2 * k))
            ctx.set_line_width(10 * (1 - k))
            ctx.arc(x, y, r + 200 * k, 0, 6.29); ctx.stroke()
            if dt < 0.9:
                _outlined(ctx, "ELIMINATED", x, y - r - 30 - 40 * k, 34, (1, 0.3, 0.3), 1 - k, 6)
        elif kind == "num" and dt < 0.8:
            k = dt / 0.8
            _outlined(ctx, e[4], e[2] + 30, e[3] - 30 - 60 * k, 34 + 10 * (1 - k) ** 3, e[5], 1 - k ** 2, 5)
        elif kind == "heal" and dt < 0.8:
            b = balls[e[2]]
            rng = random.Random(int(t0 * 100))
            for _ in range(8):
                px = b["x"] + rng.uniform(-50, 50); py = b["y"] + 30 - 160 * dt * rng.uniform(0.6, 1.2)
                draw_icon(ctx, "heal", px, py, 10, 0)
        elif kind == "block" and dt < 0.3:
            b = balls[e[2]]
            ctx.set_source_rgba(0.6, 1, 1, 1 - dt / 0.3)
            ctx.set_line_width(8)
            ctx.arc(b["x"], b["y"], b["r"] + 20 + 60 * dt, 0, 6.29); ctx.stroke()
        elif kind == "label" and dt < 0.9:
            b = balls[e[2]]
            k = dt / 0.9
            pop = 1 + 0.4 * max(0, 1 - dt / 0.15)
            _outlined(ctx, e[3], b["x"], b["y"] - b["r"] - 60 - 40 * k, 38 * pop, e[4], 1 - k ** 3, 6)
    ctx.restore()

    _hud(ctx, fr, cfg, res)

    # countdown / announcements
    for e in res["eff_ann"]:
        dt = t - e[1]
        if e[0] == "count" and 0 <= dt < 0.7:
            k = dt / 0.7
            _outlined(ctx, e[2], ACX, ACY + 95, 260 * (1.4 - 0.4 * min(1, dt / 0.15)), (1, 1, 1), 1 - k ** 3, 14)
        elif e[0] == "ann" and 0 <= dt < 1.25:
            k = dt / 1.25
            pop = 1 + 0.5 * max(0, 1 - dt / 0.12)
            a = min(1, (1.25 - dt) / 0.25)
            _outlined(ctx, e[2], ACX, ACY + 35, 110 * pop, e[3], a, 14, max_w=1300)
    if t < T_START:
        _outlined(ctx, "PICK YOUR BALL!", ACX, ACY - 150, 64, fx.GOLD, 1, 12)
        _outlined(ctx, "comment your color", ACX, ACY + 175, 38, (1, 1, 1), 0.95, 7)

    # winner
    if fr["t_end"] is not None and t > fr["t_end"]:
        w = balls[fr["winner"]]
        k = min(1.0, (t - fr["t_end"]) / 0.6)
        ctx.set_source_rgba(0, 0, 0, 0.45 * k)
        ctx.rectangle(AX0, AY0, AX1 - AX0, AY1 - AY0); ctx.fill()
        bob = 8 * math.sin(t * 4)
        draw_sprite(ctx, w["name"], "victory", w["x"], w["y"] + bob, w["r"])
        _crown(ctx, w["x"], w["y"] - w["r"] - 40 + bob - 30 * (1 - k), 120)
        _confetti(ctx, t, fr["t_end"] + 0.3, cfg.seed)
        if t > fr["t_end"] + 0.5:
            kk = min(1.0, (t - fr["t_end"] - 0.5) / 0.3)
            pop = 1 + 0.3 * (1 - kk)
            _outlined(ctx, f"{w['name'].upper()} WINS!", ACX, AY0 + 150, 130 * pop, COLS[w["name"]], kk, 16, max_w=1300)
            _outlined(ctx, f"{w['kills']} KO" + ("" if w["kills"] == 1 else "s") + "  |  "
                      + f"{w['hp']:.0f} HP left", ACX, AY1 - 110, 46, (1, 1, 1), kk, 8)
            _outlined(ctx, "Did your ball win? Tell me in the comments!", ACX, AY1 - 45, 50, fx.GOLD, kk, 8)


def _confetti(ctx, t, t0, seed, n=140):
    dt = t - t0
    if dt < 0:
        return
    rng = random.Random(seed)
    for _ in range(n):
        x = rng.uniform(AX0, AX1)
        y = AY0 - 40 + rng.uniform(250, 600) * dt
        if y > AY1 + 40:
            continue
        ctx.save()
        ctx.translate(x + 40 * math.sin(dt * 3 + x), y)
        ctx.rotate(rng.uniform(0, 6.28) + dt * rng.uniform(-6, 6))
        ctx.set_source_rgb(*fx.hsv(rng.random(), 0.7, 1.0))
        ctx.rectangle(-9, -5, 18, 10)
        ctx.fill()
        ctx.restore()


def _hud(ctx, fr, cfg, res):
    t = fr["t"]
    balls = fr["balls"]
    # left panel: title + roster
    _outlined(ctx, "BALL BATTLE", 196, 52, 44, fx.WHITE, 1, 6)
    _outlined(ctx, "ROYALE", 196, 98, 44, fx.GOLD, 1, 6)
    n = len(balls)
    rh = min(118.0, (AY1 - AY0) / n)
    for i, b in enumerate(balls):
        cx, cy = 20, AY0 + i * rh
        col = COLS[b["name"]]
        win = fr["winner"] == i
        ctx.set_source_rgba(0.07, 0.07, 0.12, 0.95)
        rounded(ctx, cx, cy + 3, 352, rh - 8, 14); ctx.fill()
        ctx.set_source_rgba(*(fx.GOLD if win else col), 1.0 if win else 0.55)
        ctx.set_line_width(5 if win else 2.5)
        rounded(ctx, cx, cy + 3, 352, rh - 8, 14); ctx.stroke()
        fy = cy + rh / 2 - 1
        draw_sprite(ctx, b["name"], b["face"], cx + 46, fy, min(34, rh / 2 - 9),
                    alpha=1.0 if b["alive"] else 0.45)
        _face(ctx, 28, True)
        ctx.move_to(cx + 92, fy - 6)
        ctx.set_source_rgba(*col, 1.0 if b["alive"] else 0.5)
        ctx.show_text(b["name"].upper())
        ctx.new_path()
        bw = 236
        ctx.set_source_rgba(0, 0, 0, 0.8)
        rounded(ctx, cx + 90, fy + 8, bw + 4, 18, 5); ctx.fill()
        if b["alive"]:
            ctx.set_source_rgb(*_hp_col(b["hp"] / HPMAX))
            ctx.rectangle(cx + 92, fy + 10, bw * b["hp"] / HPMAX, 14); ctx.fill()
        if b["kills"]:
            _outlined(ctx, f"x{b['kills']} KO", cx + 300, fy - 6, 24, fx.GOLD, 1, 5)
        if not b["alive"]:
            ctx.set_source_rgba(1, 0.25, 0.25, 0.9)
            ctx.set_line_width(7)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.move_to(cx + 22, fy - 24); ctx.line_to(cx + 70, fy + 24)
            ctx.move_to(cx + 70, fy - 24); ctx.line_to(cx + 22, fy + 24); ctx.stroke()
            _outlined(ctx, "OUT", cx + 300, fy + 24, 22, (1, 0.35, 0.3), 1, 4)
        if win:
            _crown(ctx, cx + 46, fy - 34, 34)
    # top bar over the arena
    alive = fr["alive"]
    _face(ctx, 44, True)
    ctx.move_to(AX0 + 8, 76)
    ctx.set_source_rgb(1, 1, 1)
    ctx.show_text(f"ALIVE {alive}/{n}")
    ctx.new_path()
    el = max(0.0, min(t, fr["t_end"] or t) - T_START)
    s = f"{int(el // 60)}:{int(el % 60):02d}"
    ext = ctx.text_extents(s)
    ctx.move_to(AX1 - 8 - ext.width, 76)
    ctx.show_text(s)
    ctx.new_path()
    tl = cfg.t_close - t
    if 0 < tl <= 10 and fr["t_end"] is None:
        text(ctx, f"WALLS CLOSE IN {math.ceil(tl)}", ACX, 76, 42, (1, 0.35, 0.3), 0.6 + 0.4 * (int(t * 4) % 2))
    elif fr["sudden"] and fr["t_end"] is None:
        text(ctx, "SUDDEN DEATH", ACX, 76, 42, (1, 0.35, 0.3))
    elif tl <= 0 and fr["t_end"] is None:
        text(ctx, "WALLS CLOSING", ACX, 76, 42, (1, 0.85, 0.3))
    elif fr["t_end"] is None:
        text(ctx, "LAST BALL STANDING WINS", ACX, 76, 34, (0.75, 0.8, 1.0), 0.85)
    # kill feed (newest at the top)
    feed = [f for f in res["feed"] if f[0] <= t and t - f[0] < 9][-3:]
    if fr["t_end"] is not None and t > fr["t_end"] + 0.4:
        feed = []
    for j, (ft, killer, kind, victim) in enumerate(reversed(feed)):
        y = AY0 + 54 + j * 46
        a = min(1.0, (t - ft) / 0.2, (9 - (t - ft)) / 0.5)
        _face(ctx, 28, True)
        parts = []
        if killer:
            parts.append((killer.upper(), COLS[killer]))
        wk = ctx.text_extents(parts[0][0]).x_advance if parts else 0
        wv = ctx.text_extents(victim.upper()).x_advance
        total = wk + 70 + wv
        x = AX1 - 28 - total
        ctx.set_source_rgba(0, 0, 0, 0.6 * a)
        rounded(ctx, x - 14, y - 30, total + 28, 40, 10); ctx.fill()
        if parts:
            ctx.move_to(x, y); ctx.set_source_rgba(*parts[0][1], a); ctx.show_text(parts[0][0]); ctx.new_path()
        ctx.push_group()
        draw_icon(ctx, kind, x + wk + 35, y - 11, 17)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(a)
        ctx.move_to(x + wk + 70, y)
        ctx.set_source_rgba(*COLS[victim], a * 0.8)
        ctx.show_text(victim.upper())
        ctx.new_path()
        ctx.set_source_rgba(1, 0.3, 0.3, a)
        ctx.set_line_width(4)
        ctx.move_to(x + wk + 68, y - 11); ctx.line_to(x + wk + 72 + wv, y - 11); ctx.stroke()


# ===================================================================== render
def _split_effects(res):
    ann, shake, world = [], [], []
    for e in res["effects"]:
        if e[0] in ("ann", "count"):
            ann.append(e)
        elif e[0] == "shake":
            shake.append(e)
        else:
            world.append(e)
    res["eff_ann"], res["eff_shake"] = ann, shake
    res["eff_world"] = sorted(world, key=lambda e: e[1])


def _world_window(res, t):
    return [e for e in res["eff_world"] if 0 <= t - e[1] < 1.2]


def render_video(cfg, base):
    """Simulate, then render <base>.mp4 + <base>_cover.png. Returns (res, duration)."""
    res = simulate(cfg, record=True)
    _split_effects(res)
    frames = res["frames"]
    total = len(frames) / FPS
    wav = base + ".wav"
    te = res["t_end"] or total
    duel = res["kill_times"][-2] if len(res["kill_times"]) >= 2 else te
    sections = [(0, T_START, 0), (T_START, cfg.t_close, 2), (cfg.t_close, duel, 3), (duel, te, 3),
                (te, total + 5, 1)]
    royale_audio.mix(total, res["sounds"], sections, wav, cfg.seed)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    tmp_v = base + ".video.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", tmp_v], stdin=subprocess.PIPE)
    world = res["eff_world"]
    lo = 0
    for fr in frames:
        t = fr["t"]
        while lo < len(world) and t - world[lo][1] > 1.2:
            lo += 1
        hi = lo
        while hi < len(world) and world[hi][1] <= t:
            hi += 1
        view = dict(res, eff_world=world[lo:hi])
        draw(ctx, fr, cfg, view)
        surf.flush()
        ff.stdin.write(bytes(surf.get_data()))
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg video encode failed")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_v, "-i", wav, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", base + ".mp4"],
                   check=True)
    os.remove(tmp_v)
    os.remove(wav)
    save_cover(cfg, res, base + "_cover.png")
    save_thumbnail(cfg, base + "_thumb.jpg")
    return res, round(total, 2)


def cover_frame(res):
    """A busy mid-fight moment: most balls still alive and weapons out."""
    frames = res["frames"]
    best, bi = -1, len(frames) // 4
    for i in range(int(len(frames) * 0.12), int(len(frames) * 0.4), 15):
        fr = frames[i]
        sc = fr["alive"] * 2 + sum(1 for b in fr["balls"] if b["w"]) * 3 + len(fr["bolts"])
        if sc > best:
            best, bi = sc, i
    return frames[bi]


def save_cover(cfg, res, path):
    fr = cover_frame(res)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    view = dict(res, eff_world=_world_window(res, fr["t"]))
    draw(cairo.Context(surf), fr, cfg, view)
    surf.write_to_png(path)


THUMB_LINES = ["WHO SURVIVES?", "ONLY 1 WINS!", "PICK ONE!", "LAST ONE WINS"]


def save_thumbnail(cfg, path):
    """1280x720 YouTube thumbnail: big angry/scared faces, weapons, bold question. Never shows the winner."""
    TW, TH = 1280, 720
    rng = random.Random(cfg.seed * 5 + 1)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, TW, TH)
    c = cairo.Context(surf)
    g = cairo.RadialGradient(TW / 2, TH * 0.6, 50, TW / 2, TH * 0.6, 800)
    g.add_color_stop_rgb(0, 0.16, 0.08, 0.3)
    g.add_color_stop_rgb(1, 0.02, 0.02, 0.06)
    c.set_source(g); c.paint()
    c.set_source_rgba(0.4, 0.55, 1.0, 0.12); c.set_line_width(2)
    for x in range(0, TW, 64):
        c.move_to(x, 0); c.line_to(x, TH)
    for y in range(0, TH, 64):
        c.move_to(0, y); c.line_to(TW, y)
    c.stroke()
    # explosion glow behind the middle fighter
    for rr, al in ((330, 0.18), (230, 0.3), (140, 0.45)):
        c.set_source_rgba(1, 0.55, 0.15, al); c.arc(TW / 2, 470, rr, 0, 6.29); c.fill()
    names = cfg.names[:]
    rng.shuffle(names)
    spots = [(130, 520, 98, "scared", None), (1150, 520, 98, "crying", None),
             (365, 480, 112, "angry", "sword"), (915, 480, 112, "angry", "hammer"),
             (640, 455, 150, "determined", None)]
    for (x, y, r, emo, wpn), nm in zip(spots, names):
        c.set_source_rgba(0, 0, 0, 0.45)
        c.arc(x + 6, y + 10, r, 0, 6.29); c.fill()
        draw_sprite(c, nm, emo, x, y, r)
    for (x, y, r, emo, wpn) in spots:
        if wpn:                    # weapon raised above the fighter, pointing at the middle
            draw_icon(c, wpn, x + (60 if x < TW / 2 else -60), y - r - 30, 62, rot=0.5 if x < TW / 2 else -0.5)
    draw_icon(c, "bomb", 505, 655, 40, rot=-0.3)
    draw_icon(c, "laser", 790, 660, 46, rot=0.2)
    line = rng.choice(THUMB_LINES)
    _outlined(c, line, TW / 2, 150, 128, fx.GOLD, 1, 22, max_w=1220)
    badge = f"{len(cfg.names)} BALLS  vs  1 WINNER"
    _face(c, 46, True)
    bw = c.text_extents(badge).width + 50
    c.set_source_rgb(0.85, 0.12, 0.15)
    rounded(c, TW / 2 - bw / 2, 190, bw, 66, 14); c.fill()
    text(c, badge, TW / 2, 238, 46, (1, 1, 1))
    tmp = path + ".png"
    surf.write_to_png(tmp)
    Image.open(tmp).convert("RGB").save(path, "JPEG", quality=90)
    os.remove(tmp)


def audio_events(res, cfg):          # not used (render_video makes its own audio)
    return []


def metadata_facts(res, cfg):
    return dict(template="royale", n_balls=res["n"], colors=[n.upper() for n in cfg.names[:4]
                                                             if n.upper() in ("RED", "BLUE", "GREEN", "YELLOW",
                                                                              "PURPLE", "ORANGE", "PINK", "CYAN")],
                winner=res["winner"], t_end=round(res["t_end"], 1), names=cfg.names,
                melody="original battle track")
