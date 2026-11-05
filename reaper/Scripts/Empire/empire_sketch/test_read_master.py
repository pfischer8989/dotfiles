#!/usr/bin/env python3
"""python3 empire_sketch/test_read_master.py"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import read_master as rm

# 120 BPM: a bar is 2 s, and 3840 ticks
RPP = """<REAPER_PROJECT 0.1 "7.78/macOS-arm64" 1
  TEMPO 120 4 4 0
  MARKER 1 0 Intro 0 0 1 B {A} 0 2
  MARKER 2 4 "Drop 2" 0 0 1 B {B} 0 2
  MARKER 3 8 End 0 0 1 B {C} 0 2
  <EXTSTATE
    <EMPIRE
      KEY C#
      SCALE minor
    >
  >
  <TRACK {1}
    NAME "Bass"
    <FXCHAIN
      <VST "VST3i: Hive (u-he)" Hive.vst3 0 "" 1{X}
        abc=
      >
      <VST "VST3: Presswerk (u-he)" Presswerk.vst3 0 "" 2{Y}
        abc=
      >
    >
    <ITEM
      POSITION 0
      LENGTH 8
      LOOP 1
      MUTE 0 0
      NAME "Loop"
      SOFFS 0 0
      <SOURCE MIDI
        HASDATA 1 960 QN
        E 0 90 25 64
        E 480 80 25 00
        E 3360 90 26 50
        E 480 80 26 00
        E 3360 b0 7b 00
        CCINTERP 32
      >
    >
    <ITEM
      POSITION 0
      LENGTH 8
      LOOP 1
      MUTE 1 0
      NAME "Muted"
      <SOURCE MIDI
        HASDATA 1 960 QN
        E 0 90 3c 64
        E 480 80 3c 00
        E 7200 b0 7b 00
      >
    >
  >
  <TRACK {2}
    NAME Atlas
    <FXCHAIN
      <VST "VST3i: Atlas (Algonaut)" Atlas.vst3 0 "" 3{Z}
      >
    >
    <ITEM
      POSITION 4
      LENGTH 2
      LOOP 0
      MUTE 0 0
      NAME Beat
      <SOURCE MIDI
        HASDATA 1 960 QN
        E 0 90 24 7c
        E 200 80 24 00
        E 3640 b0 7b 00
      >
    >
  >
  <TRACK {3}
    NAME Empty
  >
>
"""


def main():
    failed = []

    def check(name, got, want):
        if got != want:
            failed.append(f"{name}: got {got!r}, want {want!r}")

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "m.RPP")
        with open(path, "w") as f:
            f.write(RPP)
        project = rm.parse_project(path)
    check("tempo", project["tempo"], 120.0)
    check("key state", project["state"]["KEY"], "C#")
    check("markers", [m["name"] for m in project["markers"]], ["Intro", "Drop 2", "End"])
    check("instrument skips effects", project["tracks"][0]["instrument"], "Hive")
    check("quoted name", project["tracks"][0]["name"], "Bass")
    check("midi notes", project["tracks"][0]["items"][0]["notes"], [[0, 37, 480, 100], [3840, 38, 480, 80]])
    check("source length", project["tracks"][0]["items"][0]["source_ticks"], 7680)

    facts = rm.analyse(project, "m.RPP")
    check("sections", [(s["name"], s["first_bar"], s["bars"]) for s in facts["sections"]], [("Intro", 1, 2), ("Drop 2", 3, 2)])
    check("empty track left out", [t["name"] for t in facts["tracks"]], ["Bass", "Atlas"])
    intro, drop = facts["sections"]
    check("muted item is ignored", intro["parts"]["Bass"]["clips"], ["Loop"])
    check("no drums in the intro", "Atlas" in intro["parts"], False)
    check("loop plays on", drop["parts"]["Bass"]["notes_per_bar"], 1.0)
    check("D natural is out of C# minor", intro["parts"]["Bass"]["out_of_key"], 1)
    check("roots", intro["parts"]["Bass"]["root_per_bar"], ["C#", "D"])
    check("drum hits", drop["parts"]["Atlas"]["hits_per_bar"], {"kick": 0.5})
    check("bass on the kick", drop["parts"]["Bass"]["onsets_on_kick"], 1)
    check("grid", intro["parts"]["Bass"]["onsets_across_bars"], "x...............")
    check("repeat period", intro["parts"]["Bass"]["repeats_every_bars"], 2)
    check("markdown", "Drop 2: bar 3" in rm.to_markdown(facts), True)

    if failed:
        print("\n".join("FAIL " + f for f in failed))
        sys.exit(1)
    print("ok")


main()
