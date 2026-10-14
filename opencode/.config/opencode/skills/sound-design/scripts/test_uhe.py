"""Tests for uhe.py with small synthetic presets (python3 test_uhe.py)."""
import io
import json
from contextlib import redirect_stdout
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uhe  # noqa: E402

PRESET = """/*@Meta

Bank:
'Diva Factory'

Author:
'u-he'

Categories:
'{cat}'

*/

#AM=Diva
#Vers=10001
#cm=main
CcOp=50.00
#FX1=0
#cm=ENV1
Atk={atk}
Sus=50.00
Model=2
#cm=FX1
Module='Plate1'
#cm=VCF1
Freq={freq}
Res=0.00



// Section for ugly compressed binary Data
// DON'T TOUCH THIS

$$$$1920
abcDEF=96829
"""


class UheCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        uhe.FACTORY, uhe.USER, uhe.CATALOGS = root / "f", root / "u", root / "c"
        d = uhe.FACTORY / "Diva" / "1 BASS"
        d.mkdir(parents=True)
        for name, cat, atk, freq in (("Fat Bass", "Bass:Analogue", "1.00", "60.00"),
                                     ("Sub Bass", "Bass:Analogue", "2.00", "40.00"),
                                     ("Big Pad", "Pads:Evolving", "80.00", "120.00")):
            (d / f"{name}.h2p").write_text(PRESET.format(cat=cat, atk=atk, freq=freq), encoding="latin-1")

    def tearDown(self):
        self.tmp.cleanup()

    def spec(self, **item):
        base = {"name": "Dark Swell", "from": "Big Pad", "categories": ["Pads:Evolving"],
                "character": "Dark", "description": "A slow, dark swell.",
                "set": {"ENV1.Atk": 75, "VCF1.Freq": 70.5, "FX1.Module": "Plate1", "main.FX1": 0}}
        base.update(item)
        return {"synth": "Diva", "pack": "Test Pack", "presets": [base]}

    def test_parse_and_round_trip_keeps_binary(self):
        p = uhe.Preset.load(uhe.FACTORY / "Diva/1 BASS/Fat Bass.h2p")
        self.assertEqual(p.synth, "Diva")
        self.assertEqual(p.get("VCF1.Freq"), "60.00")
        self.assertEqual(p.meta["Categories"], "Bass:Analogue")
        out = p.text()
        self.assertTrue(out.endswith("$$$$1920\nabcDEF=96829\n"))
        again = uhe.Preset(out)
        self.assertEqual(again.params(), p.params())
        self.assertEqual(again.text(), out)

    def test_catalog_ranges_and_categories(self):
        c = uhe.build_catalog("Diva")
        self.assertEqual(len(c["presets"]), 3)
        self.assertEqual(c["params"]["VCF1.Freq"]["min"], 40.0)
        self.assertEqual(c["params"]["ENV1.Model"]["type"], "choice")
        self.assertEqual(c["params"]["FX1.Module"]["type"], "text")
        self.assertEqual(c["categories"]["Bass"]["count"], 2)
        self.assertEqual(c["categories"]["Bass:Analogue"]["params"]["VCF1.Freq"], 50.0)

    def test_pack_writes_validated_presets(self):
        written = uhe.write_pack(self.spec())
        path = uhe.USER / "Diva/Empire/Test Pack/Dark Swell.h2p"
        self.assertEqual(written[0][0], path)
        p = uhe.Preset.load(path)
        self.assertEqual(p.get("ENV1.Atk"), "75.00")
        self.assertEqual(p.get("VCF1.Freq"), "70.50")
        self.assertEqual(p.get("FX1.Module"), "'Plate1'")
        self.assertIn("#FX1=0\n", path.read_text(encoding="latin-1"))
        self.assertEqual(p.meta["Bank"], "Empire Test Pack")
        self.assertEqual(p.meta["Author"], "Empire")
        self.assertIn("$$$$1920", path.read_text(encoding="latin-1"))
        self.assertIn("VCF1.Freq: 120.00 -> 70.50", written[0][1])

    def test_bad_presets_write_nothing(self):
        cases = [
            {"set": {"VCF1.Nope": 1}},                       # unknown parameter
            {"set": {"VCF1.Freq": 500}},                     # outside the factory range
            {"set": {"ENV1.Model": 7}},                      # a choice nobody uses
            {"categories": ["Pads:Made Up"]},                # unknown category
            {"from": "No Such Preset"},
        ]
        for bad in cases:
            with self.subTest(bad=bad):
                spec = self.spec()
                spec["presets"].append(dict(spec["presets"][0], name="Second", **bad))
                with self.assertRaises(uhe.UheError):
                    uhe.write_pack(spec)
                self.assertFalse((uhe.USER / "Diva/Empire/Test Pack").exists())

    def test_existing_preset_needs_overwrite(self):
        uhe.write_pack(self.spec())
        with self.assertRaises(uhe.UheError):
            uhe.write_pack(self.spec())
        uhe.write_pack(self.spec(), overwrite=True)

    def test_cli_find_and_pack(self):
        spec = Path(self.tmp.name) / "spec.json"
        spec.write_text(json.dumps(self.spec()))
        self.assertEqual(uhe.main(["find", "Diva", "bass", "--category", "Bass"]), 0)
        self.assertEqual(uhe.main(["pack", str(spec), "--dry-run"]), 0)
        self.assertFalse((uhe.USER / "Diva/Empire").exists())
        self.assertEqual(uhe.main(["typical", "Diva", "--category", "Bass"]), 0)


ZEBRA = """/*@Meta

Categories:
'{cat}'

*/

#AM=Zebra3
#ms=none
#ms=ModWhl
#ms=LFO 1
#cm=Grid
Grid=82
#cm=MM1
Source={src}
Via=0
Dest1=none:assigned
Depth1=50.00
#cm=Osc1
PSrc=0
Source=1
#cm=Filter1
Coord=173
Cut={cut}
"""


class ZebraCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        uhe.FACTORY, uhe.USER, uhe.CATALOGS = root / "f", root / "u", root / "c"
        uhe.MANUALS = root / "m"
        d = uhe.FACTORY / "Zebra3" / "01 Atmospheres"
        d.mkdir(parents=True)
        for name, src, cut in (("Fog", 2, "40.00"), ("Mist", 1, "90.00")):
            (d / f"{name}.h2p").write_text(ZEBRA.format(cat="Atmosphere:Dark", src=src, cut=cut),
                                           encoding="latin-1")

    def tearDown(self):
        self.tmp.cleanup()

    def pack(self, changes):
        return uhe.write_pack({"synth": "Zebra3", "pack": "Z", "presets": [
            {"name": "Z1", "from": "Fog", "categories": ["Atmosphere:Dark"], "set": changes}]},
            dry_run=True)

    def test_matrix_sources_by_name_and_targets(self):
        changes = self.pack({"MM1.Source": "ModWhl", "MM1.Dest1": "Filter1.Cut", "Filter1.Cut": 60})[0][1]
        self.assertIn("MM1.Source: 2 -> 1", changes)
        self.assertIn("MM1.Dest1: none:assigned -> Filter1:Cut", changes)
        self.assertIn("MM1.Via: 0 -> 2", self.pack({"MM1.Via": 2})[0][1])   # no factory preset uses it
        for bad in ({"MM1.Source": "LFO 9"}, {"MM1.Source": 3}, {"MM1.Dest1": "Filter9:Cut"}):
            with self.subTest(bad=bad), self.assertRaises(uhe.UheError):
                self.pack(bad)

    def test_pointers_into_binary_are_protected(self):
        for key in ("Grid.Grid", "Filter1.Coord"):
            with self.subTest(key=key), self.assertRaisesRegex(uhe.UheError, "binary"):
                self.pack({key: 82})

    def test_labels(self):
        src = ["none", "ModWhl", "LFO 1"]
        self.assertEqual(uhe.label("MM1.Source", "2", src), "2 (LFO 1)")
        self.assertEqual(uhe.label("Osc1.PSrc", "1", src), "1 (ModWhl)")
        self.assertEqual(uhe.label("Osc1.Source", "1", src), "1")
        self.assertEqual(uhe.label("Filter1.FS1", "2", src), "2 (LFO 1)")
        self.assertEqual(uhe.label("GridAmp.Amp1Src", "2", src), "2")

    def test_manual_sections(self):
        uhe.MANUALS.mkdir()
        (uhe.MANUALS / "Zebra3.txt").write_text(
            "=== page 1 ===\nContents\nFilter \ufffc 2\nFilter Palette \ufffc ......3\n"
            "Comb \ufffc 4\n=== page 2 ===\nFilter\nCut is cutoff.\n"
            "=== page 3 ===\nFilter Palette\nLP Xcite\n=== page 4 ===\nComb\nDamp\n", encoding="utf-8")
        toc = uhe.manual_toc(uhe.manual_pages("Zebra3"))
        self.assertEqual(toc, [("Filter", 2, True), ("Filter Palette", 3, False), ("Comb", 4, True)])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(uhe.main(["manual", "Zebra3", "filter"]), 0)
        self.assertIn("p.2-3", out.getvalue())
        self.assertIn("LP Xcite", out.getvalue())
        self.assertNotIn("Damp", out.getvalue())


if __name__ == "__main__":
    unittest.main()
