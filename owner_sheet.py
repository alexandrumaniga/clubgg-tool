r"""Shared renderer for an owner's rakeback sheet (Paul, Abrudan, ...).

Given one or more sections of rows, writes an .xlsx + self-contained .html with
columns:

    Name | Role | Rake | Profit & Loss | Rakeback % | Profit after RB
    [ | <Owner>'s Profit ]   [ | Paid ]

where per row:
    Profit after RB   = P&L + (rakeback%/100) * Rake     (what the member keeps)
    <Owner>'s Profit  = (1 - rakeback%/100) * Rake        (rake remainder kept
                                                           by the owner)

The <Owner>'s Profit column and the Paid checkbox are optional (Paul uses them;
Abrudan does not). When the owner-profit column is shown, the summary ends with
    <OWNER>'S TOTAL FINAL PROFIT = sum of rake kept + 1/3 Bad Beat Jackpot;
otherwise the summary is just the total profit after rakeback.

Each row is a dict: {name, role, rake(float|None), pnl(float|None), pct(float)}.
Each section is {title, subtotal_label, rows}.
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HEADER_FILL = PatternFill("solid", fgColor="1F2A3C")
HEADER_FONT = Font(bold=True, color="FFFFFF")
SEC_FONT = Font(bold=True, size=12, color="1F2A3C")
TITLE_FONT = Font(bold=True, size=13, color="1F2A3C")
POS_FONT = Font(color="1E7B34", bold=True)
NEG_FONT = Font(color="B3261E", bold=True)
TOT_FILL = PatternFill("solid", fgColor="E8ECF1")
GRAND_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="D5DBE1")
NUM = "#,##0.00"
ROLE_LABEL = {"player": "Player", "agent": "Agent", "super": "Super Agent",
              "sa": "Super Agent", "ERR": "ERROR"}


def after_rb(rake, pnl, pct):
    """What the member keeps: P&L + rakeback% of Rake."""
    return round((pnl or 0) + (pct / 100.0) * (rake or 0), 2)


def owner_profit(rake, pct):
    """Rake remainder kept by the owner: (100 - rakeback%) of Rake."""
    return round((1 - pct / 100.0) * (rake or 0), 2)


def read_bbj_third(root, start, end):
    """1/3 of the Bad Beat Jackpot for the range, as a POSITIVE amount.
    BBJ = Club Profit&Loss + Fee (recomputed from the raw pnl/fee so a stale
    `bbj=` line in the file is ignored). 0.0 if the file is missing."""
    bp = Path(root) / "output" / f"managers_bbj_{start}_{end}.txt"
    if not bp.exists():
        return 0.0
    pnl = fee = 0.0
    for line in bp.read_text(encoding="utf-8").splitlines():
        if line.startswith("pnl="):
            pnl = float(line.split("=")[1])
        elif line.startswith("fee="):
            fee = float(line.split("=")[1])
    return round(abs(round(pnl + fee, 2)) / 3, 2)


def _drop_zero(rows):
    """Remove rows with no activity (rake 0 and P&L 0)."""
    return [r for r in rows if (r.get("rake") or 0) != 0 or (r.get("pnl") or 0) != 0]


# -------------------------------------------------------------------- Excel ---

def _money(cell, v, color=False):
    cell.value = None if v is None else round(v, 2)
    cell.number_format = NUM
    cell.alignment = Alignment(horizontal="right", indent=1)
    if color and isinstance(v, (int, float)):
        cell.font = POS_FONT if v >= 0 else NEG_FONT


def build(owner, start, end, sections, bbj_third, zero_filter=True,
          owner_profit_col=True, paid_col=True, file_stem=None):
    root = Path(__file__).parent
    stem = file_stem or f"{owner.lower()}_report"
    prof_col = f"{owner}'s Profit"
    C_NAME, C_ROLE, C_RAKE, C_PNL, C_PCT, C_RB = 1, 2, 3, 4, 5, 6
    headers = ["Name", "Role", "Tips", "Profit & Loss", "Tipsback %",
               "Profit after TB"]
    widths = [26, 12, 14, 16, 11, 16]
    col = 7
    C_PROF = C_PAID = None
    if owner_profit_col:
        C_PROF = col; col += 1; headers.append(prof_col); widths.append(16)
    if paid_col:
        C_PAID = col; col += 1; headers.append("Paid"); widths.append(8)
    ncols = len(headers)
    end_col = get_column_letter(ncols)
    summary_col = C_PROF if owner_profit_col else C_RB

    wb = Workbook()
    ws = wb.active
    ws.title = owner
    for i, wdt in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = wdt
    paid_dv = None
    if paid_col:
        paid_dv = DataValidation(type="list", formula1='"☐,☑"', allow_blank=True)
        paid_dv.prompt = "Tick when paid"
        ws.add_data_validation(paid_dv)

    ws.merge_cells(f"A1:{end_col}1")
    ws["A1"] = f"{owner} - Tipsback Results   |   {start} to {end}"
    ws["A1"].font = TITLE_FONT
    r = 3
    tot_rb = tot_prof = 0.0

    for sec in sections:
        rows = _drop_zero(sec["rows"]) if zero_filter else sec["rows"]
        ws.merge_cells(f"A{r}:{end_col}{r}")
        ws.cell(r, 1, sec["title"]).font = SEC_FONT
        r += 1
        for c, h in enumerate(headers, 1):
            cell = ws.cell(r, c, h)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
        r += 1
        s_rake = s_pnl = s_rb = s_prof = 0.0
        for rec in rows:
            rb = after_rb(rec["rake"], rec["pnl"], rec["pct"])
            ws.cell(r, C_NAME, rec["name"])
            ws.cell(r, C_ROLE, ROLE_LABEL.get(rec["role"], rec["role"])).alignment \
                = Alignment(horizontal="center")
            _money(ws.cell(r, C_RAKE), rec["rake"])
            _money(ws.cell(r, C_PNL), rec["pnl"], color=True)
            ws.cell(r, C_PCT, f"{rec['pct']:g}%").alignment = \
                Alignment(horizontal="center")
            _money(ws.cell(r, C_RB), rb, color=True)
            if owner_profit_col:
                op = owner_profit(rec["rake"], rec["pct"])
                _money(ws.cell(r, C_PROF), op, color=True)
                s_prof += op
            if paid_col:
                paid = ws.cell(r, C_PAID, "☐")
                paid.alignment = Alignment(horizontal="center")
                paid_dv.add(paid)
            s_rake += rec["rake"] or 0
            s_pnl += rec["pnl"] or 0
            s_rb += rb
            r += 1
        ws.cell(r, C_NAME, sec["subtotal_label"]).font = Font(bold=True)
        _money(ws.cell(r, C_RAKE), round(s_rake, 2))
        _money(ws.cell(r, C_PNL), round(s_pnl, 2), color=True)
        _money(ws.cell(r, C_RB), round(s_rb, 2), color=True)
        if owner_profit_col:
            _money(ws.cell(r, C_PROF), round(s_prof, 2), color=True)
        for c in range(1, ncols + 1):
            ws.cell(r, c).fill = TOT_FILL
            ws.cell(r, c).border = Border(top=THIN)
        r += 2
        if sec.get("in_total", True):     # display-only sections don't sum
            tot_rb += round(s_rb, 2)
            tot_prof += round(s_prof, 2)

    if owner_profit_col:
        final = round(tot_prof + bbj_third, 2)
        summary = (("Members total after tipsback", round(tot_rb, 2), True),
                   (f"{owner}'s Profit (tips kept)", round(tot_prof, 2), True),
                   ("+ Bad Beat Jackpot / 3", bbj_third, False),
                   (f"{owner.upper()}'S TOTAL FINAL PROFIT", final, True))
    else:
        summary = (("Total profit after tipsback", round(tot_rb, 2), True),)
    for label, val, color in summary:
        ws.cell(r, 1, label).font = Font(bold=("TOTAL" in label or
                                               label.startswith("Total")))
        _money(ws.cell(r, summary_col), val, color=color)
        if "TOTAL FINAL" in label:
            for c in range(1, ncols + 1):
                ws.cell(r, c).fill = GRAND_FILL
                ws.cell(r, c).border = Border(top=THIN, bottom=THIN)
        r += 1

    outp = root / "output" / f"{stem}_{start}_{end}.xlsx"
    try:
        wb.save(outp)
    except PermissionError:
        outp = outp.with_name(outp.stem + "_rev.xlsx")
        wb.save(outp)
    print(f"saved {outp}")
    _build_html(owner, start, end, sections, bbj_third, zero_filter,
                owner_profit_col, paid_col, stem)
    return outp


# --------------------------------------------------------------------- HTML ---

def _td(v):
    if v is None:
        return '<td class="num"></td>'
    cls = "pos" if v >= 0 else "neg"
    return f'<td class="num {cls}">{v:,.2f}</td>'


def _build_html(owner, start, end, sections, bbj_third, zero_filter,
                owner_profit_col=True, paid_col=True, file_stem=None):
    root = Path(__file__).parent
    stem = file_stem or f"{owner.lower()}_report"
    prof_col = f"{owner}&#39;s Profit"
    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<title>{owner} Report {start} to {end}</title><style>
body{{font:14px/1.5 system-ui,Segoe UI,Arial,sans-serif;background:#0f141b;
color:#e6edf3;margin:24px}} h1{{font-size:20px}} h2{{font-size:16px;margin-top:26px}}
table{{border-collapse:collapse;width:100%;max-width:1000px;margin:6px 0 18px}}
th,td{{padding:7px 12px;border-bottom:1px solid #2a3644;text-align:left}}
th{{background:#1f2a3c;color:#fff}} td.num{{text-align:right;
font-variant-numeric:tabular-nums}} td.c{{text-align:center}}
tr.sub td{{background:#1e2733;font-weight:600;border-top:2px solid #3a4a5c}}
.pos{{color:#3fb950}} .neg{{color:#f0645a}}
tr.grand td{{background:#2a2410;font-weight:700;font-size:15px}}
input[type=checkbox]{{width:16px;height:16px}}
</style></head><body>
<h1>{owner} - Tipsback Results &nbsp;|&nbsp; {start} to {end}</h1>"""]

    tot_rb = tot_prof = 0.0
    for sec in sections:
        rows = _drop_zero(sec["rows"]) if zero_filter else sec["rows"]
        ths = ('<th>Name</th><th>Role</th><th>Tips</th><th>Profit &amp; Loss</th>'
               '<th>Tipsback %</th><th>Profit after TB</th>')
        if owner_profit_col:
            ths += f'<th>{prof_col}</th>'
        if paid_col:
            ths += '<th>Paid</th>'
        parts.append(f'<h2>{sec["title"]}</h2><table><tr>{ths}</tr>')
        s_rake = s_pnl = s_rb = s_prof = 0.0
        for rec in rows:
            rb = after_rb(rec["rake"], rec["pnl"], rec["pct"])
            role = ROLE_LABEL.get(rec["role"], rec["role"])
            row = (f'<tr><td>{rec["name"]}</td><td class="c">{role}</td>'
                   f'{_td(rec["rake"])}{_td(rec["pnl"])}'
                   f'<td class="c">{rec["pct"]:g}%</td>{_td(rb)}')
            if owner_profit_col:
                op = owner_profit(rec["rake"], rec["pct"])
                row += _td(op)
                s_prof += op
            if paid_col:
                row += '<td class="c"><input type="checkbox"></td>'
            row += '</tr>'
            parts.append(row)
            s_rake += rec["rake"] or 0
            s_pnl += rec["pnl"] or 0
            s_rb += rb
        sub = (f'<tr class="sub"><td>{sec["subtotal_label"]}</td><td></td>'
               f'{_td(round(s_rake,2))}{_td(round(s_pnl,2))}<td></td>'
               f'{_td(round(s_rb,2))}')
        if owner_profit_col:
            sub += _td(round(s_prof, 2))
        if paid_col:
            sub += '<td></td>'
        parts.append(sub + '</tr></table>')
        if sec.get("in_total", True):     # display-only sections don't sum
            tot_rb += round(s_rb, 2)
            tot_prof += round(s_prof, 2)

    if owner_profit_col:
        final = round(tot_prof + bbj_third, 2)
        parts.append('<h2>Summary</h2><table>'
                     f'<tr><td>Members total after tipsback</td>{_td(round(tot_rb,2))}</tr>'
                     f'<tr><td>{owner}&#39;s Profit (tips kept)</td>{_td(round(tot_prof,2))}</tr>'
                     f'<tr><td>+ Bad Beat Jackpot / 3</td>'
                     f'<td class="num">{bbj_third:,.2f}</td></tr>'
                     f'<tr class="grand"><td>{owner.upper()}&#39;S TOTAL FINAL '
                     f'PROFIT</td>{_td(final)}</tr></table>')
    else:
        parts.append('<h2>Summary</h2><table>'
                     '<tr class="grand"><td>Total profit after tipsback</td>'
                     f'{_td(round(tot_rb,2))}</tr></table>')
    parts.append("</body></html>")

    outh = root / "output" / f"{stem}_{start}_{end}.html"
    outh.write_text("\n".join(parts), encoding="utf-8")
    print(f"saved {outh}")
    return outh
