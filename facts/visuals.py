"""
Scene visuals. Tried in VISUAL_ORDER (default "pexels,pixabay,pollinations"), then a generated
abstract image as the last resort, so a video never fails:
  pexels       - stock video/photo   (needs PEXELS_API_KEY; new keys are paused right now)
  pixabay      - stock video          (needs PIXABAY_API_KEY, free)
  pollinations - AI image (FLUX). Anonymous endpoint first (free but flaky, often 402 then OK on
                 retry); uses the paid gen.pollinations.ai if POLLINATIONS_TOKEN is set.
"""
import io, math, os, random, time, urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
POLL_TOKEN = os.environ.get("POLLINATIONS_TOKEN", "")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "")
ORDER = [x.strip() for x in os.environ.get("VISUAL_ORDER", "pexels,pixabay,pollinations").split(",")]
_last = [0.0]
MOCK = os.environ.get("IMAGES", "") == "mock"
UA = {"User-Agent": "shorts-bot"}


# ------------------------------------------------------------------ Pexels
def _pexels(path, params):
    r = requests.get(f"https://api.pexels.com{path}", params=params,
                     headers={"Authorization": PEXELS_KEY, **UA}, timeout=30)
    r.raise_for_status()
    return r.json()


def pexels_video(query, min_dur, used):
    data = _pexels("/videos/search", dict(query=query, orientation="portrait", size="medium", per_page=15))
    for v in data.get("videos", []):
        if v["id"] in used or v.get("duration", 0) < min(min_dur, 6):
            continue
        files = [f for f in v.get("video_files", [])
                 if f.get("width") and f.get("height") and f["height"] > f["width"]
                 and 1280 <= f["height"] <= 2160 and f.get("file_type") == "video/mp4"]
        if not files:
            continue
        f = min(files, key=lambda f: abs(f["height"] - 1920))
        used.add(v["id"])
        return dict(url=f["link"], id=v["id"], credit=v.get("user", {}).get("name", "Pexels"))
    return None


def pexels_photo(query, used):
    data = _pexels("/v1/search", dict(query=query, orientation="portrait", size="large", per_page=15))
    for p in data.get("photos", []):
        if p["id"] in used:
            continue
        used.add(p["id"])
        return dict(url=p["src"]["portrait"], id=p["id"], credit=p.get("photographer", "Pexels"))
    return None


def pixabay_video(query, min_dur, used):
    r = requests.get("https://pixabay.com/api/videos/", headers=UA, timeout=30,
                     params=dict(key=PIXABAY_KEY, q=query[:100], per_page=20, safesearch="true",
                                 video_type="film"))
    r.raise_for_status()
    for h in r.json().get("hits", []):
        if f"pb{h['id']}" in used or h.get("duration", 0) < min(min_dur, 6):
            continue
        vids = [v for v in h.get("videos", {}).values() if v.get("url") and v.get("height", 0) >= 720]
        if not vids:
            continue
        # prefer portrait, then the size closest to 1920 tall
        v = min(vids, key=lambda v: (v["width"] > v["height"], abs(max(v["height"], v["width"]) - 1920)))
        used.add(f"pb{h['id']}")
        return dict(url=v["url"], credit=h.get("user", "Pixabay"))
    return None


def _download(url, path):
    with requests.get(url, headers=UA, timeout=180, stream=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return path


# ------------------------------------------------------------------ AI image / fallback
def _pollinations(prompt, seed):
    q = urllib.parse.quote(prompt[:800])
    if POLL_TOKEN:
        url = f"https://gen.pollinations.ai/image/{q}"
        headers = {"Authorization": f"Bearer {POLL_TOKEN}", **UA}
    else:
        url = f"https://image.pollinations.ai/prompt/{q}"
        headers = UA
        wait = 16 - (time.time() - _last[0])        # anonymous: ~1 request / 15 s
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    r = requests.get(url, params=dict(width=W, height=H, model="flux", nologo="true",
                                      private="true", seed=seed), headers=headers, timeout=180)
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError("not an image")
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def fallback_art(prompt, seed):
    import colorsys
    rng = random.Random(f"{prompt}{seed}")
    hue = rng.random()
    c1 = [int(255 * v) for v in colorsys.hsv_to_rgb(hue, 0.7, 0.25)]
    c2 = [int(255 * v) for v in colorsys.hsv_to_rgb((hue + 0.15) % 1, 0.8, 0.9)]
    img = Image.new("RGB", (W, H), tuple(c1))
    d = ImageDraw.Draw(img)
    for _ in range(14):
        x, y, r = rng.randint(0, W), rng.randint(0, H), rng.randint(60, 420)
        a = rng.uniform(0.15, 0.5)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(c1[i] * (1 - a) + c2[i] * a) for i in range(3)))
    return img.filter(ImageFilter.GaussianBlur(40))


def _save_cover(img, path):
    s = max(W / img.width, H / img.height)
    img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
    l, t = (img.width - W) // 2, (img.height - H) // 2
    img.crop((l, t, l + W, t + H)).save(path)
    return path


# ------------------------------------------------------------------ main entry
def get(scene, seed, base, min_dur, used):
    """Returns dict(kind='video'|'image', path=..., source='pexels'|'pixabay'|'ai'|'art', credit=...)."""
    queries = [q for q in [scene.get("visual_query"), *(scene.get("visual_alts") or [])] if q]
    if not MOCK:
        for src in ORDER:
            if src == "pexels" and PEXELS_KEY:
                for q in queries:
                    try:
                        v = pexels_video(q, min_dur, used)
                        if v:
                            return dict(kind="video", path=_download(v["url"], base + ".mp4"),
                                        source="pexels", credit=v["credit"])
                    except Exception as e:
                        print(f"   pexels '{q}' failed: {e}")
            elif src == "pixabay" and PIXABAY_KEY:
                for q in queries:
                    try:
                        v = pixabay_video(q, min_dur, used)
                        if v:
                            return dict(kind="video", path=_download(v["url"], base + ".mp4"),
                                        source="pixabay", credit=v["credit"])
                    except Exception as e:
                        print(f"   pixabay '{q}' failed: {e}")
            elif src == "pollinations":
                for attempt in range(4):
                    try:
                        img = _pollinations(scene["image_prompt"] + ", vertical 9:16, highly detailed, "
                                            "no text", seed + attempt)
                        return dict(kind="image", path=_save_cover(img, base + ".png"), source="ai", credit=None)
                    except Exception as e:
                        print(f"   pollinations attempt {attempt + 1} failed: {e}")
                        time.sleep(5)
    return dict(kind="image", path=_save_cover(fallback_art(scene.get("image_prompt", ""), seed), base + ".png"),
                source="art", credit=None)
