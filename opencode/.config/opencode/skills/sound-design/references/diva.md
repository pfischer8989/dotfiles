# Diva

u-he's analog modelling synth: a mix-and-match of classic oscillators,
filters and envelopes. 1,432 factory presets in
`/Library/Audio/Presets/u-he/Diva/` (folders `1 BASS` … `8 TEMPLATES`,
`THIRD PARTY/...`). Every preset has the same 28 modules and 344 parameters.

Facts below come from the factory presets (ranges, which template uses which
model) or were tested by ear. `uhe.py params Diva --module X` prints the exact
ranges; trust it over memory.

## Signal flow and modules

```text
OSC (3 oscillators + noise) -> HPF -> VCF1 -> VCA1 -> FX1 -> FX2
         modulation: ENV1 (amp), ENV2 (filter/mod), LFO1, LFO2, MOD (rectify, lag, ...)
```

| module | what it is | key parameters |
| --- | --- | --- |
| `VCC` | voice control | `Mode` (0 poly, most presets; 1 and 2 mono: analogue basses use 1, INIT Minimono uses 2), `Voices`, `Trsp` (semitones: -12 for basses), `Porta` (glide 0..62, usually 0..20), `PB`/`PBD` bend range up/down |
| `OSC` | oscillators | `Model` (below), `Tune1..3` (semitones), `Vol1..3` (levels), `OscMix` (balance on 2-oscillator models), `Shape1..3` (1..9), `PW` + `PWMSrc`/`PWMDpt` (pulse width and its modulation), `Drift` (0..200, analog instability; median 20), `Noise`, `Sync2`, `FM` |
| `HPF` | high-pass filter before the VCF | `Model`, `Freq` (30..150; 30 = fully open, the median) |
| `VCF1` | main low-pass filter | `Model` (below), `Freq` (cutoff 30..150, median 72), `Res` (0..100), `FMSrc`/`FMDpt` (envelope amount; source Env2 in most presets, -120..120), `KeyScl` (key tracking 0..100), `FM2Src`/`FM2Dpt` (second modulation, usually LFO2), `Fback` (feedback, grit) |
| `ENV1` | **amplitude envelope** (tested: its attack swells the volume) | `Atk`, `Dec`, `Sus`, `Rel` (0..100), `Vel` (velocity), `Model` |
| `ENV2` | **filter/modulation envelope** (the default `VCF1.FMSrc`) | same as ENV1 |
| `LFO1`, `LFO2` | LFOs | `Rate` (-5..5), `Wave`, `Sync`, `Dly` (fade-in delay); LFO2 is the usual vibrato/PWM source |
| `VCA1` | output | `Vol` (5..100, most presets 16..62, median 35): keep it near the base preset's so a pack is level-matched; `PanSrc`/`PanDpt` (stereo spread) |
| `main` | effects on/off | `FX1`, `FX2` (0 off, 1 on) |
| `FX1`, `FX2` | effect slot types | `Module`: FX1 `Chorus1`, `Plate1`, `Delay1`, `Phaser1`, `Rotary1`; FX2 the same names ending in 2 |
| `Chrs1/2`, `Plate1/2`, `Delay1/2`, `Phase1/2`, `Rtary1/2` | the effects' settings | chorus `Rate`, `Depth`, `Wet`; plate `Decay`, `Size`, `Damp`, `Pre`, `Wet`/`Dry`; delay `LDel`/`CDel`/`RDel`, `FeedB`, `HP`/`LP`, `Wow` |
| `OPT`, `PCore`, `Scope1`, `CLK` | per-voice drift tables, version, scope, clock | leave alone |

## Models (from the INIT templates in `8 TEMPLATES`)

Each template is named after the classic synth whose parts it combines; a
model number means "the oscillator/filter/envelope from that template".

| template | OSC.Model | VCF1.Model | HPF.Model | ENV Model |
| --- | --- | --- | --- | --- |
| INIT Minipoly / Minimono (Minimoog) | 0 | 0 | 0 | 0 |
| INIT Jupe-8 (Jupiter-8) | 1 | 1 | 2 | 1 |
| INIT Jupe-6 (Jupiter-6) | 1 | 2 | 2 | 2 |
| INIT June-60 (Juno-60) | 2 | 1 | 1 | 1 |
| INIT Alpha (Alpha Juno) | 2 | 2 | 1 | 2 |
| INIT MS-Rev1 / Rev2 (MS-20) | 3 | 3 | 3 | 1 |
| INIT Digi-Uhbie (u-he digital) | 4 | 4 | 1 | 1 |

So `OSC.Model`: 0 Minimoog-style triple VCO, 1 Jupiter dual VCO, 2 Juno/Alpha
DCO, 3 MS-20 dual VCO, 4 digital. `VCF1.Model`: 0 Minimoog ladder, 1 Jupiter-8/
Juno cascade, 2 Jupiter-6/Alpha multimode, 3 MS-20, 4 Uhbie. `ENV*.Model`: 0
Minimoog-style, 1 Jupiter-8/Juno, 2 Jupiter-6/Alpha. Changing a model changes
which other parameters matter (e.g. `OscMix` on 2-oscillator models,
`Vol1..3` and `Shape1..3` on the triple VCO), so change models by starting
from a preset or template that already uses the one you want.

## Modulation sources

`*Src` parameters (and LFO `DMS1`/`FMS1`) pick from this list; `uhe.py`
prints the names:

0 none, 1 ModWhl, 2 PitchW, 3 CtrlA, 4 CtrlB, 5 Gate, 6 Velocity, 7 Pressure,
8 KeyFollow, 9 KeyFollow2, 10 Alternate, 11 Random, 12 StackVoice,
13 VoiceMap, 14 Env1, 15 Env2, 16 LFO1, 17 LFO2, 18 Rectify, 19 Invert,
20 Quant, 21 Lag, 22 Adder, 23 Multiply

## Category signatures (from `uhe.py typical`)

- **Bass:Analogue** (183): mono (`VCC.Mode` 1), `VCC.Trsp` -12, Minimoog
  envelopes (`ENV1/2.Model` 0), shorter release, more `OSC.Vol3`, a little
  `VCF1.Fback`, FX2 delay rather than plate.
- **Pads:Evolving** (101): slow attacks (`ENV1.Atk` ~39, `ENV2.Atk` ~48),
  long release (~50), Jupiter oscillators and cascade filter (`OSC.Model` 1,
  `VCF1.Model` 1).

Run `uhe.py typical Diva --category <cat>` for any of the 87 categories
before designing in it.

## Recipes (directions, not exact values)

- **Darker**: lower `VCF1.Freq`; less `VCF1.FMDpt`; or `VCF1.KeyScl` down.
- **Brighter / more bite**: raise `VCF1.Freq` or `VCF1.FMDpt`; some `VCF1.Res`.
- **Pluckier**: `ENV2` short `Dec`, low `Sus`, with a positive `VCF1.FMDpt`;
  `ENV1` short `Dec`/`Rel` for a percussive amp.
- **Swell / evolving**: raise `ENV1.Atk` and `ENV2.Atk`; slow LFO2 (`Rate`
  below 0) on `VCF1.FM2Src`/`FM2Dpt` or `OSC.PWMDpt`.
- **Wider / lusher**: chorus on (`main.FX1` 1, `FX1.Module` `Chorus1`); a
  little detune via `OSC.Tune2`; `VCA1.PanSrc` LFO2 or VoiceMap with
  `PanDpt`.
- **Vintage / unstable**: raise `OSC.Drift` (median 20, up to ~40 is common).
- **Glide**: `VCC.Porta` 5..20 on a mono preset.
