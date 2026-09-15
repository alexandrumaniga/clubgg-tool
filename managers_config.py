"""Club manager / super-agent structure for the general-club-managers-results
report. Manager aliases are pseudonyms requested by the user."""

# alias -> ClubGG member id
MANAGERS = {
    "Veres":   "2554-4367",   # in-app: Veresss
    "Abrudan": "1350-3167",   # in-app: StormSpirit88
    "Paul":    "5179-8144",   # in-app: PopaVerde
}

# super-agent id -> manager alias (who the SA belongs to)
SA_TO_MANAGER = {
    # --- Paul (7) ---
    "4698-9934": "Paul",
    "6061-4281": "Paul",
    "1383-9092": "Paul",
    "2801-0595": "Paul",
    "2671-5435": "Paul",
    "5972-2561": "Paul",
    "9583-9412": "Paul",      # Premium89 (Matin Taleby) - new SA, 80% rakeback
    # --- Abrudan (13) ---
    "8035-1495": "Abrudan",
    "8637-7916": "Abrudan",
    "6985-1738": "Abrudan",
    "7373-8956": "Abrudan",
    "3330-0334": "Abrudan",
    "4595-5186": "Abrudan",
    "3698-4023": "Abrudan",
    "6896-0336": "Abrudan",
    "7026-2052": "Abrudan",
    "3200-8832": "Abrudan",
    "5606-1021": "Abrudan",
    "5906-5014": "Abrudan",
    "3245-8417": "Abrudan",
    "6294-7248": "Abrudan",   # OMGimBusto - top-level SA; moved Paul->Abrudan 2026-09-05 (Alex)
    "5438-1780": "Abrudan",   # GerrardS8 - promoted out of uucj1919 to top-level SA
    "6591-8601": "Abrudan",   # Carmelo88 (Carme1088) - moved from Paul's Cohiba group 2026-09-12, 100%
    "3563-5971": "Abrudan",   # Azem Bejta - SUPER AGENT since ~2026-09-13 (was a plain player on 09-12)
    "7919-4380": "Paul",      # Terremoto89 - new SA (Alex 2026-09-14), 80% on Paul's sheet
    "4472-5253": "Paul",      # Luzny_Benek - new SA (Alex 2026-09-14), 70% on Paul's sheet
                              # (found 2026-09-03; was only in ABRUDAN_AGENTS before,
                              #  so its play was counted nowhere in the managers report)
    # --- Veres (1) ---
    "5368-8498": "Veres",
}


def sas_of(alias):
    """Super-agent ids belonging to a manager alias."""
    return [sid for sid, m in SA_TO_MANAGER.items() if m == alias]


# Extra PLAYERS to include directly in a manager's section of the GENERAL
# managers report. They sit directly under a manager (not via a super agent),
# so they are collected from their personal Game Statistics and get the same
# 100% rakeback as everything in that report.
# KingTwoSuited (1409-8482) was moved UNDER CopilulNorocos, so he is now counted
# inside CopilulNorocos's super-agent aggregate - no separate player row here.
# shortbusbully88 (4243-3806) sits directly under Abrudan (not under super-agent
# uucj1919, whose aggregate already covers the other fresh agents), so without an
# explicit row here his Fee/P&L would be missing from the managers report and the
# club books would not close (his 24-30 net was the whole 2,590.43 gap).
MANAGER_EXTRA_PLAYERS = {
    # "4243-3806" shortbusbully88 - removed from the club (Alex, 2026-09-12)
    # 3563-5971 Azem Bejta moved to SA_TO_MANAGER 2026-09-14 (promoted to super agent; player flow read 0)
    "2914-2112": "Abrudan",   # HHH000 - player, no upline badge (id looked up 2026-09-14)
}


def extra_players_of(alias):
    """Extra-player ids to show in a manager alias's section."""
    return [pid for pid, m in MANAGER_EXTRA_PLAYERS.items() if m == alias]


# Super-agent GROUPS owned by Paul. A group is a super agent that owns other
# super agents nested under it; each member's Super-Agent-Statistics is
# collected SEPARATELY (by id) and the whole group is SUMMED into ONE combined
# row (the group head's own stats do NOT already include the nested ones).
# Shown as one row under Paul in the managers report (100%) and on Paul's sheet
# at the group's 'pct'.
COHIBA_GROUP_MANAGER = "Paul"          # groups all belong to Paul
PAUL_SA_GROUPS = [
    {"key": "cohiba", "name": "Cohiba Lover (+group)", "pct": 80, "ids": [
        "6970-7909",   # Cohiba Lover
        "9112-8477",   # djecko1
        "3040-9892",   # Iroh
        "8770-3350",   # LarryLegend
        "7731-1905",
        "2183-9417",
        "9341-7037",   # DonnieBrasco12
        "9222-8880",
        # "6591-8601" Carmelo88 moved from Paul's Cohiba group to Abrudan (Alex, 2026-09-12)
        "4070-8185",   # POT!!
        "7410-9404",   # gin-fizz (Gin-Fizz)
        "7826-7133",   # Bluetooth8 - promoted to super agent but STAYS in the
                       # Cohiba group total (confirmed 2026-09-03)
    ]},
    {"key": "dexter", "name": "Dexter001 (+group)", "pct": 80, "ids": [
        "2801-0595",   # Dexter001 (was an individual SA at 70%)
        "9531-4227",
    ]},
    {"key": "cashvick", "name": "Cashvick (+group)", "pct": 80, "ids": [
        "1394-6890",   # Cashvick
        "6872-8668",
        "1048-3598",
        "1463-0813",
    ]},
]


def paul_group_ids():
    """All member ids across every Paul super-agent group."""
    return [cid for g in PAUL_SA_GROUPS for cid in g["ids"]]


# --------------------------------------------------------------------------
# Paul per-super-agent rakeback report (paul_report.py / build_paul_sheet.py)
#
# Section 1 of Paul's sheet lists these super agents with a DIFFERENT rakeback
# each (profit-after-rakeback = P&L + rakeback% * Rake). Data is reused from
# the managers report (managers_raw_<range>.csv) - no re-collection.
# CopilulNorocos (COPIL_OWNER) is deliberately NOT shown as a super-agent row;
# instead all members under it are listed individually in section 2.
PAUL_SA_RAKEBACK = {          # individual (non-grouped) super-agent id -> %
    "4698-9934": 80,
    "6061-4281": 80,
    "1383-9092": 80,
    "5972-2561": 80,
    "9583-9412": 80,          # Premium89 (Matin Taleby) - per Paul's notes, 80%
    "7919-4380": 80,             # Terremoto89 (Alex 2026-09-14)
    "4472-5253": 70,             # Luzny_Benek (Alex 2026-09-14)
}                             # Dexter001 (2801-0595) moved to a group (80%);
                              # Honey2025 (8282-7963) left the club - removed

# CopilulNorocos is another account of Paul with its own agents & players.
COPIL_OWNER = "2671-5435"            # not shown; expanded into its sub-members
COPIL_OWNER_NAME = "CopilulNorocos"  # roster 'agent' value for its members


# --------------------------------------------------------------------------
# Abrudan rakeback report (abrudan_report.py / build_abrudan_sheet.py)
# A flat list of entities to show. SAs (+ the manager StormSpirit88) REUSE
# Rake/P&L from the managers report; the ABRUDAN_AGENTS are collected fresh
# from their own statistics page. uucj1919 (7373-8956) itself is NOT included,
# but two entities sitting under it (gerardsb, Sodooo1) are listed individually.
ABRUDAN_SA_RAKEBACK = {          # id -> rakeback %  (reused from managers_raw)
    "8637-7916": 83,             # TheGermanGiant
    "6985-1738": 80,             # AzizLaGuerr
    "3698-4023": 100,            # Utzzu
    "6896-0336": 83,             # Knikovski
    "3200-8832": 83,             # PlayingCardsUsa
    "5606-1021": 75,             # YourPoker (Abrudan list 2026-09-12: 75%, was 80)
    "5906-5014": 80,             # Imigor (roster: Imlgor)
    "3245-8417": 80,             # PinotGrigio2026
    "6294-7248": 95,             # OMGimBusto (Abrudan list 2026-09-06: 95%)
    "5438-1780": 100,            # GerrardSB - now a top-level SA (collected by the managers run), 100%
    "6591-8601": 100,            # Carmelo88 (Abrudan list 2026-09-12; was in Paul's Cohiba group)
}                                # StormSpirit88 removed from Abrudan's list
ABRUDAN_AGENTS = {               # id -> rakeback %  (collected fresh via stats)
    "4401-4616": 80,             # Sodooo1 (roster: sodoool, under uucj)
    "2505-9401": 60,             # Seth777 (under uucj)
    "9669-7269": 90,             # Scroafa (under uucj)
    "2308-3273": 70,             # Runninggood (roster: runninggoodl, under uucj)
    # shortbusbully88 (4243-3806) removed from Abrudan's sheet 2026-09-06 (confirmed by Alex);
    # he stays in MANAGER_EXTRA_PLAYERS so the managers report still reconciles.
    "3529-4140": 90,             # Tank
    "9370-6069": 80,             # UFCfan (SA under uucj1919; id looked up 2026-09-07 - nested SA,
                                 # so his play is inside uucj1919's aggregate: NOT a SA_TO_MANAGER entry)
    "3563-5971": 80,             # Azem Bejta (player, no upline; Abrudan list 2026-09-12; id looked up 2026-09-12)
    "2914-2112": 80,             # HHH000 (player, no upline; Abrudan list 2026-09-14; id looked up 2026-09-14)
}
# canonical display names (the OCR'd names have variants like UtzzU / Imlgor)
ABRUDAN_NAMES = {
    "8637-7916": "TheGermanGiant", "6985-1738": "AzizLaGuerr",
    "3698-4023": "Utzzu",         "6896-0336": "Knikovski",
    "3200-8832": "PlayingCardsUsa", "5606-1021": "YourPoker",
    "6294-7248": "OMGimBusto",
    "5906-5014": "Imigor",        "3245-8417": "PinotGrigio2026",
    "5438-1780": "gerardsb",      "4401-4616": "Sodooo1",
    "2505-9401": "Seth777",       "9669-7269": "Scroafa",
    "2308-3273": "Runninggood",   "4243-3806": "shortbusbully88",
    "3529-4140": "Tank",          "9370-6069": "UFCfan",
    "6591-8601": "Carmelo88",     "3563-5971": "Azem Bejta",   "2914-2112": "HHH000",
}
# NOT a global rate: rakeback is PER MEMBER in config/paul_rakeback.csv (one
# editable row per player/agent). This is only the value seeded into a member's
# own row the first time the roster detects them - edit each row individually.
COPIL_SUBMEMBER_RAKEBACK = 0         # per-new-member seed default (was 60)

# Extra members to COLLECT and show under CopilulNorocos in Paul's report even
# if the (possibly stale) roster doesn't list them there yet. paul_report opens
# each by id and auto-detects the role (an Agent uses Agent Statistics), so the
# data is fresh - not reused from the managers report. id -> rakeback %.
COPIL_EXTRA_MEMBERS = {
    "1409-8482": 60,      # KingTwoSuited = Lupuleac (Agent under CopilulNorocos) - 60% from 2026-09-07 (Alex 2026-09-14; was 50)
    # New downline members found via Downline Management (2026-09-01) that were
    # not yet in the Aug-23 roster; collected fresh, 50% rakeback each.
    "1511-7925": 70,      # Laurentiu Avram (Paul's notes: 70%, corrected 2026-09-01)
    "2740-8784": 50,      # Ilexas_llaxa
    "4725-8141": 50,      # nemuncitoruL
    "4917-8602": 50,      # luckyhke27
    "6739-3615": 50,      # Alec21732
    # From Alex's Downline Players screenshots 2026-09-06 (48 members):
    "7687-5189": 60,      # GiversTakers - 60% (Alex, 2026-09-07)
    # From Alex's Downline Players screenshots 2026-09-12 (52 members, 4 new; default 50%):
    "8748-4909": 50,      # tdr2021
    "6740-2064": 50,      # TyranT1979
    "9755-3611": 80,      # Manea12 - agent under CopilulNorocos, 80% (Alex 2026-09-14; was 50)
    "8196-1768": 50,      # 2HighWins (Dicu's RomanianClub account; he is 2Highwins (dicu) in Paul's Book)
}

# Members still listed under CopilulNorocos in the (stale) roster but who have
# LEFT his downline - excluded from collection and from Paul's sheet.
COPIL_EXCLUDE = {
    "4038-7377",          # Montana811 (left downline)
    "7834-4366",          # Ins3rtC0in (left downline)
    "2314-3592",          # matt888 - gone from downline (screenshots 2026-09-06)
    "6536-7557",          # MrJuveLaButoane - gone from downline (screenshots 2026-09-06)
    "1400-2797",   # Hayanski@ - Paul's OWN account (Alex, 2026-09-12): not a member row on his sheet
}


# ---------------------------------------------------------------------------
# CRISTIAN VERES' downline sheet (veres_report.py) - requested by Alex 2026-09-14.
# Members from Alex's Downline Players screenshots (18, "Total Downline Players 18");
# all at 50% until Alex gives the real tipsback per member.
VERES_SA = "5368-8498"           # Cristian Veres (super agent under manager Veres)
VERES_DEFAULT_PCT = 50
VERES_NAMES = {
    "3173-2942": "Bogdi94",        "9177-7885": "Giumpi",         "4690-8610": "Moohemoohe",
    "2891-7189": "AnghouraYamil",  "8101-6850": "TB26",           "9789-8899": "Sergio10_bogdan",
    "8161-4823": "dasem29",        "2236-7952": "Checkpervers",   "2473-7294": "Fernando1326",
    "1049-7958": "Oly2031",        "9381-4589": "foldqq",         "5056-8747": "dexter16",
    "8207-9146": "Call___Me",      "1495-0665": "Julian 91",      "4630-8911": "regbait",
    "1149-0277": "cannoncino23",   "7004-3391": "PoatePune1",     "7755-9202": "PokerKid13",
}
VERES_MEMBERS = {pid: VERES_DEFAULT_PCT for pid in VERES_NAMES}   # id -> tipsback % (50 = placeholder)
VERES_MEMBERS.update({                                               # rates from Alex 2026-09-14
    "8101-6850": 70,     # TB26
    "9789-8899": 50,     # Sergio10_bogdan
    "3173-2942": 0,      # Bogdi94
    "2473-7294": 0,      # Fernando1326
    "1049-7958": 0,      # Oly2031
    "8207-9146": 50,     # Call___Me
    "2891-7189": 70,     # AnghouraYamil
})


# OCR / display-name fixes for ids in managers_raw (applied by statement.py and build_managers_sheet.py)
NAME_OVERRIDES = {
    "1463-0813": "Rojjerr",       # Cashvick group SA - OCR read it as "Qoiierr" (Alex, 2026-09-14)
}
