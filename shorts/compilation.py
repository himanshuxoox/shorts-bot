"""
Long video: "N Most Satisfying Simulations" — a landscape 1920x1080 compilation of 16 random
formats from the channel (different ones every time).

Layout of every simulation (like the big compilation channels):
  * a title card first (2 s): number + the caption, big, on black
  * the simulation big in the middle (cut out of the vertical Short around the arena)
  * the caption on the LEFT with its key words in gold, the number "#7 / 14" on the RIGHT
The chapters (0:00 …) go into the description, and a 1280x720 thumbnail is made from 4 covers.

    FORMATS=compilation EXTRA_FORMATS=none python -m shorts.batch --count 1 --date test --workers 1
    COMP_SEGMENTS=4 …   # quick test with 4 simulations
"""
import json, os, random, re, shutil, subprocess, tempfile
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_B = os.path.join(ROOT, "fonts", "Inter-Black.otf")
FONT_R = os.path.join(ROOT, "fonts", "Inter-Bold.otf")
W, H = 1920, 1080
FPS = 30
CROP_H = 1350                     # part of the vertical Short that is shown (1080 x 1350 -> 864 x 1080)
PANEL_W = (W - 864) // 2          # 528 px on each side
GOLD = (255, 210, 74)
CHANNEL = os.environ.get("CHANNEL_NAME", "Orbit Escape")

# caption on the left; WORDS IN CAPITALS are drawn in gold
CAPTIONS = {
    "fourier": "Only CIRCLES. What will they draw?",
    "fourier3d": "Spinning circles in 3D… what is it from the TOP?",
    "shrink": "Every bounce SHRINKS the ball and GROWS the wall",
    "shrink_duo": "Two balls. Every bounce SHRINKS the one that hit",
    "shrink_shape": "Every bounce SHRINKS the ball and GROWS the shape",
    "shrinksphere": "Every bounce SHRINKS the ball… in 3D",
    "focus": "Will they ALL hit the same point?",
    "focus_stretch": "Will they still meet if I STRETCH it?",
    "focus_3d": "377 balls in 3D. Do they ALL meet?",
    "golden": "Will this pattern EVER close?",
    "timestable": "Join dot n to dot n × k. What does it DRAW?",
    "primespiral": "Every number at angle n… then only PRIMES",
    "chaosgame": "Pick a random corner. Jump. Repeat. RANDOM?",
    "metronomes": "24 metronomes. Nobody touches them",
    "galton": "Every ball is RANDOM. The result never is",
    "nbody": "Suns pull on each other. Thrown out = OUT",
    "dragonfold": "Fold a strip 10 times. Open every fold to 90°",
    "sunflower3d": "Which ANGLE makes a sunflower?",
    "hilbert3d": "Can ONE line fill a whole cube?",
    "chladni": "Sand on a metal plate. Now add SOUND",
    "lorenz": "4,000 dots. Almost the SAME start",
    "squeeze": "Every squashed ball SPLITS into 3",
    "hammer": "Every crushed ball SPLITS into 3",
    "crush": "The press crushes a ball. It SPLITS into 3",
    "race_crush": "First ball to the top WINS. Don't get crushed",
    "race_lava": "Race to the flag. The LAVA is coming",
    "butterfly": "Same start. A tiny difference. Who SURVIVES?",
    "multiply": "Every multiplier COPIES the ball",
    "paint": "Most wall when time runs out WINS",
    "devour": "Can the black hole EAT them all?",
    "evolve": "With every bounce, the ball EVOLVES",
    "pendulum": "Will they LINE UP again?",
    "rosette": "Why doesn't this orbit CLOSE?",
    "sides": "Every bounce adds a SIDE. Can the triangle become a CIRCLE?",
    "arms": "Every bounce adds a SWINGING arm",
    "spiral": "It gets FASTER until it hits the CENTER",
    "predator": "Every prey they catch BECOMES a predator",
    "breakout": "The ball speeds up every time it SHATTERS a brick",
    "quadsplit": "Every box it fills SPLITS into 4. How SMALL can they get?",
    "redring": "Every RED bounce spawns 3 until the whole ring is RED",
    "sortwheel": "Sorting algorithm: wait for the perfect GRADIENT",
}
# which formats can appear, with weights (the channel's best formats come up more often)
POOL = {"fourier": 3, "shrink": 3, "focus_stretch": 3, "golden": 3, "shrink_duo": 2, "fourier3d": 2,
        "shrinksphere": 2, "timestable": 2, "primespiral": 2, "chaosgame": 2, "metronomes": 2, "focus": 2,
        "dragonfold": 2, "sunflower3d": 2, "hilbert3d": 2, "nbody": 2, "galton": 1, "squeeze": 1,
        "race_crush": 1, "butterfly": 1, "devour": 1, "chladni": 1, "shrink_shape": 1, "focus_3d": 1,
        "pendulum": 1, "hammer": 1, "multiply": 1, "evolve": 1, "lorenz": 1,
        # the reference-style formats (9 Nov) come up often in the long video
        "sides": 2, "arms": 2, "spiral": 2, "predator": 2, "breakout": 2, "quadsplit": 2, "redring": 2,
        "sortwheel": 2}
TITLES = [
    "{n} Most Satisfying Simulations — {m} Minutes of Pure Satisfaction",
    "{n} Satisfying Physics & Math Simulations to Relax 🌙",
    "{n} Simulations You Can't Stop Watching 🤯",
    "{n} Oddly Satisfying Simulations — Watch Till the End",
]


@dataclass
class Config:
    seed: int
    picks: list = field(default_factory=list)


def make_config(seed):
    rng = random.Random(seed * 7907 + 3)
    n = int(os.environ.get("COMP_SEGMENTS", "16"))
    pool = dict(POOL)
    picks = []
    while len(picks) < n and pool:
        keys = list(pool)
        f = rng.choices(keys, weights=[pool[k] for k in keys])[0]
        pool.pop(f)
        picks.append(f)
    return Config(seed, picks)


def simulate(cfg, record=False):
    return {}


def is_good(res):
    return True


# ------------------------------------------------------------------ drawing helpers (PIL)
def _font(path, size):
    return ImageFont.truetype(path, size)


def _wrap(words, font, max_w, draw):
    lines, cur = [], []
    for w in words:
        trial = cur + [w]
        if draw.textlength(" ".join(trial), font=font) > max_w and cur:
            lines.append(cur)
            cur = [w]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _rich_lines(draw, text, xc, yc, max_w, size, font_path=FONT_B, align="center"):
    """draw `text` wrapped, centred on (xc, yc); words written in CAPITALS (2+ letters) in gold."""
    font = _font(font_path, size)
    words = text.split()
    lines = _wrap(words, font, max_w, draw)
    while len(lines) > 4 and size > 30:
        size -= 4
        font = _font(font_path, size)
        lines = _wrap(words, font, max_w, draw)
    lh = int(size * 1.22)
    y = yc - lh * len(lines) / 2
    for ln in lines:
        lw = draw.textlength(" ".join(ln), font=font)
        x = xc - lw / 2 if align == "center" else xc
        for w in ln:
            core = re.sub(r"[^A-Za-z]", "", w)
            col = GOLD if len(core) >= 2 and core.isupper() else (255, 255, 255)
            draw.text((x, y), w, font=font, fill=col)
            x += draw.textlength(w + " ", font=font)
        y += lh


def side_panels(caption, k, n, path):
    """transparent 1920x1080 PNG: caption left, '#k / n' right, faint channel name bottom-right"""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    _rich_lines(d, caption, PANEL_W / 2, H / 2, PANEL_W - 80, 50)
    xr = W - PANEL_W / 2
    f1, f2 = _font(FONT_B, 120), _font(FONT_R, 40)
    s = f"#{k}"
    d.text((xr - d.textlength(s, font=f1) / 2, H / 2 - 110), s, font=f1, fill=GOLD)
    s2 = f"of {n}"
    d.text((xr - d.textlength(s2, font=f2) / 2, H / 2 + 30), s2, font=f2, fill=(200, 200, 210))
    f3 = _font(FONT_R, 28)
    d.text((W - 40 - d.textlength(CHANNEL, font=f3), H - 60), CHANNEL, font=f3, fill=(255, 255, 255, 90))
    im.save(path)


def title_card(caption, k, n, path):
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    f = _font(FONT_B, 70)
    s = f"#{k} of {n}"
    d.text((W / 2 - d.textlength(s, font=f) / 2, 300), s, font=f, fill=GOLD)
    _rich_lines(d, caption, W / 2, 600, 1300, 84)
    im.save(path)


def intro_card(n, path):
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    _rich_lines(d, f"{n} MOST SATISFYING simulations", W / 2, 470, 1500, 110)
    f = _font(FONT_R, 46)
    s = "Pick your favourite in the comments"
    d.text((W / 2 - d.textlength(s, font=f) / 2, 700), s, font=f, fill=(200, 200, 210))
    im.save(path)


def thumbnail(covers, crops, n, path):
    """1280x720: 2x2 grid of square crops from 4 covers + big number"""
    th = Image.new("RGB", (1280, 720), (0, 0, 0))
    for i, (c, top) in enumerate(list(zip(covers, crops))[:4]):
        im = Image.open(c).convert("RGB")
        y0 = top + (CROP_H - 1080) // 2
        sq = im.crop((0, y0, 1080, y0 + 1080)).resize((360, 360))
        th.paste(sq, (560 + (i % 2) * 360, (i // 2) * 360))
    d = ImageDraw.Draw(th)
    f = _font(FONT_B, 210)
    d.text((40, 120), str(n), font=f, fill=GOLD)
    f2 = _font(FONT_B, 64)
    d.text((44, 380), "SATISFYING", font=f2, fill=(255, 255, 255))
    d.text((44, 460), "SIMULATIONS", font=f2, fill=(255, 255, 255))
    th.save(path, quality=92)


# ------------------------------------------------------------------ video helpers (ffmpeg)
def _run(cmd):
    subprocess.run(cmd, check=True)


def _dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def crop_top(mp4):
    """-> (y, background colour). y = where the arena starts: the Short's own question at the top is
    skipped (the caption is shown on the left instead). Uses a frame from the middle: the first bright
    text block and the gap after it. The colour is the Short's background, used to fill the sides."""
    d = _dur(mp4)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{d * 0.5:.2f}", "-i", mp4, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    rgb = np.frombuffer(raw, np.uint8)[: 1080 * 1920 * 3].reshape(1920, 1080, 3)
    bg = tuple(int(c) for c in np.median(rgb[1880:1915, 4:60].reshape(-1, 3), axis=0))
    img = rgb.mean(2)
    bright = (img[:800] > 140).sum(1) > 3
    rows = np.nonzero(bright)[0]
    y_top = 285
    if len(rows):
        run = 0
        for y in range(rows[0], 800):
            run = run + 1 if not bright[y] else 0
            if run >= 26:
                y_top = int(min(max(y - 22, 120), 1920 - CROP_H))
                break
    return y_top, bg


def silent_card(png, seconds, out):
    _run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", f"{seconds}", "-i", png,
          "-f", "lavfi", "-t", f"{seconds}", "-i", "anullsrc=r=44100:cl=stereo",
          "-vf", f"fps={FPS},format=yuv420p,fade=t=in:st=0:d=0.25,fade=t=out:st={seconds - 0.25}:d=0.25",
          "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest", out])


def segment(mp4, top, bg, panel_png, out):
    col = "0x%02x%02x%02x" % bg
    _run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-i", panel_png, "-filter_complex",
          f"[0:v]crop=1080:{CROP_H}:0:{top},scale=864:1080,pad={W}:{H}:{PANEL_W}:0:{col},fps={FPS}[v];"
          f"[v][1:v]overlay=0:0,format=yuv420p[o];[0:a]aresample=44100,aformat=channel_layouts=stereo[a]",
          "-map", "[o]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
          "-c:a", "aac", "-b:a", "160k", out])


def _ts(s):
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


# ------------------------------------------------------------------ the batch interface
def render_video(cfg, base):
    from . import batch                                           # (late import: batch imports this module)
    tmp = tempfile.mkdtemp(prefix="comp_")
    n = len(cfg.picks)
    parts, chapters, covers, tops = [], [], [], []
    t = 0.0
    intro = os.path.join(tmp, "intro.mp4")
    intro_card(n, os.path.join(tmp, "intro.png"))
    silent_card(os.path.join(tmp, "intro.png"), 2.5, intro)
    parts.append(intro)
    t += _dur(intro)
    start = 500000 + cfg.seed * 50                                 # own seed range, never a Short's seed
    for k, fmt in enumerate(cfg.picks, 1):
        mod = batch.MODS[fmt]
        s = batch.find_seed(mod, start + k * 7)
        item = batch.render_one((fmt, s, tmp, k, None))
        mp4 = os.path.join(tmp, item["file"])
        cap = CAPTIONS.get(fmt) or re.sub(r"#\w+|[^\w\s?!,.'’…-]", "", item["title"]).strip()
        top, bg = crop_top(mp4)
        card_png, panel_png = os.path.join(tmp, f"card{k}.png"), os.path.join(tmp, f"panel{k}.png")
        title_card(cap, k, n, card_png)
        side_panels(cap, k, n, panel_png)
        card, seg = os.path.join(tmp, f"c{k:02d}.mp4"), os.path.join(tmp, f"s{k:02d}.mp4")
        silent_card(card_png, 2.0, card)
        segment(mp4, top, bg, panel_png, seg)
        chapters.append((0.0 if k == 1 else t, f"#{k} {re.sub(r'[A-Z]{2,}', lambda m_: m_.group(0).lower(), cap)}"))
        parts += [card, seg]
        t += _dur(card) + _dur(seg)
        covers.append(os.path.join(tmp, item["cover"]))
        tops.append(top)
        print(f"   compilation {k}/{n}: {fmt} seed {s}", flush=True)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    out = base + ".mp4"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
          "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k",
          "-movflags", "+faststart", out])
    thumbnail(covers, tops, n, base + "_thumb.jpg")
    shutil.copy(covers[0], base + "_cover.png")
    shutil.rmtree(tmp, ignore_errors=True)
    dur = _dur(out)
    return dict(chapters=chapters, picks=cfg.picks, n=n), round(dur, 2)


def metadata_facts(res, cfg):
    return dict(template="compilation", colors=[], melody="", n_balls=res["n"], chapters=res["chapters"],
                picks=res["picks"])
