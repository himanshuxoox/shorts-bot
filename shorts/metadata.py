"""Title / description / tags for each Short. Never reveals the result."""
import random

EMOJI = {"RED": "🔴", "BLUE": "🔵", "GREEN": "🟢", "YELLOW": "🟡", "PURPLE": "🟣",
         "ORANGE": "🟠", "PINK": "🩷", "CYAN": "🩵"}

# (style id, template) — ids are unique per format so a batch never repeats a style
TITLES = {
    "escape2": [
        ("which", "Which ball escapes first? {e}"),
        ("versus", "{a} vs {b} — who gets out first? {e}"),
        ("only", "Only one ball escapes this ring 😳 {e}"),
        ("pick", "Pick a color before it ends! {e}"),
        ("close", "This race was too close 😱 {e}"),
    ],
    "escapeN": [
        ("which", "Which ball escapes first? {e}"),
        ("versus", "{n} balls, 1 exit — who wins? {e}"),
        ("only", "Only one ball gets out 😳 {e}"),
        ("pick", "Pick your color before it ends! {e}"),
        ("close", "Can you guess the winner? {e}"),
    ],
    "rings": [
        ("canit", "Can this ball escape {r} rings? 😳"),
        ("guess", "Guess how long it takes to break {r} rings ⏱️"),
        ("versus", "1 ball vs {r} spinning rings 🌀"),
        ("last", "Wait for the last ring 😱"),
        ("time", "How fast can it escape {r} rings? Guess! ⏱️"),
    ],
    "grow": [
        ("fill", "Will it fill the whole circle? 😳"),
        ("guess", "Guess the bounce count 🤔"),
        ("grows", "This ball grows with every bounce… 🫧"),
        ("howmany", "How many bounces to fill this circle?"),
        ("end", "Wait for the ending 😱"),
    ],
    "paint": [
        ("pick", "Pick a color before it ends! {e}"),
        ("which", "Which color takes over the wall? {e}"),
        ("battle", "4 color battle — who wins? {e}"),
        ("close", "This color war was too close 😱 {e}"),
        ("most", "Most wall wins — pick one! {e}"),
    ],
    "butterfly": [
        ("bfx", "The Butterfly Effect of a Bouncing Ball 🦋"),
        ("same", "{n} balls, same start… who survives? 🦋"),
        ("spikes", "Which ball survives the spikes? 😳"),
        ("chaos", "Tiny difference, totally different ending 🦋"),
        ("music", "Did you recognize the music? 🎵🦋"),
    ],
    "evolve": [
        ("evolve", "With every bounce, the ball evolves… 🌈"),
        ("fill", "Will it fill the whole circle? 🌈"),
        ("guess", "Guess the bounce count 🤔🌈"),
        ("music", "Did you recognize the music? 🎵🌈"),
        ("art", "Every bounce paints a new color 🌈"),
    ],
    "multiply": [
        ("will", "Will the Ball Multiply? 😳"),
        ("guess", "1 ball… guess how many at the end! 🤯"),
        ("rings", "Will the balls break every ring? 💥"),
        ("music", "Did you recognize the music? 🎵💥"),
        ("x10", "x2, x5, x10… how many balls? 🤯"),
    ],
    "shrink": [
        ("every", "Every bounce SHRINKS the ball and GROWS the wall 😳"),
        ("who", "Ball vs wall — who wins? 😳"),
        ("guess", "Guess how many bounces before the wall wins 🤔"),
        ("music", "Did you recognize the music? 🎵"),
    ],
    "devour": [
        ("ate", "The black hole ate the ENTIRE swarm 🕳️"),
        ("every", "Every ball it eats makes the black hole BIGGER 🕳️"),
        ("can", "Can the black hole eat them all? 😳"),
        ("music", "Did you recognize the music? 🎵🕳️"),
    ],
    "crush": [
        ("crushed", "It crushed one ball into {N} pieces 😳"),
        ("handle", "Every crushed ball splits into 3… how many can it handle? 🤯"),
        ("guess", "1 ball → ??? balls. Guess the final count!"),
        ("music", "Did you recognize the music? 🎵💥"),
    ],
    "royale": [
        ("who", "{n} Balls Battle Royale — Only 1 Survives! Pick Your Ball 👑"),
        ("pick", "Pick a Ball Before the Fight Starts! {n} Ball Battle Royale ⚔️"),
        ("royale", "Ball Battle Royale: Swords, Lasers & Bombs — Last Ball Standing Wins 👑"),
        ("weapons", "{n} Balls, Random Weapons, Only 1 Winner ⚔️ Who Survives?"),
        ("walls", "The Walls Are Closing In… Which Ball Survives? | Ball Battle Royale"),
    ],
    "paint_labels": [
        ("vs", "{L} — who wins? {e}"),
        ("pick", "Pick one: {L} {e}"),
        ("takeover", "Which one takes over? {L} {e}"),
    ],
    "elim_labels": [
        ("vs", "{L} — who survives? {e}"),
        ("pick", "Pick one — only 1 survives! {e}"),
        ("last", "Last one inside wins: {L} {e}"),
    ],
    "elim": [
        ("last", "Last ball inside wins! {e}"),
        ("pick", "Pick a color — only 1 survives {e}"),
        ("who", "Who survives till the end? {e}"),
        ("out", "Fall out = eliminated 😳 {e}"),
        ("n", "{n} balls, 1 survivor — who wins? {e}"),
    ],
}

FIRST_LINE = {
    "escape": "{vs} — every bounce makes the ball bigger and the exit harder to hit.",
    "rings": "One ball, {r} spinning rings. Every time it slips through a gap, that ring shatters.",
    "grow": "The ball grows a little on every bounce, so the bounces get faster and faster until it fills the circle.",
    "paint": "{vs} — every bit of wall a ball touches turns its color. Most wall when the clock hits zero wins.",
    "elim": "{vs} — fall out of the spinning ring and you're eliminated. Last ball inside wins.",
    "shrink": "Every bounce makes the ball a little smaller and the wall grows right where it hit. Who wins?",
    "devour": "A tiny swarm eats pellets and every few pellets each ball splits in two. Every ball the black hole eats makes it bigger.",
    "crush": "Every ball the press crushes splits into 3 smaller balls: 1, 3, 9, 27… until the bucket can't take it.",
    "butterfly": "{n} balls start almost exactly in the same spot. A difference smaller than a pixel decides who survives the spikes.",
    "evolve": "Every bounce makes the ball bigger and leaves a new color behind, until it fills the whole circle.",
    "royale": "{n} ball fighters, random weapon drops (sword, blaster, hammer, laser, bomb) and electric walls that close in. Last ball standing wins.",
    "multiply": "One ball, three rings, and multipliers that copy every ball that touches them. How many balls at the end?",
}
ASK = {
    "escape": "Which one did you pick? Tell me in the comments 👇",
    "rings": "What was your time guess? Tell me in the comments 👇",
    "grow": "How many bounces did you guess? Tell me in the comments 👇",
    "paint": "Which color did you pick? Tell me in the comments 👇",
    "elim": "Which color did you pick? Tell me in the comments 👇",
    "butterfly": "Did you recognize the music? Tell me in the comments 👇",
    "shrink": "Did you recognize the music? Tell me in the comments 👇",
    "devour": "Did you recognize the music? Tell me in the comments 👇",
    "crush": "What was your guess? And did you recognize the music? 👇",
    "evolve": "Did you recognize the music? And how many bounces did you guess? 👇",
    "multiply": "What was your guess? And did you recognize the music? 👇",
    "royale": "Which ball did you pick — and did it win? Tell me in the comments 👇",
}

TAGS = ["shorts", "satisfying", "simulation", "physics simulation", "oddly satisfying",
        "satisfying video", "bouncing ball", "asmr", "relaxing"]
EXTRA_TAGS = {
    "escape": ["ball escape", "ball race", "marble race", "which ball wins", "color race"],
    "rings": ["ball escape", "ring escape", "escape the rings", "spinning rings", "guess the time"],
    "grow": ["growing ball", "ball grows every bounce", "fill the circle", "guess the bounces"],
    "paint": ["color battle", "color war", "pick a color", "paint the wall", "which color wins"],
    "elim": ["elimination", "last one standing", "marble race", "ball battle", "which ball survives"],
    "shrink": ["ball shrinks", "growing wall", "bouncing ball music", "guess the song", "satisfying physics"],
    "devour": ["black hole", "swarm", "eats everything", "bouncing ball music", "guess the song"],
    "crush": ["hydraulic press", "crushed ball", "ball splits", "how many balls", "guess the song"],
    "butterfly": ["butterfly effect", "chaos theory", "bouncing ball music", "guess the song", "spikes"],
    "evolve": ["ball evolves", "growing ball", "rainbow", "bouncing ball music", "guess the song"],
    "multiply": ["ball multiply", "multiplying balls", "ring break", "bouncing ball music", "guess the song"],
    "royale": ["battle royale", "ball battle", "ball fight", "last one standing", "pick a ball", "game simulation"],
}
HASHTAGS = {
    "escape": "#shorts #satisfying #simulation #ballrace #oddlysatisfying",
    "rings": "#shorts #satisfying #simulation #ringescape #oddlysatisfying",
    "grow": "#shorts #satisfying #simulation #bouncingball #oddlysatisfying",
    "paint": "#shorts #satisfying #simulation #colorbattle #oddlysatisfying",
    "elim": "#shorts #satisfying #simulation #elimination #oddlysatisfying",
    "butterfly": "#shorts #satisfying #butterflyeffect #bouncingball #oddlysatisfying",
    "shrink": "#shorts #satisfying #bouncingball #simulation #oddlysatisfying",
    "devour": "#shorts #satisfying #blackhole #simulation #oddlysatisfying",
    "crush": "#shorts #satisfying #hydraulicpress #simulation #oddlysatisfying",
    "evolve": "#shorts #satisfying #bouncingball #rainbow #oddlysatisfying",
    "multiply": "#shorts #satisfying #bouncingball #multiply #oddlysatisfying",
    "royale": "#battleroyale #ballbattle #simulation #marblerace #gaming",
}


def build(facts: dict, seed: int) -> dict:
    rng = random.Random(seed * 31 + 7)
    tpl_name = facts.get("template", "escape")
    cols = facts.get("colors") or []
    e = "".join(EMOJI[c] for c in cols)
    labels = facts.get("labels") or []
    if tpl_name == "escape":
        pool = TITLES["escape2" if len(cols) == 2 else "escapeN"]
    elif labels and f"{tpl_name}_labels" in TITLES:
        pool = TITLES[f"{tpl_name}_labels"]
    else:
        pool = TITLES[tpl_name]
    style, tpl = rng.choice(pool)
    L = " vs ".join(w.title() for w in labels)
    title = tpl.format(e=e, a=cols[0].title() if cols else "", b=cols[1].title() if len(cols) > 1 else "",
                       n=facts.get("n_balls", len(cols)), r=facts.get("n_rings", ""), L=L,
                       N=f"{facts.get('n_final', 0):,}")
    title = (title.strip() if tpl_name == "royale" else f"{title.strip()} #shorts")[:100]   # royale = normal video
    vs = " vs ".join(w.title() for w in (labels or cols))
    desc = "\n".join([
        FIRST_LINE[tpl_name].format(vs=vs, r=facts.get("n_rings", ""), n=facts.get("n_balls", "")),
        ASK[tpl_name],
        "",
        ("A new Ball Battle Royale every day — subscribe and pick your ball before the fight starts!"
         if tpl_name == "royale" else "New simulations every day — subscribe so you don't miss tomorrow's!"),
        "",
        (f"🎵 Melody: {facts['melody']} (public domain), synthesized for this video." if tpl_name != "royale"
         else "🎵 Music & sound effects: original, synthesized in code for this video."),
        "Simulation is 100% computer-generated with code. No real footage.",
        "",
        HASHTAGS[tpl_name],
    ])
    tags = (TAGS[1:] if tpl_name == "royale" else TAGS) + EXTRA_TAGS[tpl_name] + [f"{c.lower()} ball" for c in cols][:4] + [w.lower() for w in labels]
    return dict(title=title, title_style=f"{tpl_name}:{style}", description=desc, tags=tags,
                categoryId="20" if tpl_name == "royale" else "24")
