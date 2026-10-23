"""Tests for render.py's spec checks, timing, levels and plugin state
(python3 test_render.py; rendering itself needs pedalboard and the plugin)."""
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402
from render import SpecError  # noqa: E402


def juce_b64_decode(s: str) -> bytes:
    size, chars = s.split(".", 1)
    out = bytearray(int(size))
    bit = 0
    for ch in chars:
        val = render.JUCE_B64.index(ch)
        for k in range(6):
            if bit < len(out) * 8 and val >> k & 1:
                out[bit >> 3] |= 1 << (bit & 7)
            bit += 1
    return bytes(out)


def clip(**kw):
    c = {"preset": "WR War Brass", "file": "wr-war-brass", "bpm": 120, "bars": 4,
         "notes": [[0, "A2 E3", 4, 100], [4, "C3", 2, 90]]}
    c.update(kw)
    return c


class NotesCase(unittest.TestCase):
    def test_note_names(self):
        self.assertEqual(render.midi_note("C4"), 60)
        self.assertEqual(render.midi_note("A2"), 45)
        self.assertEqual(render.midi_note("C#3"), 49)
        self.assertEqual(render.midi_note("Bb1"), 34)
        self.assertEqual(render.midi_note("C-1"), 0)
        for bad in ("H2", "A", "C#", "G#9"):
            with self.assertRaises(SpecError):
                render.midi_note(bad)

    def test_events_are_timed_in_seconds_with_offs_first(self):
        ev = render.midi_events(clip(notes=[[0, "A2", 2, 100], [2, "A2", 2, 80]]))
        self.assertEqual(ev, [(0.0, True, 45, 100), (1.0, False, 45, 0),
                              (1.0, True, 45, 80), (2.0, False, 45, 0)])

    def test_macro_interpolation(self):
        pts = [[0, 0.0], [8, 1.0], [12, 1.0]]
        self.assertEqual(render.macro_value(pts, -1), 0.0)
        self.assertAlmostEqual(render.macro_value(pts, 4), 0.5)
        self.assertEqual(render.macro_value(pts, 10), 1.0)
        self.assertEqual(render.macro_value(pts, 99), 1.0)


class SpecCase(unittest.TestCase):
    def test_valid_spec(self):
        render.check_spec({"clips": [clip(macros={"A": [[0, 0.1], [16, 0.9]]})]})

    def test_errors(self):
        cases = [
            ({"clips": []}, "no clips"),
            ({"clips": [clip(), clip()]}, "share a file"),
            ({"clips": [clip(file="WR War")]}, "lowercase"),
            ({"clips": [clip(notes=[[0, "A2", 20, 100]])]}, "outside the 4 bars"),
            ({"clips": [clip(notes=[[0, "A2", 1, 200]])]}, "velocity"),
            ({"clips": [clip(macros={"E": [[0, 0.5]]})]}, "not one of"),
            ({"clips": [clip(macros={"A": [[0, 1.5]]})]}, "0-1"),
            ({"clips": [clip(macros={"A": [[8, 0.5], [0, 0.1]]})]}, "beat order"),
            ({"clips": [clip(bars=40, bpm=60)]}, "longer than"),
        ]
        for spec, msg in cases:
            with self.assertRaisesRegex(SpecError, msg):
                render.check_spec(spec)


class LevelCase(unittest.TestCase):
    def test_quiet_clip_is_raised_to_target(self):
        gain, capped = render.level_gain(rms=10 ** (-30 / 20), peak=10 ** (-20 / 20))
        self.assertAlmostEqual(render.db(gain), 12.0, places=6)
        self.assertFalse(capped)

    def test_peaky_clip_is_limited_by_its_peak(self):
        gain, capped = render.level_gain(rms=10 ** (-30 / 20), peak=10 ** (-6 / 20))
        self.assertTrue(capped)
        self.assertAlmostEqual(render.db(gain), 5.0, places=6)   # peak lands on -1 dBFS


class StateCase(unittest.TestCase):
    def test_juce_base64_round_trip(self):
        for data in (b"", b"a", b"#AM=Zebra3\n", bytes(range(256))):
            self.assertEqual(juce_b64_decode(render.juce_b64_encode(data)), data)

    def test_state_carries_the_preset_in_both_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "WR War Brass.h2p"
            p.write_bytes(b"/*@Meta\nAuthor:\n'x'\n*/\n\n#AM=Zebra3\n#cm=main\nCcOp=50.00\n")
            patch = render.patch_text(p)
        self.assertEqual(patch, b"#pgm=WR War Brass.h2p\n#AM=Zebra3\n#cm=main\nCcOp=50.00\n")
        xml = ('<?xml version="1.0" encoding="UTF-8"?> <VST3PluginState><IComponent>3.abc'
               '</IComponent><IEditController>3.abc</IEditController></VST3PluginState>')
        body = xml.encode()
        template = b"VC2!" + struct.pack("<I", len(body)) + body + b"\x00"
        state = render.plugin_state(template, patch)
        self.assertEqual(state[:4], b"VC2!")
        size = struct.unpack("<I", state[4:8])[0]
        self.assertEqual(size, len(state) - 9)                # the size leaves out the NUL
        blobs = re.findall(rb"<(?:IComponent|IEditController)>(.*?)<", state)
        self.assertEqual([juce_b64_decode(b.decode()) for b in blobs], [patch, patch])

    def test_not_a_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.h2p"
            p.write_bytes(b"hello")
            with self.assertRaises(SpecError):
                render.patch_text(p)


if __name__ == "__main__":
    unittest.main()
