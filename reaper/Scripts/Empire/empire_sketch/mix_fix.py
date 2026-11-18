#!/usr/bin/env python3
"""Empire's EQ moves on a mix: written into a copy of the newest saved mix session, then
measured against the pass they were made from. REAPER has to be running.

    mix_fix.py apply <song> <fixes.json>                      a new session with the moves in
    mix_fix.py report <fixes.json> <pass> <earlier pass>      what each move did

apply copies the newest session to a new mix-<stamp>.RPP, which becomes the newest, and
writes every move in the file into it: on each track it names, one TB Equalizer Pro
called "TB Equalizer Pro (Empire Fix)", after whatever is on the track. The file is the
whole set of Empire's moves, so earlier Empire Fix instances are replaced, not added to.
Paul's own plugins aren't touched. Then `mix.py print` prints the new session and
`mix_check.py` measures it, and report says per fix whether its clash got smaller.

{"schema": "empire.mixfix/v1", "fixes": [
  {"id": 1, "track": "Chords", "against": "Lead", "why": "Chords covers Lead in the Hooks",
   "bands": [{"type": "bell", "hz": 700, "q": 1.2, "db": 0,
              "duck": {"key": "Lead", "db": -5}}]},
  {"id": 2, "track": "Chords", "against": "Bass", "bands": [{"type": "highpass", "hz": 180, "slope": 12}]}]}

Tracks are named as mix_check.py names them ("Kick (Drums Live)" when two share a name).
A band is a bell, lowshelf or highshelf (hz, db, q) or a highpass or lowpass (hz, slope in
dB per octave). A duck makes the band cut by up to its db while the key track plays in
that band, through the track's sidechain; its threshold_db defaults to 12 dB under the
key's loud moments there. All of one track's ducking bands listen to the same key.
"""

import json
import os
import shutil
import sys
import time

import mix
from check_sketch import SKETCHES, slug

SCHEMA = "empire.mixfix/v1"
TYPES = ("bell", "lowshelf", "highshelf", "highpass", "lowpass")
MOST_CUT_DB, MOST_BOOST_DB, MOST_DUCK_DB = -6.0, 3.0, -9.0
Q_RANGE = (0.3, 4.0)
HZ_RANGE = (20.0, 18000.0)
HIGHPASS_UP_TO_HZ, LOWPASS_FROM_HZ = 400.0, 2000.0
SLOPES = (6, 12, 18, 24)
THRESHOLD_RANGE = (-70.0, 0.0)
ATTACK_MS, RELEASE_MS = (1.0, 200.0), (100.0, 900.0)
MOST_BANDS, MOST_FIXES = 6, 8
KEY_BELOW_LOUD_DB = 12.0
SAME_SHARE = 0.15  # as mix_check: a change smaller than this is "same"


class FixError(Exception):
    pass


def load(path):
    with open(path) as f:
        doc = json.load(f)
    if doc.get("schema") != SCHEMA:
        raise FixError(f"{path} isn't {SCHEMA}")
    return doc


def problems(doc, names):
    """Everything wrong with a fix list, so one run can fix them all."""
    out, fixes = [], doc.get("fixes")
    if not isinstance(fixes, list) or not fixes:
        return ["no fixes"]
    if len(fixes) > MOST_FIXES:
        out.append(f"{len(fixes)} fixes; at most {MOST_FIXES}, so pick the ones that matter")
    bands_on, keys_on = {}, {}
    for n, fix in enumerate(fixes, 1):
        where = f"fix {fix.get('id', n)}"
        track = fix.get("track")
        if track not in names:
            out.append(f"{where}: no track {track!r} (tracks: {', '.join(sorted(names))})")
        if fix.get("against") is not None and fix["against"] not in names:
            out.append(f"{where}: no track {fix['against']!r} to be against")
        bands = fix.get("bands") or []
        if not bands:
            out.append(f"{where}: no bands")
        bands_on[track] = bands_on.get(track, 0) + len(bands)
        for b, band in enumerate(bands, 1):
            out += [f"{where} band {b}: {p}" for p in band_problems(band, names, track)]
            if band.get("duck") and band["duck"].get("key") in names:
                keys_on.setdefault(track, set()).add(band["duck"]["key"])
    for track, count in bands_on.items():
        if count > MOST_BANDS:
            out.append(f"{track}: {count} bands; at most {MOST_BANDS} on one track")
    for track, keys in keys_on.items():
        if len(keys) > 1:
            out.append(f"{track}: ducking bands listen to {', '.join(sorted(keys))}; one key per track")
    return out


def band_problems(band, names, track):
    out, kind = [], band.get("type")
    if kind not in TYPES:
        return [f"type {kind!r} isn't one of {', '.join(TYPES)}"]
    hz = band.get("hz")
    if not isinstance(hz, (int, float)) or not HZ_RANGE[0] <= hz <= HZ_RANGE[1]:
        return [f"hz {hz!r} isn't between {HZ_RANGE[0]:g} and {HZ_RANGE[1]:g}"]
    if kind in ("highpass", "lowpass"):
        if band.get("slope", 12) not in SLOPES:
            out.append(f"slope {band.get('slope')!r} isn't one of {SLOPES}")
        if kind == "highpass" and hz > HIGHPASS_UP_TO_HZ:
            out.append(f"a highpass at {hz:g} Hz takes the body out; {HIGHPASS_UP_TO_HZ:g} Hz at most")
        if kind == "lowpass" and hz < LOWPASS_FROM_HZ:
            out.append(f"a lowpass at {hz:g} Hz dulls the track; {LOWPASS_FROM_HZ:g} Hz at least")
        if band.get("duck"):
            out.append("a highpass or lowpass can't duck")
        return out
    db = band.get("db", 0)
    if not isinstance(db, (int, float)) or not MOST_CUT_DB <= db <= MOST_BOOST_DB:
        out.append(f"db {db!r} isn't between {MOST_CUT_DB:g} and +{MOST_BOOST_DB:g}")
    q = band.get("q", 1.0 if kind == "bell" else 0.707)
    if not isinstance(q, (int, float)) or not Q_RANGE[0] <= q <= Q_RANGE[1]:
        out.append(f"q {q!r} isn't between {Q_RANGE[0]:g} and {Q_RANGE[1]:g}")
    duck = band.get("duck")
    if duck is not None:
        key = duck.get("key")
        if key not in names:
            out.append(f"duck key {key!r} isn't a track")
        elif key == track:
            out.append("a track can't duck to itself")
        d = duck.get("db")
        if not isinstance(d, (int, float)) or not MOST_DUCK_DB <= d < 0:
            out.append(f"duck db {d!r} isn't between {MOST_DUCK_DB:g} and 0")
        for field, (low, high) in (("threshold_db", THRESHOLD_RANGE), ("attack_ms", ATTACK_MS),
                                   ("release_ms", RELEASE_MS)):
            v = duck.get(field)
            if v is not None and (not isinstance(v, (int, float)) or not low <= v <= high):
                out.append(f"duck {field} {v!r} isn't between {low:g} and {high:g}")
    return out


def track_refs(print_doc):
    """Track label -> what REAPER needs to find it, from a pass's print.json."""
    from mix_check import labels, track_number
    entries = print_doc["tracks"]
    return {label: {"guid": e.get("guid", ""), "number": track_number(e), "name": e["name"], "file": e["file"],
                    "role": e.get("role", "source")}
            for e, label in zip(entries, labels(entries))}


def key_threshold(path, hz, q):
    """12 dB under the key's loud moments (90th percentile) around hz, in dBFS, so the
    duck is all the way down when the key plays out and lets go between its notes."""
    import numpy as np
    from mix_check import read_wav
    audio, rate = read_wav(path)
    signal = audio[:, :2].mean(axis=1) if audio.shape[1] > 1 else audio[:, 0]
    window = 4096
    shape = np.hanning(window).astype(np.float32)
    scale = 2 / (window * np.sum(shape ** 2))
    half = 2 ** (0.7 / max(q, 0.3))
    freqs = np.fft.rfftfreq(window, 1 / rate)
    keep = (freqs >= hz / half) & (freqs <= hz * half)
    levels = []
    for start in range(0, len(signal) - window, window // 2):
        power = np.abs(np.fft.rfft(signal[start:start + window] * shape)) ** 2 * scale
        levels.append(10 * np.log10(max(float(power[keep].sum()), 1e-12)))
    levels = np.array(levels)
    playing = levels[levels > -80]
    if playing.size == 0:
        raise FixError(f"the key {os.path.basename(path)} has nothing around {hz:g} Hz")
    loud = float(np.percentile(playing, 90))
    return round(max(THRESHOLD_RANGE[0], min(THRESHOLD_RANGE[1], loud - KEY_BELOW_LOUD_DB)), 1)


def request_tracks(doc, refs, threshold=key_threshold):
    """The fixes grouped by track, in order, with each band ready for REAPER."""
    tracks = {}
    for fix in doc["fixes"]:
        ref = refs[fix["track"]]
        entry = tracks.setdefault(fix["track"], {"guid": ref["guid"], "number": ref["number"],
                                                 "name": ref["name"], "label": fix["track"],
                                                 "bands": [], "keys": [], "fixes": []})
        entry["fixes"].append(fix.get("id"))
        for band in fix["bands"]:
            duck = band.get("duck")
            if duck:
                key = refs[duck["key"]]
                if duck.get("threshold_db") is None:  # kept in the list, so the next pass starts from it
                    duck["threshold_db"] = threshold(key["file"], band["hz"], band.get("q", 1.0))
                if not any(k["name"] == key["name"] and k["number"] == key["number"] for k in entry["keys"]):
                    entry["keys"].append({"guid": key["guid"], "number": key["number"], "name": key["name"]})
            entry["bands"].append(json.loads(json.dumps(band)))
    return list(tracks.values())


def apply_request(song, root, fixes_path, now=time.strftime, threshold=key_threshold):
    folder = os.path.join(root, slug(song))
    base = mix.current_session(folder)
    reference = mix.last_pass(base)
    if not reference:
        raise FixError(f"{os.path.basename(base)} has no printed pass to work from. Run `mix.py print` first.")
    with open(os.path.join(reference, "print.json")) as f:
        refs = track_refs(json.load(f))
    doc = load(fixes_path)
    found = problems(doc, set(refs))
    if found:
        raise FixError("the fix list has problems:\n  " + "\n  ".join(found))
    tracks = request_tracks(doc, refs, threshold)
    info = mix.session_info(base)
    new = os.path.join(folder, "mix-" + now("%Y%m%d-%H%M%S") + ".RPP")
    if os.path.exists(new):
        raise FixError(f"{new} already exists; try again in a second")
    shutil.copyfile(base, new)
    os.makedirs(new[: -len(".RPP")])
    with open(os.path.join(new[: -len(".RPP")], "fixes.json"), "w") as f:
        json.dump(doc, f, indent=1)
    with open(os.path.join(new[: -len(".RPP")], "session.json"), "w") as f:
        json.dump({"master": info.get("master"), "from": base, "reference": reference,
                   "fixes": "fixes.json"}, f)
    return {"action": "fix", "base": base, "mix": new, "close_base": bool(info.get("fixes")),
            "tracks": [{k: t[k] for k in ("guid", "number", "name", "bands", "keys")} for t in tracks]}


def discard(request):
    os.remove(request["mix"])
    shutil.rmtree(request["mix"][: -len(".RPP")])


# -- report --------------------------------------------------------------------

def fix_range(fix):
    """The frequencies a fix is about: its own, or worked out from its bands."""
    if fix.get("hz_range"):
        return tuple(fix["hz_range"])
    lows, highs = [], []
    for band in fix["bands"]:
        hz, kind = band["hz"], band["type"]
        if kind == "bell":
            spread = 2 ** (0.7 / band.get("q", 1.0))
            lows.append(hz / spread), highs.append(hz * spread)
        elif kind in ("lowshelf", "highpass"):
            lows.append(HZ_RANGE[0]), highs.append(hz * 1.4)
        else:
            lows.append(hz / 1.4), highs.append(HZ_RANGE[1])
    return min(lows), max(highs)


def pair_score(check, a, b, low, high):
    from mix_check import BANDS_HZ
    scores = check.get("band_scores", {}).get(" + ".join(sorted([a, b])), {})
    return round(sum(scores.get(str(i), 0) for i, hz in enumerate(BANDS_HZ) if low <= hz <= high), 1)


def levels(check):
    return {t["name"]: t["rms_db"] for t in check.get("tracks", [])}


def report(doc, after, before):
    now, then = levels(after), levels(before)
    rows = []
    for fix in doc["fixes"]:
        low, high = fix_range(fix)
        row = {"id": fix.get("id"), "track": fix["track"], "against": fix.get("against"),
               "hz": [round(low), round(high)]}
        if fix.get("against"):
            row["before"] = pair_score(before, fix["track"], fix["against"], low, high)
            row["after"] = pair_score(after, fix["track"], fix["against"], low, high)
            row["result"] = verdict(row["before"], row["after"])
        if fix["track"] in now and fix["track"] in then:
            row["track_rms_change_db"] = round(now[fix["track"]] - then[fix["track"]], 1)
        row["worse_elsewhere"] = [f"{' + '.join(f['tracks'])} {f['low_hz']}-{f['high_hz']} Hz ({f['change']})"
                                  for f in after.get("findings", [])
                                  if fix["track"] in f["tracks"] and f.get("change") in ("worse", "new")
                                  and set(f["tracks"]) != {fix["track"], fix.get("against")}]
        rows.append(row)
    out = {"schema": "empire.mixfix-report/v1", "fixes": rows}
    if after.get("mix") and before.get("mix"):
        out["mix_rms_change_db"] = round(after["mix"]["rms_db"] - before["mix"]["rms_db"], 1)
    return out


def verdict(before, after):
    if before == 0:
        return "no clash to fix" if after == 0 else "worse"
    if after < before * (1 - SAME_SHARE):
        return "better"
    if after > before * (1 + SAME_SHARE):
        return "worse"
    return "same"


def markdown(result):
    lines = ["# What the fixes did", "",
             "Measured, not heard: \"better\" means the clash scores lower, not that it sounds better.", "",
             "| Fix | Track | Against | Hz | Clash before | After | Result | Track level | Worse elsewhere |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in result["fixes"]:
        change = r.get("track_rms_change_db")
        lines.append(f"| {r['id']} | {r['track']} | {r.get('against') or '-'} | {r['hz'][0]}-{r['hz'][1]} | "
                     f"{r.get('before', '-')} | {r.get('after', '-')} | {r.get('result', '-')} | "
                     f"{'-' if change is None else f'{change:+.1f} dB'} | {'; '.join(r['worse_elsewhere']) or '-'} |")
    if "mix_rms_change_db" in result:
        lines += ["", f"Full mix RMS: {result['mix_rms_change_db']:+.1f} dB since the earlier pass."]
    return "\n".join(lines) + "\n"


def main():
    args, root = sys.argv[1:], os.path.expanduser(SKETCHES)
    try:
        if len(args) == 3 and args[0] == "apply":
            request = apply_request(args[1], root, args[2])
            answer = mix.run(request, root)
            if answer is not None and not answer.get("ok"):
                discard(request)
            if answer is None:
                mix.finish(None)
            if not answer.get("ok"):
                print("FAILED: " + answer.get("message", "no reason given"))
                sys.exit(1)
            print(f"session {request['mix']} (made from {os.path.basename(request['base'])})")
            for t in answer["applied"]:
                bands = "; ".join(", ".join(f"{k} {v}" for k, v in b.items()) for b in t["bands"])
                print(f"  {t['name']}: {bands}")
            print(f"Now print it: mix.py print <song>, then mix_check.py <pass> --previous "
                  f"{mix.session_info(request['mix'])['reference']}")
        elif len(args) == 4 and args[0] == "report":
            doc = load(args[1])
            with open(os.path.join(args[2], "mix-check.json")) as f:
                after = json.load(f)
            with open(os.path.join(args[3], "mix-check.json")) as f:
                before = json.load(f)
            result = report(doc, after, before)
            with open(os.path.join(args[2], "fix-report.json"), "w") as f:
                json.dump(result, f, indent=1)
            text = markdown(result)
            with open(os.path.join(args[2], "fix-report.md"), "w") as f:
                f.write(text)
            print(text)
        else:
            raise SystemExit(__doc__)
    except (FixError, mix.MixError) as problem:
        print(f"FAILED: {problem}")
        sys.exit(1)


if __name__ == "__main__":
    main()
