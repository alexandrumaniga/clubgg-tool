r"""Pull / push the live Paul's Book ledger (Cloudflare Pages + D1).

  python sync.py pull   # fetch live state -> data/state.json (+ records base version)
  python sync.py push   # upload data/state.json to the live site (safe: checks base)
  python sync.py show   # quick summary of the local data/state.json

Workflow for an update: `pull` (always start from what's live), edit
data/state.json, then `push`. Uses the admin code in .admin_code.txt.
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://paul-ledger.pages.dev"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PaulBookSync/1.0"
APP = Path(__file__).parent
DATA = APP / "data" / "state.json"
BASEF = APP / "data" / ".base"


def admin_code():
    raw = (APP / ".admin_code.txt").read_text(encoding="utf-8").strip()
    return raw.split("=")[-1].strip()


def _post(path, body, token=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers={"content-type": "application/json", "user-agent": UA})
    if token:
        req.add_header("authorization", "Bearer " + token)
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read().decode())


def _get(path, token):
    req = urllib.request.Request(BASE + path,
                                 headers={"authorization": "Bearer " + token, "user-agent": UA})
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read().decode())


def _put(path, body, token):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="PUT",
                                 headers={"content-type": "application/json",
                                          "authorization": "Bearer " + token, "user-agent": UA})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def token():
    st, d = _post("/api/login", {"code": admin_code()})
    if "token" not in d:
        raise SystemExit(f"login failed: {d}")
    return d["token"]


def pull():
    tk = token()
    _, d = _get("/api/state", tk)
    DATA.parent.mkdir(exist_ok=True)
    state = d.get("state") or {"people": [], "staking": [], "loans": [], "inbox": []}
    DATA.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    BASEF.write_text(str(d.get("updated") or 0), encoding="utf-8")
    show()
    print(f"\npulled live -> {DATA} (base={d.get('updated')})")


def push():
    tk = token()
    state = json.loads(DATA.read_text(encoding="utf-8"))
    base = int(BASEF.read_text(encoding="utf-8")) if BASEF.exists() else None
    st, d = _put("/api/state", {"state": state, "base": base}, tk)
    if st == 409:
        print("CONFLICT: the live data changed since your last pull "
              "(someone edited in the app). Run `pull` again, re-apply, then push.")
        return
    if d.get("ok"):
        BASEF.write_text(str(d["updated"]), encoding="utf-8")
        print(f"pushed -> live (updated={d['updated']})")
    else:
        print(f"push failed: {d}")


def show():
    state = json.loads(DATA.read_text(encoding="utf-8"))
    def s(v):
        return sum((0 if t.get("paid") else (t.get("amount") or 0)) for t in v.get("tx", []))
    print(f"people: {len(state.get('people',[]))}  "
          f"staking: {len(state.get('staking',[]))}  "
          f"loans: {len(state.get('loans',[]))}  inbox: {len(state.get('inbox',[]))}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    {"pull": pull, "push": push, "show": show}.get(cmd, show)()
