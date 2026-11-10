#!/usr/bin/env python3
"""python3 empire_sketch/test_check_sketch.py"""

import copy
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_sketch as cs


def doc():
    clip = lambda section, part, option, pitch: {"section": section, "part": part, "option": option, "label": "x",
                                                 "notes": [[0, pitch, 0, 240, 100]]}
    return {"schema": "empire.sketch/v1", "ppq": 960, "loop_bars": 2, "options": 2,
            "setup": {"schema": "empire.setup/v1", "tempo": 138, "time_signature": [4, 4], "key": "C#", "scale": "minor",
                      "sections": [{"name": "Drop", "bars": 8}], "tracks": []},
            "harmony": {"Drop": ["C#m", "A"]},
            "parts": [{"name": "Drums"}, {"name": "Bass"}],
            "clips": [clip("Drop", "Drums", "A", 36), clip("Drop", "Drums", "B", 38),
                      clip("Drop", "Bass", "A", 37), clip("Drop", "Bass", "B", 49)]}


def labelled():
    d = doc()
    for i, c in enumerate(d["clips"]):
        c["label"] = "idea %d" % i
    return d


failed = []


def check(name, got, want):
    if got != want:
        failed.append(f"{name}: got {got!r}, want {want!r}")


def bad(name, change, expect):
    d = copy.deepcopy(labelled())
    change(d)
    found = cs.problems(d)
    if not any(expect in p for p in found):
        failed.append(f"{name}: wanted {expect!r} in {found!r}")


check("good sketch", cs.problems(labelled()), [])
bad("schema", lambda d: d.update(schema="x"), "not an empire.sketch")
bad("key", lambda d: d["setup"].update(key="H"), "unknown key")
bad("no harmony", lambda d: d.pop("harmony"), "no harmony")
bad("short harmony", lambda d: d["harmony"].update(Drop=["C#m"]), "needs 2 chords")
bad("missing option", lambda d: d["clips"].pop(), "missing option B")
bad("twice", lambda d: d["clips"][3].update(option="A"), "appears twice")
bad("unknown part", lambda d: d["clips"][0].update(part="Nope"), "unknown part")
bad("out of key", lambda d: d["clips"][2]["notes"][0].__setitem__(1, 38), "outside the key")
bad("past the loop", lambda d: d["clips"][2]["notes"][0].__setitem__(0, 7680), "doesn't fit")
bad("float", lambda d: d["clips"][2]["notes"][0].__setitem__(0, 0.5), "whole numbers")
bad("drum note", lambda d: d["clips"][0]["notes"][0].__setitem__(1, 60), "General MIDI")
bad("no label", lambda d: d["clips"][0].pop("label"), "no label")
bad("identical", lambda d: d["clips"][3].update(notes=d["clips"][2]["notes"]), "identical")
same = doc()
check("same labels are refused", any("different labels" in p for p in cs.problems(same)), True)
copies = labelled()
copies["clips"][3]["notes"] = copies["clips"][0]["notes"]
copies["clips"][2]["notes"] = copies["clips"][0]["notes"]
copies["clips"][1]["notes"] = copies["clips"][0]["notes"]
check("copied clips are refused", any("are different" in p for p in cs.problems(copies)), True)
allowed = labelled()
allowed["clips"][2]["notes"][0][1] = 38
allowed["clips"][2]["outside_key"] = True
check("outside key on purpose", cs.problems(allowed), [])

kick = labelled()
kick["clips"][2]["notes"][0][1] = 37
rings = labelled()
rings["clips"][2]["notes"] = [[1, 37, 0, 480, 100]]
rings["clips"][0]["notes"] = [[240, 36, 0, 100, 100]]
check("bass through a kick warns", any("rings through" in w for w in cs.warnings(rings)), True)
check("bass on kick warns", any("start on a kick" in w for w in cs.warnings(kick)), True)
check("slug", cs.slug("Goa Sketch 2!"), "goa-sketch-2")
check("run folder name is the same song", cs.slug("Song Sketch - Dark Synthwave 1"), "dark-synthwave-1")
check("analysis run too", cs.slug("Song Analysis - Dark Synthwave 1"), "dark-synthwave-1")

with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, "in.json")
    with open(path, "w") as f:
        json.dump(labelled(), f)
    target = cs.install(path, "Goa Sketch 2", root)
    check("target", target, os.path.join(root, "goa-sketch-2", "sketch.json"))
    check("latest", open(os.path.join(root, "latest")).read().strip(), target)
    cs.install(path, "Goa Sketch 2", root)
    check("old one is kept", len(os.listdir(os.path.dirname(target))), 2)

# A second kit: a part named "Drums Live" on Superior plays GM drum notes too.
d = doc()
d["parts"].append({"name": "Drums Live", "template": "Superior Drummer Kit"})
d["clips"] += [{"section": "Drop", "part": "Drums Live", "option": o, "label": "live " + o,
                "notes": [[0, p, 0, 240, 100]]} for o, p in (("A", 38), ("B", 42))]
check("second kit's drum notes pass the key check", [x for x in cs.problems(d) if "Drums Live" in x], [])
d["clips"][-1]["notes"] = [[0, 61, 0, 240, 100]]
check("second kit still needs drum notes", any("Drums Live" in x and "drum note" in x for x in cs.problems(d)), True)

# Harmonic major: A natural is in C# harmonic major, A# isn't.
d = doc()
d["setup"]["scale"] = "harmonic major"
d["clips"][2]["notes"] = [[0, 57, 0, 240, 100]]     # A3
d["clips"][3]["notes"] = [[0, 58, 0, 240, 100]]     # A#3
probs = cs.problems(d)
check("harmonic major is a scale", any("unknown scale" in x for x in probs), False)
check("harmonic major's flat 6 is in key", any("Drop/Bass/A" in x for x in probs), False)
check("its natural 6 isn't", any("Drop/Bass/B" in x and "outside the key" in x for x in probs), True)

if failed:
    print("\n".join("FAIL " + f for f in failed))
    sys.exit(1)
print("ok")
