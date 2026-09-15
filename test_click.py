"""Test: find the ClubGG window, bring it to view, move the mouse to the
red 4-dot button in the bottom-right corner, click it once, then exit.

The button sits at a fixed offset from the window's bottom-right corner
(measured on recordings/20260813_045740/0007_before.png: 55px left, 59px up),
so this works even if the window has moved.
"""
import sys
import time
import ctypes
import ctypes.wintypes as wt

import pyautogui

pyautogui.FAILSAFE = True
user32 = ctypes.windll.user32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor-v2

BUTTON_OFFSET_FROM_RIGHT = 55
BUTTON_OFFSET_FROM_BOTTOM = 59


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


def main():
    hwnd = find_clubgg()
    if hwnd is None:
        print("ERROR: ClubGG window not found")
        sys.exit(1)

    user32.ShowWindow(hwnd, 9)  # SW_RESTORE, in case it's minimized
    force_foreground(hwnd)

    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    print(f"ClubGG window at ({rect.left},{rect.top}) size {w}x{h}")

    x = rect.right - BUTTON_OFFSET_FROM_RIGHT
    y = rect.bottom - BUTTON_OFFSET_FROM_BOTTOM
    print(f"moving to red 4-dot button at screen ({x},{y}) "
          f"= window-relative ({x - rect.left},{y - rect.top})")

    pyautogui.moveTo(x, y, duration=0.8)  # slow enough to watch
    time.sleep(0.3)
    pyautogui.mouseDown()
    time.sleep(0.12)
    pyautogui.mouseUp()
    print("clicked once - done.")


if __name__ == "__main__":
    main()
