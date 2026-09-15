r"""Weekly ClubGG pipeline - the one command to run every Monday ~12:00.

By default it reports on the week that just ended (last Monday-Sunday relative
to today) and does, in order:

  1. ROSTER   - reload the member roster (roster.py). Skipped if a roster was
                already loaded this week, unless --roster forces it. Loading
                the roster also refreshes Paul's editable rakeback config.
  2. MANAGERS - the general managers sheet (managers_report.py): the 3 managers
                with their super agents at 100% rakeback, plus the Bad Beat
                Jackpot.
  3. PAUL     - Paul's sheet (paul_report.py): reuses Paul's SA data + collects
                the CopilulNorocos members; rakeback per config; Paul's Profit.
  4. ABRUDAN  - Abrudan's sheet (abrudan_report.py): reuses Abrudan's SA data +
                collects gerardsb.

The three finished sheets (xlsx + html) are copied into a fresh per-week
subfolder:  output/week_<start>_<end>/  as Managers/Paul/Abrudan.{xlsx,html}.

Usage:
  python weekly_run.py                        # auto: last Monday-Sunday
  python weekly_run.py 2026-08-10 2026-08-16  # explicit interval
  python weekly_run.py --roster               # force a fresh roster reload
  python weekly_run.py --no-roster            # never load the roster this run

Prereqs: it makes sure ClubGG is open and driver.py is running elevated,
launching the driver itself if needed (accept the one UAC prompt).
"""
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import collect

ROOT = Path(__file__).parent
PY = sys.executable
OUT = ROOT / "output"


def last_week(today):
    """(start, end) = the Monday-Sunday of the week before the one containing
    `today`. Run on Monday -> the week that just finished."""
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7), this_monday - timedelta(days=1)


def roster_loaded_this_week(today):
    """Path of a roster CSV already produced this week (Mon..now), or None."""
    this_monday = today - timedelta(days=today.weekday())
    for f in OUT.glob("clubgg_roster_*.csv"):
        try:
            d = date.fromisoformat(f.stem.replace("clubgg_roster_", ""))
        except ValueError:
            continue
        if d >= this_monday:
            return f
    return None


# ------------------------------------------------------------- environment ---

def ensure_driver():
    if collect.driver_alive():
        return True
    print(">> driver not running - launching it elevated; ACCEPT the UAC "
          "prompt...", flush=True)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Start-Process -FilePath '{PY}' -ArgumentList "
                    f"'\"{ROOT / 'driver.py'}\"' -Verb RunAs"], check=False)
    for _ in range(60):
        if collect.driver_alive():
            print(">> driver is up", flush=True)
            return True
        time.sleep(1)
    return False


def clubgg_running():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "if (Get-Process ClubGG -ErrorAction SilentlyContinue)"
                        "{'yes'}else{'no'}"], capture_output=True, text=True)
    return "yes" in r.stdout


def ensure_clubgg():
    if clubgg_running():
        return
    print(">> ClubGG not running - asking the driver to launch it...",
          flush=True)
    try:
        collect.send_once({"action": "restartgg"}, timeout=280)
    except Exception as e:
        print(f">> could not auto-launch ClubGG: {e}", flush=True)


# --------------------------------------------------------------------- run ---

def step(title, argv):
    print(f"\n{'=' * 70}\n>> {title}\n{'=' * 70}", flush=True)
    rc = subprocess.run([PY, *argv], cwd=str(ROOT)).returncode
    print(f">> {title}: exit {rc}", flush=True)
    return rc == 0


def collect_sheets(start, end, folder=None):
    week = OUT / (folder or f"week_{start}_{end}")
    week.mkdir(parents=True, exist_ok=True)
    mapping = [("managers_report", "Managers"), ("paul_report", "Paul"),
               ("abrudan_report", "Abrudan"),
               ("abrudan_group1", "Abrudan-Group1"),
               ("abrudan_group2", "Abrudan-Group2")]
    copied, missing = [], []
    for ext in ("xlsx", "html"):
        src = OUT / f"veres_report_{start}_{end}.{ext}"
        if src.exists():
            shutil.copy(src, week / f"Veres.{ext}"); copied.append(f"Veres.{ext}")
    for head, nice in (("CohibaLover", "Cohiba"), ("Cashvick", "Cashvick"), ("Premium89", "Premium89")):
        st = OUT / "statements" / f"{head}_{start}_{end}.pdf"       # Paul's group statements
        if st.exists():
            shutil.copy(st, week / f"{nice}-Statement.pdf"); copied.append(f"{nice}-Statement.pdf")
    for stem, nice in mapping:
        for ext in ("xlsx", "html"):
            src = OUT / f"{stem}_{start}_{end}.{ext}"
            if src.exists():
                shutil.copy(src, week / f"{nice}.{ext}")
                copied.append(f"{nice}.{ext}")
            else:
                missing.append(src.name)
    return week, copied, missing


def parse_args(argv, today):
    """-> (start, end, force_roster, skip_roster, folder). --folder takes the
    next arg (may contain spaces when quoted); positional args are the dates."""
    force_roster = "--roster" in argv
    skip_roster = "--no-roster" in argv
    folder = None
    dates = []
    take_folder = False
    for a in argv:
        if take_folder:
            folder = a
            take_folder = False
        elif a == "--folder":
            take_folder = True
        elif not a.startswith("--"):
            dates.append(a)
    if len(dates) >= 2:
        start, end = date.fromisoformat(dates[0]), date.fromisoformat(dates[1])
    else:
        start, end = last_week(today)
    return start, end, force_roster, skip_roster, folder


def main():
    today = date.today()
    start, end, force_roster, skip_roster, folder = parse_args(sys.argv[1:],
                                                               today)
    s, e = start.isoformat(), end.isoformat()
    print(f">> Weekly run | interval {s} .. {e}", flush=True)

    if not ensure_driver():
        print("ERROR: driver not running and could not be started. Start it "
              "with:\n  Start-Process -FilePath python -ArgumentList "
              f"'\"{ROOT / 'driver.py'}\"' -Verb RunAs", flush=True)
        sys.exit(2)
    ensure_clubgg()

    results = {}

    # 1. roster
    existing = roster_loaded_this_week(today)
    if skip_roster:
        print(">> roster: skipped (--no-roster)", flush=True)
    elif existing and not force_roster:
        print(f">> roster: already loaded this week ({existing.name}); skipping"
              " (use --roster to force)", flush=True)
    else:
        results["roster"] = step("ROSTER (roster.py)", ["roster.py"])

    # 2-4. the three reports (each collects + builds its own sheet)
    results["managers"] = step("MANAGERS report", ["managers_report.py", s, e])
    results["paul"] = step("PAUL report", ["paul_report.py", s, e])
    # Paul-relevant weekly figures -> Paul's Book INBOX as proposals (Alex approves in the app)
    results["inbox"] = step("PUSH INBOX (Paul's Book)", [str(ROOT / "paul_ledger" / "app" / "push_inbox.py"), s, e])
    results["abrudan"] = step("ABRUDAN report", ["abrudan_report.py", s, e])
    # Cristian Veres' downline sheet (members collected individually, default 50%)
    results["veres"] = step("VERES downline report", ["veres_report.py", s, e])
    # Paul's "Main Agent Weekly Statement" PDFs (Cohiba group, Cashvick group, Premium89) from the managers data
    results["cohiba"] = step("COHIBA statement", ["statement.py", s, e, "--group", "cohiba"])
    results["cashvick"] = step("CASHVICK statement", ["statement.py", s, e, "--group", "cashvick"])
    results["premium"] = step("PREMIUM89 statement", ["statement.py", s, e, "--group", "premium"])

    week, copied, missing = collect_sheets(s, e, folder)
    print(f"\n{'=' * 70}\n>> DONE  interval {s} .. {e}\n{'=' * 70}", flush=True)
    for k, ok in results.items():
        print(f"   {k:10} {'OK' if ok else 'FAILED - check its log'}",
              flush=True)
    print(f"   week folder: {week}", flush=True)
    print(f"   sheets: {', '.join(copied) if copied else '(none)'}", flush=True)
    if missing:
        print(f"   MISSING (a step failed?): {', '.join(missing)}", flush=True)


if __name__ == "__main__":
    main()
