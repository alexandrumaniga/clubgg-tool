---
name: clubgg-weekly
description: The STARTING skill - run the full weekly ClubGG pipeline for a week (default last Monday-Sunday). Checks/updates the CopilulNorocos downline list (NOT a full roster reload - that's occasional only), then, in order: Managers sheet → Paul's sheet → push Paul's figures to Paul's Book inbox (Alex approves) → Abrudan's sheet → Cohiba statement PDF, into a per-week subfolder. Monday 12:00, manual 'go'. Use for "run the weekly", "weekly report", "this week's situation", the Monday run.
---

# ClubGG weekly pipeline (orchestrator)

One command runs everything: `python weekly_run.py`.

Intended cadence: **every Monday ~12:00**, reporting the week that just ended
(**last Monday-Sunday**). It figures the interval from today automatically.

```
python weekly_run.py                        # auto: last Monday-Sunday
python weekly_run.py 2026-08-10 2026-08-16  # explicit interval
python weekly_run.py --roster               # force a fresh roster reload
python weekly_run.py --no-roster            # skip the roster this run
```

## The weekly procedure (Alex's standing instruction, 2026-09-07)
**Every Monday at 12:00, triggered manually — Alex says "go".** Interval = the week that just
closed, **Monday–Sunday**. Order is fixed:

0. **Environment** — ClubGG open, `driver.py` elevated (Alex clicks the UAC "Yes"). Then any
   pending lookups (e.g. a new member's id) BEFORE collecting.
   Id lookup by name: `python lookup_member.py <name>` (Club Members search box; prints id, role,
   upline; frame saved to shots/collect/lookup_<name>.png for a visual check).
   **If the managers finals do not sum to 0: stop, report the residual, and ask Alex — do not
   auto-rescan** (his instruction 2026-09-07). Run the steps individually (not `weekly_run.py`)
   so the pipeline can pause there.
1. **CopilulNorocos downline check** — Alex usually pastes screenshots of *Downline Players*;
   read every id, check unique count == "Total Downline Players", diff vs
   `paul_report.copil_submembers()`, apply adds (`COPIL_EXTRA_MEMBERS`, ask the %) and departures
   (`COPIL_EXCLUDE`). Only run `copil_dl_frames.py` if no screenshots. Never the full roster.
2. **Managers sheet** (`managers_report.py`) → reconcile: manager finals must sum ≈ 0 vs club
   BBJ (a complete week → within a few RON). If not, `scan_sas.py SA` / `probe_missing.py`.
3. **Paul sheet** (`paul_report.py`, 100% checkpointed) → then
   **push to Paul's Book inbox** (`paul_ledger/app/push_inbox.py <start> <end>`): every
   Paul-relevant figure (SAs, groups, CopilulNorocos members) becomes a *proposed* inbox entry;
   **Alex approves them himself in the app** — never post to ledgers directly.
   Sign: inbox amount = −(P&L + tips×pct); + = they owe Paul, − = Paul owes.
   Name matching: `paul_ledger/app/inbox_aliases.json` maps ClubGG names to Paul's Book people
   (spike088→spike (Bursuc), PinkFL01D→PinkFloid, …); add a line whenever the push reports a
   member as "not yet a person" who actually exists under another name.
4. **Abrudan sheet** (`abrudan_report.py`) + its two mini group docs.
4b. **Cristian Veres downline sheet** (`veres_report.py <start> <end>`, since 2026-09-14): the 18 members
   under SA Cristian Veres (5368-8498), collected individually, tipsback per member from
   `VERES_MEMBERS` (default 50% until Alex gives the real %). Membership = Alex's screenshots ->
   `output/downline_5368-8498_live.csv`; only members who played appear on the sheet.
5. **Statements** (`statement.py <start> <end> --group cohiba|cashvick|premium`, one PDF each:
   Cohiba group, Cashvick group, Premium89) — English only, Tips /
   Tipsback wording, no percentage printed.
6. **Deliver** — xlsx/html/pdf per sheet + `Cohiba-`, `Cashvick-`, `Premium89-Statement.pdf` into the week folder Alex
   names; report the headline numbers and the reconciliation residual honestly.

`python weekly_run.py <start> <end> --no-roster --folder "<name>"` runs 2–5 in this order.

## Paul's Book manual inputs (after the push, every Monday)
Besides the RomanianClub inbox, Alex dictates and I post: Cashvick's Dubai statement (net vs his RomanianClub
result; chips = 0.5 AED, USD at 3.675) and the Dubai players (2Highwins 50, DelayPrince 50, StormSpirit 70,
Muflender 50, Paladin 80 -> staking); Paulinho on Carpatix 50; Muflender on RoyalRo 50; **RoyalRo pays Paul 10%
for Insertcoin**; 2Highwins on Mad Cows 35 (CHF); Mircea (Meeeeesi10) on Las Vegas Land 30 (club gives Paul 55%, 1 chip = 1 USD); StormSpirit on Raiciu's club 80 (nets Raiciu's debt);
Paladin's staking week lines; payments/corrections. Full list: memory `paul-book-weekly-checklist`.

## Output

The three finished sheets (xlsx + html) are copied into a fresh subfolder
**`output/week_<start>_<end>/`** as `Managers`, `Paul`, `Abrudan`. The raw
per-interval CSVs / originals stay in `output/`.

## Delivering

Report the week folder path, which steps ran vs were skipped/failed, and the
headline numbers (each manager's final; Paul's total final profit; Abrudan's
total after rakeback). Spot-check one non-zero value per report against its
`shots/collect/*.png` before declaring done - see clubgg-managers /
clubgg-paul / clubgg-abrudan for per-report detail and the config files.

## Note

The older single-sheet flow (`collect.py` + `build_sheet.py`, flat rakeback
for every player - skills clubgg-stats / clubgg-sheet) is a separate, legacy
pipeline. The weekly run above is the current one.
