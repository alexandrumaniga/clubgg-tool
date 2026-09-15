r"""Push Paul's weekly figures into Paul's Book INBOX as *proposed* entries.

THE ONE BRIDGE between the ClubGG collection tool and Paul's Book. Runs after the
Paul sheet has been built for a week; Alex approves each proposal in the app.

Source rows = exactly what Paul's sheet shows (build_paul_sheet.load_sa_data +
load_submembers): individual SAs, the SA groups (one line each), and every
CopilulNorocos member. Zero-activity rows are skipped.

Amount convention (app): + = they owe Paul, - = Paul owes them.
  member result after tipsback = P&L + tips x pct      (what the member netted)
  inbox amount               = -(result after tipsback)
  e.g. member lost 12,856 after tipsback -> +12,856 (owes Paul)
       member won 9,256 after tipsback   ->  -9,256 (Paul owes)

  python push_inbox.py 2026-08-31 2026-09-06            # push
  python push_inbox.py 2026-08-31 2026-09-06 --dry-run  # just print
Dedupes on (name, week label) so re-running a week does not double-post.
"""
import json
import re
import secrets
import sys
import urllib.request
from datetime import date
from pathlib import Path

APP = Path(__file__).parent
TOOL = APP.parent.parent            # clubgg-tool/
sys.path.insert(0, str(TOOL))
import build_paul_sheet as bps      # noqa: E402  (the ClubGG tool's Paul loaders)

BASE = "https://paul-ledger.pages.dev"
UA = "Mozilla/5.0 PaulBookSync/1.0"


def admin_code():
    return (APP / ".admin_code.txt").read_text(encoding="utf-8").strip().split("=")[-1].strip()


def req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"content-type": "application/json", "user-agent": UA})
    if token:
        r.add_header("authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def week_label(start, end):
    if start.month == end.month:
        return f"{start.day}–{end.day} {end.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')} – {end.day} {end.strftime('%b')}"


def proposals(start, end):
    rows = bps.load_sa_data(start, end) + bps.load_submembers(start, end)
    wk = week_label(start, end)
    out = []
    for r in rows:
        rake, pnl, pct = r.get("rake") or 0, r.get("pnl") or 0, r.get("pct") or 0
        if not rake and not pnl:
            continue
        after_tb = pnl + rake * pct / 100
        out.append({"n": r["name"], "wk": wk, "a": round(-after_tb, 2), "c": "RON",
                    "pl": "RomanianClub", "rb": f"{pct:g}%",
                    "pnl": round(pnl, 2), "rake": round(rake, 2), "pct": pct,
                    "src": "weekly", "role": r.get("role", ""),
                    "detail": f"tips {rake:,.2f} · P&L {pnl:+,.2f} · after tipsback {after_tb:+,.2f}"})
    return out


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def aliases():
    """ClubGG name -> target (inbox_aliases.json). Target is a person name, or
    "staking:<horse>" when the member is a horse Paul stakes (his RomanianClub
    result then becomes a week line on that horse instead of an inbox debt)."""
    f = APP / "inbox_aliases.json"
    if not f.exists():
        return {}
    return {norm(k): v for k, v in json.loads(f.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


def person_for(name, by_name, al):
    tgt = al.get(norm(name), "")
    if tgt.startswith("staking:"):
        return None
    return by_name.get(norm(name)) or by_name.get(norm(tgt))


def add_horse_line(state, horse, p):
    """Append this week's RomanianClub line to the staking horse (dedupe on week+club+account)."""
    h = next((x for x in state.get("staking", []) if norm(x["n"]) == norm(horse)), None)
    if h is None:
        return "no horse named " + horse
    h.setdefault("log", [])
    if any(l.get("wk") == p["wk"] and l.get("club") == "RomanianClub" and norm(l.get("acct")) == norm(p["n"])
           for l in h["log"]):
        return "already there"
    h["log"].append({"id": secrets.token_hex(4), "wk": p["wk"], "acct": p["n"], "club": "RomanianClub",
                     "pnl": p["pnl"], "rake": p["rake"], "pct": p["pct"], "cur": "RON", "rate": None,
                     "note": "from the weekly run"})
    return "added"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    start, end = date.fromisoformat(args[0]), date.fromisoformat(args[1])
    props = proposals(start, end)
    print(f"{len(props)} proposals for {week_label(start, end)}:")
    for p in props:
        print(f"  {p['a']:>12,.2f} RON  {p['n']:<28} {p['rb']:>4}  {p['detail']}")
    if dry:
        print("(dry run — nothing pushed)"); return
    st, d = req("POST", "/api/login", {"code": admin_code()})
    tok = d.get("token") or sys.exit(f"login failed: {d}")
    st, d = req("GET", "/api/state", token=tok)
    state, base = d.get("state") or {}, d.get("updated")
    state.setdefault("inbox", []); state.setdefault("people", [])
    have = {(norm(x.get("n")), x.get("wk")) for x in state["inbox"]}
    by_name = {norm(p["n"]): p["id"] for p in state["people"]}
    al = aliases()
    added, horses = 0, []
    for p in props:
        tgt = al.get(norm(p["n"]), "")
        if tgt == "skip":                                    # Paul's own account (e.g. Hayanski@)
            continue
        if tgt.startswith("staking:"):                       # a horse: week line, not a debt
            horses.append((p["n"], tgt[8:], add_horse_line(state, tgt[8:], p)))
            continue
        if (norm(p["n"]), p["wk"]) in have:
            continue
        pid = person_for(p["n"], by_name, al)
        state["inbox"].append({"id": secrets.token_hex(4), **p, **({"pid": pid} if pid else {})})
        added += 1
    st, d = req("PUT", "/api/state", {"state": state, "base": base}, token=tok)
    if st == 409:
        sys.exit("CONFLICT: someone edited the app during the push — re-run.")
    unmatched = [p["n"] for p in props
                 if al.get(norm(p["n"]), "") not in ("skip",) and not al.get(norm(p["n"]), "").startswith("staking:")
                 and not person_for(p["n"], by_name, al)]
    print(f"pushed {added} new proposal(s) (skipped {len(props)-added-len(horses)} already in inbox) -> live")
    for member, horse, what in horses:
        print(f"staking: {member} -> week line on horse {horse}: {what}")
    if unmatched:
        print("not yet a person in the app (Approve will create them):", ", ".join(unmatched))


if __name__ == "__main__":
    main()
