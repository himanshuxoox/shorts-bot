"""Scene images: Pollinations.ai (free FLUX) with a generated fallback so a video never fails."""
import io, math, os, random, time, urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
TOKEN = os.environ.get("POLLINATIONS_TOKEN", "")      # optional: free account = no watermark, faster
MOCK = os.environ.get("IMAGES", "") == "mock"
_last = [0.0]


def _pollinations(prompt, seed):
    q = urllib.parse.quote(prompt[:900])
    url = (f"https://image.pollinations.ai/prompt/{q}?width={W}&height={H}"
           f"&model=flux&nologo=true&private=true&seed={seed}")
    headers = {"User-Agent": "shorts-bot"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    gap = 3 if TOKEN else 16                        # anonymous: ~1 request / 15 s
    wait = gap - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    r = requests.get(url, headers=headers, timeout=180)
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError("not an image")
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def fallback(prompt, seed):
    """Abstract glowing artwork, coloured by the prompt — used if the image API is down."""
    rng = random.Random(f"{prompt}{seed}")
    hue = rng.random()
    import colorsys
    c1 = [int(255 * v) for v in colorsys.hsv_to_rgb(hue, 0.7, 0.25)]
    c2 = [int(255 * v) for v in colorsys.hsv_to_rgb((hue + 0.15) % 1, 0.8, 0.9)]
    img = Image.new("RGB", (W, H), tuple(c1))
    d = ImageDraw.Draw(img)
    for _ in range(14):
        x, y, r = rng.randint(0, W), rng.randint(0, H), rng.randint(60, 420)
        a = rng.uniform(0.15, 0.5)
        col = tuple(int(c1[i] * (1 - a) + c2[i] * a) for i in range(3))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    return img.filter(ImageFilter.GaussianBlur(40))


def get(prompt, seed, path):
    img = None
    if not MOCK:
        for attempt in range(3):
            try:
                img = _pollinations(prompt + ", vertical 9:16, highly detailed, no text", seed + attempt)
                break
            except Exception as e:
                print(f"   image attempt {attempt + 1} failed: {e}")
                time.sleep(10 * (attempt + 1))
    if img is None:
        img = fallback(prompt, seed)
    # cover-crop to 9:16
    s = max(W / img.width, H / img.height)
    img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    l, t = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((l, t, l + W, t + H))
    img.save(path)
    return path
