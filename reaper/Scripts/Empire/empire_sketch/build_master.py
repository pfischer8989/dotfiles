#!/usr/bin/env python3
"""Asks the open REAPER for a master from a song's sketch tab, and waits for it.
REAPER has to be running; this never starts it.

    build_master.py <song>
"""

import json
import os
import subprocess
import sys
import time

from check_sketch import SKETCHES, slug

REAPER = "/Applications/REAPER.app/Contents/MacOS/REAPER"
SCRIPT = "~/Library/Application Support/REAPER/Scripts/Empire/Empire Build Master.lua"
WAIT_SECONDS = 120


def is_running():
    return subprocess.run(["pgrep", "-x", "REAPER"], stdout=subprocess.DEVNULL).returncode == 0


def launch():
    subprocess.run([REAPER, "-nonewinst", os.path.expanduser(SCRIPT)], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=60, check=False)


def request_master(song, root=SKETCHES, running=is_running, start=launch, wait=WAIT_SECONDS, pause=1):
    """Returns the answer: {"ok": true, "master": ..., "clips": n} or {"ok": false, "message": ...}."""
    root = os.path.expanduser(root)
    sketch = os.path.join(root, slug(song), "sketch.json")
    if not os.path.exists(sketch):
        return {"ok": False, "message": f"no sketch at {sketch}"}
    if not running():
        return {"ok": False, "message": "REAPER isn't running. Open it with the sketch's tab, then try again."}
    result = os.path.join(root, "master-result.json")
    if os.path.exists(result):
        os.remove(result)
    with open(os.path.join(root, "master-request"), "w") as f:
        f.write(sketch + "\n")
    start()
    end = time.time() + wait
    while time.time() < end:
        if os.path.exists(result):
            with open(result) as f:
                return json.load(f)
        time.sleep(pause)
    return {"ok": False, "message": f"REAPER didn't answer within {wait} seconds. Is a dialog open in it?"}


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    answer = request_master(sys.argv[1])
    if not answer.get("ok"):
        print("FAILED: " + answer.get("message", "no reason given"))
        sys.exit(1)
    print(f"master {answer['master']}: {answer['clips']} clips")


if __name__ == "__main__":
    main()
