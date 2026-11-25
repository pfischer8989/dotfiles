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
  - drums: `Atlas Kit` (electronic; the drum part's default), `Superior Drummer
    Kit` (acoustic);
  - bass: `Bass - Hive`, `Bass - Zebra 3`, `Bass - Diva`, `Bass - Pigments`,
    `Bass - Repro-1`;
  - synths: `Synth - Hive`, `Synth - Zebra 3`, `Synth - Diva`, `Synth - Pigments`,
    `Synth - Bazille`, `Synth - Repro-1`, `Synth - Repro-5`,
    `Synth - Zebralette 3`, `Synth - Zebra HZ`, `Synth - SynthMaster 2`;
  - pads: `Pad - Diva`, `Pad - Zebra 3`, `Pad - Pigments`, `Pad - Hive`;
  - drones: `Drone - Zebra 3`, `Drone - Zebra HZ`, `Drone - Pigments`;
  - samplers: `Kontakt 8`, `Komplete Kontrol`. They load empty: Paul loads the
    library, so write for what the brief says it will be (piano, strings,
    choir) and keep to that instrument's real range. A template named after a
    saved instrument (in the Samplers folder, or any other) loads with it.

  Guitar, bass guitar and vocal templates record audio, so a sketch can't play
  them. When the brief wants a guitar part, write it as a MIDI guide on the
  synth template it names (a clean, plain sound), so Paul can learn it or play
  against it, then record the real thing on a guitar track.

  The synths load with their init sound, so prefer the ones the brief names. A
  bass part uses a `Bass -` template, so it lands on the BASS bus, unless the
  brief names another.
- A part that doesn't play in a section has no clips there. A part that does
  has exactly one clip per option.
- A drum part is named `Drums`, or `Drums <something>` when there's more than
  one kit (`Drums Live` on `Superior Drummer Kit` next to `Drums` on `Atlas
  Kit`), and uses General MIDI notes: kick 36, rim 37, snare 38, clap 39,
  closed hat 42, open hat 46, toms 45, 47 and 48, crash 49, ride 51, shaker 70.
  Always write these, whatever the kit: the build moves them to the kit's own
  notes. Atlas has one tom row, so all toms land together; Superior plays them
  as written. With two kits, give them different jobs (one keeps time, the
  other plays fills, toms and cymbals, or takes over in a section) so any pick
  of one works under any pick of the other, and don't stack two kicks.

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

Then it builds the sketch in the REAPER that's open, in a new tab, and waits
for it: `built in REAPER: ...` means Paul can start picking. It never starts
REAPER. `NOT BUILT: <reason>` means the sketch is installed but not built (most
often REAPER isn't open): quote the line in your report so Paul knows to open
REAPER and run Empire Build Sketch himself. It isn't a failure of your stage.
Don't drive REAPER any other way.

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
it and say where to listen. Finding the clash by ear is the part he has trouble with,
so a Mix Analysis run can also make EQ moves for him (see "Fixing a mix"), each in a
plugin of its own that he can bypass, change or delete. Start the session only if the
song has none, or he asks for a new one:

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/mix.py bounce "<song>"
```

Then, every pass, print what's saved and measure it:

```bash
python3 ~/dotfiles/reaper/Scripts/Empire/empire_sketch/mix.py print "<song>"
~/.venvs/reaper-audio/bin/python ~/dotfiles/reaper/Scripts/Empire/empire_sketch/mix_check.py <pass folder> --previous <last pass folder>
```

`mix.py print` names the pass to compare with ("compare with ..."): pass that as
`--previous`, and leave it out if there's none. If `mix.py` says `STILL RUNNING`, run
`mix.py wait`. If it says the session has unsaved changes, or that an older session was
saved after the newest, report that and stop: Paul has to save, or say which session he
mixed in. Don't edit project files yourself; mix_fix.py is the only way you change one. Read `mix-check.md` and
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

## Fixing a mix

You write EQ moves as a list, and `mix_fix.py` puts them into a new copy of the newest
session: on each track you name, one TB Equalizer Pro called "TB Equalizer Pro (Empire
Fix)", after Paul's own plugins, which it never touches. The new session becomes the
newest, so Paul carries on in it, and the one before is kept to compare with. The list
is every move you want, not an addition: applying it again replaces all Empire Fix
instances. On a later pass, start from the last session's `fixes.json` and change only
what his note asks.

```json
{"schema": "empire.mixfix/v1", "fixes": [
  {"id": 1, "track": "Chords", "against": "Lead", "why": "Chords covers Lead by 12.3 dB at 354-1122 Hz in every Hook",
   "hz_range": [354, 1122],
   "bands": [{"type": "bell", "hz": 700, "q": 1.0, "db": 0, "duck": {"key": "Lead", "db": -5}}]},
  {"id": 2, "track": "Bass", "against": "Kick (Atlas Kit)", "why": "peaks at 67 and 70 Hz",
   "bands": [{"type": "bell", "hz": 68, "q": 1.4, "db": 0, "duck": {"key": "Kick (Atlas Kit)", "db": -6}}]},
  {"id": 3, "track": "Chords", "against": "Bass", "why": "Chords covers Bass by 6.8 dB at 177-281 Hz",
   "bands": [{"type": "highpass", "hz": 180, "slope": 12}]}]}
```

- `track` is the track the moves go on, `against` the one they make room for. Name
  them as the check pass's mix-check.json does ("Kick (Atlas Kit)" when two tracks
  share a name). `hz_range` is the clash's range from mix-check, for the report.
- A band is a `bell`, `lowshelf` or `highshelf` (hz, db, q) or a `highpass` or
  `lowpass` (hz, slope 6/12/18/24). Limits: cut to -6 dB, boost to +3, q 0.3-4,
  highpass up to 400 Hz, lowpass from 2 kHz, 6 bands a track, 8 fixes a list. The
  script refuses a list outside them and says what to change.
- `duck` makes the band cut by up to its db (to -9) only while the key track plays in
  that band, through the track's sidechain; between the key's notes the track is whole.
  Prefer it when the two play at different moments (kick and bass, a lead over chords);
  use a plain cut or a high-pass when the masking track never needs that range. Leave
  out `threshold_db`: it's set 12 dB under the key's loud moments. One key per track.
- Move what the numbers show: a sustained note's fundamental doesn't move with EQ, so
  for two parts on the same notes, suggest the note change in the report instead.
- Don't fix more than the clashes you were asked about, or the five you'd report.

Then apply, print and measure the new session against the check pass (apply names it),
and report per fix:

```bash
E=~/dotfiles/reaper/Scripts/Empire/empire_sketch
~/.venvs/reaper-audio/bin/python $E/mix_fix.py apply "<song>" fixes.json
python3 $E/mix.py print "<song>"
~/.venvs/reaper-audio/bin/python $E/mix_check.py <new pass> --previous <check pass>
~/.venvs/reaper-audio/bin/python $E/mix_fix.py report <session folder>/fixes.json <new pass> <check pass>
```

The report says, per fix, how far the protected track stands out from the fixed one in
that band while it plays, before and after (more is better); what the fixed track lost
where the protected one is silent (a duck should lose about nothing, a plain cut loses
its depth); and anything else involving the track that got worse. A fix that comes out
"same" or "worse", or makes something else worse, goes: drop or soften it and apply
again, once. Clash scores barely move for a duck, because the kick still covers the bass,
only by more; go by "stands out". It measures and doesn't hear: say which fixes to A/B
first, and how (bypass the Empire Fix plugin on that track, loop the bars).
