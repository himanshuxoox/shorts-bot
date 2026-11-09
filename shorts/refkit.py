"""Small shared pieces for the compilation-style formats (sides, arms, spiral, predator, breakout,
quadsplit, redring, sortwheel): a two-line caption whose CAPITAL words are gold / cyan, polygon
names (triangle … dihectakaidodecagon) and a stat line."""
import re

from . import fx
from .common import text

GOLD = fx.GOLD
CYAN = fx.CYAN
WHITE = (1.0, 1.0, 1.0)


def caption(ctx, s, y=280, size=60, accent=GOLD, colors=None):
    """'Every bounce adds a SIDE | Can the triangle become a CIRCLE?'  ('|' = line break).
    Words written in CAPITALS (2+ letters) are drawn in the accent colour, or in colors[word]."""
    colors = colors or {}
    lines = []
    for part in s.split("|"):
        segs = []
        for w in part.strip().split(" "):
            core = re.sub(r"[^A-Za-z]", "", w)
            col = (colors.get(core) or accent) if len(core) >= 2 and core.isupper() else WHITE
            segs.append((w + " ", col))
        lines.append(segs)
    fx.rich_title(ctx, lines, y=y, size=size)


def stat(ctx, label, value, y=1560, size=56, col=GOLD):
    text(ctx, f"{label}{value}", 540, y, size, col, 0.95)


_UNITS = {1: "hena", 2: "di", 3: "tri", 4: "tetra", 5: "penta", 6: "hexa", 7: "hepta", 8: "octa", 9: "ennea"}
_TENS = {2: "icosi", 3: "triaconta", 4: "tetraconta", 5: "pentaconta", 6: "hexaconta", 7: "heptaconta",
         8: "octaconta", 9: "enneaconta"}
_SMALL = {3: "triangle", 4: "square", 5: "pentagon", 6: "hexagon", 7: "heptagon", 8: "octagon", 9: "nonagon",
          10: "decagon", 11: "hendecagon", 12: "dodecagon", 20: "icosagon", 100: "hectogon"}


def polygon_name(n):
    """Greek name of an n-gon (3 … 999), e.g. 17 -> HEPTADECAGON, 212 -> DIHECTAKAIDODECAGON."""
    if n in _SMALL:
        return _SMALL[n].upper()
    h, rest = divmod(n, 100)
    t, u = divmod(rest, 10)
    out = ""
    if h:
        out += ("" if h == 1 else _UNITS[h]) + "hecta"
        if rest and t <= 1:
            out += "kai"
    if rest:
        if rest < 10:
            out += {1: "hena", 2: "di"}.get(u, _UNITS[u]) + "gon"
            return out.upper()
        if t == 1:
            out += {1: "hen", 2: "do"}.get(u, _UNITS.get(u, "")) + "decagon"
            return out.upper()
        out += _TENS[t]
        if u:
            out += "kai" + _UNITS[u]
        out += "gon"
    else:
        out += "gon"
    return out.upper()
