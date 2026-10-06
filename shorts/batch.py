"""
Render today's batch of Shorts — one video per format in LINEUP.

    python -m shorts.batch --count 4                # -> out/<date>/*.mp4 + manifest + UPLOAD_SHEET
    python -m shorts.batch --count 1 --date test    # quick test
    FORMATS=rings,paint python -m shorts.batch      # choose formats

Formats: crush (press splits balls into 3), shrink (ball shrinks, wall grows), devour (black hole
vs multiplying swarm), butterfly (butterfly effect + spikes), evolve (rainbow growing ball),
multiply (multiplier tokens + breakable rings), paint (color battle), elim (elimination), rings
(multi-ring escape), grow (growing ball), escape (the original single-ring race).
The lineup rotates day by day, so with 4 videos/day every format comes back regularly.
With TRENDS=on, one video a day (paint or elim) uses safe trending words from
state/trends.json as ball names (see shorts/trends.py).
Seeds come from state/history.json so no video is ever repeated.
"""
import argparse, datetime as dt, json, os, time
from multiprocessing import Pool
from zoneinfo import ZoneInfo

import random

from . import (escape, rings, grow, paint, elim, butterfly, evolve, multiply, shrink, devour, crush,
               metadata, trends)
from .common import FPS, build_audio, render_frames, save_thumbnail

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "history.json")
IST = ZoneInfo("Asia/Kolkata")
MODS = dict(butterfly=butterfly, evolve=evolve, multiply=multiply, shrink=shrink, devour=devour,
            crush=crush, paint=paint, elim=elim, rings=rings, grow=grow, escape=escape)
DEFAULT_LINEUP = ("crush,butterfly,shrink,multiply,devour,evolve,paint,"
                  "crush,butterfly,shrink,multiply,devour,evolve,elim")
LOOP_S = 0.4                 # cross-fade back to frame 0 so replays loop seamlessly
LINEUP = [f.strip() for f in (os.environ.get("FORMATS") or DEFAULT_LINEUP).split(",") if f.strip()]
LABEL_FORMATS = {"paint": 4, "elim": 4}          # formats that can show trend words as names
TREND_VIDEOS = int(os.environ.get("TREND_VIDEOS", "1"))


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"next_seed": 1000, "videos": []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1)


def make_config(mod, seed, labels):
    return mod.make_config(seed, labels=labels) if labels else mod.make_config(seed)


def find_seed(mod, start, labels=None, max_tries=6000):
    """First seed at or after `start` whose simulation passes the format's is_good()."""
    for s in range(start, start + max_tries):
        if mod.is_good(mod.simulate(make_config(mod, s, labels))):
            return s
    raise RuntimeError(f"no good seed found for {mod.__name__}")


def render_one(args):
    fmt, seed, out_dir, idx, labels = args
    mod = MODS[fmt]
    t0 = time.time()
    cfg = make_config(mod, seed, labels)
    res = mod.simulate(cfg, record=True)
    if hasattr(mod, "prepare"):
        mod.prepare(res, cfg)
    frames = res["frames"]
    base = os.path.join(out_dir, f"{idx:02d}_{fmt}_{seed}")
    wav = base + ".wav"
    build_audio(mod.audio_events(res, cfg), len(frames) / FPS + LOOP_S, wav,
                min_gap=getattr(mod, "AUDIO_MIN_GAP", 0.0))
    draw = lambda ctx, fr: mod.draw(ctx, fr, cfg)
    render_frames(frames, draw, base + ".mp4", wav, loop_s=LOOP_S)
    os.remove(wav)
    save_thumbnail(frames[int(len(frames) * 0.45)], draw, base + "_cover.png")
    facts = mod.metadata_facts(res, cfg)
    meta = metadata.build(facts, seed)
    item = dict(format=fmt, seed=seed, file=os.path.basename(base + ".mp4"),
                cover=os.path.basename(base + "_cover.png"),
                duration=round(len(frames) / FPS + LOOP_S, 2), facts=facts, **meta)
    with open(base + ".json", "w") as f:
        json.dump(item, f, indent=1, ensure_ascii=False)
    print(f"[{idx}] {fmt} seed={seed} {item['duration']}s ({time.time() - t0:.0f}s)  {meta['title']}",
          flush=True)
    return item


def dedupe_titles(items, out_dir, recent=()):
    """No two videos in the batch share a title style, and no title repeats a recent one."""
    seen = set()
    for it in items:
        k = 1
        while (it.get("title_style") in seen or it["title"] in recent) and k < 40:
            it.update(metadata.build(it["facts"], it["seed"] + 1000 * k))
            k += 1
        seen.add(it.get("title_style"))
        with open(os.path.join(out_dir, it["file"].replace(".mp4", ".json")), "w") as f:
            json.dump(it, f, indent=1, ensure_ascii=False)


def upload_sheet(items, path):
    L = []
    for v in items:
        L += ["=" * 60, v["file"], "=" * 60, "TITLE:", v["title"], "", "DESCRIPTION:", v["description"],
              "", "TAGS:", ", ".join(v["tags"]), "",
              "Made for kids: NO  |  Category: Entertainment  |  Altered/synthetic content: NO", "", ""]
    with open(path, "w") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=len(LINEUP))
    ap.add_argument("--date", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    a = ap.parse_args()
    for f in LINEUP:
        if f not in MODS:
            raise SystemExit(f"unknown format {f!r}; choose from {', '.join(MODS)}")

    st = load_state()
    pos = st.get("lineup_pos", 0)
    fmts = [LINEUP[(pos + i) % len(LINEUP)] for i in range(a.count)]

    # trend words: only words that passed every check today (state/trends.json)
    words = trends.todays_words() if os.environ.get("TRENDS", "off") == "on" else []
    rng = random.Random(a.date)
    labels = [None] * len(fmts)
    budget = TREND_VIDEOS
    for i, f in enumerate(fmts):
        if budget and f in LABEL_FORMATS:
            pick = trends.take(words, LABEL_FORMATS[f], rng)
            if pick:
                labels[i] = pick
                budget -= 1
                print(f"[trends] video {i + 1} ({f}) uses: {', '.join(pick)}")

    start = st["next_seed"]
    seeds, used = [], set()
    for f, lb in zip(fmts, labels):
        s = find_seed(MODS[f], start, lb)
        while (f, s) in used:                    # same format twice in one batch
            s = find_seed(MODS[f], s + 1, lb)
        used.add((f, s))
        seeds.append(s)
    out_dir = os.path.join(a.out, a.date)
    os.makedirs(out_dir, exist_ok=True)

    jobs = [(f, s, out_dir, i + 1, lb) for i, (f, s, lb) in enumerate(zip(fmts, seeds, labels))]
    if a.workers > 1:
        with Pool(a.workers) as p:
            items = p.map(render_one, jobs)
    else:
        items = [render_one(j) for j in jobs]

    dedupe_titles(items, out_dir, recent={v["title"] for v in st["videos"][-24:]})
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(dict(date=a.date, videos=items), f, indent=1, ensure_ascii=False)
    upload_sheet(items, os.path.join(out_dir, "UPLOAD_SHEET.txt"))

    st["next_seed"] = max(seeds) + 1
    st["lineup_pos"] = (pos + a.count) % len(LINEUP)
    st["videos"] += [dict(date=a.date, format=i["format"], seed=i["seed"], title=i["title"]) for i in items]
    save_state(st)
    print(f"done: {len(items)} videos in {out_dir}")


if __name__ == "__main__":
    main()
