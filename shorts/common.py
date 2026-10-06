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


def _noise_burst(dur=0.35, vol=0.22, seed=0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    w = np.convolve(w, np.ones(3) / 3, mode="same")          # soften the hiss a little
    return vol * w * np.exp(-t * 14) * np.minimum(1, t / 0.002)


def _sweep(f0, f1, dur, vol):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return vol * np.sin(ph) * np.exp(-t * 3.5) * np.minimum(1, t / 0.004)


def build_audio(events, total, path, min_gap=0.0):
    """events: list of (time, freq, kind).
    kinds: pluck | tick | win | shatter (ring break) | steal (short blip) | out (falling tone) | chime"""
    buf = np.zeros(int(SR * (total + 1)))
    last_pluck = -9.0
    for t, f, kind in sorted(events, key=lambda e: e[0]):
        i = int(t * SR)
        if kind == "pluck":
            if t - last_pluck < min_gap:      # very fast bounce streams would turn into noise
                continue
            last_pluck = t
            s = _pluck(f)
        elif kind == "tick":
            s = _pluck(f, 0.25, 0.18)
        elif kind == "shatter":
            s = _noise_burst(0.4, 0.28, int(t * 1000))
            for j, semi in enumerate([0, 7, 12]):
                p = _pluck(f * 2 ** (semi / 12), 0.7, 0.2)
                o = int(j * 0.04 * SR)
                s = np.pad(s, (0, max(0, o + len(p) - len(s))))
                s[o:o + len(p)] += p
        elif kind == "steal":
            s = _pluck(f, 0.18, 0.16)
        elif kind == "out":
            s = _sweep(f, f / 2.5, 0.6, 0.3)
        elif kind == "pop":
            s = _noise_burst(0.12, 0.2, int(t * 1000) + 7)
            p = _pluck(f, 0.3, 0.22)
            s = np.pad(s, (0, max(0, len(p) - len(s))))
            s[:len(p)] += p
        elif kind == "chime":
            s = _pluck(f, 1.0, 0.3)
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
def render_frames(frames, draw_fn, out_path, audio_path, loop_s=0.0):
    """Render frames to an mp4. loop_s > 0 adds a short cross-fade from the last frame back
    to the first one, so when Shorts replays the video it loops seamlessly (more watch time)."""
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
    n_loop = int(round(loop_s * FPS))
    if n_loop:
        last = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        lc = cairo.Context(last)
        lc.set_source_surface(surf, 0, 0)
        lc.paint()
        first = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        draw_fn(cairo.Context(first), frames[0])
        for k in range(1, n_loop + 1):
            ctx.set_source_surface(last, 0, 0)
            ctx.paint()
            ctx.set_source_surface(first, 0, 0)
            ctx.paint_with_alpha(k / n_loop)
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
