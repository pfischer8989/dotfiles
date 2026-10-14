---
name: sound-design
description: Use when designing synth sounds or a preset pack for Paul's u-he synths (Diva first) on Romulus. Starts from the closest factory presets, writes new presets as intentional variations with uhe.py, and saves them where the synth's preset browser shows them (User > Empire > <pack>).
---

# Sound design for u-he synths

u-he presets (`.h2p`) are text files: a metadata header, then every
parameter by module and name. `scripts/uhe.py` searches the factory library,
shows and compares presets, and writes new ones; it validates every value
against the factory presets' ranges and writes a whole pack or nothing.
Synth guides: `references/diva.md` (read it before designing for Diva).

Run the script with `python3` (path: this skill's `scripts/uhe.py`). The
catalog of a synth builds itself the first time (under a second).

```bash
uhe.py typical Diva --category Pads:Evolving     # what makes the category sound like itself
uhe.py find Diva warm analog --category Bass     # starting points (words AND category)
uhe.py show "HS Bass Nine" --synth Diva --module VCF1
uhe.py diff "INIT Minipoly" "HS Bass Nine" --synth Diva
uhe.py params Diva --module ENV1                 # ranges and common values
uhe.py pack spec.json --dry-run                  # validate, then without --dry-run to write
```

## Steps

1. **Read the brief.** Settle the synth (Diva unless the brief says
   otherwise), a short pack name, how many presets (default 8), and what each
   one should be, e.g. "dark evolving pad, slow attack, wide". Vary the pack:
   different starting points, characters and registers, not 8 copies of one
   idea.
2. **Ground yourself in the library.** For each category you'll use, run
   `typical`. Then `find` 2-3 candidate starting presets per sound and `show`
   or `diff` them. Prefer factory presets (`--source factory`) whose
   oscillator and filter models already suit the sound (see the models table
   in the synth guide).
3. **Design each preset as a variation** of its starting preset: usually
   4-15 deliberate changes, each with a reason ("ENV1.Atk 1 -> 45: slow swell").
   Use `params` for ranges. Keep `VCA1.Vol` near the base preset's so the
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
   them. Name presets with a short shared prefix for the pack.
5. **Validate, then write**: `uhe.py pack spec.json --dry-run`; fix every
   error it reports (nothing is written while any preset is invalid); then
   run it without `--dry-run`. Presets land in
   `~/Library/Audio/Presets/u-he/<Synth>/Empire/<pack>/`.
6. **Report** (your report.md): where to find the pack in the synth's
   browser (User > Empire > <pack>; reopen the plugin window if it doesn't
   show yet), then a table with each preset's name, what it should sound
   like, its starting preset and the key changes and why. End with what to
   listen for when auditioning. Attach `spec.json`.

## Rules

- Write only under `<Synth>/Empire/`. Never modify factory presets or the
  user's own presets; `uhe.py` refuses to overwrite unless `--overwrite`.
- A later pass on the same pack (the reviewer asked for changes): name it
  `<pack> v2`, `v3`, ... so earlier versions stay for comparison, unless the
  brief says to replace them.
- Don't invent parameters or categories; if `uhe.py` rejects a value, fix
  the design rather than forcing it.
- You can't hear the result. Say so where it matters ("the resonance may be
  sharp at high notes; check C5 and up") instead of overclaiming. Never
  state measurements you can't make: no dB levels, milliseconds or Hz
  derived from parameter values ("VCA1.Vol 42-46, close to each other" is
  fine; "matched within 2 dB" is not). Only describe a change you actually
  made (don't call a preset "detuned" unless it is, or say it was already).
