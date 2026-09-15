# Paul ledger — data model (DRAFT v0.1, 2026-09-01)

Derived from [REQUIREMENTS.md](REQUIREMENTS.md). Field lists are a starting point for
the mockup; expect changes as we react to designs.

## Sign convention
Amount **positive = counterparty owes Paul**; **negative = Paul owes counterparty**.
Currencies: **RON, USD, AED, CHF** (CHF added 2026-09-05 for Mad Cows; live FX covers all).
Net balance of anyone = sum of their transaction lines.

## Entities

### 1. Counterparty (a person on the MAIN "who owes whom" list)
- `id`, `name` (nickname shown), `real_name`/alias (optional)
- `type`: `rakeback` | `partner_agent` | `rake_share` | `misc`
  (loans and horses live in their own tables, below)
- `clubgg_id` (link to the ClubGG member if applicable, e.g. Paulinho ⟵ 4197-8992)
- `platforms`: [] of platform tags they’re active on
- `net_by_currency`: computed {RON: x, USD: y, AED: z} from transactions
- `status`/`action` (free text: "to send 1-2 days", "pays tonight cash", "PAID")
- `notes`, `tags`

### 2. Transaction (a dated ledger line under a Counterparty)
- `date`, `counterparty_id`
- `amount` (signed), `currency` (RON|USD|AED)
- `platform` (RomanianClub|Carpatix|RoyalRo|Dubai|GGpoker|Stars|call-or-cry|live|…)
- `source`: `weekly_auto` | `manual` | `payment` | `adjustment`
- `status`: `proposed` (in inbox) | `confirmed`
- `paid` (bool, added 2026-09-01): a settled entry **drops out of the outstanding
  balance** but stays in history, hidden by default behind a "show settled" toggle.
  Per-person "Settle balance" marks all open entries paid at once. Loans have the same.
- `note`

### 3. StakingDeal (a horse — SEPARATE detailed tracker)
- `horse_name`, `mode`: `live` | `online`
- `platforms`: []
- `split_paul_pct` (default 50), `split_horse_pct` (default 50)
- `deposits`: [{who: paul|horse, amount, currency}]  → bankroll
- `makeup_current` (+ = still in the hole; must reach 0 before profit splits)
- `pnl_running`, `settleable_now` (0 while in makeup; else horse’s share)
- session/week log (optional): dated P&L lines that move makeup/pnl
- `notes`

### 4. Loan / Datorie (SEPARATE loans list)
- `debtor_name`, `amount`, `currency`, `direction` (default: owed to Paul)
- `due_date` (optional, e.g. David Pacific 8 Oct), `status`: `open` | `paid`
- `note`

### 5. WeeklyInboxEntry (proposed auto-feed, awaiting approval)
- Produced from the weekly Paul sheet: `counterparty_id`, `week_start/end`,
  `amount`, `currency`=RON, `platform`=RomanianClub, `status`=`proposed`
- Approve → becomes a `confirmed` Transaction; reject → discarded.

### 6. Platform (lookup, EXTENSIBLE)
- `name`, `is_clubgg` (bool), `automated` (bool; only RomanianClub=true now)

### 7. FxRate
- `pair` (USD→RON, AED→RON…), `rate`, `updated_at` (live source)

### 8. Club (added 2026-09-03 — the `[CLUBS]` tab)
Every club / site we play in, have players in, or get a deal from.
- `n` (name), `kind`: `ClubGG club` | `Online site` | `Live` | `Other`
- `cid` (ClubGG club id, e.g. 458886) and `ref` (the member id we joined the club through,
  e.g. 6985-1738 = AzizLaGuerr) — added 2026-09-05
- `rake` (rake structure, multi-line free text rendered as a monospace block in the
  expanded club row) — added 2026-09-05
- `rel` (relationship, free text: "we manage · players · rakeback · staking")
- `deal` (rakeback / share, free text: "players 50% · Paul 80%"), `cur` (RON|USD|AED|CHF)
- `auto`: `automated` (weekly numbers collected by the ClubGG tool — only RomanianClub) | `manual`
- `note`
- **People cross-reference is computed, not stored**: a person "is at" a club when any of
  their `platforms` strings matches the club name (case/punctuation-insensitive, either
  direction; aliases `RomClub` ≙ `RomanianClub`, `Royal` ≙ `RoyalRo`). Shown as "N people"
  on the club row; **tapping a club expands it** to list those members with their current
  outstanding balance, and tapping a member jumps to them in the People tab.
- **Only ClubGG clubs live here** (Alex, 2026-09-03): RomanianClub (automated), Carpatix
  (aka Carnatix), RoyalRo (Sorin's, aka Royal), Dubai (1 chip = 0.5 AED; players 50% /
  Paul 80%). GGpoker / PokerStars / "call or cry" were dropped from the tab.
- Added 2026-09-05: **Taiwanese club** (id 275818, via 6985-1738, USD, 1 chip=$0.03, rake
  capped 1.5/2 BB at 5%, deal 50% RB / 55% if deposit) and **Mad Cows** (id 140926, via
  6985-1738, **CHF**, deal recorded verbatim "55/0 rebate" — meaning to confirm; full NLH/PLO/
  bomb-pot rake table stored in `rake`; 2Highwins 35% RB there).
- People with `platforms: ["?"]` appear under no club until tagged.

### 9. Note (added 2026-09-05 — the `[NOTES]` tab)
General free-form notes / to-dos, unattached to any person or club.
- `id`, `text` (multi-line), `created` (ms), `done` (bool)
- Done notes are struck through and hidden behind a "show N done" toggle (same idiom as
  settled entries); the tab count shows OPEN notes only. Add / Edit / Del / Done / Reopen.
- Seeded: "Viza america paul turist", "Program/track net worth Paul".

## Views (screens) implied
- **Dashboard**: total owed to Paul / total Paul owes, per currency + converted grand total.
- **People**: the main list (filter by type/platform), tap → transaction history.
- **Staking**: horses with makeup/split/settleable.
- **Loans**: debts with due dates and paid/open.
- **Inbox**: weekly proposed entries to approve.
- **Clubs**: every club/site with kind, relationship, deal, and how many people are attached.
- **Notes**: general notes / to-dos with a done toggle.
- **Add/Edit** forms (simple, phone-safe) for Paul’s occasional edits.

## Still open (does not block the mockup)
- Data ambiguities (Loren direction, GGALL=0 reconciliation, Lupuleac, Sorin role) —
  resolve when populating real data. See [QUESTIONS.md](QUESTIONS.md) §K.
- Whether "partner agents" (Sorin, Raiciu) need hierarchy modeling or just balances.

### 3b. Staking — as built (2026-09-07)
- `kind`: `cash` | `tourney` | `live`. `split` text "paul / horse" (horse % = second number, default 50).
- cash: `log[]` = {wk, acct, club, pnl, rake, pct (editable, default 80), cur, rate, note, settled}.
  result = (pnl + rake×pct/100) × rate-to-RON. Period net = Σ unsettled; <0 makeup, >0 horse share.
  "Paid out · reset" sets settled on all open lines.
- tourney: `sites[]` = {site, bal, cur, rate, note}; `invested` (RON); net = Σ bal(RON) − invested.
- live: legacy `makeup` / `pnl` fields typed by hand.
- Currency `DXB` = Dubai club chip = **0.5 AED** (rate to RON = 0.5 × aed_ron).

### Entry `bucket` (2026-09-08)
Optional name on an entry. Blank = main running balance; a name = a separate debt shown as its own group with subtotal and per-group settle. Row total = all open entries.
