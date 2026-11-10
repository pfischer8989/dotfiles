---
name: sound-design
description: Use when designing synth sounds or a preset pack for Paul's u-he synths (Diva, Zebra 3) on Romulus, or rendering audio demos of a pack. Starts from the closest factory presets, writes new presets as intentional variations with uhe.py, measures them with listen.py (it plays each one headless and reports what moves, tone, width, attack and release, and what's too close to its base) before saving them where the synth's preset browser shows them (User > cListen4 > <pack>); render.py writes levelled MP3 demos.
---

# Sound design for u-he synths

u-he presets (`.h2p`) are text files: a metadata header, every parameter by
module and name, then a binary block (routing, wavetables, curves).
`scripts/uhe.py` searches the factory library, shows and compares presets,
and writes new ones: it changes text values, keeps the base preset's binary
block, refuses parameters that point into it, validates every value against
the factory presets' ranges, and writes a whole pack or nothing.

`scripts/listen.py` plays presets in the real plugin (no DAW) and measures
them, so you design with numbers instead of guesses (see "Listen and revise").

Synth guides (read the one for your synth before designing):
`references/diva.md`, `references/zebra3.md` (catalog name `Zebra3`).

Run the script with `python3` (path: this skill's `scripts/uhe.py`). The
catalog of a synth builds itself the first time (under a second).

```bash
uhe.py typical Diva --category Pads:Evolving     # what makes the category sound like itself
uhe.py find Diva warm analog --category Bass     # starting points (words AND category)
uhe.py show "HS Bass Nine" --synth Diva --module VCF1
uhe.py diff "INIT Minipoly" "HS Bass Nine" --synth Diva
uhe.py params Diva --module ENV1                 # ranges and common values
uhe.py pack spec.json --dry-run                  # validate, then without --dry-run to write
uhe.py manual Zebra3 modal resonator             # the user guide's section on a topic
uhe.py manual Zebra3 --grep detune               # every line that mentions a word, with pages
uhe.py manual Zebra3                             # its table of contents
```

`manual` reads `~/.empire/manuals/<Synth>.txt` (made once from the PDF with
`uhe.py manual <Synth> --pdf <guide.pdf>`). Look up a module before you
change it: the guide explains what each parameter does musically.

## Steps

1. **Read the brief.** Settle the synth (Diva unless the brief says
   otherwise), a short pack name, how many presets (default 8), and what each
   one should be, e.g. "dark evolving pad, slow attack, wide". Vary the pack:
   different starting points, characters and registers, not 8 copies of one
   idea.
2. **Ground yourself in the library.** First look for Paul's own starting
   patches: `uhe.py find <Synth> --source template` (they live in
   `<Synth>/cListen4/Templates/`). Their Description says what's on the grid
   and which oscillator, wavetable and MSEG does what; when one suits the
   sound, start from it rather than a factory preset, because its routing
   and waveforms are his, not u-he's. Otherwise, for each category you'll
   use, run `typical`, then `find` 2-3 candidate starting presets per sound
   and `show` or `diff` them. Prefer factory presets (`--source factory`)
   whose oscillator and filter models already suit the sound (see the models
   table in the synth guide). `typical` shows what's normal; a distinctive
   preset often sits away from it on purpose.
3. **Design each preset as a variation** of its starting preset that a
   listener would call a different sound, not a tweak: 8-20 deliberate
   changes, each with a reason ("ENV1.Atk 1 -> 45: slow swell"), spread over
   at least three areas: source (waveform, wavetable position, unison,
   tuning), tone (filter type, cutoff, resonance, drive), shape (envelopes),
   movement (LFO/MSEG rates and depths, matrix amounts, macros) and space
   (effects). Move values far enough to hear: a cutoff from 80 to 74 or a
   depth from 30 to 35 is inaudible on a pad; 80 to 45 is not. Use `params`
   for ranges. Keep `VCA1.Vol` near the base preset's so the
   pack is level-matched. Leave `OPT`, `PCore`, `Scope1` and `CLK` alone.
4. **Write the spec** as `spec.json` in your work directory:

   ```json
   {
     "synth": "Diva",
     "pack": "Night Drive Basses",
     "presets": [
       {
         "name": "ND Rubber Pulse",
         "from": "1 BASS/HS Bass Nine",
         "categories": ["Bass:Analogue"],
         "character": "Dark, Phat, Vintage",
         "features": "Mono, Glide",
         "description": "Round mono bass with a soft pluck; glide on legato notes.",
         "usage": "MW = filter opens",
         "set": {"VCF1.Freq": 58, "ENV2.Dec": 32, "VCC.Porta": 12}
       }
     ]
   }
   ```

   `from` is a preset name or `folder/name` as `find` prints it (or a file
   path). `categories` must be ones the synth already uses (`typical` lists
   them on a typo). `set` keys are `MODULE.Param` exactly as `show` prints
   them. Name presets with a short shared prefix for the pack. Modulation
   sources can be given by name (`"MM3.Source": "LFO 2"`).
5. **Validate**: `uhe.py pack spec.json --dry-run`; fix every error it
   reports (nothing is written while any preset is invalid).
6. **Listen and revise** (below) until each preset's flags are fixed or
   explained, at most three rounds.
7. **Write**: run `uhe.py pack` without `--dry-run`. Presets land in
   `~/Library/Audio/Presets/u-he/<Synth>/cListen4/<pack>/`, with Bank
   `cListen4 <pack>` and Author `cListen4` (a spec's `author` replaces
   cListen4 in all three).
8. **Report** (your report.md): where to find the pack in the synth's
   browser (User > cListen4 > <pack>; reopen the plugin window if it doesn't
   show yet), then a table with each preset's name, what it should sound
   like, its starting preset and the key changes and why. Then the final
   `listen.md` table and any flag you left, with the reason. End with what to
   listen for when auditioning. Attach `spec.json` and `listen.md`.

## Listen and revise

```bash
~/.venvs/audio/bin/python <skill>/scripts/listen.py spec.json --out <work>/listen-1
~/.venvs/audio/bin/python <skill>/scripts/listen.py spec.json --out <work>/listen-2 --macros
~/.venvs/audio/bin/python <skill>/scripts/listen.py "<pack folder>" --out <dir>   # written presets
```

It builds each preset of the spec in memory (nothing is written), plays it
and its base preset in the plugin with the same test (a minor 9th around
C3-C4 held 30 s, one chord change, 8 s of release), and writes `listen.md`
(a table, then flags) and `listen.json`. Loading the plugin takes about a
minute, then each preset a few seconds, so listen to a whole batch at once.
For sounds the chord test doesn't suit (basses, leads, hits), give the spec
a `"listen"` block (or one per preset) in render.py's clip format: `{"bpm":
120, "bars": 4, "tail": 3, "notes": [[0, "A1", 2, 100], ...]}`; the first
note or chord is the "held" part movement is measured over.

What it measures, and what to do with each flag:

- **moves**: what changes while the chord is held (brightness in octaves,
  level and pan in dB, width, spectral shape), how much, and its repeat
  period. `static` or `one movement only`: add an independent modulation
  on another target, at a rate that doesn't divide into the first.
  `loops: repeats every N s`: one LFO dominates; slow it, add a second at
  an unrelated rate, or use a free-running or random source.
- **vs base dB**: how far the tone moved from the base preset (spectral
  shape, level removed). `close to its base`: the preset is a tweak; change
  the source (wavetable position, oscillator mix, unison, pitch layers) and
  the filter, not just effects and envelopes.
- **pack: X and Y sound alike**: change one of them more.
- **wide low end** / **heavy low end**: narrow or cut what's under 120 Hz.
- **instant attack**, **release longer than the tail**, **hot**: as named.
- **level**: presets more than 3 dB from the batch's median; adjust
  `MainMix.VolMain` (Zebra 3) or `VCA1.Vol` (Diva) toward the others.
- `--macros` adds a table of what each of Ctrl A-D and the mod wheel does at
  full: `barely changes the sound` means the control is mapped to nothing
  audible; fix the mapping or its depth.

The thresholds are rules of thumb: a flag means "check this". If a flag is
intended (a deliberately static texture, a drone with an endless release),
keep it and say why in the report. Numbers describe the audio, not taste:
report them, but leave "sounds great" to Paul.

## Rules

- Write only under `<Synth>/cListen4/` (never `<Synth>/Empire/`, the old
  folder). Every preset's Usage names all four macros (`Ctrl A = <name> (...)`).
  The Perform panel knob labels live in the binary block and come from the
  base preset; `uhe.py` can't change them yet. Never modify factory presets or the
  user's own presets; `uhe.py` refuses to overwrite unless `--overwrite`.
- A later pass on the same pack (the reviewer asked for changes): name it
  `<pack> v2`, `v3`, ... so earlier versions stay for comparison, unless the
  brief says to replace them.
- Don't invent parameters or categories; if `uhe.py` rejects a value, fix
  the design rather than forcing it.
- On a modular synth (Zebra 3) only change modules the base preset actually
  uses (the guide says how to tell); an edit to an unused module is silent.
- You can measure but not hear. Use `listen.py`'s numbers for levels,
  movement, attack and release ("level -21.4 dB, 1.2 dB above the batch
  median" is fine); never derive dB, milliseconds or Hz from parameter
  values. What a measurement can't tell you (harshness, whether it's
  beautiful, resonance at notes the test doesn't play), say is for the
  audition ("check C5 and up for a sharp resonance"). Only describe a change
  you actually made (don't call a preset "detuned" unless it is, or say it
  was already).

## Demos

`scripts/render.py` renders presets to MP3 with no DAW: it loads each preset
into the plugin, plays the MIDI phrase you write with the macro knobs
moving, and levels every clip to the same loudness (-18 dBFS RMS, peaks at
most -1 dBFS). Run it with the audio venv, not `python3`:

```bash
~/.venvs/audio/bin/python <skill>/scripts/render.py demos.json --check        # validate
~/.venvs/audio/bin/python <skill>/scripts/render.py demos.json --out <dir>    # render
```

Loading the plugin takes about a minute, then each clip renders in seconds,
so put every clip in one spec.

1. **Choose the presets.** Read the pack's preset list (the `.h2p` files in
   the pack folder; `uhe.py show` for a preset's description and macro
   usage). Pick ones that together show the pack's range: different
   categories and registers, the pack's signature sounds first. A preset the
   brief names is always in.
2. **Write a phrase per preset** that plays it the way a buyer would:
   - bass: a riff in its register (A1-A2), with rests so the envelope shows;
   - lead: a melody with a held note, mid to high register (A3-A5);
   - pad, drone, atmosphere: long chords or one held note, 2-4 changes;
   - stab, brass, keys: rhythmic chords on the beat and off it;
   - drum, hit, percussion: a groove with velocity accents (the same note
     repeated, or a few pitches);
   - riser, FX: one long note across the whole clip.

   Stay in one key across the demos unless the brief says otherwise (A or
   D minor suit most packs). 15-30 s each (`bars` x 4 beats at `bpm`, plus
   `tail` seconds for the release). Move each preset's macros the way its
   Usage describes (A-D, 0-1): a slow sweep across the clip, or a change at
   a section boundary, so the clip shows what the knobs do.
3. **Write the spec** (`demos.json`):

   ```json
   {"synth": "Zebra3", "clips": [
     {"preset": "<path to the .h2p>", "file": "warrig-01-war-brass",
      "bpm": 120, "bars": 8, "tail": 3,
      "notes": [[0, "A2 E3 A3", 4, 100], [4, "F2 C3 F3", 4, 105]],
      "macros": {"A": [[0, 0.1], [32, 0.9]]}}
   ]}
   ```

   `notes` are `[start beat, "note names", length in beats, velocity 1-127]`
   (C4 = middle C); `macros` are `[beat, value]` points. `file` is
   lowercase with dashes and becomes `<file>.mp3` (320 kbps, under Gumroad's
   5 MB limit; `--wav` also writes 24-bit WAVs, only if the brief asks).
4. **Check, render, read the numbers.** `--check` first, then render.
   `render.json` lists each clip's length, RMS, peak and gain. A clip marked
   `peak_limited` came out quieter than the rest (one loud transient):
   soften the velocities or the macro that spikes and render again. A
   `silent` clip means the phrase is outside what the preset plays (wrong
   register, a note too short for a slow attack): fix the phrase.
5. **Report**: a table with each clip's preset, why it's in, what's played
   (key, tempo, the part) and the macro moves; the numbers from
   `render.json`; then what to listen for. You can't hear the clips: describe
   what you wrote, not how it sounds.

