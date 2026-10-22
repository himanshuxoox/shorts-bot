"""
ManimGL (3Blue1Brown's manim) formats, plugged into the normal batch as "render_video" formats.

Each format runs one scene from mgl/ in a separate process:
    python -m manimlib mgl/<file>.py <Scene> -w -r 1080x1920 --fps 60
(under xvfb-run when there is no screen, e.g. on GitHub Actions), then adds the sound from the
events the scene recorded (shorts/mgl_audio.py), re-encodes, and saves a cover frame.
The seed goes in through MGL_SEED, so every seed is a different (but repeatable) video.
"""
import json, os, shutil, subprocess, sys, tempfile
from dataclasses import dataclass

from . import mgl_audio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MGL_DIR = os.path.join(ROOT, "mgl")
RES = os.environ.get("MGL_RES", "1080x1920")
FPS = os.environ.get("MGL_FPS", "60")


@dataclass
class Config:
    seed: int


def _duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


class _MglFormat:
    def __init__(self, key, file, scene):
        self.key, self.file, self.scene = key, file, scene
        self.__name__ = key

    # --- the batch interface (seeds never fail: every seed makes a good video)
    def make_config(self, seed):
        return Config(seed)

    def simulate(self, cfg, record=False):
        return {}

    def is_good(self, res):
        return True

    def render_video(self, cfg, base):
        tmp = tempfile.mkdtemp(prefix=f"mgl_{self.key}_")
        events = os.path.join(tmp, "events.json")
        env = dict(os.environ, MGL_SEED=str(cfg.seed), MGL_EVENTS=events,
                   PYTHONPATH=MGL_DIR + os.pathsep + os.environ.get("PYTHONPATH", ""))
        cmd = [sys.executable, "-m", "manimlib", os.path.join(MGL_DIR, self.file), self.scene, "-w",
               "-r", RES, "--fps", FPS, "--video_dir", tmp, "--file_name", "silent"]
        if not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 2000x2000x24"] + cmd
        log = os.path.join(tmp, "manim.log")
        with open(log, "w") as lf:
            r = subprocess.run(cmd, cwd=MGL_DIR, env=env, stdout=lf, stderr=subprocess.STDOUT)
        silent = os.path.join(tmp, "silent.mp4")
        if r.returncode != 0 or not os.path.exists(silent):
            print(open(log).read()[-3000:], file=sys.stderr)
            raise RuntimeError(f"manim failed for {self.key} seed {cfg.seed}")
        wav = os.path.join(tmp, "audio.wav")
        meta, _total = mgl_audio.make_wav(events, wav)
        out = base + ".mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", wav, "-c:v", "libx264", "-preset", "medium",
                        "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", out], check=True)
        dur = _duration(out)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * 0.8:.2f}", "-i", out, "-frames:v", "1",
                        base + "_cover.png"], check=True)
        shutil.rmtree(tmp, ignore_errors=True)
        return dict(meta=meta), round(dur, 2)

    def metadata_facts(self, res, cfg):
        meta = res.get("meta", {})
        return dict(template=self.key, colors=[], melody="", n_balls=meta.get("N") or meta.get("n") or "",
                    n_final=meta.get("N") or 0, meta=meta)


FORMATS = {
    "fourier": _MglFormat("fourier", "fourier.py", "Fourier"),
    "dpendulum": _MglFormat("dpendulum", "chaos.py", "Chaos"),
    "lorenz": _MglFormat("lorenz", "lorenz.py", "Lorenz"),
    "chaosgame": _MglFormat("chaosgame", "chaos_game.py", "ChaosGame"),
    "timestable": _MglFormat("timestable", "times_table.py", "TimesTable"),
    "primespiral": _MglFormat("primespiral", "primes.py", "Primes"),
    "threebody": _MglFormat("threebody", "threebody.py", "ThreeBody"),
    "metronomes": _MglFormat("metronomes", "metronomes.py", "Metronomes"),
    "galton": _MglFormat("galton", "galton.py", "Galton"),
    "chladni": _MglFormat("chladni", "chladni.py", "Chladni"),
}
