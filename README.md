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

---

# Channel 2: daily science & AI facts

`facts/` makes 4 English Shorts a day:

| Slot | Kind | Where the topic comes from |
|---|---|---|
| 1 | NEW DISCOVERY | ScienceDaily, Phys.org, NASA, Live Science, New Scientist RSS |
| 2 | SCIENCE EXPLAINED | Gemini picks an evergreen "how / why" topic it hasn't covered yet |
| 3 | FUN FACT | Gemini, evergreen |
| 4 | MONEY SCIENCE | Psychology/history/math of money & markets, never financial advice |

(`ai_news` still exists in the code; add it back to `LINEUP` in `facts/batch.py` if you ever want it.)

The pipeline works like this:
1. Gemini writes a 40–50 s script as JSON scenes.
2. A **second fact-check pass** rewrites anything doubtful, and a low-confidence script is skipped.
3. The narration is generated with **Kokoro** (free, open-source). If Kokoro fails, Gemini TTS is used instead.
4. Visuals are tried in this order: a Pexels or Pixabay stock clip (only if you've set that API key),
   then a **Pollinations** AI image. The free endpoint sometimes returns 402 at first, so it retries.
   If all of those fail, a generated abstract image is used.
5. The renderer adds Ken Burns motion, word-by-word captions and a music bed it generates itself.

Discovery videos always link their source in the description. Every facts video is marked
"altered/synthetic content", because it uses AI images and an AI voice.

## Setup

1. Create a free Gemini API key at https://aistudio.google.com/apikey. Add it as the repo secret `GEMINI_API_KEY`.
2. (Optional) For real stock footage, add a free Pixabay API key as the secret `PIXABAY_API_KEY`. Log in at pixabay.com,
   and the key is shown at https://pixabay.com/api/docs/. A `PEXELS_API_KEY` works too, but new Pexels keys are paused right now.
3. To test, go to **Actions → Daily Facts → Run workflow** and set count = 1. Download the `facts-N` artifact.
   It holds the videos plus an `UPLOAD_SHEET.txt` with every video's title, description and tags.
4. Later, when API uploads are allowed: run `python auth_setup.py` and pick the facts channel.
   Save the refresh token as `YT_FACTS_REFRESH_TOKEN`, then set the repo variable `AUTO_UPLOAD_FACTS = true`.

Offline test: `python -m facts.batch --count 1 --mock` (uses a canned script, a fake voice and generated images).
