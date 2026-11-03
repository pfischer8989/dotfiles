#!/usr/bin/env python3
"""Writes three chord options for a pass as empire.notes/v1 files, standing in
for an agent while testing the panel. Pass 1 holds each chord for a bar; later
passes play it in eighth-note stabs, so a new pass is easy to spot.

    test_options.py <stage dir> <pass>
"""

import json
import os
import sys

BAR = 3840
EIGHTH = 480
CHORDS = {
    "Am": [57, 60, 64], "F": [53, 57, 60], "C": [55, 60, 64], "G": [55, 59, 62],
    "Dm": [57, 62, 65], "Em": [55, 59, 64], "E": [56, 59, 64],
}
OPTIONS = [
    ("A", "Am F C G", ["Am", "F", "C", "G"]),
    ("B", "Am Dm Em Am", ["Am", "Dm", "Em", "Am"]),
    ("C", "Am G F E", ["Am", "G", "F", "E"]),
]


def notes(chords, pass_number):
    out = []
    for bar, name in enumerate(chords):
        start = bar * BAR
        if pass_number == 1:
            out += [[start, p, 0, BAR - 40, 96] for p in CHORDS[name]]
        else:
            for step in range(8):
                velocity = 112 if step % 4 == 0 else 84
                out += [[start + step * EIGHTH, p, 0, EIGHTH - 60, velocity] for p in CHORDS[name]]
    return sorted(out)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    pass_number = int(sys.argv[2])
    folder = os.path.join(sys.argv[1], f"pass-{pass_number}")
    os.makedirs(folder, exist_ok=True)
    for option, label, chords in OPTIONS:
        doc = {"schema": "empire.notes/v1", "part": "chords", "ppq": 960,
               "label": label, "notes": notes(chords, pass_number)}
        with open(os.path.join(folder, f"chords-{option}.notes.json"), "w") as f:
            json.dump(doc, f)
    print(f"wrote {len(OPTIONS)} options to {folder}")


if __name__ == "__main__":
    main()
