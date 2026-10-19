"""
Smart pacing for Shorts: release ONE Short, watch its views, and only release the next one
when the live Short has stopped taking off. (Long videos like the Battle Royale keep their
normal daily schedule through shorts/upload.py.)

How it works
  * The daily batch no longer schedules Shorts at fixed slots. `pacer enqueue` puts the
    rendered MP4s in a queue: assets of a GitHub release called "pacer-queue" (so the videos
    never bloat the git history). The queue + the pacer's memory live in the same release as
    pacer-state.json.
  * A workflow runs `pacer tick` every hour. It reads the live Short's views / likes /
    comments (YouTube Data API, 1 quota unit), stores a snapshot, and decides:

      age < 4 h                        -> HOLD   (YouTube is still testing it)
      views < 1,000 at 4 h             -> RELEASE the next Short (low)
      1k+ but not doubling in 2 h      -> watch until 5 h, then RELEASE
      doubled in 2 h  ("hot")          -> HOLD, target 10,000 views
      hot, but growth stalls (<+15%/2h)-> RELEASE
      reached the target               -> reaction still strong? HOLD, target x2 (20k, 40k…)
                                          otherwise RELEASE
      never more than 24 h without a new Short (safety cap)

    Every number is a repo variable (PACE_*), see PARAMS below.
  * The next Short is picked from the queue: oldest-first after 3 days, otherwise the format
    with the best median views (state/stats.json from the Channel Watcher), never the same
    format as the last two releases.

    python -m shorts.pacer enqueue --date 2026-10-18     # after the daily render
    python -m shorts.pacer need --want 4                 # how many Shorts to render today
    python -m shorts.pacer tick                          # hourly: decide + maybe release
    python -m shorts.pacer status                        # print queue, live Short, decision
    python -m shorts.pacer simulate                      # test the rules on made-up view curves
Local testing without GitHub: PACER_STORE=/some/folder uses that folder instead of the release.
"""
import argparse, datetime as dt, json, os, shutil, statistics, subprocess, sys, tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IST = ZoneInfo("Asia/Kolkata")
TAG = os.environ.get("PACER_TAG", "pacer-queue")
STATE_ASSET = "pacer-state.json"


def _f(name, default):
    v = os.environ.get(name, "").strip()
    return float(v) if v else default


PARAMS = dict(
    check_h=_f("PACE_CHECK_H", 4.0),            # don't judge a Short before this age
    grace_h=_f("PACE_GRACE_H", 1.0),            # 1k+ Shorts get this long to show they're doubling
    min_views=_f("PACE_MIN_VIEWS", 1000),       # below this at check_h -> next Short
    hot_growth=_f("PACE_HOT_GROWTH", 2.0),      # views x2 within 2 h = hot
    stall_growth=_f("PACE_STALL_GROWTH", 1.15), # hot but < +15% in 2 h = it has peaked
    target=_f("PACE_TARGET", 10000),            # first target for a hot Short
    strong_growth=_f("PACE_STRONG_GROWTH", 1.25),  # at the target: still +25% / 2 h = strong
    strong_like=_f("PACE_STRONG_LIKE", 0.04),   # ...or like+comment rate >= 4% while still growing
    max_hold_h=_f("PACE_MAX_HOLD_H", 24.0),     # never longer than this without a new Short
    queue_max=_f("PACE_QUEUE_MAX", 12),         # stop rendering new Shorts above this queue size
    stale_days=_f("PACE_STALE_DAYS", 3.0),      # queued longer than this -> release first
)


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def _iso(t):
    return t.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


# ===================================================================== the decision (pure)
def growth_2h(snaps, now):
    """views now / views ~2 h ago (snapshot between 1.5 h and 3 h old, closest to 2 h)."""
    if not snaps:
        return None
    cur = snaps[-1]["views"]
    best = None
    for s in snaps:
        age = (now - _parse(s["t"])).total_seconds() / 3600
        if 1.5 <= age <= 3.0 and (best is None or abs(age - 2) < abs(best[0] - 2)):
            best = (age, s["views"])
    if best is None:
        return None
    return cur / max(1, best[1])


def decide(live, now, p=PARAMS):
    """live: {published, snaps:[{t, views, likes, comments}], hot, target}
    -> (action 'hold' | 'release', reason, updates to store in live)."""
    if not live:
        return "release", "nothing is live yet", {}
    age = (now - _parse(live["published"])).total_seconds() / 3600
    snaps = live.get("snaps") or []
    v = snaps[-1]["views"] if snaps else 0
    if age >= p["max_hold_h"]:
        return "release", f"safety cap: live for {age:.1f} h ({v:,} views)", {}
    if age < p["check_h"]:
        return "hold", f"testing phase: {age:.1f} h old, {v:,} views", {}
    g = growth_2h(snaps, now)
    if v < p["min_views"]:
        # exception: still under 1k but doubling fast -> give it the grace hour
        if g and g >= p["hot_growth"] and v >= 0.3 * p["min_views"] and age < p["check_h"] + p["grace_h"]:
            return "hold", f"rising fast: {v:,} views, x{g:.1f} in 2 h", {}
        return "release", f"low: {v:,} views at {age:.1f} h (needs {p['min_views']:,.0f})", {}
    if g is None:
        return "hold", f"{v:,} views, waiting for 2 h of data", {}
    hot, target = live.get("hot", False), live.get("target")
    if not hot:
        if g >= p["hot_growth"]:
            tgt = p["target"]
            while tgt <= v:
                tgt *= 2
            return "hold", f"HOT: x{g:.1f} in 2 h ({v:,} views) -> holding until {tgt:,.0f}", \
                dict(hot=True, target=tgt)
        if age < p["check_h"] + p["grace_h"]:
            return "hold", f"potential: {v:,} views, x{g:.2f} in 2 h — watching for doubling", {}
        return "release", f"{v:,} views but not doubling (x{g:.2f} in 2 h)", {}
    if v < target:
        if g < p["stall_growth"]:
            return "release", f"hot Short stalled at {v:,} (x{g:.2f} in 2 h, target {target:,.0f})", {}
        return "hold", f"hot: {v:,} -> target {target:,.0f} (x{g:.2f} in 2 h)", {}
    s = snaps[-1]
    react = (s.get("likes", 0) + s.get("comments", 0)) / max(1, v)
    strong = g >= p["strong_growth"] or (react >= p["strong_like"] and g >= 1.1)
    if strong:
        return "hold", f"target {target:,.0f} reached, still strong (x{g:.2f}/2 h, {react:.1%} likes) " \
                       f"-> next target {target * 2:,.0f}", dict(target=target * 2)
    return "release", f"target {target:,.0f} reached, reaction cooled (x{g:.2f}/2 h, {react:.1%} likes)", {}


# ===================================================================== which Short next?
def format_scores():
    p = os.path.join(ROOT, "state", "stats.json")
    try:
        days = json.load(open(p))["days"]
        return days[-1].get("formats", {}) if days else {}
    except Exception:
        return {}


def pick_next(queue, recent_formats, now, p=PARAMS):
    if not queue:
        return None
    stale = [q for q in queue if (now - _parse(q["queued"])).total_seconds() > p["stale_days"] * 86400]
    if stale:
        return min(stale, key=lambda q: q["queued"])
    scores = format_scores()
    default = statistics.median(scores.values()) if scores else 0
    avoid = set(recent_formats[-2:])
    pool = [q for q in queue if q["format"] not in avoid] or queue
    return max(pool, key=lambda q: (scores.get(q["format"], default), -_parse(q["queued"]).timestamp()))


# ===================================================================== storage (GitHub release or a folder)
class ReleaseStore:
    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY")

    def _gh(self, *args, check=True):
        cmd = ["gh", *args] + (["-R", self.repo] if self.repo else [])
        return subprocess.run(cmd, check=check, capture_output=True, text=True)

    def ensure(self):
        if self._gh("release", "view", TAG, check=False).returncode != 0:
            self._gh("release", "create", TAG, "--prerelease", "--title", "Pacer queue (bot storage — do not delete)",
                     "--notes", "Queued Shorts waiting to be released by shorts/pacer.py, plus pacer-state.json.")

    def get(self, name, dest_dir):
        r = self._gh("release", "download", TAG, "-p", name, "-D", dest_dir, "--clobber", check=False)
        return os.path.join(dest_dir, name) if r.returncode == 0 else None

    def put(self, path):
        self._gh("release", "upload", TAG, path, "--clobber")

    def delete(self, name):
        self._gh("release", "delete-asset", TAG, name, "-y", check=False)


class FolderStore:
    def __init__(self, folder):
        self.dir = folder
        os.makedirs(folder, exist_ok=True)

    def ensure(self):
        pass

    def get(self, name, dest_dir):
        src = os.path.join(self.dir, name)
        if not os.path.exists(src):
            return None
        dst = os.path.join(dest_dir, name)
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy(src, dst)
        return dst

    def put(self, path):
        dst = os.path.join(self.dir, os.path.basename(path))
        if os.path.abspath(path) != os.path.abspath(dst):
            shutil.copy(path, dst)

    def delete(self, name):
        try:
            os.remove(os.path.join(self.dir, name))
        except FileNotFoundError:
            pass


def store():
    folder = os.environ.get("PACER_STORE")
    return FolderStore(folder) if folder else ReleaseStore()


def load_state(st, tmp):
    p = st.get(STATE_ASSET, tmp)
    if p:
        with open(p) as f:
            return json.load(f)
    return {"queue": [], "live": None, "released": []}


def save_state(st, state, tmp):
    p = os.path.join(tmp, STATE_ASSET)
    with open(p, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False)
    st.put(p)


# ===================================================================== YouTube
def yt_client():
    from .watch import _yt_creds              # full scopes of the refresh token (upload + read)
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_yt_creds(), cache_discovery=False)


def fetch_stats(yt, vid):
    r = yt.videos().list(part="statistics,status", id=vid).execute()
    if not r.get("items"):
        return None
    it = r["items"][0]
    s = it.get("statistics", {})
    return dict(views=int(s.get("viewCount", 0)), likes=int(s.get("likeCount", 0)),
                comments=int(s.get("commentCount", 0)), privacy=it["status"].get("privacyStatus"))


# ===================================================================== commands
def cmd_enqueue(a):
    day_dir = os.path.join(a.out, a.date)
    mpath = os.path.join(day_dir, "manifest.json")
    manifest = json.load(open(mpath))
    st = store()
    st.ensure()
    with tempfile.TemporaryDirectory() as tmp:
        state = load_state(st, tmp)
        have = {q["asset"] for q in state["queue"]}
        n = 0
        for item in manifest["videos"]:
            if item.get("long_form") or item.get("youtube_id"):
                continue                          # long videos keep the normal schedule (upload.py)
            asset = f"{a.date}__{item['file']}"
            if asset in have:
                continue
            src = os.path.join(day_dir, item["file"])
            dst = os.path.join(tmp, asset)
            shutil.copy(src, dst)
            st.put(dst)
            q = {k: item[k] for k in ("format", "seed", "title", "description", "tags", "categoryId", "file")
                 if k in item}
            q.update(asset=asset, date=a.date, queued=_iso(now_utc()))
            state["queue"].append(q)
            item["queued"] = asset
            n += 1
            print(f"queued {asset}  |  {item['title']}")
        save_state(st, state, tmp)
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"{n} Shorts queued, queue size now {len(state['queue'])}")


def cmd_need(a):
    st = store()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            q = len(load_state(st, tmp)["queue"])
        except Exception:
            q = 0
    print(max(0, min(a.want, int(PARAMS["queue_max"]) - q)))


def _summary(lines):
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a") as f:
            f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def cmd_tick(a):
    st = store()
    st.ensure()
    now = now_utc()
    yt = None if a.dry_run else yt_client()
    with tempfile.TemporaryDirectory() as tmp:
        state = load_state(st, tmp)
        live = state.get("live")
        if live and yt:
            s = fetch_stats(yt, live["id"])
            if s:
                live.setdefault("snaps", []).append(dict(t=_iso(now), **{k: s[k] for k in ("views", "likes", "comments")}))
                live["snaps"] = live["snaps"][-60:]
        action, reason, upd = decide(live, now)
        if live:
            live.update(upd)
        lines = [f"### Pacer {now.astimezone(IST):%Y-%m-%d %H:%M IST}",
                 f"- live: {live['title'] if live else '—'}" + (f" (https://youtube.com/shorts/{live['id']})" if live else ""),
                 f"- decision: **{action.upper()}** — {reason}",
                 f"- queue: {len(state['queue'])} Shorts"]
        if action == "release":
            recent = [r["format"] for r in state.get("released", [])]
            nxt = pick_next(state["queue"], recent, now)
            if nxt is None:
                lines.append("- queue is empty, nothing to release")
            elif a.dry_run:
                lines.append(f"- would release: {nxt['title']} ({nxt['format']})")
            else:
                vid, when = _release(st, nxt, yt, tmp)
                if vid:
                    if live:
                        live["ended"] = _iso(now)
                        live["end_reason"] = reason
                        state.setdefault("released", []).append(
                            {k: live.get(k) for k in ("id", "format", "title", "published", "ended", "end_reason",
                                                      "hot", "target")} | {"views": (live.get("snaps") or [{}])[-1].get("views")})
                        state["released"] = state["released"][-200:]
                    state["queue"] = [q for q in state["queue"] if q["asset"] != nxt["asset"]]
                    state["live"] = dict(id=vid, format=nxt["format"], title=nxt["title"], published=_iso(when),
                                         snaps=[], hot=False, target=None)
                    st.delete(nxt["asset"])
                    _record_upload(vid, nxt, when)
                    lines.append(f"- released: {nxt['title']} -> https://youtube.com/shorts/{vid} "
                                 f"(public at {when.astimezone(IST):%H:%M IST})")
                else:
                    nxt["fails"] = nxt.get("fails", 0) + 1
                    if nxt["fails"] >= 3:
                        state["queue"] = [q for q in state["queue"] if q["asset"] != nxt["asset"]]
                        lines.append(f"- upload failed 3 times, dropped {nxt['asset']}")
                    else:
                        lines.append(f"- upload failed ({nxt['fails']}/3), will retry next hour")
        if not a.dry_run:
            save_state(st, state, tmp)
    _summary(lines)


def _release(st, item, yt, tmp):
    from .upload import upload_one
    path = st.get(item["asset"], tmp)
    if not path:
        print(f"asset {item['asset']} missing", file=sys.stderr)
        return None, None
    when = now_utc() + dt.timedelta(minutes=10)      # a few minutes so YouTube finishes HD processing
    body = dict(item, tags=item.get("tags", []), categoryId=item.get("categoryId", "24"))
    try:
        return upload_one(yt, path, body, when), when
    except Exception as e:
        print(f"upload failed: {e}", file=sys.stderr)
        return None, None


def _record_upload(vid, item, when):
    """state/uploads_out.json so the Channel Watcher knows each video's format."""
    p = os.path.join(ROOT, "state", "uploads_out.json")
    data = json.load(open(p)) if os.path.exists(p) else {}
    data[vid] = dict(format=item.get("format"), title=item["title"], seed=item.get("seed"),
                     publish_at=when.astimezone(IST).isoformat(), long_form=False, paced=True)
    with open(p, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def cmd_status(a):
    st = store()
    now = now_utc()
    with tempfile.TemporaryDirectory() as tmp:
        state = load_state(st, tmp)
    live = state.get("live")
    print(f"queue ({len(state['queue'])}):")
    for q in state["queue"]:
        print(f"  {q['queued'][:16]}  {q['format']:<14} {q['title']}")
    if live:
        s = (live.get("snaps") or [{}])[-1]
        print(f"live: {live['title']}  ({live['format']}, published {live['published']}) views={s.get('views')}")
    print("decision now:", *decide(live, now)[:2])


def cmd_simulate(a):
    """Run the rules on made-up view curves (no API) to see when each would be released."""
    t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    curves = {
        "flop (300 views)": lambda h: 300 * min(1, h / 3),
        "ok (1.5k, flat)": lambda h: 1500 * min(1, h / 3.5),
        "slow climber": lambda h: 400 * h,
        "takes off at 3h": lambda h: 200 * 2 ** max(0, h - 1) if h < 7 else 200 * 2 ** 6 + 3000 * (h - 7),
        "viral (keeps doubling)": lambda h: 150 * 2 ** (h / 1.6) if h < 14 else 150 * 2 ** (14 / 1.6) * (1 + 0.15 * (h - 14)),
    }
    for name, f in curves.items():
        live = dict(published=_iso(t0), snaps=[], hot=False, target=None)
        h = 0.0
        while h <= 30:
            now = t0 + dt.timedelta(hours=h)
            v = int(f(h))
            live["snaps"].append(dict(t=_iso(now), views=v, likes=int(v * 0.035), comments=int(v * 0.004)))
            act, why, upd = decide(live, now)
            live.update(upd)
            if act == "release":
                print(f"{name:<24} released next after {h:4.1f} h at {v:>8,} views — {why}")
                break
            h += 1.0
        else:
            print(f"{name:<24} still holding after 30 h")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enqueue")
    e.add_argument("--date", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    e.add_argument("--out", default=os.path.join(ROOT, "out"))
    n = sub.add_parser("need")
    n.add_argument("--want", type=int, default=4)
    t = sub.add_parser("tick")
    t.add_argument("--dry-run", action="store_true")
    sub.add_parser("status")
    sub.add_parser("simulate")
    a = ap.parse_args()
    dict(enqueue=cmd_enqueue, need=cmd_need, tick=cmd_tick, status=cmd_status, simulate=cmd_simulate)[a.cmd](a)


if __name__ == "__main__":
    main()
