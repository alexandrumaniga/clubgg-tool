r"""Build the general-club-managers-results Excel sheet from the raw data
collected by managers_report.py: one table per manager (manager row + their
super-agent rows) and a summary of each manager's combined profit-after-rakeback
+ 1/3 of the club Bad Beat Jackpot.

Columns per row: Name | Rake | Profit & Loss | Profit after Rakeback (100%)
  where Profit after Rakeback = Profit&Loss + Rake  (the member gets 100% of
  their rake back). The manager summary uses the after-rakeback figure.
Bad Beat Jackpot = Club Profit&Loss + Fee; its 1/3 share is added to each
manager as a POSITIVE amount.
"""
import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import managers_config as mc

ROOT = Path(__file__).parent

# Knobs (a variant document sets these before calling build):
ALIASES = ("Veres", "Paul", "Abrudan")          # tables, in this order
SUMMARY_ORDER = ("Paul", "Veres", "Abrudan")    # manager-profit summary order
BBJ_SHARES = 3                                  # BBJ split into this many parts
BBJ_PARTS = {}                                  # alias -> how many parts that manager gets (default 1)
EXTRA_ROWS = {}                                 # alias -> [ {name, rake, pnl} ] appended to that manager's table
STEM = "managers_report"                        # output file stem
DROP_IDS = set()                                # member ids left out entirely

HEADER_FILL = PatternFill("solid", fgColor="1F2A3C")
HEADER_FONT = Font(bold=True, color="FFFFFF")
MGR_FILL = PatternFill("solid", fgColor="FFF2CC")
TITLE_FONT = Font(bold=True, size=13, color="1F2A3C")
POS_FONT = Font(color="1E7B34", bold=True)
NEG_FONT = Font(color="B3261E", bold=True)
TOT_FILL = PatternFill("solid", fgColor="E8ECF1")
THIN = Side(style="thin", color="D5DBE1")
NUM = "#,##0.00"


def money(cell, v, color=False):
    cell.value = None if v is None else round(v, 2)
    cell.number_format = NUM
    cell.alignment = Alignment(horizontal="right", indent=1)
    if color and isinstance(v, (int, float)):
        cell.font = POS_FONT if v >= 0 else NEG_FONT


def build(start, end):
    raw = ROOT / "output" / f"managers_raw_{start}_{end}.csv"
    rows = list(csv.DictReader(raw.open(encoding="utf-8")))

    def num(s):
        try:
            return float(s)
        except (TypeError, ValueError):
            return None

    data = {}
    for r in rows:
        data[r["id"]] = {"name": mc.NAME_OVERRIDES.get(r["id"], r["name"]), "rake": num(r["rake"]),
                         "pnl": num(r["profit_loss"])}

    bp = ROOT / "output" / f"managers_bbj_{start}_{end}.txt"
    bbj_pnl = bbj_fee = None
    if bp.exists():
        for line in bp.read_text(encoding="utf-8").splitlines():
            if line.startswith("pnl="):
                bbj_pnl = float(line.split("=")[1])
            elif line.startswith("fee="):
                bbj_fee = float(line.split("=")[1])
    bbj = round((bbj_pnl or 0) + (bbj_fee or 0), 2)     # P&L + Fee
    bbj_third = round(abs(bbj) / BBJ_SHARES, 2)         # added as positive
    for d in DROP_IDS:
        data.pop(d, None)

    def after_rb(rec):
        """profit after 100% rakeback = P&L + Rake."""
        return round((rec.get("pnl") or 0) + (rec.get("rake") or 0), 2)

    wb = Workbook()
    ws = wb.active
    ws.title = "Managers"
    for i, wdt in enumerate((30, 15, 16, 20), 1):
        ws.column_dimensions[get_column_letter(i)].width = wdt

    ws.merge_cells("A1:D1")
    ws["A1"] = f"Club Managers Results   |   {start} to {end}"
    ws["A1"].font = TITLE_FONT
    r = 3

    HEADERS = ("Name", "Tips", "Profit & Loss", "Profit after TB (100%)")
    combined = {}   # alias -> sum of after-rakeback (manager + SAs)
    for alias in ALIASES:
        mid = mc.MANAGERS[alias]
        mgr = data.get(mid, {"name": "", "rake": None, "pnl": None})
        ws.merge_cells(f"A{r}:D{r}")
        ws.cell(r, 1, f"{alias}   ({mgr.get('name', '')})").font = \
            Font(bold=True, size=12)
        r += 1
        for c, h in enumerate(HEADERS, 1):
            cell = ws.cell(r, c, h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
        r += 1
        t_rake = t_pnl = t_rb = 0.0

        def emit_row(rec, label, fill=None):
            nonlocal r, t_rake, t_pnl, t_rb
            ws.cell(r, 1, label)
            money(ws.cell(r, 2), rec.get("rake"))
            money(ws.cell(r, 3), rec.get("pnl"), color=True)
            rb = after_rb(rec)
            money(ws.cell(r, 4), rb, color=True)
            if fill:
                for c in range(1, 5):
                    ws.cell(r, c).fill = fill
            t_rake += rec.get("rake") or 0
            t_pnl += rec.get("pnl") or 0
            t_rb += rb
            r += 1

        grouped = set(mc.paul_group_ids()) if alias == mc.COHIBA_GROUP_MANAGER \
            else set()
        emit_row(mgr, f"{mgr.get('name', '')}  (manager)", MGR_FILL)
        for sid in mc.sas_of(alias):
            if sid in grouped:                     # shown inside a group row
                continue
            sa = data.get(sid, {"name": sid, "rake": None, "pnl": None})
            emit_row(sa, sa.get("name", "") or sid)
        for pid in mc.extra_players_of(alias):     # players directly under mgr
            pl = data.get(pid, {"name": pid, "rake": None, "pnl": None})
            emit_row(pl, (pl.get("name", "") or pid) + "  (player)")
        if alias == mc.COHIBA_GROUP_MANAGER:       # Paul super-agent groups (summed)
            for g in mc.PAUL_SA_GROUPS:
                crows = [data[c] for c in g["ids"] if c in data]
                if crows:
                    emit_row({"rake": sum(r.get("rake") or 0 for r in crows),
                              "pnl": sum(r.get("pnl") or 0 for r in crows)},
                             g["name"])
        for x in EXTRA_ROWS.get(alias, []):        # variant documents: rows moved under this manager
            emit_row(x, x["name"])
        # subtotal
        ws.cell(r, 1, "Subtotal").font = Font(bold=True)
        money(ws.cell(r, 2), round(t_rake, 2))
        money(ws.cell(r, 3), round(t_pnl, 2), color=True)
        money(ws.cell(r, 4), round(t_rb, 2), color=True)
        for c in range(1, 5):
            ws.cell(r, c).fill = TOT_FILL
            ws.cell(r, c).border = Border(top=THIN)
        combined[alias] = round(t_rb, 2)
        r += 2

    # --- Bad Beat Jackpot ---
    ws.merge_cells(f"A{r}:D{r}")
    ws.cell(r, 1, "Bad Beat Jackpot (Club Data: Profit&Loss + Fee)").font = \
        Font(bold=True, size=12)
    r += 1
    for label, val in (("Club Profit & Loss", bbj_pnl), ("Club Fee", bbj_fee),
                       ("Bad Beat Jackpot (P&L + Fee)", bbj),
                       (f"BBJ / {BBJ_SHARES} added to each (as positive)", bbj_third)):
        ws.cell(r, 1, label)
        money(ws.cell(r, 2), val)
        r += 1
    r += 1

    # --- manager profit summary (uses after-rakeback) ---
    ws.merge_cells(f"A{r}:D{r}")
    ws.cell(r, 1, f"Manager Profit  (combined profit-after-tipsback + 1/{BBJ_SHARES} "
                  "Bad Beat Jackpot)").font = Font(bold=True, size=12)
    r += 1
    for c, h in enumerate(("Manager", "Combined after TB", f"+ BBJ/{BBJ_SHARES}",
                           "Final Profit"), 1):
        cell = ws.cell(r, c, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    r += 1
    for alias in [a for a in SUMMARY_ORDER if a in ALIASES]:
        base = combined.get(alias, 0.0)
        share = round(bbj_third * BBJ_PARTS.get(alias, 1), 2)
        ws.cell(r, 1, f"{alias} Profit" + (f"  ({BBJ_PARTS[alias]} parts of BBJ)" if BBJ_PARTS.get(alias, 1) != 1 else "")).font = Font(bold=True)
        money(ws.cell(r, 2), base, color=True)
        money(ws.cell(r, 3), share)
        money(ws.cell(r, 4), round(base + share, 2), color=True)
        r += 1

    outp = ROOT / "output" / f"{STEM}_{start}_{end}.xlsx"
    try:
        wb.save(outp)
    except PermissionError:                       # file open in Excel
        outp = outp.with_name(outp.stem + "_rev.xlsx")
        wb.save(outp)
    print(f"saved {outp}")
    build_html(start, end, data, combined, bbj_pnl, bbj_fee, bbj, bbj_third)
    return outp


def _m(v):
    """Format a money value as a coloured HTML cell."""
    if v is None:
        return '<td class="num"></td>'
    cls = "pos" if v >= 0 else "neg"
    return f'<td class="num {cls}">{v:,.2f}</td>'


def build_html(start, end, data, combined, bbj_pnl, bbj_fee, bbj, bbj_third):
    """Self-contained HTML copy of the report - opens in any browser."""
    def after_rb(rec):
        return round((rec.get("pnl") or 0) + (rec.get("rake") or 0), 2)

    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<title>Club Managers Results {start} to {end}</title><style>
body{{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;background:#0f141b;
color:#e6edf3;margin:24px}} h1{{font-size:20px}} h2{{font-size:16px;margin-top:26px}}
table{{border-collapse:collapse;width:100%;max-width:760px;margin:6px 0 18px}}
th,td{{padding:7px 12px;border-bottom:1px solid #2a3644;text-align:left}}
th{{background:#1f2a3c;color:#fff}} td.num{{text-align:right;
font-variant-numeric:tabular-nums}} tr.mgr td{{background:#2a2410}}
tr.sub td{{background:#1e2733;font-weight:600;border-top:2px solid #3a4a5c}}
.pos{{color:#3fb950}} .neg{{color:#f0645a}} .final td{{font-weight:700}}
caption{{text-align:left;font-weight:700;font-size:15px;padding:6px 0}}
</style></head><body>
<h1>Club Managers Results &nbsp;|&nbsp; {start} to {end}</h1>"""]

    for alias in ALIASES:
        mid = mc.MANAGERS[alias]
        mgr = data.get(mid, {"name": "", "rake": None, "pnl": None})
        parts.append(f'<h2>{alias} ({mgr.get("name","")})</h2><table>'
                     '<tr><th>Name</th><th>Tips</th><th>Profit &amp; Loss</th>'
                     '<th>Profit after TB (100%)</th></tr>')
        t_rake = t_pnl = t_rb = 0.0

        def row(rec, label, cls=""):
            nonlocal t_rake, t_pnl, t_rb
            rb = after_rb(rec)
            t_rake += rec.get("rake") or 0
            t_pnl += rec.get("pnl") or 0
            t_rb += rb
            return (f'<tr class="{cls}"><td>{label}</td>{_m(rec.get("rake"))}'
                    f'{_m(rec.get("pnl"))}{_m(rb)}</tr>')

        grouped = set(mc.paul_group_ids()) if alias == mc.COHIBA_GROUP_MANAGER \
            else set()
        parts.append(row(mgr, f'{mgr.get("name","")} (manager)', "mgr"))
        for sid in mc.sas_of(alias):
            if sid in grouped:
                continue
            sa = data.get(sid, {"name": sid, "rake": None, "pnl": None})
            parts.append(row(sa, sa.get("name", "") or sid))
        for pid in mc.extra_players_of(alias):     # players directly under mgr
            pl = data.get(pid, {"name": pid, "rake": None, "pnl": None})
            parts.append(row(pl, (pl.get("name", "") or pid) + " (player)"))
        if alias == mc.COHIBA_GROUP_MANAGER:       # Paul super-agent groups (summed)
            for g in mc.PAUL_SA_GROUPS:
                crows = [data[c] for c in g["ids"] if c in data]
                if crows:
                    parts.append(row({"rake": sum(r.get("rake") or 0 for r in crows),
                                      "pnl": sum(r.get("pnl") or 0 for r in crows)},
                                     g["name"]))
        for x in EXTRA_ROWS.get(alias, []):        # variant documents: rows moved under this manager
            parts.append(row(x, x["name"]))
        parts.append(f'<tr class="sub"><td>Subtotal</td>{_m(round(t_rake,2))}'
                     f'{_m(round(t_pnl,2))}{_m(round(t_rb,2))}</tr></table>')

    parts.append('<h2>Bad Beat Jackpot (Club Data: Profit&amp;Loss + Fee)</h2>'
                 '<table>'
                 f'<tr><td>Club Profit &amp; Loss</td>{_m(bbj_pnl)}</tr>'
                 f'<tr><td>Club Fee</td>{_m(bbj_fee)}</tr>'
                 f'<tr><td>Bad Beat Jackpot (P&amp;L + Fee)</td>{_m(bbj)}</tr>'
                 f'<tr><td>BBJ / {BBJ_SHARES} added to each (as positive)</td>'
                 f'<td class="num">{bbj_third:,.2f}</td></tr></table>')

    parts.append(f'<h2>Manager Profit (combined profit-after-tipsback + 1/{BBJ_SHARES} '
                 'Bad Beat Jackpot)</h2><table>'
                 f'<tr><th>Manager</th><th>Combined after TB</th><th>+ BBJ/{BBJ_SHARES}</th>'
                 '<th>Final Profit</th></tr>')
    for alias in [a for a in SUMMARY_ORDER if a in ALIASES]:
        base = combined.get(alias, 0.0)
        share = round(bbj_third * BBJ_PARTS.get(alias, 1), 2)
        lbl = f"{alias} Profit" + (f" ({BBJ_PARTS[alias]} parts of BBJ)" if BBJ_PARTS.get(alias, 1) != 1 else "")
        parts.append(f'<tr class="final"><td>{lbl}</td>{_m(base)}'
                     f'<td class="num">{share:,.2f}</td>'
                     f'{_m(round(base + share, 2))}</tr>')
    parts.append("</table></body></html>")

    outh = ROOT / "output" / f"{STEM}_{start}_{end}.html"
    outh.write_text("\n".join(parts), encoding="utf-8")
    print(f"saved {outh}")
    return outh


if __name__ == "__main__":
    import sys
    from datetime import date
    build(date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]))
