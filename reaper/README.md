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

The full design (buses, returns, templates, send levels) is in the Empire
repo: `docs/workflows.md`, "REAPER templates".
