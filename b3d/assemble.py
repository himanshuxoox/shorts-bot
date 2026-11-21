"""
Put the rendered 3D variants together into one long (landscape) video, like the popular
"3DCG physics" compilations: every variant plays with its number big at the top ("1,000 kg"),
the ASMR sound comes from the physics impacts, chapters go in the description, the thumbnail
shows one idea's variants side by side.

    python -m b3d.assemble encode <frames_dir> <out.mp4>        # in each render job: PNGs -> mp4
    python -m b3d.assemble video heavy <parts_dir> [--date D]    # -> out/<date>/NN_3d_heavy_*.mp4 + json

parts_dir holds <idea>_<variant>.mp4 and <idea>_<variant>.json (impacts.json from b3d/render.py).
"""
import argparse
import datetime as dt
import json
import os
import random
import shutil
import subprocess
import tempfile
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_B = os.path.join(ROOT, "fonts", "Inter-Black.otf")
FONT_R = os.path.join(ROOT, "fonts", "Inter-Bold.otf")
W, H, FPS = 1920, 1080, 30
IST = ZoneInfo("Asia/Kolkata")

from b3d.catalog import IDEAS, VIDEOS  # noqa: E402

CHANNEL = os.environ.get("CHANNEL_NAME", "Orbit Escape")


def _run(cmd):
    subprocess.run(cmd, check=True)


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


# ---------------------------------------------------------------- encode (render job)
def encode(frames_dir, out):
    """PNG frames (any size) -> 1920x1080 30 fps silent mp4, high quality (it is re-encoded once more)"""
    _run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(frames_dir, "f%04d.png"),
          "-vf", f"scale={W}:{H}:flags=lanczos", "-c:v", "libx264", "-preset", "medium", "-crf", "14",
          "-pix_fmt", "yuv420p", out])
    imp = os.path.join(frames_dir, "impacts.json")
    if os.path.exists(imp):
        shutil.copy(imp, out.replace(".mp4", ".json"))


# ---------------------------------------------------------------- overlays
def _font(path, size):
    return ImageFont.truetype(path, size)


def _shadow_text(im, xy, s, font, fill=(255, 255, 255, 255), anchor="mm", blur=6, offset=(0, 4)):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + offset[0], xy[1] + offset[1]), s, font=font, fill=(0, 0, 0, 150), anchor=anchor)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    im.alpha_composite(sh)
    ImageDraw.Draw(im).text(xy, s, font=font, fill=fill, anchor=anchor)


def label_png(label, sub, path, k=None, n=None):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _shadow_text(im, (W / 2, 92), label, _font(FONT_B, 92))
    _shadow_text(im, (W / 2, 168), sub, _font(FONT_R, 40), fill=(255, 255, 255, 215), blur=4, offset=(0, 2))
    if k is not None:
        _shadow_text(im, (60, 60), f"#{k}", _font(FONT_B, 54), fill=(255, 214, 80, 255), anchor="lm")
    _shadow_text(im, (W - 40, H - 34), CHANNEL, _font(FONT_R, 26), fill=(255, 255, 255, 110), anchor="rm",
                 blur=2, offset=(0, 1))
    im.save(path)


# ---------------------------------------------------------------- video
def segment(mp4, info, overlay, out, tmp, seed):
    from b3d import sound
    d = _dur(mp4)
    wav = os.path.join(tmp, os.path.basename(out).replace(".mp4", ".wav"))
    mono = sound.track([tuple(e) for e in info.get("events", [])], d, seed=seed)
    sound.write(wav, mono)
    fo = max(0.0, d - 0.18)
    _run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-i", overlay, "-i", wav, "-filter_complex",
          f"[0:v][1:v]overlay=0:0,fade=t=in:st=0:d=0.18,fade=t=out:st={fo:.3f}:d=0.18[v]",
          "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", out])
    return d


def thumbnail(parts, idea, labels, path):
    """the idea's variants side by side, each with its number (like the big 3D channels)"""
    k = len(labels)
    th = Image.new("RGB", (1280, 720), (0, 0, 0))
    pw = 1280 // k
    for i in range(k):
        mp4 = os.path.join(parts, f"{idea}_{i}.mp4")
        png = os.path.join(os.path.dirname(path), f"_th{i}.png")
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{_dur(mp4) * 0.42:.2f}", "-i", mp4, "-frames:v", "1", png])
        fr = Image.open(png).convert("RGB")
        fr = fr.resize((int(720 * 16 / 9), 720))
        x0 = (fr.width - pw) // 2
        th.paste(fr.crop((x0, 0, x0 + pw, 720)), (i * pw, 0))
        os.remove(png)
    th = th.convert("RGBA")
    d = ImageDraw.Draw(th)
    for i in range(1, k):
        d.line([(i * pw, 0), (i * pw, 720)], fill=(255, 255, 255, 255), width=6)
    for i, lab in enumerate(labels):
        size = 80
        while size > 28 and d.textlength(lab, font=_font(FONT_B, size)) > pw - 36:
            size -= 4
        f = _font(FONT_B, size)
        _shadow_text(th, (i * pw + pw / 2, 600), lab, f, fill=(255, 214, 80, 255) if i == k - 1 else (255, 255, 255, 255),
                     blur=8, offset=(0, 5))
    th.convert("RGB").save(path, quality=92)


def build_video(name, parts, out_dir, seed, only=None):
    spec = dict(VIDEOS[name])
    if only:
        spec["ideas"] = [i for i in spec["ideas"] if i in only]
    tmp = tempfile.mkdtemp(prefix=f"3d_{name}_")
    segs, chapters = [], []
    t = 0.0
    for k, idea in enumerate(spec["ideas"], 1):
        n = IDEAS[idea]["n"]
        labels = []
        for v in range(n):
            mp4 = os.path.join(parts, f"{idea}_{v}.mp4")
            info = json.load(open(os.path.join(parts, f"{idea}_{v}.json")))
            labels.append(info["label"])
            ov = os.path.join(tmp, f"ov_{idea}_{v}.png")
            label_png(info["label"], IDEAS[idea]["title"], ov, k=k)
            seg = os.path.join(tmp, f"s{k:02d}_{v}.mp4")
            if v == 0:
                chapters.append((t, IDEAS[idea]["title"]))
            t += segment(mp4, info, ov, seg, tmp, seed * 100 + k * 10 + v)
            segs.append(seg)
        chapters[-1] = (chapters[-1][0], f"{chapters[-1][1]} ({' → '.join(labels)})")
        print(f"   3d {name}: {k}/{len(spec['ideas'])} {idea}", flush=True)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in segs)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"90_3d_{name}_{seed}")
    # a soft pad under everything, then loudness to YouTube's level
    from b3d import sound
    padwav = os.path.join(tmp, "pad.wav")
    sound.write(padwav, sound.pad(t + 0.5, seed))
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", padwav,
          "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]",
          "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
          base + ".mp4"])
    thumb_idea = spec["thumb"] if spec["thumb"] in spec["ideas"] else spec["ideas"][0]
    thumbnail(parts, thumb_idea, [json.load(open(os.path.join(parts, f"{thumb_idea}_{v}.json")))["label"]
                                  for v in range(IDEAS[thumb_idea]["n"])], base + "_thumb.jpg")
    _run(["ffmpeg", "-v", "error", "-y", "-ss", "3", "-i", base + ".mp4", "-frames:v", "1", base + "_cover.png"])
    shutil.rmtree(tmp, ignore_errors=True)
    return base, round(_dur(base + ".mp4"), 2), chapters


def _ts(s):
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def metadata(name, chapters, seed):
    from shorts import metadata as md
    rng = random.Random(seed)
    spec = VIDEOS[name]
    title = rng.choice(spec["titles"])[:100]
    lines = [
        "One setup, one number changes — watch what happens 😳 Every simulation is a real 3D physics simulation, "
        "rendered in Blender. Every sound comes from the collisions.",
        "Which one surprised you the most? 👇 Tell me what I should simulate next!",
        "",
        "⏱️ Chapters",
    ] + [f"{_ts(t)} {c}" for t, c in chapters] + [
        "",
        "New simulations every day — subscribe so you don't miss the next one!",
        "",
        "🎵 Sound: physics impacts + a soft pad, synthesized in code for this video.",
        "100% computer-generated (Blender physics + Cycles). No real footage.",
        "",
        "#satisfying #3d #physics #simulation #asmr #blender #oddlysatisfying",
    ]
    tags = ["satisfying 3d", "3d physics simulation", "satisfying simulation", "blender physics", "asmr",
            "oddly satisfying", "physics", "soft body", "rigid body", "3dcg", "satisfying video", "relaxing"]
    return dict(title=title, title_style=f"3d_{name}", description="\n".join(lines), tags=tags,
                categoryId="24", channel=md.CHANNEL_NAME)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("encode")
    e.add_argument("frames")
    e.add_argument("out")
    v = sub.add_parser("video")
    v.add_argument("name", choices=list(VIDEOS))
    v.add_argument("parts")
    v.add_argument("--date", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    v.add_argument("--out", default=os.path.join(ROOT, "out"))
    v.add_argument("--seed", type=int, default=int(dt.datetime.now(IST).strftime("%j")))
    v.add_argument("--only", default="", help="comma list of ideas (preview)")
    a = ap.parse_args()
    if a.cmd == "encode":
        encode(a.frames, a.out)
        return
    day = os.path.join(a.out, a.date)
    base, dur, chapters = build_video(a.name, a.parts, day, a.seed, [x for x in a.only.split(",") if x])
    meta = metadata(a.name, chapters, a.seed)
    item = dict(format=f"3d_{a.name}", seed=a.seed, file=os.path.basename(base + ".mp4"),
                cover=os.path.basename(base + "_cover.png"), thumbnail=os.path.basename(base + "_thumb.jpg"),
                duration=dur, long_form=True, facts=dict(template=f"3d_{a.name}", chapters=chapters), **meta)
    with open(base + ".json", "w") as f:
        json.dump(item, f, indent=1, ensure_ascii=False)
    mpath = os.path.join(day, "manifest.json")
    man = json.load(open(mpath)) if os.path.exists(mpath) else {"date": a.date, "videos": []}
    man["videos"] = [x for x in man["videos"] if x.get("file") != item["file"]] + [item]
    with open(mpath, "w") as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    print(f"{base}.mp4  {dur}s  |  {meta['title']}")


if __name__ == "__main__":
    main()
