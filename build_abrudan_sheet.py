r"""Build Abrudan's rakeback sheet (xlsx + html) via the shared owner_sheet
renderer.

One section: Abrudan's super agents (Rake/P&L reused from the managers report)
followed by his agent(s) (collected by abrudan_report.py). Rakeback % per
managers_config.ABRUDAN_SA_RAKEBACK / ABRUDAN_AGENTS. Includes the "Abrudan's
Profit" column (rake kept) and a summary whose ABRUDAN'S TOTAL FINAL PROFIT =
rake kept + 1/3 of the Bad Beat Jackpot. Zero-activity rows are omitted.
"""
import csv
from pathlib import Path

import managers_config as mc
import owner_sheet

ROOT = Path(__file__).parent


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_sa_rows(start, end):
    """Abrudan's super agents, Rake/P&L reused from the managers report."""
    raw = ROOT / "output" / f"managers_raw_{start}_{end}.csv"
    by_id = {}
    if raw.exists():
        for r in csv.DictReader(raw.open(encoding="utf-8")):
            by_id[r["id"]] = r
    out = []
    for sid, pct in mc.ABRUDAN_SA_RAKEBACK.items():
        r = by_id.get(sid, {})
        out.append({"id": sid,
                    "name": mc.ABRUDAN_NAMES.get(sid) or r.get("name") or sid,
                    "role": "super", "rake": num(r.get("rake")),
                    "pnl": num(r.get("profit_loss")), "pct": pct})
    return out


def load_agent_rows(start, end):
    """Abrudan's agents collected by abrudan_report.py."""
    ap = ROOT / "output" / f"abrudan_agents_{start}_{end}.csv"
    by_id = {}
    if ap.exists():
        for r in csv.DictReader(ap.open(encoding="utf-8")):
            by_id[r["id"]] = r
    out = []
    for aid, pct in mc.ABRUDAN_AGENTS.items():
        r = by_id.get(aid, {})
        out.append({"id": aid,
                    "name": mc.ABRUDAN_NAMES.get(aid) or r.get("name") or aid,
                    "role": "agent", "rake": num(r.get("rake")),
                    "pnl": num(r.get("profit_loss")), "pct": pct})
    return out


# Abrudan wants THREE separate documents: the complete table, then one file
# per 3-member group (same data). (file_stem, section title, member ids)
GROUP_DOCS = [
    ("abrudan_group1", "TheGermanGiant / Knikovski / PlayingCardsUsa",
     ["8637-7916", "6896-0336", "3200-8832"]),
    ("abrudan_group2", "AzizLaGuerr / PinotGrigio2026 / Imigor / Azem Bejta / HHH000",
     ["6985-1738", "3245-8417", "5906-5014", "3563-5971", "2914-2112"]),
]


def _build(start, end, stem, title, rows):
    # no owner-profit column / Paid checkbox (Paul-only); show all rows.
    bbj_third = owner_sheet.read_bbj_third(ROOT, start, end)
    return owner_sheet.build(
        "Abrudan", start, end,
        [{"title": title, "subtotal_label": "Subtotal", "rows": rows,
          "in_total": True}], bbj_third, zero_filter=False,
        owner_profit_col=False, paid_col=False, file_stem=stem)


def build(start, end):
    """Build all three Abrudan documents; returns the main sheet's path."""
    rows = load_sa_rows(start, end) + load_agent_rows(start, end)
    by_id = {r["id"]: r for r in rows}
    main = _build(start, end, "abrudan_report",
                  "Abrudan - Super Agents & Agent  (tipsback per entity)", rows)
    for stem, title, ids in GROUP_DOCS:
        _build(start, end, stem, title, [by_id[i] for i in ids if i in by_id])
    return main


if __name__ == "__main__":
    import sys
    from datetime import date
    build(date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]))
