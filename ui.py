"""Minimal ClubGG UI driver: window-relative click / swipe / type / capture.

Usage:
  python ui.py shot <out.png>
  python ui.py click <x> <y> [out.png]          # window-relative coords
  python ui.py swipe <x1> <y1> <x2> <y2> [out.png]
  python ui.py type <text> [out.png]
Every action ends with a screenshot if an output path is given.
"""
import sys
import time
import ctypes
import ctypes.wintypes as wt

import pyautogui

pyautogui.FAILSAFE = True
user32 = ctypes.windll.user32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor-v2, no coord virtualization


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


def force_foreground(hwnd):
    VK_MENU = 0x12
    KEYEVENTF_KEYUP = 0x0002
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.5)


def get_rect(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect


def shot(hwnd, out):
    rect = get_rect(hwnd)
    w, h = rect.right - rect.left, rect.bottom - rect.top
    img = pyautogui.screenshot(region=(rect.left, rect.top, w, h))
    img.save(out)
    print(f"saved: {out} ({w}x{h})")


def main():
    cmd = sys.argv[1]
    hwnd = find_clubgg()
    if hwnd is None:
        print("ERROR: ClubGG window not found")
        sys.exit(1)
    user32.ShowWindow(hwnd, 9)
    force_foreground(hwnd)
    rect = get_rect(hwnd)

    if cmd == "shot":
        shot(hwnd, sys.argv[2])
        return

    if cmd == "click":
        x, y = int(sys.argv[2]), int(sys.argv[3])
        pyautogui.moveTo(rect.left + x, rect.top + y, duration=0.2)
        time.sleep(0.15)
        pyautogui.mouseDown()
        time.sleep(0.12)
        pyautogui.mouseUp()
        print(f"clicked window-relative ({x},{y})")
        out = sys.argv[4] if len(sys.argv) > 4 else None
    elif cmd == "swipe":
        x1, y1, x2, y2 = (int(v) for v in sys.argv[2:6])
        pyautogui.moveTo(rect.left + x1, rect.top + y1)
        pyautogui.mouseDown()
        pyautogui.moveTo(rect.left + x2, rect.top + y2, duration=0.4)
        time.sleep(0.1)
        pyautogui.mouseUp()
        print(f"swiped ({x1},{y1}) -> ({x2},{y2})")
        out = sys.argv[6] if len(sys.argv) > 6 else None
    elif cmd == "type":
        pyautogui.typewrite(sys.argv[2], interval=0.03)
        print(f"typed: {sys.argv[2]}")
        out = sys.argv[3] if len(sys.argv) > 3 else None
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)

    if out:
        time.sleep(1.2)  # let the UI settle before capturing
        shot(hwnd, out)


if __name__ == "__main__":
    main()
