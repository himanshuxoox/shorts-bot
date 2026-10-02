# Viral Shorts Bot: Ball Escape simulations

This bot makes 4 YouTube Shorts a day on its own, and it costs nothing to run.
Each Short is a physics race made entirely in code: neon balls bounce inside a
rotating ring, every bounce plays the next note of a public-domain melody, and
the first ball to slip through the gap wins.

- **₹0 to run**: rendering is pure Python (cairo + numpy + ffmpeg), no paid APIs
- **Never repeats**: every seed gives a different race (2/3/4 balls, colors, melody, hook text, spin)
- **Auto-schedules**: GitHub Actions renders every morning and can schedule uploads to 4 time slots

```
shorts/escape.py     simulation + drawing (one template)
shorts/melodies.py   public-domain tunes (Beethoven, Grieg, Mozart, Pachelbel, trad.)
shorts/metadata.py   title / description / tags (never spoils the winner)
shorts/batch.py      renders N videos/day -> out/<date>/ + manifest.json
shorts/upload.py     YouTube Data API upload with scheduled publishAt
auth_setup.py        one-time OAuth -> refresh token
.github/workflows/daily-shorts.yml   daily cron (07:00 IST)
```

## Run locally

```bash
sudo apt install ffmpeg libcairo2-dev pkg-config      # mac: brew install ffmpeg cairo pkg-config
pip install -r requirements.txt
python -m shorts.batch --count 1 --date test          # -> out/test/01_escape_XXXX.mp4
```

## Step 1: Put the repo on GitHub (5 min)

1. Create a new **public** repo (public repos get unlimited free Actions minutes; private repos get 2,000 min/month, which is also enough).
2. Push this folder to the repo.
3. Go to **Actions → Daily Shorts → Run workflow** to test it once.
4. When it finishes, download the `shorts-N` artifact. It holds 4 MP4s, a cover image for each, and `manifest.json` with each video's title and description.

From then on it runs every morning at 07:00 IST.

## Step 2: Upload (Phase 1, manual)

> ⚠️ **YouTube rule:** videos uploaded through the API from an *unverified* Google Cloud
> project stay locked to **private**, and you can't change them to public later.
> Until your project passes the free audit (Step 4), upload by hand.

Every day, download the artifact. In YouTube Studio, click **Create → Upload** and add each MP4. Copy its title and description from the matching `.json` file, set **"No, it's not made for kids"**, and schedule it. All 4 take about 5 minutes.

## Step 3: YouTube API credentials (do this now, it's needed for the audit)

1. Go to https://console.cloud.google.com and create a project, e.g. `shorts-bot`.
2. Under **APIs & Services → Library**, enable **YouTube Data API v3**.
3. Under **OAuth consent screen**, choose External, fill in the app name and your email, and add the scope `youtube.upload`.
   Then set **Publishing status → In production**. In "Testing" mode, refresh tokens expire after 7 days.
   You'll see a "Google hasn't verified this app" warning. That's fine for your own channel: click Advanced → Continue.
4. Under **Credentials → Create credentials → OAuth client ID → Desktop app**, download the JSON and save it as `client_secret.json` (it's already in .gitignore).
5. On your laptop, run:
   ```bash
   pip install google-auth-oauthlib
   python auth_setup.py        # log in with the Google account that owns the channel
   ```
6. In the repo, go to **Settings → Secrets and variables → Actions** and add 3 secrets:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`

## Step 4: API audit, then full auto (Phase 2)

1. Fill in the **YouTube API Services audit form**: https://support.google.com/youtube/contact/yt_api_form
   Describe the project as a "Personal tool that uploads my own original, code-generated simulation videos to my own channel."
2. After the audit is approved, add a repo **variable** (not a secret): `AUTO_UPLOAD = true`.
   Optionally add `PUBLISH_SLOTS = 08:30,12:30,17:30,21:00` (IST).
3. Test the schedule without uploading: `python -m shorts.upload --date <date> --dry-run`

The bot is now hands-free: it renders every morning and each video goes public at its scheduled slot.

## Tuning

- `BALL_MIX` in `shorts/batch.py` sets the ball count of each daily video.
- In `shorts/escape.py`: `HOOKS` and `SUBS` are the on-screen text, `PALETTE` holds the colors, and `is_good()` decides what counts as a good race.
- Add tunes to `shorts/melodies.py`. Use only public-domain compositions, and the audio must be synthesized by the code, not copied from a recording.

## Staying monetizable

YouTube demonetizes mass-produced, repetitive content. Keep it varied:
- Add more templates over time (marble race, color battle, balls that multiply).
- Rotate hooks and colors (already built in).
- Read the comments and make more of whatever gets the most replies.
