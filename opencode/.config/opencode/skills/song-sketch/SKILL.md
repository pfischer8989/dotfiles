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

## Work in steps

A full sketch is too much to plan in one go: a single long think can use up your
whole allowance and leave nothing written. Save as you go. Write the hook and
chords to a file first, then one part or section at a time, running each piece as
you add it.

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
  brief; several parts can share one. Use the name alone (the build finds the
  folder). Available for MIDI parts:
  - drums: `Atlas Kit` (the drum part's default);
  - bass: `Bass - Hive`, `Bass - Zebra 3`, `Bass - Diva`, `Bass - Pigments`,
    `Bass - Repro-1`;
  - synths: `Synth - Hive`, `Synth - Zebra 3`, `Synth - Diva`, `Synth - Pigments`,
    `Synth - Bazille`, `Synth - Repro-1`, `Synth - Repro-5`, `Synth - JE8086`,
    `Synth - Zebralette 3`, `Synth - Zebra HZ`, `Synth - SynthMaster 2`;
  - pads: `Pad - Diva`, `Pad - Zebra 3`, `Pad - Pigments`, `Pad - Hive`;
  - drones: `Drone - Zebra 3`, `Drone - Zebra HZ`, `Drone - Pigments`.

  The synths load with their init sound, so prefer the ones the brief names. A
  bass part uses a `Bass -` template, so it lands on the BASS bus, unless the
  brief names another.
- A part that doesn't play in a section has no clips there. A part that does
  has exactly one clip per option.
- The drum part must be named `Drums` and use General MIDI notes: kick 36, rim
  37, snare 38, clap 39, closed hat 42, open hat 46, toms 45, 47 and 48, crash
  49, ride 51, shaker 70. Always write these, whatever the kit: the build moves
  them to the kit's own notes. Atlas has one tom row, so all toms land together.

C4 is pitch 60 here: C#2 is 37, about 69 Hz.

## Writing options worth choosing between

These come from the first tests, where mixed picks fought each other and Paul
found the result correct but boring: "not many hooks or interesting parts."
Being interesting is the job. Paul picks each part independently, so **any option
of one part has to work with any option of another.**

1. **One chord sequence per section.** Every option of every part follows that
   section's `harmony`. Options differ in rhythm, voicing and register, never
   in chords. Being in the same key doesn't stop chords clashing. Different
   sections should usually have different sequences: a song with one
   progression throughout has nowhere to go.
2. **Labels say what's in the clip.** Paul chooses by them. A label is a few
   plain words about what you actually wrote.
3. **Options differ in idea.** Not the same pattern with a note moved. If he
   can't hear the difference on a quick click, it's a wasted option. A section
   gets its own clips: reuse a clip elsewhere only when returning to it is the
   point, and the checker refuses a sketch where under 75% of clips are different.
4. **Hooks first.** Before writing anything, write the song's main hook: a phrase
   someone could hum after one listen, with a distinctive rhythm and a shape that
   goes somewhere. A slow note per bar isn't a hook. Build the song around it:
   hint at it early, state it plainly, answer it, change it, and make its last
   return feel earned. Never pick notes at random.
5. **Keep kick and bass out of each other's way.** The checker warns when bass
   notes start on kicks or ring through them. Decide per genre: a rolling goa bass
   has to stop before the kick; a sidechained synthwave bass can sit under it.
   Report what you decided.
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

10. **Give every section a moment.** Something a listener would notice and wait
    for: a drop-out, a rhythm that changes, a line that answers the hook, a new
    register, a chord nobody expected. Note how many bars repeat, and don't let a
    long section be the same 8 bars with nothing new.
11. **Dynamics are notes too.** Use velocity, rests and space. Parts leaving is as
    strong as parts entering. The loudest moment works because of the quiet before.

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

## Building the master

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/build_master.py "<song>"
```

Makes a master from Paul's picks in his open REAPER: a new tab, saved as a dated
`master-*.RPP` in the song's folder. It prints the file and the clip count. If it
fails it says why; REAPER has to be running with the sketch's tab open, so report
that instead of trying to start REAPER. This and `apply_changes.py` are the only
REAPER commands you run.

## Applying changes

When Paul's note asks you to try suggestions, make them as a new master so he can
compare it with the old one:

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/apply_changes.py "<song>" <changes.json>
```

The script's docstring has the file format: `pick` swaps a section's part to
another sketch option, `clear` empties bars, and `add` writes notes. Keep
`changes.json` in your artifacts folder. Work from the newest `master-*.RPP`, and
read its notes before writing new ones, so added parts fit what's there. New notes
follow the same rules as a sketch: stay in key unless the suggestion is the point
of leaving it, and write drums as General MIDI. A suggestion that needs other parts
rewritten for a bar means clearing and writing those parts too.

Run it once per pass; it makes one new dated master, in its own REAPER tab, and
checks the whole list before touching anything. If it says a master has unsaved
changes, report that and stop: Paul has to save it. Don't edit project files
yourself.

Then read the new master with `read_master.py` and check each change landed. In
your report, say for every suggestion whether you applied it as written, adapted
it (how, and why) or skipped it (why), and compare the old and new masters by
section. Suggestions can conflict: choose, and say which you chose.

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

## Checking a mix

A mix session is `mix-<stamp>.RPP` in the song's folder. Paul mixes in it; you measure
it and say where to listen. Paul does the EQ, because finding the clash by ear is the
part he has trouble with. Start the session only if the song has none, or he asks for
a new one:

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/mix.py bounce "<song>"
```

Then, every pass, print what's saved and measure it:

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/mix.py print "<song>"
~/.venvs/reaper-audio/bin/python ~/dotfiles/reaper/Scripts/Empire/empire_sketch/mix_check.py <pass folder> --previous <last pass folder>
```

Leave out `--previous` if there's no earlier pass. If `mix.py` says `STILL RUNNING`, run
`mix.py wait`. If it says the session has unsaved changes, report that and stop: Paul
has to save it. Don't edit project files yourself. Read `mix-check.md` and
`mix-check.json` from the pass folder and copy both into your artifacts folder.

The report ranks every clash it can find, and most of a full arrangement overlaps
somewhere. Your job is to pick what's worth his time:

- Answer his note first, if he named a problem.
- Lead with low-end clashes between the track pairs that carry the song, such as kick
  and bass, even when a longer overlap scores higher. Score only ranks within a report.
- Give about five, each with: the two tracks, the frequencies, the bars by section,
  who covers whom and by how much, and each track's peak and notes in range when
  they're there.
- Say how to hear it: which tracks to solo, which bars to loop.
- Then one line on what he could try, marked as a suggestion, with a reason from the
  numbers: EQ, dynamic EQ, sidechain, or moving a note. EQ changes how loud a frequency
  is, not where a sustained note's fundamental sits.
- On a later pass, start with what got better, worse or stayed the same. Before any
  suggestion, say what a change to the mix did, and don't credit him or the mix with a
  change the numbers don't show.

It measures and doesn't hear. Say so, and never claim how anything sounds. Reverbs and
delays add to the level in the mix, but clashes with them aren't listed. Bus plugins
and bus automation aren't in the track prints: only the bus faders are counted, and
`mix.wav` is the only print through the buses and master.
