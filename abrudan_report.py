r"""Abrudan rakeback report.

The super agents (managers_config.ABRUDAN_SA_RAKEBACK) reuse the Rake/P&L
already collected by the managers report - no re-collection. Only the agents
in ABRUDAN_AGENTS (gerardsb) are collected here, via Agent Statistics for the
range. uucj1919 is excluded entirely.

Usage:
  python abrudan_report.py 2026-08-03 2026-08-09
  python abrudan_report.py 2026-08-03 2026-08-09 --build-only

Prereqs (collection): ClubGG open + driver.py elevated.
"""
import csv
import sys
from datetime import date
from pathlib import Path

import collect
from collect import (CaptureBlocked, block_recovery, click, goto_member_list,
                     ocr_text, search_open, send)
import managers_config as mc
import managers_report as mr

ROOT = Path(__file__).parent
FIELDS = ["role", "id", "name", "rake", "profit_loss"]


def agents_path(start, end):
    return ROOT / "output" / f"abrudan_agents_{start}_{end}.csv"


def collect_agent(pid, start, end, tag):
    """Read an entity's Fee(=rake) & P&L for the range. Prefers its Agent /
    Super-Agent Statistics; if it has no such page (i.e. it's a plain player),
    falls back to its personal Game-Statistics Custom range."""
    goto_member_list("All")
    p = search_open(pid, mr.roster_name(pid), tag)
    if p is None:
        raise RuntimeError(f"{pid} not found via search")
    name = ocr_text(p, (125, 108, 360, 140), scale=3).strip() or mr.roster_name(pid)
    try:
        mr.open_super_agent_statistics(tag)          # 'Agent Statistics' page
        rake, pnl = mr.read_agent_stats_custom(start, end, tag)
        click(25, 62, name=f"{tag}_b1", settle=1.0)  # stats -> detail
        click(25, 62, name=f"{tag}_b2", settle=1.0)  # detail -> list
    except RuntimeError:                             # no agent stats -> a player
        goto_member_list("All")                      # leave the scrolled detail
        p = search_open(pid, mr.roster_name(pid), f"{tag}p")   # re-open at top
        if p is None:
            raise RuntimeError(f"{pid} not found (player re-open)")
        rake, pnl = mr.read_member_custom_stats(p, start, end, tag)
        click(25, 62, name=f"{tag}_pb", settle=0.9)  # detail -> list
    return name, rake, pnl


def run(start, end):
    out = agents_path(start, end)
    out.parent.mkdir(exist_ok=True)
    done = {}
    if out.exists():
        done = {r["id"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
        print(f"resuming: {len(done)} agents already collected", flush=True)

    members = list(mc.ABRUDAN_AGENTS)             # ids to collect
    print(f"Abrudan agents to collect: {len(members)}", flush=True)

    recover = block_recovery(tab="All",
                             emit=lambda e: print("  " + e.get("msg",
                                 e.get("error", "")), flush=True)
                             if e.get("kind") in ("log", "blocked") else None)

    mode = "a" if done else "w"
    f = out.open(mode, newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if mode == "w":
        w.writeheader()

    try:
        send({"action": "setwin"})
        goto_member_list("All")
    except CaptureBlocked:
        if not recover():
            f.close()
            return

    i = 0
    while i < len(members):
        pid = members[i]
        if pid in done:
            i += 1
            continue
        tag = f"a{i:02d}"
        try:
            name, rake, pnl = collect_agent(pid, start, end, tag)
            rec = {"role": "agent", "id": pid, "name": name,
                   "rake": rake, "profit_loss": pnl}
            w.writerow(rec)
            f.flush()
            done[pid] = rec
            print(f"[{len(done)}/{len(members)}] agent {name} ({pid}) "
                  f"rake={rake} pnl={pnl}", flush=True)
            i += 1
        except CaptureBlocked:
            if not recover():
                break
        except Exception as e:
            print(f"  SKIPPED {pid}: {e}", flush=True)
            w.writerow({"role": "ERR", "id": pid, "name": mr.roster_name(pid),
                        "rake": "ERR", "profit_loss": "ERR"})
            f.flush()
            done[pid] = {"id": pid}
            i += 1
            try:
                goto_member_list("All")
            except Exception:
                if not recover():
                    break
    f.close()
    print("collection done", flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    if "--build-only" not in sys.argv:
        if not collect.driver_alive():
            print("ERROR: driver not running")
            sys.exit(2)
        run(start, end)
    import build_abrudan_sheet
    build_abrudan_sheet.build(start, end)
