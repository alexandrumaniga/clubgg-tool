r"""Editable per-entity rakeback config for Paul's report.

`config/paul_rakeback.csv` holds one hand-editable row per entity:

    group,id,name,rakeback_pct
      group = sa            a super agent of Paul (shown in section 1)
            = owner         CopilulNorocos (expanded into its members; pct unused)
            = copil_member  a member under CopilulNorocos (section 2)

Edit the `rakeback_pct` column by hand. Anything unknown defaults to 60%.
`roster.py` calls sync() after every roster scan, so newly-detected members
under Paul / CopilulNorocos are auto-added here at the 60% default (your edits
are preserved) - adjust them when you know the real rate. build_paul_sheet also
sync()s so the config always lists the current entities.
"""
import csv
from pathlib import Path

import managers_config as mc

ROOT = Path(__file__).parent
RAKEBACK_CSV = ROOT / "config" / "paul_rakeback.csv"
DEFAULT_PCT = mc.COPIL_SUBMEMBER_RAKEBACK          # 60
FIELDS = ["group", "id", "name", "rakeback_pct"]
_GRP_RANK = {"sa": 0, "owner": 1, "copil_member": 2}


def latest_roster():
    files = sorted((ROOT / "output").glob("clubgg_roster_*.csv"))
    return files[-1] if files else None


def _roster_rows(path=None):
    path = path or latest_roster()
    if not path or not Path(path).exists():
        return []
    return list(csv.DictReader(Path(path).open(encoding="utf-8")))


def load():
    """id -> {group, name, pct}. pct is a float, or None when left blank.
    Empty dict if the config file doesn't exist yet."""
    out = {}
    if RAKEBACK_CSV.exists():
        for r in csv.DictReader(RAKEBACK_CSV.open(encoding="utf-8")):
            try:
                pct = float(r["rakeback_pct"])
            except (TypeError, ValueError):
                pct = None
            out[r["id"]] = {"group": r.get("group", ""),
                            "name": r.get("name", ""), "pct": pct}
    return out


def desired_entities(roster_path=None):
    """(group, id, name) for every entity that belongs in the config now: all
    of Paul's super agents (CopilulNorocos flagged 'owner') plus every roster
    member whose upline is CopilulNorocos."""
    rows = _roster_rows(roster_path)
    rname = {r["player_id"]: r["name"] for r in rows}
    ent = []
    grouped = set(mc.paul_group_ids())
    for sid in mc.sas_of("Paul"):
        if sid in grouped:                    # shown only inside its group row
            continue
        grp = "owner" if sid == mc.COPIL_OWNER else "sa"
        ent.append((grp, sid, rname.get(sid, "")))
    for r in rows:
        if r["agent"] == mc.COPIL_OWNER_NAME:
            ent.append(("copil_member", r["player_id"], r["name"]))
    return ent


def _default_pct(group, pid):
    if group == "owner":
        return None                                # expanded; no direct pct
    if group == "sa":
        return mc.PAUL_SA_RAKEBACK.get(pid, DEFAULT_PCT)
    return DEFAULT_PCT                             # copil_member / anything else


def sync(roster_path=None, write=True):
    """Merge currently-detected entities into the config, preserving every
    existing row and its hand-edited rakeback. New entities are appended at
    their default %. Returns (added, stale): `added` is the new entities,
    `stale` is config ids no longer under Paul/CopilulNorocos (kept, not
    deleted). Writes only when something was added (or the file is new)."""
    existing, order = {}, []
    if RAKEBACK_CSV.exists():
        for r in csv.DictReader(RAKEBACK_CSV.open(encoding="utf-8")):
            existing[r["id"]] = r
            order.append(r["id"])

    desired = desired_entities(roster_path)
    desired_ids = {pid for _, pid, _ in desired}

    added = []
    for group, pid, name in desired:
        if pid not in existing:
            dp = _default_pct(group, pid)
            existing[pid] = {"group": group, "id": pid, "name": name,
                             "rakeback_pct": "" if dp is None else f"{dp:g}"}
            order.append(pid)
            added.append((group, pid, name))
        else:                                       # fill blanks, keep edits
            row = existing[pid]
            if not row.get("name") and name:
                row["name"] = name
            if not row.get("group"):
                row["group"] = group
    stale = [pid for pid in order if pid not in desired_ids]

    if write and (added or not RAKEBACK_CSV.exists()):
        RAKEBACK_CSV.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted((existing[pid] for pid in order),
                      key=lambda r: (_GRP_RANK.get(r.get("group"), 9),
                                     (r.get("name") or "").lower()))
        with RAKEBACK_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in FIELDS})
    return added, stale


if __name__ == "__main__":
    added, stale = sync()
    print(f"synced {RAKEBACK_CSV}")
    print(f"  added {len(added)}: " +
          ", ".join(f"{g}:{n or i}" for g, i, n in added))
    if stale:
        print(f"  stale (kept): {', '.join(stale)}")
