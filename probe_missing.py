r"""Probe specific member ids for a date range to find activity missing from the
managers report (reconciliation gap hunting). Role is auto-detected, so agents
use Agent Statistics and players use personal Game Statistics.

  python probe_missing.py 2026-08-31 2026-09-03 7826-7133 8914-8667 ...
"""
import sys
from datetime import date

import collect
from collect import CaptureBlocked, block_recovery, goto_member_list, send
import managers_report as mr
import paul_report as pr


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    ids = args[2:]
    if not collect.driver_alive():
        print("ERROR: driver not running"); sys.exit(2)
    recover = block_recovery(tab="All",
                             emit=lambda e: print("  " + e.get("msg", e.get("error", "")),
                                                  flush=True)
                             if e.get("kind") in ("log", "blocked") else None)
    try:
        send({"action": "setwin"}); goto_member_list("All")
    except CaptureBlocked:
        if not recover():
            return
    total = 0.0
    i = 0
    while i < len(ids):
        pid = ids[i]
        try:
            role, name, rake, pnl = pr.collect_submember(pid, mr.roster_name(pid),
                                                         start, end, f"pb{i:02d}")
            net = (rake or 0) + (pnl or 0)
            total += net
            print(f"[{i+1}/{len(ids)}] {role:6} {name or pid} ({pid}) "
                  f"rake={rake} pnl={pnl} net={net:,.2f}", flush=True)
            i += 1
        except CaptureBlocked:
            if not recover():
                break
        except Exception as e:  # noqa
            print(f"[{i+1}/{len(ids)}] SKIPPED {pid}: {e}", flush=True)
            i += 1
            try:
                goto_member_list("All")
            except Exception:
                if not recover():
                    break
    print(f"\nprobed total net = {total:,.2f}", flush=True)


if __name__ == "__main__":
    main()
