#!/usr/bin/env python3
"""u-he presets (.h2p): search, inspect, compare and write them.

    uhe.py catalog Diva                      index the factory + user presets
    uhe.py find Diva warm bass --category Bass
    uhe.py show "HS Bass Nine" --synth Diva --module VCF1
    uhe.py diff "INIT Minipoly" "HS Bass Nine" --synth Diva
    uhe.py params Diva --module ENV1         every parameter with its factory range
    uhe.py typical Diva --category Bass:Analogue
    uhe.py pack spec.json                    write a pack of presets (see SKILL.md)
    uhe.py manual Zebra3 filter              the manual's section on a topic

A preset is text: a /*@Meta ... */ header (bank, author, categories, ...),
then parameters grouped by module (`#cm=VCF1` then `Freq=150.00` lines), then
a binary block. The synths load the text values over the binary block (tested
with Diva and Zebra 3), but the block also holds what the text can't (Zebra's
grid routing, wavetables and MSEG curves), so presets written here keep their
base preset's block, and parameters that point into it are never changed.

Python 3.9+ standard library only (it runs on the Macs' /usr/bin/python3).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional

FACTORY = Path(os.environ.get("UHE_FACTORY_PRESETS", "/Library/Audio/Presets/u-he"))
USER = Path(os.environ.get("UHE_USER_PRESETS", Path.home() / "Library/Audio/Presets/u-he"))
CATALOGS = Path(os.environ.get("UHE_CATALOG_DIR", Path.home() / ".empire/uhe"))
MANUALS = Path(os.environ.get("UHE_MANUALS", Path.home() / ".empire/manuals"))
OUR_FOLDER = "Empire"           # everything we write goes under <user>/<Synth>/Empire/
BINARY_MARK = "// Section for ugly compressed binary Data"
META_RE = re.compile(r"/\*@Meta\n(.*?)\*/\n*", re.S)
FIELD_RE = re.compile(r"^(\w[\w ]*):\n'(.*?)'\n", re.S | re.M)
META_ORDER = ["Bank", "Author", "Usage", "Description", "Categories", "Features", "Character"]
# Internal bookkeeping (version, per-voice drift tables, scope): left out of `typical`.
NOISE_MODULES = {"main", "PCore", "OPT", "Scope1"}
SOURCE_RE = re.compile(r"(Src\d*|[DF]MS\d)$|^MM\d+\.(Source|Via)$"    # picks a mod source
                       r"|^(Filter\d+\.FS\d|Osc\dFX\d\.(Source|Trigger)|Noise\d\.(VolSc|Trigger)"
                       r"|Modal\d\.TuneSc|TxVb\.(Trigger|GrnTrig)|Excitr\d\.(Trigger|VolMS))$")
# Named like sources but using another list (5 = CtrlC on nearly every Zebra
# preset's amp can't be right) or display state: never labelled.
NOT_SOURCE_RE = re.compile(r"^GridAmp\.Amp\dSrc$|\.PlotSrc$")
DEST_RE = re.compile(r"^MM\d+\.Dest\d+$")          # Zebra matrix target, e.g. Filter1:Cut
# Parameters that point into the binary block (grid routing, curves, module
# files) or hold host/UI state: changing them breaks the preset.
PROTECTED = {
    "Zebra3": re.compile(r"^(Grid|FXGrid|MPreset|Scope|main|PCore|MGraph|MPE|LayMem|MIDI)\."
                         r"|^[OM]\dGeo\d\.|\.Coord$|^Modal\d\.MDFile|^MMap\d\.Stps$"
                         r"|^Noise\d\.KVsc$|^Tune\.MTun[NT]$"),
}
FLAG_RE = re.compile(r"#(FX\d)=")                # effect slot on/off, written with a leading #


class UheError(Exception):
    pass


# -- one preset ---------------------------------------------------------------

class Preset:
    def __init__(self, text: str, path: Optional[Path] = None):
        self.path = path
        self.meta: Dict[str, str] = {}
        body = text.replace("\r\n", "\n")
        m = META_RE.match(body)
        if m:
            self.meta = {k: v for k, v in FIELD_RE.findall(m.group(1))}
            body = body[m.end():]
        cut = body.find(BINARY_MARK)
        self.binary = ""
        if cut != -1:
            body, self.binary = body[:cut], body[cut:]
        self.lines = body.rstrip("\n").split("\n")
        self.index: Dict[str, int] = {}
        self.flags = set()                               # keys written as `#Name=`
        # The header lists the modulation sources; *Src parameters index into it.
        self.sources = [line[4:] for line in self.lines if line.startswith("#ms=")]
        module = None
        for i, line in enumerate(self.lines):
            cm = re.match(r"#cm=(\S+)$", line)
            fl = FLAG_RE.match(line)
            if cm:
                module = cm.group(1)
            elif module and fl:
                self.index[f"{module}.{fl.group(1)}"] = i
                self.flags.add(f"{module}.{fl.group(1)}")
            elif module and "=" in line and not line.startswith(("#", "/", "$")):
                self.index[f"{module}.{line.split('=', 1)[0]}"] = i

    @classmethod
    def load(cls, path: Path) -> "Preset":
        return cls(Path(path).read_text(encoding="latin-1"), Path(path))

    @property
    def synth(self) -> str:
        for line in self.lines:
            if line.startswith("#AM="):
                return line[4:]
        return ""

    @property
    def name(self) -> str:
        return self.path.stem if self.path else ""

    def params(self) -> Dict[str, str]:
        return {k: self.lines[i].split("=", 1)[1] for k, i in self.index.items()}

    def raw_name(self, key: str) -> str:
        return ("#" if key in self.flags else "") + key.split(".", 1)[1]

    def get(self, key: str) -> str:
        if key not in self.index:
            raise UheError(f"{self.synth} has no parameter {key}")
        return self.lines[self.index[key]].split("=", 1)[1]

    def set(self, key: str, value) -> str:
        old = self.get(key)
        new = format_value(old, value)
        self.lines[self.index[key]] = f"{self.raw_name(key)}={new}"
        return new

    def text(self) -> str:
        head = "/*@Meta\n\n"
        keys = [k for k in META_ORDER if self.meta.get(k)] + \
               [k for k in self.meta if k not in META_ORDER and self.meta[k]]
        for k in keys:
            value = self.meta[k].replace("'", "’").replace("\n", "\\r\\n")
            head += f"{k}:\n'{value}'\n\n"
        out = head + "*/\n\n" + "\n".join(self.lines) + "\n"
        return out + "\n\n\n" + self.binary if self.binary else out


def format_value(old: str, value) -> str:
    """Write a value the way the preset stores that parameter."""
    text = str(value).strip()
    if old.startswith("'"):                           # string, e.g. FX1.Module='Plate1'
        return "'" + text.strip("'") + "'"
    if number(old) is None:                           # bare text, e.g. Zebra's Dest1=Filter1:Cut
        return text
    n = number(text)
    if n is None:
        raise UheError(f"expected a number, got {text!r}")
    if "." in old:
        return f"{n:.2f}"
    if n != int(n):
        raise UheError(f"expected a whole number, got {text!r}")
    return str(int(n))


def number(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


# -- catalog ------------------------------------------------------------------

def preset_files(synth: str) -> List[tuple]:
    out = []
    for source, root in (("factory", FACTORY / synth), ("user", USER / synth)):
        if root.is_dir():
            out += [(source, p) for p in sorted(root.rglob("*.h2p"))]
    return out


def build_catalog(synth: str) -> dict:
    files = preset_files(synth)
    if not files:
        raise UheError(f"no {synth} presets under {FACTORY / synth} or {USER / synth}")
    presets, values, by_cat, sources = [], {}, {}, []
    for source, path in files:
        try:
            p = Preset.load(path)
        except (OSError, UnicodeError):
            continue
        root = FACTORY / synth if source == "factory" else USER / synth
        rel = path.relative_to(root).as_posix()
        ours = rel.startswith(OUR_FOLDER + "/")
        cats = [c for c in p.meta.get("Categories", "").split(", ") if c]
        presets.append({
            "name": path.stem, "path": str(path), "source": "empire" if ours else source,
            "folder": os.path.dirname(rel), "bank": p.meta.get("Bank", ""),
            "author": p.meta.get("Author", ""), "categories": cats,
            "features": p.meta.get("Features", ""), "character": p.meta.get("Character", ""),
            "description": p.meta.get("Description", "").replace("\\r\\n", " "),
        })
        if source != "factory":
            continue                                   # ranges come from factory sounds only
        sources = sources or p.sources
        params = p.params()
        groups = set(cats) | {c.split(":")[0] for c in cats}
        for k, v in params.items():
            values.setdefault(k, []).append(v)
            for g in groups:
                by_cat.setdefault(g, {}).setdefault(k, []).append(v)
    stats = {k: describe(v) for k, v in values.items()}
    categories = {}
    for g, params in by_cat.items():
        count = len(next(iter(params.values())))
        categories[g] = {"count": count, "params": {k: centre(v) for k, v in params.items()}}
    catalog = {"synth": synth, "presets": presets, "params": stats, "categories": categories,
               "sources": sources}
    CATALOGS.mkdir(parents=True, exist_ok=True)
    (CATALOGS / f"{synth}.json").write_text(json.dumps(catalog), encoding="utf-8")
    return catalog


def describe(vals: List[str]) -> dict:
    nums = [number(v) for v in vals]
    if any(n is None for n in nums):
        counts: Dict[str, int] = {}
        for v in vals:
            counts[v] = counts.get(v, 0) + 1
        return {"type": "text", "values": dict(sorted(counts.items(), key=lambda x: -x[1])[:12])}
    if all("." not in v for v in vals):
        counts = {}
        for v in vals:
            counts[v] = counts.get(v, 0) + 1
        ints = sorted(int(v) for v in counts)
        return {"type": "choice", "min": ints[0], "max": ints[-1],
                "values": dict(sorted(counts.items(), key=lambda x: -x[1]))}
    nums.sort()
    q = statistics.quantiles(nums, n=10) if len(nums) > 1 else [nums[0]] * 9
    return {"type": "number", "min": nums[0], "max": nums[-1], "median": statistics.median(nums),
            "p10": round(q[0], 2), "p90": round(q[-1], 2)}


def centre(vals: List[str]):
    nums = [number(v) for v in vals]
    if any(n is None for n in nums) or all("." not in v for v in vals):
        return max(set(vals), key=vals.count)          # most common choice
    return round(statistics.median(nums), 2)


def catalog_for(synth: str) -> dict:
    path = CATALOGS / f"{synth}.json"
    if not path.is_file():
        print(f"(building the {synth} catalog, once)", file=sys.stderr)
        return build_catalog(synth)
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(ref: str, synth: str = "") -> Path:
    """A preset by path, or by name (or folder/name) in the catalog."""
    p = Path(ref).expanduser()
    if p.is_file():
        return p
    if not synth:
        raise UheError(f"{ref}: not a file; pass --synth to look it up by name")
    want = ref.lower()
    if want.endswith(".h2p"):
        want = want[:-4]
    hits = [e for e in catalog_for(synth)["presets"]
            if e["name"].lower() == want or f"{e['folder']}/{e['name']}".lower() == want]
    if not hits:
        raise UheError(f"no {synth} preset named {ref!r} (try: uhe.py find {synth} <words>)")
    hits.sort(key=lambda e: e["source"] != "factory")
    return Path(hits[0]["path"])


# -- commands -----------------------------------------------------------------

def cmd_catalog(a):
    c = build_catalog(a.synth)
    cats = sorted(k for k in c["categories"] if ":" in k)
    print(f"{a.synth}: {len(c['presets'])} presets, {len(c['params'])} parameters, "
          f"{len(cats)} categories -> {CATALOGS / (a.synth + '.json')}")


def cmd_find(a):
    c = catalog_for(a.synth)
    words = [w.lower() for w in a.words]
    rows = []
    for e in c["presets"]:
        if a.category and not any(x.lower().startswith(a.category.lower()) for x in e["categories"]):
            continue
        if a.source and e["source"] != a.source:
            continue
        hay = " ".join([e["name"], e["folder"], e["bank"], " ".join(e["categories"]),
                        e["features"], e["character"], e["description"]]).lower()
        score = sum(hay.count(w) for w in words) + sum(3 for w in words if w in e["name"].lower())
        if words and not all(w in hay for w in words):
            continue
        rows.append((score, e))
    rows.sort(key=lambda r: (-r[0], r[1]["name"]))
    for _, e in rows[:a.limit]:
        tags = ", ".join(x for x in [", ".join(e["categories"]), e["character"]] if x)
        print(f"{e['folder'] + '/' if e['folder'] else ''}{e['name']}  [{tags}]"
              + (f"  {e['description'][:100]}" if e["description"] else ""))
    print(f"({len(rows)} match{'es' if len(rows) != 1 else ''})", file=sys.stderr)


def protected(synth: str, key: str) -> bool:
    rule = PROTECTED.get(synth)
    return bool(rule and rule.search(key))


def source_index(value, sources: List[str]):
    """A modulation source by name ("LFO 1") -> its number; numbers pass through."""
    if isinstance(value, str) and number(value) is None:
        names = [s.lower() for s in sources]
        if value.strip().lower() not in names:
            raise UheError(f"no modulation source {value!r} (sources: {', '.join(sources)})")
        return names.index(value.strip().lower())
    return value


def label(key: str, value, sources: List[str]) -> str:
    """`15` -> `15 (Env2)` for a modulation-source parameter."""
    if SOURCE_RE.search(key) and not NOT_SOURCE_RE.search(key):
        try:
            return f"{value} ({sources[int(value)]})"
        except (ValueError, IndexError):
            pass
    return str(value)


def cmd_show(a):
    p = Preset.load(resolve(a.preset, a.synth))
    for k in ("Bank", "Author", "Categories", "Features", "Character", "Description", "Usage"):
        if p.meta.get(k):
            print(f"{k}: {p.meta[k]}")
    module = None
    for k, v in p.params().items():
        m = k.split(".", 1)[0]
        if a.module and m.lower() != a.module.lower():
            continue
        if m != module:
            print(f"\n[{m}]")
            module = m
        print(f"  {k.split('.', 1)[1]}={label(k, v, p.sources)}")


def cmd_diff(a):
    pa, pb = Preset.load(resolve(a.a, a.synth)), Preset.load(resolve(a.b, a.synth))
    va, vb = pa.params(), pb.params()
    for k in va:
        if va[k] != vb.get(k):
            print(f"{k:22} {label(k, va[k], pa.sources):>14}  ->  {label(k, vb.get(k), pb.sources)}")


def cmd_params(a):
    c = catalog_for(a.synth)
    for k, s in c["params"].items():
        if a.module and k.split(".")[0].lower() != a.module.lower():
            continue
        if s["type"] == "number":
            print(f"{k:22} {s['min']:g}..{s['max']:g}  (most presets {s['p10']:g}..{s['p90']:g}, "
                  f"median {s['median']:g})")
        else:
            src = c.get("sources") or []
            vals = ", ".join(f"{label(k, v, src)} x{n}" for v, n in list(s["values"].items())[:8])
            print(f"{k:22} {s['type']}: {vals}")


def cmd_typical(a):
    c = catalog_for(a.synth)
    cat = c["categories"].get(a.category)
    if not cat:
        names = ", ".join(sorted(c["categories"]))
        raise UheError(f"no category {a.category!r}; categories: {names}")
    allc = {k: centre_from_stats(s) for k, s in c["params"].items()}
    rows = []
    src = c.get("sources") or []
    for k, v in cat["params"].items():
        if k.split(".", 1)[0] in NOISE_MODULES or protected(a.synth, k):
            continue
        s = c["params"][k]
        if s["type"] == "number":
            spread = (s["p90"] - s["p10"]) or (s["max"] - s["min"]) or 1
            score = abs(float(v) - s["median"]) / spread
            if score >= 0.15:
                rows.append((score, f"{k:22} {v:>8g}   (all {a.synth}: {s['median']:g})"))
        elif str(v) != str(allc[k]):
            rows.append((0.5, f"{k:22} {label(k, v, src):>8}   (all {a.synth}: {label(k, allc[k], src)})"))
    print(f"{a.category}: {cat['count']} factory presets. Where it differs from all {a.synth} presets:")
    for _, line in sorted(rows, key=lambda r: -r[0])[:a.limit]:
        print("  " + line)


def centre_from_stats(s: dict):
    return s["median"] if s["type"] == "number" else next(iter(s["values"]))


def check_value(stats: dict, key: str, value: str) -> Optional[str]:
    s = stats.get(key)
    if not s:
        return None
    if DEST_RE.match(key):
        target = value.replace(":", ".", 1)
        if target not in stats and value not in s["values"]:
            return f"{key}={value}: no parameter {target} to modulate (e.g. Filter1:Cut, or none:assigned)"
        return None
    if s["type"] == "number":
        n = float(value)
        if n < s["min"] or n > s["max"]:
            return f"{key}={value} is outside the factory range {s['min']:g}..{s['max']:g}"
    elif s["type"] == "choice" and value not in s["values"]:
        return f"{key}={value} is not a value the factory presets use ({', '.join(s['values'])})"
    return None


def cmd_pack(a):
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    written = write_pack(spec, dry_run=a.dry_run, overwrite=a.overwrite,
                         out_dir=Path(a.out_dir) if a.out_dir else None)
    for path, changes in written:
        print(f"{'would write' if a.dry_run else 'wrote'} {path}")
        for line in changes:
            print(f"    {line}")


def safe_name(name: str) -> str:
    name = re.sub(r'[/\\:*?"<>|]+', "-", name).strip(" .")
    if not name:
        raise UheError("empty preset name")
    return name


def write_pack(spec: dict, dry_run=False, overwrite=False, out_dir: Optional[Path] = None):
    """Validate every preset in the spec, then write them all (or none)."""
    synth = spec.get("synth") or ""
    pack = safe_name(spec.get("pack") or "")
    if not synth or not spec.get("presets"):
        raise UheError("the spec needs synth, pack and presets")
    catalog = catalog_for(synth)
    known_cats = {k for k in catalog["categories"] if ":" in k}
    dest = out_dir or USER / synth / OUR_FOLDER / pack
    plans, problems, names = [], [], set()
    for i, item in enumerate(spec["presets"], 1):
        label = item.get("name") or f"preset {i}"
        try:
            name = safe_name(item.get("name") or "")
            if name.lower() in names:
                raise UheError("duplicate name in this pack")
            names.add(name.lower())
            base = Preset.load(resolve(item.get("from") or "", synth))
            if base.synth != synth:
                raise UheError(f"{item.get('from')} is a {base.synth} preset, not {synth}")
            changes = []
            for key, value in (item.get("set") or {}).items():
                if protected(synth, key):
                    raise UheError(f"{key} points into the preset's binary data "
                                   "(routing, curves, files); uhe.py never changes it")
                old = base.get(key)
                is_source = SOURCE_RE.search(key) and not NOT_SOURCE_RE.search(key)
                if is_source:
                    value = source_index(value, base.sources)
                if DEST_RE.match(key):
                    value = str(value).strip("'").replace(".", ":", 1)
                new = base.set(key, value)
                if is_source and base.sources:
                    issue = None if 0 <= int(new) < len(base.sources) else \
                        f"{key}={new}: {synth} has sources 0..{len(base.sources) - 1}"
                else:
                    issue = check_value(catalog["params"], key, new)
                if issue:
                    raise UheError(issue)
                if new != old:
                    changes.append(f"{key}: {old} -> {new}")
            for cat in item.get("categories") or []:
                if cat not in known_cats:
                    raise UheError(f"category {cat!r} is not one {synth} uses "
                                   f"(e.g. {', '.join(sorted(known_cats)[:6])}, ...)")
            base.meta = {
                "Bank": f"{OUR_FOLDER} {pack}",
                "Author": spec.get("author") or OUR_FOLDER,
                "Usage": item.get("usage", ""),
                "Description": item.get("description", ""),
                "Categories": ", ".join(item.get("categories") or []),
                "Features": item.get("features", ""),
                "Character": item.get("character", ""),
            }
            path = dest / f"{name}.h2p"
            if path.exists() and not overwrite:
                raise UheError(f"{path} exists (use --overwrite)")
            plans.append((path, base, [f"from {base.name}"] + changes))
        except UheError as exc:
            problems.append(f"{label}: {exc}")
    if problems:
        raise UheError("nothing written:\n  " + "\n  ".join(problems))
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
        for path, preset, _ in plans:
            path.write_text(preset.text(), encoding="latin-1")
    return [(path, changes) for path, _, changes in plans]


# -- manuals -----------------------------------------------------------------
# A manual is the PDF's text with `=== page N ===` lines (see `manual --pdf`).
# Its table of contents gives each section's first page.

TOC_RE = re.compile(r"^(.+?)\s*\ufffc\s*(\.*)\s*(\d+)$")
JXA = """ObjC.import("PDFKit");
function run(argv) {
  var d = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0])), out = [];
  for (var i = 0; i < d.pageCount; i++)
    out.push("=== page " + (i + 1) + " ===\\n" + ObjC.unwrap(d.pageAtIndex(i).string));
  return out.join("\\n");
}"""


def manual_pages(synth: str) -> Dict[int, str]:
    path = MANUALS / f"{synth}.txt"
    if not path.is_file():
        raise UheError(f"no manual text at {path}; make it with: "
                       f"uhe.py manual {synth} --pdf '<the synth's user guide>.pdf'")
    parts = re.split(r"^=== page (\d+) ===\n", path.read_text(encoding="utf-8"), flags=re.M)
    return {int(n): text for n, text in zip(parts[1::2], parts[2::2])}


def manual_toc(pages: Dict[int, str]) -> List[tuple]:
    """[(title, page, top_level)] in order; top-level entries have no dot leaders."""
    toc = []
    for n in sorted(pages)[:8]:
        for line in pages[n].split("\n"):
            m = TOC_RE.match(line.strip())
            if m and m.group(1).strip():
                toc.append((m.group(1).strip(), int(m.group(3)), not m.group(2)))
    return toc


def section_end(toc: List[tuple], i: int, last: int) -> int:
    """Last page of toc[i]: up to the next chapter, or the next entry's page for a section."""
    title, start, top = toc[i]
    later = [p for _, p, tl in toc[i + 1:] if tl or not top]
    return max(start, (later[0] - 1 if top else later[0]) if later else last)


def cmd_manual(a):
    MANUALS.mkdir(parents=True, exist_ok=True)
    if a.pdf:
        import subprocess
        out = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA, str(Path(a.pdf).expanduser())],
                             capture_output=True, text=True)
        if out.returncode:
            raise UheError(f"could not read {a.pdf}: {out.stderr.strip()}")
        (MANUALS / f"{a.synth}.txt").write_text(out.stdout, encoding="utf-8")
    pages = manual_pages(a.synth)
    toc = manual_toc(pages)
    if a.grep:
        for n in sorted(pages):
            for line in pages[n].split("\n"):
                if a.grep.lower() in line.lower() and not TOC_RE.match(line.strip()):
                    print(f"p.{n}: {line.strip()}")
        return
    if not a.topic:
        for title, page, top in toc:
            print(f"{'' if top else '    '}{title}  p.{page}")
        return
    want = " ".join(a.topic).lower()
    hits = [i for i, (t, _, _) in enumerate(toc) if want in t.lower()]
    if not hits:
        raise UheError(f"no section matching {want!r}; `uhe.py manual {a.synth}` lists them, "
                       f"or search the text with --grep")
    # A whole chapter first, then an exact title, then the longest section (the Editor Bar's
    # one-line "MSEG" entry loses to the MSEG section itself).
    hits.sort(key=lambda i: (not toc[i][2], toc[i][0].lower() != want, toc[i][1] - section_end(toc, i, max(pages)), i))
    i = hits[0]
    title, start, _ = toc[i]
    end = min(section_end(toc, i, max(pages)), start + a.max_pages - 1)
    print(f"# {title} (manual p.{start}-{end})")
    if len(hits) > 1:
        print("also: " + "; ".join(f"{toc[j][0]} p.{toc[j][1]}" for j in hits[1:8]))
    for n in range(start, end + 1):
        print(f"\n--- p.{n} ---\n{pages.get(n, '').strip()}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("catalog"); s.add_argument("synth"); s.set_defaults(fn=cmd_catalog)
    s = sub.add_parser("find"); s.add_argument("synth"); s.add_argument("words", nargs="*")
    s.add_argument("--category"); s.add_argument("--source", choices=["factory", "user", "empire"])
    s.add_argument("--limit", type=int, default=25); s.set_defaults(fn=cmd_find)
    s = sub.add_parser("show"); s.add_argument("preset"); s.add_argument("--synth", default="")
    s.add_argument("--module"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("diff"); s.add_argument("a"); s.add_argument("b")
    s.add_argument("--synth", default=""); s.set_defaults(fn=cmd_diff)
    s = sub.add_parser("params"); s.add_argument("synth"); s.add_argument("--module")
    s.set_defaults(fn=cmd_params)
    s = sub.add_parser("typical"); s.add_argument("synth"); s.add_argument("--category", required=True)
    s.add_argument("--limit", type=int, default=30); s.set_defaults(fn=cmd_typical)
    s = sub.add_parser("pack"); s.add_argument("spec"); s.add_argument("--dry-run", action="store_true")
    s.add_argument("--overwrite", action="store_true"); s.add_argument("--out-dir")
    s.set_defaults(fn=cmd_pack)
    s = sub.add_parser("manual"); s.add_argument("synth"); s.add_argument("topic", nargs="*")
    s.add_argument("--grep"); s.add_argument("--pdf"); s.add_argument("--max-pages", type=int, default=6)
    s.set_defaults(fn=cmd_manual)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except UheError as exc:
        print(f"uhe: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
