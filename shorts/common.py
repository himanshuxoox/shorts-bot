"""Shared helpers: canvas constants, text drawing, synth audio, ffmpeg render."""
import math, os, re, subprocess, wave

import cairo
import numpy as np

W, H, FPS = 1080, 1920, 60
DT = 1.0 / FPS
FONT = os.environ.get("SHORTS_FONT", "Inter")
SR = 44100


# ------------------------------------------------------------------ text
def _face(ctx, size, bold):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)


def text(ctx, s, x, y, size, rgb=(1, 1, 1), a=1.0, bold=True):
    _face(ctx, size, bold)
    ext = ctx.text_extents(s)
    ctx.move_to(x - (ext.width / 2 + ext.x_bearing), y)
    ctx.set_source_rgba(*rgb, a)
    ctx.show_text(s)
    ctx.new_path()  # drop the current point so the next arc() doesn't draw a stray line


def text_fit(ctx, s, x, y, size, max_w, rgb=(1, 1, 1), a=1.0, bold=True):
    """Centered text that shrinks to fit max_w."""
    _face(ctx, size, bold)
    w = ctx.text_extents(s).width
    if w > max_w:
        size = size * max_w / w
    text(ctx, s, x, y, size, rgb, a, bold)


def rounded(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


# ------------------------------------------------------------------ audio
_SEMI = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)


def note_freq(name: str) -> float:
    m = re.fullmatch(r"([A-G])([#b]?)(\d)", name)
    semi = _SEMI[m.group(1)] + {"#": 1, "b": -1, "": 0}[m.group(2)]
    midi = 12 * (int(m.group(3)) + 1) + semi
    return 440.0 * 2 ** ((midi - 69) / 12)


def _pluck(freq, dur=0.55, vol=0.32):
    n = int(SR * dur)
    t = np.arange(n) / SR
    env = np.exp(-t * 7.0) * np.minimum(1, t / 0.004)
    w = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(4 * np.pi * freq * t)
         + 0.12 * np.sin(6 * np.pi * freq * t))
    return vol * env * w


def build_audio(events, total, path):
    """events: list of (time, freq, kind) with kind in pluck|tick|win."""
    buf = np.zeros(int(SR * (total + 1)))
    for t, f, kind in events:
        i = int(t * SR)
        if kind == "pluck":
            s = _pluck(f)
        elif kind == "tick":
            s = _pluck(f, 0.25, 0.18)
        else:
            s = np.zeros(int(SR * 2.2))
            for j, semi in enumerate([0, 4, 7, 12, 16]):
                p = _pluck(f * 2 ** (semi / 12), 1.6, 0.28)
                o = int(j * 0.09 * SR)
                s[o:o + len(p)] += p[: len(s) - o]
        buf[i:i + len(s)] += s[: len(buf) - i]
    buf = buf / max(1e-9, np.abs(buf).max()) * 0.85
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ video
def render_frames(frames, draw_fn, out_path, audio_path):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    tmp_v = out_path + ".video.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", tmp_v], stdin=subprocess.PIPE)
    for fr in frames:
        draw_fn(ctx, fr)
        surf.flush()
        ff.stdin.write(bytes(surf.get_data()))
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg video encode failed")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_v, "-i", audio_path, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out_path],
                   check=True)
    os.remove(tmp_v)


def save_thumbnail(frame, draw_fn, path):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    draw_fn(cairo.Context(surf), frame)
    surf.write_to_png(path)
