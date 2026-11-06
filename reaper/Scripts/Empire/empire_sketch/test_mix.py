#!/usr/bin/env python3
"""Tests mix.py's requests without REAPER."""

import json
import os
import tempfile
import unittest

import mix


class Requests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        self.song = os.path.join(self.root, "my-song")
        os.makedirs(self.song)
        for name in ("master-20260101-000000.RPP", "master-20260102-000000.RPP"):
            with open(os.path.join(self.song, name), "w") as f:
                f.write(name)

    def tearDown(self):
        self.dir.cleanup()

    def bounce(self):
        return mix.bounce_request("My Song", self.root, now=lambda _: "20260103-000000")

    def test_bounce_copies_the_newest_master_and_leaves_it_alone(self):
        request = self.bounce()
        self.assertTrue(request["base"].endswith("master-20260102-000000.RPP"))
        self.assertTrue(request["mix"].endswith("mix-20260103-000000.RPP"))
        with open(request["mix"]) as f:
            self.assertEqual(f.read(), "master-20260102-000000.RPP")
        self.assertTrue(os.path.isdir(request["stems"]))

    def test_a_failed_bounce_leaves_nothing_behind(self):
        request = self.bounce()
        mix.discard(request)
        self.assertFalse(os.path.exists(request["mix"]))
        self.assertFalse(os.path.exists(request["mix"][: -len(".RPP")]))
        self.assertIsNone(mix.newest(self.song, "mix"))

    def test_bounce_needs_a_master(self):
        with self.assertRaises(mix.MixError):
            mix.bounce_request("Nothing Here", self.root)

    def test_print_needs_a_session(self):
        with self.assertRaises(mix.MixError):
            mix.print_request("My Song", self.root)

    def test_print_numbers_passes_and_remembers_the_master(self):
        session = self.bounce()
        request = mix.print_request("My Song", self.root)
        self.assertEqual(request["mix"], session["mix"])
        self.assertTrue(request["folder"].endswith("passes/pass-1"))
        self.assertEqual(request["master"], session["base"])
        os.makedirs(request["folder"])
        self.assertTrue(mix.print_request("My Song", self.root)["folder"].endswith("passes/pass-2"))

    def test_run_refuses_when_reaper_is_closed(self):
        with self.assertRaises(mix.MixError):
            mix.run({}, self.root, running=lambda: False)

    def test_run_writes_the_request_and_returns_the_answer(self):
        result = os.path.join(self.root, "mix-result.json")

        def start():
            with open(os.path.join(self.root, "mix-request.json")) as f:
                self.assertEqual(json.load(f), {"action": "print"})
            with open(result, "w") as f:
                json.dump({"ok": True}, f)

        self.assertEqual(mix.run({"action": "print"}, self.root, running=lambda: True, start=start), {"ok": True})

    def test_run_says_nothing_yet_when_reaper_is_slow(self):
        self.assertIsNone(mix.run({}, self.root, running=lambda: True, start=lambda: None, wait=0))


if __name__ == "__main__":
    unittest.main()
