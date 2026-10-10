"""
One-time tool: cut the ball faces out of the "<Color> Ball – 30 Emotions" character sheets
into small transparent PNG sprites used by the battle-royale format.

    python tools/extract_sprites.py <folder with the sheets> assets/balls

Each sheet is a 10 x 3 grid. In every cell the ball is found with a Hough circle search and
cut out with a soft round mask, so the label, the glow ring and the background are dropped.
"""
import os, sys, glob

import cv2
import numpy as np

COLORS = ["blue", "red", "purple", "green", "yellow", "orange", "pink", "cyan", "white", "black"]
# 1-based positions on the sheets -> sprite names
EMOTIONS = {1: "happy", 2: "excited", 3: "determined", 4: "angry", 6: "crying", 8: "shocked",
            9: "scared", 13: "proud", 15: "focused", 19: "laughing", 21: "teasing", 22: "victory",
            23: "defeated", 25: "nervous", 30: "hyped"}
SIZE = 192


def cells(img):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cw = w / 10.0
    out = {}
    for c in range(10):
        x0, x1 = int(c * cw), int((c + 1) * cw)
        strip = cv2.GaussianBlur(gray[110:, x0:x1], (5, 5), 1.5)
        found = cv2.HoughCircles(strip, cv2.HOUGH_GRADIENT, dp=1.2, minDist=200, param1=90,
                                 param2=28, minRadius=55, maxRadius=82)
        if found is None:
            continue
        circ = sorted(found[0].tolist(), key=lambda v: v[1])
        rows = []
        for cx, cy, r in circ:                       # one circle per row band
            if all(abs(cy - ry) > 180 for _, ry, _ in rows):
                rows.append((cx, cy, r))
        for i, (cx, cy, r) in enumerate(sorted(rows, key=lambda v: v[1])[:3]):
            out[i * 10 + c + 1] = (x0 + cx, 110 + cy, r)
    return out


def cut(img, cx, cy, r):
    r = r * 1.04
    x0, y0 = int(cx - r), int(cy - r)
    d = int(2 * r)
    crop = img[max(0, y0):y0 + d, max(0, x0):x0 + d]
    crop = cv2.resize(crop, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    dist = np.hypot(xx - SIZE / 2 + 0.5, yy - SIZE / 2 + 0.5) / (SIZE / 2)
    alpha = np.clip((1.0 - dist) / 0.04, 0, 1)          # soft 4 % edge
    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return rgba


def main(src, dst):
    for color in COLORS:
        sheet = [p for p in glob.glob(os.path.join(src, "*.png")) if os.path.basename(p).lower().startswith(color)]
        if not sheet:
            print("missing sheet for", color)
            continue
        img = cv2.imread(sheet[0])
        found = cells(img)
        os.makedirs(os.path.join(dst, color), exist_ok=True)
        got = 0
        for idx, name in EMOTIONS.items():
            if idx in found:
                cv2.imwrite(os.path.join(dst, color, f"{name}.png"), cut(img, *found[idx]))
                got += 1
        print(f"{color:7s} {got}/{len(EMOTIONS)} emotions  ({len(found)} balls detected)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
