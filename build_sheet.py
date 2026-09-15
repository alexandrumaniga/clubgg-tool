r"""Build a formatted Excel sheet from a collected ClubGG stats CSV.

Usage:
  python build_sheet.py output\clubgg_stats_2026-08-05_2026-08-11.csv
  python build_sheet.py <csv> --rakeback 30 --out output\report.xlsx

Layout (one player per row):
  Player ID | Name | Rake | Profit | Profit +RB% | Agent
Profit cells are green when positive, red when negative.
"""
import csv
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ---- palette ---------------------------------------------------------------
HEADER_FILL = PatternFill("solid", fgColor="1F2A3C")   # dark slate
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F2A3C")
POS_FILL = PatternFill("solid", fgColor="E5F3E8")      # soft green
POS_FONT = Font(bold=True, color="1E7B34")
NEG_FILL = PatternFill("solid", fgColor="FBE9E7")      # soft red
NEG_FONT = Font(bold=True, color="B3261E")
BAND_FILL = PatternFill("solid", fgColor="F4F6F8")     # zebra stripe
TOTAL_FILL = PatternFill("solid", fgColor="E8ECF1")
THIN = Side(style="thin", color="D5DBE1")
ROW_BORDER = Border(bottom=THIN)

NUM_FMT = "#,##0.00"


def main():
    args = sys.argv[1:]
    rakeback = 30.0
    out = None
    if "--rakeback" in args:
        i = args.index("--rakeback")
        rakeback = float(args[i + 1])
        del args[i:i + 2]
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1])
        del args[i:i + 2]
    src = Path(args[0])
    if out is None:
        out = src.with_name(src.stem.replace("clubgg_stats", "clubgg_report")
                            + ".xlsx")

    with src.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    m = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", src.stem)
    interval = f"{m.group(1)} to {m.group(2)}" if m else src.stem
    rb = rakeback / 100.0

    wb = Workbook()
    ws = wb.active
    ws.title = "Player Stats"

    headers = ["Player ID", "Name", "Tips", "Profit",
               f"Profit +{rakeback:g}% TB", "Agent"]
    widths = [16, 26, 16, 16, 20, 24]
    for i, wdt in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = wdt

    # title
    ws.merge_cells(start_row=1, start_column=1, end_row=1,
                   end_column=len(headers))
    t = ws.cell(row=1, column=1,
                value=f"ClubGG Player Stats   •   {interval}   •   "
                      f"{len(rows)} players")
    t.font = TITLE_FONT
    t.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 34

    # header row
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 24
    ws.freeze_panes = "A3"

    def money(cell, value, colored=False):
        cell.value = round(value, 2)
        cell.number_format = NUM_FMT
        cell.alignment = Alignment(horizontal="right", vertical="center",
                                   indent=1)
        if colored:
            cell.fill = POS_FILL if value >= 0 else NEG_FILL
            cell.font = POS_FONT if value >= 0 else NEG_FONT

    r = 3
    for rec in rows:
        rake = float(rec["rake"])
        profit = float(rec["profit_loss"])
        vals = [rec["player_id"], rec["name"]]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.alignment = Alignment(vertical="center", indent=1)
        money(ws.cell(row=r, column=3), rake)
        money(ws.cell(row=r, column=4), profit, colored=True)
        money(ws.cell(row=r, column=5), profit + rb * rake, colored=True)
        agent = ws.cell(row=r, column=6, value=rec["upline"])
        agent.alignment = Alignment(vertical="center", indent=1)
        ws.row_dimensions[r].height = 20
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = ROW_BORDER
            if r % 2 == 1 and cell.fill == PatternFill():  # zebra on plain cells
                cell.fill = BAND_FILL
        r += 1

    # totals row
    tot_rake = sum(float(x["rake"]) for x in rows)
    tot_profit = sum(float(x["profit_loss"]) for x in rows)
    label = ws.cell(row=r, column=1, value="TOTAL")
    label.font = Font(bold=True, size=11)
    label.alignment = Alignment(vertical="center", indent=1)
    money(ws.cell(row=r, column=3), tot_rake)
    money(ws.cell(row=r, column=4), tot_profit, colored=True)
    money(ws.cell(row=r, column=5), tot_profit + rb * tot_rake, colored=True)
    ws.row_dimensions[r].height = 24
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=r, column=c)
        if cell.fill == PatternFill():
            cell.fill = TOTAL_FILL
        cell.border = Border(top=Side(style="medium", color="1F2A3C"))

    wb.save(out)
    print(f"saved: {out} ({len(rows)} players, rakeback {rakeback:g}%)")


if __name__ == "__main__":
    main()
