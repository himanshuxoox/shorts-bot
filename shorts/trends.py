"""
Trend scout: finds trending meme words / slang, checks every word for risk, and keeps only
the safe ones. The daily batch can then use them as ball names, e.g. "AURA vs RIZZ vs GOAT".

    GEMINI_API_KEY=... python -m shorts.trends        # scout + check -> state/trends.json
    python -m shorts.trends --offline                 # test the checks on sample words, no API

Only WORDS are taken from trends. Trending AUDIO is never downloaded or used: almost all of it
is somebody's copyrighted recording, and downloading from YouTube breaks its terms.

A word is used only if ALL of these pass (fail closed: any error = rejected):
  1. local rules  - short, plain text, not on the brand / profanity block lists, not used in
                    the last 7 days
  2. safety judge - Gemini answers a fixed checklist (real person? brand? copyrighted
                    character? song lyric? profanity? sexual? drugs? violence? politics?
                    insult?) and must say family-friendly with high confidence
  3. second judge - an independent yes/no brand-safety review must also say YES
Every decision and its reason is written to state/trends.json, so you can audit it.
"""
import argparse, datetime as dt, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state", "trends.json")
IST = ZoneInfo("Asia/Kolkata")
COOLDOWN_DAYS = 7

# Brands, franchises, characters and creators that must never be used (trademark / copyright /
# likeness). Not complete on purpose — the Gemini judges catch the rest.
BLOCK_BRANDS = {
    "APPLE", "IPHONE", "SAMSUNG", "NIKE", "ADIDAS", "GUCCI", "PRADA", "COCA COLA", "PEPSI",
    "MCDONALDS", "STARBUCKS", "TESLA", "DISNEY", "MARVEL", "DC", "PIXAR", "NETFLIX", "POKEMON",
    "PIKACHU", "MINECRAFT", "ROBLOX", "FORTNITE", "GTA", "MARIO", "SONIC", "BARBIE", "LEGO",
    "SKIBIDI", "SKIBIDI TOILET", "MRBEAST", "BEAST", "SPONGEBOB", "SHREK", "MINIONS", "GROGU",
    "BLUEY", "PEPPA", "ELSA", "SPIDERMAN", "BATMAN", "SUPERMAN", "HULK", "NARUTO", "GOKU",
    "TIKTOK", "YOUTUBE", "INSTAGRAM", "CHATGPT", "OPENAI", "GOOGLE", "PRIME", "LABUBU",
    "TUNG TUNG", "TRALALERO", "BOMBARDIRO", "BRAINROT",
}
# Profanity / crude words. Slurs are caught by the judges; this list just short-circuits.
BLOCK_WORDS = {
    "FUCK", "SHIT", "BITCH", "ASS", "DAMN", "HELL", "CRAP", "PISS", "DICK", "COCK", "PUSSY",
    "SEX", "SEXY", "NUDE", "HORNY", "THOT", "GYATT", "GYAT", "SUS", "KILL", "DIE", "DEAD",
    "GUN", "DRUG", "WEED", "HIGH", "DRUNK", "BOOBA", "MEWING", "LOOKSMAXX", "EDGING",
}

FALLBACK_WORDS = [  # long-lived, harmless slang; used only if the scout finds nothing
    "AURA", "RIZZ", "GOAT", "VIBES", "NO CAP", "SLAY", "BUSSIN", "MAIN CHARACTER", "LOCKED IN",
    "W", "BASED", "GLOW UP", "LEGEND", "BOSS", "CHAMP",
]


def today():
    return dt.datetime.now(IST).strftime("%Y-%m-%d")


def load():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {"date": None, "approved": [], "rejected": [], "used": {}}


def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ gathering
def google_trends(geos=("US", "IN", "GB")):
    """Daily trending searches (public RSS, no key). Mostly news/names -> most get rejected,
    which is fine: it shows what people are talking about."""
    out = []
    for g in geos:
        try:
            req = urllib.request.Request(f"https://trends.google.com/trending/rss?geo={g}",
                                         headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=15).read())
            out += [(it.findtext("title") or "").strip() for it in root.iter("item")]
        except Exception as e:
            print(f"[trends] google trends {g}: {e}", file=sys.stderr)
    return [w for w in out if w]


def _gemini(prompt, search=False):
    from facts.llm import client, TEXT_MODELS
    last = None
    for model in TEXT_MODELS:
        try:
            kw = {"tools": [{"type": "google_search"}]} if search else {}
            it = client().interactions.create(model=model, input=prompt, **kw)
            if it.output_text:
                return it.output_text
        except Exception as e:
            last = e
    raise RuntimeError(f"gemini failed: {last}")


def _json(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("no JSON in reply")
    return json.loads(m.group(0))


def gemini_scout():
    """Ask Gemini (with Google Search grounding if the free tier allows it) for current
    meme words. Falls back to the model's own knowledge if search grounding fails."""
    q = ("Find 20 slang words or short meme phrases (1-2 words) that are trending RIGHT NOW on "
         "TikTok, YouTube Shorts and Instagram Reels this week. Prefer words a teenager would "
         "comment, like 'aura' or 'rizz'. Do NOT include names of people, brands, games, shows, "
         "songs or characters. Return JSON: {\"words\": [{\"word\": \"...\", \"meaning\": \"...\"}]}")
    for search in (True, False):
        try:
            data = _json(_gemini(q, search=search))
            words = [w.get("word", "") for w in data.get("words", []) if isinstance(w, dict)]
            if words:
                return words, ("google_search" if search else "model_knowledge")
        except Exception as e:
            print(f"[trends] gemini scout (search={search}): {e}", file=sys.stderr)
    return [], "none"


# ------------------------------------------------------------------ checking
def normalize(w):
    w = re.sub(r"[^A-Za-z0-9 ]", "", str(w)).strip().upper()
    return re.sub(r"\s+", " ", w)


def local_check(word, used):
    if not word or len(word) < 1 or len(word) > 14:
        return "length"
    if len(word.split()) > 2:
        return "more than 2 words"
    if word in BLOCK_BRANDS or any(b in word for b in BLOCK_BRANDS if len(b) > 3):
        return "brand / franchise / character"
    if word in BLOCK_WORDS or any(p in word.split() for p in BLOCK_WORDS):
        return "profanity / unsafe word"
    last = used.get(word)
    if last and (dt.date.fromisoformat(today()) - dt.date.fromisoformat(last)).days < COOLDOWN_DAYS:
        return f"used recently ({last})"
    return None


FLAGS = ["real_person", "brand_or_trademark", "copyrighted_character_or_franchise", "song_or_lyric",
         "profanity_or_slur", "sexual_meaning", "drugs_or_alcohol", "violence_or_tragedy",
         "politics_or_religion", "insult_or_bullying", "hidden_meaning"]


def judge(words):
    """Checklist judge. Returns {word: (ok, reason, meaning)}."""
    q = ("You are a strict brand-safety reviewer for a family-friendly YouTube Shorts channel. "
         "Each word below would be shown as the NAME of a bouncing ball in a satisfying video. "
         "For EACH word answer every flag honestly, including slang meanings you know of. "
         f"Flags: {', '.join(FLAGS)}. Also give 'meaning' (short), 'family_friendly' (bool) and "
         "'confidence' (high/medium/low).\n"
         'Return JSON: {"results": [{"word": "...", "meaning": "...", ' +
         ", ".join(f'"{f}": false' for f in FLAGS) +
         ', "family_friendly": true, "confidence": "high"}]}\n\nWords: ' + json.dumps(words))
    data = _json(_gemini(q))
    out = {}
    for r in data.get("results", []):
        w = normalize(r.get("word", ""))
        bad = [f for f in FLAGS if r.get(f) is not False]   # missing flag counts as bad
        if bad:
            out[w] = (False, "judge: " + ", ".join(bad), r.get("meaning", ""))
        elif r.get("family_friendly") is not True:
            out[w] = (False, "judge: not family friendly", r.get("meaning", ""))
        elif r.get("confidence") != "high":
            out[w] = (False, f"judge: confidence {r.get('confidence')}", r.get("meaning", ""))
        else:
            out[w] = (True, "ok", r.get("meaning", ""))
    return out


def second_opinion(words):
    """Independent yes/no review. Returns {word: (ok, reason)}."""
    q = ("Would a cautious YouTube brand-safety reviewer approve each of these words as the "
         "on-screen name of a bouncing ball in a video that kids might also watch? Say NO if the "
         "word refers to a real person, a brand, a game, a show, a song, a copyrighted character, "
         "or has any crude, sexual, drug, violent, political or mocking meaning.\n"
         'Return JSON: {"answers": [{"word": "...", "approve": "YES" or "NO", "reason": "..."}]}'
         "\n\nWords: " + json.dumps(words))
    data = _json(_gemini(q))
    return {normalize(a.get("word", "")): (a.get("approve") == "YES", a.get("reason", ""))
            for a in data.get("answers", [])}


def check(candidates, used, offline=False):
    approved, rejected = [], []
    seen, pending = set(), []
    for c in candidates:
        w = normalize(c)
        if not w or w in seen:
            continue
        seen.add(w)
        why = local_check(w, used)
        if why:
            rejected.append(dict(word=w, reason=why))
        else:
            pending.append(w)
    if offline:
        for w in pending:
            rejected.append(dict(word=w, reason="offline mode: AI checks skipped (fail closed)"))
        return approved, rejected
    try:
        j = judge(pending)
        pass1 = [w for w in pending if j.get(w, (False,))[0]]
        for w in pending:
            if w not in pass1:
                rejected.append(dict(word=w, reason=j.get(w, (False, "judge: no answer"))[1]))
        s2 = second_opinion(pass1) if pass1 else {}
        for w in pass1:
            ok, why = s2.get(w, (False, "second judge: no answer"))
            if ok:
                approved.append(dict(word=w, meaning=j[w][2]))
            else:
                rejected.append(dict(word=w, reason="second judge: " + why))
    except Exception as e:                       # fail closed
        for w in pending:
            rejected.append(dict(word=w, reason=f"check error: {e}"))
    return approved, rejected


# ------------------------------------------------------------------ used by the batch
def todays_words():
    st = load()
    return [a["word"] for a in st.get("approved", [])] if st.get("date") == today() else []


def take(words, k, rng):
    """Pick k approved words for one video and mark them as used."""
    if len(words) < k:
        return None
    pick = rng.sample(words, k)
    st = load()
    for w in pick:
        st.setdefault("used", {})[w] = today()
    st["approved"] = [a for a in st["approved"] if a["word"] not in pick]
    save(st)
    for w in pick:
        words.remove(w)
    return pick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    st = load()
    used = st.get("used", {})
    if a.offline:
        cands, source = ["aura", "Skibidi", "rizz", "Taylor Swift", "gyatt", "GOAT",
                         "Minecraft movie", "no cap", "sigma boy"], "offline sample"
    else:
        found, source = gemini_scout()
        cands = found + google_trends()
        if not found:
            cands += FALLBACK_WORDS
    approved, rejected = check(cands, used, offline=a.offline)
    st.update(date=today(), source=source, approved=approved, rejected=rejected[:120])
    save(st)
    print(f"[trends] source={source}  approved {len(approved)}  rejected {len(rejected)}")
    for x in approved:
        print(f"  OK   {x['word']:<16} {x.get('meaning', '')}")
    for x in rejected[:40]:
        print(f"  NO   {x['word']:<16} {x['reason']}")


if __name__ == "__main__":
    main()
