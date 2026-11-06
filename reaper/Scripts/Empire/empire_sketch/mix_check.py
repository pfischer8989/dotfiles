#!/usr/bin/env python3
"""Measures a printed mix pass and says where tracks clash: which two tracks, which
frequencies, which bars, and which one covers the other. It measures and doesn't
hear: a clash here is a place to listen, and some of them will be fine.

    mix_check.py <pass folder> [--previous <earlier pass folder>]

Reads print.json and the WAV files that mix.py print wrote. Writes mix-check.json and
mix-check.md into the pass folder. Needs numpy (~/.venvs/reaper-audio).
"""

import json
import os
import re
import struct
import sys

import numpy as np

import read_master as rm

HOP = 1024
LOW_WINDOW, HIGH_WINDOW = 8192, 2048  # long enough to tell 60 Hz from 80 Hz; short enough for the top
SPLIT_HZ = 250
SPECTRUM_TOP_HZ = 400
BANDS_HZ = [1000 * 2 ** (k / 3) for k in range(-15, 13)]  # third octaves, 31 Hz to 16 kHz
FLOOR_DB = -70.0
RANGE_BELOW_SONG_DB = 30.0  # quieter than this next to the song's loud moments doesn't count
OWN_BAND_DB = 15.0  # a band matters to a track within this of its strongest band
EVEN_DB = 2.0  # closer than this and neither track clearly wins
COVER_FROM_DB = -3.0  # a track starts to be covered when the other is this close to it
TAKES_UP_DB = 6.0  # the covering track has at least a quarter of the band's energy
TILT_DB_PER_OCTAVE = 3.0  # music falls with frequency, so compare bands on a level field
MIN_BAR_SECONDS = 0.2
MAX_FINDINGS = 20
SAME_SHARE = 0.15


def read_wav(path):
    """Samples as floats, shape (frames, channels), and the sample rate."""
    with open(path, "rb") as f:
        head = f.read(12)
        if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError(f"{path} isn't a WAV file")
        fmt = None
        while True:
            chunk = f.read(8)
            if len(chunk) < 8:
                raise ValueError(f"{path} has no audio")
            kind, size = chunk[:4], struct.unpack("<I", chunk[4:])[0]
            if kind == b"fmt ":
                body = f.read(size + size % 2)
                tag, channels, rate = struct.unpack("<HHI", body[:8])
                bits = struct.unpack("<H", body[14:16])[0]
                if tag == 0xFFFE:
                    tag = struct.unpack("<H", body[24:26])[0]
                fmt = (tag, channels, rate, bits)
            elif kind == b"data":
                if fmt is None or fmt[0] != 3 or fmt[3] not in (32, 64):
                    raise ValueError(f"{path} isn't floating point WAV")
                data = np.fromfile(f, dtype="<f4" if fmt[3] == 32 else "<f8", count=size * 8 // fmt[3])
                frames = len(data) // fmt[1]
                return data[: frames * fmt[1]].reshape(frames, fmt[1]), fmt[2]
            else:
                f.seek(size + size % 2, 1)


def band_tables(rate):
    def bins(window, low, high):
        step = rate / window
        return max(1, int(np.ceil(low / step))), max(1, int(np.ceil(high / step)))

    out = []
    for hz in BANDS_HZ:
        low, high = hz / 2 ** (1 / 6), hz * 2 ** (1 / 6)
        window = LOW_WINDOW if hz < SPLIT_HZ else HIGH_WINDOW
        out.append((window, *bins(window, low, high)))
    return out


def stft_power(signal, window):
    """Power per frame and FFT bin, a frame every HOP samples centred on that time."""
    shape = np.hanning(window).astype(np.float32)
    scale = 2 / (window * np.sum(shape ** 2))
    padded = np.concatenate([np.zeros(window // 2, np.float32), signal, np.zeros(window, np.float32)])
    frames = len(signal) // HOP + 1
    out = np.zeros((frames, window // 2 + 1), np.float32)
    for first in range(0, frames, 512):
        count = min(512, frames - first)
        stack = np.stack([padded[(first + i) * HOP:(first + i) * HOP + window] for i in range(count)])
        out[first:first + count] = np.abs(np.fft.rfft(stack * shape, axis=1)) ** 2 * scale
    return out


def measure_channel(signal, rate, tables):
    low, high = stft_power(signal, LOW_WINDOW), stft_power(signal, HIGH_WINDOW)
    bands = np.zeros((len(tables), low.shape[0]), np.float32)
    for b, (window, first, stop) in enumerate(tables):
        source = low if window == LOW_WINDOW else high
        bands[b] = source[:, first:stop].sum(axis=1)
    top = int(SPECTRUM_TOP_HZ * LOW_WINDOW / rate) + 2
    return bands, low[:, :top]


def to_db(power):
    return 10 * np.log10(np.maximum(power, 1e-12))


def read_track(entry, tables):
    audio, rate = read_wav(entry["file"])
    gain = 10 ** (entry.get("bus_gain_db", 0) / 20)
    audio = audio.astype(np.float32) * gain
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(audio[:, :2] ** 2))) if audio.size else 0.0
    left, spectrum = measure_channel(audio[:, 0], rate, tables)
    right, spectrum_right = measure_channel(audio[:, 1], rate, tables)
    return {"name": clean_name(entry["name"]), "track": entry["name"], "role": entry.get("role", "source"),
            "bands": np.stack([left, right]), "spectrum": (spectrum + spectrum_right) / 2,
            "peak_db": 20 * np.log10(max(peak, 1e-9)), "rms_db": 20 * np.log10(max(rms, 1e-9))}, rate


def clean_name(name):
    return re.sub(r"\s+\d+/\d+$", "", name)


def tilt_db():
    return np.array([TILT_DB_PER_OCTAVE * np.log2(hz / 1000) for hz in BANDS_HZ], np.float32)[None, :, None]


def clashes(tracks):
    """Per pair and band: a frame mask of the clash, and how much it counts per frame."""
    tilt = tilt_db()
    frames = min(t["bands"].shape[2] for t in tracks)
    powers = np.stack([t["bands"][:, :, :frames] for t in tracks])  # track, channel, band, frame
    levels = to_db(powers)
    mix = to_db(powers.sum(axis=0))
    mix_flat = mix + tilt
    loudest = mix_flat.max(axis=1)  # channel, frame
    reference = float(np.percentile(loudest, 95))
    weight = np.clip((mix_flat - (reference - RANGE_BELOW_SONG_DB)) / RANGE_BELOW_SONG_DB, 0, 1)
    flat = levels + tilt
    own_best = flat.max(axis=2, keepdims=True)
    matters = (flat >= own_best - OWN_BAND_DB) & (levels >= FLOOR_DB)
    takes_up = levels >= mix - TAKES_UP_DB
    results = []
    for a in range(len(tracks)):
        for b in range(a + 1, len(tracks)):
            difference = levels[a] - levels[b]
            a_covers = takes_up[a] & matters[b] & (difference >= COVER_FROM_DB)
            b_covers = takes_up[b] & matters[a] & (-difference >= COVER_FROM_DB)
            flagged = a_covers | b_covers
            if not flagged.any():
                continue
            amount = np.minimum(np.abs(difference), 12) / 12
            score = (flagged * weight * (0.5 + amount)).max(axis=0)  # the worse channel, per band and frame
            mean_difference = to_db(powers[a].mean(axis=0)) - to_db(powers[b].mean(axis=0))
            results.append({"a": a, "b": b, "mask": flagged.any(axis=0), "score": score,
                            "difference": mean_difference})
    return results, frames


def band_edges(first, last):
    return BANDS_HZ[first] / 2 ** (1 / 6), BANDS_HZ[last] * 2 ** (1 / 6)


def group_bands(scores, seconds_per_frame):
    """Runs of neighbouring bands that hold most of a pair's clash."""
    totals = scores.sum(axis=1) * seconds_per_frame
    best = totals.max() if totals.size else 0
    if best < 0.5:
        return []
    keep = totals >= best * 0.25
    groups, b = [], 0
    while b < len(keep):
        if keep[b]:
            stop = b
            while stop + 1 < len(keep) and keep[stop + 1]:
                stop += 1
            groups.append((b, stop, float(totals[b:stop + 1].sum())))
            b = stop
        b += 1
    return groups


def bar_ranges(bars):
    """[3, 4, 5, 9, 11] -> [[3, 5], [9, 11]]: a single bar's gap doesn't split a range."""
    ranges = []
    for bar in bars:
        if ranges and bar - ranges[-1][1] <= 2:
            ranges[-1][1] = bar
        else:
            ranges.append([bar, bar])
    return ranges


def section_at(markers, seconds):
    name = ""
    for m in markers:
        if m["time"] <= seconds + 0.001:
            name = m["name"]
    return name


def peak_hz(spectrum, frames, low, high, rate):
    """Where a track's energy peaks inside a frequency range, over the given frames."""
    average = spectrum[frames].mean(axis=0) if frames.any() else spectrum.mean(axis=0)
    step = rate / LOW_WINDOW
    first, stop = max(1, int(low * 0.8 / step)), min(len(average) - 1, int(high * 1.2 / step) + 1)
    if stop <= first:
        return None
    i = first + int(np.argmax(average[first:stop]))
    a, b, c = np.log(average[i - 1:i + 2] + 1e-12)
    shift = 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c < 0 else 0
    return round(float((i + shift) * step), 1)


def read_notes(master, names):
    """Each track's notes as (start seconds, end seconds, pitch), from the master."""
    if not master or not os.path.exists(master):
        return {}
    project = rm.parse_project(master)
    if not project["tempo"]:
        return {}
    tps = project["tempo"] / 60 * 960
    out = {}
    for track in project["tracks"]:
        if track["name"] in names and not track.get("kit"):
            notes = []
            for item in track["items"]:
                if not item["muted"]:
                    notes += [(n[0] / tps, (n[0] + n[2]) / tps, n[1]) for n in rm.expand(item, tps)]
            out[track["name"]] = notes
    return out


def hz_of(pitch):
    return 440 * 2 ** ((pitch - 69) / 12)


def notes_in_range(notes, frames, low, high, seconds_per_frame):
    """Notes whose fundamental sits in the range, with the seconds they spend in the clash."""
    found = {}
    for start, end, pitch in notes:
        if low <= hz_of(pitch) <= high:
            first, stop = int(start / seconds_per_frame), int(end / seconds_per_frame) + 1
            seconds = float(frames[first:stop].sum()) * seconds_per_frame
            if seconds > 0:
                found[pitch] = found.get(pitch, 0) + seconds
    return [{"note": rm.note_name(p), "hz": round(hz_of(p), 1), "seconds": round(s, 1)}
            for p, s in sorted(found.items(), key=lambda x: -x[1])]


def finding_for(pair, group, tracks, doc, rate, notes):
    seconds_per_frame = HOP / rate
    first, last, score = group
    low, high = band_edges(first, last)
    frames = pair["mask"][first:last + 1].any(axis=0)
    a, b = tracks[pair["a"]], tracks[pair["b"]]
    bar_times = np.array(doc["bars"])
    per_bar = {}
    for frame in np.nonzero(frames)[0]:
        seconds = frame * seconds_per_frame
        if seconds < doc["song_end"]:
            bar = int(np.searchsorted(bar_times, seconds, side="right"))
            per_bar[bar] = per_bar.get(bar, 0) + seconds_per_frame
    bars = sorted(bar for bar, seconds in per_bar.items() if seconds >= MIN_BAR_SECONDS)
    difference = pair["difference"][first:last + 1][:, frames]
    median = float(np.median(difference)) if difference.size else 0.0
    if median >= EVEN_DB:
        covering, covered = a["name"], b["name"]
    elif median <= -EVEN_DB:
        covering, covered = b["name"], a["name"]
    else:
        covering, covered = None, None
    finding = {"tracks": [a["name"], b["name"]], "low_hz": round(low), "high_hz": round(high),
               "score": round(score, 1), "covering": covering, "covered": covered,
               "by_db": round(abs(median), 1), "seconds": round(sum(per_bar.values()), 1),
               "bars": [{"bars": r, "section": section_at(doc["markers"], bar_times[r[0] - 1])}
                        for r in bar_ranges(bars)]}
    if high <= SPECTRUM_TOP_HZ:
        finding["peaks_hz"] = {t["name"]: peak_hz(t["spectrum"][:len(frames)], frames, low, high, rate)
                               for t in (a, b)}
    played = {}
    for t in (a, b):
        if t["track"] in notes:
            found = notes_in_range(notes[t["track"]], frames, low, high, seconds_per_frame)
            if found:
                played[t["name"]] = found
    if played:
        finding["notes"] = played
    return finding


def compare(findings, previous, band_scores):
    """How each finding moved since the last pass, by the same pair and frequencies."""
    earlier = previous.get("band_scores", {})
    for f in findings:
        key = " + ".join(sorted(f["tracks"]))
        bands = [i for i, hz in enumerate(BANDS_HZ) if f["low_hz"] <= hz <= f["high_hz"]]
        before = sum(earlier.get(key, {}).get(str(i), 0) for i in bands)
        now = sum(band_scores.get(key, {}).get(str(i), 0) for i in bands)
        f["before_score"] = round(before, 1)
        f["change"] = change_word(before, now)
    gone = []
    for old in previous.get("findings", []):
        key = " + ".join(sorted(old["tracks"]))
        bands = [i for i, hz in enumerate(BANDS_HZ) if old["low_hz"] <= hz <= old["high_hz"]]
        now = sum(band_scores.get(key, {}).get(str(i), 0) for i in bands)
        if now < old["score"] * (1 - SAME_SHARE):
            gone.append({"tracks": old["tracks"], "low_hz": old["low_hz"], "high_hz": old["high_hz"],
                         "before_score": old["score"], "score": round(now, 1)})
    return gone


def change_word(before, now):
    if before == 0:
        return "new"
    if now > before * (1 + SAME_SHARE):
        return "worse"
    if now < before * (1 - SAME_SHARE):
        return "better"
    return "same"


def check(folder, previous=None):
    with open(os.path.join(folder, "print.json")) as f:
        doc = json.load(f)
    rate, tables, tracks, silent = None, None, [], []
    for entry in doc["tracks"]:
        if tables is None:
            _, rate = read_wav(entry["file"])
            tables = band_tables(rate)
        track, _ = read_track(entry, tables)
        if track["peak_db"] < -90:
            silent.append(track["name"])
        else:
            tracks.append(track)
    if len(tracks) < 2:
        raise ValueError("fewer than two tracks have sound")
    seconds_per_frame = HOP / rate
    pairs, frames = clashes(tracks)
    notes = read_notes(doc.get("master"), {t["track"] for t in tracks})
    findings, band_scores = [], {}
    for pair in pairs:
        key = " + ".join(sorted([tracks[pair["a"]]["name"], tracks[pair["b"]]["name"]]))
        totals = pair["score"].sum(axis=1) * seconds_per_frame
        band_scores[key] = {str(i): round(float(v), 2) for i, v in enumerate(totals) if v > 0}
        for group in group_bands(pair["score"], seconds_per_frame):
            finding = finding_for(pair, group, tracks, doc, rate, notes)
            if finding["bars"]:
                findings.append(finding)
    findings.sort(key=lambda f: -f["score"])
    findings = findings[:MAX_FINDINGS]
    result = {"schema": "empire.mix-check/v1", "session": doc.get("session", ""), "findings": findings,
              "band_scores": band_scores, "silent": silent,
              "tracks": [{"name": t["name"], "role": t["role"], "peak_db": round(t["peak_db"], 1),
                          "rms_db": round(t["rms_db"], 1)} for t in tracks]}
    if doc.get("mix") and os.path.exists(doc["mix"]):
        audio, _ = read_wav(doc["mix"])
        result["mix"] = {"peak_db": round(float(20 * np.log10(max(np.max(np.abs(audio)), 1e-9))), 1),
                         "rms_db": round(float(20 * np.log10(max(np.sqrt(np.mean(audio ** 2)), 1e-9))), 1)}
    if previous:
        with open(os.path.join(previous, "mix-check.json")) as f:
            result["improved"] = compare(findings, json.load(f), band_scores)
        result["compared_with"] = previous
    return result


def describe_who(f):
    if f["covering"]:
        return f"{f['covering']} covers {f['covered']} by about {f['by_db']} dB"
    return "about even"


def describe_bars(f):
    out = []
    for r in f["bars"]:
        span = f"{r['bars'][0]}" if r["bars"][0] == r["bars"][1] else f"{r['bars'][0]}-{r['bars'][1]}"
        out.append(f"{span} ({r['section']})" if r["section"] else span)
    return ", ".join(out)


def write_markdown(result, path):
    lines = ["# Mix check", "",
             "Measured, not heard. Each clash is a place to listen, and some will be fine. Score is a "
             "rough weight of how long and how loud a clash is, for ranking within this report.", ""]
    if result.get("mix"):
        lines += [f"Full mix: peak {result['mix']['peak_db']} dBFS, RMS {result['mix']['rms_db']} dBFS.", ""]
    lines += ["## Clashes, worst first", ""]
    compared = "compared_with" in result
    lines += ["| # | Tracks | Hz | Who | Bars | Peaks | Bass notes in range | Score |" + (" Since last |" if compared else ""),
              "|---|---|---|---|---|---|---|---|" + ("---|" if compared else "")]
    for i, f in enumerate(result["findings"], 1):
        peaks = ", ".join(f"{n} {hz}" for n, hz in f.get("peaks_hz", {}).items() if hz) or "-"
        notes = "; ".join(f"{n}: " + ", ".join(f"{x['note']} {x['hz']} Hz" for x in v[:4])
                          for n, v in f.get("notes", {}).items()) or "-"
        row = (f"| {i} | {f['tracks'][0]} + {f['tracks'][1]} | {f['low_hz']}-{f['high_hz']} | {describe_who(f)} | "
               f"{describe_bars(f)} | {peaks} | {notes} | {f['score']} |")
        lines.append(row + (f" {f['change']} |" if compared else ""))
    if not result["findings"]:
        lines.append("No clashes passed the thresholds.")
    if result.get("improved"):
        lines += ["", "## Improved since last pass", ""]
        for f in result["improved"]:
            lines.append(f"- {f['tracks'][0]} + {f['tracks'][1]}, {f['low_hz']}-{f['high_hz']} Hz: "
                         f"{f['before_score']} to {f['score']}")
    lines += ["", "## Tracks", "", "| Track | Role | Peak dBFS | RMS dBFS |", "|---|---|---|---|"]
    for t in result["tracks"]:
        lines.append(f"| {t['name']} | {t['role']} | {t['peak_db']} | {t['rms_db']} |")
    if result["silent"]:
        lines += ["", "Silent, so not measured: " + ", ".join(result["silent"])]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    args = sys.argv[1:]
    previous = None
    if "--previous" in args:
        i = args.index("--previous")
        previous = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        raise SystemExit(__doc__)
    result = check(args[0], previous)
    with open(os.path.join(args[0], "mix-check.json"), "w") as f:
        json.dump(result, f, indent=1)
    write_markdown(result, os.path.join(args[0], "mix-check.md"))
    print(f"{len(result['findings'])} clashes, written to {args[0]}/mix-check.md")


if __name__ == "__main__":
    main()
