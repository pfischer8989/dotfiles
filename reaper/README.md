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
  waiting for you and relays approve, comment or deny from inside REAPER. Needs ReaImGui
  and a board key in `~/.empire/reaper-panel.env`
  (`EMPIRE_PANEL_KEY=...`, chmod 600). Timings go to
  `~/.empire/reaper/panel/panel.log`. `empire_panel/test_run.sh create` puts a
  throwaway run on the board to try it on; `remove` deletes it.
  Tests: `lua5.4 empire_panel/test_core.lua` from `Scripts/Empire`.
- **Empire Lane Test**: can a script put MIDI on fixed item lanes? Opens a new
  tab and writes `~/.empire/reaper/lane-test.log`. Close the tab without saving.

The full design (buses, returns, templates, send levels) is in the Empire
repo: `docs/workflows.md`, "REAPER templates".
