"""
Render today's batch of Shorts.

    python -m shorts.batch --count 4                # -> out/2026-10-02/*.mp4 + manifest.json
    python -m shorts.batch --count 1 --date test    # quick test

Seeds are taken from state/history.json so no video is ever repeated.
"""
import argparse, datetime as dt, json, os, time
from multiprocessing import Pool
from zoneinfo import ZoneInfo

from . import escape, metadata
from .common import FPS, build_audio, render_frames, save_thumbnail

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "history.json")
BALL_MIX = [2, 3, 2, 4]          # ball counts for the day's videos, in order
IST = ZoneInfo("Asia/Kolkata")


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"next_seed": 1000, "videos": []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1)


def pick_seeds(start, wanted_counts, max_tries=20000):
    """Find seeds whose race is 'good' and matches the wanted ball counts."""
    picks, s = [], start
    for n in wanted_counts:
        for _ in range(max_tries):
            cfg = escape.make_config(s)
            s += 1
            if len(cfg.names) != n:
                continue
            res = escape.simulate(cfg)
            if escape.is_good(res):
                picks.append(cfg.seed)
                break
        else:
            raise RuntimeError(f"no good seed found for {n} balls")
    return picks, s


def render_one(args):
    seed, out_dir, idx = args
    t0 = time.time()
    cfg = escape.make_config(seed)
    res = escape.simulate(cfg, record=True)
    frames = res["frames"]
    base = os.path.join(out_dir, f"{idx:02d}_escape_{seed}")
    wav = base + ".wav"
    build_audio(escape.audio_events(res, cfg), len(frames) / FPS, wav)
    draw = lambda ctx, fr: escape.draw(ctx, fr, cfg)
    render_frames(frames, draw, base + ".mp4", wav)
    os.remove(wav)
    save_thumbnail(frames[int(len(frames) * 0.4)], draw, base + "_cover.png")
    facts = escape.metadata_facts(res, cfg)
    meta = metadata.build(facts, seed)
    item = dict(seed=seed, file=os.path.basename(base + ".mp4"),
                cover=os.path.basename(base + "_cover.png"),
                duration=round(len(frames) / FPS, 2), facts=facts, **meta)
    with open(base + ".json", "w") as f:
        json.dump(item, f, indent=1, ensure_ascii=False)
    print(f"[{idx}] seed={seed} {facts['n_balls']} balls winner={facts['winner']} "
          f"{item['duration']}s  ({time.time() - t0:.0f}s)  {meta['title']}", flush=True)
    return item


def dedupe_titles(items, out_dir, recent=()):
    """Make sure no two videos in the batch (or the last few days) share a title template."""
    seen = set()
    for it in items:
        k = 1
        while (it.get("title_style") in seen or it["title"] in recent) and k < 40:
            it.update(metadata.build(it["facts"], it["seed"] + 1000 * k))
            k += 1
        seen.add(it.get("title_style"))
        with open(os.path.join(out_dir, it["file"].replace(".mp4", ".json")), "w") as f:
            json.dump(it, f, indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--date", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    a = ap.parse_args()

    st = load_state()
    wanted = [BALL_MIX[(len(st["videos"]) + i) % len(BALL_MIX)] for i in range(a.count)]
    seeds, nxt = pick_seeds(st["next_seed"], wanted)
    out_dir = os.path.join(a.out, a.date)
    os.makedirs(out_dir, exist_ok=True)

    jobs = [(s, out_dir, i + 1) for i, s in enumerate(seeds)]
    if a.workers > 1:
        with Pool(a.workers) as p:
            items = p.map(render_one, jobs)
    else:
        items = [render_one(j) for j in jobs]

    dedupe_titles(items, out_dir, recent={v["title"] for v in st["videos"][-12:]})
    manifest = dict(date=a.date, videos=items)
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)

    st["next_seed"] = nxt
    st["videos"] += [dict(date=a.date, seed=i["seed"], title=i["title"]) for i in items]
    save_state(st)
    print(f"done: {len(items)} videos in {out_dir}")


if __name__ == "__main__":
    main()
