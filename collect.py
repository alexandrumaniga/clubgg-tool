"""ClubGG batch stats collector.

Collects per-player Rake and Profit/Loss for a date interval from the ClubGG
app, top-down from the Player-filtered member list, and writes a CSV.

Usage:
  python collect.py 2026-08-05 2026-08-11 20

Prerequisites:
  - ClubGG open and logged into the club
  - driver.py running elevated (see driver.py docstring)

Design: driver.py executes the clicks (ClubGG runs elevated); this script
decides WHAT to click by OCR-ing screenshots (Windows OCR via winocr).
Every step is verified before the next click - on any mismatch the script
retries once, then aborts, keeping rows collected so far. It only ever
clicks whitelisted coordinates: member rows, Custom tab, calendar cells,
calendar arrows, Confirm, back arrow, red menu open/Members, Player tab,
and mouse-wheel scrolling over the list.
"""
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops, ImageOps
import winocr

ROOT = Path(__file__).parent
BRIDGE = ROOT / "bridge"
SHOTS = ROOT / "shots" / "collect"
SHOTS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- bridge ----

def driver_alive():
    try:
        return time.time() - (BRIDGE / "driver_alive.txt").stat().st_mtime < 10
    except OSError:
        return False


class CaptureBlocked(RuntimeError):
    """Raised when ClubGG has re-armed its anti-capture flag - further
    screenshots would be blank/wrong, so we must stop (and resume after a
    fresh ClubGG launch)."""


def send_once(cmd, timeout=45):
    cmd["id"] = str(time.time_ns())
    tmp = BRIDGE / "cmd.tmp"
    tmp.write_text(json.dumps(cmd), encoding="utf-8")
    os.replace(tmp, BRIDGE / "cmd.json")
    res_path = BRIDGE / f"res_{cmd['id']}.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if res_path.exists():
            # The res file may be momentarily locked (AV scanning the bridge
            # folder) or half-written by the driver. Treat a lock / partial
            # read as "not ready yet" and retry within the timeout instead of
            # crashing with PermissionError (Errno 13) or a JSON error.
            try:
                out = json.loads(res_path.read_text(encoding="utf-8"))
            except (PermissionError, OSError, ValueError):
                time.sleep(0.05)
                continue
            try:
                res_path.unlink()
            except OSError:
                pass                       # best-effort; unique id, harmless
            if not out.get("ok"):
                raise RuntimeError(f"driver error: {out.get('error')}")
            return out
        time.sleep(0.05)
    raise RuntimeError("timeout waiting for driver")


def send(cmd, timeout=45):
    """Send a command; if the user is actively using the PC (ClubGG can't
    hold the foreground), wait and keep retrying instead of failing.
    The driver aborts BEFORE any input in that case, so retrying is safe."""
    for _ in range(60):  # up to ~5 minutes of user activity
        try:
            out = send_once(dict(cmd), timeout)
            # any captured frame that comes back capture-protected means the
            # anti-capture flag re-armed - stop before collecting garbage
            if out.get("affinity", 0) != 0:
                raise CaptureBlocked(
                    "ClubGG re-enabled capture protection (affinity="
                    f"{out['affinity']:#x})")
            return out
        except CaptureBlocked:
            raise
        except RuntimeError as e:
            if "foreground" not in str(e) and "covering" not in str(e):
                raise
            print("  ...waiting for ClubGG to be available (user active?)")
            time.sleep(5)
    raise RuntimeError("ClubGG never became available")


def shot(name, settle=None):
    path = SHOTS / f"{name}.png"
    cmd = {"action": "shot", "shot": str(path)}
    send(cmd)
    return path


def click(x, y, settle=0.8, name=None):
    cmd = {"action": "click", "x": x, "y": y}
    if name:
        cmd["shot"] = str(SHOTS / f"{name}.png")
        cmd["settle"] = settle
    send(cmd)
    return (SHOTS / f"{name}.png") if name else None


def scroll_list(px=200, name=None):
    """Scroll the member list down by ~px pixels (~1.5 rows by default).
    Unity ignores injected wheel events, so drag-swipe (with a hold before
    release, so there is no fling momentum) is used. Small steps ensure no
    row can pass through the viewport unseen."""
    cmd = {"action": "swipe", "x1": 270, "y1": 720, "x2": 270, "y2": 720 - px}
    if name:
        cmd["shot"] = str(SHOTS / f"{name}.png")
        cmd["settle"] = 0.6
    send(cmd)
    return (SHOTS / f"{name}.png") if name else None


# ------------------------------------------------------------------- ocr ----

def ocr_lines(img_path, crop=None, scale=1):
    img = Image.open(img_path)
    if crop:
        img = img.crop(crop)
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale),
                         Image.LANCZOS)
    res = winocr.recognize_pil_sync(img, "en")
    lines = []
    for line in res["lines"]:
        words = line["words"]
        x = min(w["bounding_rect"]["x"] for w in words) / scale
        y = min(w["bounding_rect"]["y"] for w in words) / scale
        if crop:
            x, y = x + crop[0], y + crop[1]
        lines.append((y, x, line["text"]))
    return lines


def ocr_text(img_path, crop, scale=3):
    return " ".join(t for _, _, t in ocr_lines(img_path, crop, scale))


# ClubGG's exact money format: comma-grouped thousands, optional 2 decimals.
# Examples that MUST validate: 0  708.89  50,000  41,858.64  999,783.17
# Examples that MUST be rejected (OCR damage): 70889 (dropped dot; ClubGG
# would show 70,889), 708.8 (dropped a decimal), 708,89 (dot->comma),
# 41858.64 (dropped comma). Rejecting instead of guessing means a misread
# fails loudly and the player is flagged - never silently wrong.
MONEY_RE = re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d{1,3})(?:\.\d{2})?$")


def parse_money_strict(raw):
    """Parse a ClubGG money string, rejecting anything not in ClubGG's exact
    display format. Raises ValueError on malformed input (so callers retry or
    flag rather than record a corrupted number)."""
    s = re.sub(r"[^\d.,\-]", "", raw.strip())
    neg = s.startswith("-")
    core = s.lstrip("-")
    if not MONEY_RE.match(core):
        raise ValueError(f"malformed money {raw!r}")
    val = float(core.replace(",", ""))
    return -val if neg else val


def ocr_money_text(img_path, box, scale=6, thresh=None):
    """OCR a money crop with preprocessing tuned for ClubGG's colored values:
    take the per-pixel max channel (so white rake, red losses and green
    profits all become bright against the dark panel), then autocontrast and
    upscale. `thresh` optionally binarizes; None (the default) keeps the
    autocontrast grayscale, which reads both bright and DIM colored text
    (a fixed threshold wipes out dim red/green values)."""
    im = Image.open(img_path).crop(box).convert("RGB")
    r, g, b = im.split()
    v = ImageChops.lighter(ImageChops.lighter(r, g), b)   # max(R,G,B)
    v = ImageOps.autocontrast(v)
    v = v.resize((v.width * scale, v.height * scale), Image.LANCZOS)
    if thresh is not None:
        v = v.point(lambda px: 255 if px > thresh else 0)
    res = winocr.recognize_pil_sync(v, "en")
    return " ".join(line["text"] for line in res["lines"])


def read_money(p, box, tag):
    """OCR a monetary value from screenshot p at box, using colour-aware
    preprocessing across several zoom/crop/threshold variants, and return the
    CONSENSUS value. Consensus (not first-valid) is essential: one variant can
    misread e.g. '11,393.46' as a well-formed but truncated '393.46' - taking
    the most frequent read (tie-broken toward the longer/full value, since
    truncation drops a leading group) rejects such outliers. Raises if nothing
    parses (a misread must never be recorded)."""
    l, t, r, b = box
    wide = (l - 8, t - 3, r + 12, b + 3)
    attempts = [(box, 4, None), (box, 5, None), (box, 6, None), (box, 8, None),
                (wide, 4, None), (wide, 6, None), (wide, 8, None),
                (box, 6, 110), (wide, 6, 110), (box, 6, 60)]
    seen, vals = [], []
    for bx, scale, th in attempts:
        txt = ocr_money_text(p, bx, scale=scale, thresh=th)
        seen.append(f"s{scale}t{th}:{txt!r}")
        try:
            vals.append(parse_money_strict(txt))
        except ValueError:
            continue
    if not vals:
        raise RuntimeError(f"unreadable money [{tag}]; OCR gave {seen}")
    counts = Counter(vals)
    # most frequent read; ties -> the value with the most digits (full read)
    return max(counts, key=lambda v: (counts[v],
                                      len(re.sub(r"\D", "", f"{abs(v)}"))))


ID_RE = re.compile(r"ID\s*:?\s*([0-9\- ]{6,})")


def norm_id(raw):
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 8:
        return None
    return f"{digits[:4]}-{digits[4:]}"


# ------------------------------------------------------------ navigation ----

def screen_of(lines):
    txt = " | ".join(t for _, _, t in lines)
    if "Select Date" in txt:
        return "calendar"
    if "Member Detail" in txt:
        return "detail"
    if "Club Members" in txt:
        return "members"
    if "Create New Table" in txt or "Tables" in txt:
        return "lobby"
    return "unknown"


def swipe_carousel(name):
    """Advance the club carousel one card (right-to-left). Returns screenshot."""
    send({"action": "swipe", "x1": 450, "y1": 400, "x2": 90, "y2": 400,
          "shot": str(SHOTS / f"{name}.png"), "settle": 0.8})
    return SHOTS / f"{name}.png"


def dismiss_promo(p=None, tag="promo"):
    """ClubGG sometimes shows a full-screen promo/ad overlay (e.g. the WSOP
    Circuit banner) - especially right after a launch/restart - which no screen
    classifier recognizes and which blocks all navigation. If one is up, click
    its 'Don't show this again for 7 days.' line to dismiss it (that also
    suppresses it for a week). Returns True if a promo was dismissed."""
    if p is None:
        p = shot(f"{tag}_chk")
    for y, x, t in ocr_lines(p):
        if "show this again" in t.lower():
            click(270, int(y), name=f"{tag}_x", settle=1.2)
            return True
    return False


def enter_club(club="RomanianClub", tag="club"):
    """From anywhere after a restart, go to the Club tab, scroll the club
    carousel to `club`, and enter it. Returns the club lobby screenshot.
    The launcher auto-logs in, so no credentials are needed."""
    dismiss_promo(tag=f"{tag}_promo0")                   # clear any launch promo
    p = click(40, 950, name=f"{tag}_tab", settle=1.2)   # bottom-left Club tab
    for _ in range(90):                                  # wait for home to load
        lines = ocr_lines(p)                             # (launcher may UPDATE,
        if any("Search Club" in t for _, _, t in lines):  # which is slow - be
            break                                         # patient, up to ~90s)
        if dismiss_promo(p, tag=f"{tag}_promo"):         # promo covering home
            p = click(40, 950, name=f"{tag}_tab", settle=1.2)
            continue
        time.sleep(1)
        p = shot(f"{tag}_tab")
    else:
        raise RuntimeError("club home (Search Club) not shown after restart")
    target = club.lower().replace(" ", "")
    last_name = None
    for i in range(12):
        name = ocr_text(p, (128, 545, 412, 588), scale=3).strip()
        if "romanian" in name.lower() or target[:8] in name.lower().replace(" ", ""):
            pe = click(270, 400, name=f"{tag}_enter", settle=1.5)
            txt = " ".join(t for _, _, t in ocr_lines(pe)).lower()
            if screen_of(ocr_lines(pe)) == "lobby" or "romanian" in txt:
                return pe
            raise RuntimeError(f"clicked {name!r} but did not enter the club")
        if name and name == last_name:               # carousel reached the end
            break
        last_name = name
        p = swipe_carousel(f"{tag}_c{i}")
    raise RuntimeError(f"{club!r} not found in the club carousel")


def block_recovery(club="RomanianClub", tab="Player", max_restarts=40,
                   emit=None):
    """Return a recover() callable shared by every collection loop: on a
    capture block it restarts ClubGG, re-enters `club`, and returns to the
    member list on the given filter `tab`. recover() returns True to continue
    or False when restarts are exhausted / a restart failed. `emit` (optional)
    takes an event dict."""
    state = {"n": 0}

    def note(**e):
        if emit:
            emit(e)

    def recover():
        state["n"] += 1
        if state["n"] > max_restarts:
            note(kind="blocked", error=f"reached max auto-restarts "
                 f"({max_restarts})")
            return False
        note(kind="restart", n=state["n"])
        note(kind="log", msg=f"capture blocked - auto-restarting ClubGG "
             f"(#{state['n']}), then resuming...")
        try:
            send_once({"action": "restartgg"}, timeout=280)
        except Exception as e:  # noqa
            note(kind="blocked", error=f"ClubGG restart failed: {e}")
            return False
        # Re-enter the club + member list. The carousel nav is intermittently
        # flaky ("RomanianClub not found in the club carousel"), so retry the
        # navigation a few times (without repeating the slow restart) before
        # giving up - it usually succeeds on a later attempt.
        for attempt in range(4):
            try:
                dismiss_promo()
                enter_club(club)
                goto_member_list(tab)
                note(kind="log", msg=f"back in {club} - resuming")
                return True
            except Exception as e:  # noqa
                note(kind="log", msg=f"re-entry attempt {attempt + 1} failed "
                     f"({e}); retrying")
                time.sleep(2)
        note(kind="blocked",
             error=f"auto-restart failed: could not re-enter {club}")
        return False

    return recover


# Filter tabs on the Club Members screen (y=273). "All" is the default.
TAB_X = {"All": 79, "Manager": 174, "SA": 269, "Agent": 364, "Player": 460}


def tab_active(img_path, x):
    """A selected filter tab has a green pill background at (x, 273)."""
    r, g, b = Image.open(img_path).convert("RGB").getpixel((x, 273))[:3]
    return g > 120 and g > r + 40 and g > b + 40


def goto_member_list(tab="Player"):
    """Navigate to the Club Members screen and ensure `tab` is the active
    filter ('All', 'Manager', 'SA', 'Agent', or 'Player'). Returns the
    members screenshot."""
    p = shot("nav")
    lines = ocr_lines(p)
    scr = screen_of(lines)
    unknown_streak = 0
    for _ in range(12):
        if scr == "members":
            break
        if scr == "unknown":
            # A capture-blocked frame raises CaptureBlocked before we get here,
            # so "unknown" means a real but unclassified screen (e.g. Super
            # Agent Statistics / Club Data, or a full-screen promo overlay).
            # Dismiss a promo first; otherwise the top-left back arrow (25,62)
            # is universal in ClubGG, so backing out is safe.
            if dismiss_promo(p, tag="nav_promo"):
                p = shot("nav")
            else:
                unknown_streak += 1
                if unknown_streak >= 6:
                    raise RuntimeError(
                        "screen unrecognized repeatedly - cannot reach member list")
                p = click(25, 62, name="nav", settle=1.0)
        else:
            unknown_streak = 0
            if scr == "lobby":
                # menu already open? "Inbox" label visible at the bottom bar
                if any("Inbox" in t for _, _, t in lines):
                    p = click(174, 937, name="nav")   # Members
                else:
                    p = click(485, 931, settle=0.6, name="nav")  # 4-dot menu
            elif scr == "calendar":
                p = click(270, 120, name="nav")       # tap above sheet closes it
            elif scr == "detail":
                p = click(25, 62, name="nav")         # back
        lines = ocr_lines(p)
        scr = screen_of(lines)
    else:
        raise RuntimeError(f"could not reach member list (stuck on {scr})")
    x = TAB_X[tab]
    if not tab_active(p, x):
        p = click(x, 273, name="nav")
        if not tab_active(p, x):
            raise RuntimeError(f"could not activate the {tab} filter tab")
    return p


def goto_player_list():
    """Members screen on the Player filter (stats collection needs Players)."""
    return goto_member_list("Player")


# --------------------------------------------------------------- list ops ---

def read_id_zoom(img_path, y):
    """Re-read the '(ID : xxxx-xxxx)' line zoomed - the full-frame OCR often
    confuses ID digits (0<->7, 0<->9), creating phantom duplicate members."""
    for scale in (4, 5):
        txt = ocr_text(img_path, (118, int(y) - 6, 278, int(y) + 24),
                       scale=scale)
        m = ID_RE.search(txt)
        pid = norm_id(m.group(1)) if m else None
        if pid:
            return pid
    return None


ID_MARKER = re.compile(r"\(?\s*ID\b", re.I)


def parse_rows(img_path):
    """Return visible complete rows: [{id, name, role, upline, y}]."""
    lines = ocr_lines(img_path)
    rows = []
    for y, x, text in lines:
        if not (100 < x < 260 and 360 < y < 910):
            continue
        m = ID_RE.search(text)
        # detect an ID row from a clean match OR an "ID" marker (the latter
        # catches rows whose id OCR'd with letters); zoom decides the value
        if not (m or ID_MARKER.search(text)):
            continue
        pid = read_id_zoom(img_path, y) or (norm_id(m.group(1)) if m else None)
        if pid is None:
            continue
        # name: nearest line above the ID within ~30px at same x band
        names = [t for (yy, xx, t) in lines
                 if 0 < y - yy < 32 and 100 < xx < 300]
        # badge: role at x~55-90, upline at x~95-260, ~53px below the ID
        roles = [t for (yy, xx, t) in lines if 40 < yy - y < 66 and xx < 95]
        ups = [t for (yy, xx, t) in lines
               if 40 < yy - y < 66 and 95 <= xx < 270 and "Alias" not in t]
        role = (roles[0] if roles else "")
        role = "SA" if "SA" in role.upper() else \
               ("Agent" if role.upper().startswith("AG") else role)
        upline = ups[0].replace(" ", "") if ups else ""
        if upline:
            # re-OCR the badge upline zoomed 3x - full-frame OCR mangles it
            fine = ocr_text(img_path, (95, int(y) + 38, 275, int(y) + 68),
                            scale=3).replace(" ", "")
            if fine:
                upline = fine
        # names OCR far better zoomed 3x from a tight crop than off the
        # full frame (the low-res full-frame read produces most name errors)
        name = ocr_text(img_path, (118, int(y) - 36, 348, int(y) - 2),
                        scale=3).strip()
        if not name:
            name = names[0] if names else ""
        rows.append({"id": pid, "y": y, "name": name,
                     "role": role, "upline": upline})
    rows.sort(key=lambda r: r["y"])
    return rows


# ------------------------------------------------------------- calendar -----

CAL_X = [62, 131, 200, 269, 338, 407, 476]           # Sun..Sat
CAL_Y = [513, 581, 650, 719, 788, 857]               # week rows
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def day_cell(d):
    first_col = (date(d.year, d.month, 1).weekday() + 1) % 7   # Sun=0
    cell = first_col + d.day - 1
    return CAL_X[cell % 7], CAL_Y[cell // 7]


def read_month(img_path):
    txt = ocr_text(img_path, (150, 305, 390, 350), scale=3)
    for i, mn in enumerate(MONTHS):
        if mn.lower() in txt.lower():
            m = re.search(r"(20\d\d)", txt)
            if m:
                return date(int(m.group(1)), i + 1, 1)
    raise RuntimeError(f"cannot read calendar month from {txt!r}")


def goto_month(img_path, target):
    cur = read_month(img_path)
    for _ in range(24):
        if (cur.year, cur.month) == (target.year, target.month):
            return img_path
        arrow = (53, 327) if (target < cur) else (486, 327)
        img_path = click(*arrow, settle=0.5, name="cal_nav")
        cur = read_month(img_path)
    raise RuntimeError("calendar month navigation did not converge")


def select_calendar_range(p, start, end, tag="cal"):
    """Given screenshot `p` with the 'Select Date' calendar already OPEN,
    pick start..end and press Confirm. Returns the post-confirm screenshot.
    The same calendar is used for member Custom, Super Agent Statistics
    Custom, and Club Data - so all three share this."""
    if screen_of(ocr_lines(p)) != "calendar":
        raise RuntimeError("date picker is not open")
    p = goto_month(p, start)
    click(*day_cell(start), settle=0.4)
    if (end.year, end.month) != (start.year, start.month):
        p = goto_month(shot(f"{tag}_mid"), end)
    p = click(*day_cell(end), settle=0.4, name=f"{tag}_range")
    label = ocr_text(p, (100, 362, 440, 402), scale=3)
    if re.findall(r"20\d\d-\d\d-\d\d", label) != [start.isoformat(),
                                                  end.isoformat()]:
        raise RuntimeError(f"range label {label!r} != expected {start} ~ {end}")
    return click(269, 941, name=f"{tag}_confirm", settle=1.2)   # Confirm


def set_range(start, end):
    """From a member detail page: open the Custom picker, select range, confirm."""
    p = click(428, 636, name="cal_open")
    if screen_of(ocr_lines(p)) != "calendar":
        raise RuntimeError("Custom tab did not open the date picker")
    return select_calendar_range(p, start, end, tag="stats")


# ------------------------------------------------------------ per player ----

def read_stats_on_detail(p, start, end, tag):
    """Given a Member Detail screenshot `p`, set the custom date range and
    read (name, rake, profit_loss). Returns after Confirm; caller navigates
    away. Retries the stats read since numbers can render/OCR late."""
    name = ocr_text(p, (125, 108, 360, 140), scale=3).strip()
    p = set_range(start, end)
    last_err = None
    for attempt in range(4):
        if attempt:
            time.sleep(0.8)
            p = shot(f"{tag}_stats")
        try:
            tab = ocr_text(p, (350, 618, 512, 656), scale=3)
            got = re.findall(r"(\d{1,2})\s*/\s*(\d{1,2})", tab)
            want = [(str(start.month), str(start.day)),
                    (str(end.month), str(end.day))]
            if got != want:
                raise RuntimeError(f"stats tab {tab!r} != expected {want}")
            # Gate on the Hands count: a zero-activity player shows lone "0"
            # cells that OCR to empty - that's legitimately 0, not a failure.
            hand_txt = ocr_text(p, (300, 690, 512, 720), scale=3)
            m = re.search(r"([\d,]+)\s*Hand", hand_txt)
            if m and int(m.group(1).replace(",", "")) == 0:
                return name, 0.0, 0.0
            rake = read_money(p, (280, 722, 512, 750), f"{tag}-rake")
            pnl = read_money(p, (280, 753, 512, 782), f"{tag}-pnl")
            return name, rake, pnl
        except CaptureBlocked:
            raise
        except (ValueError, RuntimeError) as e:
            last_err = e
    raise RuntimeError(f"stats unreadable after retries: {last_err}")


def collect_player(row, start, end, idx):
    p = click(216, int(row["y"]) - 8, name=f"p{idx:02d}_detail", settle=1.0)
    if screen_of(ocr_lines(p)) != "detail":
        raise RuntimeError("row click did not open Member Detail")
    head_id = norm_id(ocr_text(p, (125, 135, 350, 168), scale=3))
    if head_id != row["id"]:
        raise RuntimeError(f"opened {head_id}, expected {row['id']}")
    name, rake, pnl = read_stats_on_detail(p, start, end, f"p{idx:02d}")
    name = name or row["name"]
    p = click(25, 62, name=f"p{idx:02d}_back", settle=1.0)
    if screen_of(ocr_lines(p)) != "members":
        raise RuntimeError("back did not return to member list")
    return {"name": name, "player_id": row["id"], "role": row["role"],
            "upline": row["upline"], "rake": rake, "profit_loss": pnl}, p


# --------------------------------------------------- selected players (UI) ---

def search_open(pid, name, tag):
    """From the member list, search for a player by ID (then name) and open
    the matching detail page. Returns the detail screenshot, or None.
    Each query re-focuses the box and clears it first, so queries can never
    concatenate."""
    shot_path = SHOTS / f"{tag}_search.png"
    # IDs display as xxxx-xxxx; search with the dash form first, then name.
    for query in (pid, name, pid.replace("-", "")):
        if not query:
            continue
        click(270, 196, settle=0.3)                 # (re)focus the search box
        send({"action": "type", "text": query, "clear": True,
              "shot": str(shot_path), "settle": 1.0})
        hit = [r for r in parse_rows(shot_path) if r["id"] == pid]
        if not hit:
            continue
        # the row's ID already matched pid, so trust it and just confirm we
        # landed on a detail page (header re-OCR was falsely rejecting).
        p = click(216, int(hit[0]["y"]) - 8, name=f"{tag}_detail", settle=1.0)
        if screen_of(ocr_lines(p)) == "detail":
            return p
        click(25, 62, settle=0.6)                   # didn't open, back out
    return None


def collect_selected(start, end, targets, out_path, on_progress=None,
                     club="RomanianClub"):
    """Collect rake/P&L for a specific set of players (list of dicts with
    id/name/agent), finding each via search. Resumes from out_path. Calls
    on_progress(event_dict) as it goes. When ClubGG re-arms its anti-capture
    flag, automatically restarts ClubGG, re-enters `club`, and resumes.
    Returns the list of collected rows."""
    def emit(**e):
        if on_progress:
            on_progress(e)

    auto_restart = block_recovery(club, emit=on_progress)

    fields = ["name", "player_id", "role", "upline", "rake", "profit_loss"]
    done, seen = [], set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as f:
            done = list(csv.DictReader(f))
        seen = {r["player_id"] for r in done}

    remaining = [t for t in targets if t["id"] not in seen]
    emit(kind="start", total=len(targets), remaining=len(remaining),
         already=len(done))
    mode = "a" if done else "w"
    with out_path.open(mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if mode == "w":
            w.writeheader()
        try:
            send({"action": "setwin"})
            goto_player_list()
        except CaptureBlocked:
            if not auto_restart():
                emit(kind="done", done=len(done), total=len(targets))
                return done

        i = 0
        while i < len(remaining):
            t = remaining[i]
            tag = f"sel{i:03d}"
            try:
                p = search_open(t["id"], t.get("name", ""), tag)
                if p is None:
                    emit(kind="skip", id=t["id"], name=t.get("name"),
                         reason="not found via search")
                    goto_player_list()
                    i += 1
                    continue
                name, rake, pnl = read_stats_on_detail(p, start, end, tag)
                rec = {"name": name or t.get("name", ""),
                       "player_id": t["id"], "role": "",
                       "upline": t.get("agent", ""),
                       "rake": rake, "profit_loss": pnl}
                w.writerow(rec)
                f.flush()
                done.append(rec)
                click(25, 62, settle=0.8)           # back to search list
                goto_player_list()                  # clean base for next search
                emit(kind="player", done=len(done), rec=rec)
                i += 1
            except CaptureBlocked:
                # ClubGG blocked capture mid-player: restart, re-enter, and
                # RETRY the same player (do not advance i).
                if not auto_restart():
                    break
            except Exception as e:                  # unreadable/other: skip it
                emit(kind="skip", id=t["id"], name=t.get("name"),
                     reason=str(e))
                i += 1
                try:
                    goto_player_list()
                except CaptureBlocked:
                    if not auto_restart():
                        break
    emit(kind="done", done=len(done), total=len(targets))
    return done


# ----------------------------------------------------------------- main -----

def main():
    args = [a for a in sys.argv[1:] if a != "--fresh"]
    fresh = "--fresh" in sys.argv
    start = date.fromisoformat(args[0])
    end = date.fromisoformat(args[1])
    count = None if len(args) < 3 or args[2] == "all" else int(args[2])
    if not driver_alive():
        print("ERROR: driver not running (see driver.py docstring)")
        sys.exit(2)

    out_path = ROOT / "output" / \
        f"clubgg_stats_{start.isoformat()}_{end.isoformat()}.csv"
    out_path.parent.mkdir(exist_ok=True)

    # resume by default: already-collected players are not re-visited
    fields = ["name", "player_id", "role", "upline", "rake", "profit_loss"]
    done, seen = [], set()
    if out_path.exists() and not fresh:
        with out_path.open(encoding="utf-8") as f:
            done = list(csv.DictReader(f))
        seen = {r["player_id"] for r in done}
        print(f"resuming: {len(done)} players already in CSV")

    stale_scrolls = 0
    skipped = []
    blocked = False
    t0 = time.time()
    mode = "a" if (done and not fresh) else "w"
    with out_path.open(mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if mode == "w":
            w.writeheader()
        def cli_emit(e):
            if e.get("kind") == "log":
                print("  " + e["msg"])
            elif e.get("kind") == "blocked":
                print("  " + e.get("error", "blocked"))
        recover = block_recovery(emit=cli_emit)

        try:
            send({"action": "setwin"})
            list_shot = goto_player_list()
        except CaptureBlocked:
            list_shot = shot("list") if recover() else None
        while (list_shot is not None
               and (count is None or len(done) < count) and stale_scrolls < 4):
            try:
                # always act on the topmost unseen fully-visible row of a
                # FRESH screenshot - the list re-sorts live
                rows = [r for r in parse_rows(list_shot) if r["id"] not in seen]
                if not rows:
                    stale_scrolls += 1
                    list_shot = scroll_list(name="list")
                    continue
                stale_scrolls = 0
                row = rows[0]
                seen.add(row["id"])          # marked seen -> never re-tried
                rec, list_shot = collect_player(row, start, end, len(done) + 1)
                done.append(rec)
                w.writerow(rec)
                f.flush()
                print(f"[{len(done)}{'/' + str(count) if count else ''}] "
                      f"{rec['name']} ({rec['player_id']}) rake={rec['rake']} "
                      f"pnl={rec['profit_loss']} [{time.time() - t0:.0f}s]")
            except CaptureBlocked:
                if not recover():
                    blocked = True
                    break
                list_shot = shot("list")     # fresh list after restart
            except Exception as e:
                print(f"  SKIPPED {row['id']}: {e}")
                skipped.append(row["id"])
                try:
                    list_shot = goto_player_list()
                except CaptureBlocked:
                    if not recover():
                        blocked = True
                        break
                    list_shot = shot("list")

    print(f"\n{'Stopped early' if blocked else 'Done'}: {len(done)} players "
          f"total in {time.time() - t0:.0f}s")
    if skipped:
        print(f"skipped this run: {', '.join(skipped)} (rerun to retry them)")
    print(f"CSV: {out_path}")


if __name__ == "__main__":
    main()
