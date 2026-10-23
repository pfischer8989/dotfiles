#!/usr/bin/env python3
"""Render u-he presets to WAV demos: load each preset into the plugin, play a
phrase of MIDI through it with the macro knobs moving, and write a levelled
24-bit WAV per clip.

    ~/.venvs/audio/bin/python render.py demos.json --out <dir>
    ~/.venvs/audio/bin/python render.py demos.json --check    validate only

The plugin runs headless through pedalboard (install once:
`python3 -m venv ~/.venvs/audio && ~/.venvs/audio/bin/pip install pedalboard mido numpy`).
A preset is loaded by writing it into the plugin's VST3 state, which for u-he
plugins is the preset text itself (`#pgm=<file>` then the .h2p body from
`#AM=`). Loading the plugin takes about a minute, so all clips render in one
run.

Spec (see SKILL.md, "Demos"):

    {"synth": "Zebra3", "clips": [
      {"preset": "WR War Brass", "file": "wr-war-brass", "bpm": 120, "bars": 8,
       "notes": [[0, "A2 E3", 4, 100], [4, "C3", 2, 90]],
       "macros": {"A": [[0, 0.1], [24, 0.9]]},
       "tail": 3}]}

`notes` are [start beat, note(s), length in beats, velocity]; `macros` map a
knob (A-D) to [beat, value 0-1] points, interpolated linearly.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uhe  # noqa: E402

SAMPLE_RATE = 48000
BLOCK = 1024                      # samples between macro updates (~21 ms)
TARGET_RMS_DB = -18.0             # every clip is levelled to this loudness...
PEAK_CEILING_DB = -1.0            # ...unless that would push a peak above this
FADE_S = 0.3
MAX_SECONDS = 60.0
MACRO_PARAM = "internal_control_{}"
NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
JUCE_B64 = ".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"


class SpecError(Exception):
    pass


# -- notes and timing -------------------------------------------------------
def midi_note(name: str) -> int:
    """'A2' -> 45 (C4 = 60, as in u-he and most DAWs except Yamaha's)."""
    m = NOTE_RE.match(name.strip())
    if not m:
        raise SpecError(f"not a note name: {name!r} (use e.g. A2, C#3, Bb1)")
    letter, acc, octave = m.groups()
    n = "C D EF G A B".index(letter.upper()) + {"#": 1, "b": -1, "": 0}[acc]
    value = (int(octave) + 1) * 12 + n
    if not 0 <= value <= 127:
        raise SpecError(f"note out of MIDI range: {name}")
    return value


def clip_seconds(clip: dict) -> Tuple[float, float]:
    """(seconds of music, seconds including the tail)."""
    music = clip["bars"] * 4 * 60.0 / clip["bpm"]
    return music, music + float(clip.get("tail", 3))


def check_clip(clip: dict, i: int) -> None:
    where = f"clip {i + 1} ({clip.get('file') or clip.get('preset')})"
    for key in ("preset", "file", "bpm", "bars", "notes"):
        if key not in clip:
            raise SpecError(f"{where}: missing {key!r}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", clip["file"]):
        raise SpecError(f"{where}: file must be lowercase letters, digits and dashes")
    if not 40 <= clip["bpm"] <= 240:
        raise SpecError(f"{where}: bpm {clip['bpm']} outside 40-240")
    beats = clip["bars"] * 4
    if clip_seconds(clip)[1] > MAX_SECONDS:
        raise SpecError(f"{where}: longer than {MAX_SECONDS:.0f} s")
    if not clip["notes"]:
        raise SpecError(f"{where}: no notes")
    for n in clip["notes"]:
        if len(n) != 4:
            raise SpecError(f"{where}: a note is [beat, 'A2 C3', beats, velocity], got {n}")
        start, names, length, vel = n
        for name in str(names).split():
            midi_note(name)
        if start < 0 or length <= 0 or start + length > beats + 1e-9:
            raise SpecError(f"{where}: note {n} is outside the {clip['bars']} bars")
        if not 1 <= vel <= 127:
            raise SpecError(f"{where}: velocity {vel} outside 1-127")
    for knob, points in (clip.get("macros") or {}).items():
        if knob not in "ABCD" or len(knob) != 1:
            raise SpecError(f"{where}: macro {knob!r} is not one of A, B, C, D")
        if not points or any(len(p) != 2 or not 0 <= p[1] <= 1 for p in points):
            raise SpecError(f"{where}: macro {knob} points are [beat, 0-1]")
        if [p[0] for p in points] != sorted(p[0] for p in points):
            raise SpecError(f"{where}: macro {knob} points must be in beat order")


def check_spec(spec: dict) -> None:
    if not spec.get("clips"):
        raise SpecError("no clips")
    files = [c.get("file") for c in spec["clips"]]
    if len(set(files)) != len(files):
        raise SpecError("two clips share a file name")
    for i, clip in enumerate(spec["clips"]):
        check_clip(clip, i)


def midi_events(clip: dict) -> List[Tuple[float, bool, int, int]]:
    """(seconds, is_on, note, velocity), note-offs before note-ons at a tie."""
    spb = 60.0 / clip["bpm"]
    events = []
    for start, names, length, vel in clip["notes"]:
        for name in str(names).split():
            note = midi_note(name)
            events.append((start * spb, True, note, int(vel)))
            events.append(((start + length) * spb, False, note, 0))
    return sorted(events, key=lambda e: (e[0], e[1]))


def macro_value(points: List[List[float]], beat: float) -> float:
    if beat <= points[0][0]:
        return float(points[0][1])
    for (b0, v0), (b1, v1) in zip(points, points[1:]):
        if beat <= b1:
            return float(v0 + (v1 - v0) * (beat - b0) / (b1 - b0)) if b1 > b0 else float(v1)
    return float(points[-1][1])


# -- levels -----------------------------------------------------------------
def db(x: float) -> float:
    return 20 * math.log10(x) if x > 0 else -math.inf


def level_gain(rms: float, peak: float) -> Tuple[float, bool]:
    """Gain that brings the clip to TARGET_RMS_DB without a peak above the
    ceiling; True if the ceiling decided it."""
    want = 10 ** ((TARGET_RMS_DB - db(rms)) / 20)
    limit = 10 ** (PEAK_CEILING_DB / 20) / peak
    return (limit, True) if want > limit else (want, False)


# -- plugin state -----------------------------------------------------------
def juce_b64_encode(data: bytes) -> str:
    """juce::MemoryBlock::toBase64Encoding: '<size>.' then 6-bit chunks, LSB first."""
    nbits = len(data) * 8
    out = []
    for i in range((nbits + 5) // 6):
        val = 0
        for k in range(6):
            bit = i * 6 + k
            if bit < nbits and data[bit >> 3] >> (bit & 7) & 1:
                val |= 1 << k
        out.append(JUCE_B64[val])
    return f"{len(data)}.{''.join(out)}"


def patch_text(preset: Path) -> bytes:
    """The preset as the plugin's state holds it."""
    data = preset.read_bytes()
    start = data.find(b"#AM=")
    if start < 0:
        raise SpecError(f"{preset} is not a u-he preset (no #AM= line)")
    return b"#pgm=" + preset.name.encode("utf-8") + b"\n" + data[start:]


def plugin_state(template: bytes, patch: bytes) -> bytes:
    """The host's VST3 state (``VC2!`` + size + XML) with both the component
    and controller blobs replaced by ``patch``."""
    xml_start = template.index(b"<?xml")
    xml = template[xml_start:].rstrip(b"\x00").decode("utf-8")
    enc = juce_b64_encode(patch)
    for tag in ("IComponent", "IEditController"):
        xml, n = re.subn(rf"<{tag}>.*?</{tag}>", f"<{tag}>{enc}</{tag}>", xml, flags=re.S)
        if n != 1:
            raise SpecError(f"plugin state has no {tag} block")
    body = xml.encode("utf-8")
    return template[:4] + struct.pack("<I", len(body)) + body + b"\x00"


def plugin_path(synth: str) -> Path:
    for root in (Path("/Library/Audio/Plug-Ins/VST3"), Path.home() / "Library/Audio/Plug-Ins/VST3"):
        hits = sorted(root.glob(f"{synth}*.vst3"))
        if hits:
            return hits[0]
    raise SpecError(f"no VST3 plugin for {synth}")


# -- rendering --------------------------------------------------------------
def render(spec: dict, out: Path, log=print) -> List[dict]:
    import numpy as np
    from mido import Message
    from pedalboard import load_plugin
    from pedalboard.io import AudioFile

    synth = spec.get("synth", "Zebra3")
    presets = [uhe.resolve(c["preset"], synth) for c in spec["clips"]]
    log(f"loading {synth} (about a minute)")
    plugin = load_plugin(str(plugin_path(synth)))
    params = plugin.parameters                  # slow to build: once
    template = plugin.raw_state
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for clip, preset in zip(spec["clips"], presets):
        plugin.raw_state = plugin_state(template, patch_text(preset))
        plugin.reset()
        music_s, total_s = clip_seconds(clip)
        n_total = int(total_s * SAMPLE_RATE)
        events = midi_events(clip)
        spb = 60.0 / clip["bpm"]
        macros = {k: v for k, v in (clip.get("macros") or {}).items()}
        chunks, e = [], 0
        for start in range(0, n_total, BLOCK):
            n = min(BLOCK, n_total - start)
            t0, t1 = start / SAMPLE_RATE, (start + n) / SAMPLE_RATE
            for knob, points in macros.items():
                params[MACRO_PARAM.format(knob.lower())].raw_value = macro_value(points, t0 / spb)
            msgs = []
            while e < len(events) and events[e][0] < t1:
                at, on, note, vel = events[e]
                kind = "note_on" if on else "note_off"
                msgs.append(Message(kind, note=note, velocity=vel, time=max(0.0, at - t0)))
                e += 1
            chunks.append(plugin(msgs, duration=n / SAMPLE_RATE, sample_rate=SAMPLE_RATE,
                                 num_channels=2, buffer_size=n, reset=False))
        audio = np.concatenate(chunks, axis=1)[:, :n_total].astype(np.float64)
        if not np.all(np.isfinite(audio)):
            raise SpecError(f"{clip['file']}: the plugin produced NaN or infinite samples")
        peak = float(np.max(np.abs(audio)))
        if peak < 1e-4:
            results.append({"file": clip["file"], "preset": preset.stem, "error": "silent"})
            log(f"{clip['file']}: SILENT, not written")
            continue
        loud = np.abs(audio).max(axis=0) > 1e-3     # ignore silence in the RMS
        rms = float(np.sqrt(np.mean(audio[:, loud] ** 2)))
        gain, capped = level_gain(rms, peak)
        audio *= gain
        fade = int(FADE_S * SAMPLE_RATE)
        audio[:, -fade:] *= np.linspace(1.0, 0.0, fade)
        path = out / f"{clip['file']}.wav"
        with AudioFile(str(path), "w", SAMPLE_RATE, 2, bit_depth=24) as f:
            f.write(audio.astype(np.float32))
        r = {"file": path.name, "preset": preset.stem, "seconds": round(total_s, 2),
             "raw_peak_db": round(db(peak), 1), "peak_db": round(db(peak * gain), 1),
             "rms_db": round(db(rms * gain), 1), "gain_db": round(db(gain), 1),
             "peak_limited": capped, "clipped_before_levelling": peak > 1.0}
        results.append(r)
        log(f"{path.name}: {r['seconds']} s, rms {r['rms_db']} dBFS, peak {r['peak_db']} dBFS"
            + (" (quieter: peak-limited)" if capped else ""))
    (out / "render.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--out", help="folder for the WAVs and render.json")
    ap.add_argument("--check", action="store_true", help="validate the spec and presets only")
    a = ap.parse_args(argv)
    try:
        spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
        check_spec(spec)
        synth = spec.get("synth", "Zebra3")
        for clip in spec["clips"]:
            uhe.resolve(clip["preset"], synth)
        if a.check:
            print(f"ok: {len(spec['clips'])} clips")
            return 0
        if not a.out:
            raise SpecError("--out is required to render")
        results = render(spec, Path(a.out))
    except (SpecError, uhe.UheError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1 if any("error" in r for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
