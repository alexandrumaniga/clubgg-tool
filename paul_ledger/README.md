# Paul's Book — a SEPARATE project

> ⚠️ **Read this first. This is NOT part of the ClubGG collection tool.**
> It only happens to live in a subfolder of `clubgg-tool/` for convenience.

## Two different projects — do not conflate them

| | **ClubGG collection tool** (parent folder) | **Paul's Book** (this folder) |
|---|---|---|
| What it is | Windows automation that drives the **ClubGG desktop app** to scrape rake / P&L and build weekly Excel/PDF reports | A **hosted web app** tracking who owes Paul money, staking (horses/makeup), and loans |
| Where it runs | Locally on Alex's PC, needs ClubGG open + `driver.py` **elevated** (UAC) | **Cloudflare** — https://paul-ledger.pages.dev — runs in the cloud, nothing local needed |
| Language / stack | Python + OCR + openpyxl + Excel COM | JavaScript (Cloudflare Worker) + D1 (SQLite) + a static HTML app |
| Data | CSVs in `clubgg-tool/output/`, roster, managers_raw, paul_submembers | One JSON doc in the **D1 `kv('state')`** table in the cloud |
| Who uses it | Alex only (it's an automation) | Alex **and Paul** (Paul logs in on his phone with a code) |
| Key files | `collect.py`, `driver.py`, `roster.py`, `managers_config.py`, `weekly_run.py` | `app/src/worker.js`, `app/public/index.html`, `app/sync.py` |
| How to change it | edit Python, run the weekly pipeline | edit data via `app/sync.py pull/push`; deploy code via `wrangler pages deploy` |

**They share no code.** `paul_ledger/` imports nothing from the ClubGG tooling, and the
ClubGG scripts know nothing about this app.

## The one intentional (future) link
The **only** planned connection is one-directional and **not built yet**: the weekly
ClubGG run will eventually *push proposed rakeback figures* into this app's
**Weekly inbox**, where Alex approves them. Until that's wired, the two are entirely
independent. Even then, it's a one-way data feed — not shared code.

## Don't do this
- ❌ Don't run the ClubGG driver/roster/OCR machinery to change data here — this app's
  data lives in the cloud; use `app/sync.py`.
- ❌ Don't edit `managers_config.py` / rakeback configs expecting this app to change,
  or vice-versa. Rakeback **percentages** for ClubGG reports and the **balances** shown
  here are maintained separately today.
- ❌ Don't put ClubGG CSVs, screenshots or reports in this folder.

## Docs in this folder
- **[HOSTING.md](HOSTING.md)** — the stack, why Cloudflare (not Firebase/Supabase), cost,
  auth/codes, and the full runbook. **Start here.**
- [REQUIREMENTS.md](REQUIREMENTS.md) — decisions made with Alex, in order.
- [DATA_MODEL.md](DATA_MODEL.md) — entities and fields.
- [NOTES_RAW.md](NOTES_RAW.md) — Paul's original raw notes (source of truth for the data).
- [UNDERSTANDING.md](UNDERSTANDING.md) — interpretation of those notes.
- [QUESTIONS.md](QUESTIONS.md) — open questions.
