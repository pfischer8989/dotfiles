#!/usr/bin/env python3
"""Writes a setup proposal for a pass as an empire.setup/v1 file, standing in for
an agent while testing the panel. Pass 1 is A minor in 4/4; later passes differ
in everything, so a new pass is easy to spot.

    test_setup.py <stage dir> <pass>
"""

import json
import os
import sys

FIRST = {
    "tempo": 142, "time_signature": [4, 4], "key": "A", "scale": "minor",
    "sections": [{"name": "Intro", "bars": 16}, {"name": "Build", "bars": 16}, {"name": "Drop", "bars": 32},
                 {"name": "Break", "bars": 16}, {"name": "Drop 2", "bars": 32}, {"name": "Outro", "bars": 16}],
    "tracks": ["Atlas Kit", "Synth - Zebra 3", "Pad - Diva", "Guitar - NAM"],
}
LATER = {
    "tempo": 96, "time_signature": [6, 8], "key": "F#", "scale": "phrygian",
    "sections": [{"name": "Verse", "bars": 8}, {"name": "Chorus", "bars": 8}, {"name": "End Section", "bars": 4}],
    "tracks": ["Superior Drummer Kit", "Ambient Guitar - NAM"],
}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    pass_number = int(sys.argv[2])
    folder = os.path.join(sys.argv[1], f"pass-{pass_number}")
    os.makedirs(folder, exist_ok=True)
    doc = {"schema": "empire.setup/v1", **(FIRST if pass_number == 1 else LATER)}
    with open(os.path.join(folder, "setup.json"), "w") as f:
        json.dump(doc, f, indent=2)
    print(f"wrote setup to {folder}")


if __name__ == "__main__":
    main()
