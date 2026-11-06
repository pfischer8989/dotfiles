#!/usr/bin/env python3
"""Tests mix_check on made-up audio, where the right answer is known."""

import json
import os
import struct
import tempfile
import unittest

import numpy as np

import mix_check as mc

RATE = 48000
BAR = 2.0
BARS = 16


def write_wav(path, left, right=None):
    right = left if right is None else right
    data = np.stack([left, right], axis=1).astype("<f4").tobytes()
    fmt = struct.pack("<HHIIHH", 3, 2, RATE, RATE * 8, 8, 32)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"data" + struct.pack("<I", len(data)) + data)


def tone(hz, level=0.3, seconds=BARS * BAR):
    t = np.arange(int(seconds * RATE)) / RATE
    return level * np.sin(2 * np.pi * hz * t)


def only_bars(signal, first, last):
    out = np.zeros_like(signal)
    a, b = int((first - 1) * BAR * RATE), int(last * BAR * RATE)
    out[a:b] = signal[a:b]
    return out


def kick(hz, first, last, level=0.6):
    out = np.zeros(int(BARS * BAR * RATE))
    t = np.arange(int(0.25 * RATE)) / RATE
    hit = level * np.sin(2 * np.pi * hz * t) * np.exp(-t * 12)
    for bar in range(first, last + 1):
        for beat in range(4):
            at = int(((bar - 1) * BAR + beat * BAR / 4) * RATE)
            out[at:at + len(hit)] += hit
    return out


def pass_folder(root, name, stems):
    folder = os.path.join(root, name)
    os.makedirs(folder)
    tracks = []
    for track, audio in stems.items():
        path = os.path.join(folder, track.split("/")[0].strip() + ".wav")
        if isinstance(audio, tuple):
            write_wav(path, *audio)
        else:
            write_wav(path, audio)
        tracks.append({"name": track, "file": path, "role": "source", "bus_gain_db": 0})
    with open(os.path.join(folder, "print.json"), "w") as f:
        json.dump({"markers": [{"name": "Verse", "time": 0.0}, {"name": "Hook", "time": 8 * BAR}],
                   "song_end": BARS * BAR, "bars": [i * BAR for i in range(BARS)], "tracks": tracks}, f)
    return folder


def involving(result, a, b):
    return [f for f in result["findings"] if set(f["tracks"]) == {a, b}]


class Clashes(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def test_finds_a_kick_and_bass_clash_only_where_both_play(self):
        folder = pass_folder(self.root, "p", {"Kick 3/4": kick(78, 9, 16), "Bass": only_bars(tone(82.4), 5, 16),
                                              "Lead": tone(2000, 0.1)})
        result = mc.check(folder)
        found = involving(result, "Kick", "Bass")
        self.assertTrue(found)
        top = found[0]
        self.assertLess(top["low_hz"], 82)
        self.assertGreater(top["high_hz"], 78)
        self.assertLessEqual(top["high_hz"], 125)
        bars = [b for r in top["bars"] for b in range(r["bars"][0], r["bars"][1] + 1)]
        self.assertTrue(set(bars) >= set(range(10, 16)), bars)
        self.assertTrue(all(b >= 9 for b in bars), bars)
        self.assertEqual(top["bars"][0]["section"], "Hook")
        self.assertAlmostEqual(top["peaks_hz"]["Bass"], 82.4, delta=4)

    def test_a_kick_with_a_bright_click_still_counts_for_its_body(self):
        click = kick(78, 1, 16)
        for bar in range(16):
            for beat in range(4):
                at = int((bar * BAR + beat * BAR / 4) * RATE)
                click[at:at + 400] += 0.5 * np.sin(2 * np.pi * 8000 * np.arange(400) / RATE)
        folder = pass_folder(self.root, "p", {"Kick": click, "Bass": tone(82.4), "Lead": tone(2000, 0.1)})
        found = involving(mc.check(folder), "Kick", "Bass")
        self.assertTrue(any(f["low_hz"] < 80 < f["high_hz"] for f in found), found)

    def test_short_hits_outrank_a_quiet_overlap_that_runs_longer(self):
        hum = tone(3000, 0.02)
        folder = pass_folder(self.root, "p", {"Kick": kick(78, 1, 16), "Bass": tone(82.4),
                                              "Air 1": hum, "Air 2": tone(3000, 0.02)})
        findings = mc.check(folder)["findings"]
        self.assertEqual(set(findings[0]["tracks"]), {"Kick", "Bass"})

    def test_returns_are_not_reported(self):
        folder = pass_folder(self.root, "p", {"Pad": tone(1000), "Verb": tone(1000, 0.2), "Kick": kick(1000, 1, 16)})
        with open(os.path.join(folder, "print.json")) as f:
            doc = json.load(f)
        doc["tracks"][1]["role"] = "return"
        with open(os.path.join(folder, "print.json"), "w") as f:
            json.dump(doc, f)
        result = mc.check(folder)
        self.assertFalse([f for f in result["findings"] if "Verb" in f["tracks"]])
        self.assertTrue(involving(result, "Pad", "Kick"))

    def test_a_finding_is_narrow_enough_to_act_on(self):
        noise = np.random.default_rng(1).normal(0, 0.1, int(BARS * BAR * RATE))
        other = np.random.default_rng(2).normal(0, 0.1, int(BARS * BAR * RATE))
        folder = pass_folder(self.root, "p", {"Noise 1": noise, "Noise 2": other})
        for f in mc.check(folder)["findings"]:
            self.assertLessEqual(f["high_hz"] / f["low_hz"], 2 ** (6 / 3))

    def test_bars_split_at_sections(self):
        folder = pass_folder(self.root, "p", {"Pad": tone(1000), "Lead": tone(1000)})
        top = mc.check(folder)["findings"][0]
        self.assertEqual([(r["section"], r["bars"]) for r in top["bars"]], [("Verse", [1, 8]), ("Hook", [9, 16])])

    def test_no_clash_when_they_never_play_together(self):
        folder = pass_folder(self.root, "p", {"Kick": kick(78, 1, 8), "Bass": only_bars(tone(82.4), 9, 16)})
        self.assertFalse(involving(mc.check(folder), "Kick", "Bass"))

    def test_no_clash_when_they_sit_apart_in_frequency(self):
        folder = pass_folder(self.root, "p", {"Kick": kick(50, 1, 16), "Bass": tone(400)})
        self.assertFalse(involving(mc.check(folder), "Kick", "Bass"))

    def test_hard_panned_opposite_tracks_do_not_clash(self):
        silent = np.zeros(int(BARS * BAR * RATE))
        folder = pass_folder(self.root, "p", {"Left": (tone(1000), silent), "Right": (silent, tone(1000))})
        self.assertFalse(involving(mc.check(folder), "Left", "Right"))

    def test_says_which_track_covers_the_other(self):
        folder = pass_folder(self.root, "p", {"Pad": tone(1000, 0.5), "Lead": tone(1000, 0.1)})
        top = involving(mc.check(folder), "Pad", "Lead")[0]
        self.assertEqual((top["covering"], top["covered"]), ("Pad", "Lead"))
        self.assertAlmostEqual(top["by_db"], 14, delta=1)

    def test_a_cut_shows_as_better_on_the_next_pass(self):
        first = pass_folder(self.root, "one", {"Kick": kick(78, 1, 16), "Bass": tone(82.4), "Lead": tone(2000, 0.1)})
        before = mc.check(first)
        with open(os.path.join(first, "mix-check.json"), "w") as f:
            json.dump(before, f)
        second = pass_folder(self.root, "two", {"Kick": kick(78, 1, 16), "Bass": tone(200), "Lead": tone(2000, 0.1)})
        after = mc.check(second, first)
        moved = [f for f in after["improved"] if set(f["tracks"]) == {"Kick", "Bass"}]
        self.assertTrue(moved)
        self.assertLess(moved[0]["now"], moved[0]["before"])

    def test_silent_stems_are_named_and_not_measured(self):
        silent = np.zeros(int(BARS * BAR * RATE))
        folder = pass_folder(self.root, "p", {"Snare 5/6": silent, "Kick": kick(78, 1, 16), "Bass": tone(82.4)})
        self.assertEqual(mc.check(folder)["silent"], ["Snare"])


class Pieces(unittest.TestCase):
    def test_bar_ranges_bridge_one_bar_gaps(self):
        self.assertEqual(mc.bar_ranges([3, 4, 5, 7, 11]), [[3, 7], [11, 11]])


if __name__ == "__main__":
    unittest.main()
