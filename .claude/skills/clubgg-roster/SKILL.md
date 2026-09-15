---
name: clubgg-roster
description: Scan the complete ClubGG Player-filter member list (scroll-only, no detail pages) and produce a CSV roster of every player's ID, name and agent (upline), verified against the "Total members" count. Use when the user asks for the full player list / roster / who belongs to which agent.
---

# ClubGG full roster scan

Produces `output\clubgg_roster_<date>.csv` (columns: `player_id, name,
agent`) covering **every** player in the Player filter tab, count-verified.
Role (SA/Agent) is intentionally not included.

## Run

1. Setup as in `clubgg-stats`: ClubGG open, `driver.py` running elevated.
2. `python roster.py` (from `c:\Users\PC1\clubgg-tool`, foreground; ~5-10 min
   for ~260 players). It only scrolls and reads - no player pages are opened.
   Every frame is saved under `shots\roster_frames\`.
3. To rebuild/repair the roster WITHOUT re-scanning (e.g. some names/agents
   read blank): `python roster.py --reparse` re-OCRs all saved frames
   offline - no ClubGG, no driver, no capture-budget cost. It keeps the best
   (non-empty) name/agent for each player seen across frames. Note this only
   helps if the frames were retained from a scan on THIS version; older runs
   overwrote frames. Non-Latin/emoji names may still not OCR.

## How it verifies (and what to check afterwards)

- Reads the green **Total members** number on the tab at the start AND the
  end (it changes live), then sweeps top-to-bottom in ~2.8-row swipe steps,
  deduping by player ID. If the collected count is short, it scrolls back to
  the top and re-sweeps (the list re-sorts live by fee, so a single sweep
  can miss a player that jumped upward) - up to 3 passes.
- Agent names are re-OCR'd per row from a 3x zoomed crop of the same
  screenshot (no extra captures). Rows whose agent still can't be read are
  saved with agent `UNKNOWN` - the script does NOT search player names to
  fill them (per user instruction; searching burns the capture budget).
- The output header says `VERIFIED` or `CHECK` vs the tab count. Report any
  `UNKNOWN` agents and any count gap to the user; a rerun (fresh launch) can
  fill gaps.
- Capture budget: ClubGG re-arms its anti-capture flag after ~100 captures
  per launch (~one full sweep). The script saves progress after each sweep
  and stops cleanly if the flag re-arms mid-run. If it stops early, have the
  user restart ClubGG and rerun.

## Name/agent verification (accuracy pass)

Windows OCR reliably confuses `1`/`l`/`I`/`0`/`O` and inserts spaces in
stylized gamertags. To verify against the photos after a scan:
- Read frames in `shots\roster_frames\` and compare to the CSV. Focus on
  OCR-risky names (space-before-digit, lowercase `l` touching digits) and the
  DISTINCT agents (far fewer than players; a misread agent is wrong the same
  way everywhere - fix once, apply globally).
- Record confirmed corrections in `output\roster_fixes.py` (`NAME_FIX` by id,
  `AGENT_FIX` by whole-column value) and apply with its `apply_fixes(rows)`.
- Known-good agent canonicalizations found so far: `PKR`->`11 PKR 11`,
  `PinkFLOlD`->`PinkFL0ID`, `7enith-`->`Zenith_`, `blrkln`->`b1rk1n`.

## Safety

Allowed clicks only: list scrolling (swipes), the search box (270, 196),
typing a player name, back arrow (25, 62), red-menu navigation from
`clubgg-stats`. Never click member rows or anything else - this task is
read-only on the list.
