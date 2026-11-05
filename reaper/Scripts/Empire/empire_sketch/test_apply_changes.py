#!/usr/bin/env python3
"""python3 empire_sketch/test_apply_changes.py"""

import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apply_changes as ac

failed = []


def check(name, got, want):
    if got != want:
        failed.append(f"{name}: got {got!r}, want {want!r}")


def clip(position_bar, notes, loop=True, source_bars=2, muted=False, name="old"):
    return {"position": (position_bar - 1) * 2.0, "length": 8.0, "muted": muted, "loop": loop, "offset": 0.0,
            "name": name, "notes": notes, "source_ticks": source_bars * 3840, "ppq": 960}


def project():  # 120 BPM: a bar is 2 s. Verse is bars 1-4, Hook bars 5-8.
    return {"tempo": 120.0, "time_signature": [4, 4], "state": {},
            "markers": [{"name": "Verse", "time": 0.0}, {"name": "Hook", "time": 8.0}, {"name": "End", "time": 16.0}],
            "tracks": [{"name": "Bass", "kit": "", "items": [clip(1, [[0, 40, 480, 100]]), clip(5, [[0, 41, 7680, 90]])]},
                       {"name": "Drums", "kit": "Atlas Kit", "items": [clip(5, [[0, 36, 120, 100]])]}]}


SKETCH = {"loop_bars": 2, "clips": [
    {"section": "Hook", "part": "Bass", "option": "B", "label": "gallop", "notes": [[0, 43, 0, 240, 99]]},
    {"section": "Hook", "part": "Drums", "option": "C", "notes": [[0, 49, 0, 120, 110]]}]}


def plan(*changes):
    return ac.make_plan(project(), SKETCH, list(changes))


check("sections", ac.song_sections(project()), [{"name": "Verse", "first_bar": 1, "bars": 4},
                                                {"name": "Hook", "first_bar": 5, "bars": 4}])

e = plan({"op": "pick", "section": "Hook", "part": "Bass", "option": "B"})
check("pick is one looped clip", (len(e), e[0]["first_bar"], e[0]["bars"], e[0]["loop_bars"]), (1, 5, 4, 2))
check("pick name", e[0]["name"], "Hook Bass B: gallop")
check("pick notes", e[0]["notes"], [[0, 43, 0, 240, 99]])

e = plan({"op": "pick", "section": "Hook", "part": "Drums", "option": "C"})
check("picked drums move to the kit", e[0]["notes"][0][1], 48)

e = plan({"op": "clear", "part": "Bass", "bars": [2, 2]})
check("clear flattens the loop and removes a bar", e[0]["notes"],
      [[0, 40, 0, 480, 100], [7680, 40, 0, 480, 100]])
check("clear has no loop", "loop_bars" in e[0], False)
check("edited name", e[0]["name"], "old, edited")

e = plan({"op": "clear", "part": "Bass", "bars": [6, 6]})
check("a note ringing into a cleared bar stops there", e[0]["notes"], [[0, 41, 0, 3840, 90], [7680, 41, 0, 7680, 90]])

e = plan({"op": "clear", "part": "Bass", "bars": [4, 5]})
check("clear across two sections", [x["section"] for x in e], ["Verse", "Hook"])
check("the Hook's first bar is cleared, its second loop stays", e[1]["notes"], [[7680, 41, 0, 7680, 90]])

e = plan({"op": "add", "part": "Drums", "bar": 6, "notes": [[0, 49, 0, 120, 110]]})
check("added drums move to the kit, and the loop's other bars stay", e[0]["notes"],
      [[0, 36, 0, 120, 100], [3840, 48, 0, 120, 110], [7680, 36, 0, 120, 100]])

e = plan({"op": "pick", "section": "Hook", "part": "Bass", "option": "B"},
         {"op": "clear", "part": "Bass", "bars": [8, 8]})
check("clear after a pick works on the picked clip", e[0]["notes"], [[0, 43, 0, 240, 99], [7680, 43, 0, 240, 99]])
check("and notes it was edited", e[0]["name"], "Hook Bass B: gallop, edited")

e = plan({"op": "add", "part": "Bass", "bar": 8, "notes": [[0, 50, 0, 99999, 90]]})
check("a long note stops at the section's end", [n for n in e[0]["notes"] if n[1] == 50], [[11520, 50, 0, 3840, 90]])


def refused(*changes):
    try:
        plan(*changes)
    except ac.ChangeError as err:
        return str(err)
    return None


check("unknown part", refused({"op": "clear", "part": "Flute", "bars": [1, 1]}), "change 1: no track called Flute")
check("unknown option", refused({"op": "pick", "section": "Hook", "part": "Bass", "option": "Z"}),
      "change 1: the sketch has no option Z for Hook Bass")
check("bar past the end", refused({"op": "add", "part": "Bass", "bar": 9, "notes": []}), "change 1: bar 9 isn't in the song")
check("bad note", "bad note" in refused({"op": "add", "part": "Bass", "bar": 1, "notes": [[0, 200, 0, 1, 1]]}), True)
check("malformed", "malformed" in refused({"part": "Bass"}), True)

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "..", "empire_panel", "core.lua")) as f:
    lua = re.search(r'\["Atlas Kit"\].*?from_gm = \{(.*?)\},\s*fallback = (\d+)', f.read(), re.S)
table = {int(k): int(v) for k, v in re.findall(r"\[(\d+)\] = (\d+)", lua.group(1))}
check("kit map matches core.lua", ac.KIT_FROM_GM["Atlas Kit"], (table, int(lua.group(2))))

RPP = """<REAPER_PROJECT 0.1 "7" 1
  TEMPO 120 4 4
  MARKER 1 0 "Verse" 0
  MARKER 2 8 "End" 0
  <TRACK
    NAME "Bass"
  >
>
"""
with tempfile.TemporaryDirectory() as root:
    folder = os.path.join(root, "song")
    os.mkdir(folder)
    changes = os.path.join(root, "c.json")
    with open(changes, "w") as f:
        json.dump({"schema": "empire.changes/v1", "changes": [{"op": "clear", "part": "Bass", "bars": [1, 1]}]}, f)
    with open(os.path.join(folder, "sketch.json"), "w") as f:
        json.dump({"loop_bars": 2, "clips": []}, f)

    def ask(**kw):
        kw.setdefault("running", lambda: True)
        kw.setdefault("wait", 1)
        kw.setdefault("pause", 0.01)
        return ac.request_changes("song", changes, root, **kw)

    check("no master", ask()["ok"], False)
    base = os.path.join(folder, "master-20260101-000000.RPP")
    with open(base, "w") as f:
        f.write(RPP)
    with open(os.path.join(folder, "master-20250101-000000.RPP"), "w") as f:
        f.write("old")
    check("reaper closed", ask(running=lambda: False)["message"].startswith("REAPER isn't running"), True)

    seen = {}

    def reaper_says(**fields):
        def start():
            with open(os.path.join(root, "apply-request.json")) as f:
                seen.update(json.load(f))
            with open(os.path.join(root, "apply-result.json"), "w") as f:
                json.dump(fields, f)
        return start

    got = ask(start=reaper_says(ok=False, message="save it"))
    check("reaper's refusal comes back", got["message"], "save it")
    check("and the copy is removed", len([n for n in os.listdir(folder) if n.endswith(".RPP")]), 2)
    check("newest master is the base", seen["base"], base)

    got = ask(start=reaper_says(ok=True))
    check("done", (got["ok"], got["base"], got["entries"]), (True, base, 1))
    check("base untouched", open(base).read(), RPP)
    check("new master made", open(got["master"]).read(), RPP)
    check("changes kept beside it", os.path.exists(got["master"][:-4] + ".changes.json"), True)

    os.remove(got["master"])
    check("no answer", "didn't answer" in ask(start=lambda: None, wait=0)["message"], True)

if failed:
    print("\n".join(failed))
    sys.exit(1)
print("ok")
