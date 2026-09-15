r"""Scan the club member list on a filter tab (SA / Manager / Agent) and dump
every row (id, name, upline) so we can see the CURRENT structure without a full
roster sweep. Flags entities not present in managers_config.

  python scan_sas.py SA
  python scan_sas.py Manager
"""
import sys

import collect
from collect import (CaptureBlocked, block_recovery, goto_member_list,
                     parse_rows, scroll_list, send, shot)
import managers_config as mc


def main():
    tab = sys.argv[1] if len(sys.argv) > 1 else "SA"
    if not collect.driver_alive():
        print("ERROR: driver not running"); sys.exit(2)
    recover = block_recovery(tab=tab,
                             emit=lambda e: print("  " + e.get("msg", e.get("error", "")),
                                                  flush=True)
                             if e.get("kind") in ("log", "blocked") else None)
    try:
        send({"action": "setwin"})
        p = goto_member_list(tab)
    except CaptureBlocked:
        if not recover():
            return
        p = shot("sascan")

    seen = {}
    prev = None
    stable = 0
    for _ in range(60):
        try:
            p = shot("sascan")
        except CaptureBlocked:
            if not recover():
                break
            continue
        rows = parse_rows(p)
        for r in rows:
            if r["id"] and r["id"] not in seen:
                seen[r["id"]] = (r.get("name", ""), r.get("upline", ""))
        ids = tuple(r["id"] for r in rows)
        if ids and ids == prev:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        prev = ids
        try:
            scroll_list(px=220, name="sascan")
        except CaptureBlocked:
            if not recover():
                break

    tracked = (set(mc.SA_TO_MANAGER) | set(mc.paul_group_ids())
               | set(mc.MANAGERS.values()) | set(mc.MANAGER_EXTRA_PLAYERS))
    print(f"\n=== {tab} tab: {len(seen)} entities ===")
    for pid, (name, up) in sorted(seen.items(), key=lambda kv: kv[1][0].lower()):
        mark = "" if pid in tracked else "   <-- NOT IN CONFIG"
        print(f"  {pid}  {name:22} upline={up or '-':16}{mark}")
    missing = [(p, n, u) for p, (n, u) in seen.items() if p not in tracked]
    print(f"\nNOT in managers_config: {len(missing)}")
    for p, n, u in missing:
        print(f"   {p}  {n}  (upline {u or '-'})")


if __name__ == "__main__":
    main()
