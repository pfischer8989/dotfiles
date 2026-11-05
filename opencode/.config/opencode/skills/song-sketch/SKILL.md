---
name: song-sketch
description: Use when writing a song sketch for Paul's REAPER idea board on Romulus, or analysing a master built from one. Covers the empire.sketch/v1 file, the rules for writing options worth choosing between, checking and installing the sketch with check_sketch.py, and reading a master with read_master.py.
---

# Song sketches

A sketch is a batch of short MIDI loops: for each song section, each part that
plays in it gets three options. Paul auditions them in REAPER on lanes, clicks
what he likes, and builds a master from his picks. Your job is to give him
options that are real musical ideas. MIDI only: the sounds are his.

Scripts are in `~/dotfiles/reaper/Scripts/Empire/empire_sketch/`. Romulus has
Python 3.9 and no third-party music libraries are needed.

## The file

Write a Python script that generates the file, so a later pass can change one
thing and keep the rest. Keep the script with your artifacts.

```json
{
  "schema": "empire.sketch/v1",
  "ppq": 960,
  "loop_bars": 8,
  "options": 3,
  "genre": "...",
  "mood": "...",
  "setup": {
    "schema": "empire.setup/v1",
    "tempo": 138, "time_signature": [4, 4], "key": "C#", "scale": "minor",
    "sections": [{"name": "Intro", "bars": 32}],
    "tracks": ["Atlas Kit", "Synth - Hive"]
  },
  "parts": [{"name": "Drums", "template": "Atlas Kit"}, {"name": "Bass", "template": "Synth - Hive"}],
  "harmony": {"Intro": ["C#m", "C#m", "A", "A", "F#m", "F#m", "G#m", "G#m"]},
  "clips": [
    {"section": "Intro", "part": "Bass", "option": "A", "label": "offbeat roll",
     "notes": [[240, 37, 0, 190, 112]]}
  ]
}
```

- A note is `[start, pitch, channel, length, velocity]`, whole numbers. `start`
  is in ticks from the start of the clip. A bar of 4/4 is 3840 ticks and a
  sixteenth is 240. Notes must fit inside the loop.
- `bars` is the section's length in the song; `loop_bars` is the length of each
  clip, which the master repeats to fill the section. Keep `bars` a multiple of
  `loop_bars`.
- `template` is the REAPER track template for the part. Use the names in the
  brief. Available: `Atlas Kit`, `Synth - Hive`, `Synth - Zebra 3`,
  `Synth - Diva`, `Pad - Diva`.
- A part that doesn't play in a section has no clips there. A part that does
  has exactly one clip per option.
- The drum part must be named `Drums` and use General MIDI notes: kick 36, rim
  37, snare 38, clap 39, closed hat 42, open hat 46, toms 45, 47 and 48, crash
  49, ride 51, shaker 70. Always write these, whatever the kit: the build moves
  them to the kit's own notes. Atlas has one tom row, so all toms land together.

C4 is pitch 60 here: C#2 is 37, about 69 Hz.

## Writing options worth choosing between

These come from analysing the first test sketch, where mixed picks fought each
other. Paul picks each part independently, so **any option of one part has to
work with any option of another.**

1. **One chord sequence per section.** Every option of every part follows that
   section's `harmony`. Options differ in rhythm, voicing and register, never
   in chords. Being in the same key doesn't stop chords clashing.
2. **Labels say what's in the clip.** Paul chooses by them. A label is a few
   plain words about what you actually wrote.
3. **Options differ in idea.** Not the same pattern with a note moved. If he
   can't hear the difference on a quick click, it's a wasted option.
4. **Real melodies.** Write lines with a shape and a place they're going. Don't
   pick notes at random. Give the song a short theme and let it come back in
   different sections and forms.
5. **Keep kick and bass apart.** Bass notes shouldn't start on a kick in any
   combination, unless that's the idea of the genre.
6. **Keep registers apart.** Decide which range each part owns. Two parts
   sitting in the same octaves mask each other.
7. **Sections have to differ when they change.** Going into a bigger section,
   something must change at the bar it arrives. Don't let the section before it
   already use the same bass pattern and arpeggio density.
8. **Fills mean something.** A roll says a change is coming. A loop repeats, so
   a fill in the last bar of the clip plays every time round; in a long section
   that's a false promise. Put big fills only in sections that are one loop
   long, or make them small.
9. **Think about the loop's turnaround.** Clips repeat, so bar 8 has to lead
   back to bar 1 as well as onward.

Stay in the key and scale unless the brief says otherwise. A clip that steps
outside on purpose sets `"outside_key": true`, and your report says so.

## Check and install

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/check_sketch.py sketch.json --install "<song>"
```

It lists every problem and installs nothing until there are none. Read any
warnings and fix the ones you didn't intend. Installing copies the file to
`~/.empire/reaper/sketches/<song>/`, keeps any earlier sketch there under a dated
name, and makes it the one **Empire Build Sketch** opens.

Don't open or drive REAPER yourself: Paul runs the build.

## Reading a master

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/read_master.py <master.RPP> <out folder>
```

It writes `<name>.facts.md` and `.facts.json`: what's in each section, per part
(clips, density, range, roots per bar, rhythm), and per pair of parts how often
they sound a semitone apart, in which bars. It reads the saved project, so hand
edits count if Paul saved them.

**It reads notes only.** You can't hear patches or mix. Don't claim anything
about how the song sounds, and audio tracks are listed as not read. A semitone
rub is a place to listen, not an error: some of the best dark moments are one.
Every number you quote must come from the facts file, and every bar number from
there too.
