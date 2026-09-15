r"""Variant of the managers document requested by Alex (2026-09-14):
Veres is removed entirely (manager Veresss AND the super agent Cristian Veres), and every
member of Cristian Veres' downline who PLAYED this week is listed under Abrudan at full
(100%) tipsback, i.e. Profit after TB = P&L + Tips like every other row. Only Paul and
Abrudan appear; the Bad Beat Jackpot is split in 3 parts: 2 to Abrudan, 1 to Paul (Craciunas).

  python build_managers_novers.py 2026-09-07 2026-09-14

Needs managers_raw_<range>.csv (managers run) and downline_5368-8498_<range>.csv (veres_report.py).
Output: output/managers_report_novers_<range>.{xlsx,html}
"""
import csv
import sys
from datetime import date
from pathlib import Path

import build_managers_sheet as bms
import managers_config as mc

ROOT = Path(__file__).parent


def veres_players(start, end):
    f = ROOT / "output" / f"downline_{mc.VERES_SA}_{start}_{end}.csv"
    if not f.exists():
        raise SystemExit(f"missing {f} - run veres_report.py first")
    out = []
    for r in csv.DictReader(f.open(encoding="utf-8")):
        if r["rake"] in ("", "ERR"):
            continue
        rake, pnl = float(r["rake"]), float(r["profit_loss"])
        if not rake and not pnl:
            continue                                  # only those who played
        name = mc.VERES_NAMES.get(r["id"]) or r["name"] or r["id"]
        out.append({"name": f"{name}  (from Cristian Veres, {r['role']})", "rake": rake, "pnl": pnl})
    return out


def build(start, end):
    bms.ALIASES = ("Paul", "Abrudan")
    bms.SUMMARY_ORDER = ("Paul", "Abrudan")
    bms.BBJ_SHARES = 3                      # BBJ in 3 parts: 2 to Abrudan, 1 to Paul (Craciunas) - Alex 2026-09-14
    bms.BBJ_PARTS = {"Abrudan": 2, "Paul": 1}
    bms.STEM = "managers_report_novers"
    bms.DROP_IDS = {mc.MANAGERS["Veres"], mc.VERES_SA}
    moved = veres_players(start, end)
    bms.EXTRA_ROWS = {"Abrudan": moved}
    print(f"moved under Abrudan at 100% TB: {len(moved)} Cristian Veres member(s) who played")
    return bms.build(start, end)


if __name__ == "__main__":
    build(date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]))
