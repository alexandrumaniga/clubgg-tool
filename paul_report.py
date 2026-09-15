r"""Paul per-super-agent rakeback report (part 2 of the club results).

Section 1 reuses Paul's super-agent Rake/P&L already collected by the managers
report (managers_raw_<range>.csv), applying a per-SA rakeback (see
managers_config.PAUL_SA_RAKEBACK). CopilulNorocos is NOT shown as a super
agent; instead this script collects every member under it (from the roster)
individually:
  - a PLAYER  -> personal Game-Statistics Custom range (Rake & P&L)
  - an AGENT / SUPER AGENT -> its Agent-Statistics Custom range (Fee=Rake & P&L)
detecting the role from the member-detail 'Member Role' field. All sub-members
get a flat rakeback (managers_config.COPIL_SUBMEMBER_RAKEBACK).

Usage:
  python paul_report.py 2026-08-03 2026-08-09
  python paul_report.py 2026-08-03 2026-08-09 --build-only   # rebuild sheet

Prereqs (collection): ClubGG open + driver.py elevated. Per-member CSV
checkpoint (paul_submembers_<range>.csv) so a rerun resumes.
"""
import csv
import sys
from datetime import date
from pathlib import Path

import collect
from collect import (CaptureBlocked, block_recovery, click, enter_club,
                     goto_member_list, ocr_lines, ocr_text, screen_of,
                     search_open, send)
import managers_config as mc
import managers_report as mr

ROOT = Path(__file__).parent
FIELDS = ["role", "id", "name", "rake", "profit_loss"]


def sub_path(start, end):
    return ROOT / "output" / f"paul_submembers_{start}_{end}.csv"


def copil_submembers():
    """(id, name) of every roster member whose agent is CopilulNorocos."""
    files = sorted((ROOT / "output").glob("clubgg_roster_*.csv"))
    if not files:
        raise RuntimeError("no roster CSV found - run the roster loader first")
    exclude = getattr(mc, "COPIL_EXCLUDE", set())
    rows = [r for r in csv.DictReader(files[-1].open(encoding="utf-8"))
            if r["agent"] == mc.COPIL_OWNER_NAME and r["player_id"] not in exclude]
    members = [(r["player_id"], r["name"]) for r in rows]
    # include extras not (yet) in the roster under CopilulNorocos; collected
    # via the normal member flow (role auto-detected -> Agent Statistics etc.)
    have = {pid for pid, _ in members}
    for pid in getattr(mc, "COPIL_EXTRA_MEMBERS", {}):
        if pid not in have and pid not in exclude:
            members.append((pid, mr.roster_name(pid) or ""))
    return members


def read_role(p):
    """Detect a member's role from the 'Member Role' field on the detail page.
    Returns 'player', 'agent' or 'super'. Defaults to 'player' if unreadable
    (players have no management section, so the agent flow can't misfire)."""
    for y, x, t in ocr_lines(p):
        if x < 240 and "member role" in t.lower():
            v = ocr_text(p, (300, int(y) - 17, 505, int(y) + 17),
                         scale=3).strip().lower()
            if "super" in v:
                return "super"
            if "agent" in v:
                return "agent"
            if "player" in v:
                return "player"
    return "player"


def collect_submember(pid, name_hint, start, end, tag):
    """Open a member under CopilulNorocos and read its Rake & P&L for the
    range, using the player or agent flow according to its role."""
    goto_member_list("All")                 # clean starting screen
    p = search_open(pid, name_hint or mr.roster_name(pid), tag)
    if p is None:
        raise RuntimeError(f"{pid} not found via search")
    name = ocr_text(p, (125, 108, 360, 140), scale=3).strip() \
        or name_hint or mr.roster_name(pid)
    role = read_role(p)
    if role in ("agent", "super"):
        mr.open_super_agent_statistics(tag)          # matches 'Agent Statistics'
        rake, pnl = mr.read_agent_stats_custom(start, end, tag)
        click(25, 62, name=f"{tag}_b1", settle=1.0)  # stats -> detail
        click(25, 62, name=f"{tag}_b2", settle=1.0)  # detail -> list
    else:
        rake, pnl = mr.read_member_custom_stats(p, start, end, tag)
        click(25, 62, name=f"{tag}_back", settle=0.9)
    return role, name, rake, pnl


def run(start, end):
    out = sub_path(start, end)
    out.parent.mkdir(exist_ok=True)
    done = {}
    if out.exists():
        done = {r["id"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
        print(f"resuming: {len(done)} sub-members already collected", flush=True)

    members = copil_submembers()
    print(f"CopilulNorocos sub-members to collect: {len(members)}", flush=True)

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
    while i < len(members):
        pid, name_hint = members[i]
        if pid in done:
            i += 1
            continue
        tag = f"c{i:02d}"
        try:
            role, name, rake, pnl = collect_submember(pid, name_hint,
                                                       start, end, tag)
            rec = {"role": role, "id": pid, "name": name,
                   "rake": rake, "profit_loss": pnl}
            w.writerow(rec)
            f.flush()
            done[pid] = rec
            print(f"[{len(done)}/{len(members)}] {role} {name} ({pid}) "
                  f"rake={rake} pnl={pnl}", flush=True)
            i += 1
        except CaptureBlocked:
            if not recover():
                break
        except Exception as e:                        # skip, flag, continue
            print(f"  SKIPPED {pid}: {e}", flush=True)
            w.writerow({"role": "ERR", "id": pid,
                        "name": name_hint or mr.roster_name(pid),
                        "rake": "ERR", "profit_loss": "ERR"})
            f.flush()
            done[pid] = {"id": pid}
            i += 1
            try:
                goto_member_list("All")
            except Exception:
                if not recover():
                    break
    f.close()
    print("collection done", flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    if "--build-only" not in sys.argv:
        if not collect.driver_alive():
            print("ERROR: driver not running")
            sys.exit(2)
        run(start, end)
    import build_paul_sheet
    build_paul_sheet.build(start, end)
