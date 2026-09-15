# Paul ledger — working interpretation (DRAFT, to verify with Paul/Alex)

Everything below is my best reading of [NOTES_RAW.md](NOTES_RAW.md). Items marked
**(?)** are guesses to confirm. Nothing here is final.

## Glossary (Romanian / poker slang → meaning)
| term | meaning |
|---|---|
| de trimis | to send (money to be sent) |
| are de dat / de dat | he has to give → **owes Paul** |
| are sa ne dea / trebuie sa ne dea | he must give us → **owes Paul** |
| trebuie sa ii dam / avem sa ii dam | we must give him → **Paul owes him** |
| achitat | settled / PAID |
| achita seara asta | pays tonight |
| sapt trecută | last week |
| lei / Ron | Romanian Lei (RON) |
| dolari / usd / $ | US dollars |
| aed | UAE dirham (Dubai) |
| fisa | chip ("1 fisa = 0.5 aed" = chip↔currency rate) |
| calut (live/online) | "little horse" = a **staked player**, live or online |
| makeup | staking make-up: the hole a horse must climb out of before profit is split |
| impartit la 2 cu Paul | split 50/50 with Paul |
| profit masiv | massive profit |
| rakeback ... de trecut / trecem la | switch him to <x>% rakeback |
| mutat super agent / mutat sub X | moved to super-agent / moved under X (hierarchy change) |
| bagat la X (prin Y) | staked/entered at club X (through person Y) |
| De rerulat get roster | to-do: re-run the roster scan |

## Sign convention (verified from the ledgers)
**Positive = the person owes Paul. Negative = Paul owes the person.**
- Raiciu: −11883 +5724 +1800 = **−4359** and note says "trebuie sa ii dam 4359" (Paul owes). ✔
- PinkFloid: +54533 +35467 = **90000** and note says "trebuie sa ne dea 90k" (owes Paul). ✔

## Currencies in play
RON (lei), USD (dolari/$), AED (Dubai, but Paul's Dubai share is expressed in USD;
1 chip = 0.5 AED). Most balances are RON; a few are USD (Lupuleac, Cohiba, Ana,
Dubai). **Multi-currency is required.**

## Apparent categories (may become separate tables/views)
1. **ClubGG rakeback balances** — CopilulNorocos members / SAs whose balance is the
   accumulation of weekly rakeback settlement. Many map to members we already track.
2. **Staked players ("caluti")** — live & online; have makeup, deposits, profit split.
   (Paladin 50/50, Cheloo, Cata, ketamin(?), DaniParaschiv(?))
3. **Plain debts ("Datorii")** — fixed amounts owed to Paul, some with due dates.
4. **External rake shares** — 10% of rake from a couple of Abrudan's players.
5. **Cross-platform play** — same person active on several clubs/sites at once.
6. **Hierarchy moves** — agents/players moved under a super-agent or "through" someone.

## Platforms / clubs mentioned
- **Rom Club** = RomanianClub (ClubGG) — the one our tooling already automates.
- **Carpatix / Carnatix** — a club (ClubGG club? external?) **(?)**
- **Royal** club — **(?)**
- **Dubai** club — ClubGG club, chips priced in AED, players get 50%, Paul 80% share **(?)**
- **GGpoker** — external site.
- **Stars** (PokerStars) — external site.
- **call or cry** — a club/game **(?)**

## Entities extracted (balance: + = owes Paul, − = Paul owes; ⟵ = maps to a ClubGG member)
| # | Name | Balance | Cur | Category | Rakeback | Notes / ClubGG link |
|---|---|--:|---|---|---|---|
| 1 | Loren | 11100 | RON? | ? | | "de trimis (1-2 zile)"; direction unclear. Also "11100 loren1" appears under Paladin ⟵ LorenBoss 9814-1348? **(?)** |
| 2 | Dexter | 0 | | | | ⟵ Dexter001 SA group |
| 3 | GGALL | 0 | RON | rakeback | | still to collect 14200 from **Ivan**; ledger 300/+9000/−5000/+6457/−14200 ⟵ GGALLPkR 9790-5912 |
| 4 | Muflender | −2790 (owes? see note) | RON | rakeback | 50% (Royal+Dubai) | "are de dat 2790" = **owes Paul 2790** ⟵ muflender 2562-4159 |
| 5 | Raiciu | −4359 | RON | ? | | Paul owes; a club/agent people are "staked at through Sorin" |
| 6 | PinkFloid | +90000 | RON | ? | | owes Paul; +54533 +35467 |
| 7 | ssRMN | −3930 | RON | rakeback | | Paul owes ⟵ gsRMN 8920-6033 |
| 8 | Lupuleac | +1686 | USD | ? | | "are de trimis" — direction to confirm |
| 9 | Paulinho | +27170 | RON | rakeback + multi-club | | owes Paul; at Raiciu (through Sorin) + Carpatix; RomClub +13600/−3100/+15475, Carnatix +1167 ⟵ Paulinho0909 4197-8992 |
| 10 | spike (Bursuc) | +5000 | RON | rakeback | **80%** (from last wk) | owes; sent 3700 to Avram ⟵ spike088 4715-1001 |
| 11 | Avram Laurențiu | −6086 | RON | rakeback + staking? | **70%** | Paul owes, pays tonight cash; added to CopilulNorocos ⟵ Laurentiu Avram 1511-7925 **⚠ we set 50%, notes say 70%** |
| 12 | Sorin | ? | RON | agent | | has Royal club; send 14300 to Abrudan; insertcoin(Stars) moved under him; ledger −14300/+70087/+500 |
| 13 | DaniParaschiv | +10500 | RON | staking? | | "de la shovelini" |
| 14 | Montana (Emir) | +38171 | RON | rakeback | | pays in Albania; +32676 +5495 ⟵ Montana811 4038-7377 (we just EXCLUDED from downline — left the club but still owes) |
| 15 | Cohiba | −15213 | USD | SA group | | Paul to pay; ledger −69352/+457; Bluetooth8 moved super-agent ⟵ Cohiba SA group |
| 16 | Premium89 (Matin Taleby) | new | | SA | **80%** | new super-agent |
| 17 | skybri / Skybri | −6563 | RON | rakeback | | Paul owes; −5513 −1050 ⟵ SkyBri777 6506-3317 |
| 18 | Paladin | profit 23589, **50/50** | RON | **staking** | | split with Paul; RomClub +1349, call-or-cry −1200, Carpatix 12340, loren1 11100 ⟵ Paladin9 8839-4897 |
| 19 | ketamin | "profit masiv" | | staking? | | amount TBD |
| 20 | cheloo | makeup 2256 | RON? | **staking (online)** | | online horse |
| 21 | Dubai (bucket) | Paul share 1340 | USD | platform | 80% Paul / 50% players | 1 chip=0.5 AED; 2Highwins(dicu) +906 USD **PAID** |
| 22 | Cata | makeup 6400 | RON | **staking (live)** | | Paul deposited 50k RON, horse 20k RON |

## Debts ("Datorii") — owed to Paul (?)
| Name | Amount | Cur | Due | ClubGG link |
|---|--:|---|---|---|
| Ana | 5900 | USD | | |
| Andrees Camion | 13500 | RON | | |
| David Pacific | 13500 | RON | **8 Oct** | |
| Dan Pincaru | 6000 | RON | | |
| Sberea | 15200 | RON | | |
| David Duma | 5000 | RON | | |
| Ascunde-le | 12950 | RON | | ⟵ Ascunde-le! 1425-5428 |
| Veress | 135913 | RON | | ⟵ Veres (a MANAGER) |

## External rake share
10% of rake from a couple of **Abrudan's** players: **GOREGX**, **TYLLIND**.

## Misc / to-do in notes
- "De rerulat get roster" — re-run roster scan.
- "De găsit un breloc cu un elf" — personal to-do (find an elf keychain); not part of the system.

## Big observation — this overlaps the weekly ClubGG numbers
Several balances equal the weekly rakeback figures we already compute. Clearest:
**Nemuncitorul owes 12856** and his 24–30 profit-after-tipsback (50%) was **−12855.88**.
So at least the CopilulNorocos members' balances look like accumulated weekly
rakeback settlements → the ledger could be **fed automatically** from the Paul sheet
rather than typed by hand. To confirm with Paul/Alex.

## Rakeback deltas implied by the notes (may need to update the config)
- Avram Laurențiu → **70%** (currently set to 50%)
- Nemuncitorul → 50% (matches)
- spike088 → **80%**
- Muflender → 50% (Royal + Dubai)
- Premium89 → new SA **80%**

## Open questions
See the running list in [QUESTIONS.md](QUESTIONS.md).
