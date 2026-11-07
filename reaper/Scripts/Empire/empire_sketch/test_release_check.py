#!/usr/bin/env python3
"""Tests release_check on made-up audio, where the right answer is known."""

import os
import struct
import tempfile
import unittest

import numpy as np

import release_check as rc

RATE = 44100


def sine(freq, seconds, peak, phase=0.0):
    t = np.arange(int(seconds * RATE)) / RATE
    return peak * np.sin(2 * np.pi * freq * t + phase)


def stereo(left, right=None):
    return np.stack([left, left if right is None else right], axis=1)


def write_wav(path, samples, bits=24, rate=RATE, code=1):
    frames = np.asarray(samples)
    if code == 3:
        data = frames.astype("<f4").tobytes()
    elif bits == 16:
        data = np.round(frames * 32767).astype("<i2").tobytes()
    else:
        ints = np.round(frames * 8388607).astype(np.int32).reshape(-1)
        data = np.stack([ints & 255, ints >> 8 & 255, ints >> 16 & 255], axis=1).astype(np.uint8).tobytes()
    channels = frames.shape[1]
    align = channels * bits // 8
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE")
        f.write(b"LIST" + struct.pack("<I", 4) + b"INFO")  # a chunk to skip
        f.write(b"fmt " + struct.pack("<IHHIIHH", 16, code, channels, rate, rate * align, align, bits))
        f.write(b"data" + struct.pack("<I", len(data)) + data)


class Loudness(unittest.TestCase):
    def test_full_scale_sine_in_one_channel(self):
        # BS.1770's own reference: 997 Hz at 0 dBFS in one channel reads -3.01.
        silent = np.zeros(int(RATE * 5))
        got = rc.integrated_lufs(stereo(sine(997, 5, 1.0), silent), RATE)
        self.assertAlmostEqual(got, -3.01, delta=0.1)

    def test_twenty_down_in_both_channels(self):
        got = rc.integrated_lufs(stereo(sine(997, 5, 0.1)), RATE)
        self.assertAlmostEqual(got, -20.0, delta=0.1)

    def test_gating_ignores_silence(self):
        tone = sine(997, 5, 0.1)
        got = rc.integrated_lufs(stereo(np.concatenate([tone, np.zeros(RATE * 20)])), RATE)
        self.assertAlmostEqual(got, -20.0, delta=0.15)

    def test_silence_has_no_loudness(self):
        self.assertIsNone(rc.integrated_lufs(np.zeros((RATE * 2, 2)), RATE))

    def test_k_weighting_cuts_low_end(self):
        low = rc.integrated_lufs(stereo(sine(30, 5, 0.1)), RATE)
        self.assertLess(low, -22)


class Peaks(unittest.TestCase):
    def test_true_peak_finds_the_peak_between_samples(self):
        # A quarter-rate sine at 45 degrees never lands on its crest: the samples
        # read 0.707 of it, so the sample peak is 3 dB low.
        # The fade stops a hard start and end ringing above the tone's own peak.
        tone = sine(RATE / 4, 2, 1.0, np.pi / 4)
        x = stereo(tone * np.hanning(len(tone)) ** 0.1)
        self.assertAlmostEqual(rc.db(np.abs(x).max()), -3.01, delta=0.02)
        self.assertAlmostEqual(rc.db(rc.true_peak(x)), 0.0, delta=0.05)

    def test_true_peak_of_plain_sine(self):
        x = stereo(sine(997, 3, 0.5))
        self.assertAlmostEqual(rc.db(rc.true_peak(x)), -6.02, delta=0.05)

    def test_peak_in_the_second_channel_or_late_in_the_file(self):
        x = np.zeros((RATE * 4, 2))
        x[RATE * 3:RATE * 3 + 200, 1] = sine(997, 200 / RATE, 0.5)
        self.assertAlmostEqual(rc.db(rc.true_peak(x)), -6.02, delta=0.3)


class Files(unittest.TestCase):
    def run_on(self, samples, **kw):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "song.wav")
            write_wav(path, samples, **kw)
            return rc.check(path)

    def levels(self, result):
        return [level for level, _ in result["findings"]]

    def test_good_master_passes(self):
        r = self.run_on(stereo(sine(997, 4, 0.5)))
        self.assertEqual((r["bits"], r["rate"], r["channels"]), (24, RATE, 2))
        self.assertEqual(set(self.levels(r)), {"ok"})
        self.assertAlmostEqual(r["seconds"], 4.0, delta=0.01)

    def test_24_bit_negative_samples_read_right(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "song.wav")
            write_wav(path, stereo(np.array([-0.5, 0.5, -0.25])))
            got, _ = rc.read_wav(path)
        self.assertAlmostEqual(got[0, 0], -0.5, delta=1e-5)
        self.assertAlmostEqual(got[2, 1], -0.25, delta=1e-5)

    def test_sixteen_bit_passes(self):
        self.assertNotIn("block", self.levels(self.run_on(stereo(sine(997, 2, 0.5)), bits=16)))

    def test_float_is_blocked(self):
        r = self.run_on(stereo(sine(997, 2, 0.5)), bits=32, code=3)
        self.assertIn("block", self.levels(r))

    def test_mono_is_blocked(self):
        r = self.run_on(sine(997, 2, 0.5).reshape(-1, 1))
        self.assertIn("block", self.levels(r))

    def test_silent_file_is_blocked(self):
        self.assertIn("block", self.levels(self.run_on(np.zeros((RATE * 2, 2)))))

    def test_other_rate_only_warns(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "song.wav")
            write_wav(path, stereo(sine(997, 2, 0.5)), rate=48000)
            r = rc.check(path)
        self.assertIn("warn", self.levels(r))
        self.assertNotIn("block", self.levels(r))

    def test_hot_master_warns(self):
        r = self.run_on(stereo(np.clip(sine(997, 2, 2.0), -1, 1)))
        self.assertIn("warn", self.levels(r))
        self.assertGreater(r["clipped_runs"], 0)

    def test_silence_at_ends_is_measured(self):
        x = np.concatenate([np.zeros(RATE * 3), sine(997, 2, 0.5), np.zeros(RATE * 7)])
        r = self.run_on(stereo(x))
        self.assertAlmostEqual(r["head_silence_s"], 3.0, delta=0.01)
        self.assertAlmostEqual(r["tail_silence_s"], 7.0, delta=0.01)
        self.assertEqual(self.levels(r).count("warn"), 2)

    def test_not_a_wav_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "song.wav")
            with open(path, "wb") as f:
                f.write(b"this is not audio at all")
            self.assertEqual(rc.main([path]), 2)

    def test_exit_codes_and_report_files(self):
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "good.wav")
            bad = os.path.join(d, "bad.wav")
            write_wav(good, stereo(sine(997, 2, 0.5)))
            write_wav(bad, sine(997, 2, 0.5).reshape(-1, 1))
            out = os.path.join(d, "out")
            self.assertEqual(rc.main([good, "--out", out]), 0)
            self.assertEqual(rc.main([bad]), 1)
            self.assertTrue(os.path.exists(os.path.join(out, "release-check.md")))
            self.assertTrue(os.path.exists(os.path.join(out, "release-check.json")))


if __name__ == "__main__":
    unittest.main()
