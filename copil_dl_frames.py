r"""Capture the CopilulNorocos Downline Players list as saved frames (like the
roster does), so it can be re-OCR'd offline AND inspected visually - no extra
capture cost per frame. One clean top->bottom scroll after a fresh restart.

  python copil_dl_frames.py            # live capture -> shots/copil_dl_frames/
  python copil_dl_frames.py --parse    # offline: parse frames + diff vs sheet
"""
import csv
import glob
import shutil
import sys
from pathlib import Path

import collect
from collect import (CaptureBlocked, click, enter_club, goto_member_list,
                     ocr_lines, send, send_once, shot)
from copil_downline import (parse_downline, read_total, sheet_members, PID)

ROOT = Path(__file__).parent
FRAMES = ROOT / "shots" / "copil_dl_frames"


def open_downline():
    from copil_downline import open_downline as _open
    return _open()


def capture():
    print("restarting ClubGG for a clean capture budget...", flush=True)
    send_once({"action": "restartgg"}, timeout=280)
    send({"action": "setwin"}); enter_club("RomanianClub"); goto_member_list("All")
    open_downline()
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    print("Downline Players opened; capturing frames top->bottom...", flush=True)
    prev = None
    stable = 0
    n = 0
    target = None
    seen = set()
    for _ in range(40):
        p = shot("dl_cap")
        n += 1
        shutil.copyfile(p, FRAMES / f"{n:03d}.png")
        if target is None:
            target = read_total(p)
        ids = tuple(pid for pid, _ in parse_downline(p))
        for i in ids:
            seen.add(i)
        if ids and ids == prev:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        prev = ids
        if target and len(seen) >= target:
            # keep going a couple frames to be safe, then stop
            pass
        # ~3-row step: 5 shown, ~2 row overlap -> no row skipped
        send({"action": "swipe", "x1": 270, "y1": 860, "x2": 270, "y2": 470,
              "shot": str(collect.SHOTS / "dl_cap.png"), "settle": 0.7})
    print(f"captured {n} frames -> {FRAMES}  (target={target})", flush=True)


def parse_frames():
    frames = sorted(FRAMES.glob("*.png"))
    members = {}
    for fr in frames:
        for pid, name in parse_downline(fr):
            if pid and (pid not in members or not members[pid]):
                members[pid] = name or members.get(pid, "")
    return members, len(frames)


def do_diff():
    live, nframes = parse_frames()
    out = ROOT / "output" / "copil_downline_live.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id", "name"])
        for pid, name in sorted(live.items()):
            w.writerow([pid, name])
    sheet, sheet_file = sheet_members()
    print(f"parsed {nframes} frames -> {len(live)} unique members -> {out}")
    print(f"sheet ({Path(sheet_file).name}): {len(sheet)}")
    missing = {p: n for p, n in live.items() if p not in sheet}
    extra = {p: n for p, n in sheet.items() if p not in live}
    print(f"\n--- IN APP DOWNLINE BUT NOT IN SHEET ({len(missing)}): ---")
    for p, n in sorted(missing.items()):
        print(f"   {p}  {n}")
    print(f"\n--- IN SHEET BUT NOT PARSED FROM FRAMES ({len(extra)}): ---")
    for p, n in sorted(extra.items()):
        print(f"   {p}  {n}")


def main():
    if "--parse" in sys.argv:
        do_diff(); return
    if not collect.driver_alive():
        print("ERROR: driver not running"); sys.exit(2)
    try:
        capture()
    except CaptureBlocked:
        print("capture blocked mid-run; retrying once with fresh restart",
              flush=True)
        capture()
    do_diff()


if __name__ == "__main__":
    main()
