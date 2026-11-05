#!/usr/bin/env python3
"""python3 empire_sketch/test_build_master.py"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_master as bm

failed = []


def check(name, got, want):
    if got != want:
        failed.append(f"{name}: got {got!r}, want {want!r}")


with tempfile.TemporaryDirectory() as root:
    def ask(**kw):
        kw.setdefault("running", lambda: True)
        kw.setdefault("wait", 1)
        kw.setdefault("pause", 0.01)
        return bm.request_master("Goa Sketch 2", root, **kw)

    check("no sketch", ask(start=lambda: None)["ok"], False)
    folder = os.path.join(root, "goa-sketch-2")
    os.makedirs(folder)
    sketch = os.path.join(folder, "sketch.json")
    open(sketch, "w").close()
    started = []
    answer = ask(running=lambda: False, start=lambda: started.append(1))
    check("never starts REAPER", (answer["ok"], started), (False, []))
    request = os.path.join(root, "master-request")
    check("no request left when it isn't running", os.path.exists(request), False)

    def reaper_answers():
        check("request names the sketch", open(request).read().strip(), sketch)
        with open(os.path.join(root, "master-result.json"), "w") as f:
            json.dump({"ok": True, "master": "m.RPP", "clips": 28}, f)

    check("answer comes back", ask(start=reaper_answers)["clips"], 28)
    # an old answer must not pass for a new one
    answer = ask(start=lambda: None)
    check("old answer is ignored", (answer["ok"], "didn't answer" in answer["message"]), (False, True))

if failed:
    print("\n".join("FAIL " + f for f in failed))
    sys.exit(1)
print("ok")
