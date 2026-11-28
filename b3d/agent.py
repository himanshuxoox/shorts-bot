"""
The 3D Shorts agent. Every run it RESEARCHES, INVENTS, TESTS and PICKS new 3D Shorts:

  1. research  - what works for us: views of every 3D Short we posted (YouTube API, ~1 quota unit)
                 and the Channel Watcher's medians per format (state/stats.json);
                 what works out there: YouTube search for the most-viewed 3D simulation Shorts of
                 the last 2 weeks (100 units a search: 1 a day, 3 on Sunday when no Shorts upload),
                 their titles turned into keyword weights. Everything is kept in state/research_3d.json.
  2. invent    - combines structure x action x variable x palette x ball x backdrop x camera into
                 recipes (b3d/recipes.py) that were never posted before (state/history_3d.json).
  3. score     - our own results per feature (bandit: unknown features get an optimistic bonus so new
                 things get tried), trend keywords, novelty (no repeat of the same idea for 14 days).
  4. test      - runs the physics of all 3 variants (no rendering) and tunes the recipe until the
                 3 variants tell a story: the small one does (almost) nothing, the big one wrecks it.
                 Boring or chaotic recipes are thrown away and the next one is tried.

    python b3d/agent.py plan --count 2 --out plan.json        # in Blender's Python (needs bpy)
    python b3d/agent.py research                              # research only (no bpy needed)
"""
import argparse
import datetime as dt
import itertools
import json
import math
import os
import random
import re
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
IST = ZoneInfo("Asia/Kolkata")
HIST = os.path.join(ROOT, "state", "history_3d.json")
RESEARCH = os.path.join(ROOT, "state", "research_3d.json")
QUERIES = ["satisfying 3d simulation", "3d physics simulation satisfying", "blender physics simulation shorts",
           "satisfying 3d animation asmr", "softbody simulation satisfying", "rigid body simulation satisfying"]
# title words -> recipe features (a trend word counts for every feature it points to)
KEYMAP = {
    r"\bwall": ["structure:wall"], r"\bpyramid": ["structure:pyramid"], r"\btower": ["structure:tower", "structure:columns"],
    r"\bcube|\bblock": ["structure:cube"], r"\bbuilding|\bcity|\bskyscraper": ["structure:columns"],
    r"wrecking|\bswing": ["action:wrecking"], r"\bdrop|\bfall|\bheight|\bhigh\b": ["action:drop", "variable:height"],
    r"\bkg\b|\bheavy|\bweight|\bmass|\bton": ["variable:mass"], r"gravity|\bmoon|jupiter|\bmars|planet": ["variable:gravity"],
    r"explo|\bblast|\bbomb|\btnt\b": ["action:blast"], r"\bwind|\bstorm|tornado|hurricane": ["action:wind"],
    r"\bspin|\brpm\b|rotat|\bfast": ["action:spin"], r"quake|\bshake|tremor|richter": ["action:quake"],
    r"\bball|\bsphere": ["action:wrecking", "action:drop"], r"\bgold": ["hitter:gold"], r"\bsteel|\bmetal|\biron": ["hitter:steel"],
    r"rainbow": ["palette:rainbow"], r"\bcandy|\bsweet": ["palette:candy"],
    r"\bsize\b|\bbig\b|\bhuge|\bgiant": ["variable:size"],
}
# trend words we cannot build yet: reported so the next build can add them
UNSUPPORTED = [r"domino", r"hydraulic|\bpress\b", r"\bjelly|\bslime|\bsoft", r"\bcloth|\bfabric|\bsilk", r"\blava",
               r"\bwater|\bfluid|\bliquid", r"\bglass", r"\bsand\b", r"\bmarble", r"\bcar\b|\btruck",
               r"\bknife|\bcut|\bslice", r"\bfire|\bburn", r"\bice\b|\bfreez"]


def now():
    return dt.datetime.now(IST)


def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ 1. research
def _yt():
    if not os.environ.get("YT_REFRESH_TOKEN"):
        return None
    from googleapiclient.discovery import build
    from shorts.watch import _yt_creds
    return build("youtube", "v3", credentials=_yt_creds(), cache_discovery=False)


def research(searches=None, log=print):
    """-> research dict (also saved). Never fails: every missing piece is just skipped."""
    R = _load(RESEARCH, {"market": [], "own": {}, "log": []})
    hist = _load(HIST, {"next_id": 1000, "shorts": []})
    today = now()
    if searches is None:
        searches = 3 if today.weekday() == 6 else 1           # Sunday: no Shorts are uploaded, more quota
    yt = None
    try:
        yt = _yt()
    except Exception as e:
        log(f"research: no YouTube access ({e})")
    # --- our own 3D Shorts: views per video (1 unit per 50 videos)
    up = _load(os.path.join(ROOT, "state", "uploads_out.json"), {})
    ids = {vid: v for vid, v in up.items() if str(v.get("format", "")).startswith("s3d_")}
    if yt and ids:
        try:
            vids = list(ids)
            for i in range(0, len(vids), 50):
                r = yt.videos().list(part="statistics", id=",".join(vids[i:i + 50])).execute()
                for it in r.get("items", []):
                    R["own"][it["id"]] = dict(views=int(it["statistics"].get("viewCount", 0)),
                                              seed=ids[it["id"]].get("seed"), at=today.isoformat())
        except Exception as e:
            log(f"research: own views not read ({e})")
    # --- the market: most viewed 3D simulation Shorts of the last 14 days
    if yt and searches:
        done = {q["query"] for q in R["log"] if q.get("date") == today.date().isoformat()}
        qs = [q for q in QUERIES if q not in done]
        random.Random(today.toordinal()).shuffle(qs)
        after = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for q in qs[:searches]:
            try:
                r = yt.search().list(part="snippet", q=q, type="video", videoDuration="short", order="viewCount",
                                     publishedAfter=after, maxResults=25, relevanceLanguage="en").execute()
                vids = [it["id"]["videoId"] for it in r.get("items", [])]
                st = yt.videos().list(part="statistics,snippet", id=",".join(vids)).execute() if vids else {"items": []}
                have = {m["id"] for m in R["market"]}
                for it in st.get("items", []):
                    if it["id"] in have:
                        continue
                    R["market"].append(dict(id=it["id"], title=it["snippet"]["title"],
                                            channel=it["snippet"]["channelTitle"],
                                            views=int(it["statistics"].get("viewCount", 0)),
                                            published=it["snippet"]["publishedAt"][:10], query=q,
                                            seen=today.date().isoformat()))
                R["log"].append(dict(date=today.date().isoformat(), query=q, found=len(vids)))
                log(f"research: '{q}' -> {len(vids)} Shorts")
            except Exception as e:
                log(f"research: search stopped ({str(e)[:120]})")
                break
    cutoff = (today - dt.timedelta(days=30)).date().isoformat()
    R["market"] = [m for m in R["market"] if m.get("seen", "9") >= cutoff][-600:]
    R["log"] = R["log"][-200:]
    # --- keyword weights from the market (log views, last 30 days)
    tw, unsup = {}, {}
    for m in R["market"]:
        t = m["title"].lower()
        w = math.log10(max(10, m["views"]))
        for pat, feats in KEYMAP.items():
            if re.search(pat, t):
                for f in feats:
                    tw[f] = tw.get(f, 0.0) + w
        for pat in UNSUPPORTED:
            if re.search(pat, t):
                unsup[pat] = unsup.get(pat, 0.0) + w
    R["trend_weights"] = dict(sorted(tw.items(), key=lambda x: -x[1]))
    R["unsupported_trends"] = dict(sorted(unsup.items(), key=lambda x: -x[1]))
    # --- our own results per feature (average log views of the Shorts that used it)
    by_id = {s["id"]: s for s in hist["shorts"]}
    feat = {}
    for vid, o in R["own"].items():
        s = by_id.get(o.get("seed"))
        if not s:
            continue
        lv = math.log10(max(10, o["views"]))
        for f in features(s["recipe"]):
            feat.setdefault(f, []).append(lv)
    stats = _load(os.path.join(ROOT, "state", "stats.json"), {"days": []})
    med = stats["days"][-1]["formats"] if stats.get("days") else {}
    for fmt, v in med.items():                            # Channel Watcher medians, e.g. s3d_wrecking
        if fmt.startswith("s3d_") and v:
            feat.setdefault("action:" + fmt[4:], []).append(math.log10(max(10, v)))
    R["own_scores"] = {f: round(sum(v) / len(v), 3) for f, v in feat.items()}
    R["channel_median_log"] = round(math.log10(max(10, sorted(med.values())[len(med) // 2])), 3) if med else 3.0
    R["updated"] = today.isoformat()
    _save(RESEARCH, R)
    return R


# ------------------------------------------------------------------ 2-3. invent + score
def features(r):
    out = [f"action:{r['action']}", f"structure:{r['structure']}", f"variable:{r['variable']}",
           f"palette:{r['palette']}", f"backdrop:{r['backdrop']}"]
    if r["action"] in ("wrecking", "drop"):
        out.append(f"hitter:{r['hitter']}")
    return out


def signature(r):
    return f"{r['action']}|{r['variable']}|{r['structure']}|{r['palette']}|{r.get('hitter', '-')}"


def candidates(rng):
    from b3d.recipes import ACTIONS, STRUCTURES, SPIN_OK, PALETTES, HITTERS, BACKDROPS
    out = []
    for action, vars_ in ACTIONS.items():
        for variable, structure in itertools.product(vars_, STRUCTURES):
            if action == "spin" and structure not in SPIN_OK:
                continue
            for palette in PALETTES:
                hitters = HITTERS if action in ("wrecking", "drop") else ["-"]
                for hitter in hitters:
                    out.append(dict(action=action, variable=variable, structure=structure, palette=palette,
                                    hitter=hitter, backdrop=rng.choice(BACKDROPS)))
    return out


def score(c, R, recent, rng):
    own = R.get("own_scores", {})
    base = R.get("channel_median_log", 3.0)
    fs = features(c)
    # bandit: known features score their average views vs the channel; unknown ones get a bonus
    o = [(own[f] - base) if f in own else 0.25 for f in fs]
    s_own = sum(o) / len(o)
    tw = R.get("trend_weights", {})
    top = max(tw.values()) if tw else 1.0
    s_trend = sum(tw.get(f, 0.0) for f in fs) / (top * 2) if tw else 0.0
    key = (c["action"], c["variable"], c["structure"])
    s_nov = 0.0
    for r_, age in recent:
        if (r_["action"], r_["variable"], r_["structure"]) == key and age < 14:
            s_nov -= 0.8
        if r_["action"] == c["action"] and age < 2:
            s_nov -= 0.25
        if r_["palette"] == c["palette"] and age < 2:
            s_nov -= 0.1
    return 0.5 * s_own + 0.35 * s_trend + s_nov + rng.uniform(0, 0.3)


# ------------------------------------------------------------------ 4. test (physics only)
def probe(r, log=print):
    """runs the physics of the 3 variants -> [disturbance 0..1] (needs bpy)"""
    import bpy  # noqa: F401
    from b3d import kit, recipes
    out = []
    for v in range(3):
        sc = kit.reset(res=(64, 114), spp=1)
        S = recipes.build(r, v)
        blocks = [(o, o.matrix_world.translation.copy()) for o in sc.objects
                  if o.rigid_body and o.rigid_body.type == "ACTIVE" and o.name not in ("ball",)]
        pl = S.get("platform")
        pl0 = pl.matrix_world.copy() if pl is not None else None
        for f in range(1, S["frames"] + 1):
            if S["pre"]:
                S["pre"](f)
            sc.frame_set(f)
        out.append(round(recipes.disturbance(blocks, pl, pl0), 3))
    return out


def interesting(d, r):
    d0, d1, d2 = d
    if r["variable"] == "gravity":
        if d2 >= 0.25 and d2 - d0 >= 0.15 and d1 >= d0 - 0.05:
            return True, "ok"
        return False, ("low too strong" if d0 > 0.3 else "high too weak")
    if d0 > 0.12:
        return False, "low too strong"
    if d2 < 0.35 or d2 - d0 < 0.3:
        return False, "high too weak"
    if d1 < d0 - 0.03 or d1 > d2 + 0.05:
        return False, "middle out of order"
    if d1 < d0 + 0.04:
        return False, "middle too weak"
    return True, "ok"


def tune(r, log=print, tries=5):
    """adjust the knob k until the 3 variants tell a story; -> (recipe or None, disturbances)"""
    from b3d.recipes import START_K
    mass_like = r["action"] in ("wrecking", "drop", "blast", "wind")
    k = START_K.get(r["action"], 1.0)
    seen = []
    for _ in range(tries):
        r["k"] = round(k, 4)
        t0 = time.time()
        d = probe(r, log)
        ok, why = interesting(d, r)
        seen.append((round(k, 3), d, why))
        log(f"   test k={k:.3g}: {d} -> {why} ({time.time() - t0:.0f}s)")
        if ok:
            return r, seen
        if why == "middle out of order":
            return None, seen
        if why == "low too strong":
            k = k * 2.2 if mass_like else k * 0.7
        elif why == "middle too weak":
            k = k / 1.6 if mass_like else k * 1.2
        else:
            k = k / 2.2 if mass_like else k * 1.35
    return None, seen


# ------------------------------------------------------------------ plan
def plan(count, out, log=print, offline=False, max_tests=8):
    from b3d import recipes
    R = research(searches=0 if offline else None, log=log)
    hist = _load(HIST, {"next_id": 1000, "shorts": []})
    today = now()
    used = {signature(s["recipe"]) for s in hist["shorts"]}
    recent = []
    for s in hist["shorts"]:
        try:
            age = (today.date() - dt.date.fromisoformat(s["date"])).days
        except Exception:
            age = 99
        recent.append((s["recipe"], age))
    rng = random.Random(today.toordinal() * 31 + len(hist["shorts"]))
    cands = [c for c in candidates(rng) if signature(c) not in used]
    for c in cands:
        c["score"] = score(c, R, recent, rng)
    cands.sort(key=lambda c: -c["score"])
    def idea(c):
        return f"{c['action']}|{c['variable']}|{c['structure']}"

    failed = {}
    for rj in hist.get("rejected", []):
        k_ = "|".join(rj["sig"].split("|")[:3])
        failed[k_] = failed.get(k_, 0) + 1
    picked, tested = [], 0
    for c in cands:
        if len(picked) >= count or tested >= max_tests:
            break
        if failed.get(idea(c), 0) >= 2:
            continue                                         # this physics idea never tells a story
        if any((p["action"], p["structure"]) == (c["action"], c["structure"]) or p["action"] == c["action"]
               for p in picked):
            continue                                         # variety inside one day
        vals, _fmt = recipes.ACTIONS[c["action"]][c["variable"]]
        r = dict(c, id=hist["next_id"], values=list(vals), labels=recipes.labels_for(c["action"], c["variable"], vals),
                 yaw=round(rng.uniform(-38, 38), 1), elev=round(rng.uniform(12, 26), 1))
        r["hook"] = recipes.hook_for(r)
        log(f"try #{r['id']}: {signature(r)}  score {c['score']:.2f}")
        tested += 1
        good, seen = tune(r, log)
        if good:
            good.pop("score", None)
            picked.append(good)
            hist["shorts"].append(dict(id=good["id"], date=today.date().isoformat(), recipe=good, tests=seen))
            hist["next_id"] += 1
        else:
            hist.setdefault("rejected", []).append(dict(sig=signature(r), date=today.date().isoformat(), tests=seen))
            hist["rejected"] = hist["rejected"][-300:]
            used.add(signature(r))
            failed[idea(r)] = 2                              # don't retry it with other colours today
    _save(HIST, hist)
    data = dict(date=today.date().isoformat(), recipes=picked,
                research=dict(trends=list(R.get("trend_weights", {}).items())[:10],
                              unsupported=list(R.get("unsupported_trends", {}).items())[:8],
                              own=R.get("own_scores", {}), market_titles=len(R.get("market", []))))
    _save(out, data)
    summary(data, log)
    return data


def summary(data, log=print):
    L = [f"### 3D Shorts agent {data['date']}", ""]
    for r in data["recipes"]:
        L.append(f"- **#{r['id']}** {r['hook']}  ({' → '.join(r['labels'])}) · {r['structure']} · {r['palette']} · "
                 f"{r.get('hitter', '-')} · {r['backdrop']} · k={r['k']}")
    if not data["recipes"]:
        L.append("- nothing passed the physics test today")
    t = data["research"]
    L += ["", f"Trends from {t['market_titles']} top Shorts: " + ", ".join(f"{k} ({v:.0f})" for k, v in t["trends"]),
          "Popular but not buildable yet: " + (", ".join(k.strip("\\b") for k, _ in t["unsupported"]) or "-")]
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a") as f:
            f.write("\n".join(L) + "\n")
    for line in L:
        log(line)


def matrix(plan_path):
    data = _load(plan_path, {"recipes": []})
    print(json.dumps({"include": [{"id": r["id"], "v": v} for r in data["recipes"] for v in range(3)]}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--count", type=int, default=2)
    p.add_argument("--out", default="plan.json")
    p.add_argument("--offline", action="store_true")
    sub.add_parser("research")
    m = sub.add_parser("matrix")
    m.add_argument("plan")
    a = ap.parse_args()
    if a.cmd == "plan":
        import bpy  # noqa: F401  (mathutils needs bpy first)
        plan(a.count, a.out, offline=a.offline)
    elif a.cmd == "research":
        R = research()
        print(json.dumps({k: R.get(k) for k in ("trend_weights", "unsupported_trends", "own_scores")}, indent=1))
    else:
        matrix(a.plan)


if __name__ == "__main__":
    main()
