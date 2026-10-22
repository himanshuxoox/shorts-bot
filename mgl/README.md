# ManimGL scenes (3Blue1Brown's manim)

These 10 formats are drawn with [ManimGL](https://github.com/3b1b/manim) instead of cairo.
`shorts/manim_fmt.py` runs a scene through manim (headless, under `xvfb-run` on GitHub Actions),
then adds the sound (`shorts/mgl_audio.py`) and plugs it into the normal batch, pacer and upload.

| key | scene | hook |
|---|---|---|
| `fourier` | `fourier.py` Fourier | Only circles. What will they draw? (2 → 16 → 100+ circles: heart, π, Σ, star …) |
| `dpendulum` | `chaos.py` Chaos | 60 pendulums, 0.0001° apart → CHAOS |
| `lorenz` | `lorenz.py` Lorenz | 4,000 dots, almost the same start → butterfly |
| `chaosgame` | `chaos_game.py` ChaosGame | Pick a random corner, jump halfway → Sierpinski / pentagon / square / hexagon fractal |
| `timestable` | `times_table.py` TimesTable | What does × 2 draw? petals, guess ×10, ×119 graph paper, ×239 flat lines |
| `primespiral` | `primes.py` Primes | Every number n at angle n → 6 spirals, 44 spirals, 280 rays of primes |
| `threebody` | `threebody.py` ThreeBody | 3 suns, one gets thrown out — pick a color |
| `metronomes` | `metronomes.py` Metronomes | 24 metronomes, nobody touches them → perfect sync |
| `galton` | `galton.py` Galton | Where will 1,500 balls land? → bell curve |
| `chladni` | `chladni.py` Chladni | Sand on a metal plate, now add sound → patterns |

Try one locally (needs `pip install -r requirements-mgl.txt`, plus `xvfb` on a server without a screen):

```bash
FORMATS=galton python -m shorts.batch --count 1 --date test --workers 1
```

Every scene reads its seed from `MGL_SEED`, so the same seed always gives the same video and a new
seed gives a new one (colours, shapes, winners, pattern sequences change).
