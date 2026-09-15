# Paul ledger — confirmed requirements (grows as we decide)

Living record of DECISIONS (not guesses). Source discussion: Alex, from 2026-09-01.

## DEPLOYED (2026-09-02) — Cloudflare Pages + D1
- **Live URL:** https://paul-ledger.pages.dev
- **Stack:** Cloudflare Pages (advanced mode `_worker.js`) + D1 database `paul-ledger`
  (id 3b2b560b-5927-4aa9-9794-d28ce18bb59f). Account: Alex.maniga1@gmail.com (personal),
  id 9f0bc8cd3dce6bb6e64b64ba174e11f9. **$0** (free tier, no card, no pause).
- **Code:** `paul_ledger/app/` — `dist/` is the deploy output (`index.html` = app,
  `_worker.js` = API), `src/worker.js` + `public/index.html` are the sources copied into dist,
  `schema.sql`, `wrangler.jsonc`. Redeploy: `cd paul_ledger/app && cp -r public/. dist/ &&
  cp src/worker.js dist/_worker.js && wrangler pages deploy dist --project-name=paul-ledger
  --branch=main --commit-dirty=true` (copies ALL of public/: icons, manifest, sw.js).
- **Auth:** code-based. `codes` table in D1. Enter code → Worker validates → HMAC token
  (signed with `AUTH_SECRET` Pages secret) stored in device localStorage → auto-login.
  Admin code unlocks the in-app "Codes" panel to generate/revoke Paul's codes.
  **Admin code saved in** `paul_ledger/app/.admin_code.txt` (currently 4FK59FEC).
- **Ledger storage:** one versioned JSON doc in `kv('state')`; app seeds from its built-in
  SEED on first load; last-writer-wins + refetch-on-focus/25s.
- **Chose Pages over Workers** because workers.dev subdomain onboarding was blocking; Pages
  gives *.pages.dev with no subdomain step.
- **PENDING:** wire the weekly Python run to push inbox entries (write to D1 `kv`/an inbox
  path via the API or a service token). (Live FX done 2026-09-03 via `/api/fx`.)

## VISUAL DESIGN (decided 2026-09-03): “The Terminal”
Three drafts were rendered side-by-side with real data (Ledger / Terminal / Broadsheet);
Alex chose **Terminal** — dark, all-monospace, ticker-strip totals, hairline grid, bracketed
tabs/buttons, no cards/pills/shadows. Dark-only by design. Details in HOSTING.md.

## FORMAT (confirmed 2026-09-01): hosted, mobile-first **web app**
Both open it by link (Alex PC, Paul phone). Handles the review inbox, per-person
history, staking math, multi-currency, and Paul's light edits. Local tooling pushes
the weekly auto-suggestions. Data model + a tentative mockup drive the final layout.

## Users & access (confirmed 2026-09-01)
- **Maintainer:** Alex, ~95% of edits. Paul can occasionally edit some things.
- **Readers:** Alex mostly; Paul must be able to check it whenever he wants.
- **Devices:** Alex → PC. Paul → **phone ~80% of the time** (traveling), PC at home.
- **Editing by Paul:** occasional, must be simple and safe (no raw formulas).

### Consequences for format
- ❌ Local-only file on Alex's PC (Paul can't reach it while traveling).
- ✅ Must be **reachable from anywhere** and **phone-friendly** for Paul.
- ✅ Must be **shared** between two people, with **light editing** for Paul.
- Front-runners: a **hosted web dashboard/app** (mobile-first) or a **cloud
  spreadsheet** (Google Sheets). Final choice deferred until data model is set,
  because the data (multi-currency, staking with makeup/splits, categories) may be
  too structured for a comfortable phone spreadsheet.

## Mockup v2 — editable (2026-09-01)
- Same URL. Adds full CRUD: tap a person → their entries; **edit / delete / add** each
  entry, **note per entry**, **note per person**, edit/delete person, add person; plus
  edit/add/delete for loans and horses; inbox Approve posts into a person's ledger.
- Persists **on-device (localStorage)** only, for iterating the editing UX.

## ⚠ Sharing / sync fork (found 2026-09-01) — NEEDS A DECISION
- claude.ai Artifact runtime stores (`db`, `room`) are **organization-internal**: only
  people signed into Alex's claude.ai org can open such a page. **Paul is external**, so
  live cross-device sync CANNOT run through a capability-backed claude.ai artifact.
- A **static** artifact (no capabilities) can be shared by public link (Paul can open it),
  but has no shared storage — hence on-device localStorage for v2.
- Options for real Alex↔Paul sync to settle later:
  1. **Google Sheet backend** (shared by link; the web app reads/writes it) — external-friendly.
  2. **Small self-hosted web app** (own storage/auth) — most control, most setup.
  3. Keep claude.ai artifact + a manual export/import between devices (clunky).
- Until decided, v2 is single-device.

## Tentative mockup v1 (2026-09-01)
- File: `paul_ledger/mockup_v1.html` · Artifact:
  https://claude.ai/code/artifact/66750246-7cc3-4369-99d7-0a78da6bf76c
- Embodies: 4 areas (People / Staking / Loans / Weekly inbox); People = one list with
  type filters + tap-to-expand history; green=to collect, red=to pay; dashboard tiles
  (collect / pay / net converted); inbox approve→post. Sample data from the notes.
- Static prototype only (no persistence yet) — for structural feedback before build.

## Data model (confirmed direction 2026-09-01)
- **Staking = its own detailed tracker** (not just a balance line): makeup, split %,
  deposits, per-week P&L, live vs online, platform.
- **Debts ("Datorii") = a separate loans list** (own due dates), kept apart from the
  poker balances.
- **Main structure (leaning, NOT final):** a main "who owes whom" balances list +
  a separate staking tracker + a separate loans list. Alex wants to **see tentative
  designs before committing** to how much lives in the "main list" vs separate views.
  → produce mockups once currencies + staking mechanics + integration are known.

## Currencies (confirmed 2026-09-01)
- Store each balance in its **native currency** (RON / USD / AED).
- Also show a **converted grand total** using **live FX rates**.
- Note: AED is often already expressed as Paul's USD share in practice.
- Open impl detail: "live rates" — fetch in-browser vs refresh at update-time by
  local tooling (a Claude Artifact's CSP blocks in-browser fetch; a cloud sheet has
  GOOGLEFINANCE; a self-hosted app can fetch). Decide with the format.

## Integration with weekly ClubGG tooling (confirmed 2026-09-01)
- ClubGG members' weekly rakeback is **auto-SUGGESTED** from the weekly Paul sheet;
  **Alex reviews & confirms** to apply it as a ledger line (not silent auto-apply).
- Needs a **review inbox**: proposed weekly entries waiting for approval.
- Payments (cash, transfers) and non-ClubGG activity are entered manually.

## Ledger model (confirmed 2026-09-01)
- **Full transaction history per person**: dated lines (amount, currency, source/note);
  net balance = sum of lines. Keep the audit trail, not just the net.
- Implication: this is a small **stateful app with an approve-then-apply workflow**,
  which a static spreadsheet handles poorly (would need a staging tab + manual copy).

## Staking model (confirmed 2026-09-01)
- **Makeup-based**: a horse must repay all covered losses (makeup carries over between
  sessions/weeks) **before** any profit is split.
- **Split** default **50/50**, with a per-horse override field for exceptions.
- **Deposits = the bankroll**; losses eat the bankroll and become makeup.
- Per-horse fields: name, live/online, platform(s), split %, bankroll/deposits
  (Paul's vs horse's), current makeup, running P&L, current settle-able balance.
- Nuance to confirm at design: when both Paul and horse deposit (Cata 50k/20k), whose
  money absorbs losses first / how the horse's own deposit is treated.

## Platforms / clubs (confirmed 2026-09-01)
- Multiple ClubGG clubs exist; **most play is on RomanianClub** (the only automated one).
- Known clubs now (names approximate): **RomanianClub, Carpatix, RoyalRo, a Dubai club**;
  more later. A **master ClubGG account with access to all clubs** is planned → future
  automation of the other clubs.
- **Automation scope now: RomanianClub only.** All other clubs + external sites
  (**GGpoker, PokerStars**) + live cash = **manual entry**.
- Model: every ledger line / balance carries a **platform tag**; a person can hold
  balances across several platforms (Paulinho: RomClub + Carnatix; Paladin: RomClub +
  call-or-cry + Carpatix + loren1). Platform list must be **editable/extensible**.
- Multi-club players are few for now; handle fully once Alex has the master-account scope.

## Rakeback rate changes from the notes (2026-09-01)
- **Avram Laurențiu → 70%** — APPLIED to `managers_config.COPIL_EXTRA_MEMBERS`
  (was 50%; his 24-30 sheet had used 50% — recompute if that week's balance matters).
- Pending (recorded only, NOT applied — apply deliberately later):
  - spike088 → **80%**
  - Muflender → **50%** (Royal + Dubai)
  - **Premium89** (Matin Taleby) → NEW super-agent at **80%** (needs adding to config)
  - Nemuncitorul → 50% (already matches)
