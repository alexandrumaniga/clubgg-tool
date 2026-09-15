---
name: clubgg-abrudan
description: Generate Abrudan's rakeback sheet - his 10 super agents (each at its own rakeback %) plus the agent gerardsb, with per-entity rake, P&L and profit-after-rakeback. Use when asked for "Abrudan's sheet / Abrudan results". uucj1919 is excluded.
---

# Abrudan rakeback report

Produces **three separate documents** (xlsx + html each):
- `abrudan_report_<start>_<end>` - the complete table (all SAs + gerardsb)
- `abrudan_group1_<start>_<end>` - TheGermanGiant / Knikovski / PlayingCardsUsa
- `abrudan_group2_<start>_<end>` - AzizLaGuerr / PinotGrigio2026 / Imigor

The two group docs are separate files with the same columns and their own
total (defined by `GROUP_DOCS` in build_abrudan_sheet.py). In the weekly folder
they land as Abrudan / Abrudan-Group1 / Abrudan-Group2.

```
python abrudan_report.py 2026-08-03 2026-08-09          # collect gerardsb + build
python abrudan_report.py 2026-08-03 2026-08-09 --build-only
```

Prereqs (collection): ClubGG open + `driver.py` elevated.

## Structure (managers_config.py)

- `ABRUDAN_SA_RAKEBACK`: 10 super agents -> rakeback %. Their Rake/P&L is
  **reused** from the managers report (`managers_raw_<range>.csv`) - no
  re-collection.
- `ABRUDAN_AGENTS`: gerardsb = `5438-1780` (roster: GerrardS8), an **Agent** ->
  collected fresh via Agent Statistics for the range (100% rakeback).
- `ABRUDAN_NAMES`: canonical display names (OCR gave UtzzU / Imlgor /
  PinotGrigi02026).
- **uucj1919 (7373-8956) is excluded entirely** - it is Abrudan's own account
  and, unlike Paul's CopilulNorocos, is NOT expanded or shown.

## Sheet (owner_sheet.py renderer)

Columns: `Name | Role | Rake | Profit & Loss | Rakeback % | Profit after RB`.
**No "Abrudan's Profit" column and no Paid checkbox** (those are Paul-only:
`owner_profit_col=False, paid_col=False`). All enumerated entities are shown
even at zero activity (`zero_filter=False`). The summary is a plain "Total
profit after rakeback". Profit after RB = P&L + rakeback%*Rake; P&L sign from
colour via the consensus OCR readers.

Part of the weekly pipeline (clubgg-weekly). Abrudan's manager-level final
(100% rakeback + BBJ/3) lives in the managers report, not here.
