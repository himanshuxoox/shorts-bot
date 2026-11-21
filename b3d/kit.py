"""
Studio kit for the 3D (Blender) formats: a seamless coloured backdrop, soft studio lights, a few
good-looking materials, rigid-body helpers, and an impact tracker for the sound.

Runs inside Blender's Python (pip package `bpy`, see requirements-3d.txt). Everything is built by
code, nothing is loaded from .blend files, so a scene is the same on every machine.
"""
import colorsys
import math

import bpy
from mathutils import Vector

BACKDROPS = {                                    # (backdrop colour, light warmth) like a photo studio
    "orange": (0.80, 0.42, 0.16),
    "pink": (0.86, 0.48, 0.58),
    "lavender": (0.55, 0.50, 0.80),
    "steel": (0.30, 0.34, 0.40),
    "mint": (0.42, 0.72, 0.62),
    "sand": (0.82, 0.66, 0.46),
    "night": (0.10, 0.11, 0.14),
}


def reset(fps=30, res=(1280, 720), spp=12):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()
    _DATA.clear()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = spp
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.05
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.cycles.transmission_bounces = 4
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.blur_glossy = 1.0
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.view_settings.exposure = -0.35
    sc.frame_start = 1
    return sc


# ---------------------------------------------------------------- look
def studio(color="orange", wall_y=6.0, width=240.0, height=40.0, radius=3.0, light=1.0, key_from=(-0.5, -1.0)):
    """Curved backdrop (floor bends up into a wall: no horizon line), a big soft key light, a fill
    from the world. Returns the backdrop object (it is also the ground for the physics)."""
    sc = bpy.context.scene
    rgb = BACKDROPS.get(color, color)
    # profile in the y-z plane: floor from far in front to the curve, quarter circle, wall up
    prof = [(-120.0, 0.0), (wall_y - radius, 0.0)]
    for i in range(1, 12):
        a = i / 12 * math.pi / 2
        prof.append((wall_y - radius + radius * math.sin(a), radius - radius * math.cos(a)))
    prof += [(wall_y, radius), (wall_y, height)]
    verts, faces = [], []
    for x in (-width / 2, width / 2):
        for y, z in prof:
            verts.append((x, y, z))
    n = len(prof)
    for i in range(n - 1):
        faces.append((i, i + 1, n + i + 1, n + i))
    me = bpy.data.meshes.new("backdrop")
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new("backdrop", me)
    sc.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    ob.data.materials.append(mat_plain(rgb, rough=0.75))
    # the physics ground is a flat box (the curved mesh is only for looks)
    ground = box((0, 0, -0.5), (width, 60, 1.0), mat=None, name="ground")
    ground.hide_render = True
    rigid(ground, "PASSIVE", friction=0.6, bounce=0.3)
    # key light: big soft area light above and in front; a rim light behind
    kx, ky = key_from
    area_light((6 * kx, 6 * ky - 2, 9), size=7, energy=2000 * light, target=(0, 0, 0))
    area_light((4, wall_y - 1.5, 7), size=5, energy=450 * light, target=(0, 0, 1), color=(1.0, 0.95, 0.9))
    w = bpy.data.worlds.new("world")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*[0.45 + 0.55 * c for c in rgb], 1)
    bg.inputs["Strength"].default_value = 0.25 * light
    return ob


def area_light(loc, size=4, energy=1000, target=(0, 0, 0), color=(1, 1, 1)):
    bpy.ops.object.light_add(type="AREA", location=loc)
    L = bpy.context.object
    L.data.energy = energy
    L.data.size = size
    L.data.color = color
    L.visible_camera = False
    L.visible_glossy = True
    look_at(L, target)
    return L


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def camera(loc, target, lens=50, dof=None):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.data.lens = lens
    look_at(cam, target)
    if dof:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = (Vector(target) - Vector(loc)).length
        cam.data.dof.aperture_fstop = dof
    bpy.context.scene.camera = cam
    return cam


# ---------------------------------------------------------------- materials
_MATS = {}


def _principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes["Principled BSDF"]


def mat_plain(rgb, rough=0.5):
    m, b = _principled("plain")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def mat_plastic(rgb, rough=0.28, coat=0.4):
    key = ("plastic", tuple(round(c, 3) for c in rgb), rough, coat)
    if key in _MATS:
        return _MATS[key]
    m, b = _principled("plastic")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.08
    _MATS[key] = m
    return m


def mat_metal(rgb=(0.92, 0.92, 0.95), rough=0.12):
    key = ("metal", rgb, rough)
    if key in _MATS:
        return _MATS[key]
    m, b = _principled("metal")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = rough
    _MATS[key] = m
    return m


def mat_jelly(rgb, alpha_rough=0.08):
    """glossy, a bit see-through, like gummy candy"""
    m, b = _principled("jelly")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = alpha_rough
    b.inputs["Transmission Weight"].default_value = 0.75
    b.inputs["IOR"].default_value = 1.35
    b.inputs["Subsurface Weight"].default_value = 0.2
    b.inputs["Coat Weight"].default_value = 0.6
    return m


def mat_wood(rgb=(0.55, 0.33, 0.17), scale=6.0):
    key = ("wood", rgb, scale)
    if key in _MATS:
        return _MATS[key]
    m, b = _principled("wood")
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale * 0.12, scale * 0.12)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 2.0
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*[c * 0.55 for c in rgb], 1)
    ramp.color_ramp.elements[1].color = (*rgb, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    b.inputs["Coat Weight"].default_value = 0.25
    _MATS[key] = m
    return m


def mat_glass(rgb=(0.85, 0.95, 1.0)):
    m, b = _principled("glass")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.45
    return m


def mat_clear(rgb=(0.92, 0.97, 1.0)):
    """cheap see-through 'glass' (alpha + glossy coat): no dark refraction, renders fast"""
    m, b = _principled("clear")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = 0.05
    b.inputs["Alpha"].default_value = 0.18
    b.inputs["Coat Weight"].default_value = 1.0
    return m


def rainbow(i, n, s=0.72, v=0.95, h0=0.0):
    return colorsys.hsv_to_rgb((h0 + i / max(1, n)) % 1.0, s, v)


# ---------------------------------------------------------------- objects
def _finish(ob, mat, name, smooth):
    if name:
        ob.name = name
    if mat is not None:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
    return ob


def box(loc, size, mat=None, name=None, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.object
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.harden_normals = False
    return _finish(ob, mat, name, smooth=bool(bevel))


def ball(loc, r, mat=None, name=None, seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=seg // 2)
    return _finish(bpy.context.object, mat, name, smooth=True)


def cylinder(loc, r, depth, mat=None, name=None, verts=48, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, vertices=verts, rotation=rot)
    ob = bpy.context.object
    for p in ob.data.polygons:                       # smooth sides, flat caps
        p.use_smooth = len(p.vertices) == 4
    if mat is not None:
        ob.data.materials.append(mat)
    if name:
        ob.name = name
    return ob


_DATA = {}


def duplicate(ob, loc, mat=None, linked=True):
    """fast copy that shares mesh data (one mesh per prototype + material), so hundreds of rigid
    bodies stay light. Modifiers (bevel) are applied to the shared mesh once."""
    if ob.modifiers:
        bpy.context.view_layer.objects.active = ob
        for m in list(ob.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
    o = ob.copy()
    if mat is not None:
        key = (ob.data.name, mat.name)
        if key not in _DATA:
            d = ob.data.copy()
            d.materials.clear()
            d.materials.append(mat)
            _DATA[key] = d
        o.data = _DATA[key]
    elif not linked:
        o.data = ob.data.copy()
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o


# ---------------------------------------------------------------- physics
def physics(gravity=-9.81, substeps=10, iterations=20, frames=300):
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rw = sc.rigidbody_world
    rw.substeps_per_frame = substeps
    rw.solver_iterations = iterations
    rw.point_cache.frame_start = 1
    rw.point_cache.frame_end = frames + 5
    sc.gravity = (0, 0, gravity)
    sc.frame_end = frames
    return rw


def rigid(ob, kind="ACTIVE", mass=1.0, friction=0.5, bounce=0.2, shape=None, margin=0.002, damp=(0.04, 0.1)):
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    sc.rigidbody_world.collection = sc.rigidbody_world.collection or bpy.data.collections.new("RigidBodyWorld")
    coll = sc.rigidbody_world.collection
    if ob.name not in coll.objects:
        coll.objects.link(ob)
    rb = ob.rigid_body
    rb.type = kind
    rb.mass = mass
    rb.friction = friction
    rb.restitution = bounce
    rb.collision_margin = margin
    rb.use_margin = True
    rb.linear_damping, rb.angular_damping = damp
    if shape:
        rb.collision_shape = shape
    return ob


def constraint(a, b, kind="FIXED", breaking=None, loc=None):
    sc = bpy.context.scene
    e = bpy.data.objects.new("con", None)
    sc.collection.objects.link(e)
    e.location = loc if loc is not None else (Vector(a.location) + Vector(b.location)) / 2
    if sc.rigidbody_world.constraints is None:
        sc.rigidbody_world.constraints = bpy.data.collections.new("RigidBodyConstraints")
    sc.rigidbody_world.constraints.objects.link(e)
    bpy.context.view_layer.objects.active = e
    bpy.ops.rigidbody.constraint_add()
    c = e.rigid_body_constraint
    c.type = kind
    c.object1, c.object2 = a, b
    if breaking is not None:
        c.use_breaking = True
        c.breaking_threshold = breaking
    return e


# ---------------------------------------------------------------- sound
class Impacts:
    """Watches objects frame by frame. A sudden change of velocity = an impact; its size goes in the
    sound track (b3d/sound.py turns these into clacks and thuds)."""

    def __init__(self, objs, kind="clack", scale=1.0, min_dv=0.6):
        self.objs = list(objs)
        self.kind, self.scale, self.min_dv = kind, scale, min_dv
        self.prev = [None] * len(self.objs)
        self.prev_v = [Vector((0, 0, 0))] * len(self.objs)
        self.events = []

    def step(self, frame, fps):
        for i, o in enumerate(self.objs):
            p = o.matrix_world.translation.copy()
            if self.prev[i] is not None:
                v = (p - self.prev[i]) * fps
                dv = (v - self.prev_v[i]).length
                if dv > self.min_dv and frame > 2:
                    self.events.append((frame / fps, self.kind, min(1.0, dv * self.scale / 12.0)))
                self.prev_v[i] = v
            self.prev[i] = p


def kinematic(ob, friction=0.6, bounce=0.2, shape=None):
    """a body that moves by code (pre-hook) and pushes the others"""
    rigid(ob, "PASSIVE", friction=friction, bounce=bounce, shape=shape)
    ob.rigid_body.kinematic = True
    return ob


def cloth(ob, mass=0.3, tension=15, bending=0.5, pressure=None, quality=6, frames=300, self_collision=False,
          shrink=0.0):
    mod = ob.modifiers.new("cloth", "CLOTH")
    s = mod.settings
    s.quality = quality
    s.mass = mass
    s.tension_stiffness = s.compression_stiffness = tension
    s.shear_stiffness = tension
    s.bending_stiffness = bending
    s.air_damping = 1.0
    if pressure is not None:
        s.use_pressure = True
        s.uniform_pressure_force = pressure
        s.use_internal_springs = True
        s.internal_spring_max_length = 0.0
        s.internal_tension_stiffness = tension * 0.5
        s.internal_compression_stiffness = tension * 0.5
    if shrink:
        s.shrink_min = shrink
    c = mod.collision_settings
    c.distance_min = 0.004
    c.use_self_collision = self_collision
    c.self_distance_min = 0.01
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = frames + 5
    return mod


def collider(ob, thickness=0.01, friction=5.0):
    ob.modifiers.new("collision", "COLLISION")
    ob.collision.thickness_outer = thickness
    ob.collision.cloth_friction = friction
    return ob


def subdivided_cube(loc, size, level=3, mat=None, name=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.object
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=level)
    bpy.ops.object.mode_set(mode="OBJECT")
    return _finish(ob, mat, name, smooth=True)


def grid(loc, size, cuts=40, mat=None, name=None):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=cuts, y_subdivisions=cuts, size=size, location=loc)
    return _finish(bpy.context.object, mat, name, smooth=True)


def cone(loc, r, depth, mat=None, name=None, verts=24):
    bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=0.0, depth=depth, location=loc, vertices=verts)
    return _finish(bpy.context.object, mat, name, smooth=True)


def mesh_object(name, verts, faces, mat=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return _finish(ob, mat, None, smooth)
