"""Client for driver.py - sends one ClubGG UI command and waits for the result.

The driver must already be running elevated (see driver.py docstring).
All coordinates are ClubGG-window-relative, assuming the 540x990 canonical
window size (run `gg.py setwin` once to enforce it).

Usage:
  python gg.py ping
  python gg.py setwin [--shot out.png]
  python gg.py shot <out.png>
  python gg.py click <x> <y> [--shot out.png]
  python gg.py swipe <x1> <y1> <x2> <y2> [--shot out.png]
  python gg.py scroll <x> <y> <clicks> [--shot out.png]   # wheel; negative = down
  python gg.py type <text> [--shot out.png]
  python gg.py quit

With --shot, the driver waits ~1.2s after the action (UI settle) and then
saves a screenshot of the ClubGG window to the given path.
"""
import json
import os
import sys
import time
from pathlib import Path

BRIDGE = Path(__file__).parent / "bridge"
CMD = BRIDGE / "cmd.json"
HEARTBEAT = BRIDGE / "driver_alive.txt"


def driver_alive():
    try:
        return time.time() - HEARTBEAT.stat().st_mtime < 10
    except OSError:
        return False


def send(cmd, timeout=45):
    if not driver_alive():
        print("ERROR: driver not running. Start it elevated (accept the UAC prompt):")
        print("  Start-Process -FilePath python -ArgumentList "
              "'\"c:\\Users\\PC1\\clubgg-tool\\driver.py\"' -Verb RunAs")
        sys.exit(2)
    cmd["id"] = str(time.time_ns())
    tmp = BRIDGE / "cmd.tmp"
    tmp.write_text(json.dumps(cmd), encoding="utf-8")
    os.replace(tmp, CMD)
    res_path = BRIDGE / f"res_{cmd['id']}.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if res_path.exists():
            out = json.loads(res_path.read_text(encoding="utf-8"))
            res_path.unlink()
            print(json.dumps(out))
            sys.exit(0 if out.get("ok") else 1)
        time.sleep(0.05)
    print("ERROR: timeout waiting for driver response")
    sys.exit(3)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    action, rest = args[0], args[1:]
    cmd = {"action": action}
    if "--shot" in rest:
        i = rest.index("--shot")
        cmd["shot"] = str(Path(rest[i + 1]).resolve())
        del rest[i:i + 2]

    if action == "restartgg":
        send(cmd, timeout=280)
        return
    if action in ("ping", "quit", "setwin", "ggpath"):
        pass
    elif action == "shot":
        cmd["shot"] = str(Path(rest[0]).resolve())
    elif action == "click":
        cmd["x"], cmd["y"] = int(rest[0]), int(rest[1])
    elif action == "swipe":
        cmd["x1"], cmd["y1"], cmd["x2"], cmd["y2"] = (int(v) for v in rest[:4])
    elif action == "scroll":
        cmd["x"], cmd["y"], cmd["clicks"] = int(rest[0]), int(rest[1]), int(rest[2])
    elif action == "type":
        cmd["text"] = rest[0]
    else:
        print(f"unknown action: {action}")
        sys.exit(1)
    send(cmd)


if __name__ == "__main__":
    main()
