r"""Look up a club member's id by (partial) name via the Club Members search box.

  python lookup_member.py UFCfan            # prints every matching row: id, name, role, upline

Needs the elevated driver + ClubGG inside RomanianClub. Read-only; leaves the app
on the member list with the search cleared. Saves shots/collect/lookup_<name>.png
so the result can be confirmed visually if OCR mangles the name."""
import sys

import collect
from collect import (SHOTS, click, goto_member_list, parse_rows, send)


def lookup(name, tab="All"):
    send({"action": "setwin"})
    goto_member_list(tab)
    shot_path = SHOTS / f"lookup_{name}.png"
    click(270, 196, settle=0.3)                       # focus the search box
    send({"action": "type", "text": name, "clear": True,
          "shot": str(shot_path), "settle": 1.2})
    rows = parse_rows(shot_path)
    send({"action": "type", "text": "", "clear": True, "settle": 0.3})  # clear
    return rows, shot_path


if __name__ == "__main__":
    from collect import CaptureBlocked, block_recovery
    name = sys.argv[1]
    recover = block_recovery(tab="All", emit=lambda e: print("  " + e.get("msg", e.get("error", "")), flush=True)
                             if e.get("kind") in ("log", "blocked") else None)
    for attempt in range(6):                      # capture block -> auto-restart ClubGG and retry
        try:
            rows, p = lookup(name); break
        except CaptureBlocked:
            print(f"capture blocked (attempt {attempt + 1}); restarting ClubGG...", flush=True)
            if not recover():
                sys.exit("could not recover ClubGG")
    else:
        sys.exit("gave up after repeated capture blocks")
    print(f"search '{name}' -> {len(rows)} row(s)   (frame: {p})")
    for r in rows:
        print(f"  {r['id']}  {r['name']:<24} role={r['role'] or '-':<6} upline={r['upline'] or '-'}")
