"""
Upload a day's batch to YouTube, each scheduled to a different time slot.

    python -m shorts.upload --date 2026-10-02            # real upload
    python -m shorts.upload --date 2026-10-02 --dry-run  # just print the plan

Needs env vars (GitHub secrets): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Get the refresh token once with:  python auth_setup.py

Each upload is scheduled to the next free slot. The last slot used is remembered in
state/schedule_<out>.json, so two runs on the same day (e.g. a manual run and the
scheduled one) never put two videos on the same slot.
"""
import argparse, datetime as dt, json, os, sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IST = ZoneInfo("Asia/Kolkata")
# publish slots (IST): 6 Shorts a day, every 4 hours. Chosen from the Channel Watcher's slot table
# (15:30 has the best median of the slots with several videos; 04:08 had a 21k hit; 08:30, 17:30
# and 21:00 were the weakest). Override with env / repo variable PUBLISH_SLOTS.
SLOTS = [s.strip() for s in (os.environ.get("PUBLISH_SLOTS") or "03:30,07:30,11:30,15:30,19:30,23:30").split(",")]


def _sched_path(out_dir):
    return os.path.join(ROOT, "state", f"schedule_{os.path.basename(os.path.normpath(out_dir))}.json")


def last_slot(out_dir):
    try:
        with open(_sched_path(out_dir)) as f:
            return dt.datetime.fromisoformat(json.load(f)["last_publish_at"])
    except Exception:
        return None


def save_last_slot(out_dir, when):
    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)
    with open(_sched_path(out_dir), "w") as f:
        json.dump({"last_publish_at": when.isoformat()}, f, indent=1)


def plan_times(date_str, n, after=None):
    """Return n aware datetimes: the next free slots (today's remaining ones, then tomorrow's),
    always later than `after` (the last slot an earlier run already used)."""
    try:
        day = dt.date.fromisoformat(date_str)
    except ValueError:  # e.g. a "test" folder -> schedule from today
        day = dt.datetime.now(IST).date()
    now = dt.datetime.now(IST) + dt.timedelta(minutes=20)  # YouTube needs publishAt in future
    if after is not None and after >= now:
        now = after + dt.timedelta(minutes=1)
        day = max(day, now.date())
    out, d = [], day
    while len(out) < n:
        for s in SLOTS:
            hh, mm = map(int, s.split(":"))
            t = dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=IST)
            if t > now and len(out) < n:
                out.append(t)
        d += dt.timedelta(days=1)
    return out


def record_upload(out_dir, vid, item, when):
    """state/uploads_<out>.json: youtube id -> format, so the channel watcher knows what each video is."""
    p = os.path.join(ROOT, "state", f"uploads_{os.path.basename(os.path.normpath(out_dir))}.json")
    data = json.load(open(p)) if os.path.exists(p) else {}
    data[vid] = dict(format=item.get("format"), title=item["title"], seed=item.get("seed"),
                     publish_at=when.isoformat(), long_form=bool(item.get("long_form")))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def youtube_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_one(yt, path, item, publish_at):
    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {
            "title": item["title"],
            "description": item["description"],
            "tags": item["tags"],
            "categoryId": item.get("categoryId", "24"),
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",          # required for scheduled publishing
            "publishAt": publish_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "selfDeclaredMadeForKids": False,
            # simulations: False; facts channel (AI images + AI voice): True
            "containsSyntheticMedia": bool(item.get("containsSyntheticMedia", False)),
        },
    }
    media = MediaFileUpload(path, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _status, resp = req.next_chunk()
    vid = resp["id"]
    thumb = item.get("thumbnail")
    if thumb:                       # long videos get their own thumbnail (needs a phone-verified channel)
        tpath = os.path.join(os.path.dirname(path), thumb)
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(tpath, mimetype="image/jpeg")).execute()
            print("   thumbnail set")
        except Exception as e:      # video is still uploaded fine; YouTube then picks a frame
            print(f"   thumbnail not set ({e}). Verify the channel by phone at youtube.com/verify",
                  file=sys.stderr)
    return vid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.datetime.now(IST).strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=os.path.join(ROOT, "out"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--long-only", action="store_true",
                    help="only the long videos (royale); Shorts go through shorts/pacer.py instead")
    a = ap.parse_args()

    day_dir = os.path.join(a.out, a.date)
    mpath = os.path.join(day_dir, "manifest.json")
    with open(mpath) as f:
        manifest = json.load(f)
    todo = [v for v in manifest["videos"] if not v.get("youtube_id") and not v.get("queued")
            and (v.get("long_form") or not a.long_only)]
    if not todo:
        print("nothing to upload")
        return
    times = plan_times(a.date, len(todo), after=last_slot(a.out))

    yt = None if a.dry_run else youtube_client()
    for item, when in zip(todo, times):
        path = os.path.join(day_dir, item["file"])
        print(f"{when:%Y-%m-%d %H:%M IST}  {item['file']}  |  {item['title']}")
        if a.dry_run:
            continue
        try:
            vid = upload_one(yt, path, item, when)
        except Exception as e:  # keep going with the rest, report at the end
            print(f"   upload failed: {e}", file=sys.stderr)
            item["upload_error"] = str(e)
            continue
        item["youtube_id"] = vid
        item["publish_at"] = when.isoformat()
        save_last_slot(a.out, when)
        record_upload(a.out, vid, item, when)
        print(f"   -> https://youtube.com/{'watch?v=' if item.get('long_form') else 'shorts/'}{vid}")

    if not a.dry_run:
        with open(mpath, "w") as f:
            json.dump(manifest, f, indent=1, ensure_ascii=False)
        if any("upload_error" in v for v in todo):
            sys.exit(1)


if __name__ == "__main__":
    main()
