---
name: clubgg-paul
description: Generate Paul's per-super-agent rakeback sheet - Paul's super agents (each at its own rakeback %) plus every member under his CopilulNorocos account (players & agents, collected individually), with a Paid checkbox per row and a grand total. Use when asked for "Paul's sheet / Paul results / the CopilulNorocos breakdown / part 2 of the club results".
---

# Paul rakeback report (part 2 of the club results)

Produces `output/paul_report_<start>_<end>.xlsx` (+ a self-contained `.html`).

## Run

```
python paul_report.py 2026-08-03 2026-08-09          # collect submembers + build
python paul_report.py 2026-08-03 2026-08-09 --build-only   # rebuild sheet only
```

Prereqs (collection): ClubGG open + `driver.py` elevated. Per-member CSV
checkpoint (`paul_submembers_<range>.csv`) so a rerun resumes. Auto-restarts
ClubGG on capture blocks.

## Rakeback config (config/paul_rakeback.csv) - EDIT THIS

Per-entity rakeback lives in `config/paul_rakeback.csv`
(`group,id,name,rakeback_pct`), managed by `paul_rakeback.py`:
- `group=sa` one of Paul's super agents (section 1); `owner` = CopilulNorocos
  (expanded, pct unused); `copil_member` = a member under CopilulNorocos.
- **Edit `rakeback_pct` by hand.** Unknown entities default to 60%.
- `build_paul_sheet` and `paul_report` read the % from here (the
  `managers_config` defaults below are only the seed/fallback).
- **Auto-sync:** `roster.py` calls `paul_rakeback.sync()` after every scan, so
  a newly-detected SA or CopilulNorocos member is auto-added at 60% with your
  existing edits preserved. `build_paul_sheet` also sync()s. Regenerate/repair
  it any time with `python paul_rakeback.py`.

## Seed defaults (managers_config.py)

- `PAUL_SA_RAKEBACK`: Paul's super agents -> seed rakeback % (80/70/0...).
  **CopilulNorocos (2671-5435) is deliberately NOT in this list** - it is
  another account of Paul and is expanded into its members instead.
- `COPIL_OWNER` / `COPIL_OWNER_NAME` / `COPIL_SUBMEMBER_RAKEBACK` (flat 60%).

## Two sections in the sheet

1. **Paul - Super Agents**: the 6 SAs above. Rake/P&L are **reused** from the
   managers report (`managers_raw_<range>.csv`) - no re-collection.
2. **CopilulNorocos - Members**: every roster member whose `agent` is
   CopilulNorocos, collected individually by `paul_report.py`:
   - a **Player** -> personal Game-Statistics **Custom** range (Rake & P&L).
   - an **Agent / Super Agent** -> its **Agent Statistics** -> **Custom** range
     (Fee = rake & P&L). Role is detected from the detail-page **Member Role**
     field (`read_role`).

Row: `Name | Role | Rake | Profit & Loss | Rakeback % | Profit after RB | Paid`.
**Profit after RB = P&L + (rakeback%/100) * Rake.** Each section has a subtotal;
a final **TOTAL PROFIT** sums every after-rakeback figure. P&L sign from colour
(red = loss / green = profit), magnitude from the consensus OCR reader.

## Paid checkbox

Excel: a click-to-toggle **☐ / ☑** data-validation cell (openpyxl can't emit
Excel's native embedded checkbox without risking a corrupt file). HTML: a real
`<input type="checkbox">`. Both are manual.

## Gotchas learned

- The **Agent Statistics** page is more COMPACT than the **Super Agent
  Statistics** page, so the **Custom** tab is at a different Y. It is
  OCR-LOCATED (`read_agent_stats_custom`), never hardcoded. Fee/P&L are read
  before scrolling (already visible on the compact agent page), scroll is a
  fallback. `read_agent_stats_custom` is shared with the managers report.
- Member names in the sheet are best-effort OCR; **IDs are authoritative**
  (collection is always by ID). A few names may look garbled - that's cosmetic.
