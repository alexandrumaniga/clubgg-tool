"""ClubGG flow recorder.

Run this, then perform your normal weekly data-collection routine in the
ClubGG app (clicking through members, stats screens, etc.). Every click and
keypress that happens while ClubGG is the active window is logged, with a
screenshot of the ClubGG window taken just before the click and another one
~1.5s after (so the resulting screen is captured too).

Press F10 to stop recording.

Output: recordings/<timestamp>/ containing events.jsonl and numbered PNGs.
"""
import ctypes
import ctypes.wintypes as wt
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pyautogui
from pynput import keyboard, mouse

user32 = ctypes.windll.user32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor-v2

pyautogui.FAILSAFE = False  # we only screenshot, never move the mouse

SESSION_DIR = Path(__file__).parent / "recordings" / datetime.now().strftime("%Y%m%d_%H%M%S")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
LOG = (SESSION_DIR / "events.jsonl").open("w", encoding="utf-8")

shot_counter = 0
lock = threading.Lock()
stop_event = threading.Event()


def title_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value.strip()


def clubgg_foreground():
    hwnd = user32.GetForegroundWindow()
    if title_of(hwnd) != "ClubGG":
        return None, None
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return hwnd, rect


def snap(rect, tag):
    global shot_counter
    with lock:
        shot_counter += 1
        name = f"{shot_counter:04d}_{tag}.png"
    w, h = rect.right - rect.left, rect.bottom - rect.top
    try:
        img = pyautogui.screenshot(region=(rect.left, rect.top, w, h))
        img.save(SESSION_DIR / name)
        return name
    except Exception as e:
        print(f"screenshot failed: {e}")
        return None


def log_event(ev):
    ev["t"] = round(time.time(), 3)
    LOG.write(json.dumps(ev, ensure_ascii=False) + "\n")
    LOG.flush()


def announce(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def on_click(x, y, button, pressed):
    if not pressed or stop_event.is_set():
        return
    hwnd, rect = clubgg_foreground()
    if hwnd is None:
        return  # ignore clicks outside ClubGG
    rel = (x - rect.left, y - rect.top)
    before = snap(rect, "before")
    announce(f"CLICK  at {rel}  (screenshot: {before})")
    log_event({"type": "click", "button": str(button), "rel": rel,
               "window": [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top],
               "shot_before": before})

    def after():
        time.sleep(1.5)
        if stop_event.is_set():
            return
        hwnd2, rect2 = clubgg_foreground()
        if hwnd2 is not None:
            after_name = snap(rect2, "after")
            announce(f"       screen settled  (screenshot: {after_name})")
            log_event({"type": "settle", "shot_after": after_name})
    threading.Thread(target=after, daemon=True).start()


def on_scroll(x, y, dx, dy):
    if stop_event.is_set():
        return
    hwnd, rect = clubgg_foreground()
    if hwnd is None:
        return
    announce(f"SCROLL at {(x - rect.left, y - rect.top)}  dy={dy}")
    log_event({"type": "scroll", "rel": (x - rect.left, y - rect.top), "dy": dy})


def on_key(key):
    if key == keyboard.Key.f10:
        print("F10 pressed - stopping recorder.")
        stop_event.set()
        return False
    if stop_event.is_set():
        return False
    hwnd, rect = clubgg_foreground()
    if hwnd is None:
        return  # only record keys typed into ClubGG
    try:
        k = key.char
    except AttributeError:
        k = str(key)
    announce(f"KEY    {k}")
    log_event({"type": "key", "key": k})


def main():
    print(f"Recording to: {SESSION_DIR}")
    print("Do your normal weekly routine in ClubGG now.")
    print("Only activity inside the ClubGG window is recorded. Press F10 to finish.")
    ml = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    kl = keyboard.Listener(on_press=on_key)
    ml.start(); kl.start()
    kl.join()
    stop_event.set()
    ml.stop()
    time.sleep(0.3)
    LOG.close()
    print(f"Done. {shot_counter} screenshots saved in {SESSION_DIR}")
    try:
        input("Press Enter to close this window.")
    except EOFError:
        pass  # no console attached (run in background)


if __name__ == "__main__":
    main()
