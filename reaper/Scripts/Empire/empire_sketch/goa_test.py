#!/usr/bin/env python3
"""Writes a goa psytrance sketch to try the lanes workflow on: 138 BPM, C# minor,
dark Blade Runner mood. Each lane follows its own chord path, and every pitched
note stays in the key. Drops are the fullest part. These patterns are hand-written
rules standing in for an agent.

    goa_test.py [folder]   (default ~/.empire/reaper/sketches/goa-test)
"""

import json
import os
import random
import sys

BEAT, BAR, S16 = 960, 3840, 240
LOOP_BARS = 8
SCALE = [1, 3, 4, 6, 8, 9, 11]  # C# natural minor
PATHS = {"A": [0, 0, 5, 5, 3, 3, 4, 4], "B": [0, 0, 2, 2, 6, 6, 5, 4], "C": [0, 5, 0, 6, 0, 3, 6, 4]}
KICK, RIM, SNARE, CLAP, HAT, OPEN, TOM_L, TOM_M, TOM_H, RIDE = 36, 37, 38, 39, 42, 46, 45, 47, 48, 51
DRUM_NOTES = {KICK, RIM, SNARE, CLAP, HAT, OPEN, TOM_L, TOM_M, TOM_H, RIDE}

# name, form bars, energy, parts playing
SECTIONS = [
    ("Intro", 16, 1, ["Drums", "Arp", "Pad"]),
    ("Build", 16, 2, ["Drums", "Bass", "Arp", "Pad"]),
    ("Drop", 32, 3, ["Drums", "Bass", "Acid", "Arp", "Pad"]),
    ("Break", 16, 0, ["Acid", "Arp", "Pad"]),
    ("Drop 2", 32, 4, ["Drums", "Bass", "Acid", "Arp", "Pad"]),
    ("Outro", 16, 1, ["Drums", "Bass", "Pad"]),
]
PARTS = [("Drums", "Atlas Kit"), ("Bass", "Synth - Hive"), ("Acid", "Synth - Zebra 3"),
         ("Arp", "Synth - Diva"), ("Pad", "Pad - Diva")]


def pitch(degree, octave):
    return 12 * (octave + 1) + SCALE[degree % 7] + 12 * (degree // 7)


def note(out, start, p, length, velocity):
    out.append([start, p, 0, length, max(1, min(127, velocity))])


def chord_runs(path):
    """Consecutive bars on the same chord, as (first bar, bars, degree)."""
    runs = []
    for bar, degree in enumerate(path):
        if runs and runs[-1][2] == degree:
            runs[-1][1] += 1
        else:
            runs.append([bar, 1, degree])
    return runs


def drums(energy, option):
    out = []
    for bar in range(LOOP_BARS):
        last = bar == LOOP_BARS - 1
        for beat in range(4):
            at = bar * BAR + beat * BEAT
            note(out, at, KICK, 200, 124)
            if option == "A":
                note(out, at + 480, OPEN, 200, 92)
                if energy >= 2 and beat % 2:
                    note(out, at, CLAP, 200, 105)
                if energy >= 3:
                    for step in (1, 3):
                        note(out, at + step * S16, HAT, 100, 70)
            elif option == "B":
                steps = range(4) if energy >= 2 else (0, 2)
                for step in steps:
                    note(out, at + step * S16, HAT, 100, 96 if step == 2 else 62)
                if energy >= 2 and beat == 3:
                    note(out, at, CLAP, 200, 100)
                if energy >= 3:
                    note(out, at + 480, RIDE, 240, 70)
                    if (bar * 4 + beat) % 3 == 0:
                        note(out, at + 3 * S16, RIM, 100, 88)
            else:
                note(out, at + 480, HAT, 120, 88)
                if energy >= 2:
                    for step, tom in ((1, TOM_H), (3, TOM_M)) if beat % 2 else ((3, TOM_L),):
                        note(out, at + step * S16, tom, 180, 82)
                if energy >= 3 and beat % 2:
                    note(out, at, CLAP, 200, 98)
            if energy >= 4 and option != "A":
                note(out, at + 3 * S16, OPEN, 120, 70)
        if last and energy >= 2:
            # a snare roll over the last bar: longer before a section changes
            first = 0 if energy == 2 else 8
            for step in range(first, 16):
                note(out, bar * BAR + step * S16, SNARE, 110, 50 + (step - first) * (70 // max(1, 16 - first)))
    return out


def bass(energy, option):
    out = []
    path = PATHS[option] if energy >= 2 else [0] * LOOP_BARS
    for bar, degree in enumerate(path):
        low = degree >= 5  # keep the roots near the bottom of the part
        root = pitch(degree, 1 if low else 2)
        fifth = pitch(degree + 4, 1 if low else 2)
        for beat in range(4):
            at = bar * BAR + beat * BEAT
            if energy == 1:
                steps = {1: root, 3: root}
            elif option == "A":
                steps = {1: root, 2: root, 3: root}
            elif option == "B":
                steps = {1: root, 3: fifth if beat == 3 else root}
            else:
                steps = {1: root, 2: root + 12, 3: root}
            if energy >= 4 and beat == 3 and bar % 2:
                steps = {1: root + 12, 2: fifth, 3: root + 12}
            for step, p in steps.items():
                note(out, at + step * S16, p, 190, 112 if step == 1 else 96)
    return out


def pad(energy, option):
    out = []
    velocity = {0: 92, 1: 66, 2: 78, 3: 88, 4: 94}[energy]
    for first, bars, degree in chord_runs(PATHS[option]):
        start, length = first * BAR, bars * BAR - 30
        if energy == 1:
            voices = [(degree, 3), (degree + 4, 3)]
        elif option == "A":
            voices = [(degree, 3), (degree + 2, 3), (degree + 4, 3)]
        elif option == "B":
            voices = [(degree, 3), (degree + 4, 3), (degree + 8, 3)]
        else:
            voices = [(degree, 3), (degree + 2, 3), (degree + 4, 3)]
            for bar in range(bars):
                top = degree + (7 if bar % 2 == 0 else 8)
                note(out, start + bar * BAR, pitch(top, 3), BAR - 30, velocity - 8)
        if energy == 0:
            voices.append((degree, 2))
        if energy >= 3:
            voices.append((degree, 4))
        if energy == 4:
            voices.append((degree + 2, 4))
        for d, octave in voices:
            note(out, start, pitch(d, octave), length, velocity)
    return out


def arp(energy, option):
    out = []
    path = PATHS[option]
    for bar, degree in enumerate(path):
        tones = [pitch(degree + d, 4) for d in (0, 2, 4)]
        tones += [t + 12 for t in tones] if energy >= 3 else [tones[0] + 12]
        if option == "B":
            tones = tones + tones[-2:0:-1]
        if energy == 0:
            steps = [0, 3, 6, 9, 12] if bar % 2 == 0 else [0, 6]  # dotted eighths, sparse
        elif energy == 1:
            steps = range(0, 16, 2)
        elif energy == 2 and bar < 4:
            steps = range(0, 16, 2)
        elif option == "C":
            steps = [s for s in range(16) if s % 8 in (0, 3, 6)]
        else:
            steps = range(16)
        for i, step in enumerate(steps):
            p = tones[i % len(tones)]
            if energy == 4 and step % 8 == 7:
                p += 12
            note(out, bar * BAR + step * S16, p, 170, 104 if step % 4 == 0 else 78)
    return out


VANGELIS = {
    "A": [(0, 8, 0), (8, 4, 2), (12, 4, 1), (16, 12, 0), (28, 4, 6)],
    "B": [(0, 6, 4), (6, 2, 5), (8, 8, 4), (16, 4, 2), (20, 4, 1), (24, 8, 0)],
    "C": [(0, 4, 7), (4, 4, 6), (8, 8, 4), (16, 8, 5), (24, 4, 4), (28, 4, 2)],
}


def acid(section, energy, option):
    out = []
    if energy == 0:
        # a slow, long-note line for the break; (start beat, beats, degree)
        for start, beats, degree in VANGELIS[option]:
            note(out, start * BEAT, pitch(degree, 5), beats * BEAT - 40, 90)
        return out
    rng = random.Random(f"{section}/{option}")
    octave = {"A": 2, "B": 4, "C": 3}[option]
    degrees = {"A": [0, 0, 0, 2, 6, 3], "B": [0, 2, 4, 6, 7, 4], "C": [7, 6, 5, 4, 2, 0]}[option]
    density = 0.6 if energy >= 4 else 0.45
    motif = []
    for step in range(32):
        if step % 4 == 0 and option == "A":
            continue  # leave the kick alone
        if rng.random() < density:
            choice = degrees[(step // 3) % len(degrees)] if option == "C" else rng.choice(degrees)
            jump = 7 if energy >= 4 and rng.random() < 0.15 else 0
            slide = rng.random() < 0.25
            motif.append((step, pitch(choice + jump, octave), 260 if slide else 150))
    for repeat in range(4):
        for step, p, length in motif:
            if repeat == 3 and step >= 16 and step % 3 == 0:
                continue  # thin the end of the loop so it turns around
            velocity = 112 if step % 4 == 2 else 92
            note(out, repeat * 2 * BAR + step * S16, p, length, velocity)
    return out


def build(section, energy, part, option):
    if part == "Drums":
        return drums(energy, option)
    if part == "Bass":
        return bass(energy, option)
    if part == "Pad":
        return pad(energy, option)
    if part == "Arp":
        return arp(energy, option)
    return acid(section, energy, option)


LABELS = {
    "Drums": {"A": "straight", "B": "rolling hats", "C": "tribal"},
    "Bass": {"A": "rolling", "B": "gallop", "C": "octaves"},
    "Acid": {"A": "low squelch", "B": "high calls", "C": "falling"},
    "Arp": {"A": "up", "B": "up and down", "C": "3-3-2"},
    "Pad": {"A": "held triads", "B": "open ninths", "C": "moving top"},
}


def check(part, notes):
    for start, p, _, length, _ in notes:
        assert 0 <= start < LOOP_BARS * BAR, (part, start)
        assert length > 0 and 0 <= p <= 127, (part, p)
        if part == "Drums":
            assert p in DRUM_NOTES, (part, p)
        else:
            assert p % 12 in SCALE, (part, p)


def main():
    default = os.path.expanduser("~/.empire/reaper/sketches/goa-test")
    folder = sys.argv[1] if len(sys.argv) > 1 else default
    os.makedirs(folder, exist_ok=True)
    clips = []
    for section, _, energy, parts in SECTIONS:
        for part in parts:
            for option in "ABC":
                notes = sorted(build(section, energy, part, option))
                check(part, notes)
                clips.append({"section": section, "part": part, "option": option,
                              "label": LABELS[part][option], "notes": notes})
    doc = {
        "schema": "empire.sketch/v1",
        "setup": {"schema": "empire.setup/v1", "tempo": 138, "time_signature": [4, 4], "key": "C#", "scale": "minor",
                  "sections": [{"name": s[0], "bars": s[1]} for s in SECTIONS],
                  "tracks": [p[1] for p in PARTS]},
        "genre": "goa psytrance", "mood": "dark, Blade Runner",
        "ppq": 960, "loop_bars": LOOP_BARS, "options": 3,
        "parts": [{"name": name, "template": template} for name, template in PARTS],
        "clips": clips,
    }
    path = os.path.join(folder, "sketch.json")
    with open(path, "w") as f:
        json.dump(doc, f)
    with open(os.path.join(os.path.dirname(folder), "latest"), "w") as f:
        f.write(path + "\n")
    print(f"wrote {len(clips)} clips to {path}")


if __name__ == "__main__":
    main()
