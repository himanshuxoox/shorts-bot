"""
Render one variant of one 3D idea to PNG frames + an impacts.json for the sound.

    python b3d/render.py <idea> <variant> <out_dir> [--res 1280] [--spp 12] [--only 1,60,120] [--every 1]

Needs the `bpy` package (requirements-3d.txt). Physics is stepped frame by frame in order, so a
variant always renders the same way. --only renders just those frames (quick look); the physics
still runs through every frame before them.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402

from b3d import ideas, kit  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("idea")
    ap.add_argument("variant", type=int)
    ap.add_argument("out")
    ap.add_argument("--res", type=int, default=1280)
    ap.add_argument("--spp", type=int, default=12)
    ap.add_argument("--only", default="")
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    idea = ideas.IDEAS[a.idea]
    os.makedirs(a.out, exist_ok=True)
    sc = kit.reset(fps=a.fps, res=(a.res, a.res * 9 // 16), spp=a.spp)
    t0 = time.time()
    scene = idea["build"](a.variant)
    n = scene["frames"]
    hook = scene.get("hook")
    pre = scene.get("pre")              # pre(f): move animated (kinematic) objects for frame f
    impacts = scene.get("impacts", [])
    only = {int(x) for x in a.only.split(",") if x}
    print(f"[{a.idea} {a.variant}] built in {time.time() - t0:.1f}s, {n} frames", flush=True)
    t_r = 0.0
    done = 0
    for f in range(1, n + 1):
        if pre:
            pre(f)
        sc.frame_set(f)
        if hook:
            hook(f)
        for imp in impacts:
            imp.step(f, a.fps)
        if (only and f in only) or (not only and (f - 1) % a.every == 0):
            sc.render.filepath = os.path.join(a.out, f"f{f:04d}.png")
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            t_r += time.time() - t1
            done += 1
            if done % 20 == 0 or only:
                print(f"  frame {f}/{n}  {t_r / done:.1f}s/frame", flush=True)
    events = sorted(e for imp in impacts for e in imp.events)
    with open(os.path.join(a.out, "impacts.json"), "w") as fh:
        json.dump(dict(idea=a.idea, variant=a.variant, frames=n, fps=a.fps, label=scene["label"],
                       events=events), fh)
    print(f"[{a.idea} {a.variant}] done: {done} frames, {t_r / max(1, done):.1f}s/frame, "
          f"{len(events)} impacts, total {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
