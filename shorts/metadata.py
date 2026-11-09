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
    "hammer": [
        ("hammer", "Every ball the hammer hits splits into 3… how many can it hold? 🔨"),
        ("guess", "1 ball → ??? balls. Guess the final count! 🔨"),
        ("crushed", "This hammer turned 1 ball into {N} 😳"),
        ("music", "Did you recognize the music? 🎵🔨"),
    ],
    "squeeze": [
        ("squeeze", "Every ball caught in the squeeze splits into 3 😳"),
        ("guess", "How many balls before the circle bursts? Guess! 🤯"),
        ("crushed", "4 bars, 1 ball… {N} balls at the end 😳"),
        ("music", "Did you recognize the music? 🎵💥"),
    ],
    "lasers": [
        ("stop", "Can the lasers stop the doubling? 🔴🔵"),
        ("every", "Every ball a laser hits becomes a LASER 😳"),
        ("who", "Doubling balls vs lasers — who wins? 🔴🔵"),
        ("music", "Did you recognize the music? 🎵🔵"),
    ],
    "race_lava": [
        ("pick", "Pick a color — who escapes the lava? {e}"),
        ("first", "First ball to the flag wins! Lava is coming 🔥 {e}"),
        ("survive", "Only the fastest ball survives the lava 😳 {e}"),
    ],
    "race_flood": [
        ("pick", "Pick a color — the rooms are flooding! {e}"),
        ("first", "Which ball escapes the flood first? 🌊 {e}"),
        ("survive", "The water is rising… who makes it out? 😳 {e}"),
    ],
    "race_crush": [
        ("pick", "Pick a color — dodge the crusher! {e}"),
        ("first", "First ball to the top wins (don't get crushed) 😳 {e}"),
        ("survive", "Crusher vs 4 balls — who survives? 💥 {e}"),
    ],
    "race_shrink": [
        ("pick", "Too big for the exit! Pick a color {e}"),
        ("first", "Only 2 shrink pads… who escapes? 😳 {e}"),
        ("survive", "Shrink or burn — which ball escapes? 🔥 {e}"),
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
    "focus": [
        ("same", "Will they all hit the same point? 🤯"),
        ("fib", "1, 2, 3, 5, 8… {N} balls. Do they ALL meet? 😳"),
        ("magic", "The magic point inside every ellipse ✨"),
        ("every", "Every single ball lands on ONE point 🎯"),
    ],
    "focus_stretch": [
        ("stretch", "Will they still meet if I stretch it? 🤔"),
        ("shape", "I keep changing the shape… do they still meet? 😳"),
        ("magic", "Stretch it, squash it — they STILL meet ✨"),
    ],
    "focus_3d": [
        ("3d", "Does it work in 3D too? 🤯"),
        ("meet", "{N} balls in 3D — will they all meet? 😳"),
        ("magic", "The ellipse trick… but in 3D ✨"),
    ],
    "golden": [
        ("close", "Will this pattern ever close? 🤔"),
        ("start", "Will the ball ever get back to the start? 😳"),
        ("golden", "The golden ratio does THIS to a bouncing ball ✨"),
        ("repeat", "Does this pattern EVER repeat? 🤯"),
    ],
    "pendulum": [
        ("line", "Will they line up again? 🤔"),
        ("wait", "Wait for them to line up… 😳"),
        ("wave", "{n} pendulums, one perfect moment ✨"),
        ("chaos", "Chaos… then THIS happens 🤯"),
    ],
    "rosette": [
        ("close", "Why doesn't this orbit close? 🤔"),
        ("what", "What is a rosette orbit? 🌸"),
        ("mercury", "Mercury's orbit secretly does this 🤯"),
        ("flower", "A planet that draws a flower 🌸"),
    ],
    "fourier": [
        ("circles", "Only circles. What will they draw? 🤯"),
        ("guess", "Spinning circles draw THIS… guess first 😳"),
        ("wait", "Wait for the last circle ✨"),
    ],
    "dpendulum": [
        ("apart", "{n} pendulums, almost the same start… 😳"),
        ("chaos", "Watch the exact moment it turns into CHAOS 🤯"),
        ("tiny", "A tiny difference. Then THIS happens 🌀"),
    ],
    "lorenz": [
        ("dots", "4,000 dots start together… where do they go? 🦋"),
        ("butterfly", "The butterfly effect, in 4,000 dots 🦋"),
        ("wait", "Wait for the butterfly ✨"),
    ],
    "chaosgame": [
        ("random", "Pick a random corner. Jump. Repeat. 🎲"),
        ("chance", "Pure chance draws THIS 🤯"),
        ("wait", "Random dots… wait for it 😳"),
    ],
    "timestable": [
        ("x2", "What does × 2 draw on a circle? 🤔"),
        ("guess", "Guess how many petals × 10 makes 🌸"),
        ("graph", "× 119 turns into graph paper?! 🤯"),
    ],
    "primespiral": [
        ("angle", "Every number n at angle n… then only primes 🤯"),
        ("rays", "Why do prime numbers make rays? 🤔"),
        ("spirals", "Prime numbers draw THIS 😳"),
    ],
    "threebody": [
        ("pick", "{n} suns. Pick a color! ☀️"),
        ("which", "Which suns get thrown out? 😳"),
        ("chaos", "The {n}-body problem in 20 seconds 🌌"),
    ],
    "metronomes": [
        ("touch", "24 metronomes. Nobody touches them 😳"),
        ("sync", "Wait for the metronomes to sync… 🤯"),
        ("chaos", "From chaos to perfect sync, by themselves ⏱️"),
    ],
    "galton": [
        ("where", "Where will {N} balls land? 🤔"),
        ("guess", "{N} random balls… guess the shape 😳"),
        ("bell", "Every ball is random. The result never is 🔔"),
    ],
    "chladni": [
        ("sand", "Sand on a metal plate… now add sound 🔊"),
        ("pitch", "Watch the sand when the pitch goes up 🤯"),
        ("draw", "Sound can draw with sand ✨"),
    ],
    "shrink_duo": [
        ("vs", "{a} vs {b} — every bounce SHRINKS the ball 😳 {e}"),
        ("pick", "Pick a color! Every bounce shrinks the ball {e}"),
        ("last", "Which ball lasts longer? 😳 {e}"),
    ],
    "shrink_shape": [
        ("shape", "Every bounce SHRINKS the ball and GROWS the wall 😳"),
        ("vs", "Ball vs wall — who wins? 😳"),
        ("music", "Did you recognize the music? 🎵"),
    ],
    "dish_3d": [
        ("same", "Will they all hit the same point? 🤯"),
        ("dish", "{N} balls vs a satellite dish 😳"),
        ("3d", "The dish trick in 3D 🤯"),
    ],
    "sphere_star": [
        ("fill", "Will the bounces ever fill the ball? 🤔"),
        ("golden", "The golden angle inside a sphere 🤯"),
        ("star", "1 ball draws a star… 120 balls draw THIS 😳"),
    ],
    "torus_knot": [
        ("back", "Will the ball ever come back? 🍩"),
        ("knot", "A ball on a donut ties a KNOT 🤯"),
        ("golden", "The golden ratio on a donut never closes 😳"),
    ],
    "nbody": [
        ("pick", "{n} suns. Pick a color! ☀️"),
        ("survive", "{n} suns, gravity only — will your color survive? 😳"),
        ("out", "Thrown out = OUT. Pick a sun! 🌌"),
    ],
    "dragonfold": [
        ("fold", "Fold a strip 10 times… what appears? 🐉"),
        ("open", "Open every fold to 90°… wait for it 😳"),
        ("dragon", "1,024 pieces of paper draw THIS 🤯"),
    ],
    "fourier3d": [
        ("top", "Spinning circles in 3D… what's the shape from the TOP? 🤯"),
        ("knot", "This 3D knot is secretly a picture 😳"),
        ("circles", "Only circles… but in 3D ✨"),
    ],
    "shrinksphere": [
        ("3d", "Every bounce SHRINKS the ball… in 3D 😳"),
        ("wall", "Ball vs a growing wall — in 3D 😳"),
        ("music", "Did you recognize the music? 🎵"),
    ],
    "sunflower3d": [
        ("angle", "Which angle makes a sunflower? 🌻"),
        ("golden", "137.5° is a magic angle 🤯"),
        ("turn", "Turn every seed by the same angle… 😳"),
    ],
    "hilbert3d": [
        ("cube", "Can ONE line fill a whole cube? 🤯"),
        ("corners", "One line, 4,096 corners 😳"),
        ("split", "Every corner splits into 8… 🧊"),
    ],
    "sides": [
        ("circle", "Every bounce adds a SIDE… when is it a circle? 😳"),
        ("triangle", "Can a triangle become a CIRCLE? 🤯"),
        ("music", "Every bounce adds a side 🎵 Did you recognize the music?"),
    ],
    "arms": [
        ("arms", "Every bounce adds an ARM 😳 {N} arms later…"),
        ("ring", "Wait for the ring… 🤯"),
        ("name", "Can you even say the name of this shape? 😳"),
    ],
    "spiral": [
        ("faster", "It gets FASTER until it hits the center 😳"),
        ("speed", "Every bounce makes it faster… how fast at the end? 🤯"),
        ("music", "Faster and faster 🎵 Did you recognize the music?"),
    ],
    "predator": [
        ("prey", "Every prey they catch BECOMES a predator 😳"),
        ("one", "1 predator vs {n} prey 🤯"),
        ("time", "How long until ALL {n} are caught? ⏱️"),
    ],
    "breakout": [
        ("faster", "Every brick makes the ball FASTER 😳"),
        ("all", "Can it break ALL the bricks? 🧱"),
        ("music", "Brick breaker 🎵 Did you recognize the music?"),
    ],
    "quadsplit": [
        ("split", "Every full box SPLITS into 4 😳"),
        ("small", "How SMALL can the boxes get? 🤯"),
        ("one", "One box → {N} boxes 😳"),
    ],
    "redring": [
        ("red", "Hit red = +3 balls 😳 until the whole ring is RED"),
        ("balls", "How many balls to turn the ring RED? 🔴"),
        ("spawn", "Every red bounce spawns 3 balls 🤯"),
    ],
    "sortwheel": [
        ("gradient", "Sorting algorithm… wait for the perfect gradient 🌈"),
        ("sound", "This is what sorting SOUNDS like 🔊"),
        ("algo", "Can a sorting algorithm fix the rainbow? 🌈"),
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
    "race_lava": "4 balls race through a maze to the exit flag while lava creeps through the corridors behind them. Touch the lava = OUT.",
    "race_flood": "4 balls race room to room to the exit flag while the rooms flood behind them. Touch the water = OUT.",
    "race_crush": "4 balls race up a hall to the exit while a crusher slams up and down and lava rises from below. Hide in the side alcoves!",
    "race_shrink": "4 balls are too BIG for the exit. Only 2 shrink pads, each works once — and the fire is closing in.",
    "hammer": "A drop hammer smashes the balls on the floor and every ball it crushes splits into 3: 1, 3, 9, 27… until the circle bursts.",
    "squeeze": "Four bars on springs snap into the middle. Every ball they squash splits into 3, until the circle can't hold any more.",
    "lasers": "Every ball keeps splitting in two. Every ball a laser hits turns into a new laser. Exponential vs exponential — who wins?",
    "royale": "{n} ball fighters, random weapon drops (sword, blaster, hammer, laser, bomb) and electric walls that close in. Last ball standing wins.",
    "multiply": "One ball, three rings, and multipliers that copy every ball that touches them. How many balls at the end?",
    "focus": "Balls start at one focus of an ellipse. After ONE bounce off the wall, every single ball passes through the other focus — at the same moment, every time. 1, 2, 3, 5, 8… up to {N}.",
    "focus_stretch": "Ellipse magic: every ball that starts at one focus bounces through the other focus. So what happens if I keep stretching and squashing the shape — even into a circle?",
    "focus_3d": "The ellipse focus trick works in 3D too: an ellipsoid sends every ball from one focus through the other — {N} balls, all at the same moment.",
    "golden": "Every bounce moves the ball the same angle around the circle: {A} of a full turn. If that number is irrational, the ball can never land on its start point again.",
    "pendulum": "{n} pendulums with slightly different lengths. Each one swings a little faster than the one below it — so they drift apart into waves and spirals… and then line up perfectly again.",
    "rosette": "A planet orbits a star, but gravity is a tiny bit stronger close to the star. So every lap the ellipse turns a little, and the path draws a rosette. Mercury's real orbit turns like this too (very slowly) — one of the clues for Einstein's general relativity.",
    "fourier": "A chain of spinning circles, each turning at a whole-number speed. With 2 circles you get a blob, with 16 a sketch, with 100+ the hidden picture appears (a Fourier series).",
    "dpendulum": "{n} double pendulums released at almost exactly the same angle. For a few seconds they move as one… then chaos takes over.",
    "lorenz": "4,000 points start almost at the same spot and follow the Lorenz equations (a simple weather model). They split apart and draw the famous butterfly — the butterfly effect.",
    "chaosgame": "The Chaos Game: pick a random corner, jump part of the way there, put a dot, repeat. Every move is random, yet a perfect fractal appears.",
    "timestable": "240 dots on a circle; dot n is joined to dot n × k. × 2 draws a heart (cardioid), × 3 two petals… and some big numbers make shapes you won't expect.",
    "primespiral": "Every whole number n is placed at distance n and angle n (radians). Zoom out: 6 spirals, 44 spirals — keep only the primes and they line up into 280 rays.",
    "threebody": "{n} suns start almost at rest and pull on each other with Newton's gravity. Close encounters fling suns out of the cluster — a sun that is thrown out is OUT.",
    "metronomes": "24 metronomes on a board that can slide a little. They start completely out of time, and the tiny pushes through the board pull them into perfect sync.",
    "galton": "A Galton board: {N} balls, each bounces left or right at random on every peg. Every single ball is unpredictable — together they always build the bell curve.",
    "chladni": "Chladni patterns: a metal plate vibrates with sound, sand slides away from the moving parts and gathers on the still lines. Higher pitch, more detailed pattern.",
    "shrink_duo": "{vs} — every bounce shrinks the ball that hit and grows the wall in its colour. Shrink to a dot and you're OUT.",
    "shrink_shape": "Every bounce makes the ball a little smaller and grows the wall right where it hit — this time inside a shape, in rainbow.",
    "dish_3d": "A satellite dish is a paraboloid: every ball that comes straight down bounces once and goes through the same point (the focus) at the same moment. 1, 2, 3, 5 … up to {N}.",
    "sphere_star": "Each ball bounces inside a sphere and turns by the golden angle every bounce. One ball draws a star; many balls draw a ball — with a perfectly hollow core no bounce can ever reach.",
    "torus_knot": "A ball circles a donut: 2 laps one way for every 3 the other ties a trefoil knot. Then 3:5, 5:8… and with the golden ratio it never comes back — it covers the whole donut.",
    "nbody": "{n} suns start almost at rest and pull on each other with Newton's gravity. Close encounters fling suns out of the cluster — a sun that is thrown out is OUT.",
    "dragonfold": "Fold a paper strip in half 10 times, then open every fold to exactly 90°. 1,024 pieces of paper draw the famous dragon curve.",
    "fourier3d": "100+ spinning circles, each turning at a whole-number speed, draw a 3D knot. Look at it from the top and a picture appears (a Fourier series).",
    "shrinksphere": "Every bounce makes the ball smaller and pushes the wall inward right where it hit — this time inside a sphere.",
    "sunflower3d": "Put every seed one angle further round and a little further out. 90° makes 4 lines, 137° makes spirals with gaps — the golden angle 137.5° packs them perfectly, like a real sunflower.",
    "hilbert3d": "The 3D Hilbert curve: 8 corners, then every corner splits into its own little curve — 64, 512, 4,096. Always ONE line that never crosses itself and fills the whole cube.",
    "sides": "A ball bounces inside a triangle and every bounce adds one more side — square, pentagon, hexagon … 48 sides, and it's a circle.",
    "arms": "Every bounce adds one more swinging arm to the cage and makes the ball a bit faster. Square, pentagon … over a hundred arms, and it becomes a glowing ring.",
    "spiral": "A ball zig-zags down a spiked spiral groove. Every wall hit makes it 1% faster — slow at the start, a blur at the center.",
    "predator": "{n} prey run from one predator. Every prey it catches becomes a predator too, so the hunters double and double until nobody is left.",
    "breakout": "No paddle — just a ball in a box of bricks. Every brick it breaks makes it a little faster, until it's a blur hunting the last ones.",
    "quadsplit": "One ball, one box. Every bounce fills the box a bit; when it's full it splits into 4 boxes, each with its own ball. 1, 4, 16 … {N}.",
    "redring": "Hit a blue segment and it turns red. Hit a red one and you get 3 new balls. It snowballs until the whole ring is red.",
    "sortwheel": "A color wheel cut into slices and shuffled, then a real sorting algorithm swaps it back one pair at a time. Every swap plays the color's note.",
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
    "race_lava": "Which color did you pick? Tell me in the comments 👇",
    "race_flood": "Which color did you pick? Tell me in the comments 👇",
    "race_crush": "Which color did you pick? Tell me in the comments 👇",
    "race_shrink": "Which color did you pick? Tell me in the comments 👇",
    "hammer": "What was your guess? And did you recognize the music? 👇",
    "squeeze": "What was your guess? And did you recognize the music? 👇",
    "lasers": "Did you think the lasers would win? Tell me in the comments 👇",
    "royale": "Which ball did you pick — and did it win? Tell me in the comments 👇",
    "focus": "Did you think they would ALL meet? Tell me in the comments 👇",
    "focus_stretch": "Did you think they would still meet? Tell me in the comments 👇",
    "focus_3d": "Did you guess it works in 3D? Tell me in the comments 👇",
    "golden": "What did you guess — will it close or not? 👇",
    "pendulum": "Did you wait for the line-up? Tell me in the comments 👇",
    "rosette": "Did you know orbits can do this? Tell me in the comments 👇",
    "fourier": "What did you guess it would draw? 👇",
    "dpendulum": "When did you see the chaos start? 👇",
    "lorenz": "Did you expect a butterfly? 👇",
    "chaosgame": "Did you think random dots could do this? 👇",
    "timestable": "Which k was your favourite? 👇",
    "primespiral": "Do you know why primes do this? Tell me below 👇",
    "threebody": "Which color did you pick? 👇",
    "metronomes": "How many seconds did it take? 👇",
    "galton": "Did you guess the shape? 👇",
    "chladni": "Which pattern was the best? 👇",
    "shrink_duo": "Which color did you pick? 👇",
    "shrink_shape": "Did you recognize the music? Tell me in the comments 👇",
    "dish_3d": "Did you think they would ALL meet? 👇",
    "sphere_star": "Did you expect a hollow ball? 👇",
    "torus_knot": "Which knot was the coolest? 👇",
    "nbody": "Which color did you pick — did it survive? 👇",
    "dragonfold": "Did you guess a dragon? 👇",
    "fourier3d": "What did you think it was before the top view? 👇",
    "shrinksphere": "Did you recognize the music? Tell me in the comments 👇",
    "sunflower3d": "Did you know sunflowers do this? 👇",
    "hilbert3d": "Did you think one line could do it? 👇",
    "sides": "At how many sides did it look like a circle to you? 👇",
    "arms": "At how many arms did it turn into a ring for you? 👇",
    "spiral": "Guess the speed at the center before it ends 👇",
    "predator": "Guess the time before it ends 👇",
    "breakout": "Which brick do you think goes last? 👇",
    "quadsplit": "Did you guess the final number of boxes? 👇",
    "redring": "Guess the final ball count 👇",
    "sortwheel": "Which sorting algorithm should I do next? 👇",
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
    "race_lava": ["ball race", "marble race", "escape the lava", "pick a color", "maze race"],
    "race_flood": ["ball race", "marble race", "flood escape", "pick a color", "which ball wins"],
    "race_crush": ["ball race", "crusher", "escape race", "pick a color", "which ball wins"],
    "race_shrink": ["ball race", "shrink", "escape race", "pick a color", "which ball wins"],
    "hammer": ["drop hammer", "hammer crush", "ball splits", "how many balls", "guess the song"],
    "squeeze": ["crusher", "ball splits", "how many balls", "satisfying physics", "guess the song"],
    "lasers": ["lasers", "exponential growth", "doubling", "bouncing ball music", "who wins"],
    "royale": ["battle royale", "ball battle", "ball fight", "last one standing", "pick a ball", "game simulation"],
    "focus": ["ellipse", "math", "geometry", "focus of an ellipse", "fibonacci", "billiards"],
    "focus_stretch": ["ellipse", "math", "geometry", "focus of an ellipse", "billiards"],
    "focus_3d": ["ellipsoid", "ellipse", "math", "3d geometry", "fibonacci"],
    "golden": ["golden ratio", "math", "irrational numbers", "geometry", "pattern"],
    "pendulum": ["pendulum wave", "physics", "pendulum", "satisfying physics", "waves"],
    "rosette": ["orbit", "rosette orbit", "space", "physics", "mercury", "general relativity"],
    "fourier": ["fourier series", "epicycles", "math animation", "3blue1brown style", "drawing with circles"],
    "dpendulum": ["double pendulum", "chaos theory", "butterfly effect", "physics simulation"],
    "lorenz": ["lorenz attractor", "butterfly effect", "chaos theory", "math animation"],
    "chaosgame": ["chaos game", "sierpinski triangle", "fractal", "math animation", "randomness"],
    "timestable": ["times table", "cardioid", "modular arithmetic", "math art", "math animation"],
    "primespiral": ["prime numbers", "prime spiral", "math animation", "3blue1brown style"],
    "threebody": ["three body problem", "gravity simulation", "chaos", "space", "pick a color"],
    "metronomes": ["metronome sync", "synchronization", "physics", "satisfying physics"],
    "galton": ["galton board", "bell curve", "normal distribution", "probability", "ball drop"],
    "chladni": ["chladni patterns", "cymatics", "sand and sound", "physics", "satisfying"],
    "shrink_duo": ["ball shrinks", "growing wall", "pick a color", "ball battle", "guess the song"],
    "shrink_shape": ["ball shrinks", "growing wall", "bouncing ball music", "guess the song", "satisfying physics"],
    "dish_3d": ["satellite dish", "parabola", "focus", "3d simulation", "fibonacci"],
    "sphere_star": ["golden angle", "golden ratio", "sphere", "3d simulation", "math art"],
    "torus_knot": ["torus knot", "trefoil knot", "golden ratio", "3d math", "donut"],
    "nbody": ["n body problem", "three body problem", "gravity simulation", "pick a color", "space"],
    "dragonfold": ["dragon curve", "paper folding", "fractal", "math animation", "satisfying"],
    "fourier3d": ["fourier series", "epicycles", "3d math", "math animation", "drawing with circles"],
    "shrinksphere": ["ball shrinks", "growing wall", "3d simulation", "bouncing ball music", "guess the song"],
    "sunflower3d": ["golden angle", "golden ratio", "sunflower", "phyllotaxis", "math in nature"],
    "hilbert3d": ["hilbert curve", "space filling curve", "fractal", "3d math", "math animation"],
    "sides": ["polygon", "every bounce adds a side", "triangle to circle", "geometry", "guess the song"],
    "arms": ["polygon", "polygon names", "every bounce", "satisfying geometry", "guess the song"],
    "spiral": ["spiral", "gets faster", "speed", "satisfying spiral", "guess the song"],
    "predator": ["predator prey", "simulation", "swarm", "infection simulation", "emergent behavior"],
    "breakout": ["brick breaker", "breakout", "bricks", "speeds up", "guess the song"],
    "quadsplit": ["quadtree", "fractal", "splits into 4", "satisfying boxes", "guess the song"],
    "redring": ["ball multiplies", "red ring", "spawn balls", "ball explosion", "satisfying"],
    "sortwheel": ["sorting algorithm", "sound of sorting", "color wheel", "rainbow", "algorithm visualization"],
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
    "race_lava": "#shorts #ballrace #marblerace #simulation #pickacolor",
    "race_flood": "#shorts #ballrace #marblerace #simulation #pickacolor",
    "race_crush": "#shorts #ballrace #marblerace #simulation #pickacolor",
    "race_shrink": "#shorts #ballrace #marblerace #simulation #pickacolor",
    "hammer": "#shorts #satisfying #hammer #simulation #oddlysatisfying",
    "squeeze": "#shorts #satisfying #crusher #simulation #oddlysatisfying",
    "lasers": "#shorts #satisfying #lasers #simulation #oddlysatisfying",
    "royale": "#battleroyale #ballbattle #simulation #marblerace #gaming",
    "focus": "#shorts #maths #geometry #physics #satisfying",
    "focus_stretch": "#shorts #maths #geometry #physics #satisfying",
    "focus_3d": "#shorts #maths #geometry #3d #satisfying",
    "golden": "#shorts #maths #goldenratio #geometry #satisfying",
    "pendulum": "#shorts #physics #pendulum #satisfying #science",
    "rosette": "#shorts #physics #space #orbit #science",
    "fourier": "#shorts #maths #fourier #animation #satisfying",
    "dpendulum": "#shorts #physics #chaos #pendulum #satisfying",
    "lorenz": "#shorts #maths #chaos #butterflyeffect #satisfying",
    "chaosgame": "#shorts #maths #fractal #randomness #satisfying",
    "timestable": "#shorts #maths #mathart #geometry #satisfying",
    "primespiral": "#shorts #maths #primenumbers #animation #satisfying",
    "threebody": "#shorts #physics #space #threebodyproblem #pickacolor",
    "metronomes": "#shorts #physics #satisfying #sync #science",
    "galton": "#shorts #maths #probability #galtonboard #satisfying",
    "chladni": "#shorts #physics #cymatics #sound #satisfying",
    "shrink_duo": "#shorts #satisfying #bouncingball #pickacolor #oddlysatisfying",
    "shrink_shape": "#shorts #satisfying #bouncingball #simulation #oddlysatisfying",
    "dish_3d": "#shorts #maths #physics #3d #satisfying",
    "sphere_star": "#shorts #maths #goldenratio #3d #satisfying",
    "torus_knot": "#shorts #maths #knots #3d #satisfying",
    "nbody": "#shorts #physics #space #gravity #pickacolor",
    "dragonfold": "#shorts #maths #fractal #paperfolding #satisfying",
    "fourier3d": "#shorts #maths #fourier #3d #satisfying",
    "shrinksphere": "#shorts #satisfying #bouncingball #3d #oddlysatisfying",
    "sunflower3d": "#shorts #maths #goldenratio #nature #satisfying",
    "hilbert3d": "#shorts #maths #fractal #3d #satisfying",
    "sides": "#shorts #satisfying #geometry #bouncingball #oddlysatisfying",
    "arms": "#shorts #satisfying #geometry #polygon #oddlysatisfying",
    "spiral": "#shorts #satisfying #spiral #bouncingball #oddlysatisfying",
    "predator": "#shorts #simulation #predator #swarm #satisfying",
    "breakout": "#shorts #satisfying #brickbreaker #bouncingball #oddlysatisfying",
    "quadsplit": "#shorts #satisfying #fractal #bouncingball #oddlysatisfying",
    "redring": "#shorts #satisfying #bouncingball #simulation #oddlysatisfying",
    "sortwheel": "#shorts #sortingalgorithm #satisfying #rainbow #coding",
}


def build_compilation(facts: dict, seed: int) -> dict:
    """long landscape compilation: numbered chapters in the description, no #shorts in the title"""
    from .compilation import TITLES as CT
    rng = random.Random(seed * 53 + 11)
    n = facts.get("n_balls", 14)
    ch = facts.get("chapters", [])
    mins = max(1, round((ch[-1][0] + 30) / 60)) if ch else 8
    title = rng.choice(CT).format(n=n, m=mins)[:100]
    lines = [f"{n} of the most satisfying physics and math simulations from {CHANNEL_NAME}, back to back.",
             "Which one was your favourite? Tell me the number in the comments 👇", "", "⏱️ Chapters"]
    for t, name in ch:
        s = int(round(t))
        lines.append(f"{s // 60}:{s % 60:02d} {name}")
    lines += ["", "New simulations every day — subscribe so you don't miss them!", "",
              "🎵 Music & sound effects: original or public-domain melodies, synthesized in code.",
              "Every simulation is 100% computer-generated with code. No real footage.", "",
              "#satisfying #simulation #physics #maths #oddlysatisfying"]
    tags = ["satisfying simulations", "satisfying video", "physics simulation", "math animation",
            "oddly satisfying", "relaxing video", "compilation", "satisfying compilation", "bouncing ball",
            "simulation compilation"]
    return dict(title=title, title_style="compilation", description="\n".join(lines), tags=tags, categoryId="24")


CHANNEL_NAME = "Orbit Escape"


def build(facts: dict, seed: int) -> dict:
    rng = random.Random(seed * 31 + 7)
    tpl_name = facts.get("template", "escape")
    if tpl_name == "compilation":
        return build_compilation(facts, seed)
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
        FIRST_LINE[tpl_name].format(vs=vs, r=facts.get("n_rings", ""), n=facts.get("n_balls", ""),
                                    N=f"{facts.get('n_final', 0):,}", A=facts.get("angle_label", "")),
        ASK[tpl_name],
        "",
        ("A new Ball Battle Royale every day — subscribe and pick your ball before the fight starts!"
         if tpl_name == "royale" else "New simulations every day — subscribe so you don't miss tomorrow's!"),
        "",
        (f"🎵 Melody: {facts['melody']} (public domain), synthesized for this video." if facts.get("melody") and tpl_name != "royale"
         else "🎵 Music & sound effects: original, synthesized in code for this video."),
        "Simulation is 100% computer-generated with code. No real footage.",
        "",
        HASHTAGS[tpl_name],
    ])
    tags = (TAGS[1:] if tpl_name == "royale" else TAGS) + EXTRA_TAGS[tpl_name] + [f"{c.lower()} ball" for c in cols][:4] + [w.lower() for w in labels]
    return dict(title=title, title_style=f"{tpl_name}:{style}", description=desc, tags=tags,
                categoryId="20" if tpl_name == "royale" else "24")
