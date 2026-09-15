r"""Build Paul's rakeback sheet (xlsx + html) via the shared owner_sheet
renderer.

Section 1: Paul's super agents (CopilulNorocos excluded) - Rake/P&L reused from
the managers report, rakeback % from the editable config.
Section 2: every member under CopilulNorocos collected by paul_report.py,
rakeback % from the editable config (default 60%).

Columns include "Paul's Profit" (the rake remainder Paul keeps) and a summary
whose PAUL'S TOTAL FINAL PROFIT = sum of rake kept + 1/3 of the Bad Beat
Jackpot. Zero-activity rows are omitted.
"""
import csv
from pathlib import Path

import managers_config as mc
import owner_sheet
import paul_rakeback as pr

ROOT = Path(__file__).parent


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _pct(cfg, pid, fallback):
    c = cfg.get(pid)
    if c and c["pct"] is not None:
        return c["pct"]
    return fallback


def load_sa_data(start, end):
    """Paul's super agents (config 'sa' group, PAUL_SA_RAKEBACK first), Rake/P&L
    reused from the managers report, rakeback % from the config."""
    raw = ROOT / "output" / f"managers_raw_{start}_{end}.csv"
    by_id = {}
    if raw.exists():
        for r in csv.DictReader(raw.open(encoding="utf-8")):
            by_id[r["id"]] = r
    cfg = pr.load()
    sa_ids = list(mc.PAUL_SA_RAKEBACK) + \
        [pid for pid, c in cfg.items()
         if c["group"] == "sa" and pid not in mc.PAUL_SA_RAKEBACK
         and pid not in set(mc.paul_group_ids())]   # grouped SAs show only as their group row
    out = []
    for sid in sa_ids:
        r = by_id.get(sid, {})
        out.append({"id": sid,
                    "name": r.get("name") or cfg.get(sid, {}).get("name") or sid,
                    "role": "super", "rake": num(r.get("rake")),
                    "pnl": num(r.get("profit_loss")),
                    "pct": _pct(cfg, sid, mc.PAUL_SA_RAKEBACK.get(sid,
                                                                 pr.DEFAULT_PCT))})
    # Paul super-agent groups: each is several SAs summed into one row (data
    # reused from managers_raw where they were collected), shown at its pct.
    for g in mc.PAUL_SA_GROUPS:
        crows = [by_id[c] for c in g["ids"] if c in by_id]
        if crows:
            out.append({"id": g["key"], "name": g["name"], "role": "super",
                        "rake": round(sum(num(r.get("rake")) or 0 for r in crows), 2),
                        "pnl": round(sum(num(r.get("profit_loss")) or 0 for r in crows), 2),
                        "pct": g["pct"]})
    return out


def load_submembers(start, end):
    """CopilulNorocos members collected by paul_report.py; rakeback % and the
    display name come from the editable config (config name wins - the one
    place to fix a garbled OCR name)."""
    sub = ROOT / "output" / f"paul_submembers_{start}_{end}.csv"
    cfg = pr.load()
    exclude = getattr(mc, "COPIL_EXCLUDE", set())
    out = []
    if sub.exists():
        for r in csv.DictReader(sub.open(encoding="utf-8")):
            if r["id"] in exclude:
                continue
            name = cfg.get(r["id"], {}).get("name") or r.get("name") or r["id"]
            # rakeback: config value if set, else the extra-member default
            # (e.g. KingTwoSuited 50%), else the flat CopilulNorocos default.
            default = mc.COPIL_EXTRA_MEMBERS.get(r["id"], mc.COPIL_SUBMEMBER_RAKEBACK)
            out.append({"id": r["id"], "name": name,
                        "role": r.get("role", "player"),
                        "rake": num(r.get("rake")), "pnl": num(r.get("profit_loss")),
                        "pct": _pct(cfg, r["id"], default)})
    return out


def build(start, end):
    try:                      # keep the config in step with the latest roster
        added, _ = pr.sync()
        if added:
            print(f"rakeback config: added {len(added)} new entity(ies) at "
                  f"default {pr.DEFAULT_PCT:g}% -> {pr.RAKEBACK_CSV}")
    except Exception as e:
        print(f"rakeback config sync skipped: {e}")

    sections = [
        {"title": "Paul - Super Agents  (tipsback per agent)",
         "subtotal_label": "Subtotal - Super Agents",
         "rows": load_sa_data(start, end)},
        {"title": "CopilulNorocos - Members  (tipsback per member)",
         "subtotal_label": "Subtotal - CopilulNorocos members",
         "rows": load_submembers(start, end)},
    ]
    bbj_third = owner_sheet.read_bbj_third(ROOT, start, end)
    return owner_sheet.build("Paul", start, end, sections, bbj_third,
                             zero_filter=True)


if __name__ == "__main__":
    import sys
    from datetime import date
    build(date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]))
