r"""Scan the FULL member roster (the default "All" filter): every member's
name + their agent/SA (upline). Top-level members (managers / super-agents
with nobody above them) have no upline and are recorded as "-".

No detail pages are opened - this only scrolls the member list, OCRs each row
(name, ID, role + upline badge), and verifies the collected count against the
"Total members" number shown on the tab. Every processed frame is retained
under shots\roster_frames\ so the roster can be rebuilt offline (re-OCR
names/agents) with no capture cost. Output: output\clubgg_roster_<today>.csv.

Usage:
  python roster.py            # live scan (needs ClubGG + driver)
  python roster.py --reparse  # rebuild from saved frames, offline, no driver

Prerequisites (live scan): ClubGG open + driver.py running elevated.
"""
import csv
import re
import shutil
import sys
import time
from datetime import date
from pathlib import Path

from collect import (ROOT, SHOTS, CaptureBlocked, block_recovery,
                     driver_alive, goto_member_list, ocr_text, parse_rows,
                     scroll_list, send, shot)

# Every frame the sweep processes is kept here, so names/agents can be
# re-OCR'd offline (python roster.py --reparse) with zero capture cost.
FRAMES = ROOT / "shots" / "roster_frames"


def capture_blocked():
    """True if ClubGG has turned its anti-capture flag back on mid-run."""
    r = send({"action": "shot", "shot": str(SHOTS / "roster_affchk.png")})
    return r.get("affinity", 0) != 0


def write_roster(players, total, final_total):
    out = ROOT / "output" / f"clubgg_roster_{date.today().isoformat()}.csv"
    out.parent.mkdir(exist_ok=True)
    ordered = sorted(players.values(), key=lambda r: r["name"].lower())
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["player_id", "name", "agent"])
        for r in ordered:
            # top-level members (managers / super-agents) have no upline -> "-"
            w.writerow([r["id"], r["name"], r["upline"] or "-"])
    return out


def read_total(img_path):
    txt = ocr_text(img_path, (180, 318, 310, 356), scale=3)
    m = re.search(r"\d+", txt.replace(",", "").replace(" ", ""))
    if not m:
        raise RuntimeError(f"cannot read Total members from {txt!r}")
    return int(m.group())


def scroll_to_top():
    """Best-effort: swipe up until the visible rows stop changing. Never
    raises - returns the last screenshot regardless."""
    prev = None
    p = SHOTS / "roster_top.png"
    stable = 0
    for _ in range(60):
        send({"action": "swipe", "x1": 270, "y1": 300, "x2": 270, "y2": 950,
              "shot": str(p), "settle": 0.5})
        ids = tuple(r["id"] for r in parse_rows(p))
        if ids and ids == prev:
            stable += 1
            if stable >= 2:
                return p
        else:
            stable = 0
        prev = ids
    return p


def merge_row(players, r):
    """Insert/upgrade a row keyed by id, preferring non-empty name/agent.
    A player appears in several consecutive frames, so a field missed on one
    frame is often present on another - keep the best of each."""
    cur = players.get(r["id"])
    if cur is None:
        players[r["id"]] = dict(r)
        return True
    upgraded = False
    for k in ("name", "role", "upline"):
        if not cur.get(k) and r.get(k):
            cur[k] = r[k]
            upgraded = True
    return upgraded


# module-level frame counter so numbering is unique across passes
_frame_no = [0]


def fast_forward_past_seen(players, recover):
    """After a restart ClubGG reopens at the TOP of the list. Skip past the
    already-collected top region, then hand back to the fine scan. Uses a
    single moderate swipe per check (so it can't fly past unseen members) and,
    the moment an unseen member appears, backs up one swipe so the fine scan
    re-covers the boundary rows instead of skipping them."""
    prev = None
    for _ in range(250):
        try:
            # one ~4-row swipe keeps ~1 row of overlap - no rows fly past
            send({"action": "swipe", "x1": 270, "y1": 900, "x2": 270, "y2": 360})
            p = shot("roster_ff")
        except CaptureBlocked:
            if recover():
                prev = None
                continue
            raise
        rows = parse_rows(p)
        if any(r["id"] not in players for r in rows):
            # overshoot guard: step back up so the fine scan re-reads the
            # rows just above this frame (a skipped unseen member lives there)
            send({"action": "swipe", "x1": 270, "y1": 360, "x2": 270, "y2": 900})
            return shot("roster_ff")
        ids = tuple(r["id"] for r in rows)
        if ids and ids == prev:
            return p                       # bottom reached, all seen
        prev = ids
    return shot("roster_ff")


def scan_pass(players, list_shot, label, recover):
    """One sweep to the bottom of the list; adds rows to players and retains
    every frame under FRAMES. On a capture block it restarts ClubGG, fast-
    forwards past seen players, and continues. Terminates at the list bottom
    (a scroll that doesn't change the visible ids)."""
    prev_ids = None
    step = 0
    while True:
        _frame_no[0] += 1
        kept = FRAMES / f"{_frame_no[0]:04d}.png"
        try:
            shutil.copyfile(list_shot, kept)
        except OSError:
            kept = list_shot
        rows = parse_rows(kept)
        added = sum(merge_row(players, r) for r in rows)
        ids = tuple(r["id"] for r in rows)
        step += 1
        if added:
            print(f"  [{label}] {len(players)} players "
                  f"(+{added} at step {step})")
        if ids and ids == prev_ids:        # scroll no longer moves = bottom
            return list_shot
        if step > 400:                     # safety cap (guards live re-sort)
            return list_shot
        prev_ids = ids
        try:
            # small step => big overlap (each row in ~4 frames), so no row is
            # ever skipped and its id/name gets several OCR chances
            list_shot = scroll_list(px=200, name="roster_list")
        except CaptureBlocked:
            if not recover():
                raise
            list_shot = fast_forward_past_seen(players, recover)
            prev_ids = None


def reparse_offline():
    """Rebuild the roster purely from saved frames - no ClubGG/driver needed
    and no capture cost. Uses the same merge logic across all frames."""
    frames = sorted(FRAMES.glob("*.png"))
    if not frames:
        print(f"no saved frames in {FRAMES} - run a live scan first")
        sys.exit(1)
    print(f"reparsing {len(frames)} saved frames...")
    players = {}
    for fr in frames:
        for r in parse_rows(fr):
            merge_row(players, r)
    out = write_roster(players, len(players), len(players))
    unknown = [r["name"] or r["id"] for r in players.values()
               if not r["upline"]]
    noname = [r["id"] for r in players.values() if not r["name"]]
    print(f"reparsed {len(players)} players -> {out}")
    if noname:
        print(f"still no name for: {', '.join(noname)}")
    if unknown:
        print(f"still no agent for: {', '.join(unknown)}")


def main():
    if "--reparse" in sys.argv:
        reparse_offline()
        return
    if not driver_alive():
        print("ERROR: driver not running (see driver.py docstring)")
        sys.exit(2)
    # fresh frame set for this run so --reparse later uses only these frames
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def cli_emit(e):
        if e.get("kind") == "log":
            print("  " + e["msg"], flush=True)
        elif e.get("kind") == "blocked":
            print("  " + e.get("error", "blocked"), flush=True)
    recover = block_recovery(tab="All", emit=cli_emit)

    try:
        send({"action": "setwin"})
        list_shot = goto_member_list("All")
    except CaptureBlocked:
        list_shot = shot("roster_list") if recover() else None
    if list_shot is None:
        print("could not start the roster scan")
        return
    total = read_total(list_shot)
    print(f"Total members on tab: {total}", flush=True)

    players = {}
    final_total = total
    out = None
    try:
        # scan_pass runs to the list bottom, auto-restarting ClubGG and fast-
        # forwarding past seen members on a capture block. Repeat sweeps until
        # every member is collected or a whole pass adds nobody new.
        prev_count = -1
        for pass_no in range(1, 12):
            list_shot = scan_pass(players, list_shot, f"pass{pass_no}", recover)
            out = write_roster(players, total, total)
            print(f"pass {pass_no} done: {len(players)}/{total}", flush=True)
            if len(players) >= total:
                break
            if len(players) == prev_count:
                print(f"a full pass added nobody new - stopping at "
                      f"{len(players)}/{total}", flush=True)
                break
            prev_count = len(players)
            try:
                list_shot = scroll_to_top()
            except CaptureBlocked:
                if not recover():
                    break
                list_shot = shot("roster_list")

        try:
            final_total = read_total(goto_member_list("All"))
        except CaptureBlocked:
            pass
    finally:
        out = write_roster(players, total, final_total)

    noname = [r["id"] for r in players.values() if not r["name"]]
    print(f"\nDone: {len(players)} members in {time.time() - t0:.0f}s "
          f"(tab start={total} end={final_total})", flush=True)
    if len(players) not in (total, final_total):
        print(f"NOTE: collected {len(players)}, tab showed {total}/"
              f"{final_total} - rerun to fill the gap", flush=True)
    if noname:
        print(f"WARNING: no name for: {', '.join(noname)}", flush=True)
    print(f"roster: {out}", flush=True)

    # keep Paul's editable rakeback config in step with the fresh roster:
    # newly-detected SAs / CopilulNorocos members are added at the 60% default
    # (existing hand-edited rates are preserved).
    try:
        import paul_rakeback
        added, stale = paul_rakeback.sync(out)
        if added:
            print(f"rakeback config: added {len(added)} new entity(ies) at "
                  f"default {paul_rakeback.DEFAULT_PCT:g}% - edit "
                  f"{paul_rakeback.RAKEBACK_CSV}", flush=True)
        if stale:
            print(f"rakeback config: {len(stale)} entry(ies) no longer under "
                  f"Paul/CopilulNorocos (kept): {', '.join(stale[:8])}",
                  flush=True)
    except Exception as e:
        print(f"rakeback config sync skipped: {e}", flush=True)


if __name__ == "__main__":
    main()
