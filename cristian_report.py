r"""Cristian Veres report: every member under the super-agent Cristian Veres
(5368-8498), collected individually - an AGENT via Agent Statistics, a PLAYER
via personal Game-Statistics Custom - all at 100% tipsback. Standalone sheet
(cristian_veres_report_<range>.xlsx/.html) rendered by owner_sheet.

Usage:
  python cristian_report.py 2026-08-17 2026-08-23
  python cristian_report.py 2026-08-17 2026-08-23 --build-only

Prereqs (collection): ClubGG open + driver.py elevated. Per-member checkpoint
(cristian_submembers_<range>.csv) so a rerun resumes.
"""
import csv
import sys
from datetime import date
from pathlib import Path

import collect
from collect import CaptureBlocked, block_recovery, goto_member_list, send
import managers_report as mr
import paul_report as pp          # reuse collect_submember (role-detect + read)
import owner_sheet

ROOT = Path(__file__).parent
OWNER = "Cristian Veres"
AGENT_KEY = "cristianveres"       # roster 'agent' value, space/case-insensitive
FIELDS = ["role", "id", "name", "rake", "profit_loss"]


def sub_path(start, end):
    return ROOT / "output" / f"cristian_submembers_{start}_{end}.csv"


def members():
    """(id, name) of every roster member whose agent is Cristian Veres."""
    files = sorted((ROOT / "output").glob("clubgg_roster_*.csv"))
    if not files:
        raise RuntimeError("no roster CSV found - run the roster loader first")
    rows = [r for r in csv.DictReader(files[-1].open(encoding="utf-8"))
            if r["agent"].replace(" ", "").lower() == AGENT_KEY]
    return [(r["player_id"], r["name"]) for r in rows]


def run(start, end):
    out = sub_path(start, end)
    out.parent.mkdir(exist_ok=True)
    done = {}
    if out.exists():
        done = {r["id"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
        print(f"resuming: {len(done)} already collected", flush=True)
    mem = members()
    print(f"Cristian Veres members to collect: {len(mem)}", flush=True)

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
    while i < len(mem):
        pid, name_hint = mem[i]
        if pid in done:
            i += 1
            continue
        tag = f"cv{i:02d}"
        try:
            role, name, rake, pnl = pp.collect_submember(pid, name_hint,
                                                          start, end, tag)
            rec = {"role": role, "id": pid, "name": name,
                   "rake": rake, "profit_loss": pnl}
            w.writerow(rec)
            f.flush()
            done[pid] = rec
            print(f"[{len(done)}/{len(mem)}] {role} {name} ({pid}) "
                  f"rake={rake} pnl={pnl}", flush=True)
            i += 1
        except CaptureBlocked:
            if not recover():
                break
        except Exception as e:
            print(f"  SKIPPED {pid}: {e}", flush=True)
            w.writerow({"role": "ERR", "id": pid,
                        "name": name_hint or mr.roster_name(pid),
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


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _downline_lookup():
    """From the latest roster: how many members list each name as their upline
    (i.e. which agents actually have a downline), plus id->name."""
    from collections import Counter
    files = sorted((ROOT / "output").glob("clubgg_roster_*.csv"))
    counts, rmap = Counter(), {}
    if files:
        for r in csv.DictReader(files[-1].open(encoding="utf-8")):
            rmap[r["player_id"]] = r["name"]
            counts[r["agent"].replace(" ", "").lower()] += 1
    return counts, rmap


def build(start, end):
    subs = {}
    p = sub_path(start, end)
    if p.exists():
        subs = {r["id"]: r for r in csv.DictReader(p.open(encoding="utf-8"))}
    op = ROOT / "output" / f"cristian_agent_ownplay_{start}_{end}.csv"
    own = {}
    if op.exists():
        own = {r["id"]: r for r in csv.DictReader(op.open(encoding="utf-8"))}
    counts, rmap = _downline_lookup()

    def has_downline(pid):
        nm = rmap.get(pid, subs.get(pid, {}).get("name", ""))
        return counts.get(nm.replace(" ", "").lower(), 0) > 0

    rows = []
    for pid, r in subs.items():
        role = r.get("role", "player")
        # RULE: agent WITH a real downline -> Agent Statistics (its downline
        # aggregate). Agent WITHOUT a downline -> personal Game Statistics
        # (Agent Statistics is truncated for mid-week promotions). Players are
        # already their personal Game Statistics.
        if role in ("agent", "super") and not has_downline(pid) and pid in own \
                and own[pid].get("rake") not in (None, "ERR"):
            rake = _num(own[pid]["rake"])
            pnl = _num(own[pid]["profit_loss"])
        else:
            rake = _num(r.get("rake"))
            pnl = _num(r.get("profit_loss"))
        rows.append({"id": pid, "name": r.get("name") or pid, "role": role,
                     "rake": rake, "pnl": pnl, "pct": 100})
    sections = [{"title": "Cristian Veres - all members (100% tipsback)",
                 "subtotal_label": "Total", "rows": rows, "in_total": True}]
    return owner_sheet.build(OWNER, start, end, sections, 0.0,
                             zero_filter=False, owner_profit_col=False,
                             paid_col=False, file_stem="cristian_veres_report")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    if "--build-only" not in sys.argv:
        if not collect.driver_alive():
            print("ERROR: driver not running")
            sys.exit(2)
        run(start, end)
    build(start, end)
