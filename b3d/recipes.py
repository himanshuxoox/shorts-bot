"""
3D Short recipes: a structure + an action + ONE variable that changes over 3 variants.
The agent (b3d/agent.py) invents recipes as plain JSON; this module builds them in Blender.

    recipe = dict(id, action, structure, variable, values, labels, hitter, palette, backdrop,
                  yaw, elev, k)       # k = calibration knob found by the agent's physics test

actions:    wrecking (ball on a rope), drop (ball falls from above), blast, wind, spin (turntable),
            quake (shake table)
structures: wall, pyramid, tower (round), cube (8x8x8 small cubes), columns (5 thin towers)
"""
import colorsys
import math
import random

from mathutils import Vector

from b3d import kit
from b3d.kit import bpy

FPS = 30

# ------------------------------------------------------------------ the space the agent picks from
ACTIONS = {
    #          variable -> (values, label format)
    "wrecking": {"mass": ([1, 50, 1000], "{:,} kg"), "size": ([0.2, 0.45, 0.85], None)},
    "drop": {"height": ([1, 5, 25], "{} m"), "mass": ([1, 50, 1000], "{:,} kg"),
             "gravity": ([1.62, 9.81, 24.8], None)},
    "blast": {"power": ([1, 10, 100], "Power {}")},
    "wind": {"speed": ([20, 80, 300], "{} km/h")},
    "spin": {"rpm": ([10, 60, 200], "{} RPM")},
    "quake": {"magnitude": ([3, 6, 9], "Magnitude {}")},
}
STRUCTURES = ["wall", "pyramid", "tower", "cube", "columns"]
NOUN = {"wall": "WALL", "pyramid": "PYRAMID", "tower": "TOWER", "cube": "CUBE", "columns": "TOWERS"}
SPIN_OK = {"pyramid", "tower", "cube", "columns"}           # fit on a turntable
PALETTES = ["rainbow", "candy", "sunset", "ocean", "mono", "checker", "mint", "berry"]
HITTERS = ["steel", "gold", "copper", "red", "black"]
BACKDROPS = ["orange", "pink", "lavender", "steel", "mint", "sand", "peach", "sky", "sage", "lilac", "coral"]
FRAMES = {"wrecking": 165, "drop": 180, "blast": 165, "wind": 180, "spin": 180, "quake": 180}
SIZE_LABELS = ["Small ball", "Medium ball", "HUGE ball"]
PLANETS = ["Moon", "Earth", "Jupiter"]


def labels_for(action, variable, values):
    if variable == "size":
        return SIZE_LABELS[:]
    if variable == "gravity":
        return [f"{p} gravity" for p in PLANETS]
    fmt = ACTIONS[action][variable][1]
    return [fmt.format(v) for v in values]


def hook_for(r):
    n = NOUN[r["structure"]]
    a, v = r["action"], r["variable"]
    return {
        ("wrecking", "mass"): f"Which one breaks the {n}?",
        ("wrecking", "size"): f"Which ball breaks the {n}?",
        ("drop", "height"): f"From how high does it SMASH the {n}?",
        ("drop", "mass"): f"How HEAVY to smash the {n}?",
        ("drop", "gravity"): "The same crash on 3 PLANETS",
        ("blast", "power"): f"How much POWER to blow up the {n}?",
        ("wind", "speed"): f"How much WIND to knock down the {n}?",
        ("spin", "rpm"): f"How FAST until the {n} flies apart?",
        ("quake", "magnitude"): f"Which EARTHQUAKE knocks down the {n}?",
    }[(a, v)]


# ------------------------------------------------------------------ colours
def palette_mats(name, n, rng):
    """n plastic materials for layers 0..n-1"""
    if name == "rainbow":
        cols = [kit.rainbow(i, n, 0.8, 0.93, rng.random()) for i in range(n)]
    elif name == "candy":
        base = [(1.0, 0.55, 0.72), (0.55, 0.95, 0.8), (1.0, 0.93, 0.5), (0.7, 0.7, 1.0)]
        cols = [base[i % 4] for i in range(n)]
    elif name == "sunset":
        cols = [colorsys.hsv_to_rgb(0.08 - 0.25 * i / max(1, n - 1), 0.85, 0.98) for i in range(n)]
        cols = [(r_, g_, b_) for r_, g_, b_ in cols]
    elif name == "ocean":
        cols = [colorsys.hsv_to_rgb(0.47 + 0.18 * i / max(1, n - 1), 0.75, 0.95 - 0.3 * i / max(1, n - 1))
                for i in range(n)]
    elif name == "mono":
        h = rng.random()
        cols = [colorsys.hsv_to_rgb(h, 0.35 + 0.55 * i / max(1, n - 1), 0.98 - 0.25 * i / max(1, n - 1))
                for i in range(n)]
    elif name == "checker":
        h = rng.random()
        a_, b_ = colorsys.hsv_to_rgb(h, 0.8, 0.95), colorsys.hsv_to_rgb((h + 0.5) % 1, 0.15, 0.97)
        cols = [a_ if i % 2 == 0 else b_ for i in range(n)]
    elif name == "mint":
        cols = [colorsys.hsv_to_rgb(0.42 + 0.1 * math.sin(i), 0.45 + 0.3 * (i % 2), 0.95) for i in range(n)]
    else:                                                     # berry
        cols = [colorsys.hsv_to_rgb(0.85 + 0.12 * i / max(1, n - 1), 0.75, 0.9) for i in range(n)]
    return [kit.mat_plastic(c, rough=0.3) for c in cols]


def hitter_mat(name):
    return {"steel": lambda: kit.mat_metal((0.8, 0.8, 0.84), 0.14),
            "gold": lambda: kit.mat_metal((1.0, 0.76, 0.33), 0.18),
            "copper": lambda: kit.mat_metal((0.95, 0.55, 0.38), 0.2),
            "red": lambda: kit.mat_plastic((0.85, 0.06, 0.08), 0.15, 1.0),
            "black": lambda: kit.mat_plastic((0.03, 0.03, 0.035), 0.25, 1.0)}[name]()


# ------------------------------------------------------------------ structures
def _place(proto, positions, mats, layer_of, mass, rot=None):
    out = []
    for i, p in enumerate(positions):
        o = kit.duplicate(proto, p, mat=mats[layer_of[i] % len(mats)])
        if rot is not None:
            o.rotation_euler = rot[i]
        kit.rigid(o, mass=mass, friction=0.55, bounce=0.15, shape="BOX")
        out.append(o)
    bpy.data.objects.remove(proto)
    return out


def structure(name, z0, mass, pal, rng):
    """build on top of height z0; returns (blocks, bbox_min, bbox_max)"""
    pos, layer, rot = [], [], None
    if name == "wall":
        bw, bh, bd = 0.5, 0.25, 0.25
        proto = kit.box((0, 0, -50), (bw - 0.008, bd, bh - 0.008), bevel=0.012)
        rows = 8
        for r in range(rows):
            n = 10 if r % 2 == 0 else 9
            for c in range(n):
                pos.append(((c - (n - 1) / 2) * bw, 0, z0 + bh / 2 + r * bh))
                layer.append(r)
        nl = rows
    elif name == "pyramid":
        s = 0.34
        proto = kit.box((0, 0, -50), (s - 0.01,) * 3, bevel=0.014)
        nl = 7
        for L in range(nl):
            n = nl - L
            for i in range(n):
                for j in range(n):
                    pos.append(((i - (n - 1) / 2) * s, (j - (n - 1) / 2) * s, z0 + s / 2 + L * s))
                    layer.append(L)
    elif name == "tower":
        proto = kit.box((0, 0, -50), (0.62, 0.2, 0.2), bevel=0.012)
        nl = 14
        rot = []
        for L in range(nl):
            for i in range(10):
                a = (i + 0.5 * (L % 2)) / 10 * 2 * math.pi
                pos.append((1.05 * math.cos(a), 1.05 * math.sin(a), z0 + 0.1 + L * 0.2))
                rot.append((0, 0, a + math.pi / 2))
                layer.append(L)
    elif name == "cube":
        s = 0.22
        proto = kit.box((0, 0, -50), (s - 0.008,) * 3, bevel=0.01)
        nl = 8
        for L in range(nl):
            for i in range(8):
                for j in range(8):
                    pos.append(((i - 3.5) * s, (j - 3.5) * s, z0 + s / 2 + L * s))
                    layer.append(L)
    else:                                                     # columns: 5 thin towers
        s = 0.3
        proto = kit.box((0, 0, -50), (s - 0.01,) * 3, bevel=0.012)
        nl = 11
        hs = [7, 10, 11, 9, 6]
        for c, hgt in enumerate(hs):
            for L in range(hgt):
                pos.append(((c - 2) * 0.62, 0, z0 + s / 2 + L * s))
                layer.append(L)
    mats = palette_mats(pal, nl, rng)
    blocks = _place(proto, pos, mats, layer, mass, rot)
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    zs = [p[2] for p in pos]
    m = 0.35
    return blocks, Vector((min(xs) - m, min(ys) - m, z0)), Vector((max(xs) + m, max(ys) + m, max(zs) + m))


def _corners(lo, hi):
    return [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


# ------------------------------------------------------------------ build
def build(r, v):
    """build variant v of recipe r in an empty scene -> dict(frames, label, hook, pre, impacts)"""
    rng = random.Random(r["id"] * 7 + 1)
    action, var = r["action"], r["variable"]
    val = r["values"][v]
    k = r.get("k", 1.0)
    frames = FRAMES[action] + (15 if (action == "drop" and var == "gravity") else 0)
    kit.studio(r["backdrop"], light=1.15 if r["backdrop"] in ("steel", "sky") else 1.0)
    g = -val if var == "gravity" else -9.81
    kit.physics(gravity=g, frames=frames, substeps=20, iterations=25)
    block_mass = 2.0 * k
    z0 = 0.0
    platform = None
    if action in ("spin", "quake"):
        z0 = 0.3
        if action == "spin":
            platform = kit.cylinder((0, 0, 0.15), 2.4, 0.3, mat=kit.mat_plastic((0.13, 0.13, 0.15), 0.4, 0.6),
                                    name="table", verts=72)
            kit.kinematic(platform, friction=0.9, shape="CYLINDER")
        else:
            platform = kit.box((0, 0, 0.15), (5.2, 3.2, 0.3), mat=kit.mat_wood((0.6, 0.38, 0.2)), name="table",
                               bevel=0.02)
            kit.kinematic(platform, friction=0.9, shape="BOX")
    blocks, lo, hi = structure(r["structure"], z0, block_mass, r["palette"], rng)
    H = hi.z
    pts = _corners(lo, hi)
    impacts = [kit.Impacts(blocks, "clack", 1.0)]
    pre = hook = None
    hm = hitter_mat(r["hitter"]) if action in ("wrecking", "drop") else None

    if action == "wrecking":
        rad = val if var == "size" else 0.6
        mass = (val if var == "mass" else 6000 * rad ** 3) * 1.0
        front = lo.y + 0.35                              # front face of the structure
        zc = min(1.1, 0.42 * H) + 0.05
        L = 4.2
        piv = Vector((0, front - rad + 0.08, zc + L))
        a0 = math.radians(84)
        ball = kit.ball(piv + Vector((0, -L * math.sin(a0), -L * math.cos(a0))), rad, hm, "ball", seg=48)
        kit.rigid(ball, mass=mass, friction=0.4, bounce=0.1, shape="SPHERE", damp=(0.0, 0.05))
        hk = kit.box(piv, (0.2, 0.2, 0.2), mat=None, name="pivot")
        hk.hide_render = True
        kit.rigid(hk, "PASSIVE")
        hk.rigid_body.collision_collections[0] = False
        hk.rigid_body.collision_collections[19] = True
        kit.constraint(hk, ball, "POINT", loc=piv)
        rope = kit.cylinder((0, 0, 0), 0.025, 1.0, mat=kit.mat_metal((0.15, 0.15, 0.16), 0.5), name="rope", verts=12)

        def hook(f):
            p = ball.matrix_world.translation
            d = p - piv
            rope.location = (piv + p) / 2
            rope.scale = (1, 1, d.length)
            rope.rotation_euler = d.to_track_quat("Z", "Y").to_euler()

        hook(1)
        pts += [ball.location.copy() + Vector((0, -rad, 0)), Vector((0, front - rad, zc - rad))]
        impacts.append(kit.Impacts([ball], "thud", 0.6, 1.5))
    elif action == "drop":
        h = val if var == "height" else 5.0
        mass = val if var == "mass" else 40.0
        rad = 0.55
        top = H + rad + h
        bx = 1.05 if r["structure"] == "tower" else 0.12     # the round tower is hollow: hit its wall
        ball = kit.ball((bx, -0.08, top), rad, hm, "ball", seg=48)
        kit.rigid(ball, mass=mass, friction=0.4, bounce=0.15, shape="SPHERE")
        pts += [Vector((0, 0, H + 1.3))]                  # the ball enters from the top of the frame
        impacts.append(kit.Impacts([ball], "thud", 0.6, 1.5))
    elif action == "blast":
        bpy.ops.object.effector_add(type="FORCE", location=(0, 0, z0 - 0.25))
        ff = bpy.context.object
        ff.field.shape = "POINT"
        ff.field.falloff_type = "SPHERE"
        ff.field.use_max_distance = True
        ff.field.distance_max = 3.2
        flash = kit.ball((0, 0, z0 + 0.05), 0.4, None, "flash", seg=32)
        m, b = kit._principled("flash")
        b.inputs["Emission Color"].default_value = (1.0, 0.55, 0.15, 1)
        flash.data.materials.append(m)
        T0 = 1.0
        strength = 400.0 * (val / 100) ** 0.5                 # the knob k only changes the block weight

        def pre(f):
            t = f / FPS
            ff.field.strength = strength if T0 <= t < T0 + 0.12 else 0.0
            gl = max(0.0, 1 - abs(t - T0 - 0.05) / 0.25)
            b.inputs["Emission Strength"].default_value = 60.0 * gl * (0.3 + 0.7 * val / 100)
            flash.scale = [0.2 + 2.5 * gl * (0.3 + 0.7 * val / 100)] * 3
    elif action == "wind":
        bpy.ops.object.effector_add(type="WIND", location=(-6, 0, 1))
        wf = bpy.context.object
        wf.rotation_euler = (0, math.radians(90), 0)
        target = 60.0 * (val / 300) ** 2

        def pre(f):
            t = f / FPS
            wf.field.strength = target * min(1.0, max(0.0, (t - 0.6) / 1.2))
            wf.field.noise = 0.4
    elif action == "spin":
        w_max = val * k / 60 * 2 * math.pi
        state = {"a": 0.0}

        def pre(f):
            t = f / FPS
            state["a"] += w_max * min(1.0, max(0.0, (t - 0.5) / 1.5)) / FPS
            platform.rotation_euler = (0, 0, state["a"])

        pts += _corners(Vector((-2.4, -2.4, 0)), Vector((2.4, 2.4, 0.3)))
    else:                                                     # quake
        mag = val
        amp = 0.30 * (mag / 9) ** (3.0 / k)                     # k=1: 3 -> 1 cm, 6 -> 9 cm, 9 -> 30 cm
        freq = 2.2 + 0.25 * mag

        def pre(f):
            t = f / FPS
            env = min(1.0, max(0.0, (t - 0.6) / 0.8)) * (1.0 if t < 4.6 else max(0.0, 1 - (t - 4.6) / 0.6))
            platform.location = (amp * env * math.sin(2 * math.pi * freq * t),
                                 0.4 * amp * env * math.sin(2 * math.pi * freq * 1.37 * t + 1.0), 0.15)

        pts += _corners(Vector((-2.6, -1.6, 0)), Vector((2.6, 1.6, 0.3)))
    kit.camera_fit(pts, yaw_deg=r["yaw"], elev_deg=r["elev"], lens=32, dof=9)
    return dict(frames=frames, label=r["labels"][v], hook=hook, pre=pre, impacts=impacts, platform=platform)


START_K = {"wrecking": 1.0, "drop": 1.0, "blast": 0.15, "wind": 0.03, "spin": 1.0, "quake": 1.0}


def disturbance(blocks_start, platform=None, platform_start=None):
    """fraction of blocks moved more than 0.25 m (the agent's 'did something happen' meter);
    on a turntable / shake table it is measured in the table's frame (riding along is not moving)"""
    moved = 0
    if platform is not None:
        now_inv = platform.matrix_world.inverted()
        start_inv = platform_start.inverted()
    for o, p in blocks_start:
        q = o.matrix_world.translation
        if platform is not None:
            d = (now_inv @ q) - (start_inv @ p)
        else:
            d = q - p
        if d.length > 0.25:
            moved += 1
    return moved / max(1, len(blocks_start))
