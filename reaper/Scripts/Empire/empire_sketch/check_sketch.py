#!/usr/bin/env python3
"""Checks a sketch file before anyone waits on it, and can install it where
Empire Build Sketch looks. Exits 1 and lists every problem if it isn't usable.

    check_sketch.py <sketch.json>
    check_sketch.py <sketch.json> --install <song>   (also copies it into
        ~/.empire/reaper/sketches/<song>/ and makes it the latest; a sketch
        already there is kept under a dated name)
"""

import json
import os
import re
import shutil
import sys
import time

from read_master import ROOTS, SCALES

DRUM_NOTES = {35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 69, 70}
KICKS = {35, 36}
MIN_UNIQUE_CLIPS = 0.75
RING_WARNING = 0.5
SKETCHES = "~/.empire/reaper/sketches"


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def problems(doc):
    out = []
    if not isinstance(doc, dict) or doc.get("schema") != "empire.sketch/v1":
        return ["not an empire.sketch/v1 file"]
    setup = doc.get("setup")
    if not isinstance(setup, dict) or setup.get("schema") != "empire.setup/v1":
        return ["setup isn't an empire.setup/v1 block"]
    if doc.get("ppq") != 960:
        out.append("ppq must be 960")
    tempo = setup.get("tempo")
    if not isinstance(tempo, (int, float)) or tempo <= 0:
        out.append("bad tempo")
    if setup.get("time_signature") != [4, 4]:
        out.append("only 4/4 is supported for now")
    if setup.get("key") not in ROOTS:
        out.append(f"unknown key {setup.get('key')}")
    if setup.get("scale") not in SCALES:
        out.append(f"unknown scale {setup.get('scale')}")
    loop_bars, options = doc.get("loop_bars"), doc.get("options")
    if not is_int(loop_bars) or loop_bars < 1:
        return out + ["bad loop_bars"]
    if not is_int(options) or not 1 <= options <= 26:
        return out + ["bad options"]
    letters = [chr(65 + i) for i in range(options)]

    sections = [s.get("name") for s in setup.get("sections", [])]
    if not sections or len(set(sections)) != len(sections) or not all(sections):
        out.append("sections need unique names")
    for s in setup.get("sections", []):
        if not is_int(s.get("bars")) or s["bars"] < 1:
            out.append(f"section {s.get('name')}: bad bars")
    parts = [p.get("name") for p in doc.get("parts", [])]
    if not parts or len(set(parts)) != len(parts) or not all(parts):
        out.append("parts need unique names")

    harmony = doc.get("harmony")
    if not isinstance(harmony, dict):
        out.append("no harmony: one list of chords per section, a chord per loop bar")
        harmony = {}
    for name in sections:
        chords = harmony.get(name)
        if not isinstance(chords, list) or len(chords) != loop_bars:
            out.append(f"harmony for {name}: needs {loop_bars} chords")

    in_key = None
    if setup.get("key") in ROOTS and setup.get("scale") in SCALES:
        in_key = {(ROOTS[setup["key"]] + i) % 12 for i in SCALES[setup["scale"]]}
    loop_ticks = loop_bars * 3840
    seen = {}
    for clip in doc.get("clips", []):
        where = f"{clip.get('section')}/{clip.get('part')}/{clip.get('option')}"
        if clip.get("section") not in sections:
            out.append(f"{where}: unknown section")
        if clip.get("part") not in parts:
            out.append(f"{where}: unknown part")
        if clip.get("option") not in letters:
            out.append(f"{where}: unknown option")
        if not clip.get("label"):
            out.append(f"{where}: no label")
        cell = (clip.get("section"), clip.get("part"))
        if clip.get("option") in seen.setdefault(cell, set()):
            out.append(f"{where}: appears twice")
        seen[cell].add(clip.get("option"))
        notes = clip.get("notes")
        if not notes:
            out.append(f"{where}: no notes")
            continue
        drums = clip.get("part") == "Drums"
        for n in notes:
            if not (isinstance(n, list) and len(n) == 5 and all(is_int(x) for x in n)):
                out.append(f"{where}: a note isn't [start, pitch, channel, length, velocity] in whole numbers")
                break
            start, pitch, channel, length, velocity = n
            if start < 0 or length <= 0 or start + length > loop_ticks:
                out.append(f"{where}: note at {start} doesn't fit the {loop_bars}-bar loop")
                break
            if not (0 <= pitch <= 127 and 0 <= channel <= 15 and 1 <= velocity <= 127):
                out.append(f"{where}: pitch, channel or velocity out of range at {start}")
                break
            if drums and pitch not in DRUM_NOTES:
                out.append(f"{where}: {pitch} isn't a General MIDI drum note")
                break
            if not drums and in_key is not None and pitch % 12 not in in_key and not clip.get("outside_key"):
                out.append(f"{where}: pitch {pitch} is outside the key (set outside_key on the clip if it's on purpose)")
                break
        same = {json.dumps(sorted(c["notes"])) for c in doc["clips"]
                if (c.get("section"), c.get("part")) == cell and c.get("notes")}
        if clip.get("option") == letters[-1] and len(same) < len(seen[cell]):
            out.append(f"{cell[0]}/{cell[1]}: two options are identical")
    clips = [c for c in doc.get("clips", []) if c.get("notes")]
    unique = len({json.dumps(sorted(c["notes"])) for c in clips if all(isinstance(n, list) for n in c["notes"])})
    if clips and unique / len(clips) < MIN_UNIQUE_CLIPS:
        out.append(f"only {unique} of {len(clips)} clips are different: a section needs its own ideas, not copies")
    labels = {}
    for c in doc.get("clips", []):
        labels.setdefault((c.get("section"), c.get("part")), []).append(c.get("label"))
    for cell, names in labels.items():
        if len(set(names)) < len(names):
            out.append(f"{cell[0]}/{cell[1]}: options need different labels to choose by")
    for cell, have in seen.items():
        missing = [x for x in letters if x not in have]
        if missing:
            out.append(f"{cell[0]}/{cell[1]}: missing option {', '.join(missing)}")
    if not seen:
        out.append("no clips")
    return out


def warnings(doc):
    """Things worth looking at that don't stop the sketch being built."""
    out = []
    loop_bars = doc["loop_bars"]
    for s in doc["setup"]["sections"]:
        if s["bars"] % loop_bars:
            out.append(f"{s['name']}: {s['bars']} bars isn't a whole number of {loop_bars}-bar loops")
    for section in {c["section"] for c in doc["clips"]}:
        kicks = {n[0] for c in doc["clips"] if c["section"] == section and c["part"] == "Drums"
                 for n in c["notes"] if n[1] in KICKS}
        for c in doc["clips"]:
            if c["section"] == section and c["part"] == "Bass":
                hits = sum(1 for n in c["notes"] if n[0] in kicks)
                if hits:
                    out.append(f"{section}/Bass/{c['option']}: {hits} notes start on a kick")
                rung = sum(1 for k in kicks if any(n[0] < k < n[0] + n[3] for n in c["notes"]))
                if kicks and rung / len(kicks) > RING_WARNING:
                    out.append(f"{section}/Bass/{c['option']}: rings through {rung} of {len(kicks)} kicks")
    return sorted(out)


def slug(song):
    """A song's folder name. A run's folder is called "Song Sketch - <song>", and
    that name means the same song."""
    name = re.sub(r"[^a-z0-9]+", "-", song.lower()).strip("-")
    return re.sub(r"^song-(sketch|analysis)-", "", name)


def install(path, song, root=SKETCHES):
    root = os.path.expanduser(root)
    name = slug(song)
    if not name:
        raise ValueError(f"no usable song name in {song!r}")
    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, "sketch.json")
    if os.path.exists(target):
        os.rename(target, os.path.join(folder, time.strftime("sketch-%Y%m%d-%H%M%S.json")))
    shutil.copyfile(path, target)
    with open(os.path.join(root, "latest"), "w") as f:
        f.write(target + "\n")
    return target


def main():
    args = sys.argv[1:]
    if len(args) not in (1, 3) or (len(args) == 3 and args[1] != "--install"):
        raise SystemExit(__doc__)
    with open(args[0]) as f:
        doc = json.load(f)
    found = problems(doc)
    if found:
        print("\n".join("PROBLEM " + p for p in found))
        sys.exit(1)
    for w in warnings(doc):
        print("WARNING " + w)
    print(f"ok: {len(doc['clips'])} clips, {len(doc['setup']['sections'])} sections, {len(doc['parts'])} parts")
    if len(args) == 3:
        print("installed " + install(args[0], args[2]))


if __name__ == "__main__":
    main()
