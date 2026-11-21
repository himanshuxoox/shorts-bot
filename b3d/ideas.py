"""
The 3D ideas. Each one is ONE setup where ONE number changes between variants (like the popular
"3DCG physics" compilations), shown one after another with the number big on screen.

IDEAS[name] = dict(title, labels, build) — build(variant) builds the scene in an empty Blender file
and returns dict(frames, label, impacts=[kit.Impacts], hook=f(frame) after the physics step,
pre=f(frame) before it, for objects moved by code).
"""
import math
import random

from mathutils import Vector

from b3d import kit
from b3d.kit import bpy

FPS = 30
SAT, VAL = 0.82, 0.92
BRICK_KG = 2.0           # wrecking: heavy enough that the 1 kg ball bounces off
BRIDGE_K = 0.4           # breaking impulse per "strength" point (calibrated: 500 holds, 50 cracks, 5 shatters)
WIND_K = 60.0            # wind field strength at 300 km/h (force grows with speed squared)


def _cols(n, h0=0.0, s=SAT, v=VAL):
    return [kit.mat_plastic(kit.rainbow(i, n, s, v, h0)) for i in range(n)]


def _stairs(n, w, step_d, step_h, x0=0.0, y0=0.0, mat=None):
    """step i at y0 + i * step_d, the highest one at the back (largest y)"""
    out = []
    for i in range(n):
        h = step_h * (i + 1)
        o = kit.box((x0, y0 + i * step_d, h / 2), (w, step_d, h), mat=mat, bevel=0.01)
        kit.rigid(o, "PASSIVE", friction=0.5, bounce=0.3, shape="BOX")
        out.append(o)
    return out


# ------------------------------------------------------------------ VIDEO 1
def wrecking(v):
    """wrecking ball vs a rainbow brick wall: 1 kg / 50 kg / 1,000 kg"""
    m = [1, 50, 1000][v]
    kit.studio("orange")
    kit.physics(frames=165, substeps=25, iterations=30)
    bw, bh, bd = 0.5, 0.25, 0.25
    cols, rows = 10, 8
    proto = kit.box((0, 0, -50), (bw - 0.008, bd, bh - 0.008), bevel=0.012)
    mats = _cols(rows, 0.0)
    bricks = []
    for r in range(rows):
        n = cols if r % 2 == 0 else cols - 1
        for c in range(n):
            o = kit.duplicate(proto, ((c - (n - 1) / 2) * bw, 0, bh / 2 + r * bh), mat=mats[r])
            kit.rigid(o, mass=BRICK_KG, friction=0.5, bounce=0.2, shape="BOX")
            bricks.append(o)
    bpy.data.objects.remove(proto)
    L = 4.2
    piv = Vector((0, -0.85, 5.3))
    a0 = math.radians(88)
    ball = kit.ball(piv + Vector((0, -L * math.sin(a0), -L * math.cos(a0))), 0.62,
                    kit.mat_metal((0.78, 0.78, 0.82), 0.15), "ball", seg=48)
    kit.rigid(ball, mass=m, friction=0.4, bounce=0.1, shape="SPHERE", damp=(0.0, 0.05))
    hk = kit.box(piv, (0.3, 0.3, 0.3), mat=None, name="pivot")
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
    kit.camera((-6.4, -8.4, 3.3), (0, -0.9, 2.0), lens=30, dof=8)
    return dict(frames=165, label=f"{m:,} kg", hook=hook,
                impacts=[kit.Impacts(bricks, "clack", 1.0), kit.Impacts([ball], "thud", 0.6, 1.5)])


def gravity(v):
    """the same crash on the Moon, on Earth and on Jupiter"""
    name, g = [("Moon", 1.62), ("Earth", 9.81), ("Jupiter", 24.8)][v]
    kit.studio("steel", light=1.2)
    kit.physics(gravity=-g, frames=180)
    s = 0.36
    mats = _cols(7, 0.55)
    cubes = []
    proto = kit.box((0, 0, -50), (s - 0.01, s - 0.01, s - 0.01), bevel=0.015)
    for layer in range(7):
        n = 7 - layer
        for i in range(n):
            for j in range(n):
                p = ((i - (n - 1) / 2) * s, (j - (n - 1) / 2) * s, s / 2 + layer * s)
                o = kit.duplicate(proto, p, mat=mats[layer])
                kit.rigid(o, mass=0.4, friction=0.55, bounce=0.2, shape="BOX")
                cubes.append(o)
    bpy.data.objects.remove(proto)
    ball = kit.ball((0.25, -0.15, 7.5), 0.5, kit.mat_metal((0.9, 0.75, 0.35), 0.18), "ball", seg=48)
    kit.rigid(ball, mass=30, friction=0.4, bounce=0.2, shape="SPHERE")
    kit.camera((0, -10.5, 3.6), (0, 0, 1.6), lens=38, dof=8)
    return dict(frames=180, label=f"{name} gravity", impacts=[kit.Impacts(cubes, "clack", 1.0),
                                                              kit.Impacts([ball], "thud", 0.6, 1.0)])


def bounce(v):
    """120 balls poured down a staircase: bounciness 0% / 50% / 95%"""
    b = [0.0, 0.5, 0.95][v]
    kit.studio("pink")
    kit.physics(frames=180)
    rng = random.Random(5)
    steps = _stairs(8, 3.2, 0.55, 0.38, y0=-2.2, mat=kit.mat_wood((0.62, 0.38, 0.2)))
    for o in steps:
        o.rigid_body.restitution = b
    balls = []
    mats = _cols(12, 0.9)
    proto = kit.ball((0, 0, -50), 0.13, seg=24)
    for i in range(120):
        p = (rng.uniform(-1.3, 1.3), 1.65 + rng.uniform(-0.2, 0.2), 3.4 + rng.uniform(0, 2.4))
        o = kit.duplicate(proto, p, mat=mats[i % 12])
        kit.rigid(o, mass=0.1, friction=0.4, bounce=b, shape="SPHERE", damp=(0.02, 0.1))
        balls.append(o)
    bpy.data.objects.remove(proto)
    kit.camera((5.6, -9.0, 4.2), (0, -0.6, 1.3), lens=34, dof=9)
    return dict(frames=180, label=f"Bounciness {int(b * 100)}%",
                impacts=[kit.Impacts(balls, "tick", 0.8, 1.0)])


def spikes(v):
    """a jelly cube falls on a bed of nails: 1 spike / 9 spikes / 100 spikes"""
    n = [1, 9, 100][v]
    kit.studio("mint")
    frames = 165
    kit.physics(frames=frames)
    base = kit.box((0, 0, 0.1), (2.4, 2.4, 0.2), mat=kit.mat_wood((0.5, 0.3, 0.16)), bevel=0.02)
    kit.collider(base)
    k = int(round(math.sqrt(n)))
    pitch = 2.0 / max(1, k)
    metal = kit.mat_metal((0.85, 0.85, 0.88), 0.2)
    for i in range(k):
        for j in range(k):
            x = (i - (k - 1) / 2) * pitch
            y = (j - (k - 1) / 2) * pitch
            c = kit.cone((x, y, 0.2 + 0.55), 0.05 if n > 9 else 0.08, 1.1, metal, verts=16)
            kit.collider(c, thickness=0.001)
    jelly = kit.subdivided_cube((0, 0, 3.0), (1.2, 1.2, 1.2), level=7,
                                mat=kit.mat_jelly((0.95, 0.18, 0.35)), name="jelly")
    cast = jelly.modifiers.new("round", "CAST")           # round the corners like a gummy
    cast.factor = 0.35
    bpy.context.view_layer.objects.active = jelly
    bpy.ops.object.modifier_apply(modifier="round")
    jelly.rotation_euler = (0.05, 0.08, 0.3)
    kit.cloth(jelly, mass=0.4, tension=3, bending=0.2, pressure=2.0, quality=8, frames=frames,
              self_collision=False)
    kit.camera((4.8, -6.8, 3.4), (0, 0, 0.9), lens=42, dof=6)
    return dict(frames=frames, label=f"{n} spike{'s' if n > 1 else ''}", impacts=[kit.Impacts([jelly], "squish", 0.7, 1.0)])


def spin(v):
    """a tower of blocks on a turntable: 10 / 60 / 200 RPM"""
    rpm = [10, 60, 200][v]
    kit.studio("lavender")
    frames = 180
    kit.physics(frames=frames, substeps=20)
    table = kit.cylinder((0, 0, 0.15), 2.3, 0.3, mat=kit.mat_plastic((0.15, 0.15, 0.18), 0.4, 0.6), name="table", verts=64)
    kit.kinematic(table, friction=0.9, shape="CYLINDER")
    mats = _cols(8, 0.7)
    blocks = []
    proto = kit.box((0, 0, -50), (0.62, 0.2, 0.2), bevel=0.012)
    for layer in range(12):                          # a round tower: rings of blocks, alternating
        r = 1.1
        nb = 10
        for i in range(nb):
            a = (i + 0.5 * (layer % 2)) / nb * 2 * math.pi
            o = kit.duplicate(proto, (r * math.cos(a), r * math.sin(a), 0.3 + 0.1 + layer * 0.2),
                              mat=mats[layer % 8])
            o.rotation_euler = (0, 0, a + math.pi / 2)
            kit.rigid(o, mass=0.3, friction=0.7, bounce=0.1, shape="BOX")
            blocks.append(o)
    bpy.data.objects.remove(proto)
    w_max = rpm / 60 * 2 * math.pi
    state = {"ang": 0.0}

    def pre(f):
        t = f / FPS
        w = w_max * min(1.0, max(0.0, (t - 0.5) / 1.5))      # spin up over 1.5 s
        state["ang"] += w / FPS
        table.rotation_euler = (0, 0, state["ang"])

    kit.camera((0, -9.5, 5.2), (0, 0, 1.1), lens=38, dof=9)
    return dict(frames=frames, label=f"{rpm} RPM", pre=pre, impacts=[kit.Impacts(blocks, "clack", 0.9)])


def plinko(v):
    """3D plinko: 10 / 100 / 500 balls fall through 120 pegs into bins"""
    n = [10, 100, 500][v]
    kit.studio("sand")
    frames = 240 if n < 500 else 330
    kit.physics(frames=frames, substeps=12)
    rng = random.Random(3)
    D = 0.26                                          # slot depth (y)
    wood = kit.mat_wood((0.6, 0.4, 0.22))
    back = kit.box((0, D / 2 + 0.05, 2.6), (4.2, 0.1, 5.4), mat=wood)
    kit.rigid(back, "PASSIVE", friction=0.2, shape="BOX")
    for yy in (-D / 2 - 0.3, D / 2 + 0.35):           # invisible glass in front, hopper walls above
        g = kit.box((0, yy, 7.0), (4.2, 0.6, 14.0), mat=None)
        g.hide_render = True
        kit.rigid(g, "PASSIVE", friction=0.1, shape="BOX")
    for sx in (-1, 1):
        w = kit.box((sx * 2.05, 0, 2.6), (0.1, D + 0.2, 5.4), mat=wood)
        kit.rigid(w, "PASSIVE", friction=0.2, shape="BOX")
        hw = kit.box((sx * 2.3, 0, 10.0), (0.6, D + 1.0, 9.0), mat=None)
        hw.hide_render = True
        kit.rigid(hw, "PASSIVE", friction=0.1, shape="BOX")
    metal = kit.mat_metal((0.9, 0.9, 0.92), 0.2)
    rows = 12
    for r in range(rows):
        k = 13 if r % 2 == 0 else 12
        for c in range(k):
            x = (c - (k - 1) / 2) * 0.3
            p = kit.cylinder((x, 0, 4.4 - r * 0.25), 0.035, D + 0.1, metal, verts=12, rot=(math.pi / 2, 0, 0))
            kit.rigid(p, "PASSIVE", friction=0.1, bounce=0.4, shape="CYLINDER")
    for i in range(14):                                # bin walls
        x = -1.95 + i * 0.3
        b = kit.box((x, 0, 0.6), (0.03, D, 1.2), mat=metal)
        kit.rigid(b, "PASSIVE", friction=0.2, shape="BOX")
    for sx in (-1, 1):                                # funnel at the top
        f_ = kit.box((sx * 1.05, 0, 5.0), (1.9, D, 0.05), mat=metal)
        f_.rotation_euler = (0, -sx * math.radians(25), 0)
        kit.rigid(f_, "PASSIVE", friction=0.1, shape="BOX")
    r_b = 0.07
    mats = _cols(10, 0.05)
    proto = kit.ball((0, 0, -50), r_b, seg=20)
    balls = []
    for i in range(n):
        p = (rng.uniform(-1.6, 1.6), rng.uniform(-0.04, 0.04), 5.9 + i * (0.011 if n > 100 else 0.1) + rng.uniform(0, 0.1))
        o = kit.duplicate(proto, p, mat=mats[i % 10])
        kit.rigid(o, mass=0.05, friction=0.2, bounce=0.35, shape="SPHERE", damp=(0.02, 0.1))
        balls.append(o)
    bpy.data.objects.remove(proto)
    kit.camera((2.2, -9.6, 3.0), (0, 0, 2.7), lens=40, dof=10)
    return dict(frames=frames, label=f"{n:,} balls", impacts=[kit.Impacts(balls, "tick", 0.7, 1.2)])


def bridge(v):
    """a heavy ball rolls onto a plank bridge: strength 500 / 50 / 5"""
    s = [500, 50, 5][v]
    kit.studio("steel", light=1.15)
    frames = 180
    kit.physics(frames=frames, substeps=20, iterations=40)
    wood = kit.mat_wood((0.66, 0.42, 0.22))
    stone = kit.mat_plain((0.75, 0.74, 0.7), 0.6)
    H = 1.6
    for sx in (-1, 1):
        p = kit.box((sx * 2.6, 0, H / 2), (1.0, 1.4, H), mat=stone, bevel=0.03)
        kit.rigid(p, "PASSIVE", friction=0.6, shape="BOX")
    planks = []
    n = 14
    pw = 4.2 / n
    for i in range(n):
        x = -2.1 + pw / 2 + i * pw
        o = kit.box((x, 0, H - 0.05), (pw - 0.01, 1.1, 0.1), mat=wood, bevel=0.008)
        kit.rigid(o, mass=0.6, friction=0.7, bounce=0.1, shape="BOX")
        planks.append(o)
    anchors = []
    for sx, end in ((-1, planks[0]), (1, planks[-1])):
        a = kit.box((sx * 2.15, 0, H - 0.05), (0.1, 1.1, 0.1), mat=wood)
        kit.rigid(a, "PASSIVE", shape="BOX")
        anchors.append(a)
    th = s * BRIDGE_K
    kit.constraint(anchors[0], planks[0], "FIXED", breaking=th)
    for a_, b_ in zip(planks, planks[1:]):
        kit.constraint(a_, b_, "FIXED", breaking=th)
    kit.constraint(planks[-1], anchors[1], "FIXED", breaking=th)
    ball = kit.ball((0.35, 0, H + 4.2), 0.42, kit.mat_metal((0.3, 0.3, 0.33), 0.25), "ball", seg=48)
    kit.rigid(ball, mass=60, friction=0.5, bounce=0.05, shape="SPHERE", damp=(0.0, 0.02))
    kit.camera((0.8, -8.6, 3.0), (0, 0, 1.6), lens=34, dof=9)
    return dict(frames=frames, label=f"Strength {s}", impacts=[kit.Impacts(planks, "wood", 1.0),
                                                              kit.Impacts([ball], "thud", 0.5, 1.5)])


def wind(v):
    """wind vs a pyramid of light blocks: 20 / 80 / 300 km/h"""
    kmh = [20, 80, 300][v]
    kit.studio("sand")
    frames = 180
    kit.physics(frames=frames)
    s = 0.3
    mats = _cols(6, 0.12)
    blocks = []
    proto = kit.box((0, 0, -50), (s - 0.01, s - 0.01, s - 0.01), bevel=0.012)
    for layer in range(6):
        n = 6 - layer
        for i in range(n):
            for j in range(n):
                p = ((i - (n - 1) / 2) * s, (j - (n - 1) / 2) * s, s / 2 + layer * s)
                o = kit.duplicate(proto, p, mat=mats[layer])
                kit.rigid(o, mass=0.05, friction=0.5, bounce=0.2, shape="BOX")
                blocks.append(o)
    bpy.data.objects.remove(proto)
    bpy.ops.object.effector_add(type="WIND", location=(-5, 0, 1))
    wf = bpy.context.object
    wf.rotation_euler = (0, math.radians(90), 0)
    target = WIND_K * (kmh / 300) ** 2

    def pre(f):
        t = f / FPS
        wf.field.strength = target * min(1.0, max(0.0, (t - 0.6) / 1.2))
        wf.field.noise = 0.4

    kit.camera((2.5, -9.5, 3.2), (0.6, 0, 0.9), lens=36, dof=8)
    return dict(frames=frames, label=f"Wind {kmh} km/h", pre=pre, impacts=[kit.Impacts(blocks, "tick", 1.0)])


# ------------------------------------------------------------------ VIDEO 2
BLAST_K = 400.0          # force-field strength of "Blast 100" (calibrated)
PULL_K = 6.0             # attraction strength of "1x"


def _ramp_ball(m, r, start_x, mat=None):
    """a ramp on the left and a heavy ball at its top; returns the ball"""
    wood = kit.mat_wood((0.62, 0.4, 0.22))
    ramp = kit.box((start_x + 1.3, 0, 1.15), (3.4, 1.0, 0.12), mat=wood)
    ramp.rotation_euler = (0, math.radians(30), 0)
    kit.rigid(ramp, "PASSIVE", friction=0.5, shape="BOX")
    for sy in (-1, 1):
        rail = kit.box((start_x + 1.3, sy * 0.53, 1.3), (3.4, 0.06, 0.25), mat=wood)
        rail.rotation_euler = (0, math.radians(30), 0)
        kit.rigid(rail, "PASSIVE", friction=0.2, shape="BOX")
    xb = start_x + 0.15                                 # on the ramp surface, never inside it
    zs = 1.15 + (start_x + 1.3 - xb) * math.tan(math.radians(30)) + 0.06 / math.cos(math.radians(30))
    b = kit.ball((xb, 0, zs + r + 0.03), r, mat or kit.mat_metal((0.3, 0.3, 0.32), 0.22), "ball", seg=48)
    kit.rigid(b, mass=m, friction=0.6, bounce=0.1, shape="SPHERE", damp=(0.0, 0.02))
    return b


def towers(v):
    """the same heavy ball rolls into 10 / 100 / 1,000 blocks"""
    n = [10, 100, 1000][v]
    kit.studio("lavender")
    frames = 180
    kit.physics(frames=frames, substeps=15)
    s = 0.24
    shape = {10: (1, 1, 10), 100: (10, 1, 10), 1000: (10, 10, 10)}[n]
    nx, ny, nz = shape
    mats = _cols(nz, 0.6)
    proto = kit.box((0, 0, -50), (s - 0.008, s - 0.008, s - 0.008), bevel=0.01)
    blocks = []
    for k in range(nz):
        for i in range(nx):
            for j in range(ny):
                p = (1.0 + i * s, (j - (ny - 1) / 2) * s, s / 2 + k * s)
                o = kit.duplicate(proto, p, mat=mats[k])
                kit.rigid(o, mass=0.15, friction=0.5, bounce=0.2, shape="BOX")
                blocks.append(o)
    bpy.data.objects.remove(proto)
    ball = _ramp_ball(25, 0.42, -3.4)
    kit.camera((-2.0, -9.2, 3.6), (0.6, 0, 1.0), lens=33, dof=9)
    return dict(frames=frames, label=f"{n:,} blocks", impacts=[kit.Impacts(blocks, "clack", 0.8),
                                                              kit.Impacts([ball], "thud", 0.5, 1.5)])


def _funnel_mesh(r_top, r_bot, z_top, z_bot, seg=48):
    verts, faces = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        verts.append((r_top * math.cos(a), r_top * math.sin(a), z_top))
        verts.append((r_bot * math.cos(a), r_bot * math.sin(a), z_bot))
    for k in range(seg):
        a, b = 2 * k, 2 * ((k + 1) % seg)
        faces.append((a, b, b + 1, a + 1))
    return verts, faces


def _cup_mesh(r, h, seg=48):
    verts, faces = [(0, 0, 0)], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        verts.append((r * math.cos(a), r * math.sin(a), 0))
        verts.append((r * math.cos(a), r * math.sin(a), h))
    for k in range(seg):
        a, b = 1 + 2 * k, 1 + 2 * ((k + 1) % seg)
        faces.append((a, b, b + 1, a + 1))
        faces.append((0, b, a))
    return verts, faces


def funnel(v):
    """100 / 1,000 / 3,000 balls through a funnel into a glass"""
    n = [100, 1000, 3000][v]
    kit.studio("pink")
    frames = 240 if n < 3000 else 300
    kit.physics(frames=frames, substeps=10, iterations=15)
    rng = random.Random(9)
    metal = kit.mat_metal((0.9, 0.9, 0.92), 0.15)
    fv, ff = _funnel_mesh(1.5, 0.22, 3.6, 2.5)
    fn = kit.mesh_object("funnel", fv, ff, metal)
    sol = fn.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.03
    kit.rigid(fn, "PASSIVE", friction=0.1, bounce=0.2, shape="MESH")
    cv, cf = _cup_mesh(0.75, 1.5)
    cup = kit.mesh_object("cup", cv, cf, kit.mat_clear())
    sol = cup.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.04
    kit.rigid(cup, "PASSIVE", friction=0.3, bounce=0.2, shape="MESH")
    stand = kit.cylinder((0, 0, 3.0), 0.04, 6.0, metal, verts=12)
    stand.location = (1.65, 0, 3.0)
    kit.box((0.85, 0, 3.55), (1.6, 0.05, 0.05), mat=metal)
    r_b = 0.055 if n >= 1000 else 0.07
    mats = _cols(12, 0.0)
    proto = kit.ball((0, 0, -50), r_b, seg=16)
    balls = []
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        rr = 1.25 * math.sqrt(rng.random())
        p = (rr * math.cos(a), rr * math.sin(a), 4.0 + i * (1.4 / 1000 if n >= 1000 else 0.02) + rng.uniform(0, 0.1))
        o = kit.duplicate(proto, p, mat=mats[i % 12])
        kit.rigid(o, mass=0.02, friction=0.2, bounce=0.3, shape="SPHERE", damp=(0.02, 0.1))
        balls.append(o)
    bpy.data.objects.remove(proto)
    kit.camera((2.6, -8.4, 3.4), (0, 0, 2.1), lens=38, dof=10)
    return dict(frames=frames, label=f"{n:,} balls", impacts=[kit.Impacts(balls[:400], "tick", 0.6, 1.0)])


def attract(v):
    """zero gravity: 600 balls pulled to the centre, pull 1x / 10x / 100x"""
    k = [1, 10, 100][v]
    kit.studio("night", light=1.4)
    frames = 210
    kit.physics(gravity=0.0, frames=frames, substeps=12)
    rng = random.Random(21)
    mats = _cols(10, 0.5, s=0.75, v=1.0)
    proto = kit.ball((0, 0, -50), 0.09, seg=20)
    balls = []
    for i in range(600):
        while True:
            p = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
            if 0.35 < p.length <= 1:
                break
        p = p * 3.2 + Vector((0, 0, 2.6))
        o = kit.duplicate(proto, p, mat=mats[i % 10])
        kit.rigid(o, mass=0.1, friction=0.4, bounce=0.3, shape="SPHERE", damp=(0.05, 0.1))
        balls.append(o)
    bpy.data.objects.remove(proto)
    bpy.ops.object.effector_add(type="FORCE", location=(0, 0, 2.6))
    ff = bpy.context.object
    ff.field.strength = -PULL_K * k
    ff.field.flow = 0.0
    ff.field.shape = "POINT"
    ff.field.falloff_type = "SPHERE"
    core = kit.ball((0, 0, 2.6), 0.25, kit.mat_metal((1.0, 0.8, 0.35), 0.2), "core", seg=32)
    kit.rigid(core, "PASSIVE", friction=0.5, shape="SPHERE")
    kit.camera((0, -10.5, 3.0), (0, 0, 2.6), lens=40, dof=10)
    return dict(frames=frames, label=f"Pull {k}x", impacts=[kit.Impacts(balls[:300], "tick", 0.7, 0.8)])


def blast(v):
    """a blast under a pile of 200 blocks: power 1 / 10 / 100"""
    k = [1, 10, 100][v]
    kit.studio("steel", light=1.2)
    frames = 180
    kit.physics(frames=frames, substeps=15)
    s = 0.3
    mats = _cols(6, 0.02)
    proto = kit.box((0, 0, -50), (s - 0.01, s - 0.01, s - 0.01), bevel=0.012)
    blocks = []
    for layer in range(6):
        n = 7 - layer
        for i in range(n):
            for j in range(n):
                p = ((i - (n - 1) / 2) * s, (j - (n - 1) / 2) * s, s / 2 + layer * s)
                o = kit.duplicate(proto, p, mat=mats[layer])
                kit.rigid(o, mass=0.3, friction=0.6, bounce=0.2, shape="BOX")
                blocks.append(o)
    bpy.data.objects.remove(proto)
    bpy.ops.object.effector_add(type="FORCE", location=(0, 0, -0.2))
    ff = bpy.context.object
    ff.field.shape = "POINT"
    ff.field.falloff_type = "SPHERE"
    ff.field.use_max_distance = True
    ff.field.distance_max = 3.0
    flash = kit.ball((0, 0, 0.05), 0.4, None, "flash", seg=32)
    m, b = kit._principled("flash")
    b.inputs["Emission Color"].default_value = (1.0, 0.55, 0.15, 1)
    b.inputs["Emission Strength"].default_value = 0.0
    flash.data.materials.append(m)
    T0 = 1.0

    def pre(f):
        t = f / FPS
        on = T0 <= t < T0 + 0.12
        ff.field.strength = BLAST_K * (k / 100) ** 0.5 if on else 0.0
        g = max(0.0, 1 - abs(t - T0 - 0.05) / 0.25)
        b.inputs["Emission Strength"].default_value = 60.0 * g * (0.3 + 0.7 * k / 100)
        flash.scale = [0.2 + 2.5 * g * (0.3 + 0.7 * k / 100)] * 3

    kit.camera((0, -10.0, 3.4), (0, 0, 1.2), lens=34, dof=9)
    return dict(frames=frames, label=f"Blast power {k}", pre=pre, impacts=[kit.Impacts(blocks, "clack", 0.9)])


def ballpit(v):
    """a ball falls into a pit of 1,125 balls: 1 kg / 100 kg / 10,000 kg"""
    m = [1, 100, 10000][v]
    kit.studio("mint")
    frames = 180
    kit.physics(frames=frames, substeps=10, iterations=15)
    rng = random.Random(4)
    wall_mat = kit.mat_plastic((0.95, 0.95, 0.97), 0.35, 0.2)
    W = 3.0
    for sx, sy, sz in ((1, 0, (0.12, W + 0.24, 1.3)), (-1, 0, (0.12, W + 0.24, 1.3)),
                       (0, 1, (W + 0.24, 0.12, 1.3)), (0, -1, (W + 0.24, 0.12, 1.3))):
        w = kit.box((sx * (W / 2 + 0.06), sy * (W / 2 + 0.06), 0.65), sz, mat=wall_mat, bevel=0.03)
        kit.rigid(w, "PASSIVE", friction=0.3, shape="BOX")
    r = 0.1
    mats = _cols(8, 0.0, s=0.8, v=0.95)
    proto = kit.ball((0, 0, -50), r, seg=16)
    balls = []
    k = 15
    for layer in range(5):
        for i in range(k):
            for j in range(k):
                p = (-W / 2 + r + i * 2 * r + rng.uniform(-0.01, 0.01),
                     -W / 2 + r + j * 2 * r + rng.uniform(-0.01, 0.01), r + layer * 2 * r * 0.98)
                o = kit.duplicate(proto, p, mat=mats[rng.randrange(8)])
                kit.rigid(o, mass=0.05, friction=0.3, bounce=0.3, shape="SPHERE", damp=(0.03, 0.1))
                balls.append(o)
    bpy.data.objects.remove(proto)
    big = kit.ball((0.1, 0.1, 11.0), 0.5, kit.mat_metal((0.85, 0.7, 0.35), 0.2), "ball", seg=48)
    kit.rigid(big, mass=m, friction=0.4, bounce=0.2, shape="SPHERE")
    kit.camera((0, -8.8, 5.6), (0, 0, 0.9), lens=36, dof=9)
    return dict(frames=frames, label=f"{m:,} kg", impacts=[kit.Impacts(balls[:500], "tick", 0.6, 1.0),
                                                           kit.Impacts([big], "thud", 0.4, 1.5)])


def friction(v):
    """5 little towers on a slope: ice / wood / rubber"""
    name, mu = [("Ice", 0.02), ("Wood", 0.35), ("Rubber", 1.0)][v]
    kit.studio("sand")
    frames = 165
    kit.physics(frames=frames, substeps=15)
    ang = math.radians(24)
    slope = kit.box((0, 0, 1.6), (6.5, 2.2, 0.14), mat=kit.mat_wood((0.65, 0.42, 0.24)) if name == "Wood"
                    else kit.mat_plastic((0.75, 0.9, 1.0), 0.05, 0.8) if name == "Ice"
                    else kit.mat_plastic((0.12, 0.12, 0.13), 0.7, 0.0), bevel=0.02)
    slope.rotation_euler = (0, ang, 0)
    kit.rigid(slope, "PASSIVE", friction=mu, bounce=0.1, shape="BOX")
    leg = kit.box((-2.95, 0, 1.45), (0.3, 2.0, 2.9), mat=kit.mat_wood((0.5, 0.3, 0.17)))
    kit.rigid(leg, "PASSIVE", shape="BOX")
    s = 0.28
    mats = _cols(5, 0.0)
    proto = kit.box((0, 0, -50), (s - 0.006, s - 0.006, s - 0.006), bevel=0.012)
    blocks = []
    for t in range(5):
        u = -2.2 + t * 0.85                            # position along the slope
        for h in range(3):
            # point on the slope surface, then up along its normal
            n_ = Vector((math.sin(ang), 0, math.cos(ang)))
            base = Vector((u * math.cos(ang), 0, 1.6 - u * math.sin(ang))) + n_ * (0.07 + s / 2 + h * s)
            for yy in (-0.5, 0.5):
                o = kit.duplicate(proto, base + Vector((0, yy, 0)), mat=mats[t])
                o.rotation_euler = (0, ang, 0)
                kit.rigid(o, mass=0.3, friction=mu, bounce=0.1, shape="BOX")
                blocks.append(o)
    bpy.data.objects.remove(proto)
    kit.camera((1.0, -9.0, 3.2), (0.6, 0, 1.0), lens=33, dof=9)
    return dict(frames=frames, label=f"{name} (friction {mu:g})", impacts=[kit.Impacts(blocks, "clack", 0.8)])


def fabric(v):
    """a sheet falls on a statue: silk / cotton / denim"""
    name, mass, tension, bend, col = [("Silk", 0.15, 5, 0.05, (0.95, 0.35, 0.55)),
                                      ("Cotton", 0.3, 15, 0.5, (0.95, 0.92, 0.85)),
                                      ("Denim", 1.0, 40, 10.0, (0.18, 0.3, 0.55))][v]
    kit.studio("orange")
    frames = 165
    kit.physics(frames=frames)
    marble = kit.mat_plain((0.92, 0.91, 0.88), 0.25)
    ped = kit.box((0, 0, 0.6), (0.9, 0.9, 1.2), mat=marble, bevel=0.03)
    kit.collider(ped, thickness=0.01, friction=5)
    head = kit.ball((0, 0, 1.75), 0.55, marble, "statue", seg=48)
    kit.collider(head, thickness=0.01, friction=5)
    for sx in (-1, 1):
        c = kit.cylinder((sx * 1.15, 0.0, 0.5), 0.18, 1.0, marble, verts=32)
        kit.collider(c, thickness=0.01)
    sheet = kit.grid((0, 0, 3.2), 3.4, cuts=70, mat=None, name="sheet")
    m, b = kit._principled(name)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = 0.35 if name == "Silk" else 0.8
    b.inputs["Sheen Weight"].default_value = 0.8 if name != "Denim" else 0.3
    sheet.data.materials.append(m)
    sheet.rotation_euler = (0.08, 0.05, 0.3)
    kit.cloth(sheet, mass=mass, tension=tension, bending=bend, quality=6, frames=frames, self_collision=True)
    sol = sheet.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = 0.012
    sub = sheet.modifiers.new("smooth", "SUBSURF")
    sub.levels = sub.render_levels = 1
    kit.camera((3.6, -7.6, 3.4), (0, 0, 1.2), lens=40, dof=7)
    return dict(frames=frames, label=name, impacts=[kit.Impacts([sheet], "swish", 0.5, 0.8)])


def seesaw(v):
    """balls rain into a bucket on a seesaw; a block sits on the other end: 10 / 100 / 1,000 balls"""
    n = [10, 100, 1000][v]
    kit.studio("lavender")
    frames = 210
    kit.physics(frames=frames, substeps=15, iterations=30)
    rng = random.Random(8)
    wood = kit.mat_wood((0.65, 0.42, 0.22))
    ful = kit.box((0, 0, 0.45), (0.5, 1.2, 0.9), mat=kit.mat_plain((0.85, 0.85, 0.85), 0.5), bevel=0.03)
    kit.rigid(ful, "PASSIVE", shape="BOX")
    plank = kit.box((0, 0, 0.98), (5.2, 1.0, 0.12), mat=wood, bevel=0.01)
    kit.rigid(plank, mass=4.0, friction=0.6, shape="BOX")
    kit.constraint(ful, plank, "HINGE", loc=(0, 0, 0.95)).rotation_euler = (math.pi / 2, 0, 0)
    parts = []
    for (x, y, sx, sy) in ((-2.6, 0, 0.08, 1.0), (-1.4, 0, 0.08, 1.0), (-2.0, -0.5, 1.28, 0.08), (-2.0, 0.5, 1.28, 0.08)):
        w = kit.box((x, y, 1.39), (sx, sy, 0.7), mat=kit.mat_plastic((0.95, 0.95, 0.97), 0.3), bevel=0.01)
        kit.rigid(w, mass=0.3, friction=0.3, shape="BOX")
        kit.constraint(plank, w, "FIXED")
        parts.append(w)
    weight = kit.box((2.2, 0, 1.39), (0.7, 0.7, 0.7), mat=kit.mat_metal((0.85, 0.65, 0.3), 0.25), name="weight", bevel=0.03)
    kit.rigid(weight, mass=3.0, friction=0.6, bounce=0.1, shape="BOX")
    r = 0.06
    mats = _cols(10, 0.3)
    proto = kit.ball((0, 0, -50), r, seg=16)
    balls = []
    for i in range(n):
        layer, k_ = divmod(i, 42)
        gx, gy = divmod(k_, 6)
        p = (-2.39 + gx * 0.13 + rng.uniform(-0.01, 0.01), -0.33 + gy * 0.13 + rng.uniform(-0.01, 0.01),
             2.6 + layer * (0.13 if n > 10 else 0.6))
        o = kit.duplicate(proto, p, mat=mats[i % 10])
        kit.rigid(o, mass=0.012, friction=0.3, bounce=0.3, shape="SPHERE", damp=(0.02, 0.1))
        balls.append(o)
    bpy.data.objects.remove(proto)
    kit.camera((0.5, -9.8, 3.4), (0, 0, 1.8), lens=34, dof=10)
    return dict(frames=frames, label=f"{n:,} balls", impacts=[kit.Impacts(balls[:300], "tick", 0.6, 1.0),
                                                              kit.Impacts([weight], "thud", 0.5, 1.5)])


from b3d.catalog import IDEAS as _CAT  # noqa: E402

IDEAS = {k: dict(v, build=globals()[k]) for k, v in _CAT.items()}
