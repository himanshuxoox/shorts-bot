"""Names of the 3D ideas and which long video uses them (no Blender needed to read this)."""

IDEAS = {
    # video 1 — heavier, softer, stronger
    "wrecking": dict(title="Wrecking ball vs brick wall", n=3),
    "gravity": dict(title="The same crash on 3 planets", n=3),
    "bounce": dict(title="120 balls down the stairs", n=3),
    "spikes": dict(title="Jelly vs a bed of nails", n=3),
    "spin": dict(title="Tower on a turntable", n=3),
    "plinko": dict(title="3D plinko", n=3),
    "bridge": dict(title="Heavy ball vs plank bridge", n=3),
    "wind": dict(title="Wind vs block pyramid", n=3),
    # video 2 — 1 vs 1,000
    "towers": dict(title="Same ball, more blocks", n=3),
    "funnel": dict(title="Balls through a funnel", n=3),
    "attract": dict(title="Zero gravity: 600 balls", n=3),
    "blast": dict(title="Blast under 140 blocks", n=3),
    "ballpit": dict(title="Ball pit splash", n=3),
    "friction": dict(title="Towers on a slope", n=3),
    "fabric": dict(title="Fabric on a statue", n=3),
    "seesaw": dict(title="Balls vs seesaw", n=3),
}

# each long video: its ideas in order, the idea shown on the thumbnail, title ideas
VIDEOS = {
    "heavy": dict(ideas=["wrecking", "spikes", "gravity", "bounce", "bridge", "spin", "plinko", "wind"],
                  thumb="wrecking",
                  titles=["1 kg vs 1,000 kg 😳 Satisfying 3D Physics Simulations",
                          "Heavier, Softer, Stronger 😳 Satisfying 3D Physics",
                          "What Changes EVERYTHING? 🤯 Satisfying 3D Physics Simulations"]),
    "count": dict(ideas=["towers", "ballpit", "funnel", "attract", "blast", "seesaw", "fabric", "friction"],
                  thumb="towers",
                  titles=["10 vs 1,000 🤯 Satisfying 3D Physics Simulations",
                          "1 vs 1,000: Which One Wins? 😳 Satisfying 3D Physics",
                          "More and More… 🤯 Satisfying 3D Physics Simulations"]),
}


def jobs(videos):
    """[(idea, variant)] to render for these long videos"""
    out = []
    for v in videos:
        for idea in VIDEOS[v]["ideas"]:
            out += [(idea, k) for k in range(IDEAS[idea]["n"])]
    return out


if __name__ == "__main__":                       # used by the workflow: print the render matrix as JSON
    import json
    import sys
    vids = [w for w in " ".join(sys.argv[1:]).replace(",", " ").split() if w in VIDEOS] or list(VIDEOS)
    print(json.dumps({"include": [{"idea": i, "v": v} for i, v in jobs(vids)]}))
