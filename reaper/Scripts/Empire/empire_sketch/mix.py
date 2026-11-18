#!/usr/bin/env python3
"""Mix sessions for a song, through the open REAPER. It has to be running; this never
starts it.

    mix.py bounce <song> [master.RPP]   print a master's tracks into a new mix session
    mix.py print <song> [mix.RPP]       print the newest saved mix session for measuring
    mix.py wait                         keep waiting for a job that ran past the wait

A session is mix-<stamp>.RPP in the song's folder. Its audio is in mix-<stamp>/stems/
and each pass's prints in mix-<stamp>/passes/pass-<n>/. The master is never touched,
and bounce works from the newest master unless told which. mix_fix.py makes a new
session from the newest one, which then becomes the newest; print says which earlier
pass to compare with, following a session back to the one it came from.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

from check_sketch import SKETCHES, slug

REAPER = "/Applications/REAPER.app/Contents/MacOS/REAPER"
SCRIPT = "~/Library/Application Support/REAPER/Scripts/Empire/Empire Mix.lua"
WAIT_SECONDS = 540  # under the ten minutes an agent's shell command can run
STILL_RUNNING = 3


class MixError(Exception):
    pass


def is_running():
    return subprocess.run(["pgrep", "-x", "REAPER"], stdout=subprocess.DEVNULL).returncode == 0


def launch():
    try:
        subprocess.run([REAPER, "-nonewinst", os.path.expanduser(SCRIPT)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        pass  # REAPER has the job; the result file says how it went


def newest(folder, prefix):
    found = sorted(glob.glob(os.path.join(folder, prefix + "-*.RPP")))
    return found[-1] if found else None


def session_info(session):
    path = os.path.join(session[: -len(".RPP")], "session.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def current_session(folder, session=None):
    """The newest mix session, unless one is named. An older one saved after it means
    Paul mixed in the wrong tab, so say so instead of printing the wrong one."""
    if session:
        if not os.path.exists(session):
            raise MixError(f"no mix session {session}")
        return session
    mix = newest(folder, "mix")
    if not mix:
        raise MixError(f"no mix session in {folder}. Bounce one first.")
    later = [s for s in glob.glob(os.path.join(folder, "mix-*.RPP"))
             if s != mix and os.path.getmtime(s) > os.path.getmtime(mix) + 2]
    if later:
        raise MixError(f"{os.path.basename(later[0])} was saved after the newest session, "
                       f"{os.path.basename(mix)}. Mix in the newest one, or name the session to print.")
    return mix


def last_pass(session):
    """The newest printed pass of a session, or of the session it was made from."""
    seen = set()
    while session and session not in seen:
        seen.add(session)
        passes = os.path.join(session[: -len(".RPP")], "passes")
        numbers = [int(m.group(1)) for m in (re.fullmatch(r"pass-(\d+)", n) for n in
                                             (os.listdir(passes) if os.path.isdir(passes) else [])) if m]
        found = [n for n in sorted(numbers, reverse=True)
                 if os.path.exists(os.path.join(passes, f"pass-{n}", "print.json"))]
        if found:
            return os.path.join(passes, f"pass-{found[0]}")
        session = session_info(session).get("from")
    return None


def next_pass(session):
    passes = os.path.join(session[: -len(".RPP")], "passes")
    numbers = [int(m.group(1)) for m in (re.fullmatch(r"pass-(\d+)", n) for n in
                                         (os.listdir(passes) if os.path.isdir(passes) else [])) if m]
    return os.path.join(passes, f"pass-{max(numbers, default=0) + 1}")


def bounce_request(song, root, master=None, now=time.strftime):
    folder = os.path.join(root, slug(song))
    base = master or newest(folder, "master")
    if not base or not os.path.exists(base):
        raise MixError(f"no master in {folder}")
    mix = os.path.join(folder, "mix-" + now("%Y%m%d-%H%M%S") + ".RPP")
    shutil.copyfile(base, mix)
    stems = os.path.join(mix[: -len(".RPP")], "stems")
    os.makedirs(stems)
    with open(os.path.join(mix[: -len(".RPP")], "session.json"), "w") as f:
        json.dump({"master": base}, f)
    return {"action": "bounce", "base": base, "mix": mix, "stems": stems}


def print_request(song, root, session=None):
    mix = current_session(os.path.join(root, slug(song)), session)
    master = session_info(mix).get("master")
    if not master:
        raise MixError(f"{mix} has no session.json naming its master")
    return {"action": "print", "mix": mix, "folder": next_pass(mix), "master": master,
            "previous": last_pass(mix)}


def wait_for(result, wait=WAIT_SECONDS, pause=1):
    end = time.time() + wait
    while time.time() < end:
        if os.path.exists(result):
            with open(result) as f:
                return json.load(f)
        time.sleep(pause)
    return None


def run(request, root, running=is_running, start=launch, wait=WAIT_SECONDS, pause=1):
    if not running():
        raise MixError("REAPER isn't running. Open it, then try again.")
    result = os.path.join(root, "mix-result.json")
    if os.path.exists(result):
        os.remove(result)
    target = os.path.join(root, "mix-request.json")
    with open(target + ".tmp", "w") as f:
        json.dump(request, f)
    os.rename(target + ".tmp", target)
    start()
    return wait_for(result, wait, pause)


def discard(request):
    """A failed bounce leaves nothing behind, so it can't be taken for the newest session."""
    os.remove(request["mix"])
    shutil.rmtree(request["mix"][: -len(".RPP")])


def finish(answer, request=None):
    if answer is None:
        print("STILL RUNNING: REAPER is working. Run `mix.py wait`, and don't start another job.")
        sys.exit(STILL_RUNNING)
    if not answer.get("ok"):
        print("FAILED: " + answer.get("message", "no reason given"))
        sys.exit(1)
    if "mix" in answer:
        print(f"session {answer['mix']}")
        print(f"printed {len(answer['printed'])}: " + ", ".join(answer["printed"]))
        print("silent, so left empty: " + (", ".join(answer["silent"]) or "none"))
        if answer.get("split"):
            print("played everything on one output, so printed per drum: " + ", ".join(answer["split"]))
    else:
        print(f"pass {answer['folder']}: {answer['tracks']} tracks")
        if request and request.get("previous"):
            print(f"compare with {request['previous']}")
    print(f"took {answer['seconds']} seconds")


def main():
    args, root = sys.argv[1:], os.path.expanduser(SKETCHES)
    try:
        if args == ["wait"]:
            finish(wait_for(os.path.join(root, "mix-result.json")))
        elif len(args) in (2, 3) and args[0] == "bounce":
            request = bounce_request(args[1], root, args[2] if len(args) == 3 else None)
            answer = run(request, root)
            if answer is not None and not answer.get("ok"):
                discard(request)
            finish(answer)
        elif len(args) in (2, 3) and args[0] == "print":
            request = print_request(args[1], root, args[2] if len(args) == 3 else None)
            finish(run(request, root), request)
        else:
            raise SystemExit(__doc__)
    except MixError as problem:
        print(f"FAILED: {problem}")
        sys.exit(1)


if __name__ == "__main__":
    main()
