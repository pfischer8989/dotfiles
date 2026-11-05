#!/usr/bin/env python3
"""Reads a saved master .RPP and writes down what is actually in it, per section,
for Song Analysis to work from. It reads the project rather than the sketch, so
hand edits count. It only reads notes: it can't tell what a patch sounds like.

    read_master.py <master.RPP> [out folder]   (default: next to the project)

Writes <name>.facts.json and <name>.facts.md.
"""

import json
import os
import re
import shlex
import sys

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ROOTS = {n: i for i, n in enumerate(NAMES)}
ROOTS.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10, "Cb": 11})
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
          "dorian": [0, 2, 3, 5, 7, 9, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10],
          "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
          "harmonic minor": [0, 2, 3, 5, 7, 8, 11], "melodic minor": [0, 2, 3, 5, 7, 9, 11],
          "phrygian dominant": [0, 1, 4, 5, 7, 8, 10], "locrian": [0, 1, 3, 5, 6, 8, 10],
          "minor pentatonic": [0, 3, 5, 7, 10], "major pentatonic": [0, 2, 4, 7, 9]}
# What each note is on a kit the build mapped. Empire core.lua holds the same.
KIT_NAMES = {"Atlas Kit": {36: "kick", 37: "snare", 38: "clap", 39: "hat", 40: "open hat", 41: "shaker", 42: "tom",
                           43: "other", 44: "other 2", 45: "other 3", 46: "other 4", 47: "other 5"}}
DRUM_NAMES = {35: "kick2", 36: "kick", 37: "rim", 38: "snare", 39: "clap", 40: "snare2", 41: "tom", 42: "hat",
              43: "tom", 44: "pedal hat", 45: "tom low", 46: "open hat", 47: "tom mid", 48: "tom high",
              49: "crash", 50: "tom", 51: "ride", 69: "shaker", 70: "shaker"}
STEPS_PER_BAR = 16


def note_name(p):
    return f"{NAMES[p % 12]}{p // 12 - 1}"


def parse_midi(lines):
    """Notes as [start, pitch, length, velocity] in source ticks, and the source length."""
    now, held, notes = 0, {}, []
    for line in lines:
        t = line.split()
        if not t or t[0][0] not in "EeXx" or not t[0].rstrip("m").lower() in ("e", "x"):
            continue
        now += int(t[1])
        if t[0][0] in "Xx" or len(t) < 5:
            continue
        status, pitch, value = int(t[2], 16), int(t[3], 16), int(t[4], 16)
        kind, channel = status & 0xF0, status & 0x0F
        if kind == 0x90 and value > 0:
            held[(channel, pitch)] = (now, value, "m" in t[0])
        elif kind in (0x80, 0x90) and (channel, pitch) in held:
            start, velocity, muted = held.pop((channel, pitch))
            if not muted:
                notes.append([start, pitch, now - start, velocity])
    return notes, now


def parse_project(path):
    project = {"tempo": None, "time_signature": [4, 4], "markers": [], "tracks": [], "state": {},
               "tempo_points": set()}
    stack, track, item, midi = [], None, None, None
    with open(path, errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("<"):
                tag = line[1:].split()[0] if line[1:] else ""
                stack.append(tag)
                if tag == "TRACK" and len(stack) == 2:
                    track = {"name": "", "instrument": "", "items": [], "muted": False, "audio": False, "kit": ""}
                    project["tracks"].append(track)
                elif tag == "ITEM" and track is not None:
                    item = {"position": 0.0, "length": 0.0, "muted": False, "loop": False, "offset": 0.0,
                            "name": "", "notes": [], "source_ticks": 0, "ppq": 960}
                    track["items"].append(item)
                elif tag == "SOURCE" and item is not None and "MIDI" in line:
                    midi = []
                elif tag == "SOURCE" and item is not None and "SECTION" not in line and track is not None:
                    track["audio"] = True
                elif tag.startswith("VST") or tag.startswith("AU") or tag == "JS":
                    if track is not None and not track["instrument"] and re.match(r'<(VST3?i|AUi)|<VST "VST3?i:|<AU "AUi:', line):
                        track["instrument"] = re.sub(r" \(.*", "", shlex.split(line[1:], posix=True)[1]).split(": ")[-1]
                continue
            if line == ">":
                tag = stack.pop() if stack else ""
                if tag == "SOURCE" and midi is not None:
                    item["notes"], item["source_ticks"] = parse_midi(midi)
                    midi = None
                elif tag == "ITEM":
                    item = None
                elif tag == "TRACK" and len(stack) == 1:
                    track = None
                continue
            if midi is not None:
                if line.startswith("HASDATA"):
                    item["ppq"] = int(line.split()[2])
                else:
                    midi.append(line)
                continue
            parent = stack[-1] if stack else ""
            if parent == "EXT" and len(stack) == 3 and track is not None and line.startswith("empire_drums "):
                track["kit"] = line.split(" ", 1)[1].strip('"')
                continue
            word = line.split(" ", 1)
            key, rest = word[0], word[1] if len(word) > 1 else ""
            if parent == "EMPIRE":
                project["state"][key] = rest
            elif parent == "REAPER_PROJECT":
                if key == "TEMPO":
                    t = rest.split()
                    project["tempo"], project["time_signature"] = float(t[0]), [int(t[1]), int(t[2])]
                elif key == "MARKER":
                    t = shlex.split(rest)
                    if t[3] == "0":  # regions come as pairs and set this flag
                        project["markers"].append({"name": t[2], "time": float(t[1])})
            elif parent == "TEMPOENVEX" and key == "PT":
                project["tempo_points"].add(float(rest.split()[1]))
            elif parent == "TRACK" and track is not None:
                if key == "NAME":
                    track["name"] = shlex.split(rest)[0] if rest else ""
                elif key == "MUTESOLO":
                    track["muted"] = rest.split()[0] == "1"
            elif parent == "ITEM" and item is not None:
                if key == "POSITION":
                    item["position"] = float(rest)
                elif key == "LENGTH":
                    item["length"] = float(rest)
                elif key == "MUTE":
                    item["muted"] = rest.split()[0] == "1"
                elif key == "LOOP":
                    item["loop"] = rest.strip() == "1"
                elif key == "SOFFS":
                    item["offset"] = float(rest.split()[0])
                elif key == "NAME":
                    item["name"] = shlex.split(rest)[0] if rest else ""
    return project


def expand(item, ticks_per_second):
    """The notes an item really plays, in project ticks, looped and trimmed."""
    start = round(item["position"] * ticks_per_second)
    length = round(item["length"] * ticks_per_second)
    offset = round(item["offset"] * ticks_per_second)
    source = item["source_ticks"]
    out = []
    repeats = (length + offset) // source + 1 if item["loop"] and source > 0 else 1
    for k in range(repeats):
        for s, p, l, v in item["notes"]:
            at = s + k * source - offset
            if 0 <= at < length:
                out.append([start + at, p, min(l, length - at), v])
    return out


def is_drums(notes, name, instrument, kit=""):
    if kit:
        return True
    named = "drum" in name.lower() or "atlas" in instrument.lower()
    return named and bool(notes) and all(35 <= n[1] <= 51 or n[1] in (69, 70) for n in notes)


def analyse(project, source_name=""):
    if not project["tempo"]:
        raise ValueError("no tempo in the project")
    if not project["markers"]:
        raise ValueError("no section markers in the project")
    ppq = 960
    tps = project["tempo"] / 60 * ppq
    beats = project["time_signature"][0] * 4 / project["time_signature"][1]
    bar = round(beats * ppq)
    step = bar // STEPS_PER_BAR
    key, scale = project["state"].get("KEY"), project["state"].get("SCALE")
    in_key = None
    if key in ROOTS and scale in SCALES:
        in_key = {(ROOTS[key] + i) % 12 for i in SCALES[scale]}

    marks = sorted(project["markers"], key=lambda m: m["time"])
    bounds = [round(m["time"] * tps) for m in marks]
    has_end = marks[-1]["name"].lower() == "end"
    sections = []
    for i, m in enumerate(marks[:-1] if has_end else marks):
        sections.append({"name": m["name"], "start": bounds[i], "end": bounds[i + 1] if i + 1 < len(bounds) else None})

    parts = []
    for t in project["tracks"]:
        live = [i for i in t["items"] if not i["muted"] and i["notes"]]
        if not live or t["muted"]:
            continue
        notes = []
        for i in live:
            notes += expand(i, tps)
        parts.append({"name": t["name"], "instrument": t["instrument"], "items": live, "notes": notes,
                      "drums": is_drums(notes, t["name"], t["instrument"], t.get("kit", "")),
                      "names": KIT_NAMES.get(t.get("kit", ""), DRUM_NAMES)})
    song_end = max((n[0] + n[2] for p in parts for n in p["notes"]), default=0)
    if sections and sections[-1]["end"] is None:
        sections[-1]["end"] = max(song_end, sections[-1]["start"] + bar)

    facts = {"schema": "empire.song-facts/v1", "project": source_name, "tempo": project["tempo"],
             "time_signature": project["time_signature"], "key": key, "scale": scale,
             "tempo_changes_ignored": bool(project["tempo_points"] - {project["tempo"]}),
             "audio_not_read": [t["name"] for t in project["tracks"] if t.get("audio")],
             "tracks": [{"name": p["name"], "instrument": p["instrument"], "drums": p["drums"]} for p in parts],
             "sections": []}
    for s in sections:
        facts["sections"].append(section_facts(s, parts, bar, step, in_key, ppq, tps))
    return facts


def section_facts(section, parts, bar, step, in_key, ppq, tps):
    start, end = section["start"], section["end"]
    bars = round((end - start) / bar)
    out = {"name": section["name"], "first_bar": start // bar + 1, "bars": bars, "parts": {}, "pairs": []}
    pitched = {}
    kicks = set()
    for p in parts:
        notes = sorted(n for n in p["notes"] if start <= n[0] < end)
        if not notes:
            continue
        clips = [i["name"] for i in p["items"]
                 if round(i["position"] * tps) < end and round((i["position"] + i["length"]) * tps) > start]
        fact = {"clips": clips, "notes_per_bar": round(len(notes) / bars, 1),
                "velocity": [min(n[3] for n in notes), max(n[3] for n in notes)]}
        by_bar = {}
        for n in notes:
            by_bar.setdefault((n[0] - start) // bar, []).append((n[0] % bar, n[1], n[2], n[3]))
        shapes = [tuple(sorted(by_bar.get(b, []))) for b in range(bars)]
        fact["distinct_bars"] = len(set(shapes))
        fact["repeats_every_bars"] = next((c for c in range(1, bars + 1)
                                           if all(shapes[b] == shapes[b % c] for b in range(bars))), bars)
        if p["drums"]:
            hits = {}
            for n in notes:
                hits[n[1]] = hits.get(n[1], 0) + 1
            names = p["names"]
            fact["hits_per_bar"] = {names.get(k, str(k)): round(v / bars, 1) for k, v in sorted(hits.items())}
            kicks |= {n[0] for n in notes if names.get(n[1], "").startswith("kick")}
            last = [n for n in notes if n[0] >= end - bar]
            fact["last_bar_snares"] = sum(1 for n in last if names.get(n[1], "").startswith("snare"))
        else:
            fact["range"] = [note_name(min(n[1] for n in notes)), note_name(max(n[1] for n in notes))]
            fact["pitch_classes"] = sorted({NAMES[n[1] % 12] for n in notes}, key=NAMES.index)
            if in_key is not None:
                fact["out_of_key"] = sum(1 for n in notes if n[1] % 12 not in in_key)
            fact["root_per_bar"] = [NAMES[min(x[1] for x in by_bar[b]) % 12] if b in by_bar else "-"
                                    for b in range(min(bars, fact["repeats_every_bars"]))]
            hit = [False] * STEPS_PER_BAR
            for b in by_bar.values():
                for x in b:
                    hit[x[0] // step] = True
            fact["onsets_across_bars"] = "".join("x" if h else "." for h in hit)
            fact["sustain"] = round(sum(n[2] for n in notes) / (end - start), 2)
            pitched[p["name"]] = notes
        out["parts"][p["name"]] = fact
    out["notes_per_bar"] = round(sum(f["notes_per_bar"] for f in out["parts"].values()), 1)

    # bass against kick, and each pair of pitched parts against each other
    grid = {}
    steps = (end - start) // step
    for name, notes in pitched.items():
        g = [set() for _ in range(steps)]
        for n in notes:
            for i in range((n[0] - start) // step, min(steps, (n[0] + max(n[2] - 1, 0) - start) // step + 1)):
                g[i].add(n[1])
        grid[name] = g
        if kicks:
            on = sum(1 for n in notes if n[0] in kicks)
            over = sum(1 for k in kicks if any(n[0] < k < n[0] + n[2] for n in notes))
            out["parts"][name]["onsets_on_kick"] = on
            out["parts"][name]["held_across_kick"] = over
    names = list(grid)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = clash = tight = 0
            clash_bars = set()
            for at, (x, y) in enumerate(zip(grid[a], grid[b])):
                if not x or not y:
                    continue
                both += 1
                ic = {min((m - n) % 12, (n - m) % 12) for m in x for n in y}
                if 1 in ic:
                    clash += 1
                    clash_bars.add(out["first_bar"] + at // STEPS_PER_BAR)
                if any(abs(m - n) in (1, 2) and min(m, n) < 60 for m in x for n in y):
                    tight += 1
            ra, rb = out["parts"][a]["range"], out["parts"][b]["range"]
            la, lb = pitched[a], pitched[b]
            overlap = min(max(n[1] for n in la), max(n[1] for n in lb)) - max(min(n[1] for n in la), min(n[1] for n in lb))
            out["pairs"].append({"a": a, "b": b, "shared_steps": both, "semitone_clash_pct": round(100 * clash / both) if both else 0,
                                 "close_low_pct": round(100 * tight / both) if both else 0,
                                 "clash_bars": sorted(clash_bars),
                                 "range_overlap_semitones": max(overlap, 0), "ranges": [ra, rb]})
    return out


def to_markdown(facts):
    lines = [f"# Facts: {facts['project']}", "",
             f"{facts['tempo']:g} BPM, {facts['time_signature'][0]}/{facts['time_signature'][1]}, {facts['key']} {facts['scale']}", ""]
    if facts["tempo_changes_ignored"]:
        lines += ["WARNING: the project has tempo changes and bar numbers here ignore them.", ""]
    if facts["audio_not_read"]:
        lines += ["WARNING: audio on these tracks wasn't read: " + ", ".join(facts["audio_not_read"]), ""]
    lines.append("Tracks: " + ", ".join(f"{t['name']} ({t['instrument'] or 'no instrument'})" for t in facts["tracks"]))
    for s in facts["sections"]:
        lines += ["", f"## {s['name']}: bar {s['first_bar']}, {s['bars']} bars, {s['notes_per_bar']} notes a bar"]
        for name, f in s["parts"].items():
            lines.append(f"- {name}: {'; '.join(f['clips'])}. {f['notes_per_bar']}/bar, vel {f['velocity'][0]}-{f['velocity'][1]}, "
                         f"repeats every {f['repeats_every_bars']} bars ({f['distinct_bars']} distinct)")
            if "hits_per_bar" in f:
                lines.append(f"    hits/bar {f['hits_per_bar']}; last bar snares {f['last_bar_snares']}")
            else:
                lines.append(f"    range {f['range'][0]}-{f['range'][1]}, sustain {f['sustain']}, out of key {f.get('out_of_key')}, "
                             f"pcs {' '.join(f['pitch_classes'])}")
                lines.append(f"    roots {' '.join(f['root_per_bar'])}; grid {f['onsets_across_bars']}; "
                             f"on kick {f.get('onsets_on_kick')}, across kick {f.get('held_across_kick')}")
        for p in s["pairs"]:
            lines.append(f"- {p['a']}/{p['b']}: semitone clash {p['semitone_clash_pct']}% of {p['shared_steps']} shared 16ths, "
                         f"close low {p['close_low_pct']}%, range overlap {p['range_overlap_semitones']} st, "
                         f"bars {' '.join(map(str, p['clash_bars'])) or 'none'}")
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) == 3 else os.path.dirname(os.path.abspath(path))
    base = os.path.join(out, os.path.splitext(os.path.basename(path))[0])
    facts = analyse(parse_project(path), os.path.basename(path))
    with open(base + ".facts.json", "w") as f:
        json.dump(facts, f, indent=1)
    with open(base + ".facts.md", "w") as f:
        f.write(to_markdown(facts))
    print(base + ".facts.md")


if __name__ == "__main__":
    main()
