"""Local web UI for ClubGG stats collection.

Serves a page where you pick an agent/SA, tick the players you want, choose a
date range + rakeback, and hit Collect. It runs collect_selected() for ONLY
the ticked players over that range, then builds the Excel sheet.

Run:  python server.py    then open http://127.0.0.1:8765
Prereqs for collecting: ClubGG open + driver.py running elevated.
"""
import csv
import json
import os
import subprocess
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import collect  # collect_selected, driver_alive, ROOT

ROOT = Path(__file__).parent
UI = ROOT / "ui" / "index.html"
PORT = 8765

JOB = {"running": False, "events": [], "done": 0, "total": 0,
       "finished": False, "error": None, "sheet": None, "csv": None}
ROSTER = {"running": False, "finished": False, "error": None, "log": []}
LOCK = threading.Lock()


def latest_roster():
    files = sorted((ROOT / "output").glob("clubgg_roster_*.csv"))
    return files[-1] if files else None


def load_roster():
    """agent -> [{id, name}], sorted; plus counts."""
    path = latest_roster()
    agents = {}
    if path:
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                agents.setdefault(r["agent"] or "UNKNOWN", []).append(
                    {"id": r["player_id"], "name": r["name"]})
    for lst in agents.values():
        lst.sort(key=lambda p: p["name"].lower())
    return {"roster": path.name if path else None,
            "agents": [{"agent": a, "players": p}
                       for a, p in sorted(agents.items(),
                                          key=lambda kv: kv[0].lower())]}


def run_job(start, end, targets, rakeback):
    def on_progress(e):
        with LOCK:
            JOB["events"].append(e)
            if e["kind"] == "player":
                JOB["done"] = e["done"]
                JOB["events"].append({"kind": "log",
                    "msg": f"[{e['done']}] {e['rec']['name']} "
                           f"({e['rec']['player_id']}) rake={e['rec']['rake']} "
                           f"pnl={e['rec']['profit_loss']}"})
            elif e["kind"] == "skip":
                JOB["events"].append({"kind": "log",
                    "msg": f"skipped {e.get('name') or e['id']}: {e['reason']}"})
            elif e["kind"] == "blocked":
                JOB["events"].append({"kind": "log", "msg":
                    "ClubGG re-armed capture protection - restart ClubGG and "
                    "press Collect again to resume the rest."})
            elif e["kind"] == "start":
                JOB["total"] = e["total"]
                JOB["events"].append({"kind": "log", "msg":
                    f"{e['total']} selected, {e['already']} already done, "
                    f"{e['remaining']} to collect"})

    csv_path = ROOT / "output" / f"clubgg_stats_{start}_{end}.csv"
    try:
        collect.collect_selected(date.fromisoformat(start),
                                 date.fromisoformat(end), targets,
                                 csv_path, on_progress)
        # build the sheet from whatever has been collected so far
        subprocess.run([sys.executable, str(ROOT / "build_sheet.py"),
                        str(csv_path), "--rakeback", str(rakeback)],
                       check=True, capture_output=True, text=True)
        sheet = csv_path.with_name(
            csv_path.stem.replace("clubgg_stats", "clubgg_report") + ".xlsx")
        with LOCK:
            JOB["csv"] = str(csv_path)
            JOB["sheet"] = str(sheet) if sheet.exists() else None
        if sheet.exists():                     # open the finished sheet
            try:
                os.startfile(str(sheet))       # noqa - Windows only
            except OSError:
                pass
    except Exception as e:  # noqa
        with LOCK:
            JOB["error"] = str(e)
    finally:
        with LOCK:
            JOB["running"] = False
            JOB["finished"] = True


def run_roster():
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "roster.py")],
                              capture_output=True, text=True, timeout=7200)
        with LOCK:
            ROSTER["log"] = (proc.stdout or "").splitlines()[-40:]
            if proc.returncode != 0:
                ROSTER["error"] = (proc.stderr or "roster scan failed")[-800:]
    except Exception as e:  # noqa
        with LOCK:
            ROSTER["error"] = str(e)
    finally:
        with LOCK:
            ROSTER["running"] = False
            ROSTER["finished"] = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/roster":
            self._send(200, json.dumps(load_roster()))
        elif self.path == "/api/driver":
            self._send(200, json.dumps({"alive": collect.driver_alive()}))
        elif self.path == "/api/progress":
            with LOCK:
                self._send(200, json.dumps(JOB))
        elif self.path == "/api/roster_status":
            with LOCK:
                self._send(200, json.dumps(ROSTER))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path == "/api/reload_roster":
            with LOCK:
                if ROSTER["running"]:
                    return self._send(409, json.dumps({"error": "already running"}))
                if not collect.driver_alive():
                    return self._send(400, json.dumps({"error":
                        "driver not running - start driver.py elevated"}))
                ROSTER.update(running=True, finished=False, error=None, log=[])
            threading.Thread(target=run_roster, daemon=True).start()
            return self._send(200, json.dumps({"started": True}))
        if self.path != "/api/collect":
            return self._send(404, json.dumps({"error": "not found"}))
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        with LOCK:
            if JOB["running"]:
                return self._send(409, json.dumps({"error": "already running"}))
            if not collect.driver_alive():
                return self._send(400, json.dumps({"error":
                    "driver not running - start driver.py elevated"}))
            if not req.get("targets"):
                return self._send(400, json.dumps({"error": "no players selected"}))
            JOB.update(running=True, events=[], done=0,
                       total=len(req["targets"]), finished=False,
                       error=None, sheet=None, csv=None)
        threading.Thread(target=run_job, args=(
            req["start"], req["end"], req["targets"],
            req.get("rakeback", 30)), daemon=True).start()
        self._send(200, json.dumps({"started": True}))


if __name__ == "__main__":
    print(f"ClubGG UI at http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
