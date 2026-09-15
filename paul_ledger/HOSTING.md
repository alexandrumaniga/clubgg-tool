# Paul's Book — hosting, stack & runbook

> ⚠️ **Separate project from the ClubGG collection tool.** It merely lives in a subfolder
> of `clubgg-tool/`. Different stack, different data, different users, no shared code.
> See **[README.md](README.md)** for the side-by-side difference before touching anything.

Everything about how the live tool is hosted, why it's built this way, what it costs,
and how to operate it. Companion docs: [README.md](README.md) (what this is / isn't),
[REQUIREMENTS.md](REQUIREMENTS.md) (decisions), [DATA_MODEL.md](DATA_MODEL.md) (schema),
[NOTES_RAW.md](NOTES_RAW.md) (Paul's raw notes).

## What it is
A private, mobile-first web app tracking **who owes Paul / who Paul owes**, **staking**
(horses, makeup, splits), **loans**, and a **weekly-rakeback inbox**. Multi-currency
(RON/USD/AED). Used by Alex (maintainer, PC) and Paul (external, phone).

**Live: https://paul-ledger.pages.dev**

---

## Hosting decision — what we picked and WHY (incl. why NOT Firebase)

Requirements that drove it: Paul is **external** (not in Alex's work org); both need
access from **anywhere, phone-first**; Alex's **Python tooling must push** weekly
numbers; data is **private**; must be **cheap and low-maintenance**; login is a
**code Alex generates**, and the device is then **remembered**.

| Option | Verdict |
|---|---|
| **claude.ai Artifact + `db`/`room`** | ❌ Capability-backed artifacts are **organization-internal** — only members of Alex's claude.ai org can open them. Paul is external. (A *static* artifact is publicly shareable but has no shared storage — that's why the earlier mockup used per-device localStorage.) |
| **Alex's PC + a tunnel** (Cloudflare Tunnel / Tailscale) | ❌ Only works while Alex's PC is on and online. Paul checks at odd hours while travelling. |
| **Google Sheets** (as the whole tool) | ⚠️ Shareable and easy, but the review-inbox, staking makeup logic, converted totals and clean phone editing all fight a spreadsheet. Fallback, not best. |
| **Firebase** (Firestore + Auth + Hosting) | ⚠️ Great generic choice and my *first* recommendation — but to validate a **custom access code server-side** you need Cloud Functions, which requires the **Blaze plan + a credit card**. Firebase Auth is built around email/OAuth logins, not "a code I hand someone". |
| **Supabase** (Postgres + realtime + auth) | ⚠️ Free and capable, code check possible via Edge Functions — but **free projects pause after ~7 days of inactivity**, and Paul may not open it for a week. |
| ✅ **Cloudflare Pages + Worker + D1** | **Chosen.** Free, **no credit card**, **never pauses**, global/fast. A Worker validates the code **server-side** and issues a signed token — exactly the auth model asked for. |

**On "realtime":** Cloudflare has no push-realtime like Firestore. Not needed here — the
app refetches on focus and every ~25s, so each person sees the other's latest on open.
For two low-frequency editors that's indistinguishable from live.

**Pages, not Workers:** deploying as a Worker required registering a `workers.dev`
subdomain, and Cloudflare's onboarding link 404'd. **Pages** gives a `*.pages.dev` URL
with no subdomain step, and supports the same code via advanced-mode `_worker.js`.

---

## Cost
**$0 / month.** Cloudflare free tier: Pages (unlimited static requests), Workers
(100k req/day), D1 (5 GB storage, 5M rows read/day). This workload is two users and a
single JSON document — orders of magnitude under the limits. No credit card, no pause.
The only thing that would ever cost money is an **optional custom domain (~$10–15/yr)**;
the free `paul-ledger.pages.dev` works fine.

---

## Live architecture
```
Browser (Alex PC / Paul phone)
   |  HTTPS, same origin
   v
Cloudflare Pages  ──  dist/_worker.js  (advanced mode: API + static asset fallback)
                          |  /api/login, /api/state, /api/codes
                          v
                    D1 database "paul-ledger"
                      kv('state')  -> the whole ledger as one versioned JSON doc
                      codes        -> access codes (label, is_admin, revoked)
```
- **Static app**: `dist/index.html` served for all non-`/api` routes via `env.ASSETS`.
- **Ledger storage**: ONE versioned JSON document in `kv('state')`. Simple, and the whole
  dataset is small. Concurrency: **last-writer-wins with a version guard** — a save sends
  the `base` version it read; if someone saved in between the server returns **409** and
  the client reloads to the newest (no silent overwrite). Clients refetch on focus / 25s.

## Auth model (code login, device remembered)
1. Alex generates a code (in-app **Codes** panel, admin only).
2. Paul opens the URL, enters the code once → the Worker checks it against the `codes`
   table → returns an **HMAC-signed token** (signed with the `AUTH_SECRET` Pages secret).
3. The token is stored in that device's `localStorage` → **auto-login forever after**.
4. Revoking a code in the Codes panel kills the devices using it.
- `is_admin=1` codes additionally unlock the **Codes** panel.
- All `/api/state` calls require a valid token (no token → **401**).

### Current codes (sensitive — revocable anytime from the Codes panel)
| Code | For | Admin |
|---|---|---|
| `4FK59FEC` | original setup admin (also in `app/.admin_code.txt`) | yes |
| `KE2FD354` | Alex personal PC | yes |
| `MKDAN8` | Paul's phone | no |
| `2NTRVN`, `5TDML9` | Alex test / spare | no |

## Cloudflare account & IDs
- Account: **Alex.maniga1@gmail.com's Account**, id `9f0bc8cd3dce6bb6e64b64ba174e11f9`
- Pages project: **paul-ledger** (production branch `main`)
- D1 database: **paul-ledger**, id `3b2b560b-5927-4aa9-9794-d28ce18bb59f`
- Pages secret: **AUTH_SECRET** (production) — token signing key
- `wrangler` CLI installed globally and logged in (OAuth).

## Files
```
paul_ledger/app/
  wrangler.jsonc        Pages config + D1 binding (pages_build_output_dir = ./dist)
  schema.sql            D1 tables (kv, codes)
  sync.py               pull / push / show the live ledger
  src/worker.js         API source        -> copied to dist/_worker.js
  public/index.html     app source        -> copied to dist/index.html
  dist/                 ACTUAL deploy output (what wrangler uploads)
  data/state.json       local mirror of the live ledger (+ .base version)
  .admin_code.txt       admin code
```

---

## Runbook

### Update the ledger data (the usual: "X paid", "set Y to Z")
Always **pull first** — Alex/Paul may have edited in the app; never push a stale file.
```bash
cd paul_ledger/app
python sync.py pull      # live -> data/state.json (+ .base)
#   edit data/state.json
python sync.py push      # 409 => someone edited since pull: re-pull and redo
python sync.py show      # quick counts
```
Conventions: `amount` **+ = they owe Paul, − = Paul owes**. `paid:true` on an entry drops
it from the outstanding balance but keeps it in history (hidden behind "show settled").
To settle someone: mark all their entries `paid`. To change a balance: append an entry
for the difference (label it honestly — "payment received" vs "balance update").

### Deploy CODE changes (layout / logic)
```bash
cd paul_ledger/app
cp -r public/. dist/ && cp src/worker.js dist/_worker.js
wrangler pages deploy dist --project-name=paul-ledger --branch=main --commit-dirty=true
```

### Generate / revoke access codes
Easiest: log in with an admin code → **Codes** button in the header.
By API:
```bash
TOK=$(curl -s -X POST https://paul-ledger.pages.dev/api/login \
  -H "content-type: application/json" -d '{"code":"KE2FD354"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -X POST https://paul-ledger.pages.dev/api/codes \
  -H "authorization: Bearer $TOK" -H "content-type: application/json" \
  -d '{"label":"Someone new"}'
```
An **admin** code must be inserted directly (the API only mints normal codes):
```bash
wrangler d1 execute paul-ledger --remote --command \
  "INSERT INTO codes(code,label,is_admin,revoked,created) VALUES('NEWCODE','Label',1,0,0)"
```

### Inspect the database
```bash
wrangler d1 execute paul-ledger --remote --command "SELECT code,label,is_admin,revoked FROM codes"
wrangler d1 execute paul-ledger --remote --command "SELECT length(value) FROM kv WHERE key='state'"
```

---

## Gotchas learned the hard way
- **Cloudflare edge returns 403 to `python-urllib`'s default User-Agent.** `sync.py` sends
  a browser-like UA — keep it.
- **Windows console (cp1252) can't print Romanian characters** (ț, ș) and crashes the
  script *after* the file write. Use `PYTHONIOENCODING=utf-8` and/or
  `.encode('ascii','replace')` when printing names.
- **`dist/` is what deploys**, not `public/`+`src/`. Always copy before deploying or your
  changes silently don't ship.
- Element IDs with hyphens are **not** JS globals — a `ReferenceError` there kills the
  whole script (blank page, dead buttons). Use `getElementById`.
- The mockup's seed had Paulinho at 27,142 vs Paul's note 27,170 — a 28 gap that surfaced
  later. Seeded figures are approximations; the live ledger is the source of truth now.

## Visual design — “The Terminal” (chosen 2026-09-03)
Alex picked draft 2 of three (Ledger / Terminal / Broadsheet — see
`paul_ledger/design_drafts.html`, artifact ec7e8b98…). **Dark-only, one monospace family
(JetBrains Mono), hierarchy by weight/size only.** Totals live in a sticky **ticker strip**
(`COLLECT · PAY · NET`), tabs render as `[PEOPLE] [STAKING] …`, lists are hairline grids
with `NAME / BALANCE` column headers; **no cards, shadows, pills or chevrons**. Buttons are
bracketed text `[PAID] [EDIT] [DEL]`. Colours: ground `#0E1112`, text `#D7DEDC`, dim
`#7C8886`, credit green `#59B37E`, debit red `#D95F5F`, amber `#D9A441` = needs action /
active. The light theme and theme toggle were removed on purpose (single visual world).
Icon regenerated in the same palette (`make_icons.py`: amber chip on dark).

## Live FX (added 2026-09-03)
`GET /api/fx` (token-gated) returns `{usd_ron, aed_ron, chf_ron, source, updated}` (CHF added 2026-09-05). The **Worker**
fetches https://open.er-api.com/v6/latest/USD server-side (no CORS/key needed) and caches
the result in D1 `kv('fx')` for **6 hours**; on provider failure it serves the stale cache,
then a hard-coded fallback. The app calls it after login and recomputes the converted
grand total; AED is now converted properly instead of being lumped in with RON.

## PWA / installable (added 2026-09-03)
`public/manifest.webmanifest`, `public/sw.js`, and icons generated by
`python make_icons.py` (poker chip; `icon-192/512`, `icon-maskable-512`, `icon-180`
for iOS, `favicon.png`). The service worker is **network-first** deliberately — money must
never be stale and a deploy must apply at once; the cache is only an offline shell
fallback and `/api/` is never cached. NOTE: the deploy now copies the WHOLE `public/`
folder into `dist/`, not just index.html.

## Pending / not done yet
- **Weekly ClubGG auto-feed**: wire the weekly Python run to push proposed inbox entries
  (would call `/api/state` with a service/admin code, or write D1 directly).
- Cross-check "Cohiba" vs "Cohiba Lover" — the app has one `Cohiba` entity.

## "It asked me for the code again" (2026-09-07)
- Only the canonical URL **https://paul-ledger.pages.dev** remembers the device. Every
  deploy also prints a preview URL (`xxxxxxxx.paul-ledger.pages.dev`); that is a
  different origin with its own empty localStorage, so it always asks for a code.
  Never bookmark/share the preview link.
- Before 2026-09-07 the client showed the login screen on *any* load failure (offline,
  slow network, 5xx). Now only a real 401 (revoked/invalid token) shows it; other
  failures show a "could not reach the server - retrying" panel and keep the token.
- Tokens never expire; they die only if the code is revoked or the user taps LOGOUT.
