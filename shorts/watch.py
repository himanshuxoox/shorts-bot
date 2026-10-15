"""
Channel Watcher agent (watch-only: it never changes anything on the channel or in the lineup).

Every day it:
  1. reads every video on the channel (YouTube Data API) + watch time / retention / subs
     gained per video (YouTube Analytics API, ~2 days delay),
  2. works out which FORMAT each video is (state/uploads_out.json, then history titles,
     then the title templates in shorts/metadata.py),
  3. ranks the formats, the publish slots and the videos, compares with yesterday,
  4. asks Gemini (free tier, optional) for a short Hinglish summary,
  5. posts it all as a GitHub Issue (label "channel-report"); yesterday's report is closed.
History of daily snapshots is kept in state/stats.json.

    python -m shorts.watch                 # needs YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN
    python -m shorts.watch --demo          # fake data, prints the report (no API calls)
    python -m shorts.watch --no-issue      # print the report instead of opening an issue
"""
import argparse, datetime as dt, json, os, random, re, statistics, sys, urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo

from . import metadata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.path.join(ROOT, "state", "stats.json")
IST = ZoneInfo("Asia/Kolkata")
CHANNEL_NAME = os.environ.get("CHANNEL_NAME", "Orbit Escape")
START = os.environ.get("STATS_START", "2026-09-01")


# ===================================================================== data
def _yt_creds():
    from google.oauth2.credentials import Credentials
    return Credentials(token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                       client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                       token_uri="https://oauth2.googleapis.com/token")


def fetch():
    """-> (channel dict, [video dicts]) from the YouTube Data + Analytics APIs."""
    from googleapiclient.discovery import build
    creds = _yt_creds()
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=tok).execute()
        ids += [it["contentDetails"]["videoId"] for it in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    videos = []
    for k in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails,status", id=",".join(ids[k:k + 50])).execute()
        for v in r["items"]:
            st = v.get("statistics", {})
            videos.append(dict(
                id=v["id"], title=v["snippet"]["title"], published=v["snippet"]["publishedAt"],
                privacy=v["status"].get("privacyStatus"), publish_at=v["status"].get("publishAt"),
                duration=_iso_dur(v["contentDetails"]["duration"]),
                views=int(st.get("viewCount", 0)), likes=int(st.get("likeCount", 0)),
                comments=int(st.get("commentCount", 0))))
    # analytics per video (retention, watch time, subs)
    an = {}
    try:
        ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        end = dt.date.today().isoformat()
        r = ya.reports().query(ids="channel==MINE", startDate=START, endDate=end, dimensions="video",
                               metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
                                       "subscribersGained,likes,shares",
                               sort="-views", maxResults=200).execute()
        cols = [c["name"] for c in r["columnHeaders"]]
        for row in r.get("rows", []):
            d = dict(zip(cols, row))
            an[d["video"]] = d
    except Exception as e:                      # analytics scope missing / API disabled: report still works
        print(f"[watch] analytics unavailable: {e}", file=sys.stderr)
    for v in videos:
        a = an.get(v["id"], {})
        v.update(avg_pct=a.get("averageViewPercentage"), avg_dur=a.get("averageViewDuration"),
                 minutes=a.get("estimatedMinutesWatched"), subs=a.get("subscribersGained"),
                 shares=a.get("shares"))
    channel = dict(id=ch["id"], title=ch["snippet"]["title"],
                   subs=int(ch["statistics"].get("subscriberCount", 0)),
                   views=int(ch["statistics"].get("viewCount", 0)),
                   videos=int(ch["statistics"].get("videoCount", 0)), analytics=bool(an))
    return channel, videos


def _iso_dur(s):
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    h, mi, se = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + se


def demo_data():
    rng = random.Random(7)
    fmts = ["crush", "lasers", "hammer", "squeeze", "race_lava", "race_flood", "butterfly", "shrink",
            "devour", "evolve", "multiply", "paint", "elim", "royale"]
    base = {f: rng.uniform(300, 4000) for f in fmts}
    base["royale"] = 900
    vids = []
    day0 = dt.datetime(2026, 9, 20, tzinfo=IST)
    for k in range(80):
        f = rng.choice(fmts)
        when = day0 + dt.timedelta(days=k // 5, hours=rng.choice([8.5, 12.5, 15.5, 18.5, 21.0]))
        views = int(base[f] * rng.lognormvariate(0, 0.8))
        vids.append(dict(id=f"vid{k:03d}", title=f"[{f}] demo video {k}", published=when.isoformat(),
                         privacy="public", publish_at=None, duration=150 if f == "royale" else rng.randint(18, 40),
                         views=views, likes=int(views * rng.uniform(0.02, 0.06)),
                         comments=int(views * rng.uniform(0.001, 0.01)),
                         avg_pct=rng.uniform(55, 120) if f != "royale" else rng.uniform(25, 45),
                         avg_dur=rng.uniform(12, 40), minutes=views * 0.4, subs=int(views * 0.004), shares=0,
                         format=f))
    ch = dict(id="demo", title="Orbit Escape", subs=812, views=sum(v["views"] for v in vids), videos=len(vids),
              analytics=True)
    return ch, vids


# ===================================================================== which format is a video?
def _template_regexes():
    out = []
    for key, styles in metadata.TITLES.items():
        fmt = re.sub(r"(_labels|2|N)$", "", key)
        for _style, tpl in styles:
            parts = re.split(r"\{[a-zA-Z]+\}", tpl)
            rx = r".*".join(re.escape(p.strip()) for p in parts if p.strip())
            if len(rx) > 8:
                out.append((re.compile(rx), fmt))
    out.sort(key=lambda p: -len(p[0].pattern))      # most specific template first
    return out


def classify(videos):
    known = {}
    up = os.path.join(ROOT, "state", "uploads_out.json")
    if os.path.exists(up):
        known.update({k: v.get("format") for k, v in json.load(open(up)).items()})
    hist = {}
    hp = os.path.join(ROOT, "state", "history.json")
    if os.path.exists(hp):
        for h in json.load(open(hp)).get("videos", []):
            if h.get("format"):
                hist[h["title"].strip()] = h["format"]
    rx = _template_regexes()
    for v in videos:
        if v.get("format"):
            continue
        f = known.get(v["id"]) or hist.get(v["title"].strip())
        if not f:
            f = next((fm for r, fm in rx if r.search(v["title"])), None)
        if not f and v["duration"] > 60:
            f = "royale"
        v["format"] = f or "other"
    return videos


# ===================================================================== analysis
def _pub_time(v):
    s = v.get("publish_at") or v["published"]
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(IST)


def analyse(channel, videos, now=None):
    now = now or dt.datetime.now(IST)
    live = [v for v in videos if v["privacy"] == "public" and _pub_time(v) <= now]
    scheduled = [v for v in videos if v not in live]
    # only videos that had 2+ days to collect views are fair to compare
    ripe = [v for v in live if (now - _pub_time(v)).days >= 2]
    by = defaultdict(list)
    for v in ripe:
        by[v["format"]].append(v)
    fmt_rows = []
    for f, vs in by.items():
        views = [v["views"] for v in vs]
        pct = [v["avg_pct"] for v in vs if v.get("avg_pct") is not None]
        fmt_rows.append(dict(format=f, n=len(vs), median=int(statistics.median(views)), best=max(views),
                             total=sum(views), pct=round(statistics.mean(pct), 1) if pct else None,
                             subs=sum(v.get("subs") or 0 for v in vs),
                             like_rate=round(100 * sum(v["likes"] for v in vs) / max(1, sum(views)), 1)))
    fmt_rows.sort(key=lambda r: -r["median"])
    slot = defaultdict(list)
    for v in ripe:
        if v["duration"] <= 60:
            slot[_pub_time(v).strftime("%H:%M")].append(v["views"])
    slot_rows = sorted(((k, len(x), int(statistics.median(x))) for k, x in slot.items()), key=lambda r: -r[2])
    week = [v for v in live if (now - _pub_time(v)).days < 7]
    return dict(channel=channel, live=len(live), scheduled=len(scheduled), ripe=len(ripe),
                formats=fmt_rows, slots=slot_rows,
                top_week=sorted(week, key=lambda v: -v["views"])[:5],
                top_all=sorted(live, key=lambda v: -v["views"])[:5],
                flops=sorted(ripe, key=lambda v: v["views"])[:3])


def snapshot(a, now):
    st = json.load(open(STATS)) if os.path.exists(STATS) else {"days": []}
    prev = st["days"][-1] if st["days"] else None
    today = dict(date=now.strftime("%Y-%m-%d"), subs=a["channel"]["subs"], views=a["channel"]["views"],
                 videos=a["live"], formats={r["format"]: r["median"] for r in a["formats"]})
    st["days"] = [d for d in st["days"] if d["date"] != today["date"]] + [today]
    st["days"] = st["days"][-120:]
    return st, prev, today


# ===================================================================== report
def _n(x):
    return f"{x:,}" if isinstance(x, int) else ("–" if x is None else str(x))


def _link(v):
    path = f"shorts/{v['id']}" if v["duration"] <= 60 else f"watch?v={v['id']}"
    t = v["title"].replace("#shorts", "").replace("|", "/").strip()
    return f"[{t[:60]}](https://youtube.com/{path})"


def report(a, prev, today, summary=None):
    ch = a["channel"]
    L = []
    d_subs = today["subs"] - prev["subs"] if prev else None
    d_views = today["views"] - prev["views"] if prev else None
    L += [f"## 📊 {ch['title']} — {today['date']}", ""]
    L += ["| Subscribers | Total views | Live videos | Scheduled |", "|---|---|---|---|",
          (f"| **{_n(ch['subs'])}** ({'+' if d_subs >= 0 else ''}{_n(d_subs)} since last report) "
           f"| **{_n(ch['views'])}** (+{_n(d_views)}) | {a['live']} | {a['scheduled']} |" if prev else
           f"| **{_n(ch['subs'])}** (first report) | **{_n(ch['views'])}** | {a['live']} | {a['scheduled']} |"), ""]
    if summary:
        L += ["### 🤖 Agent's take", "", summary.strip(), ""]
    L += ["### 🏆 Format leaderboard", f"_Videos at least 2 days old ({a['ripe']}). Sorted by median views._", "",
          "| # | Format | Videos | Median views | Best | Avg % viewed | Like rate | Subs gained |",
          "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(a["formats"], 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, str(i))
        L.append(f"| {medal} | `{r['format']}` | {r['n']} | **{_n(r['median'])}** | {_n(r['best'])} | "
                 f"{'–' if r['pct'] is None else str(r['pct']) + '%'} | {r['like_rate']}% | {_n(r['subs'])} |")
    if a["slots"]:
        L += ["", "### ⏰ Publish slots (Shorts, median views)", "", "| Slot (IST) | Videos | Median views |",
              "|---|---|---|"]
        L += [f"| {s} | {n} | {_n(m)} |" for s, n, m in a["slots"]]
    L += ["", "### 🔥 Top videos this week", ""]
    L += [f"{i}. {_link(v)} — **{_n(v['views'])}** views · `{v['format']}`"
          + (f" · {round(v['avg_pct'])}% viewed" if v.get("avg_pct") else "") for i, v in enumerate(a["top_week"], 1)]
    if not a["top_week"]:
        L.append("_No videos published in the last 7 days._")
    L += ["", "### 👑 All-time top 5", ""]
    L += [f"{i}. {_link(v)} — **{_n(v['views'])}** views · `{v['format']}`" for i, v in enumerate(a["top_all"], 1)]
    if a["flops"]:
        L += ["", "### 🧊 Weakest (2+ days old)", ""]
        L += [f"- {_link(v)} — {_n(v['views'])} views · `{v['format']}`" for v in a["flops"]]
    if not ch.get("analytics"):
        L += ["", "> ⚠️ Retention / watch-time columns are empty: re-run `auth_setup.py` (new scopes) and enable the "
                  "**YouTube Analytics API** in Google Cloud."]
    L += ["", "_Watch-only agent: it does not change uploads or the lineup._"]
    return "\n".join(L)


def gemini_summary(a, prev):
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from facts.llm import ask
        data = dict(formats=a["formats"][:12], slots=a["slots"], subs=a["channel"]["subs"],
                    prev_subs=prev["subs"] if prev else None,
                    top_week=[dict(title=v["title"], views=v["views"], format=v["format"], pct=v.get("avg_pct"))
                              for v in a["top_week"]])
        prompt = ("You analyse a faceless YouTube Shorts channel of physics-simulation videos. Below are its stats "
                  "per FORMAT (median views, average % viewed, likes, subs). Write 4-6 short bullet points in "
                  "Hinglish (Hindi in Latin script mixed with English), direct and practical: which formats are "
                  "winning and losing, any surprising number, which publish slot works, and ONE concrete idea "
                  "to test next week. Only use the numbers given; if there is too little data, say so. "
                  "No intro, no sign-off.\n\n" + json.dumps(data, ensure_ascii=False))
        return ask(prompt)
    except Exception as e:
        print(f"[watch] gemini summary skipped: {e}", file=sys.stderr)
        return None


# ===================================================================== GitHub issue
def _gh(method, path, body=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}",
                                 data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or "null")


def post_issue(title, body):
    old = _gh("GET", "/issues?state=open&labels=channel-report&per_page=20") or []
    new = _gh("POST", "/issues", dict(title=title, body=body, labels=["channel-report"]))
    for it in old:
        _gh("PATCH", f"/issues/{it['number']}", dict(state="closed"))
    return new["html_url"]


# ===================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-issue", action="store_true")
    a_ = ap.parse_args()
    now = dt.datetime.now(IST)
    channel, videos = demo_data() if a_.demo else fetch()
    classify(videos)
    a = analyse(channel, videos, now)
    st, prev, today = snapshot(a, now)
    summary = None if a_.demo else gemini_summary(a, prev)
    body = report(a, prev, today, summary)
    if a_.demo or a_.no_issue or not os.environ.get("GITHUB_TOKEN"):
        print(body)
    else:
        url = post_issue(f"📊 {channel['title']} report — {today['date']} · {channel['subs']:,} subs", body)
        print("report:", url)
    if not a_.demo:
        os.makedirs(os.path.dirname(STATS), exist_ok=True)
        with open(STATS, "w") as f:
            json.dump(st, f, indent=1)


if __name__ == "__main__":
    main()
