# Viral Shorts Bot: physics simulation Shorts

This bot makes 4 YouTube Shorts a day on its own, and it costs nothing to run.
Every Short is a physics simulation made entirely in code, and every bounce plays the next
note of a famous **public-domain** tune ("Did you recognize the music?").

| Format | What happens | Hook |
|---|---|---|
| `fourier` `dpendulum` `lorenz` `chaosgame` `timestable` `primespiral` `threebody` `metronomes` `galton` `chladni` | 10 math / physics Shorts drawn with **ManimGL** (3Blue1Brown's manim) — see [mgl/README.md](mgl/README.md) | Fourier circles, chaos pendulums, Lorenz butterfly, chaos-game fractals, × k circle, prime spirals, three suns, metronome sync, Galton board, Chladni sand |
| `focus` | Balls fly out of one focus of an ellipse; after one bounce ALL of them pass through the other focus at the same moment. 1, 2, 3, 5, 8 … 377 balls | Will they all hit the same point? |
| `focus_stretch` | Same trick, but the shape is stretched / squashed (even a circle) every time they meet | Will they still meet if I stretch it? |
| `focus_3d` | The ellipsoid version in 3D, slowly turning, up to 610 balls | Does it work in 3D too? |
| `golden` | Every bounce moves the ball the same angle round a circle (1/φ², 1/π, 1/√2 … of a turn) — or the twist 55/144, which DOES close after 144 bounces | Will this pattern ever close? |
| `pendulum` | Pendulum wave: 14-22 pendulums drift into snakes and spirals and line up again at exactly T seconds (loops perfectly) | Will they line up again? |
| `rosette` | A planet whose orbit turns a little every lap draws a flower (like Mercury, much faster) | Why doesn't this orbit close? |
| `crush` | A hydraulic press in a bucket; every crushed ball splits into 3 smaller ones (1 → 10,000+), then the bucket bursts | Guess the final count |
| `shrink` | Every bounce shrinks the ball and grows the wall inward (radial spokes) until the wall wins | Ball vs wall |
| `devour` | A swarm eats pellets and multiplies; a black hole eats the swarm and grows until it swallows everything | Can it eat them all? |
| `butterfly` | 12-30 balls start a fraction of a pixel apart, move as one, then split; spikes pop them. Last ball alive wins | Butterfly effect / who survives |
| `multiply` | 1 ball, 3 breakable rings and x2/x3/x5/x10 tokens. 1 ball becomes hundreds | Guess the final count |
| `evolve` | The ball grows every bounce and leaves a rainbow tube behind until it fills the circle | Guess the bounces |
| `paint` | 4 balls paint the wall; most wall at 0s wins (can use trending words as names) | Pick one |
| `elim` | 5-6 balls in a spinning ring with a gap; fall out = eliminated (can use trending words) | Pick one |
| `rings` | One ball breaks out of 6-9 spinning rings | Guess the time |
| `grow` | Growing ball, neon style | Guess the bounces |
| `escape` | The original: first ball out of the ring wins | Pick a color |

The first three copy what works best in this niche (black background, thin neon lines, a small
question at the top, "Did you recognize the music?" at the bottom) — without paying for a
simulator tool, without a watermark, and without copyrighted songs.

- The daily lineup **rotates** (`squeeze,fourier,race_crush,galton,shrink,…`): the best formats by median views
  (squeeze, shrink, hammer, race_crush) come back most often and about a third are the ManimGL formats.
  ManimGL needs `pip install -r requirements-mgl.txt` (and `xvfb` on a machine without a screen); the workflow does this. Override with the repo variable `FORMATS`.
- **Seamless loops**: every video ends with a 0.4 s cross-fade back to its first frame, so when
  Shorts replays it the loop is invisible (the top channels in this niche all do this).
- **Trend scout** (`shorts/trends.py`): finds trending slang/meme *words*, runs three safety
  checks, and lets one video a day use the approved words as ball names ("Aura vs Rizz vs Goat").
  Trending *audio* is never used. **Off by default**; set the repo variable `TRENDS = on` to enable.
- **Music**: only melodies composed before 1910, written out note by note and synthesized by
  the code (`shorts/melodies.py`). Never add pop / film / Bollywood / game music.

```
shorts/crush.py shrink.py devour.py butterfly.py multiply.py evolve.py paint.py elim.py rings.py grow.py escape.py   one file per format
shorts/trends.py     trend scout: trending words -> 3 safety checks -> state/trends.json
shorts/fx.py         shared drawing (balls, glow rings, particles, scoreboards, end banner)
shorts/melodies.py   public-domain tunes (Beethoven, Grieg, Mozart, Pachelbel, trad.)
shorts/metadata.py   title / description / tags per format (never spoils the result)
shorts/batch.py      renders the day's lineup -> out/<date>/ + manifest.json + UPLOAD_SHEET.txt
shorts/upload.py     YouTube Data API upload with scheduled publishAt
auth_setup.py        one-time OAuth -> refresh token
.github/workflows/daily-shorts.yml   daily cron + "Run workflow" button
```

## Run locally

```bash
sudo apt install ffmpeg libcairo2-dev pkg-config      # mac: brew install ffmpeg cairo pkg-config
pip install -r requirements.txt
python -m shorts.batch --count 4 --date test          # -> out/test/01_rings_XXXX.mp4 ...
FORMATS=paint python -m shorts.batch --count 1 --date test   # just one format
```

## Step 1: Put the repo on GitHub (5 min)

1. Create a new **public** repo (public repos get unlimited free Actions minutes; private repos get 2,000 min/month, which is also enough).
2. Push this folder to the repo.
3. Go to **Actions → Daily Shorts → Run workflow** to test it once.
4. When it finishes, download the `shorts-N` artifact. It holds 4 MP4s, a cover image for each, and `UPLOAD_SHEET.txt` with every title, description and tags.

From then on it runs every morning at 07:00 IST.

## Step 2: Upload (Phase 1, manual)

> ⚠️ **YouTube rule:** videos uploaded through the API from an *unverified* Google Cloud
> project stay locked to **private**, and you can't change them to public later.
> Until your project passes the free audit (Step 4), upload by hand.

Every day, download the artifact. In YouTube Studio, click **Create → Upload** and add each MP4. Copy its title and description from `UPLOAD_SHEET.txt`, set **"No, it's not made for kids"**, and schedule it. All 4 take about 5 minutes.

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

## Fixed slots: 6 Shorts a day, every 4 hours (`PACING = slots`)

Repo variable `PACING = slots` (with `AUTO_UPLOAD = true`): the daily batch renders up to 6 Shorts and
queues them; **Actions → Shorts Pacer** uploads every queued Short and lets YouTube publish it at the
next free slot: **03:30, 07:30, 11:30, 15:30, 19:30, 23:30 IST** (override with `PUBLISH_SLOTS`).
No view checks. YouTube publishes at the exact minute, so late GitHub runs don't matter. At most
`PACE_DRAIN_MAX` = 3 uploads per run (small API bursts). The batch renders fewer Shorts when more than
12 are already waiting (queue + scheduled), so the buffer stays around 1-2 days.

## Smart pacing (optional): hold the next Short while one is taking off

Repo variable `PACING = on` (together with `AUTO_UPLOAD = true`) switches Shorts from fixed
time slots to "one Short at a time":

1. The daily batch renders the Shorts and puts them in a **queue** (assets of a GitHub release
   called `pacer-queue`, so the videos never go into git history). The long Battle Royale video
   is still scheduled normally, at `LONG_SLOTS` (default `21:00` IST).
2. **Actions → Shorts Pacer** runs every hour. It reads the live Short's views / likes / comments
   and decides (all numbers are repo variables, defaults shown):

   | Situation | Action |
   |---|---|
   | younger than `PACE_CHECK_H` = 4 h | wait (YouTube is still testing it) |
   | under `PACE_MIN_VIEWS` = 1,000 at 4 h | release the next Short (unless it's doubling — then 1 grace hour) |
   | 1k+ but not doubling in 2 h (`PACE_HOT_GROWTH` = 2) | watch 1 more hour (`PACE_GRACE_H`), then release |
   | doubled in 2 h = **hot** | hold until `PACE_TARGET` = 10,000 views |
   | hot but growth falls under +15 % / 2 h (`PACE_STALL_GROWTH` = 1.15) | release |
   | target reached and still strong (+25 % / 2 h, or 4 %+ likes while growing) | hold, target × 2 (20k, 40k …) |
   | live longer than `PACE_MAX_HOLD_H` = 24 h | release anyway (safety cap) |

3. Which Short goes next: anything queued for 3+ days first; otherwise the format with the best
   median views in the Channel Watcher stats, never the same format as the last two.
4. Rendering stops piling up: when `PACE_QUEUE_MAX` = 12 Shorts are already waiting, the daily
   batch renders fewer (or none).

Every hourly run writes its decision in the run summary (Actions → Shorts Pacer → latest run).
Try the rules offline: `python -m shorts.pacer simulate`. See the queue: `python -m shorts.pacer status`.
Turn it off again: delete the `PACING` variable — the old fixed slots come back.

## Ball Battle Royale (2-3 min long video, OFF by default)

Off by default now (Shorts only). Turn it back on with the repo variable `EXTRA_FORMATS = royale`.

Every day's batch also renders one **Ball Battle Royale** (`shorts/royale.py`), a 2:15-2:45
**landscape 1920x1080 video** (a normal YouTube video, not a Short) with its own 1280x720
thumbnail. 8-10 ball characters with reacting faces fight in a big arena. Weapons drop in (sword, blaster,
hammer, laser, bomb) plus heal / shield / speed / GIANT. After about a minute the electric walls
close in. Kill feed, roster with HP bars, "FIRST BLOOD!", "FINAL DUEL!", winner with crown.
Category: Gaming. The title has no #shorts.
- Custom thumbnail: uploaded automatically with `thumbnails.set`. This only works on a
  **phone-verified channel** (youtube.com/verify, free). If not verified, the video still
  uploads and YouTube picks a frame.

- Faces: `assets/balls/<color>/<emotion>.png`, cut from the character sheets with
  `python tools/extract_sprites.py <sheets folder> assets/balls`.
- Music and sound effects are synthesized in code (`shorts/royale_audio.py`), nothing copyrighted.
- A hidden "director" paces the damage so eliminations are spread over the whole video.
- Turn it off: repo variable `EXTRA_FORMATS = none`. Test alone:
  `FORMATS=royale EXTRA_FORMATS=none python -m shorts.batch --count 1 --date test`
- Publish slots are now 5 a day: `08:30,12:30,15:30,18:30,21:00` (the royale gets the last one).

## Tuning

- Repo variable `FORMATS` sets the rotating lineup (a format can appear more than once to give it more weight).
- Repo variable `TRENDS = on` turns the trend scout on (default off); `TREND_VIDEOS` (env) = trend-word videos per day (default 1).
- Every decision of the trend scout (approved / rejected + reason) is in `state/trends.json`.
- Each format file has `HOOKS` / `SUBS` (on-screen text) and `is_good()`, which decides what counts as a
  good video (length, close finish, lead changes…). Seeds that fail it are skipped.
- Titles and descriptions are in `shorts/metadata.py`.
- Add tunes to `shorts/melodies.py`. Use only public-domain compositions, and the audio must be synthesized by the code, not copied from a recording.

## Staying monetizable

YouTube's "inauthentic content" policy can keep mass-produced, near-identical videos out of the
Partner Program. That is why there are several formats with different goals, and why hooks, colors,
melodies and speeds rotate. Keep it varied:
- Keep at least 3 formats in the lineup, and add new ones over time (balls that multiply, mazes…).
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

## Channel Watcher agent (watch-only)

`shorts/watch.py` + `.github/workflows/channel-watch.yml` run every morning (09:41 IST):
reads all videos + YouTube Analytics (retention, watch time, subs gained), works out each
video's format, and posts a **GitHub Issue** (label `channel-report`) with the format
leaderboard, best publish slots, top / weakest videos and a short Hinglish summary from
Gemini (free tier, optional). Yesterday's report issue is closed. Daily snapshots: `state/stats.json`.

One-time setup:
1. Google Cloud console -> APIs & Services -> Library -> enable **YouTube Analytics API**.
2. Run `python auth_setup.py` again on your laptop (it now asks for read-only stats access too)
   and replace the `YT_REFRESH_TOKEN` secret with the new value.
3. Actions -> Channel Watcher -> Run workflow. The report appears under Issues.
   Test locally without APIs: `python -m shorts.watch --demo`.

