r"""general-club-managers-results: weekly club situation across the 3 managers.

For a date range it collects, per manager (Veres/Abrudan/Paul):
  - the MANAGER's own rake & P&L from the member Custom stats
  - each of their SUPER AGENTS' Fee(=rake) & P&L from the SA's
    "Super Agent Statistics" -> Custom page
Plus the club BAD BEAT JACKPOT from Club Data (Profit&Loss - Fee for the
range). Then builds an Excel sheet: one table per manager (manager row +
their SA rows) and a summary of each manager's combined profit + BBJ/3.

Usage:
  python managers_report.py 2026-08-03 2026-08-09
  python managers_report.py 2026-08-03 2026-08-09 --build-only   # rebuild xlsx

Prereqs: ClubGG open + driver.py elevated (auto-restarts on capture block).
"""
import csv
import re
import sys
import time
from datetime import date
from pathlib import Path

from PIL import Image

import collect
from collect import (CaptureBlocked, block_recovery, click, day_cell,
                     enter_club, goto_member_list, ocr_lines, ocr_text,
                     read_money, read_stats_on_detail, screen_of,
                     search_open, select_calendar_range, send, send_once, shot)
import managers_config as mc

ROOT = Path(__file__).parent
ROSTER = None


def roster_name(pid):
    global ROSTER
    if ROSTER is None:
        ROSTER = {}
        files = sorted((ROOT / "output").glob("clubgg_roster_*.csv"))
        if files:
            ROSTER = {r["player_id"]: r["name"]
                      for r in csv.DictReader(files[-1].open(encoding="utf-8"))}
    return ROSTER.get(pid, "")


# --------------------------------------------------------------- navigation --

def goto_lobby():
    """Navigate to the club lobby (where the red 4-dot menu lives)."""
    p = shot("navL")
    for _ in range(10):
        scr = screen_of(ocr_lines(p))
        if scr == "lobby":
            return p
        if scr == "calendar":
            p = click(270, 120, name="navL", settle=0.6)
        else:                                  # members / detail / unknown
            p = click(25, 62, name="navL", settle=1.0)
    raise RuntimeError("could not reach the club lobby")


# ------------------------------------------------------------- reading bits --

def read_labeled_money(img, label_pred, tag):
    """Find a stat row whose left-column label matches label_pred(text) and
    read the money value on its right."""
    for y, x, t in ocr_lines(img):
        if x < 170 and label_pred(t):
            return read_money(img, (280, int(y) - 15, 512, int(y) + 15), tag)
    raise RuntimeError(f"[{tag}] label row not found")


def money_at(img, y, tag):
    """Read the money value on row `y`. Returns 0.0 only when NO OCR variant
    finds any digit (a genuinely empty/zero-activity cell) - a single blank
    variant must not zero out a real value. Otherwise defers to read_money's
    consensus (which raises only on a non-empty malformed read)."""
    box = (280, int(y) - 15, 512, int(y) + 15)
    for scale, th in ((6, None), (4, None), (8, None), (6, 110)):
        if re.search(r"\d", collect.ocr_money_text(img, box, scale=scale,
                                                    thresh=th) or ""):
            return read_money(img, box, tag)
    return 0.0


def color_sign(img, box):
    """Sign of a P&L value from its colour: ClubGG shows losses RED and
    profits GREEN. OCR drops the leading '-' unreliably, so colour is the
    trustworthy sign source. Returns -1 (red/loss) or +1 (green/white)."""
    crop = Image.open(img).crop(box).convert("RGB")
    bright = [(r, g, b) for r, g, b in crop.get_flattened_data()
              if max(r, g, b) > 90]
    if not bright:
        return 1
    mr = sum(p[0] for p in bright) / len(bright)
    mg = sum(p[1] for p in bright) / len(bright)
    return -1 if mr > mg + 25 else 1


def signed_pnl(img, y, tag):
    """P&L for the row at `y`: magnitude from OCR, sign from cell colour."""
    mag = abs(money_at(img, int(y), tag))
    if mag == 0:
        return 0.0
    return round(color_sign(img, (300, int(y) - 14, 512, int(y) + 14)) * mag, 2)


# ------------------------------------------------------------- manager stat --

def read_member_custom_stats(p, start, end, tag):
    """Read a member's Game-Statistics Custom Rake & P&L by LOCATING the
    'Custom' tab and the 'Rake'/'Profit & Loss' label rows - robust to the
    manager layout (which shifts everything up ~1 row vs a normal player)."""
    cy = None
    for y, x, t in ocr_lines(p):
        if t.strip().lower() == "custom" and x > 340 and 520 < y < 690:
            cy = int(y)
            break
    if cy is None:
        raise RuntimeError("Custom tab not found on member detail")
    pc = click(428, cy, name=f"{tag}_cust", settle=1.0)
    if screen_of(ocr_lines(pc)) != "calendar":
        raise RuntimeError("Custom did not open the date picker")
    pr = select_calendar_range(pc, start, end, tag=f"{tag}_c")
    last = None
    for attempt in range(4):
        if attempt:
            time.sleep(0.6)
            pr = shot(f"{tag}_st")
        try:
            labels = {t.strip().lower(): int(y)
                      for y, x, t in ocr_lines(pr) if x < 170}
            if "rake" in labels and any("profit" in k for k in labels):
                ry = labels["rake"]
                py = next(y for k, y in labels.items() if "profit" in k)
                return (money_at(pr, ry, f"{tag}_rk"),      # rake >= 0
                        signed_pnl(pr, py, f"{tag}_pl"))    # sign by colour
            raise RuntimeError("Rake / Profit&Loss labels not visible")
        except (ValueError, RuntimeError) as e:
            last = e
    raise RuntimeError(f"manager stats unreadable: {last}")


def collect_manager(mid, start, end, tag):
    """Manager: open member, read personal Custom rake & P&L."""
    goto_member_list("All")                 # guarantee a clean starting screen
    p = search_open(mid, roster_name(mid), tag)
    if p is None:
        raise RuntimeError(f"manager {mid} not found via search")
    name = ocr_text(p, (125, 108, 360, 140), scale=3).strip() or roster_name(mid)
    rake, pnl = read_member_custom_stats(p, start, end, tag)
    click(25, 62, name=f"{tag}_back", settle=0.9)     # -> member list
    return name, rake, pnl


# ---------------------------------------------------------- super-agent stat -

def open_super_agent_statistics(tag):
    """From an open member detail page, scroll to the Super Agent Management
    section and open 'Super Agent Statistics'. Returns that page's screenshot."""
    for i in range(5):
        p = send({"action": "swipe", "x1": 270, "y1": 820, "x2": 270,
                  "y2": 340, "shot": str(collect.SHOTS / f"{tag}_sm.png"),
                  "settle": 0.7})
        img = collect.SHOTS / f"{tag}_sm.png"
        for y, x, t in ocr_lines(img):
            tl = t.lower()
            if "agent" in tl and "statistic" in tl and x < 260 and 200 < y < 900:
                return click(270, int(y), name=f"{tag}_saopen", settle=1.5)
    raise RuntimeError("'Super Agent Statistics' button not found")


def read_agent_stats_custom(start, end, tag):
    """From an already-open Agent / Super-Agent Statistics page: open the
    Custom tab, pick the date range and read Fee & Profit&Loss. Returns
    (fee(=rake) >= 0, signed P&L). Shared by super agents (managers report) and
    the agents under an owner-account (Paul report). The two pages differ in
    height - the agent page is more compact - so the Custom tab is LOCATED by
    OCR rather than hardcoded, and Fee/P&L are read before scrolling (they are
    already visible on the compact agent page) with scroll as a fallback."""
    p = shot(f"{tag}_sacur")
    cy = None
    for y, x, t in ocr_lines(p):
        if t.strip().lower() == "custom" and x > 340 and y > 640:
            cy = int(y)
            break
    if cy is None:
        raise RuntimeError("Custom tab not found on Agent Statistics page")
    p = click(428, cy, name=f"{tag}_sacustom", settle=1.2)
    if screen_of(ocr_lines(p)) != "calendar":
        raise RuntimeError("Agent Statistics Custom did not open the date picker")
    p = select_calendar_range(p, start, end, tag=f"{tag}_sa")
    for attempt in range(4):
        if attempt == 0:
            img = shot(f"{tag}_sd")                 # values often already shown
        else:
            send({"action": "swipe", "x1": 270, "y1": 780, "x2": 270,
                  "y2": 380, "shot": str(collect.SHOTS / f"{tag}_sd.png"),
                  "settle": 0.7})
            img = collect.SHOTS / f"{tag}_sd.png"
        labels = {t.strip().lower(): int(y)
                  for y, x, t in ocr_lines(img) if x < 170}
        if any(k == "fee" for k in labels) and any("profit" in k for k in labels):
            fy = labels["fee"]
            py = next(y for k, y in labels.items() if "profit" in k)
            return (money_at(img, fy, f"{tag}_fee"),      # fee(rake) >= 0
                    signed_pnl(img, py, f"{tag}_pnl"))    # sign by colour
    raise RuntimeError("Agent Fee / Profit&Loss not found after scrolling")


def collect_super_agent(sid, start, end, tag):
    """Super agent: open member -> Super Agent Statistics -> Custom range ->
    read Fee (rake) & Profit&Loss."""
    goto_member_list("All")                 # guarantee a clean starting screen
    p = search_open(sid, roster_name(sid), tag)
    if p is None:
        raise RuntimeError(f"super agent {sid} not found via search")
    name = ocr_text(p, (125, 108, 360, 140), scale=3).strip() or roster_name(sid)
    open_super_agent_statistics(tag)
    fee, pnl = read_agent_stats_custom(start, end, tag)
    click(25, 62, name=f"{tag}_b1", settle=1.0)       # SA stats -> detail
    click(25, 62, name=f"{tag}_b2", settle=1.0)       # detail -> member list
    return name, fee, pnl


# ------------------------------------------------------------ bad beat jackpot

def collect_bbj(start, end, tag="bbj"):
    """Club Data -> set range -> BBJ = Profit&Loss - Fee for the range."""
    # open the Club Data menu, verifying it actually loaded (retry if not)
    p = None
    for _ in range(3):
        pl = goto_lobby()
        # the red 4-dot menu toggles: only click it to OPEN if it's not
        # already expanded (clicking an open menu closes it - the bug we hit)
        menu_open = any(t in ("Inbox", "Data", "Counter", "Admin")
                        for _, _, t in ocr_lines(pl))
        if not menu_open:
            pl = click(485, 931, name=f"{tag}_rm", settle=0.9)
            if not any(t in ("Inbox", "Data", "Counter")
                       for _, _, t in ocr_lines(pl)):
                continue                                    # menu didn't open
        p = click(344, 935, name=f"{tag}_data", settle=1.8)   # Data
        if any("Club Data" in t for _, _, t in ocr_lines(p)):
            break
    else:
        raise RuntimeError("could not open the Club Data menu")
    # OCR-locate the date-range line near the top and click its centre
    dy = 150
    for y, x, t in ocr_lines(p):
        if y < 235 and "Club Data" not in t and re.search(r"20\d\d-\d\d-\d\d", t):
            dy = int(y)
            break
    p = click(270, dy, name=f"{tag}_date", settle=1.3)
    if screen_of(ocr_lines(p)) != "calendar":
        raise RuntimeError("Club Data date did not open the date picker")
    p = select_calendar_range(p, start, end, tag=tag)
    pbox = (150, 353, 348, 386)
    pnl = abs(read_money(p, pbox, f"{tag}_pnl")) * color_sign(p, pbox)
    fee = read_money(p, (350, 353, 512, 386), f"{tag}_fee")
    goto_lobby()
    return pnl, fee, round(pnl + fee, 2)          # BBJ = Club P&L + Fee


# ----------------------------------------------------------------- orchestrate

FIELDS = ["kind", "manager", "id", "name", "rake", "profit_loss"]


def raw_path(start, end):
    return ROOT / "output" / f"managers_raw_{start}_{end}.csv"


def bbj_path(start, end):
    return ROOT / "output" / f"managers_bbj_{start}_{end}.txt"


def run(start, end):
    out = raw_path(start, end)
    out.parent.mkdir(exist_ok=True)
    done = {}
    if out.exists():
        done = {r["id"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
        print(f"resuming: {len(done)} entries already collected", flush=True)

    # build the ordered work list: each manager then its super agents
    work = []   # (kind, alias, id)
    for alias in ("Veres", "Paul", "Abrudan"):
        work.append(("manager", alias, mc.MANAGERS[alias]))
        for sid in mc.sas_of(alias):
            work.append(("sa", alias, sid))
        for pid in mc.extra_players_of(alias):     # players directly under mgr
            work.append(("player", alias, pid))
        if alias == mc.COHIBA_GROUP_MANAGER:       # Paul super-agent groups
            have = {w[2] for w in work}            # skip ids already queued
            for cid in mc.paul_group_ids():
                if cid not in have:
                    work.append(("cohiba", alias, cid))
                    have.add(cid)

    recover = block_recovery(tab="All",
                             emit=lambda e: print("  " + e.get("msg",
                                 e.get("error", "")), flush=True)
                             if e.get("kind") in ("log", "blocked") else None)

    mode = "a" if done else "w"
    f = out.open(mode, newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if mode == "w":
        w.writeheader()

    try:
        send({"action": "setwin"})
        goto_member_list("All")
    except CaptureBlocked:
        if not recover():
            f.close()
            return

    i = 0
    while i < len(work):
        kind, alias, pid = work[i]
        if pid in done:
            i += 1
            continue
        tag = f"m{i:02d}"
        try:
            if kind in ("manager", "player"):     # both read personal stats
                name, rake, pnl = collect_manager(pid, start, end, tag)
            else:
                name, rake, pnl = collect_super_agent(pid, start, end, tag)
            rec = {"kind": kind, "manager": alias, "id": pid, "name": name,
                   "rake": rake, "profit_loss": pnl}
            w.writerow(rec)
            f.flush()
            done[pid] = rec
            print(f"[{len(done)}] {kind} {alias} {name} ({pid}) "
                  f"rake={rake} pnl={pnl}", flush=True)
            i += 1
        except CaptureBlocked:
            if not recover():
                break
        except Exception as e:                        # skip, flag, continue
            print(f"  SKIPPED {kind} {alias} {pid}: {e}", flush=True)
            w.writerow({"kind": kind, "manager": alias, "id": pid,
                        "name": roster_name(pid), "rake": "ERR",
                        "profit_loss": "ERR"})
            f.flush()
            done[pid] = {"id": pid}
            i += 1
            try:                                       # get back to a clean list
                goto_member_list("All")
            except Exception:                          # incl. CaptureBlocked
                if not recover():
                    break
    f.close()

    # bad beat jackpot (once)
    bp = bbj_path(start, end)
    if not bp.exists():
        for _ in range(6):
            try:
                pnl, fee, bbj = collect_bbj(start, end)
                bp.write_text(f"pnl={pnl}\nfee={fee}\nbbj={bbj}\n",
                              encoding="utf-8")
                print(f"BBJ: P&L={pnl} Fee={fee} -> BBJ={bbj}", flush=True)
                break
            except CaptureBlocked:
                if not recover():
                    break
            except Exception as e:
                print(f"  BBJ read failed: {e}", flush=True)
                break
    print("collection done", flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    if "--build-only" not in sys.argv:
        if not collect.driver_alive():
            print("ERROR: driver not running")
            sys.exit(2)
        run(start, end)
    import build_managers_sheet          # noqa - builds the xlsx
    build_managers_sheet.build(start, end)
