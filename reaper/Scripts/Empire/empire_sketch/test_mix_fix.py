#!/usr/bin/env python3
"""Tests mix_fix.py without REAPER (needs numpy for the key threshold test)."""

import json
import os
import tempfile
import unittest

import mix
import mix_fix as mf

NAMES = {"Chords", "Lead", "Bass", "Kick (Drums)", "Kick (Drums Live)"}


def fixes(*items):
    return {"schema": mf.SCHEMA, "fixes": list(items)}


def bell(hz=700, **kw):
    return dict({"type": "bell", "hz": hz, "q": 1.2, "db": -3}, **kw)


class Problems(unittest.TestCase):
    def test_a_sound_list_has_none(self):
        doc = fixes({"id": 1, "track": "Chords", "against": "Lead",
                     "bands": [bell(db=0, duck={"key": "Lead", "db": -5}), {"type": "highpass", "hz": 180}]})
        self.assertEqual(mf.problems(doc, NAMES), [])

    def test_limits(self):
        doc = fixes({"id": 1, "track": "Chords", "bands": [
            bell(db=-10), bell(q=8), {"type": "highpass", "hz": 600}, {"type": "lowpass", "hz": 800},
            {"type": "notch", "hz": 100}, {"type": "highpass", "hz": 100, "slope": 48}]})
        text = " ".join(mf.problems(doc, NAMES))
        for part in ("db -10", "q 8", "600 Hz", "800 Hz", "'notch'", "slope 48"):
            self.assertIn(part, text)

    def test_names_must_be_tracks(self):
        doc = fixes({"id": 1, "track": "Kick", "against": "Bas", "bands": [bell(duck={"key": "Leed", "db": -3})]})
        text = " ".join(mf.problems(doc, NAMES))
        self.assertIn("no track 'Kick'", text)
        self.assertIn("'Bas'", text)
        self.assertIn("'Leed'", text)

    def test_ducks(self):
        doc = fixes({"id": 1, "track": "Bass", "bands": [
            bell(67, duck={"key": "Kick (Drums)", "db": -12}),
            bell(140, duck={"key": "Kick (Drums Live)", "db": -3}),
            bell(300, duck={"key": "Bass", "db": -3})]})
        text = " ".join(mf.problems(doc, NAMES))
        self.assertIn("duck db -12", text)
        self.assertIn("one key per track", text)
        self.assertIn("duck to itself", text)

    def test_too_many_bands_on_one_track_across_fixes(self):
        doc = fixes({"id": 1, "track": "Chords", "bands": [bell(200 + i * 50) for i in range(4)]},
                    {"id": 2, "track": "Chords", "bands": [bell(900 + i * 50) for i in range(3)]})
        self.assertIn("7 bands", " ".join(mf.problems(doc, NAMES)))


class Apply(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        self.song = os.path.join(self.root, "my-song")
        session = os.path.join(self.song, "mix-20260101-000000")
        self.session = session + ".RPP"
        self.pass1 = os.path.join(session, "passes", "pass-1")
        os.makedirs(self.pass1)
        with open(self.session, "w") as f:
            f.write("session")
        with open(os.path.join(session, "session.json"), "w") as f:
            json.dump({"master": "/m/master.RPP"}, f)
        tracks = [{"name": "Kick 3/4", "parent": "Drums", "file": "/p/13 Kick 3_4.wav", "guid": "{A}", "number": 13},
                  {"name": "Kick 3/4", "parent": "Drums Live", "file": "/p/22 Kick 3_4.wav", "guid": "{B}", "number": 22},
                  {"name": "Bass", "parent": "BASS", "file": "/p/30 Bass.wav", "guid": "{C}", "number": 30},
                  {"name": "Chords", "parent": "SYNTHS", "file": "/p/40 Chords.wav", "guid": "{D}", "number": 40},
                  {"name": "Lead", "parent": "SYNTHS", "file": "/p/41 Lead.wav", "guid": "{E}", "number": 41}]
        with open(os.path.join(self.pass1, "print.json"), "w") as f:
            json.dump({"tracks": tracks}, f)
        self.fixes = os.path.join(self.root, "fixes.json")

    def tearDown(self):
        self.dir.cleanup()

    def write(self, doc):
        with open(self.fixes, "w") as f:
            json.dump(doc, f)

    def apply(self, stamp="20260102-000000"):
        return mf.apply_request("My Song", self.root, self.fixes, now=lambda _: stamp,
                                threshold=lambda path, hz, q: -33.0)

    def test_a_new_session_from_the_newest_with_moves_per_track(self):
        self.write(fixes({"id": 1, "track": "Bass", "against": "Kick (Drums Live)",
                          "bands": [bell(67, db=0, duck={"key": "Kick (Drums Live)", "db": -6})]},
                         {"id": 2, "track": "Chords", "against": "Bass", "bands": [{"type": "highpass", "hz": 180}]},
                         {"id": 3, "track": "Bass", "against": "Chords", "bands": [bell(220)]}))
        request = self.apply()
        self.assertTrue(request["mix"].endswith("mix-20260102-000000.RPP"))
        self.assertEqual(request["base"], self.session)
        self.assertFalse(request["close_base"])
        bass, chords = request["tracks"]
        self.assertEqual((bass["guid"], bass["name"], len(bass["bands"])), ("{C}", "Bass", 2))
        self.assertEqual(bass["keys"], [{"guid": "{B}", "number": 22, "name": "Kick 3/4"}])
        self.assertEqual(bass["bands"][0]["duck"]["threshold_db"], -33.0)
        self.assertEqual(chords["keys"], [])
        folder = request["mix"][: -len(".RPP")]
        info = mix.session_info(request["mix"])
        self.assertEqual((info["from"], info["reference"], info["master"]), (self.session, self.pass1, "/m/master.RPP"))
        with open(os.path.join(folder, "fixes.json")) as f:
            kept = json.load(f)
        self.assertEqual(kept["fixes"][0]["bands"][0]["duck"]["threshold_db"], -33.0)
        # The fix session is now the newest: a second apply replaces it and closes its tab,
        # and still compares with the pass the fixes were made from.
        again = self.apply("20260103-000000")
        self.assertEqual(again["base"], request["mix"])
        self.assertTrue(again["close_base"])
        self.assertEqual(mix.session_info(again["mix"])["reference"], self.pass1)
        self.assertEqual(mix.last_pass(again["mix"]), self.pass1)

    def test_a_reapply_answers_the_check_not_the_fix_test_print(self):
        self.write(fixes({"id": 1, "track": "Chords", "bands": [bell()]}))
        first = self.apply()
        tested = os.path.join(first["mix"][: -len(".RPP")], "passes", "pass-1")
        os.makedirs(tested)
        with open(os.path.join(tested, "print.json"), "w") as f:
            json.dump({"tracks": [{"name": "Lead", "file": "/q/41 Lead.wav", "number": 41}]}, f)
        with open(os.path.join(tested, "fix-report.json"), "w") as f:
            f.write("{}")
        again = self.apply("20260103-000000")  # Chords isn't in the fix-test print, but is in the check
        self.assertEqual(mix.session_info(again["mix"])["reference"], self.pass1)
        self.assertEqual(mix.last_pass(again["mix"]), tested)

    def test_a_bad_list_makes_nothing(self):
        self.write(fixes({"id": 1, "track": "Chords", "bands": [bell(db=-20)]}))
        with self.assertRaises(mf.FixError):
            self.apply()
        self.assertEqual(sorted(os.listdir(self.song)), ["mix-20260101-000000", "mix-20260101-000000.RPP"])

    def test_needs_a_printed_pass(self):
        os.remove(os.path.join(self.pass1, "print.json"))
        self.write(fixes({"id": 1, "track": "Chords", "bands": [bell()]}))
        with self.assertRaises(mf.FixError):
            self.apply()

    def test_print_refuses_an_older_session_saved_later(self):
        self.write(fixes({"id": 1, "track": "Chords", "bands": [bell()]}))
        request = self.apply()
        os.utime(request["mix"], (1000, 1000))
        os.utime(self.session, (5000, 5000))
        with self.assertRaises(mix.MixError):
            mix.print_request("My Song", self.root)
        named = mix.print_request("My Song", self.root, self.session)
        self.assertEqual(named["mix"], self.session)


class Report(unittest.TestCase):
    def check(self, scores, rms, mix_rms, findings=()):
        return {"band_scores": scores, "tracks": [{"name": n, "rms_db": v} for n, v in rms.items()],
                "mix": {"rms_db": mix_rms}, "findings": list(findings)}

    def test_says_what_each_fix_did(self):
        doc = fixes({"id": 1, "track": "Chords", "against": "Lead", "bands": [bell(700, q=1.0)]},
                    {"id": 2, "track": "Bass", "against": "Kick (Drums)", "bands": [{"type": "lowshelf", "hz": 100, "db": -2}]})
        # Bands 13-15 are 400-794 Hz; band 3 is 63 Hz.
        before = self.check({"Chords + Lead": {"13": 4.0, "14": 6.0, "15": 2.0}, "Bass + Kick (Drums)": {"3": 5.0}},
                            {"Chords": -25.0, "Bass": -20.0, "Lead": -22.0, "Kick (Drums)": -27.0}, -13.2)
        after = self.check({"Chords + Lead": {"13": 1.0, "14": 2.0}, "Bass + Kick (Drums)": {"3": 6.5}},
                           {"Chords": -26.2, "Bass": -21.0, "Lead": -22.0, "Kick (Drums)": -27.0}, -13.6,
                           [{"tracks": ["Chords", "Pad"], "low_hz": 177, "high_hz": 561, "change": "worse"}])
        result = mf.report(doc, after, before)
        one, two = result["fixes"]
        self.assertEqual((one["before"], one["after"], one["result"]), (12.0, 3.0, "better"))
        self.assertEqual(one["track_rms_change_db"], -1.2)
        self.assertEqual(one["worse_elsewhere"], ["Chords + Pad 177-561 Hz (worse)"])
        self.assertEqual(two["result"], "worse")
        self.assertEqual(result["mix_rms_change_db"], -0.4)
        self.assertIn("| 1 | Chords | Lead |", mf.markdown(result))

    def test_a_track_missing_from_a_pass_isnt_called_better(self):
        doc = fixes({"id": 1, "track": "Chords", "against": "Lead", "bands": [bell(700)]})
        before = self.check({"Chords + Lead": {"14": 6.0}}, {"Chords": -25.0, "Lead": -20.0}, -13.0)
        after = self.check({}, {"Lead": -20.0}, -13.5)
        row = mf.report(doc, after, before)["fixes"][0]
        self.assertTrue(row["result"].startswith("not measured: Chords"))
        self.assertNotIn("after", row)

    def test_a_track_relabelled_since_is_followed(self):
        doc = fixes({"id": 2, "track": "Bass", "against": "Kick (track 13)", "bands": [bell(68, q=1.4)]})
        before = self.check({"Bass + Kick (track 13)": {"3": 8.0}}, {"Bass": -20.0, "Kick (track 13)": -27.0}, -13.0)
        before["tracks"][1]["track"] = "Kick 3/4"
        after = self.check({"Bass + Kick (Atlas Kit)": {"3": 2.0}}, {"Bass": -21.0, "Kick (Atlas Kit)": -27.0}, -13.2)
        after["tracks"][1].update(track="Kick 3/4", number=13)
        after["tracks"][0].update(track="Bass", number=31)
        row = mf.report(doc, after, before)["fixes"][0]
        self.assertEqual((row["against"], row["before"], row["after"], row["result"]),
                         ("Kick (Atlas Kit)", 8.0, 2.0, "better"))

    def test_ranges(self):
        self.assertEqual(mf.fix_range({"bands": [{"type": "highpass", "hz": 200}]}), (20.0, 280.0))
        low, high = mf.fix_range({"bands": [bell(1000, q=0.7)]})
        self.assertAlmostEqual(low, 500, delta=1)
        self.assertAlmostEqual(high, 2000, delta=2)
        self.assertEqual(mf.fix_range({"hz_range": [354, 1122], "bands": []}), (354, 1122))


class KeyThreshold(unittest.TestCase):
    def test_sits_under_the_keys_loud_moments(self):
        try:
            import numpy as np
            from test_mix_check import write_wav, RATE
        except ImportError:
            self.skipTest("needs numpy")
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "lead.wav")
            t = np.arange(RATE * 4) / RATE
            write_wav(path, 0.25 * np.sin(2 * np.pi * 700 * t) * (t % 1 < 0.5))  # half a second on, half off
            level = 10 * np.log10(0.25 ** 2 / 2)
            self.assertAlmostEqual(mf.key_threshold(path, 700, 1.0), level - 12, delta=1.5)


if __name__ == "__main__":
    unittest.main()
