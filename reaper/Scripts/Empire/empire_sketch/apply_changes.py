#!/usr/bin/env python3
"""Applies a list of changes to a song's newest saved master, as a new dated master.
The old master isn't touched, so the two can be compared. REAPER has to be running;
this never starts it.

    apply_changes.py <song> <changes.json>

The file holds {"schema": "empire.changes/v1", "changes": [...]}, applied in order:

    {"op": "pick",  "section": "Hook", "part": "Stabs", "option": "B"}
    {"op": "clear", "part": "Drums", "bars": [104, 104]}
    {"op": "add",   "part": "Lead", "bar": 103, "notes": [[0, 76, 0, 480, 90]]}

Bars are song bars, and both ends of "bars" count. Notes are [start, pitch, channel,
length, velocity] like a sketch's, with start in ticks from the start of "bar" and
drums written as General MIDI. A section's part that is cleared or added to becomes
one long clip of its notes, so controller data in that clip isn't kept.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import time

import read_master as rm
from check_sketch import SKETCHES, slug

REAPER = "/Applications/REAPER.app/Contents/MacOS/REAPER"
SCRIPT = "~/Library/Application Support/REAPER/Scripts/Empire/Empire Apply Changes.lua"
WAIT_SECONDS = 180
PPQ = 960
# Empire core.lua holds the same.
KIT_FROM_GM = {"Atlas Kit": ({35: 36, 36: 36, 37: 43, 38: 37, 39: 38, 40: 37, 41: 42, 42: 39, 43: 42, 44: 39,
                              45: 42, 46: 40, 47: 42, 48: 42, 49: 48, 50: 42, 51: 49, 69: 41, 70: 41}, 43)}


class ChangeError(Exception):
    pass


def kit_note(kit, pitch):
    if kit not in KIT_FROM_GM:
        return pitch
    table, fallback = KIT_FROM_GM[kit]
    return table.get(pitch, fallback)


def song_sections(project):
    """Name, first bar and bars of each section, from the master's markers."""
    beats = project["time_signature"][0] * 4 / project["time_signature"][1]
    bar_seconds = beats * 60 / project["tempo"]
    marks = sorted(project["markers"], key=lambda m: m["time"])
    if not marks or marks[-1]["name"].lower() != "end":
        raise ChangeError("the master has no End marker, so its sections can't be read")
    first = [round(m["time"] / bar_seconds) + 1 for m in marks]
    return [{"name": m["name"], "first_bar": first[i], "bars": first[i + 1] - first[i]}
            for i, m in enumerate(marks[:-1])]


def _loop(notes, loop_ticks, length):
    out = []
    for k in range(length // loop_ticks + 1):
        for s, p, c, l, v in notes:
            at = s + k * loop_ticks
            if at < length:
                out.append([at, p, c, min(l, length - at), v])
    return out


class Plan:
    def __init__(self, project, sketch):
        self.project, self.sketch = project, sketch
        self.tps = project["tempo"] / 60 * PPQ
        beats = project["time_signature"][0] * 4 / project["time_signature"][1]
        self.bar_ticks = round(beats * PPQ)
        self.sections = song_sections(project)
        self.tracks = {t["name"]: t for t in project["tracks"]}
        self.touched = {}

    def _track(self, part):
        if part not in self.tracks:
            raise ChangeError(f"no track called {part}")
        return self.tracks[part]

    def _section_at(self, bar):
        for s in self.sections:
            if s["first_bar"] <= bar < s["first_bar"] + s["bars"]:
                return s
        raise ChangeError(f"bar {bar} isn't in the song")

    def _section_named(self, name):
        for s in self.sections:
            if s["name"] == name:
                return s
        raise ChangeError(f"no section called {name}")

    def _existing(self, part, section):
        """What the master plays now: notes from the section's start, and a clip name."""
        start = (section["first_bar"] - 1) * self.bar_ticks
        length = section["bars"] * self.bar_ticks
        notes, names = [], []
        for item in self._track(part)["items"]:
            at = round(item["position"] * self.tps)
            if item["muted"] or not start <= at < start + length:
                continue
            names.append(item["name"])
            notes += [[n[0] - start, n[1], 0, n[2], n[3]] for n in rm.expand(item, self.tps)]
        return notes, " + ".join(n for n in names if n)

    def _flat(self, part, section):
        """A part's section as one long clip, ready to edit."""
        key = (part, section["name"])
        entry = self.touched.get(key)
        length = section["bars"] * self.bar_ticks
        if entry is None:
            notes, name = self._existing(part, section)
            entry = {"part": part, "section": section["name"], "first_bar": section["first_bar"],
                     "bars": section["bars"], "name": name or f"{section['name']} {part}", "notes": notes}
            self.touched[key] = entry
        elif entry.get("loop_bars"):
            entry["notes"] = _loop(entry["notes"], entry.pop("loop_bars") * self.bar_ticks, length)
        if not entry["name"].endswith(", edited"):
            entry["name"] += ", edited"
        return entry

    def pick(self, section, part, option):
        track = self._track(part)
        where = self._section_named(section)
        for clip in self.sketch["clips"]:
            if (clip["section"], clip["part"], clip["option"]) == (section, part, option):
                break
        else:
            raise ChangeError(f"the sketch has no option {option} for {section} {part}")
        label = f": {clip['label']}" if clip.get("label") else ""
        self.touched[(part, section)] = {
            "part": part, "section": section, "first_bar": where["first_bar"], "bars": where["bars"],
            "loop_bars": self.sketch["loop_bars"], "name": f"{section} {part} {option}{label}",
            "notes": [[n[0], kit_note(track.get("kit", ""), n[1]), n[2], n[3], n[4]] for n in clip["notes"]]}

    def clear(self, part, first, last):
        self._track(part)
        if last < first:
            raise ChangeError(f"bars {first}-{last} run backwards")
        for s in self.sections:
            top = s["first_bar"] + s["bars"] - 1
            if s["first_bar"] > last or top < first:
                continue
            entry = self._flat(part, s)
            lo = (max(first, s["first_bar"]) - s["first_bar"]) * self.bar_ticks
            hi = (min(last, top) - s["first_bar"] + 1) * self.bar_ticks
            kept = []
            for n in entry["notes"]:
                if lo <= n[0] < hi:
                    continue
                kept.append([n[0], n[1], n[2], min(n[3], lo - n[0]) if n[0] < lo else n[3], n[4]])
            entry["notes"] = kept

    def add(self, part, bar, notes):
        track = self._track(part)
        section = self._section_at(bar)
        entry = self._flat(part, section)
        base = (bar - section["first_bar"]) * self.bar_ticks
        length = section["bars"] * self.bar_ticks
        for s, p, c, l, v in notes:
            if not (0 <= p <= 127 and 1 <= v <= 127 and l > 0 and s >= 0):
                raise ChangeError(f"bad note at bar {bar}: {[s, p, c, l, v]}")
            if base + s >= length:
                raise ChangeError(f"a note from bar {bar} starts after {section['name']} ends")
            entry["notes"].append([base + s, kit_note(track.get("kit", ""), p), c, min(l, length - base - s), v])

    def entries(self):
        for entry in self.touched.values():
            entry["notes"].sort()
        return sorted(self.touched.values(), key=lambda e: (e["first_bar"], e["part"]))


def make_plan(project, sketch, changes):
    plan = Plan(project, sketch)
    for i, change in enumerate(changes):
        try:
            op = change["op"]
            if op == "pick":
                plan.pick(change["section"], change["part"], change["option"])
            elif op == "clear":
                plan.clear(change["part"], change["bars"][0], change["bars"][1])
            elif op == "add":
                plan.add(change["part"], change["bar"], change["notes"])
            else:
                raise ChangeError(f"unknown op {op}")
        except (KeyError, IndexError, TypeError, ValueError) as err:
            raise ChangeError(f"change {i + 1} is malformed: {err!r}")
        except ChangeError as err:
            raise ChangeError(f"change {i + 1}: {err}")
    return plan.entries()


def is_running():
    return subprocess.run(["pgrep", "-x", "REAPER"], stdout=subprocess.DEVNULL).returncode == 0


def launch():
    subprocess.run([REAPER, "-nonewinst", os.path.expanduser(SCRIPT)], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=60, check=False)


def newest_master(folder):
    masters = sorted(glob.glob(os.path.join(folder, "master-*.RPP")))
    return masters[-1] if masters else None


def request_changes(song, changes_path, root=SKETCHES, running=is_running, start=launch,
                    wait=WAIT_SECONDS, pause=1):
    """Returns the answer: {"ok": true, "master": ..., "base": ..., "entries": n} or {"ok": false, "message": ...}."""
    root = os.path.expanduser(root)
    folder = os.path.join(root, slug(song))
    base = newest_master(folder)
    if not base:
        return {"ok": False, "message": f"no master-*.RPP in {folder}"}
    if not running():
        return {"ok": False, "message": "REAPER isn't running. Open it, then try again."}
    with open(changes_path) as f:
        changes = json.load(f)
    if changes.get("schema") != "empire.changes/v1":
        return {"ok": False, "message": "the changes file's schema isn't empire.changes/v1"}
    with open(os.path.join(folder, "sketch.json")) as f:
        sketch = json.load(f)
    try:
        entries = make_plan(rm.parse_project(base), sketch, changes["changes"])
    except ChangeError as err:
        return {"ok": False, "message": str(err)}
    if not entries:
        return {"ok": False, "message": "the changes file changes nothing"}

    master = os.path.join(folder, "master-" + time.strftime("%Y%m%d-%H%M%S") + ".RPP")
    if os.path.exists(master):
        return {"ok": False, "message": f"{master} already exists; try again in a second"}
    shutil.copy2(base, master)
    result = os.path.join(root, "apply-result.json")
    if os.path.exists(result):
        os.remove(result)
    with open(os.path.join(root, "apply-request.json"), "w") as f:
        json.dump({"base": base, "master": master, "entries": entries}, f)
    start()
    end = time.time() + wait
    answer = {"ok": False, "message": f"REAPER didn't answer within {wait} seconds. Is a dialog open in it?"}
    while time.time() < end:
        if os.path.exists(result):
            with open(result) as f:
                answer = json.load(f)
            break
        time.sleep(pause)
    if not answer.get("ok"):
        os.remove(master)
        return answer
    shutil.copy2(changes_path, master[:-len(".RPP")] + ".changes.json")
    return {"ok": True, "master": master, "base": base, "entries": len(entries)}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    answer = request_changes(sys.argv[1], sys.argv[2])
    if not answer.get("ok"):
        print("FAILED: " + answer.get("message", "no reason given"))
        sys.exit(1)
    print(f"master {answer['master']}: {answer['entries']} clips rewritten, from {os.path.basename(answer['base'])}")


if __name__ == "__main__":
    main()
