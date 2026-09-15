---
name: clubgg-sheet
description: Build the formatted Excel report from a collected ClubGG stats CSV (styled per-player sheet with red/green profit cells and rakeback column). Use after clubgg-stats has produced the CSV, or when the user asks to (re)build/restyle the weekly sheet.
---

# ClubGG sheet builder

Turn a collected stats CSV (from the `clubgg-stats` skill / `collect.py`)
into a formatted Excel report.

## Run

```
python build_sheet.py output\clubgg_stats_<start>_<end>.csv
```

Options: `--rakeback 30` (percent, default 30) · `--out <path>`
(default: same folder, `clubgg_report_<start>_<end>.xlsx`).
After building, verify by loading the workbook and printing a few rows,
then tell the user the output path so they can open it in Excel.

## Design contract (keep consistent when editing build_sheet.py)

- One player per row. Column order is fixed by the user's spec:
  **Player ID first, Name second, … Agent (upline) absolute last.**
  Currently: `Player ID | Name | Rake | Profit | Profit +RB% | Agent`
- **Profit and Profit+RB cells: green fill/font when >= 0, red when
  negative** (soft fills: green `E5F3E8`/`1E7B34`, red `FBE9E7`/`B3261E`).
- `Profit +RB%` = profit_loss + (rakeback/100) x rake — the player's result
  if they get that percent of their rake back. Default 30% for everyone
  (per-player rakeback rates may come later).
- Generous spacing: wide columns (16-26), row height 20+, indented cells,
  numbers right-aligned with `#,##0.00`.
- Dark slate header row (`1F2A3C`, white bold), merged title row with
  interval + player count, zebra striping, TOTAL row at the bottom
  (sums with the same red/green treatment), frozen header (`A3`).

## Notes

- Input CSV columns: `name,player_id,role,upline,rake,profit_loss`
  (`role` is not shown on the sheet currently; `upline` is the Agent column).
- Names/uplines come from OCR - occasional character quirks are expected;
  IDs are digit-verified and exact.
- If the user asks for layout changes, edit `build_sheet.py`, rebuild, and
  update the design contract above to match.
