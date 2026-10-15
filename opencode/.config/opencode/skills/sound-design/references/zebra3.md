# Zebra 3

u-he's modular flagship: oscillators, filters, resonators and effects that a
preset wires together on a grid. 1,216 factory presets in
`/Library/Audio/Presets/u-he/Zebra3/` (folders `01 Atmospheres`,
`02 Basses & Drones`, ... `15 FX`, `Templates`). Every preset lists all 161
possible modules and 2,718 parameters, used or not. Catalog name: `Zebra3`.

Facts below come from the factory presets, the user guide (v3.0.0; look
things up with `uhe.py manual Zebra3 <topic>`), or were tested by ear (marked
**tested**). `uhe.py params Zebra3 --module X` prints exact ranges.

## What uhe.py can and can't change

- **Text values load** (**tested**: edited Osc/Env/Filter values were heard,
  with and without the binary block). `uhe.py` keeps the base preset's binary
  block, which holds what the text can't: the grid routing, oscillator
  curves/wavetables, MSEG shapes, mapper tables, modal profiles.
- **Routing is invisible.** Which modules are on the grid, and in what order,
  lives only in the binary block. Every preset has text for Osc1..4, Filter1..6,
  Comb1..4 etc. whether it uses them or not, and editing an unused module does
  nothing. Before changing a module, find evidence the preset uses it:
  1. a factory matrix slot targets it (`show <preset> --module MM1` ...
     `MM32`): the matrix target menu only offers modules on the grid
     (manual p.92), so a `Dest1` naming the module is proof;
  2. the preset's description or Usage names it ("Comb filter processed...");
  3. a template that's known to use it (below).
  Otherwise prefer the always-present parts: the pitch modules (`PG1..4`),
  envelopes, LFOs, the matrix, `GridAmp` lane levels and `MainMix`.
- **Protected** (pointers into the binary block, host or UI state; `pack`
  refuses them): `Grid.*`, `FXGrid.*`, `O?Geo1.*`, `M?Geo1.*`, any `*.Coord`,
  `Modal*.MDFile*`, `MMap*.Stps`, `Noise*.KVsc`, `MPreset.*`, `Scope.*`,
  `PCore.*`, `MIDI.*`, `MPE.*`, `LayMem.*`, `MGraph.*`, `main.*`,
  `Tune.MTunN/MTunT`. You can't change a wavetable, curve, MSEG shape or modal
  profile; choose a base preset that already has the one you want, then move
  *positions* through it (`Osc1.Pos`, `MSEG1.CMorph`, `Modal1.Blend`).

## Templates (clean starting points in `Templates/`)

| template | what it is |
| --- | --- |
| `01 Three Osc Poly` | basic analog poly: two saws and a sub, Filter1. Env1 is the amp envelope and `Filter1.Cut` darkens it (**tested**) |
| `02 Duophony` | Pitch 1 lowest note, Pitch 2 highest, on two oscillator sets (manual p.131) |
| `03 Major Third` | Osc1's curve morph crossfades between two notes: a chord from one oscillator (manual p.129) |
| `04 Windowed Sync` | Osc FX Sync + Window (manual p.129) |
| `05 Simply Modal` | modal resonator, "String" profile in A and "Tube" in B; `Modal1.Blend` gives other plucked strings. Start here for struck or resonant bodies |
| `06 Adder` | additive renderer (manual p.128) |

## Modules (manual pages in brackets)

| module | what it is | key parameters |
| --- | --- | --- |
| `PG1..4` | **pitch generators** [21-25]: key follow, transpose, glide, drift, vibrato for every module that picks a `KeySrc`/`PSrc` (Pitch 1 is the leader; 2-4 follow unless switched) | `Transp` (choice: semitones + 26, so 26 = 0, 14 = -12, 38 = +12, 2 = -24; inferred from the factory spread), `TpFine`, `DftAmt` (calibration amount: 0 none, 50 subtle, 100 exaggerated) + `DftTyp` (manual order Uncalibrate, Hypercalibrate, Destabilize = tape wow; 0/1/2 assumed), `VibDpt`/`VibRate`, `GldAmt`/`GldMde`/`GldTrg`, `ModSrc`/`ModDpt` (fast pitch mod), `PWRng+`/`PWRng-` (bend: same +26 coding, 28 = +2) |
| `Osc1..4` | wavetable/additive oscillators [26-31] | `Pitch` (-48..48 semitones), `Pos` (curve morph = wavetable position 0..100; direct mod `PosSrc`/`PosDpt`), `Vol`, `Pan`, `Voices` (unison 1..16), `Detune` (fine tune at 1 voice, spread above), `Width` (unison stereo), `Render` (0 wavetable, 1 additive), `SpecMod`/`SpecDis`/`SpecNos` (additive spectral modifier, distortion, noise), `PhsRst` |
| `Osc1FX1/FX2` .. `Osc4FX1/FX2` | two effects per oscillator [34-38] | `FX` (type, index into the menu: Curve Filter, Filter, Formant, Sparse, Spectral Focus, Tone Works, DeltaX, Map-o-Matic, Phase Distortion, Scrambler, Symmetry, Sync, Wrap & Zap, Dual Wave, Window, Zoom, Dissociate, Posterize, Spectral Decay, Spectral Noise, Twinkles; order not verified), `Value`/`Depth` + `Source` (mod), `Morph`, `Bypass`. Dissociate at ~20 in FX2 = subtle motion without detuning; Spectral Noise = moving cloud |
| `FMO1..4` | FM oscillators [50-51] | `Ratio`, `FM`, `FB` (feedback), `Vol` |
| `Noise1/2` | noise [52-53] | `Type` (white, pink, crackles, velvet, low bit, digital, static, grey, green; order not verified), `Shape` (0 constant; others are hits/rises/pulses), `F1` (lowpass, or clock for digital types), `F2` (highpass or density), `Vol`, `Width`, `Frq`/`Dense`/`Jit` |
| `Excitr1/2` | exciter for physical models [54] | impulses that excite Comb / Modal |
| `Filter1..4` (voice), `Filter5/6` (FX grid) | filters [55-57] | `Mode` (palette index: 0 is the most common; copy the value from a preset whose filter you like), `Cut` (0..150, semitone steps), `Res`, `Drv` (a model-specific flavour), `KeySrc`/`KeyScl`, `FM1`+`FS1`, `FM2`+`FS2` (two cutoff mods), `filtFM` (audio-rate FM) |
| `Comb1..4` | comb filters / resonators [61-62] | `Mode` (Simple, Complex 4/8, Dissonant, Blown, Reverb: "polyphonic reverb"), `Tune`, `FB` (bipolar; negative = octave down, hollow), `Damp`, `Dist`, `Detn`, `Dry`, `Vol`; **can get very loud** with sustained input |
| `Modal1/2` | modal resonator [64-66] | `Tune`, `Detune`, `HPF`, `Positn` (strike position), `Decay` (max + low `Absorpt` = rings forever), `Absorpt`, `Dispers`, `Normal`, `Blend` (profile A to B), `Density`, `Volume`, `Dry`; **can get very loud** |
| `Env1..4` | ADSR [79] | `Attack`, `Decay`, `Sustain`, `Release`, `Vel` (0 = velocity-independent), `TrigMd`, `TrigSrc`, `Var1Typ`/`Var1Dpt`, `Var2Typ`/`Var2Dpt` (delay, hold, init, overshoot; gain, key scale, stretch) |
| `LFO1..4` | LFOs [84-85] | `Wave` (manual order Sine, Triangle, Saw Up, Saw Down, Sqr Hi-Low, Sqr Low-Hi, Rand Hold, Rand Glide; 0..7 assumed), `Rate` (-5..5, each step halves/doubles), `Timebse` (seconds or synced), `Trig` (free, sync, reset, single, random), `Amp`, `Slew`, `DlyTime`, `Polar` |
| `MSEG1..4` | multi-stage envelopes [80-83] | shapes are binary; `CMorph` (morph between its curves), `TimeBse`, `Attack`/`Loop`/`Release` (speeds, -4..4), `Vel`, `Trigger` |
| `MMap1..4`, `MMath1..4` | mappers and math [86-89] | tables are binary; use as sources |
| `MM1..32` | **the modulation matrix** [91-93], see below | |
| `GridAmp` | the four lanes' levels | `Vol1..4` (lane level), `Pan1..4`, `Mute1..4`; `Amp?Src` is not a matrix source number |
| `GridMix` | lane to FX bus routing | `Send1..3`, `L?Out` |
| `Rev1/2` | reverb [95] | `Algo` (manual p.95 order: classic plate with pre-delay, lush; 0/1 assumed; factory: 1 x939, 0 x277), `Predly`, `Size`, `Decay`, `Damping`, `Diffusn`, `depth` (modulation), `Tone`, `DryWet` |
| `TxVb` | Texture: granular + reverb [96-97] | `GrnSize`, `GrnShpe`, `pos`, `rdSpeed`/`rdSpdFn` (grain pitch), `jitter`, `scatter`, `dir`, `density`, `width`, `Fdbck`, `Size`, `Decay`, `Amount` (to 50 fades in reverb, above fades out grains), `DryWet`, `Trigger` (freeze) |
| `Delay1/2` | stereo delay [98-99] | `tpSync`, `tapL`/`tapR`, `ratio`, `fdbck` (safe to ~94), `colour` (digital, surge, haze), `mod`, `diff` (diffusion: smears toward reverb), `lPass`/`hPass`, `width`, `drywet`, `rMode` (stereo, cross, summed) |
| `ModFX1..4` | chorus / flanger / phaser [101-103] | `effect`, `speed`, `depth`, `ctrDly`, `fdbck`, `nvoic`, `drywet` |
| `MainMix` | output | `VolMain` (median 75), `VolBus1..3` (FX bus returns) |

**Level matching:** keep `MainMix.VolMain` and the `GridAmp.Vol?` lanes near
the base preset's; most factory presets sit at `VolMain` 40..100.

## Modulation

Sources (every `*Src`, `MM*.Source`/`Via`, `Filter*.FS*`, `Osc*FX*.Source`;
`uhe.py` prints the names and `pack` accepts them by name, e.g.
`"MM5.Source": "LFO 2"`):

0 none, 1 ModWhl, 2 PitchW, 3-6 CtrlA-D, 7 KeyFollow, 8 Gate, 9 Trigger,
10 Velocity, 11 Release, 12 Hold Pedal, 13 Pressure, 14 Constant, 15 Random,
16 Alternate, 17 ModNoise, 18-21 LFO 1-4, 22-25 MSEG 1-4, 26-29 Envelope 1-4,
30-33 ModMath 1-4, 34-37 Mapper 1-4, 38-41 Pitch 1-4

A matrix slot `MMn` has `Active` (1 on), `Source`, `Via` + `ViaDpt` (scales
the amount; LFO via ModWhl = vibrato on the wheel), `Dest1` (`Module:Param`,
e.g. `Filter1:Cut`, or `none:assigned`; `pack` also takes `Filter1.Cut`),
`Depth1` (-100..100), and modifiers `Curve1`, `Qntze1`, `Rect1`, `SH1`,
`Slew1`. Pitch depth: 100 = 48 semitones, so 5 semitones = 10.42 (or use
Constant via -48 and depth = semitones x 4, manual p.130). A slot can target
another slot's depth (`MM11:Depth1`).

To add a modulation, use a slot whose `Dest1` is `none:assigned` and set
`Active` 1, `Source`, `Dest1`, `Depth1`. Not yet tested by ear: list it under
"what to listen for" until it is. Point it only at modules the preset uses.

**Performance macros:** factory pads map `CtrlA..D` (the Perform panel
knobs) to several matrix slots each ("CtrlC opens the delay and the
filter"). Do the same and say what each does in the preset's `usage`.

## Drones (24 factory presets in Pads:Drones)

`uhe.py typical Zebra3 --category Pads:Drones` and the presets themselves
agree on:

- **Amp envelope:** `Env1.Attack` 45..70, `Sustain` 100, `Release` 55..80,
  `Vel` 0 (every note the same level).
- **Instability:** `PG1.DftAmt` ~20 (often `DftTyp` 2); unison
  (`Osc?.Voices` 2..16) with small `Detune`; slow LFOs at small depths (2..15)
  on `Osc?.Pos`, `Osc?.Detune`, `Filter1.Cut`, lane pans
  (`GridAmp:Pan?`).
- **Register stacking:** oscillators an octave or two apart
  (`Osc?.Pitch` -12, -24, -48), the low one loudest.
- **Wavetable position off zero** (`Osc?.Pos` 20..90) so there's harmonic
  content to sweep; LFO or MSEG on `Pos` for slow timbre change.
- **Space:** wet effects. `Rev1.DryWet` 40..100, `Decay` 50..90, `Size`
  75..100; Texture `TxVb.DryWet` 60..100 with `Amount` 50..80; `Delay1`
  `drywet` ~50, `fdbck` 40..60. Envelope 2 often a slow second swell
  (attack 40..90) on filter or wavetable.
- **Macros everywhere:** CtrlA..D on reverb/delay amounts, filter, detune,
  noise level.

Starting points by character (`folder/name` for `from`):

| character | presets |
| --- | --- |
| dark, sub, horror | `15 FX/Infrasound Drone` (Osc1 at -48, ring mod, glide), `08 Winds & Strings/Titan` ("try lower notes"), `02 Basses & Drones/Remnant`, `02 Basses & Drones/Vomit Plague` |
| airy, clean, sine | `09 Synth Pads/Shimmering Sines`, `08 Winds & Strings/Heavenly Sine`, `01 Atmospheres/Faraway Chime Bell`, `01 Atmospheres/Remembrance`, `09 Synth Pads/Cloudrift` |
| metallic, digital, resonant | `09 Synth Pads/Hollow Worlds` (comb + ring), `01 Atmospheres/Cold Cypher`, `02 Basses & Drones/Crystal Conflux`, `01 Atmospheres/Elevation`, `01 Atmospheres/Rogue Planet` (FM) |
| evolving, moving | `01 Atmospheres/Celestial Rise`, `01 Atmospheres/Desolate Periphery`, `01 Atmospheres/Seething Causality`, `10 Pulsations/Nightcrawlers` |
| organic, plucked over pad | `01 Atmospheres/Spirited Away` (comb + modal), `01 Atmospheres/Dynasty of Delirium` (exciter + modal + comb) |

## Recipes (directions, not exact values)

- **Slower, longer**: `Env1.Attack` and `Release` up; `Env2` likewise if it
  drives the filter or position.
- **Darker / softer** (**tested** on the template): `Filter1.Cut` down,
  `Res` modest; or a negative `Rev1.Tone`.
- **More motion**: a slow LFO (`Rate` -2..-4) or MSEG on `Osc?.Pos` or
  `Filter1:Cut` at small depth; two LFOs at unrelated rates for non-repeating
  movement; `PG1.DftAmt` up for tape-like wobble.
- **Wider**: unison `Voices` 3..8 with `Detune` a few points and `Width` up;
  LFOs on `GridAmp:Pan?`; ModFX chorus.
- **Bigger space**: raise `Rev1.Size`/`Decay`/`DryWet`, or Texture
  (`TxVb.DryWet`, `Amount`); `Delay1.diff` up turns the delay into a wash.
- **Grit**: `Filter1.Drv`, `Comb?.Dist`, a Wrap & Zap or Scrambler osc FX
  on a preset that has one.
- **Resonant body**: start from `05 Simply Modal` or a comb preset; Modal
  `Decay` up + `Absorpt` down for endless ringing; watch the level.

## Taste (from auditions)

Add what the listener liked or rejected here, with the date and pack.

- 2026-10-14, Zebra 3 test on `01 Three Osc Poly`: the edits read as "more
  mellow and a slower attack" (filter and Env1 heard; Osc1 +12 not
  remarked on).
- 2026-10-14, pack `Zebra3 Study Drones` (8 single-change tests on factory
  drones: LFO wave, drift type and amount, transpose, a new matrix slot,
  unison, wavetable position, reverb off): all sounded very close to their
  base presets, too close to confirm or refute anything. Small moves vanish
  in dense, effect-heavy drones; test with extreme values, and design
  presets with many bold changes.

## Not yet verified

Treat these as guesses and flag them in reports: menu orders for `LFO?.Wave`,
`Noise?.Type`, `Osc?FX?.FX`, `Rev1.Algo`, `Delay1.colour`, `PG?.DftTyp`;
the `PG?.Transp` +26 coding; whether a newly activated matrix slot works;
which `GridAmp` lane a module sits on.
