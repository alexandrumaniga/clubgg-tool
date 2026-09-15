r"""Enumerate CopilulNorocos' LIVE downline via the app's
Super Agent Management -> Downline Management list, and diff it against the
members currently in his sheet (paul_submembers_<range>.csv, i.e. roster
upline==CopilulNorocos + extras).

Writes output/copil_downline_live.csv (id,name) and prints the delta.
Needs ClubGG + driver.py elevated. Restarts ClubGG first for a fresh capture
budget, and recovers from capture blocks mid-scroll by re-opening the list.
"""
import csv
import glob
import re
import sys
from pathlib import Path

import collect
from collect import (CaptureBlocked, click, enter_club, goto_member_list,
                     ocr_lines, search_open, send, send_once, shot)

ROOT = Path(__file__).parent
PID = "2671-5435"

# The ID label + number is OCR'd loosely: 'ID' may be 'lD'/'1D', and the 8
# digits often carry stray spaces/dashes (e.g. '(ID 3548-51 79)'). Match an
# ID-ish prefix inside a paren, grab the whole digit blob, then keep 8 digits.
ID_RE = re.compile(r"\(\s*[Iil1|]?[dD][\s:.]*([0-9][0-9\s\-]{5,12}[0-9])")
_SKIP = ("clubgg", "downline", "search member", "total downline",
         "copilulnorocos", "ccwi", "member detail", "edit downline",
         "alias", "fee")


def norm_id(raw):
    d = re.sub(r"\D", "", raw)
    return f"{d[:4]}-{d[4:8]}" if len(d) >= 8 else raw.strip()


def parse_downline(path):
    """Yield (id, name) for each member row on a Downline Players frame. The
    name is the last plausible text line seen above the '(ID ...)' line."""
    out = []
    last_name = ""
    for y, x, t in ocr_lines(path):
        s = t.strip()
        if not s:
            continue
        m = ID_RE.search(s)
        if m:
            out.append((norm_id(m.group(1)), last_name))
            last_name = ""
            continue
        sl = s.lower()
        if any(k in sl for k in _SKIP) or sl in ("sa", "player", "agent"):
            continue
        last_name = s
    return out


def open_downline():
    """From the member list, open CopilulNorocos -> Downline Management.
    Returns the first list screenshot."""
    p = search_open(PID, "CopilulNorocos", "dl")
    if p is None:
        raise RuntimeError("CopilulNorocos not found via search")
    # one swipe brings 'Downline Management' (first row of SA Management) up
    send({"action": "swipe", "x1": 270, "y1": 820, "x2": 270, "y2": 340,
          "shot": str(collect.SHOTS / "dl_sm.png"), "settle": 0.7})
    path = collect.SHOTS / "dl_sm.png"
    labels = [(int(y), int(x), t.lower()) for y, x, t in ocr_lines(path)]
    # 'Downline Management' (first row of Super Agent Management) sits one row
    # (~64px) above 'Super Agent Statistics'; OCR reads Statistics reliably but
    # often not the Downline row, so anchor off Statistics and tap the row text.
    for y, x, tl in labels:
        if "downl" in tl and "manag" in tl and x < 320:
            return click(200, y, name="dl_open", settle=1.6)
    for y, x, tl in labels:
        if "agent" in tl and "statistic" in tl and x < 320:
            return click(200, y - 64, name="dl_open", settle=1.6)
    print("  anchor not found; left-column labels seen:", flush=True)
    for y, x, tl in labels:
        if x < 320 and tl.strip():
            print(f"    y={y:4} x={x:4}  {tl}", flush=True)
    raise RuntimeError("Downline Management row not found")


def restart_and_open():
    send_once({"action": "restartgg"}, timeout=280)
    send({"action": "setwin"})
    enter_club("RomanianClub")
    goto_member_list("All")
    return open_downline()


def read_total(path):
    """'Total Downline Players' count shown on the list page, else None."""
    lines = ocr_lines(path)
    for i, (y, x, t) in enumerate(lines):
        if "total downline" in t.lower():
            # the number is usually the next line
            for yy, xx, tt in lines:
                m = re.fullmatch(r"\s*(\d{1,3})\s*", tt)
                if m and abs(int(yy) - int(y)) < 60:
                    return int(m.group(1))
    return None


def scan(members, target=None, step=136):
    """Scroll the open Downline Players list, merging (id,name) into `members`.
    Steps ~1 row at a time so every row passes through the readable centre of
    the screen; `step` varies per pass so a row whose ID was OCR-dropped lands
    at a fresh y next time. Stops at the target count, or when genuinely stuck."""
    no_progress = 0
    prev = None
    for _ in range(90):
        p = shot("dl_list")
        if target is None:
            target = read_total(p)
        before = len(members)
        rows = parse_downline(p)
        for pid, name in rows:
            if pid and (pid not in members or not members[pid]):
                members[pid] = name or members.get(pid, "")
        ids = tuple(pid for pid, _ in rows)
        if len(members) == before and ids == prev:
            no_progress += 1
        else:
            no_progress = 0
        prev = ids
        if target and len(members) >= target:
            return
        if no_progress >= 14:           # truly stuck at the bottom
            return
        send({"action": "swipe", "x1": 270, "y1": 860, "x2": 270,
              "y2": 860 - step, "shot": str(collect.SHOTS / "dl_list.png"),
              "settle": 0.6})


def scroll_top():
    """Swipe back up to the top of the Downline Players list."""
    for _ in range(30):
        send({"action": "swipe", "x1": 270, "y1": 340, "x2": 270, "y2": 900,
              "shot": str(collect.SHOTS / "dl_top.png"), "settle": 0.4})


def collect_downline():
    members = {}
    print("restarting ClubGG for a clean capture budget...", flush=True)
    try:
        restart_and_open()
    except CaptureBlocked:
        restart_and_open()
    print("Downline Management opened; scanning...", flush=True)
    target = None
    # larger steps complete a whole pass within the ~100-shot capture budget
    # (no mid-pass block); varying them shifts where each row is cut/rendered,
    # giving OCR-dropped IDs a fresh y on the next pass.
    steps = [240, 210, 285, 190, 265, 225]
    fruitless = 0
    # up to 6 full top->bottom passes; re-OCR fills IDs missed on earlier passes
    for pass_no in range(1, 7):
        before = len(members)
        try:
            scan(members, target, steps[(pass_no - 1) % len(steps)])
        except CaptureBlocked:
            print(f"  capture blocked at {len(members)}; restarting & resuming",
                  flush=True)
            restart_and_open()
            continue
        t = read_total(shot("dl_after"))
        target = target or t
        print(f"  pass {pass_no}: {len(members)}"
              f"{'/' + str(target) if target else ''} collected", flush=True)
        if target and len(members) >= target:
            break
        fruitless = fruitless + 1 if len(members) == before else 0
        if fruitless >= 2:               # two varied passes added nobody new
            break
        try:
            scroll_top()
        except CaptureBlocked:
            restart_and_open()
    return members


def sheet_members():
    """id -> name currently in CopilulNorocos' sheet (latest submembers CSV)."""
    files = sorted(glob.glob(str(ROOT / "output" / "paul_submembers_*.csv")))
    rows = list(csv.DictReader(open(files[-1], encoding="utf-8")))
    return {r["id"]: r["name"] for r in rows}, files[-1]


def main():
    if not collect.driver_alive():
        print("ERROR: driver not running"); sys.exit(2)
    live = collect_downline()
    out = ROOT / "output" / "copil_downline_live.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id", "name"])
        for pid, name in sorted(live.items()):
            w.writerow([pid, name])
    sheet, sheet_file = sheet_members()

    print(f"\n=== LIVE downline (app): {len(live)} members -> {out}", flush=True)
    print(f"=== SHEET ({Path(sheet_file).name}): {len(sheet)} members", flush=True)

    missing = {pid: n for pid, n in live.items() if pid not in sheet}
    extra = {pid: n for pid, n in sheet.items() if pid not in live}
    print(f"\n--- IN APP DOWNLINE BUT NOT IN SHEET ({len(missing)}): ---")
    for pid, n in sorted(missing.items()):
        print(f"   {pid}  {n}")
    print(f"\n--- IN SHEET BUT NOT IN APP DOWNLINE ({len(extra)}): ---")
    for pid, n in sorted(extra.items()):
        print(f"   {pid}  {n}")


if __name__ == "__main__":
    main()
