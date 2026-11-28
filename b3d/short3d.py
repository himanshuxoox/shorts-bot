"""
Put a 3D Short together (vertical 1080x1920) from its 3 rendered variants:
hook question at the top (CAPITAL words in gold), the variant's number big under it, 3 progress
dots, the physics sound (b3d/sound.py), title / description / tags made from the recipe.

    python -m b3d.short3d build <plan.json> <parts_dir> [--date D] [--out out]
       parts_dir holds <id>_<variant>.mp4 + .json (python -m b3d.assemble encode --vertical ...)
    -> out/<date>/8N_s3d_<action>_<id>.mp4 (+ _cover.png, .json) and manifest.json for the pacer
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import tempfile

from PIL import Image, ImageDraw

from b3d.assemble import FONT_B, IST, ROOT, _dur, _font, _run, _shadow_text

W, H = 1080, 1920
GOLD = (255, 214, 80, 255)


def _wrap(draw, text, font, max_w):
    lines, cur = [], []
    for w in text.split():
        if cur and draw.textlength(" ".join(cur + [w]), font=font) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def overlay(hook, label, k, n, path, last=False):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = _font(FONT_B, 68)
    lines = _wrap(d, hook, f, 960)
    y = 210 - (len(lines) - 1) * 40
    for ln in lines:
        # word by word so CAPITAL words can be gold
        total = d.textlength(" ".join(ln), font=f)
        x = (W - total) / 2
        for i, w in enumerate(ln):
            core = re.sub(r"[^A-Za-z]", "", w)
            col = GOLD if len(core) >= 2 and core.isupper() else (255, 255, 255, 255)
            _shadow_text(im, (x, y), w, f, fill=col, anchor="lm", blur=5, offset=(0, 3))
            x += d.textlength(w + " ", font=f)
        y += 82
    size = 118
    while size > 60 and d.textlength(label, font=_font(FONT_B, size)) > 980:
        size -= 6
    _shadow_text(im, (W / 2, y + 95), label, _font(FONT_B, size), fill=GOLD if last else (255, 255, 255, 255),
                 blur=8, offset=(0, 5))
    cy = y + 95 + size * 0.75
    for i in range(n):
        x = W / 2 + (i - (n - 1) / 2) * 44
        r = 11 if i == k else 8
        d.ellipse((x - r, cy - r, x + r, cy + r), fill=GOLD if i == k else (255, 255, 255, 120))
    im.save(path)


def build(recipe, parts, out_dir, k_index=0):
    from b3d import sound
    tmp = tempfile.mkdtemp(prefix=f"s3d_{recipe['id']}_")
    segs = []
    n = len(recipe["labels"])
    for v in range(n):
        mp4 = os.path.join(parts, f"{recipe['id']}_{v}.mp4")
        info = json.load(open(os.path.join(parts, f"{recipe['id']}_{v}.json")))
        ov = os.path.join(tmp, f"ov{v}.png")
        overlay(recipe["hook"], recipe["labels"][v], v, n, ov, last=(v == n - 1))
        d = _dur(mp4)
        wav = os.path.join(tmp, f"a{v}.wav")
        mono = sound.track([tuple(e) for e in info.get("events", [])], d, seed=recipe["id"] * 10 + v)
        mono = mono + sound.pad(d, recipe["id"] + v, vol=0.03)[: len(mono)]
        sound.write(wav, mono)
        seg = os.path.join(tmp, f"s{v}.mp4")
        fo = max(0.0, d - 0.15)
        _run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-i", ov, "-i", wav, "-filter_complex",
              f"[0:v][1:v]overlay=0:0,fade=t=in:st=0:d=0.15,fade=t=out:st={fo:.3f}:d=0.15[v]",
              "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", seg])
        segs.append(seg)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in segs)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"{80 + k_index:02d}_s3d_{recipe['action']}_{recipe['id']}")
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
          "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
          "-movflags", "+faststart", base + ".mp4"])
    dur = _dur(base + ".mp4")
    _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * 0.85:.2f}", "-i", base + ".mp4", "-frames:v", "1",
          base + "_cover.png"])
    shutil.rmtree(tmp, ignore_errors=True)
    return base, round(dur, 2)


def metadata(r):
    a, b, c = r["labels"]
    title = f"{r['hook']} {a} vs {b} vs {c} 😳"
    if len(title) > 90:
        title = f"{r['hook']} 😳"
    desc = "\n".join([
        f"{r['hook']} Same 3D setup, ONE thing changes: {a} → {b} → {c}.",
        "Which one surprised you the most? 👇 Tell me what I should test next!",
        "",
        "New 3D simulations every day — subscribe so you don't miss the next one!",
        "",
        "Real 3D physics (Blender rigid bodies) rendered in Cycles. Every sound comes from the collisions.",
        "100% computer-generated. No real footage.",
        "",
        "#shorts #3d #satisfying #physics #simulation #asmr",
    ])
    tags = ["3d simulation", "satisfying 3d", "physics simulation", "blender", "satisfying", "asmr",
            "oddly satisfying", f"{r['action']} simulation", r["structure"], "3dcg", "shorts"]
    return dict(title=f"{title} #shorts"[:100], title_style=f"s3d:{r['action']}", description=desc, tags=tags,
                categoryId="24")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("plan")
    b.add_argument("parts")
    b.add_argument("--date", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    b.add_argument("--out", default=os.path.join(ROOT, "out"))
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    day = os.path.join(a.out, a.date)
    mpath = os.path.join(day, "manifest.json")
    os.makedirs(day, exist_ok=True)
    man = json.load(open(mpath)) if os.path.exists(mpath) else {"date": a.date, "videos": []}
    for i, r in enumerate(plan["recipes"]):
        if not all(os.path.exists(os.path.join(a.parts, f"{r['id']}_{v}.mp4")) for v in range(len(r["labels"]))):
            print(f"#{r['id']}: a variant failed to render, skipped")
            continue
        base, dur = build(r, a.parts, day, i)
        meta = metadata(r)
        item = dict(format=f"s3d_{r['action']}", seed=r["id"], file=os.path.basename(base + ".mp4"),
                    cover=os.path.basename(base + "_cover.png"), duration=dur,
                    facts=dict(template="s3d", recipe=r), **meta)
        with open(base + ".json", "w") as f:
            json.dump(item, f, indent=1, ensure_ascii=False)
        man["videos"] = [x for x in man["videos"] if x.get("file") != item["file"]] + [item]
        print(f"{base}.mp4  {dur}s  |  {meta['title']}")
    with open(mpath, "w") as f:
        json.dump(man, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
