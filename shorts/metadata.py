"""Title / description / tags for each Short. Never reveals the winner."""
import random

EMOJI = {"RED": "🔴", "BLUE": "🔵", "GREEN": "🟢", "YELLOW": "🟡", "PURPLE": "🟣",
         "ORANGE": "🟠", "PINK": "🩷", "CYAN": "🩵"}

# (style id, template) — ids are shared so a batch never repeats a style
TITLES_2 = [
    ("which", "Which ball escapes first? {e}"),
    ("versus", "{a} vs {b} — who gets out first? {e}"),
    ("only", "Only one ball escapes this ring 😳 {e}"),
    ("pick", "Pick a color before it ends! {e}"),
    ("close", "This race was too close 😱 {e}"),
]
TITLES_N = [
    ("which", "Which ball escapes first? {e}"),
    ("versus", "{n} balls, 1 exit — who wins? {e}"),
    ("only", "Only one ball gets out 😳 {e}"),
    ("pick", "Pick your color before it ends! {e}"),
    ("close", "Can you guess the winner? {e}"),
]
TAGS = ["shorts", "satisfying", "simulation", "physics simulation", "ball escape",
        "ball race", "marble race", "oddly satisfying", "satisfying video", "which ball wins",
        "bouncing ball", "asmr", "relaxing", "color race"]
HASHTAGS = "#shorts #satisfying #simulation #ballrace #oddlysatisfying"


def build(facts: dict, seed: int) -> dict:
    rng = random.Random(seed * 31 + 7)
    cols = facts["colors"]
    e = "".join(EMOJI[c] for c in cols)
    pool = TITLES_2 if len(cols) == 2 else TITLES_N
    style, tpl = rng.choice(pool)
    title = tpl.format(e=e, a=cols[0].title(), b=cols[1].title(), n=len(cols))
    title = f"{title} #shorts"[:100]
    desc = "\n".join([
        f"{' vs '.join(c.title() for c in cols)} — every bounce makes the ball bigger and the exit harder to hit.",
        "Which one did you pick? Tell me in the comments 👇",
        "",
        "New simulation races every day — subscribe so you don't miss tomorrow's!",
        "",
        f"🎵 Melody: {facts['melody']} (public domain), synthesized for this video.",
        "Simulation is 100% computer-generated with code. No real footage.",
        "",
        HASHTAGS,
    ])
    tags = TAGS + [f"{c.lower()} ball" for c in cols]
    return dict(title=title, title_style=style, description=desc, tags=tags, categoryId="24")
