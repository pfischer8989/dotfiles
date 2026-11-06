# REAPER (Empire templates)

Lua scripts that build and use the Empire mix templates. On Romulus,
`Scripts/Empire` is a symlink:

```bash
ln -sfn ~/dotfiles/reaper/Scripts/Empire ~/Library/Application\ Support/REAPER/Scripts/Empire
```

- **Empire Build Templates**: writes the "Empire Song" project template and
  the track templates in `TrackTemplates/Empire/`. Rerun after changing the
  design or saving your own chains in `FXChains/Empire/` (`Channel Strip`,
  `Guitar Amp`, `Bus`, `Mix Bus`, or a return's name).
- **Empire Insert Track**: load it into the action list and give it a
  shortcut. Picks a template, moves it into its folder bus, joins the VCA
  group, creates its sends and arms it.
- **Empire Test Templates**: inserts every template into a fresh Empire Song
  and writes `Empire-test.log` in the REAPER resource folder.

- **Empire Panel** (test bed): shows which REAPER runs on the Empire board are
  waiting for you, with the same Accept and Another pass as the dashboard. Needs ReaImGui
  and a board key in `~/.empire/reaper-panel.env`
  (`EMPIRE_PANEL_KEY=...`, chmod 600). Timings go to
  `~/.empire/reaper/panel/panel.log`. `empire_panel/test_run.sh create` puts a
  throwaway run on the board with a test setup and chords to try it on; `setup N`
  and `options N` write them for pass N, `reset` starts over and `remove` deletes it. **Load MIDI**
  puts a pass's options from `~/.empire/reaper/runs/<run>/<stage>/pass-<N>/`
  on a new track, one fixed lane each. **Set up this project** builds a project
  from a stage's `setup.json` (`empire.setup/v1`: tempo, time signature, key,
  scale, sections and tracks) on Empire Song, in a new tab if this one is in use.
  Accepting a setup stage saves what the project holds then to
  `accepted-setup.json` for later stages. REAPER only lets scripts set the MIDI
  editor's key, which is one setting for every editor; the build sets the root and steps to the scale.
  Tests: `lua5.4 empire_panel/test_core.lua` from `Scripts/Empire`.
- **Empire Lane Test**: can a script put MIDI on fixed item lanes? Opens a new
  tab and writes `~/.empire/reaper/lane-test.log`. Close the tab without saving.

- **Empire Build Sketch**: builds an idea board from a sketch file named by
  `~/.empire/reaper/sketches/latest` (`empire.sketch/v1`): one short loop per
  song section in its own region, a track per part, a fixed lane per option.
  **Empire Sketch Next Section** and **Previous Section** move the loop; give
  them shortcuts.
- **Empire Sketch Launcher**: the build starts it. Clicking a clip in a sketch
  plays it for that track and section and mutes the other options there;
  Cmd-clicking layers. It also switches the MIDI editor to named rows with no key
  snap on drum tracks. Run it again to stop it.
- **Drum kits** are in `core.DRUM_KITS`. Sketches write General MIDI drum notes and
  the build moves them to the kit's notes (Atlas: C2 kick, C#2 snare, D2 clap, D#2
  closed hat, E2 open hat, F2 shaker, F#2 tom, G2 other, C3 crash, C#3 ride).
- **Empire Build Master**: makes a master project in a new tab from what's
  playing in the sketch: the unmuted clips looped to full section length, same
  tracks and plugins, with section markers.
- `empire_sketch/goa_test.py` writes a goa psytrance test sketch, and **Empire
  Sketch Test** proves the build and master steps with no plugins.
- `empire_sketch/build_master.py <song>` asks the open REAPER for a master from
  that song's sketch tab, so Accepting the picks in the board can build it.
- `empire_sketch/apply_changes.py <song> <changes.json>` makes a new dated master
  from the newest one with a list of changes (another option, cleared bars, added
  notes) through **Empire Apply Changes**. The old master isn't touched. Another
  pass on a Song Sketch review, with a note saying what to try, uses it.
- **Empire Mix**, through `empire_sketch/mix.py bounce <song>`: prints the newest
  master's tracks after their plugins and fader, into a new `mix-<stamp>.RPP` in its own
  tab. Those tracks play audio at unity; buses, returns, sends, VCAs and the master
  chain stay live, so bus effects can still be changed. The master isn't touched.
  If Atlas plays everything on its main output, as the template does now, the kit
  prints once per drum onto the output tracks, with their plugins bypassed and sends
  muted, to sound like the master. Each drum's notes are muted out, so effects inside
  Atlas are heard per drum.
- `mix.py print <song>` prints the saved session for measuring, into
  `mix-<stamp>/passes/pass-<n>/`. `empire_sketch/mix_check.py <pass> [--previous <pass>]`
  reports where tracks clash: pair, frequencies, bars, who covers whom, and the notes
  in range. It needs numpy: `python3 -m venv ~/.venvs/reaper-audio &&
  ~/.venvs/reaper-audio/bin/pip install numpy`. Tests: `test_mix.py`, `test_mix_check.py`.
- `empire_sketch/check_sketch.py` checks a sketch and installs it for the build;
  `empire_sketch/read_master.py` turns a saved master into facts per section. The
  Song Sketch and Song Analysis workflows use both, through the `song-sketch` skill.
  Tests: `python3 empire_sketch/test_check_sketch.py` and `test_read_master.py`.

The full design (buses, returns, templates, send levels) is in the Empire
repo: `docs/workflows.md`, "REAPER templates".
