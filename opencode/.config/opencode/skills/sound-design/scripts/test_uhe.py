"""Tests for uhe.py with small synthetic presets (python3 test_uhe.py)."""
import json
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
                "set": {"ENV1.Atk": 75, "VCF1.Freq": 70.5, "FX1.Module": "Plate1"}}
        base.update(item)
        return {"synth": "Diva", "pack": "Test Pack", "presets": [base]}

    def test_parse_and_round_trip_without_binary(self):
        p = uhe.Preset.load(uhe.FACTORY / "Diva/1 BASS/Fat Bass.h2p")
        self.assertEqual(p.synth, "Diva")
        self.assertEqual(p.get("VCF1.Freq"), "60.00")
        self.assertEqual(p.meta["Categories"], "Bass:Analogue")
        out = p.text()
        self.assertNotIn("DON'T TOUCH", out)
        self.assertEqual(uhe.Preset(out).params(), p.params())

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
        self.assertEqual(p.meta["Bank"], "Empire Test Pack")
        self.assertEqual(p.meta["Author"], "Empire")
        self.assertNotIn("$$$$", path.read_text(encoding="latin-1"))
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


if __name__ == "__main__":
    unittest.main()
