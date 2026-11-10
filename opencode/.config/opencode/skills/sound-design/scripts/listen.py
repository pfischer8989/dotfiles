#!/usr/bin/env python3
"""Listen to presets while designing them: play each one headless, measure
what it does, and flag what a designer would hear as a problem.

    ~/.venvs/audio/bin/python listen.py spec.json --out <dir>            a pack spec (before writing)
    ~/.venvs/audio/bin/python listen.py spec.json --out <dir> --macros   also test Ctrl A-D and MW
    ~/.venvs/audio/bin/python listen.py <pack folder or .h2p files> --out <dir>
    ~/.venvs/audio/bin/python listen.py ... --audio                       also write MP3s to audition

With a spec (the one `uhe.py pack` takes), each preset is built in memory,
nothing is written to the preset library, and each is compared with the base
preset it starts from. Every preset plays the same test: a held chord, one
chord change, then the release (the spec's "listen" block can replace it).

Measured per preset, from the audio:

- **movement**: what changes while the chord is held (brightness, level,
  width, pan, spectral shape), by how much, and how often it repeats;
- **tone**: brightness (spectral centroid), width, low-end share and low-end
  width, level;
- **shape**: attack and release times;
- **vs base**: how far the tone moved from the base preset (dB of spectral
  shape) and whether the movement differs;
- **vs pack**: pairs of presets that sound alike.

Thresholds are rules of thumb tuned on test signals and factory presets, not
taste: a flag means "check this", and the designer still decides.

Pure numpy for the measuring (tested without the plugin); pedalboard plays.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402
import uhe  # noqa: E402

SR = render.SAMPLE_RATE
FRAME = 4096
HOP = 2048                                   # ~43 ms at 48 kHz
SMOOTH_S = 0.5                               # movement is measured on 0.5 s averages
SETTLE_S = 3.0                               # skip the attack before measuring movement
BANDS = (20, 120, 250, 500, 1000, 2000, 4000, 8000, 16000)
LOW_HZ = 120
TONE_BANDS = 24                              # log-spaced bands for comparing tone
# How much a measure must vary over the held chord to count as a movement
# (standard deviation of the 0.5 s averages).
MOVES = {"brightness": 0.06,                 # octaves of spectral centroid
         "level": 0.8,                       # dB
         "width": 0.04,                      # side share of the energy (0..1)
         "pan": 0.8,                         # dB of left-right balance
         "shape": 0.9}                       # dB, mean band change after removing level
CLOSE_TONE_DB = 2.5                          # tone closer than this to the base or a pack mate
REPEAT_CORR = 0.9                            # a held chord that repeats this exactly...
REPEAT_MAX_S = 12.0                          # ...at a period this short loops audibly
LOW_WIDTH_MAX = 0.25                         # side share below 120 Hz: phasey under bass
LOW_SHARE_MIN = 0.05                         # below this there's no low end to judge
LOW_SHARE_MAX = 0.45                         # energy share below 120 Hz for a C3-C4 chord
LEVEL_SPREAD_DB = 3.0                        # from the median of the presets measured
FAST_ATTACK_S = 0.01
ATTACK_WINDOW_S = 0.1
CONTROL_CHANGE_DB = 1.0                      # a macro at 1 vs 0 must move tone or level this much

DEFAULT_TEST = {
    # The brief's test: a minor 9th around C3-C4 held 30 s, one change, then release.
    "bpm": 60, "bars": 10, "tail": 8,
    "notes": [[0, "C3 Eb3 G3 Bb3 D4", 30, 90], [30, "Ab2 C3 Eb3 G3 Bb3", 8, 90]],
}
CONTROLS = {"A": ("macro", "A"), "B": ("macro", "B"), "C": ("macro", "C"),
            "D": ("macro", "D"), "MW": ("cc", 1)}
CONTROL_TEST = {"bpm": 60, "bars": 3, "tail": 0, "notes": [[0, "C3 Eb3 G3 Bb3 D4", 12, 90]]}


class ListenError(Exception):
    pass


# -- measuring -----------------------------------------------------------------
def _frames(x, n=FRAME, hop=HOP):
    import numpy as np
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    count = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    return x[idx] * np.hanning(n)[None, :]


def spectra(audio):
    """Per-frame power spectra of mid, side, left and right (frames x bins)."""
    import numpy as np
    left, right = audio[0], audio[1]
    out = {}
    for name, sig in (("mid", (left + right) / 2), ("side", (left - right) / 2),
                      ("left", left), ("right", right)):
        out[name] = np.abs(np.fft.rfft(_frames(sig), axis=1)) ** 2
    out["freqs"] = np.fft.rfftfreq(FRAME, 1.0 / SR)
    return out


def smooth(series, seconds=SMOOTH_S):
    import numpy as np
    k = max(1, int(round(seconds * SR / HOP)))
    if k == 1 or len(series) < k:
        return np.asarray(series, dtype=float)
    kernel = np.ones(k) / k
    return np.convolve(series, kernel, mode="valid")


def _db(x):
    import numpy as np
    return 10 * np.log10(np.maximum(x, 1e-12))


def period(series) -> Optional[float]:
    """Seconds between repeats of a movement (first strong autocorrelation
    peak), or None when it doesn't repeat within half the window."""
    import numpy as np
    s = np.asarray(series, dtype=float)
    if len(s) < 8:
        return None
    t = np.arange(len(s))
    s = s - np.polyval(np.polyfit(t, s, 1), t)
    if s.std() < 1e-9:
        return None
    ac = np.correlate(s, s, mode="full")[len(s) - 1:]
    ac = ac / ac[0]
    lo = max(2, int(0.4 * SR / HOP))
    hi = len(s) // 2
    for lag in range(lo, hi):
        if ac[lag] > 0.5 and ac[lag] >= ac[lag - 1] and ac[lag] >= ac[lag + 1]:
            return round(lag * HOP / SR, 1)
    return None


def repeat(features) -> Tuple[float, Optional[float]]:
    """How exactly the held sound repeats: (best correlation, its period in
    seconds) over every moving measure together."""
    import numpy as np
    x = np.asarray(features, dtype=float)
    if x.ndim != 2 or x.shape[0] < 8 or x.shape[1] == 0:
        return 0.0, None
    x = (x - x.mean(axis=0)) / np.maximum(x.std(axis=0), 1e-9)
    lo = max(2, int(1.0 * SR / HOP))
    hi = min(int(REPEAT_MAX_S * SR / HOP), x.shape[0] // 2)
    best, best_lag = 0.0, None
    for lag in range(lo, hi + 1):
        a, b = x[:-lag], x[lag:]
        corr = float(np.mean(np.sum(a * b, axis=0) /
                             np.maximum(np.sqrt(np.sum(a * a, axis=0) * np.sum(b * b, axis=0)),
                                        1e-12)))
        if corr > best:
            best, best_lag = corr, lag
    return round(best, 3), (round(best_lag * HOP / SR, 1) if best_lag else None)


def tone_profile(spec, frames) -> "np.ndarray":
    """Mean spectral shape over ``frames`` in log-spaced bands, level removed (dB)."""
    import numpy as np
    freqs = spec["freqs"]
    edges = np.geomspace(40, 16000, TONE_BANDS + 1)
    power = spec["mid"][frames].mean(axis=0) + spec["side"][frames].mean(axis=0)
    bands = np.array([power[(freqs >= a) & (freqs < b)].sum() for a, b in zip(edges, edges[1:])])
    db = _db(bands)
    return db - db.max()


def tone_distance(a, b) -> float:
    """Mean absolute difference of two tone profiles in dB, over bands that
    either sound uses (within 50 dB of its loudest band)."""
    import numpy as np
    used = (a > -50) | (b > -50)
    if not used.any():
        return 0.0
    return round(float(np.mean(np.abs(np.maximum(a, -60) - np.maximum(b, -60))[used])), 2)


def envelope(audio, seconds=0.005):
    """Sample-level RMS envelope (mono)."""
    import numpy as np
    mono = (audio[0] + audio[1]) / 2
    k = max(1, int(seconds * SR))
    c = np.cumsum(np.concatenate([[0.0], mono ** 2]))
    return np.sqrt(np.maximum((c[k:] - c[:-k]) / k, 0))


def measure(audio, hold: Tuple[float, float], off: float) -> dict:
    """Everything about one take. ``hold`` is the held chord (start, end) in
    seconds, ``off`` when the last note ends."""
    import numpy as np
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < 1e-4:
        return {"silent": True}
    spec = spectra(audio)
    freqs = spec["freqs"]
    total = spec["mid"] + spec["side"]
    times = (np.arange(total.shape[0]) * HOP + FRAME / 2) / SR
    start = hold[0] + min(SETTLE_S, max(0.0, (hold[1] - hold[0]) / 3))
    held = (times >= start) & (times + FRAME / (2 * SR) <= hold[1])
    if held.sum() < 8:
        held = (times >= hold[0]) & (times <= hold[1])
    frames = np.where(held)[0]

    # tone over the held chord
    power = total[frames]
    energy = power.sum(axis=1)
    centroid = (power * freqs[None, :]).sum(axis=1) / np.maximum(energy, 1e-12)
    low = freqs < LOW_HZ
    up = freqs >= 250
    mid_up, side_up = spec["mid"][frames][:, up].sum(axis=1), spec["side"][frames][:, up].sum(axis=1)
    width = side_up / np.maximum(mid_up + side_up, 1e-12)
    mid_low, side_low = spec["mid"][frames][:, low].sum(axis=1), spec["side"][frames][:, low].sum(axis=1)
    pan = _db(spec["left"][frames].sum(axis=1)) - _db(spec["right"][frames].sum(axis=1))
    band_db = np.stack([_db(power[:, (freqs >= a) & (freqs < b)].sum(axis=1))
                        for a, b in zip(BANDS, BANDS[1:])], axis=1)
    level_db = _db(energy)

    # movement: 0.5 s averages over the held chord
    series = {
        "brightness": smooth(np.log2(np.maximum(centroid, 20.0))),
        "level": smooth(level_db),
        "width": smooth(width),
        "pan": smooth(pan),
    }
    shape = band_db - level_db[:, None]
    loud_bands = band_db.mean(axis=0) > level_db.mean() - 40
    shape_sm = np.stack([smooth(shape[:, i]) for i in range(shape.shape[1])], axis=1) \
        if loud_bands.any() else np.zeros((len(series["level"]), 0))
    moves = {name: float(np.std(s)) for name, s in series.items()}
    moves["shape"] = float(np.mean(np.std(shape_sm[:, loud_bands], axis=0))) if loud_bands.any() else 0.0
    moving = {k: v for k, v in moves.items() if v >= MOVES[k]}
    periods = {k: period(series[k]) for k in moving if k in series}
    if "shape" in moving:
        i = int(np.argmax(np.std(shape_sm[:, loud_bands], axis=0)))
        periods["shape"] = period(shape_sm[:, loud_bands][:, i])
    together = [series[k] for k in moving if k in series]
    if "shape" in moving:
        together += [shape_sm[:, loud_bands][:, i] for i in range(int(loud_bands.sum()))]
    corr, every = repeat(np.stack(together, axis=1)) if together else (0.0, None)

    # shape: attack from the first note, release after the last
    # A 100 ms RMS rides over the beating between chord tones; a step input
    # reaches 3 dB below its level half a window in, so that much is taken off.
    win = ATTACK_WINDOW_S
    env = envelope(audio, win)
    a0 = int(hold[0] * SR)
    held_level = float(np.median(env[a0:int(hold[1] * SR)] + 1e-12))
    reach = np.where(env[a0:int(hold[1] * SR)] >= held_level * 0.708)[0]   # within 3 dB
    attack = round(max(0.0, float(reach[0]) / SR - win / 2), 3) if len(reach) else float("nan")
    o = min(int(off * SR), len(env) - 1)
    at_off = float(np.mean(env[max(0, o - int(0.05 * SR)):o] + 1e-12))
    gone = np.where(env[o:] < at_off * 0.01)[0]                            # 40 dB down
    release = round(max(0.0, gone[0] / SR - win / 2), 2) if len(gone) else None

    sounding = np.abs(audio).max(axis=0) > 1e-3
    rms = float(np.sqrt(np.mean(audio[:, sounding] ** 2))) if sounding.any() else 0.0
    return {
        "level_db": round(20 * math.log10(max(rms, 1e-12)), 1),
        "peak_db": round(20 * math.log10(peak), 1),
        "brightness_hz": int(round(float(2 ** np.median(np.log2(np.maximum(centroid, 20.0)))))),
        "width": round(float(np.median(width)), 3),
        "low_share": round(float(power[:, low].sum() / max(power.sum(), 1e-12)), 3),
        "low_width": round(float(side_low.sum() / max((mid_low + side_low).sum(), 1e-12)), 3),
        "attack_s": attack,
        "release_s": release,
        "moves": {k: round(v, 3) for k, v in moves.items()},
        "moving": sorted(moving),
        "periods": periods,
        "repeat": {"corr": corr, "every_s": every},
        "_tone": tone_profile(spec, frames).tolist(),
    }


def describe_movement(m: dict) -> str:
    """'brightness ±0.21 oct /7.5 s; width ±0.08 (irregular)'."""
    if m.get("silent"):
        return "silent"
    units = {"brightness": " oct", "level": " dB", "width": "", "pan": " dB", "shape": " dB"}
    parts = []
    for k in m["moving"]:
        p = m["periods"].get(k)
        parts.append(f"{k} ±{m['moves'][k]:g}{units[k]} " + (f"/{p:g} s" if p else "(irregular)"))
    return "; ".join(parts) or "static"


def flags(m: dict, base: Optional[dict] = None, tail_s: float = 0.0) -> List[str]:
    """What to check in one preset (empty when nothing stands out)."""
    if m.get("silent"):
        return ["silent: plays nothing for the test chord (register, velocity, or a gate)"]
    out = []
    if not m["moving"]:
        out.append("static: nothing moves while the chord is held")
    elif len(m["moving"]) < 2 or (len(m["moving"]) == 2 and set(m["moving"]) == {"brightness", "shape"}):
        out.append(f"one movement only ({', '.join(m['moving'])}); the brief asks for two independent ones")
    corr, every = m["repeat"]["corr"], m["repeat"]["every_s"]
    if m["moving"] and every and corr >= REPEAT_CORR:
        out.append(f"loops: the held chord repeats every {every:g} s (corr {corr:.2f})")
    if m["low_width"] > LOW_WIDTH_MAX and m["low_share"] >= LOW_SHARE_MIN:
        out.append(f"wide low end: {m['low_width']:.2f} of the energy below {LOW_HZ} Hz is side "
                   "(not mono-compatible)")
    if m["low_share"] > LOW_SHARE_MAX:
        out.append(f"heavy low end: {m['low_share']:.0%} of the energy is below {LOW_HZ} Hz")
    if isinstance(m["attack_s"], float) and not math.isnan(m["attack_s"]) and m["attack_s"] < FAST_ATTACK_S:
        out.append(f"instant attack ({m['attack_s'] * 1000:.0f} ms)")
    if m["release_s"] is None and tail_s:
        out.append(f"release longer than the {tail_s:g} s tail (or a drone that never stops)")
    if m["peak_db"] > -0.5:
        out.append(f"hot: peaks at {m['peak_db']:g} dBFS")
    if base and not base.get("silent"):
        d = tone_distance(_arr(m["_tone"]), _arr(base["_tone"]))
        same_moves = set(m["moving"]) == set(base["moving"]) and all(
            abs(m["moves"][k] - base["moves"][k]) < MOVES[k] for k in m["moving"])
        if d < CLOSE_TONE_DB and same_moves:
            out.append(f"close to its base: tone {d:g} dB away and the same movement")
        elif d < CLOSE_TONE_DB:
            out.append(f"tone close to its base ({d:g} dB); only the movement changed")
    return out


def _arr(x):
    import numpy as np
    return np.asarray(x, dtype=float)


def pack_flags(results: List[dict]) -> List[str]:
    """Presets that sound alike, and level outliers, across what was measured."""
    import numpy as np
    out = []
    live = [r for r in results if not r["take"].get("silent")]
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            d = tone_distance(_arr(a["take"]["_tone"]), _arr(b["take"]["_tone"]))
            if d < CLOSE_TONE_DB and set(a["take"]["moving"]) == set(b["take"]["moving"]):
                out.append(f"{a['name']} and {b['name']} sound alike (tone {d:g} dB apart, "
                           "same movement)")
    if len(live) >= 3:
        median = float(np.median([r["take"]["level_db"] for r in live]))
        for r in live:
            off = r["take"]["level_db"] - median
            if abs(off) > LEVEL_SPREAD_DB:
                out.append(f"{r['name']} is {off:+.1f} dB from the pack's median level")
    return out


# -- what to play ------------------------------------------------------------
def test_clip(spec: dict, item: Optional[dict] = None) -> dict:
    clip = dict(DEFAULT_TEST)
    clip.update((spec or {}).get("listen") or {})
    clip.update((item or {}).get("listen") or {})
    clip.setdefault("file", "listen")
    clip.setdefault("preset", "listen")
    render.check_clip(clip, 0)
    return clip


def hold_window(clip: dict) -> Tuple[Tuple[float, float], float]:
    """The first chord's (start, end) and when the last note ends, in seconds."""
    spb = 60.0 / clip["bpm"]
    starts = sorted({n[0] for n in clip["notes"]})
    first = starts[0]
    end_first = min(n[0] + n[2] for n in clip["notes"] if n[0] == first)
    nxt = next((s for s in starts if s > first), None)
    stop = min(end_first, nxt) if nxt is not None else end_first
    off = max(n[0] + n[2] for n in clip["notes"])
    return (first * spb, stop * spb), off * spb


def control_take(host, patch: bytes, control: str) -> "np.ndarray":
    kind, which = CONTROLS[control]
    clip = dict(CONTROL_TEST, file="ctl", preset="ctl")
    if kind == "macro":
        clip["macros"] = {which: [[0, 1.0], [1, 1.0]]}
        return host.play(patch, clip)
    return host.play(patch, clip, controllers={which: 127})


def control_effect(m0: dict, m1: dict) -> Tuple[float, float, bool]:
    """(tone change dB, level change dB, movement changed) from 0 to 1."""
    tone = tone_distance(_arr(m0["_tone"]), _arr(m1["_tone"]))
    level = round(m1["level_db"] - m0["level_db"], 1)
    moved = set(m0["moving"]) != set(m1["moving"]) or any(
        abs(m0["moves"][k] - m1["moves"][k]) >= MOVES[k] for k in m0["moves"])
    return tone, level, moved


# -- inputs ------------------------------------------------------------------
def load_targets(args: List[str], synth: str) -> Tuple[dict, List[dict]]:
    """[(name, patch bytes, base patch bytes or None, item)] from a spec or files."""
    if len(args) == 1 and args[0].endswith(".json"):
        spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            plans = uhe.plan_pack(spec, out_dir=Path(tmp), check_exists=False)
        targets = []
        for (path, preset, _), item in zip(plans, spec["presets"]):
            base = preset.base_path
            targets.append({"name": path.stem, "item": item,
                            "patch": render.patch_bytes(path.name, preset.text().encode("latin-1")),
                            "base": base.stem,
                            "base_patch": render.patch_text(base)})
        return spec, targets
    files: List[Path] = []
    for a in args:
        p = Path(a).expanduser()
        if p.is_dir():
            files += sorted(p.glob("*.h2p"))
        elif p.is_file():
            files.append(p)
        else:
            files.append(uhe.resolve(a, synth))
    if not files:
        raise ListenError("no presets to listen to")
    return {"synth": synth}, [{"name": f.stem, "item": {}, "patch": render.patch_text(f),
                               "base": None, "base_patch": None} for f in files]


# -- the run -----------------------------------------------------------------
def listen(args: List[str], out: Path, synth: str = "Zebra3", controls: bool = False,
           audio: bool = False, log=print) -> dict:
    spec, targets = load_targets(args, synth)
    synth = spec.get("synth") or synth
    host = render.Host(synth, log)
    out.mkdir(parents=True, exist_ok=True)
    bases: Dict[str, dict] = {}
    results = []
    for t in targets:
        clip = test_clip(spec, t["item"])
        hold, off = hold_window(clip)
        take_audio = host.play(t["patch"], clip)
        take = measure(take_audio, hold, off)
        base = None
        if t["base_patch"] is not None:
            key = t["base"] + json.dumps(clip, sort_keys=True)
            if key not in bases:
                bases[key] = measure(host.play(t["base_patch"], clip), hold, off)
            base = bases[key]
        r = {"name": t["name"], "base": t["base"], "take": take, "base_take": base,
             "flags": flags(take, base, clip.get("tail", 0))}
        if base and not base.get("silent") and not take.get("silent"):
            r["vs_base_tone_db"] = tone_distance(_arr(take["_tone"]), _arr(base["_tone"]))
        if controls and not take.get("silent"):
            ctl_hold, ctl_off = hold_window(dict(CONTROL_TEST))
            zero = measure(host.play(t["patch"], dict(CONTROL_TEST, file="c", preset="c")),
                           ctl_hold, ctl_off)
            r["controls"] = {}
            for name in CONTROLS:
                one = measure(control_take(host, t["patch"], name), ctl_hold, ctl_off)
                if one.get("silent") or zero.get("silent"):
                    r["controls"][name] = {"silent": True}
                    r["flags"].append(f"{name} at full makes it silent")
                    continue
                tone, level, moved = control_effect(zero, one)
                r["controls"][name] = {"tone_db": tone, "level_db": level, "movement_changed": moved}
                if tone < CONTROL_CHANGE_DB and abs(level) < CONTROL_CHANGE_DB and not moved:
                    label = "MW" if name == "MW" else f"Ctrl {name}"
                    r["flags"].append(f"{label} barely changes the sound (tone {tone:g} dB, "
                                      f"level {level:+g} dB at full)")
        if audio and not take.get("silent"):
            write_mp3(out / f"{safe(t['name'])}.mp3", take_audio)
        results.append(r)
        log(f"{t['name']}: {describe_movement(take)}"
            + (f"  [{len(r['flags'])} flag(s)]" if r["flags"] else ""))
    report = {"synth": synth, "test": test_clip(spec), "presets": results,
              "pack": pack_flags(results)}
    for r in results:
        for k in ("take", "base_take"):
            if r.get(k):
                r[k] = {a: b for a, b in r[k].items() if a != "_tone"}
    (out / "listen.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / "listen.md").write_text(markdown(report), encoding="utf-8")
    return report


def safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_ " else "-" for c in name).strip()


def write_mp3(path: Path, audio) -> None:
    import numpy as np
    from pedalboard.io import AudioFile
    peak = float(np.max(np.abs(audio)))
    gain = min(10 ** (-1 / 20) / peak, 10 ** ((render.TARGET_RMS_DB - 20 * math.log10(
        max(float(np.sqrt(np.mean(audio ** 2))), 1e-9))) / 20))
    with AudioFile(str(path), "w", SR, 2, quality=render.MP3_KBPS) as f:
        f.write((audio * gain).astype(np.float32))


def markdown(report: dict) -> str:
    t = report["test"]
    lines = [f"# Listening: {len(report['presets'])} {report['synth']} presets", "",
             f"Test: {t['notes']} at {t['bpm']} bpm (beats), {t.get('tail', 0)} s tail. "
             "Movement is measured over the held chord.", "",
             "| preset | moves (± per 0.5 s average, repeat period) | bright Hz | width | "
             "low share / width | attack s | release s | level dB | vs base dB |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in report["presets"]:
        m = r["take"]
        if m.get("silent"):
            lines.append(f"| {r['name']} | silent | | | | | | | |")
            continue
        lines.append(
            f"| {r['name']} | {describe_movement(m)} | {m['brightness_hz']} | {m['width']:.2f} | "
            f"{m['low_share']:.2f} / {m['low_width']:.2f} | {m['attack_s']} | "
            f"{m['release_s'] if m['release_s'] is not None else '>tail'} | {m['level_db']} | "
            f"{r.get('vs_base_tone_db', '')} |")
    flagged = [r for r in report["presets"] if r["flags"]]
    lines += ["", "## Flags", ""]
    if not flagged and not report["pack"]:
        lines.append("None.")
    for r in flagged:
        lines.append(f"- **{r['name']}**: " + "; ".join(r["flags"]))
    for f in report["pack"]:
        lines.append(f"- pack: {f}")
    ctl = [r for r in report["presets"] if r.get("controls")]
    if ctl:
        lines += ["", "## Controls (full vs 0: tone dB, level dB, movement)", "",
                  "| preset | " + " | ".join(CONTROLS) + " |",
                  "| --- | " + " | ".join("---" for _ in CONTROLS) + " |"]
        for r in ctl:
            cells = []
            for name in CONTROLS:
                c = r["controls"].get(name, {})
                cells.append("silent" if c.get("silent") else
                             f"{c['tone_db']:g} / {c['level_db']:+g}" + (" / moves" if c["movement_changed"] else ""))
            lines.append(f"| {r['name']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inputs", nargs="+", help="a pack spec.json, or .h2p files / folders / names")
    ap.add_argument("--out", required=True, help="folder for listen.json, listen.md (and MP3s)")
    ap.add_argument("--synth", default="Zebra3", help="for files and names (a spec names its own)")
    ap.add_argument("--macros", action="store_true", help="also test Ctrl A-D and the mod wheel")
    ap.add_argument("--audio", action="store_true", help="also write an MP3 of each test")
    ap.add_argument("--strict", action="store_true", help="exit 1 when anything is flagged")
    a = ap.parse_args(argv)
    try:
        report = listen(a.inputs, Path(a.out), a.synth, controls=a.macros, audio=a.audio)
    except (ListenError, render.SpecError, uhe.UheError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print((Path(a.out) / "listen.md").read_text(encoding="utf-8"))
    flagged = report["pack"] or any(r["flags"] for r in report["presets"])
    return 1 if a.strict and flagged else 0


if __name__ == "__main__":
    sys.exit(main())
