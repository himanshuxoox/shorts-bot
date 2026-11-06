# ManimGL scenes (3Blue1Brown's manim)

These formats are drawn with [ManimGL](https://github.com/3b1b/manim) instead of cairo.
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
| `nbody` (also `threebody`) | `nbody.py` NBody | 6 / 8 / 9 suns, pick a color — thrown out = OUT (replaces the old 3-body scene, which named the wrong star) |
| `dragonfold` | `dragon_fold.py` DragonFold | Fold a strip 10 times, open every fold to 90° → dragon curve (3D ribbon) |
| `fourier3d` | `fourier_3d.py` Fourier3D | Spinning circles draw a 3D knot… from the TOP it's a picture |
| `shrinksphere` | `shrink_sphere.py` ShrinkSphere | Every bounce shrinks the ball and grows the wall — inside a sphere |
| `sunflower3d` | `sunflower_3d.py` Sunflower3D | Which angle makes a sunflower? 90° → 137° → 137.5°, then a 3D pine cone |
| `hilbert3d` | `hilbert_3d.py` Hilbert3D | Can ONE line fill a whole cube? 8 → 64 → 512 → 4,096 corners |
| `metronomes` | `metronomes.py` Metronomes | 24 metronomes, nobody touches them → perfect sync |
| `galton` | `galton.py` Galton | Where will 1,500 balls land? → bell curve |
| `chladni` | `chladni.py` Chladni | Sand on a metal plate, now add sound → patterns |

Try one locally (needs `pip install -r requirements-mgl.txt`, plus `xvfb` on a server without a screen):

```bash
FORMATS=galton python -m shorts.batch --count 1 --date test --workers 1
```

Every scene reads its seed from `MGL_SEED`, so the same seed always gives the same video and a new
seed gives a new one (colours, shapes, winners, pattern sequences change).
