"""ClubGG elevated driver.

ClubGG runs as administrator, so Windows discards synthetic input from
non-elevated processes. This driver runs elevated (one UAC prompt) and
executes UI commands sent by gg.py through a file-based queue, so the rest
of the tooling can stay non-elevated.

Start it (accept the UAC prompt):
  Start-Process -FilePath python -ArgumentList '"c:\\Users\\PC1\\clubgg-tool\\driver.py"' -Verb RunAs

Protocol: gg.py writes bridge/cmd.json; the driver executes it and writes
bridge/res_<id>.json. All coordinates are ClubGG-window-relative.
Actions: ping, setwin, shot, click, swipe, type, quit.
"""
import json
import os
import subprocess
import time
import ctypes
import ctypes.wintypes as wt
from pathlib import Path

import mss
import pyautogui
from PIL import Image

pyautogui.FAILSAFE = False
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor-v2

# Remember ClubGG's exe path so we can relaunch it after killing it.
GG_PATH = Path(__file__).parent / "bridge" / "clubgg_path.txt"

user32.CreateWindowExW.restype = wt.HWND
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]

BRIDGE = Path(__file__).parent / "bridge"
BRIDGE.mkdir(exist_ok=True)
CMD = BRIDGE / "cmd.json"
HEARTBEAT = BRIDGE / "driver_alive.txt"

# Canonical window geometry - all skill coordinates assume this position/size.
# ClubGG is a Unity app that PAUSES RENDERING when its window is not focused,
# so it is only capturable while it is the focused foreground window. The
# driver keeps it focused during each action; runs must not be interrupted by
# the user grabbing focus. Primary-monitor position is the proven config.
DEFAULT_POS = (37, 0)
DEFAULT_SIZE = (540, 990)


def process_of_window(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def exe_path_of_pid(pid):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(h)
    return None


def remember_gg_path():
    hwnd = find_clubgg()
    if not hwnd:
        return
    path = exe_path_of_pid(process_of_window(hwnd))
    if path:
        try:
            GG_PATH.write_text(path, encoding="utf-8")
        except OSError:
            pass


def restart_clubgg():
    """Kill ClubGG and relaunch it (elevated child - no UAC since the driver
    is already elevated). Returns the exe path. Waits for the window to
    reappear but does NOT log in or enter a club (caller handles that)."""
    hwnd = find_clubgg()
    path = None
    if hwnd:
        pid = process_of_window(hwnd)
        path = exe_path_of_pid(pid)
        PROCESS_TERMINATE = 0x0001
        h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if h:
            kernel32.TerminateProcess(h, 1)
            kernel32.CloseHandle(h)
    if not path and GG_PATH.exists():
        path = GG_PATH.read_text(encoding="utf-8").strip()
    if not path:
        raise RuntimeError("ClubGG exe path unknown - cannot relaunch")
    # ClubGG.exe refuses to run directly ("run launcher.exe"); the launcher
    # updates then starts the client, so always relaunch via launcher.exe.
    folder = Path(path).parent
    launcher = folder / "launcher.exe"
    target = str(launcher if launcher.exists() else path)
    # wait for the old window to disappear
    for _ in range(20):
        if not find_clubgg():
            break
        time.sleep(0.5)
    time.sleep(2)
    subprocess.Popen([target], cwd=str(folder))
    # wait for the new ClubGG window (launcher may update first, so be patient)
    for _ in range(120):
        if find_clubgg():
            break
        time.sleep(1)
    else:
        raise RuntimeError("ClubGG did not reappear within 120s of relaunch")
    time.sleep(5)  # let the app finish loading its first screen
    return path


def find_clubgg():
    result = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def enum_cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value.strip() == "ClubGG":
            result.append(hwnd)
        return True

    user32.EnumWindows(enum_cb, 0)
    return result[0] if result else None


def _allow_foreground_stealing():
    # SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001; set to 0 so SetForegroundWindow
    # is not blocked by the foreground lock while another app is active.
    user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(0), 0)


def force_foreground(hwnd):
    """Reliably make hwnd the focused foreground window even when another
    process currently owns the foreground (defeats the foreground lock via
    AttachThreadInput). ClubGG is Unity and only renders while focused, so
    this must actually win, not just try."""
    HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
    SWP = 0x0002 | 0x0001  # NOMOVE | NOSIZE
    fg = user32.GetForegroundWindow()
    cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)
    attached = []
    for tid in {fg_tid, tgt_tid}:
        if tid and tid != cur_tid and user32.AttachThreadInput(cur_tid, tid, True):
            attached.append(tid)
    try:
        VK_MENU, KEYUP = 0x12, 0x0002
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYUP, 0)
        user32.BringWindowToTop(hwnd)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        for tid in attached:
            user32.AttachThreadInput(cur_tid, tid, False)
    time.sleep(0.4)


def visually_on_top(hwnd, rect):
    """True if the pixel at the window's center actually belongs to ClubGG."""
    GA_ROOT = 2
    cx = (rect.left + rect.right) // 2
    cy = (rect.top + rect.bottom) // 2
    under = user32.WindowFromPoint(wt.POINT(cx, cy))
    return user32.GetAncestor(under, GA_ROOT) == hwnd


def get_rect(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect


# --- DWM thumbnail mirror ----------------------------------------------------
# ClubGG's window gets promoted to a GPU hardware overlay plane (MPO), which
# makes it invisible to every software capture API (screenshots show whatever
# is BEHIND it). DWM thumbnails render from the compositor and are immune, so
# the driver mirrors ClubGG into a plain window and captures the mirror.
# Bonus: the mirror stays correct even when ClubGG is covered by other windows.

MIRROR = {"hwnd": None, "x": 0, "y": 0, "thumb": None, "target": None}


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [("dwFlags", wt.DWORD), ("rcDestination", wt.RECT),
                ("rcSource", wt.RECT), ("opacity", ctypes.c_ubyte),
                ("fVisible", wt.BOOL), ("fSourceClientAreaOnly", wt.BOOL)]


def create_mirror():
    vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    if vx <= -DEFAULT_SIZE[0]:        # a monitor exists to the left
        x, y = vx + 60, 120
    else:                             # fallback: right side of the primary
        x, y = user32.GetSystemMetrics(0) - DEFAULT_SIZE[0] - 10, 45
    WS_POPUP, WS_VISIBLE = 0x80000000, 0x10000000
    EX = 0x00000080 | 0x08000000 | 0x00000008  # TOOLWINDOW|NOACTIVATE|TOPMOST
    hwnd = user32.CreateWindowExW(EX, "STATIC", "GGMirror",
                                  WS_POPUP | WS_VISIBLE, x, y,
                                  DEFAULT_SIZE[0], DEFAULT_SIZE[1],
                                  None, None, None, None)
    if not hwnd:
        print("WARNING: mirror window creation failed - falling back to "
              "direct capture (may be blank if MPO is active)")
        return
    MIRROR.update(hwnd=hwnd, x=x, y=y)
    print(f"mirror window at ({x},{y})")


def refresh_thumbnail(target, w, h):
    if MIRROR["thumb"] and MIRROR["target"] == target:
        return
    if MIRROR["thumb"]:
        dwmapi.DwmUnregisterThumbnail(MIRROR["thumb"])
        MIRROR.update(thumb=None, target=None)
    thumb = ctypes.c_void_p()
    hr = dwmapi.DwmRegisterThumbnail(MIRROR["hwnd"], target,
                                     ctypes.byref(thumb))
    if hr:
        raise RuntimeError(f"DwmRegisterThumbnail failed: {hr:#010x}")
    props = DWM_THUMBNAIL_PROPERTIES()
    props.dwFlags = 0x1 | 0x4 | 0x8 | 0x10  # DST|OPACITY|VISIBLE|CLIENTONLY
    props.rcDestination = wt.RECT(0, 0, w, h)
    props.opacity = 255
    props.fVisible = True
    props.fSourceClientAreaOnly = False
    hr = dwmapi.DwmUpdateThumbnailProperties(thumb, ctypes.byref(props))
    if hr:
        raise RuntimeError(f"DwmUpdateThumbnailProperties failed: {hr:#010x}")
    MIRROR.update(thumb=thumb, target=target)
    time.sleep(0.15)  # let DWM compose the first mirrored frame


def pump_messages():
    msg = wt.MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def demote_from_overlay(hwnd):
    """Make the window 254/255 opaque (imperceptible) so DWM cannot promote
    it to a hardware overlay plane (MPO). Overlay-promoted windows are
    invisible to BitBlt screenshots - the capture shows the window BEHIND."""
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x80000
    LWA_ALPHA = 0x2
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not ex & WS_EX_LAYERED:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(hwnd, 0, 254, LWA_ALPHA)


def ensure_window():
    """Find ClubGG, bring it to front, and force canonical position/size.

    Every action goes through this, so window-relative coordinates are
    always valid regardless of where the user left the window.
    """
    hwnd = find_clubgg()
    if hwnd is None:
        raise RuntimeError("ClubGG window not found")
    demote_from_overlay(hwnd)
    rect = get_rect(hwnd)
    size = (rect.right - rect.left, rect.bottom - rect.top)
    if (user32.GetForegroundWindow() == hwnd and visually_on_top(hwnd, rect)
            and (rect.left, rect.top) == DEFAULT_POS and size == DEFAULT_SIZE):
        return hwnd, rect  # fast path: already front and in place
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    for attempt in range(6):
        force_foreground(hwnd)
        if (user32.GetForegroundWindow() == hwnd
                and visually_on_top(hwnd, get_rect(hwnd))):
            break
        time.sleep(0.5)  # user may be interacting with another window
    else:
        raise RuntimeError("could not bring ClubGG to the top (another "
                           "window keeps covering it) - action aborted")
    rect = get_rect(hwnd)
    size = (rect.right - rect.left, rect.bottom - rect.top)
    if (rect.left, rect.top) != DEFAULT_POS or size != DEFAULT_SIZE:
        user32.MoveWindow(hwnd, DEFAULT_POS[0], DEFAULT_POS[1],
                          DEFAULT_SIZE[0], DEFAULT_SIZE[1], True)
        time.sleep(0.5)  # let the app relayout
        rect = get_rect(hwnd)
        size = (rect.right - rect.left, rect.bottom - rect.top)
        if size != DEFAULT_SIZE:
            raise RuntimeError(f"could not resize ClubGG to {DEFAULT_SIZE}, got {size}")
    return hwnd, rect


def capture_mirror(hwnd, w, h):
    """Capture via a DWM thumbnail mirror - immune to MPO overlay and to
    ClubGG being covered by other windows. Returns a PIL image or None."""
    if not MIRROR["hwnd"]:
        return None
    try:
        refresh_thumbnail(hwnd, w, h)
        pump_messages()
        time.sleep(0.1)
        with mss.mss() as sct:
            raw = sct.grab({"left": MIRROR["x"], "top": MIRROR["y"],
                            "width": w, "height": h})
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        # A near-black frame means DWM has no redirected surface for the
        # source (occluded and/or on a GPU overlay plane) - reject it so the
        # caller falls back to direct capture.
        hi = img.convert("L").getextrema()[1]
        if hi < 40:
            return None
        return img
    except Exception as e:
        print(f"mirror capture failed: {e}")
        return None


def do_shot(hwnd, out):
    rect = get_rect(hwnd)
    w, h = rect.right - rect.left, rect.bottom - rect.top
    img = capture_mirror(hwnd, w, h)
    method = "mirror"
    if img is None:
        img = pyautogui.screenshot(region=(rect.left, rect.top, w, h))
        method = "direct"
    img.save(out)
    aff = wt.DWORD()
    user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(aff))
    return {"shot": str(out), "size": [w, h], "method": method,
            "affinity": aff.value,
            "foreground": user32.GetForegroundWindow() == hwnd}


def handle(cmd):
    action = cmd["action"]
    if action == "ping":
        return {"pong": True,
                "elevated": bool(ctypes.windll.shell32.IsUserAnAdmin())}
    if action == "quit":
        return {"quitting": True}
    if action == "ggpath":
        remember_gg_path()
        hwnd = find_clubgg()
        return {"path": exe_path_of_pid(process_of_window(hwnd)) if hwnd
                else (GG_PATH.read_text(encoding="utf-8").strip()
                      if GG_PATH.exists() else None)}
    if action == "restartgg":
        path = restart_clubgg()
        hwnd, rect = ensure_window()
        res = {"relaunched": True, "path": path}
        if cmd.get("shot"):
            res.update(do_shot(hwnd, cmd["shot"]))
        return res

    hwnd, rect = ensure_window()
    remember_gg_path()  # cache the exe path whenever we have a live window

    def assert_foreground():
        # Final check right before injecting input: if focus was stolen
        # between ensure_window() and now, refuse rather than hit another app.
        if (user32.GetForegroundWindow() != hwnd
                or not visually_on_top(hwnd, get_rect(hwnd))):
            raise RuntimeError("ClubGG lost foreground right before input - "
                               "action aborted")

    if action == "setwin":
        pass  # ensure_window() already enforced canonical geometry
    elif action == "click":
        x, y = cmd["x"], cmd["y"]
        pyautogui.moveTo(rect.left + x, rect.top + y, duration=0.25)
        time.sleep(0.1)
        assert_foreground()
        pyautogui.mouseDown()
        time.sleep(0.12)
        pyautogui.mouseUp()
    elif action == "swipe":
        pyautogui.moveTo(rect.left + cmd["x1"], rect.top + cmd["y1"])
        assert_foreground()
        pyautogui.mouseDown()
        pyautogui.moveTo(rect.left + cmd["x2"], rect.top + cmd["y2"],
                         duration=0.4)
        time.sleep(0.5)  # hold before release so the list gets no fling momentum
        pyautogui.mouseUp()
    elif action == "scroll":
        pyautogui.moveTo(rect.left + cmd["x"], rect.top + cmd["y"])
        time.sleep(0.1)
        assert_foreground()
        pyautogui.scroll(cmd["clicks"])  # positive = up, negative = down
    elif action == "type":
        assert_foreground()
        if cmd.get("clear"):
            # Unity input fields often ignore Ctrl+A, so clear by walking to
            # the end and backspacing well past any plausible content length.
            pyautogui.press("end")
            time.sleep(0.03)
            pyautogui.press("backspace", presses=40, interval=0.01)
            pyautogui.press("delete", presses=40, interval=0.01)
            time.sleep(0.05)
        pyautogui.typewrite(cmd["text"], interval=0.03)
    elif action == "shot":
        pass  # screenshot handled below
    else:
        raise ValueError(f"unknown action: {action}")

    res = {"window": [rect.left, rect.top,
                      rect.right - rect.left, rect.bottom - rect.top]}
    if cmd.get("shot"):
        if action != "shot":
            time.sleep(cmd.get("settle", 1.2))  # let the UI settle first
        assert_foreground()  # an overlapping window would poison the capture
        res.update(do_shot(hwnd, cmd["shot"]))
    return res


def main():
    _allow_foreground_stealing()
    # Park our own console on the right so it can never cover ClubGG.
    console = ctypes.windll.kernel32.GetConsoleWindow()
    if console:
        user32.MoveWindow(console, 700, 40, 900, 500, True)
    print(f"ClubGG driver running (elevated={bool(ctypes.windll.shell32.IsUserAnAdmin())})")
    print(f"watching {CMD} - leave this window open. Ctrl+C to stop.")
    # DWM thumbnail mirror is disabled: ClubGG's content lives on a GPU
    # overlay plane that DWM has no redirected copy of, so the mirror is
    # always black. Direct capture works as long as ClubGG is not covered.
    # create_mirror()
    last_beat = 0.0
    while True:
        pump_messages()
        now = time.time()
        if now - last_beat > 2:
            HEARTBEAT.write_text(str(now), encoding="utf-8")
            last_beat = now
        if CMD.exists():
            try:
                data = json.loads(CMD.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                time.sleep(0.05)  # writer not finished yet
                continue
            CMD.unlink()
            try:
                out = {"ok": True, **handle(data)}
            except Exception as e:
                out = {"ok": False, "error": str(e)}
            res_path = BRIDGE / f"res_{data.get('id', 'x')}.json"
            tmp = res_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(out), encoding="utf-8")
            os.replace(tmp, res_path)
            print(f"{data.get('action')}: {out}")
            if data.get("action") == "quit":
                break
        time.sleep(0.1)


if __name__ == "__main__":
    main()
