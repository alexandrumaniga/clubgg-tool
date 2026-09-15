r"""Enumerate a super agent's LIVE downline (member detail -> Super Agent Management
-> Downline Management) and collect each downline member's stats for a week:
players via their member stats, agents via Agent Statistics (role auto-detected,
same flow as Paul's CopilulNorocos sub-members).

  python downline_report.py 9583-9412 Premium89 2026-08-31 2026-09-06
  python downline_report.py 1394-6890 Cashvick  2026-08-31 2026-09-06 --reenum

Outputs
  shots/dl_<id>/NNN.png                       frames of the Downline Players list (read visually if OCR drops a row)
  output/downline_<id>_live.csv               id,name of the downline (from the frames)
  output/downline_<id>_<start>_<end>.csv      role,id,name,rake,profit_loss  (resumable; feeds statement.py)

Needs ClubGG in RomanianClub + driver.py elevated. The downline list is reused if
already enumerated (delete the live csv or pass --reenum to rescan).
"""
import csv
import shutil
import sys
from datetime import date
from pathlib import Path

import collect
from collect import (CaptureBlocked, block_recovery, click, enter_club,
                     goto_member_list, ocr_lines, search_open, send, send_once, shot)
import copil_downline as cd
import paul_report as pr

ROOT = Path(__file__).parent
FIELDS = ["role", "id", "name", "rake", "profit_loss"]


def live_path(pid):
    return ROOT / "output" / f"downline_{pid}_live.csv"


def stats_path(pid, start, end):
    return ROOT / "output" / f"downline_{pid}_{start}_{end}.csv"


def open_downline(pid, name):
    """Open <pid>'s detail page and tap Downline Management. Returns the list shot."""
    p = search_open(pid, name, "dl")
    if p is None:
        raise RuntimeError(f"{name} ({pid}) not found via search")
    for attempt in range(3):
        if attempt:                      # scroll the detail page down a bit more each time
            send({"action": "swipe", "x1": 270, "y1": 820, "x2": 270, "y2": 340,
                  "shot": str(collect.SHOTS / "dl_sm.png"), "settle": 0.7})
            p = collect.SHOTS / "dl_sm.png"
        labels = [(int(y), int(x), t.lower()) for y, x, t in ocr_lines(p)]
        for y, x, tl in labels:
            if "downl" in tl and "manag" in tl and x < 320 and y > 120:
                return click(200, y, name="dl_open", settle=1.6)
        for y, x, tl in labels:          # OCR misses the row text itself: anchor off Statistics
            if "agent" in tl and "statistic" in tl and x < 320 and y - 64 > 120:
                return click(200, y - 64, name="dl_open", settle=1.6)
    raise RuntimeError("Downline Management row not found on the detail page")


def capture_frames(pid, name):
    frames = ROOT / "shots" / f"dl_{pid}"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    send({"action": "setwin"})
    goto_member_list("All")
    open_downline(pid, name)
    prev, stable, n, target, seen = None, 0, 0, None, set()
    for _ in range(60):
        p = shot("dl_cap")
        n += 1
        shutil.copyfile(p, frames / f"{n:03d}.png")
        if target is None:
            target = cd.read_total(p)
        ids = tuple(i for i, _ in cd.parse_downline(p))
        seen.update(i for i in ids if i)
        if ids == prev:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        prev = ids
        if target is not None and target <= 5:      # short list: one frame holds it all
            break
        send({"action": "swipe", "x1": 270, "y1": 860, "x2": 270, "y2": 470,
              "shot": str(collect.SHOTS / "dl_cap.png"), "settle": 0.7})
    click(25, 62, settle=0.8)                        # back to the detail page
    click(25, 62, settle=0.8)                        # back to the member list
    members = {}
    for fr in sorted(frames.glob("*.png")):
        for mid, mname in cd.parse_downline(fr):
            if mid and (mid not in members or not members[mid]):
                members[mid] = mname or members.get(mid, "")
    members.pop(pid, None)                           # never the head itself
    with live_path(pid).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id", "name"])
        for mid, mname in sorted(members.items()):
            w.writerow([mid, mname])
    print(f"downline of {name}: 'Total Downline Players' = {target}, parsed {len(members)} "
          f"from {n} frame(s) -> {live_path(pid)}   (frames: {frames})", flush=True)
    if target is not None and len(members) != target:
        print(f"  WARNING: parsed {len(members)} != total {target} - read {frames} visually "
              f"and fix {live_path(pid)} before collecting", flush=True)
    return members


def load_live(pid):
    return {r["id"]: r["name"] for r in csv.DictReader(live_path(pid).open(encoding="utf-8"))}


def collect_stats(pid, members, start, end):
    out = stats_path(pid, start, end)
    done = {}
    if out.exists():
        done = {r["id"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
        print(f"resuming: {len(done)} already collected", flush=True)
    recover = block_recovery(tab="All", emit=lambda e: print("  " + e.get("msg", e.get("error", "")), flush=True)
                             if e.get("kind") in ("log", "blocked") else None)
    mode = "a" if done else "w"
    f = out.open(mode, newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if mode == "w":
        w.writeheader()
    try:
        send({"action": "setwin"}); goto_member_list("All")
    except CaptureBlocked:
        if not recover():
            f.close(); return
    items = list(members.items())
    i = 0
    while i < len(items):
        mid, hint = items[i]
        if mid in done:
            i += 1; continue
        tag = f"d{i:02d}"
        try:
            role, name, rake, pnl = pr.collect_submember(mid, hint, start, end, tag)
            rec = {"role": role, "id": mid, "name": name, "rake": rake, "profit_loss": pnl}
            w.writerow(rec); f.flush(); done[mid] = rec
            print(f"[{len(done)}/{len(items)}] {role} {name} ({mid}) rake={rake} pnl={pnl}", flush=True)
            i += 1
        except CaptureBlocked:
            if not recover():
                break
        except Exception as e:
            print(f"  SKIPPED {mid}: {e}", flush=True)
            w.writerow({"role": "ERR", "id": mid, "name": hint, "rake": "ERR", "profit_loss": "ERR"}); f.flush()
            done[mid] = {"id": mid}; i += 1
            try:
                goto_member_list("All")
            except Exception:
                if not recover():
                    break
    f.close()
    print(f"saved {out}", flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pid, name = args[0], args[1]
    start, end = date.fromisoformat(args[2]), date.fromisoformat(args[3])
    if not collect.driver_alive():
        print("ERROR: driver not running"); sys.exit(2)
    if "--reenum" in sys.argv or not live_path(pid).exists():
        recover = block_recovery(tab="All", emit=lambda e: print("  " + e.get("msg", e.get("error", "")), flush=True)
                                 if e.get("kind") in ("log", "blocked") else None)
        for attempt in range(8):
            try:
                members = capture_frames(pid, name); break
            except CaptureBlocked:
                print(f"capture blocked while enumerating (attempt {attempt + 1}); auto-restarting ClubGG", flush=True)
                if not recover():
                    print("could not recover ClubGG"); sys.exit(1)
        else:
            print("gave up enumerating after repeated capture blocks"); sys.exit(1)
    else:
        members = load_live(pid)
        print(f"downline of {name} from {live_path(pid)}: {len(members)} member(s)", flush=True)
    if not members:
        print("no downline members found - nothing to collect"); return
    if "--enum-only" in sys.argv:
        return
    collect_stats(pid, members, start, end)


if __name__ == "__main__":
    main()
