"""Turn a topic into a short, fact-checked script (via Gemini)."""
import json, random

from . import llm, sources

CATEGORY_LABEL = {"ai_news": "AI NEWS", "discovery": "NEW DISCOVERY",
                  "explainer": "SCIENCE EXPLAINED", "fun": "FUN FACT", "money": "MONEY SCIENCE"}

STYLE = """You write scripts for a faceless English YouTube Shorts channel about science, AI and
mind-blowing facts. Audience: curious adults and teens worldwide.
Rules:
- Total narration 110-140 words (about 45-55 seconds). Simple words, short sentences, energetic.
- Follow this 5-STAGE RETENTION STRUCTURE across 6 scenes (it keeps people watching to the end):
  1. GOLDEN HOOK (scene 1): a counter-intuitive claim or visual paradox in under 12 words.
     No "Did you know", no greetings, no slow intro.
  2. DISRUPT THE ASSUMPTION (scene 2): state what most people believe, then break it in one line.
  3. UNVEIL THE SECRET (scenes 3-4): the hidden mechanism or surprising detail, step by step.
  4. THE REAL TRUTH (scene 5): the satisfying "aha" payoff that explains everything.
  5. ELEVATE (scene 6): a punchy takeaway that makes the viewer see the world differently.
  Then "outro": a debate-style question that people will want to answer in the comments.
- Each scene is 1-2 sentences of narration plus the visuals to show while it is spoken.
- "visual_query": a 2-4 word search phrase for STOCK VIDEO footage of something concrete and
  filmable that matches the line (e.g. "galaxy stars", "scientist microscope", "ocean waves",
  "stock market screen", "brain scan"). No abstract ideas, no names of people or brands.
- "visual_alts": two broader fallback search phrases (e.g. ["space", "night sky"]).
- "image_prompt": a vivid cinematic prompt for an AI image, used only if no footage is found
  (no text, no logos, no real people's faces).
- Only state facts you are highly confident are true. No made-up numbers. Round numbers are fine.
- End with "outro": a short question that makes viewers comment.
- Never give financial, medical or legal advice.
- The title must be accurate: no exaggerated or misleading claims (no "invented", "changed forever"
  unless literally true)."""

SCHEMA = """JSON shape:
{"title": "catchy YouTube title, max 70 chars, no hashtags",
 "hook_text": "max 6 words shown big on screen at the start",
 "scenes": [{"stage": "hook|disrupt|secret|truth|elevate", "narration": "...",
             "visual_query": "...", "visual_alts": ["...", "..."], "image_prompt": "..."}],   // 6 scenes
 "outro": "question for the comments, max 12 words",
 "description": "2-3 sentence YouTube description",
 "tags": ["8-12 lowercase tags"]}"""


def pick_news(kind, history):
    used = {v.get("link") for v in history if v.get("link")}
    items = sources.fetch_items(kind, used_links=used)
    if not items:
        return None
    menu = "\n".join(f"{i}. {it['title']} — {it['summary'][:200]}" for i, it in enumerate(items))
    q = (f"Pick the ONE story below that would make the most fascinating 45-second YouTube Short "
         f"for a general audience (wow factor, easy to explain, not politics, not a product sale, "
         f"not a death or tragedy).\n\n{menu}\n\nReply as JSON: {{\"index\": <number>}}")
    try:
        idx = int(llm.ask_json(q)["index"])
        return items[idx] if 0 <= idx < len(items) else items[0]
    except Exception:
        return items[0]


def pick_evergreen(kind, history, rng):
    area = rng.choice(sources.EVERGREEN_AREAS[kind])
    recent = [v["topic"] for v in history[-80:]]
    what = {"explainer": "a 'how/why does X work' science explainer",
            "fun": "one jaw-dropping, true fun fact",
            "money": "a surprising, well-documented fact about the science, psychology or history of "
                     "money and markets (e.g. a famous bubble, a cognitive bias, how compounding works). "
                     "Educational only, no investment advice, no gossip about private lives"}[kind]
    q = (f"Suggest {what} about {area} for a YouTube Short. It must be well-established and "
         f"verifiable. Avoid these recent topics: {json.dumps(recent)}.\n"
         f"Reply as JSON: {{\"topic\": \"short topic name\", \"angle\": \"one-line hook idea\"}}")
    return llm.ask_json(q)


def write(kind, history, rng):
    """Returns a script dict ready for voice/visuals."""
    label = CATEGORY_LABEL[kind]
    src = None
    if kind in ("ai_news", "discovery"):
        src = pick_news(kind, history)
        if src is None:  # feeds down -> fall back to an explainer
            kind, label = "explainer", CATEGORY_LABEL["explainer"]
    if src:
        topic = src["title"]
        brief = (f"Make a Short about this real news story. Use ONLY facts from the source text "
                 f"plus widely known background. Say it is recent news (no exact dates).\n"
                 f"SOURCE ({src['source']}): {src['title']}\n{src['summary']}")
    else:
        idea = pick_evergreen(kind, history, rng)
        topic = idea["topic"]
        brief = f"Topic: {idea['topic']}. Angle: {idea.get('angle', '')}"

    script = llm.ask_json(f"{STYLE}\n\nCategory: {label}\n{brief}\n\n{SCHEMA}")
    script = _ensure_length(script)
    script = fact_check(script, src)
    script.update(kind=kind, category=label, topic=topic,
                  source=src and {"title": src["title"], "link": src["link"], "name": src["source"]})
    return script


def _words(script):
    return sum(len(sc.get("narration", "").split()) for sc in script.get("scenes", []))


def _ensure_length(script, min_words=100):
    """Short scripts lose the 5-stage arc; ask once to expand them."""
    if _words(script) >= min_words:
        return script
    try:
        longer = llm.ask_json(
            f"This Short script is only {_words(script)} words. Expand it to 115-135 words total by "
            f"adding concrete, TRUE detail (no new statistics unless certain), keeping the 5-stage "
            f"structure (hook, disrupt, secret, truth, elevate), the same JSON shape and 6 scenes.\n\n"
            f"{json.dumps(script, ensure_ascii=False)}")
        if longer.get("scenes") and _words(longer) > _words(script):
            return longer
    except Exception:
        pass
    return script


def fact_check(script, src):
    """Second pass: remove or soften anything not clearly true."""
    ctx = f"Source text: {src['title']} — {src['summary']}\n" if src else ""
    q = (f"You are a strict science fact-checker. {ctx}Check every claim in this YouTube Short "
         f"script. Rewrite any narration line that is false, exaggerated, or not supported by the "
         f"source/well-established science so that it is accurate (keep the same energy and length). "
         f"Do not add new claims. Return the SAME JSON structure with an extra field "
         f"\"confidence\": \"high\" | \"medium\" | \"low\" for the final script.\n\n"
         f"{json.dumps(script, ensure_ascii=False)}")
    try:
        checked = llm.ask_json(q)
        if checked.get("scenes"):
            return checked
    except Exception:
        pass
    script["confidence"] = "medium"
    return script
