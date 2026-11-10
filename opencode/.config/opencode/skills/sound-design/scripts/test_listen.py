"""Tests for listen.py's measuring on synthetic sounds (needs numpy:
~/.venvs/audio/bin/python test_listen.py). Playing presets needs the plugin."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import listen  # noqa: E402

SR = listen.SR
HOLD = (0.0, 30.0)
OFF = 30.0
LENGTH = 34.0


def t(seconds=LENGTH):
    return np.arange(int(seconds * SR)) / SR


def chord(times, freqs=(130.8, 155.6, 196.0, 233.1, 293.7), bright=0.0):
    """A soft saw-ish chord: harmonics falling off, ``bright`` (array or
    number, 0..1) lifts the upper harmonics."""
    out = np.zeros_like(times)
    for f in freqs:
        for h in range(1, 12):
            if f * h > 12000:
                break
            gain = (1.0 / h) * (0.15 + bright * (h / 12.0)) if h > 1 else 1.0
            out += gain * np.sin(2 * np.pi * f * h * times + h)
    return out / (len(freqs) * 3)


def gate(x, times, off=OFF, release=1.0):
    env = np.where(times < off, 1.0, np.exp(-(times - off) / (release / 4.6)))
    return x * env


def stereo(left, right=None):
    return np.stack([left, left if right is None else right])


class Movement(unittest.TestCase):
    def test_static_chord_is_static(self):
        x = t()
        m = listen.measure(stereo(gate(chord(x), x)), HOLD, OFF)
        self.assertEqual(m["moving"], [])
        self.assertIn("static", " ".join(listen.flags(m)))

    def test_tremolo_is_level_movement_that_loops(self):
        x = t()
        lfo = 10 ** ((3 * np.sin(2 * np.pi * 0.2 * x)) / 20)
        m = listen.measure(stereo(gate(chord(x) * lfo, x)), HOLD, OFF)
        self.assertIn("level", m["moving"])
        self.assertAlmostEqual(m["periods"]["level"], 5.0, delta=0.4)
        text = " ".join(listen.flags(m))
        self.assertIn("one movement", text)
        self.assertIn("loops", text)

    def test_two_unrelated_movements_dont_loop(self):
        x = t()
        lfo = 10 ** ((3 * np.sin(2 * np.pi * 0.13 * x)) / 20)
        pan = 0.5 + 0.45 * np.sin(2 * np.pi * 0.071 * x + 1)
        sig = gate(chord(x) * lfo, x)
        m = listen.measure(np.stack([sig * np.sqrt(1 - pan), sig * np.sqrt(pan)]), HOLD, OFF)
        self.assertIn("level", m["moving"])
        self.assertIn("pan", m["moving"])
        text = " ".join(listen.flags(m))
        self.assertNotIn("loops", text)
        self.assertNotIn("one movement", text)
        self.assertIn("pan", listen.describe_movement(m))

    def test_filter_sweep_moves_brightness(self):
        x = t()
        bright = 0.5 + 0.5 * np.sin(2 * np.pi * 0.09 * x)
        m = listen.measure(stereo(gate(chord(x, bright=bright * 4), x)), HOLD, OFF)
        self.assertIn("brightness", m["moving"])

    def test_period_of_noise_is_irregular(self):
        rng = np.random.default_rng(1)
        self.assertIsNone(listen.period(rng.normal(size=400)))


class Tone(unittest.TestCase):
    def test_mono_and_wide(self):
        x = t()
        sig = gate(chord(x), x)
        mono = listen.measure(stereo(sig), HOLD, OFF)
        self.assertLess(mono["width"], 0.01)
        rng = np.random.default_rng(2)
        noise_l, noise_r = (gate(rng.normal(size=len(x)) * 0.1, x) for _ in range(2))
        wide = listen.measure(np.stack([sig + noise_l, sig + noise_r]), HOLD, OFF)
        self.assertGreater(wide["width"], mono["width"] + 0.05)

    def test_wide_low_end_and_heavy_low_end(self):
        x = t()
        sub = gate(0.5 * np.sin(2 * np.pi * 55 * x), x)
        top = gate(chord(x), x) * 0.2
        m = listen.measure(np.stack([top + sub, top - sub]), HOLD, OFF)
        text = " ".join(listen.flags(m))
        self.assertIn("wide low end", text)
        self.assertIn("heavy low end", text)

    def test_same_sound_is_close_and_different_sound_is_not(self):
        x = t()
        a = listen.measure(stereo(gate(chord(x), x)), HOLD, OFF)
        b = listen.measure(stereo(gate(chord(x) * 0.5, x)), HOLD, OFF)
        c = listen.measure(stereo(gate(chord(x, bright=3.0), x)), HOLD, OFF)
        near = listen.tone_distance(np.array(a["_tone"]), np.array(b["_tone"]))
        far = listen.tone_distance(np.array(a["_tone"]), np.array(c["_tone"]))
        self.assertLess(near, 0.5)
        self.assertGreater(far, listen.CLOSE_TONE_DB)
        self.assertIn("close to its base", " ".join(listen.flags(b, base=a)))
        self.assertFalse(any("base" in f for f in listen.flags(c, base=a)))


class Shape(unittest.TestCase):
    def test_attack_and_release(self):
        x = t()
        ramp = np.clip(x / 1.5, 0, 1)
        m = listen.measure(stereo(gate(chord(x) * ramp, x, release=2.0)), HOLD, OFF)
        self.assertAlmostEqual(m["attack_s"], 1.06, delta=0.15)   # 3 dB below = 0.708 of 1.5 s
        self.assertAlmostEqual(m["release_s"], 2.0, delta=0.3)

    def test_instant_attack_is_flagged(self):
        x = t()
        m = listen.measure(stereo(gate(chord(x), x)), HOLD, OFF)
        self.assertIn("instant attack", " ".join(listen.flags(m)))

    def test_endless_release_is_flagged(self):
        x = t()
        m = listen.measure(stereo(chord(x)), HOLD, OFF)
        self.assertIsNone(m["release_s"])
        self.assertIn("release longer", " ".join(listen.flags(m, tail_s=4)))

    def test_silence(self):
        m = listen.measure(np.zeros((2, SR * 4)), HOLD, OFF)
        self.assertTrue(m["silent"])
        self.assertIn("silent", listen.flags(m)[0])


class Pack(unittest.TestCase):
    def test_alike_pair_and_level_outlier(self):
        x = t()
        base = gate(chord(x), x)
        takes = [listen.measure(stereo(s), HOLD, OFF) for s in
                 (base, base * 0.9, gate(chord(x, bright=3.0), x) * 0.1)]
        results = [{"name": n, "take": m} for n, m in zip(("A", "B", "C"), takes)]
        text = " ".join(listen.pack_flags(results))
        self.assertIn("A and B sound alike", text)
        self.assertIn("C is", text)

    def test_controls(self):
        x = t(12)
        a = listen.measure(stereo(chord(x)), (0, 12), 12)
        b = listen.measure(stereo(chord(x, bright=3.0)), (0, 12), 12)
        tone, level, moved = listen.control_effect(a, a)
        self.assertEqual((tone, level, moved), (0.0, 0.0, False))
        tone, level, moved = listen.control_effect(a, b)
        self.assertGreater(tone, listen.CONTROL_CHANGE_DB)


class Clip(unittest.TestCase):
    def test_default_test_and_hold_window(self):
        clip = listen.test_clip({})
        hold, off = listen.hold_window(clip)
        self.assertEqual(hold, (0.0, 30.0))
        self.assertEqual(off, 38.0)

    def test_spec_and_preset_overrides(self):
        spec = {"listen": {"bpm": 120}}
        item = {"listen": {"notes": [[0, "A1", 8, 100], [8, "C2", 4, 100]], "bars": 4}}
        clip = listen.test_clip(spec, item)
        self.assertEqual(clip["bpm"], 120)
        hold, off = listen.hold_window(clip)
        self.assertEqual(hold, (0.0, 4.0))
        self.assertEqual(off, 6.0)

    def test_markdown_has_a_row_and_flags(self):
        x = t()
        m = listen.measure(stereo(gate(chord(x), x)), HOLD, OFF)
        m.pop("_tone")
        report = {"synth": "Zebra3", "test": listen.test_clip({}), "pack": [],
                  "presets": [{"name": "BNN Test", "take": m, "flags": listen.flags(m)}]}
        md = listen.markdown(report)
        self.assertIn("| BNN Test | static |", md)
        self.assertIn("**BNN Test**", md)


if __name__ == "__main__":
    unittest.main()
