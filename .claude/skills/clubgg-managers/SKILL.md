---
name: clubgg-managers
description: Generate the "general-club-managers-results" weekly report - each of the 3 club managers (Veres/Abrudan/Paul) with their super-agents' rake & P&L for a date range, plus the club Bad Beat Jackpot, as an Excel sheet. Use when asked for the managers' weekly situation / manager results / the 3-manager report.
---

# ClubGG managers report (general-club-managers-results)

Produces `output/managers_report_<start>_<end>.xlsx`: one table per manager
(manager row + their super-agents) and a profit-split summary.

## Run

```
python managers_report.py 2026-08-03 2026-08-09          # collect + build
python managers_report.py 2026-08-03 2026-08-09 --build-only   # rebuild xlsx only
```

Prereqs: ClubGG open + `driver.py` running elevated. Auto-restarts ClubGG on
capture blocks; per-entity CSV checkpoint (`managers_raw_<range>.csv`) so a
rerun resumes. The BBJ is written to `managers_bbj_<range>.txt`.

## Structure (managers_config.py)

- 3 managers (aliases -> id): Veres 2554-4367, Abrudan 1350-3167, Paul 5179-8144.
- `SA_TO_MANAGER` maps each super-agent id -> manager alias (also in
  `output/sa_manager_map.csv`). Edit `managers_config.py` to change membership.

## Collection rules (per user)

- MANAGER rake/P&L: open member -> personal Game-Statistics **Custom** range
  (reader OCR-locates the Custom tab + Rake/Profit&Loss labels; managers have a
  shifted layout with no Member Role dropdown).
- SUPER AGENT rake/P&L: open member -> **Super Agent Statistics** -> **Custom**
  range -> read **Fee (= rake)** and **Profit & Loss**.
- **P&L sign comes from COLOUR** (red = loss, green = profit) - OCR drops the
  "-" unreliably. Magnitude from OCR, sign from `color_sign()`. Never trust the
  OCR minus for P&L.
- Zero-activity members read as 0 (empty value cell).
- BAD BEAT JACKPOT: red menu (don't re-click if already open) -> Data -> click
  the date -> Custom range -> **BBJ = Club Profit&Loss + Fee**.

## Sheet

Columns: `Name | Rake | Profit & Loss | Profit after RB (100%)` where
after-RB = **P&L + Rake**. Each manager table has a subtotal. Final summary:
each manager's **Final Profit = combined-after-rakeback (manager + their SAs)
+ BBJ/3 added as a positive amount**. Losses red, profits green.

## Verifying

Per-entity screenshots are kept in `shots/collect/m<NN>_*.png` (tag order =
Veres, its SAs, Paul, its SAs, Abrudan, its SAs). To re-check a P&L sign,
inspect the value colour on that entity's screenshot.
