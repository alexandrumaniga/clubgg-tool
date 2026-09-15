r"""Cristian Veres' downline sheet: every member under the super agent Cristian Veres
(5368-8498), collected individually (players via member stats, agents via Agent
Statistics), at the tipsback % in managers_config.VERES_MEMBERS (default 50%).

  python veres_report.py 2026-09-07 2026-09-13            # collect (resumable) + build
  python veres_report.py 2026-09-07 2026-09-13 --build    # rebuild the sheet only

Membership comes from Alex's Downline Players screenshots (output/downline_5368-8498_live.csv,
kept in step by hand) - the same file downline_report.py would write. Zero-activity rows are
omitted from the sheet ("those players that played").
"""
import csv
import sys
from datetime import date
from pathlib import Path

import managers_config as mc
import owner_sheet
import downline_report as dl

ROOT = Path(__file__).parent


def members():
    """id -> name from the live csv; pct from config (default VERES_DEFAULT_PCT)."""
    live = dl.live_path(mc.VERES_SA)
    if live.exists():
        names = {r["id"]: r["name"] for r in csv.DictReader(live.open(encoding="utf-8"))}
    else:
        names = {}
    for pid in mc.VERES_MEMBERS:
        names.setdefault(pid, mc.VERES_NAMES.get(pid, pid))
    return names


def rows(start, end):
    f = dl.stats_path(mc.VERES_SA, start, end)
    out = []
    if not f.exists():
        return out
    for r in csv.DictReader(f.open(encoding="utf-8")):
        if r["rake"] in ("", "ERR"):
            continue
        pct = mc.VERES_MEMBERS.get(r["id"], mc.VERES_DEFAULT_PCT)
        out.append({"id": r["id"], "name": mc.VERES_NAMES.get(r["id"]) or r["name"] or r["id"],
                    "role": {"agent": "agent", "super": "super"}.get(r["role"], "player"),
                    "rake": float(r["rake"]), "pnl": float(r["profit_loss"]), "pct": pct})
    return out


def build(start, end):
    sections = [{"title": "Cristian Veres - downline members  (tipsback per member)",
                 "subtotal_label": "Subtotal - Cristian Veres members", "rows": rows(start, end)}]
    return owner_sheet.build("Veres", start, end, sections, 0.0, zero_filter=True,
                             owner_profit_col=False, file_stem="veres_report")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    if "--build" not in sys.argv:
        import collect
        if not collect.driver_alive():
            print("ERROR: driver not running"); sys.exit(2)
        m = members()
        print(f"Cristian Veres downline to collect: {len(m)}", flush=True)
        dl.collect_stats(mc.VERES_SA, m, start, end)
    build(start, end)


if __name__ == "__main__":
    main()
