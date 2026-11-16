"""
"Every bounce plays Flight of the Bumblebee… at 2x speed": the shrink format (every bounce shrinks
the ball and grows the wall) with a ball twice as fast, so the notes come twice as fast and the
famous chromatic buzz (Rimsky-Korsakov, 1900: public domain) rushes faster as space runs out.
"""
import random

from . import fx, melodies, shrink
from .shrink import Config, simulate, draw, audio_events, AUDIO_MIN_GAP  # noqa: F401  (the batch interface)

TUNE = "Flight of the Bumblebee"
TITLES = [
    [[("Every bounce plays ", fx.WHITE), ("BUMBLEBEE", fx.GOLD)], [("at ", fx.WHITE), ("2x SPEED", fx.CYAN)]],
    [[("The ball is ", fx.WHITE), ("2x FASTER", fx.CYAN)], [("Can you keep up with the ", fx.WHITE), ("SONG?", fx.GOLD)]],
    [[("Every bounce = ", fx.WHITE), ("1 NOTE", fx.GOLD)], [("Now at ", fx.WHITE), ("DOUBLE SPEED", fx.CYAN)]],
]


def make_config(seed):
    rng = random.Random(seed * 5531 + 7)
    col, hi = rng.choice(shrink.PALETTES)
    return Config(seed, rng.uniform(34, 44), rng.uniform(0.987, 0.991), rng.uniform(40, 52),
                  shrink.math.radians(rng.uniform(10, 14)), col, hi, TUNE, melodies.MELODIES[TUNE],
                  speed=shrink.SPEED * 2, title=rng.choice(TITLES), tag="bumblebee")


def is_good(res):
    return res["t_end"] is not None and 17 <= res["t_end"] <= 30 and res["bounces"] >= 120


def metadata_facts(res, cfg):
    return shrink.metadata_facts(res, cfg)
