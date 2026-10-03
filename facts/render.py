"""Compose a facts Short: Ken Burns images, word-by-word captions, voice + music bed."""
import math, os, subprocess, wave

import cairo
import numpy as np

W, H, FPS = 1080, 1920, 30
SR = 24000
GAP = 0.18          # pause between scenes (s)
OUTRO = 2.6         # outro card length (s)
FADE = 0.35
FONT = os.environ.get("SHORTS_FONT", "Inter")
ACCENT = {"AI NEWS": (0.36, 0.62, 1.0), "NEW DISCOVERY": (0.2, 0.9, 0.6),
          "SCIENCE EXPLAINED": (1.0, 0.75, 0.2), "FUN FACT": (1.0, 0.4, 0.7),
          "MONEY SCIENCE": (0.4, 0.95, 0.4)}


# ------------------------------------------------------------------ timeline
def build_timeline(scenes, audios, outro_len=OUTRO):
    t, out = 0.0, []
    for sc, a in zip(scenes, audios):
        speech = len(a) / SR
        words = sc["narration"].split()
        weights = np.array([len(w) + 2 for w in words], float)
        edges = np.concatenate([[0], np.cumsum(weights)]) / weights.sum() * speech
        out.append(dict(start=t, speech=speech, end=t + speech + GAP,
                        words=[(w, t + edges[i], t + edges[i + 1]) for i, w in enumerate(words)]))
        t += speech + GAP
    return out, t + outro_len


def caption_chunks(words, max_words=3, max_chars=18):
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or sum(len(x[0]) + 1 for x in cur) + len(w[0]) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w[0][-1:] in ".?!,;:":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


# ------------------------------------------------------------------ drawing helpers
def _font(ctx, size, bold=True):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)


def _wrap(ctx, text, size, max_w):
    _font(ctx, size)
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if ctx.text_extents(trial).x_advance > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _outlined(ctx, s, x, y, size, fill=(1, 1, 1), stroke=6, alpha=1.0):
    _font(ctx, size)
    ctx.move_to(x, y)
    ctx.text_path(s)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_source_rgba(0, 0, 0, 0.85 * alpha)
    ctx.set_line_width(stroke)
    ctx.stroke_preserve()
    ctx.set_source_rgba(*fill, alpha)
    ctx.fill()
    ctx.new_path()


def _centered_block(ctx, lines, cy, size, fill=(1, 1, 1), alpha=1.0, lh=1.15):
    _font(ctx, size)
    total = len(lines) * size * lh
    y = cy - total / 2 + size
    for ln in lines:
        e = ctx.text_extents(ln)
        _outlined(ctx, ln, W / 2 - e.x_advance / 2, y, size, fill, max(4, size / 9), alpha)
        y += size * lh


def _pill(ctx, x, y, w, h, rgb, a=1.0):
    r = h / 2
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, math.pi / 2)
    ctx.arc(x + r, y + r, r, math.pi / 2, 3 * math.pi / 2)
    ctx.close_path()
    ctx.set_source_rgba(*rgb, a)
    ctx.fill()


def _rrect(ctx, x, y, w, h, r, rgb, a=1.0):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    ctx.set_source_rgba(*rgb, a)
    ctx.fill()


STILL = set()   # scene indexes that are still images (get Ken Burns); videos play as-is


def _paint_image(ctx, surf, p, idx, alpha):
    """Ken Burns for stills (alternate zoom in / out with a gentle drift); videos untouched."""
    if idx in STILL:
        z = 1.04 + 0.10 * (p if idx % 2 == 0 else 1 - p)
        dx = (18 if idx % 3 == 0 else -18) * (p - 0.5)
    else:
        z, dx = 1.0, 0.0
    ctx.save()
    ctx.translate(W / 2 + dx, H / 2)
    ctx.scale(z, z)
    ctx.translate(-W / 2, -H / 2)
    ctx.set_source_surface(surf, 0, 0)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def draw_frame(ctx, t, T, script, tl, surfs, chunks, outro_len=OUTRO):
    acc = ACCENT.get(script["category"], (1, 0.8, 0.2))
    i = max(k for k, s in enumerate(tl) if s["start"] <= t) if t >= 0 else 0
    s = tl[i]
    seg_len = (s["end"] - s["start"]) + (outro_len if i == len(tl) - 1 else 0)
    p = min(1.0, (t - s["start"]) / seg_len)

    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    if i > 0 and t - s["start"] < FADE:
        prev = tl[i - 1]
        pp = min(1.0, (t - prev["start"]) / (prev["end"] - prev["start"]))
        _paint_image(ctx, surfs[i - 1], pp, i - 1, 1.0)
        _paint_image(ctx, surfs[i], p, i, (t - s["start"]) / FADE)
    else:
        _paint_image(ctx, surfs[i], p, i, 1.0)

    # readability gradients
    for y0, y1, a0, a1 in ((0, 520, 0.65, 0.0), (1050, H, 0.0, 0.75)):
        g = cairo.LinearGradient(0, y0, 0, y1)
        g.add_color_stop_rgba(0, 0, 0, 0, a0)
        g.add_color_stop_rgba(1, 0, 0, 0, a1)
        ctx.rectangle(0, y0, W, y1 - y0)
        ctx.set_source(g)
        ctx.fill()

    # progress bar
    ctx.rectangle(0, 0, W * min(1, t / T), 10)
    ctx.set_source_rgb(*acc)
    ctx.fill()

    # category chip
    _font(ctx, 44)
    lab = script["category"]
    tw = ctx.text_extents(lab).x_advance
    _pill(ctx, W / 2 - tw / 2 - 36, 140, tw + 72, 84, acc, 0.95)
    _font(ctx, 44)
    ctx.move_to(W / 2 - tw / 2, 198)
    ctx.set_source_rgb(0.05, 0.05, 0.08)
    ctx.show_text(lab)
    ctx.new_path()

    speech_end = tl[-1]["start"] + tl[-1]["speech"]
    # hook text (first ~2.6 s)
    if t < 2.6:
        k = min(1.0, t / 0.25)
        a = 1.0 if t < 2.2 else max(0.0, (2.6 - t) / 0.4)
        lines = _wrap(ctx, script["hook_text"].upper(), 96, W - 140)
        ctx.save()
        ctx.translate(W / 2, 600)
        sc = 0.85 + 0.15 * k
        ctx.scale(sc, sc)
        ctx.translate(-W / 2, -600)
        _centered_block(ctx, lines, 600, 96, (1, 1, 1), a)
        ctx.restore()

    # word-by-word captions
    if t < speech_end:
        for ch in chunks:
            if ch[0][1] <= t < ch[-1][2] + 0.05:
                text = " ".join(w for w, _, _ in ch)
                size = 92
                _font(ctx, size)
                while ctx.text_extents(text).x_advance > W - 120 and size > 50:
                    size -= 4
                    _font(ctx, size)
                x = W / 2 - ctx.text_extents(text).x_advance / 2
                pop = min(1.0, (t - ch[0][1]) / 0.12)
                ctx.save()
                ctx.translate(W / 2, 1330)
                ctx.scale(0.9 + 0.1 * pop, 0.9 + 0.1 * pop)
                ctx.translate(-W / 2, -1330)
                for w, a, b in ch:
                    col = (1, 0.88, 0.2) if a <= t < b else (1, 1, 1)
                    _outlined(ctx, w, x, 1330, size, col, 9)
                    _font(ctx, size)
                    x += ctx.text_extents(w + " ").x_advance
                ctx.restore()
                break
    else:
        # outro card
        k = min(1.0, (t - speech_end) / 0.3)
        _rrect(ctx, 70, 1120, W - 140, 330, 44, (0.05, 0.05, 0.1), 0.78 * k)
        lines = _wrap(ctx, script["outro"], 62, W - 220)
        _centered_block(ctx, lines, 1260, 62, (1, 1, 1), k)
        _font(ctx, 40)
        msg = "Comment below  •  Follow for more"
        e = ctx.text_extents(msg)
        _outlined(ctx, msg, W / 2 - e.x_advance / 2, 1410, 40, acc, 5, k)


# ------------------------------------------------------------------ audio
def music_bed(n, seed=0):
    """Original ambient pad + soft arpeggio, generated in code (no copyright)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    roots = rng.choice([[57, 53, 48, 55], [50, 46, 53, 48], [52, 48, 55, 50]])
    bar = 3.2
    out = np.zeros(n, np.float32)
    f = lambda m: 440 * 2 ** ((m - 69) / 12)
    for b in range(int(n / SR / bar) + 1):
        root = roots[b % 4]
        s, e = int(b * bar * SR), min(n, int((b + 1) * bar * SR + SR))
        if s >= n:
            break
        tt = t[s:e] - b * bar
        env = np.minimum(1, tt / 0.8) * np.exp(-np.maximum(0, tt - bar) * 3)
        for iv in (0, 7, 12, 16):
            out[s:e] += 0.05 * env * np.sin(2 * np.pi * f(root + iv) * tt)
        for k, iv in enumerate((12, 19, 24, 19)):
            ps = int((b * bar + k * bar / 4) * SR)
            pe = min(n, ps + int(0.7 * SR))
            if ps < n:
                tp = t[ps:pe] - (b * bar + k * bar / 4)
                out[ps:pe] += 0.03 * np.exp(-tp * 5) * np.sin(2 * np.pi * f(root + iv) * tp)
    return out


def mix_audio(tl, audios, T, path, seed, outro_audio=None):
    n = int(T * SR)
    voice = np.zeros(n, np.float32)
    for s, a in zip(tl, audios):
        i = int(s["start"] * SR)
        voice[i:i + len(a)] += a[: n - i]
    if outro_audio is not None:
        i = int(tl[-1]["end"] * SR)
        voice[i:i + len(outro_audio)] += outro_audio[: n - i]
    voice /= max(1e-6, np.abs(voice).max()) / 0.9
    env = np.convolve(np.abs(voice), np.ones(SR // 10) / (SR // 10), "same")
    duck = 1 - 0.55 * np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
    mus = music_bed(n, seed) * duck
    fade = np.ones(n)
    fade[-SR:] = np.linspace(1, 0, SR)
    mixd = np.clip(voice + mus * 0.6 * fade, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mixd * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ main entry
class ClipReader:
    """Streams a stock clip as 1080x1920 BGRA frames (cropped to fill, looped if too short)."""

    def __init__(self, path, dur):
        self.n = W * H * 4
        self.buf = bytearray(self.n)
        self.surf = cairo.ImageSurface.create_for_data(self.buf, cairo.FORMAT_ARGB32, W, H, W * 4)
        self.p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", path, "-t", f"{dur + 0.5:.2f}", "-an",
             "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                    f"eq=saturation=1.08",
             "-f", "rawvideo", "-pix_fmt", "bgra", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def next(self):
        data = self.p.stdout.read(self.n)
        if data and len(data) == self.n:
            self.buf[:] = data
            self.surf.mark_dirty()
        return self.surf

    def close(self):
        self.p.stdout.close()
        self.p.kill()
        self.p.wait()


def render(script, visuals, audios, out_path, seed=0, outro_audio=None):
    """visuals: list of dict(kind='video'|'image', path=...) — one per scene."""
    outro_len = OUTRO if outro_audio is None else max(OUTRO, len(outro_audio) / SR + 0.9)
    tl, T = build_timeline(script["scenes"], audios, outro_len)
    words = [w for s in tl for w in s["words"]]
    chunks = caption_chunks(words)
    STILL.clear()
    surfs, readers = [], {}
    for i, v in enumerate(visuals):
        if v["kind"] == "video":
            surfs.append(None)
        else:
            STILL.add(i)
            surfs.append(cairo.ImageSurface.create_from_png(v["path"]))
    wav = out_path + ".wav"
    mix_audio(tl, audios, T, wav, seed, outro_audio)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    tmp = out_path + ".video.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    nframes = int(T * FPS)
    for f in range(nframes):
        t = f / FPS
        i = max(k for k, sc in enumerate(tl) if sc["start"] <= t)
        if visuals[i]["kind"] == "video":
            if i not in readers:
                dur = (tl[i]["end"] - tl[i]["start"]) + (outro_len if i == len(tl) - 1 else 0)
                readers[i] = ClipReader(visuals[i]["path"], dur)  # previous clip keeps its last frame for the crossfade
            surfs[i] = readers[i].next()
        draw_frame(ctx, t, T, script, tl, surfs, chunks, outro_len)
        surf.flush()
        ff.stdin.write(bytes(surf.get_data()))
        if f == int(1.2 * FPS):
            surf.write_to_png(out_path.replace(".mp4", "_cover.png"))
    ff.stdin.close()
    for r in readers.values():
        r.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path], check=True)
    os.remove(tmp)
    os.remove(wav)
    return round(T, 2)
