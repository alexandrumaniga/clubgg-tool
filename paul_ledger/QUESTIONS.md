# Paul ledger — open questions (living doc)

Grouped, most decision-critical first. Answers get filled in inline as we discuss.

## A. Purpose & users (drives the format) — ANSWERED 2026-09-01
- A1. Maintainer → **~95% Alex**, but Paul should be able to edit *some* things if he wants.
- A2. Reader → **Mostly Alex**, but Paul must be able to check it when he wants.
- A3. Device → **Both.** Alex mainly PC. **Paul is ~80% traveling → phone**, PC at home.
- A4. Paul editing → **Occasionally edits** (mostly views).
- **Implication:** not a local-only file. Must be reachable from anywhere, phone-first
  for Paul, PC for Alex, shared between the two, with light/safe editing for Paul.
  → leans toward a hosted, mobile-friendly web view (spreadsheet-in-cloud or web app),
  final format deferred until the data model is known.

## B. Format (sheet / local tool + HTML/PDF / web app)
- B1. Preference or constraints (offline-only? phone-friendly? shareable link?)? →
- B2. Must it support add / edit / delete by hand easily, or mostly generated? →

## C. Data model & balances
- C1. Confirm sign convention: **+ = owes Paul, − = Paul owes**. →
- C2. Are the +/− lists under each name the transaction history that sums to the
     balance? Keep full history or just current net? →
- C3. Currencies RON / USD / AED — keep native per balance, or convert to one
     currency for a grand total? Do you have the rates you use? →

## D. Categories
- D1. Model these as separate buckets or one ledger: (i) ClubGG rakeback, (ii)
     staking/horses, (iii) plain debts "Datorii", (iv) Abrudan 10% rake share? →
- D2. "Datorii" — poker-related or plain personal loans? Interest / terms? →

## E. Integration with the existing weekly ClubGG tooling (BIG)
- E1. Nemuncitorul's balance (12856) equals his weekly profit-after-tipsback. Should
     CopilulNorocos members' balances be **auto-rolled from the weekly Paul sheet**,
     or is the ledger kept fully by hand? →
- E2. Staking P&L (Paladin, Cheloo, Cata…) — from ClubGG sheets or entered manually
     / from other sites (GGpoker, Stars)? →

## F. Platforms / clubs
- F1. Which of these are ClubGG clubs vs external sites: Rom Club, Carpatix/Carnatix,
     Royal, Dubai, GGpoker, Stars, "call or cry"? →
- F2. Is only RomanianClub automated, or can we also pull the other ClubGG clubs
     (Carpatix / Royal / Dubai)? →

## G. Rakeback discrepancies to resolve now
- G1. Notes say **Avram Laurențiu = 70%** but we added him at **50%**. Correct to 70%? →
- G2. Apply other rate changes from the notes to the config now (spike→80%,
     Muflender 50%, Premium89 new SA 80%)? Or keep those only in the ledger? →
     **spike088 = 80% confirmed 2026-09-07 (config/paul_rakeback.csv + app both 80%).**

## H. Staking mechanics (so I model it right)
- H1. Walk me through makeup: does the horse repay makeup fully before any profit
     split? What split %? (Paladin 50/50; is that standard?) →
- H2. Deposits (Cata: Paul 50k + horse 20k) — how do those factor into settlement? →
- H3. Live vs online horses — treated differently? →

## I. Relationships / hierarchy
- I1. Do you need the system to model agent moves / "through X" nesting (insertcoin
     under Sorin, Bluetooth8 moved SA, Paulinho via Sorin), or just the money? →

## J. Statuses / actions
- J1. Track action items & due dates (to-send 1-2 days, "pays tonight cash",
     PAID, David Pacific due 8 Oct)? A status + reminder field per entry? →

## K. Specific note ambiguities
- K1. Loren 11100 "de trimis" — who sends to whom? Related to "11100 loren1" under
     Paladin? →
- K2. GGALL shows "0" but the ledger nets to −3443 with a pending −14200 from Ivan
     — how does it reconcile to 0? →
- K3. Lupuleac +1686 USD "are de trimis" — owes Paul, or Paul sends? →
- K4. Sorin — is he an agent/partner (own Royal club) rather than a debtor? His
     ledger −14300/+70087/+500 — what does it represent? →
- K5. "Ivan", "shovelini", "dicu", "Bursuc", "Emir", "Matin Taleby" — real names /
     aliases for the nicknames? →
