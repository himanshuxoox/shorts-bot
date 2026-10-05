"""Public-domain melodies (all composed before 1910). One note per bounce.

Only the bare tune is used, written out note by note here and synthesized by our own code,
so there is no recording and no modern arrangement involved. Do NOT add songs that are still
under copyright (pop, film, Bollywood, game music): even a re-played melody can be claimed.
"""

MELODIES = {
    # Beethoven — Symphony No. 9, "Ode to Joy" (1824)
    "Ode to Joy": (
        "E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 E5 D5 D5 "
        "E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 D5 C5 C5 "
        "D5 D5 E5 C5 D5 E5 F5 E5 C5 D5 E5 F5 E5 D5 C5 D5 G4 "
        "E5 E5 F5 G5 G5 F5 E5 D5 C5 C5 D5 E5 D5 C5 C5").split(),
    # Beethoven — Für Elise (c. 1810)
    "Fur Elise": (
        "E5 D#5 E5 D#5 E5 B4 D5 C5 A4 C4 E4 A4 B4 E4 G#4 B4 C5 E4 "
        "E5 D#5 E5 D#5 E5 B4 D5 C5 A4 C4 E4 A4 B4 E4 C5 B4 A4").split(),
    # Grieg — In the Hall of the Mountain King (1875)
    "Mountain King": (
        "B4 C#5 D5 E5 F#5 D5 F#5 F5 C#5 F5 E5 C5 E5 "
        "B4 C#5 D5 E5 F#5 D5 F#5 B5 A5 F#5 D5 F#5 A5").split(),
    # Traditional — Twinkle Twinkle Little Star (18th c.)
    "Twinkle Twinkle Little Star": (
        "C5 C5 G5 G5 A5 A5 G5 F5 F5 E5 E5 D5 D5 C5 "
        "G5 G5 F5 F5 E5 E5 D5 G5 G5 F5 F5 E5 E5 D5").split(),
    # Pachelbel — Canon in D (c. 1680)
    "Canon in D": (
        "F#5 E5 D5 C#5 B4 A4 B4 C#5 D5 C#5 B4 A4 G4 F#4 G4 E4 "
        "D5 F#5 A5 G5 F#5 D5 F#5 E5 D5 B4 D5 A5 G5 B5 A5 G5").split(),
    # Mozart — Eine kleine Nachtmusik (1787)
    "Eine kleine": (
        "G5 D5 G5 D5 G5 D5 G5 B5 D6 C6 A5 C6 A5 C6 A5 F#5 A5 D5").split(),
    # Hill sisters — "Good Morning to All" (1893), the Happy Birthday tune (public domain)
    "Happy Birthday": (
        "G4 G4 A4 G4 C5 B4 G4 G4 A4 G4 D5 C5 "
        "G4 G4 G5 E5 C5 B4 A4 F5 F5 E5 C5 D5 C5").split(),
    # James Lord Pierpont — Jingle Bells (1857)
    "Jingle Bells": (
        "E5 E5 E5 E5 E5 E5 E5 G5 C5 D5 E5 "
        "F5 F5 F5 F5 F5 E5 E5 E5 E5 D5 D5 E5 D5 G5 "
        "E5 E5 E5 E5 E5 E5 E5 G5 C5 D5 E5 "
        "F5 F5 F5 F5 F5 E5 E5 E5 G5 G5 F5 D5 C5").split(),
    # Offenbach — Infernal Galop / "Can-Can" (1858)
    "Can-Can": (
        "C5 D5 F5 E5 D5 G5 G5 G5 A5 E5 F5 D5 D5 D5 F5 E5 D5 "
        "C5 C6 B5 A5 G5 F5 E5 D5 "
        "C5 D5 F5 E5 D5 G5 G5 G5 A5 E5 F5 D5 D5 D5 F5 E5 D5 C5 G5 D5 E5 C5").split(),
    # Scott Joplin — The Entertainer (1902)
    "The Entertainer": (
        "D5 D#5 E5 C6 E5 C6 E5 C6 C6 D6 D#6 E6 C6 D6 E6 B5 D6 C6 "
        "D5 D#5 E5 C6 E5 C6 E5 C6 A5 G5 F#5 A5 C6 E6 D6 C6 A5 D6").split(),
    # Mozart — Rondo alla Turca / "Turkish March" (1783)
    "Turkish March": (
        "B4 A4 G#4 A4 C5 D5 C5 B4 C5 E5 F5 E5 D#5 E5 "
        "B5 A5 G#5 A5 B5 A5 G#5 A5 C6 A5 C6 B5 A5 G5 A5 B5 A5 G5 A5 B5 A5 G5 F#5 E5").split(),
    # Rossini — William Tell Overture, finale (1829)
    "William Tell": (
        "G4 G4 G4 G4 G4 G4 G4 G4 C5 D5 E5 G4 G4 G4 G4 G4 C5 E5 D5 B4 "
        "G4 G4 G4 G4 G4 G4 G4 G4 C5 D5 E5 C5 E5 G5 G5 F5 E5 D5 C5").split(),
    # Traditional — When the Saints Go Marching In
    "When the Saints": (
        "C5 E5 F5 G5 C5 E5 F5 G5 C5 E5 F5 G5 E5 C5 E5 D5 "
        "E5 E5 D5 C5 C5 E5 G5 G5 F5 E5 F5 G5 E5 C5 D5 C5").split(),
    # Traditional — Frère Jacques
    "Frere Jacques": (
        "C5 D5 E5 C5 C5 D5 E5 C5 E5 F5 G5 E5 F5 G5 "
        "G5 A5 G5 F5 E5 C5 G5 A5 G5 F5 E5 C5 C5 G4 C5 C5 G4 C5").split(),
    # Brahms — Wiegenlied / "Brahms' Lullaby" (1868)
    "Brahms Lullaby": (
        "E5 E5 G5 E5 E5 G5 E5 G5 C6 B5 A5 A5 G5 "
        "D5 E5 F5 D5 D5 E5 F5 D5 F5 B5 A5 G5 B5 C6").split(),
    # Traditional — Old MacDonald Had a Farm
    "Old MacDonald": (
        "G5 G5 G5 D5 E5 E5 D5 B5 B5 A5 A5 G5 "
        "D5 G5 G5 G5 D5 E5 E5 D5 B5 B5 A5 A5 G5").split(),
}

# The tunes almost everyone recognises within a few notes — used by the
# "Did you recognize the music?" formats.
FAMOUS = ["Happy Birthday", "Jingle Bells", "Fur Elise", "Can-Can", "The Entertainer",
          "Turkish March", "William Tell", "Mountain King", "Ode to Joy",
          "Twinkle Twinkle Little Star", "When the Saints", "Frere Jacques", "Old MacDonald"]


def track(times, melody, min_gap=0.0):
    """Assign the melody's notes, in order, to hit times. Hits closer than min_gap to the
    previous kept note are dropped *before* a note is used, so the tune stays intact."""
    out, last, i = [], -9.0, 0
    for t in sorted(times):
        if t - last < min_gap:
            continue
        out.append((t, melody[i % len(melody)]))
        last, i = t, i + 1
    return out
