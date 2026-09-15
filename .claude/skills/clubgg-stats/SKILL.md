---
name: clubgg-stats
description: Collect per-player Rake and Profit/Loss stats from the ClubGG desktop app for a given date interval and produce a CSV. Use when the user asks to collect ClubGG player stats, weekly rake/P&L numbers, or the weekly club report. Inputs - a date interval (e.g. "5 august - 11 august") and how many players to collect.
---

# ClubGG interval stats collection

Drive the ClubGG Windows app by clicking through it (there is no API), read the
screens from screenshots, and produce a CSV with one row per player:
`name, player_id, role, upline, rake, profit_loss` for the requested date interval.

## Fast path — use collect.py (default)

`collect.py` runs the entire loop deterministically with local OCR — no
AI-in-the-loop latency (≈7s/player, 50 players ≈ 6 min):

1. Do the **Setup** below (driver running, ClubGG open).
2. Run in the foreground and watch its output:
   `python collect.py 2026-08-05 2026-08-11 20`
   (start date, end date, player count; run from `c:\Users\PC1\clubgg-tool`)
3. It writes `output\clubgg_stats_<start>_<end>.csv` incrementally, prints one
   line per player, and audit screenshots land in `shots\collect\`.
4. Afterwards: report the CSV to the user as a table; for any line the script
   printed `retry`/`SKIPPED` for, Read the matching `shots\collect\p*_*.png`
   and verify/fill values by eye.

collect.py verifies every screen by OCR before clicking and aborts rather
than guessing — if it aborts repeatedly, fall back to the manual flow below
to diagnose (that's what the coordinate map is for).

**Capture prerequisite:** screenshots of ClubGG only work with MPO hardware
overlays disabled — registry `HKLM\SOFTWARE\Microsoft\Windows\Dwm`
`OverlayTestMode=5` (set 2026-08-13, needs reboot after setting). Symptom of
MPO active: screenshots show the window *behind* ClubGG while the user sees
ClubGG fine. If that reappears, re-check that registry value.

## Inputs (ask if missing)

- **Date interval** — start and end date, e.g. Aug 5 – Aug 11. If the user says
  "last week", compute the previous Monday–Sunday from today's date.
- **Player count N** — how many players to collect, taken top-down from the
  member list filtered to Players (sorted by Fee, the default sort).

## Architecture — why the driver exists

ClubGG runs **as administrator**; Windows silently discards clicks/keys sent
from non-elevated processes. All input therefore goes through `driver.py`
(runs elevated, one UAC prompt) and `gg.py` (non-elevated client you call).
The driver **forces the ClubGG window to (37,0) at 540x990 before every
action**, so the coordinate map below is always valid — never scale or guess
coordinates. You are the vision system: after every action take a `--shot`
screenshot and **Read it before deciding the next click**. Never click blind.

## Safety policy — a wrong click must NEVER happen

Before EVERY click, all three checks must pass on the LATEST screenshot
(taken after the previous action, never an older one):

1. The screen is the one you expect (correct title/header visible).
2. The element you intend to click is visible at the mapped coordinates.
3. The click target is on the allowed list below.

If any check fails: take a fresh `shot`, re-orient, and if still ambiguous
STOP and ask the user. Retrying blindly or guessing is never acceptable.

**Allowed click targets (complete list):** red 4-dot button, "Members" on the
red menu, X-close on the red menu, "Player" filter tab, member rows,
"Custom" / date-range stats tab, calendar day cells, calendar month arrows,
calendar "Confirm", the back arrow (25, 62).

**Forbidden — never click, no exceptions:** Removal, Send Membership,
Trace Player, Member Role dropdown, Create New Table, any table row in the
lobby, Inbox / Counter / Data / Admin on the red menu, the Applicants List
tab, anything inside an unexpected popup, and the window's minimize /
maximize / close buttons. If one of these is where you're about to click,
you are mis-oriented — stop.

## Setup

1. Check the driver: `python gg.py ping` (run from `c:\Users\PC1\clubgg-tool`).
   If it reports not running, start it and tell the user to accept the UAC prompt:
   `Start-Process -FilePath python -ArgumentList '"c:\Users\PC1\clubgg-tool\driver.py"' -Verb RunAs`
   Then ping again; result must show `"elevated": true`.
2. ClubGG must be open and logged into the club. If the window is missing,
   ask the user to open it.
3. Take a baseline: `python gg.py setwin --shot shots\00_start.png` (this also
   snaps the window to its canonical 540x990 geometry, which the driver then
   re-enforces before every action).
   Save screenshots to `shots\` (overwrite freely; they are disposable).
4. Read the screenshot to identify the current screen, then navigate to the
   Club lobby (the screen with the club name banner, "Create New Table", and a
   table list). From most screens, clicking the back arrow **(25, 62)**
   repeatedly gets you there.

## Coordinate map (window-relative, 540x990)

**Club lobby**
- Red 4-dot admin button (bottom-right): **(485, 931)**. Clicking it expands a
  red menu bar: Inbox (107,935) / Members (174,935) / Counter (265,935) /
  Data (344,935) / Admin (423,935) / X-close (489,934). If the menu bar is
  already open (you see those labels), skip the 4-dot click.
- Click **Members (174, 937)** → Club Members screen.

**Club Members screen**
- Role filter tabs at y=273: All (79) / Manager (174) / SA (269) / Agent (364)
  / **Player (460, 273)** ← click this; member count drops (e.g. 369 → 259).
- Search box at (270, 196) — available fallback: click it, `gg.py type <name>`.
- Member rows (fully visible): centers at y ≈ **419, 555, 690, 826**; a 5th row
  peeks at the bottom. Click a row at **(216, <row_y>)** (on the name/avatar,
  not on the blue upline name).
- Each row shows: nickname, `(ID : xxxx-xxxx)`, chip amount (the Fee), and a
  badge at the row's bottom-left: `SA <name>` (blue) or `Agent <name>` (orange).
  **Record role and upline from this badge** — it is the "sa/agent of the
  player" for the CSV.
- Scrolling: touch-style drag. `python gg.py swipe 270 820 270 420 --shot ...`
  scrolls down ~3 rows. There may be momentum — always re-read the screenshot
  to see which rows are now visible; dedupe players by ID.

**Member Detail screen** (opens after clicking a row)
- Header: nickname, `(ID : xxxx-xxxx)`, Last Sign In, chip balance.
- DO NOT click: **Removal**, **Send Membership**, **Trace Player**, or the
  Member Role dropdown. This task is read-only.
- Game Statistics tabs at y=636: Overall (111) / Past 7days (269) /
  **Custom (428, 636)** ← click to open the date picker. After a range is set,
  this tab relabels to e.g. `8/3 ~ 8/9`.
- Stats values (right-aligned, x≈465): Hand y=704, **Rake y=735**,
  **Profit & Loss y=766** (negative shown orange with minus), Non-Chip Prize
  y=797, Sent out y=828, Claimed back y=859.
- Back arrow: **(25, 62)** returns to the member list (filter and scroll
  position are preserved — verify with the screenshot anyway).

**Select Date sheet** (after clicking Custom)
- Month header y=327 (e.g. "August 2026"); prev-month arrow **(53, 327)**,
  next-month **(486, 327)**; current range label y=382; **Confirm (269, 941)**.
- Day-cell grid — column x by weekday (Sun first) and row y by week:
  - x: Sun 62, Mon 131, Tue 200, Wed 269, Thu 338, Fri 407, Sat 476
  - y: week1 513, week2 581, week3 650, week4 719, week5 788, week6 857
  - Cell for day D: `offset = weekday of the 1st of the displayed month
    (Sun=0)`; `cell = offset + D - 1`; `row = cell // 7`, `col = cell % 7`.
    Example: August 2026 starts Saturday (offset 6), so Aug 5 → cell 10 →
    row 1 col 3 → **(269, 581)**; Aug 11 → cell 16 → row 2 col 2 → (200, 650).
- Selection order: click the **start day first, then the end day** — first
  click resets the range start, second sets the end (range highlights green).
  If the interval is in another month, navigate with the arrows first; for a
  cross-month interval click the start day, navigate, then click the end day.
- **Verify the range label reads exactly the requested interval in the
  screenshot before clicking Confirm.** If wrong, click the correct start day
  and rebuild the selection.

## Per-player loop

For each of the top N rows (top-down, scrolling as needed):

1. From the list screenshot, note the row's **name, ID, badge role + upline**.
2. Click the row → `--shot shots\detail.png`; confirm it's the right player
   (name/ID in header).
3. Click Custom (428, 636) → `--shot shots\cal.png`; confirm the date sheet.
4. Click start day, then end day (grid math above) → `--shot shots\range.png`;
   confirm the range label.
5. Click Confirm (269, 941) → `--shot shots\stats.png`; the stats tab should
   now read e.g. `8/5 ~ 8/11`. Read **Rake** and **Profit & Loss** from this
   screenshot.
6. Click back (25, 62) → `--shot shots\list.png`; confirm you're on the list
   and see where you are (scroll if the next target row isn't fully visible).

Keep a running tally in your notes: `name, id, role, upline, rake, p&l`.

## Output

Write `output\clubgg_stats_<start>_<end>.csv` (create `output\` if needed),
e.g. `output\clubgg_stats_2026-08-05_2026-08-11.csv`:

```csv
name,player_id,role,upline,rake,profit_loss
ennuye,9905-0070,SA,TheGermanGiant,25584.23,-50000
rattyro,8817-7072,Agent,GerrardS8,...
```

- Strip thousands separators from numbers ("25,584.23" → 25584.23); keep the
  minus sign on losses.
- After finishing, show the user the CSV contents in a table and mention any
  players skipped or uncertain readings.

## Recovery & cautions

- Wrong/unexpected screen: `python gg.py shot shots\where.png`, read it,
  navigate back to a known screen (back arrow, or X on the red menu).
- A popup/dialog you didn't expect: do not guess destructive buttons; close
  via X or back. If it looks consequential (removal, membership, payments),
  stop and ask the user.
- Click landed but nothing changed: re-shot and retry once; if still stuck,
  re-run `setwin` (window may have moved/resized, invalidating coordinates).
- The stats numbers update live; capture Rake/P&L from the **same screenshot**
  in step 5 for consistency.
- If a row badge shows no upline (rare), record role/upline as empty strings.
