"""
Daily batch for the facts channel.

    GEMINI_API_KEY=... python -m facts.batch --count 4
    python -m facts.batch --count 1 --mock        # offline test: canned script, fake voice/images

Output: out_facts/<date>/NN_<kind>.mp4 + .json + _cover.png, manifest.json, UPLOAD_SHEET.txt
"""
import argparse, datetime as dt, json, os, random, time, traceback
from zoneinfo import ZoneInfo

from . import images, render, voice

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "facts_history.json")
IST = ZoneInfo("Asia/Kolkata")
# the day's lineup (AI news removed on request)
LINEUP = ["discovery", "explainer", "fun", "money"]
HASHTAGS = {"AI NEWS": "#ai #technews #artificialintelligence",
            "NEW DISCOVERY": "#science #discovery #space",
            "SCIENCE EXPLAINED": "#science #howitworks #learn",
            "FUN FACT": "#facts #funfacts #didyouknow",
            "MONEY SCIENCE": "#money #psychology #economics"}

MOCK_SCRIPT = {
    "title": "Your body glows in the dark (you just can't see it)",
    "hook_text": "You are glowing right now",
    "scenes": [
        {"narration": "Right now, your body is literally glowing.",
         "image_prompt": "human silhouette softly glowing in a dark room, cinematic"},
        {"narration": "Scientists in Japan filmed people with ultra sensitive cameras and caught a faint light coming from their skin.",
         "image_prompt": "ultra sensitive camera in a dark lab, blue light"},
        {"narration": "It is about a thousand times weaker than what your eyes can detect.",
         "image_prompt": "human eye close up in darkness, faint glow"},
        {"narration": "The glow comes from chemical reactions in your cells, the same kind of chemistry that makes fireflies shine.",
         "image_prompt": "fireflies glowing over a field at night, magical"},
        {"narration": "And it changes during the day, with the face glowing brightest in the late afternoon.",
         "image_prompt": "sunset light over a city, warm cinematic glow"},
    ],
    "outro": "Did you know you were glowing?",
    "description": "Humans emit a tiny amount of visible light called biophotons, far too dim for our eyes.",
    "tags": ["science", "facts", "human body", "bioluminescence", "biophotons"],
    "confidence": "high",
}


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"videos": []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)


def make_meta(script):
    title = script["title"].strip().rstrip(".")[:88] + " #shorts"
    desc = [script.get("description", "").strip(), "",
            f"💬 {script['outro']}", ""]
    if script.get("source"):
        desc += [f"Source: {script['source']['name']} — {script['source']['link']}", ""]
    if script["category"] == "MONEY SCIENCE":
        desc += ["Educational content only — not financial advice.", ""]
    desc += ["Visuals are AI-generated illustrations. Narration is an AI voice.",
             "New science & AI shorts every day — subscribe! 🔔", "",
             f"#shorts {HASHTAGS.get(script['category'], '#facts')}"]
    tags = [t.lower() for t in script.get("tags", [])][:12] + ["shorts", "facts", "science"]
    return dict(title=title, description="\n".join(desc), tags=list(dict.fromkeys(tags)),
                categoryId="28", containsSyntheticMedia=True)


def make_one(kind, idx, out_dir, history, rng, mock):
    t0 = time.time()
    if mock:
        from .writer import CATEGORY_LABEL
        script = dict(MOCK_SCRIPT, kind="fun", category=CATEGORY_LABEL["fun"], topic="mock", source=None)
    else:
        from . import writer
        script = writer.write(kind, history, rng)
    if script.get("confidence") == "low":
        raise RuntimeError("fact-check confidence low — skipped")
    base = os.path.join(out_dir, f"{idx:02d}_{script['kind']}")
    seed = rng.randint(1, 10 ** 6)

    audios = [voice.speak(sc["narration"]) for sc in script["scenes"]]
    outro_audio = voice.speak(script["outro"])
    imgs = [images.get(sc["image_prompt"], seed + k, f"{base}_img{k}.png")
            for k, sc in enumerate(script["scenes"])]
    dur = render.render(script, imgs, audios, base + ".mp4", seed, outro_audio)
    for p in imgs:
        os.remove(p)

    item = dict(file=os.path.basename(base + ".mp4"), cover=os.path.basename(base + "_cover.png"),
                duration=dur, kind=script["kind"], topic=script["topic"],
                link=script["source"]["link"] if script.get("source") else None,
                script=script, **make_meta(script))
    with open(base + ".json", "w") as f:
        json.dump(item, f, indent=1, ensure_ascii=False)
    print(f"[{idx}] {script['category']}: {script['title']}  ({dur}s, {time.time() - t0:.0f}s)", flush=True)
    return item


def upload_sheet(items, path):
    L = []
    for v in items:
        L += ["=" * 60, v["file"], "=" * 60, "TITLE:", v["title"], "", "DESCRIPTION:", v["description"],
              "", "TAGS:", ", ".join(v["tags"]), "",
              "Made for kids: NO  |  Category: Science & Technology  |  Altered/synthetic content: YES", "", ""]
    with open(path, "w") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=4)
    ap.add_argument("--date", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out_facts"))
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    if a.mock:
        os.environ["IMAGES"] = "mock"
        images.MOCK = True
        voice.ENGINE = "mock"

    st = load_state()
    rng = random.Random(f"{a.date}-{len(st['videos'])}")
    kinds = [LINEUP[i % len(LINEUP)] for i in range(a.count)]

    out_dir = os.path.join(a.out, a.date)
    os.makedirs(out_dir, exist_ok=True)
    items = []
    for i, kind in enumerate(kinds, 1):
        try:
            items.append(make_one(kind, i, out_dir, st["videos"], rng, a.mock))
        except Exception:
            print(f"[{i}] {kind} FAILED:\n{traceback.format_exc()}", flush=True)
            continue
        if not a.mock:
            st["videos"].append(dict(date=a.date, kind=items[-1]["kind"], topic=items[-1]["topic"],
                                     link=items[-1]["link"], title=items[-1]["title"]))
            save_state(st)

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(dict(date=a.date, videos=items), f, indent=1, ensure_ascii=False)
    upload_sheet(items, os.path.join(out_dir, "UPLOAD_SHEET.txt"))
    print(f"done: {len(items)}/{len(kinds)} videos in {out_dir}")
    if not items:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
