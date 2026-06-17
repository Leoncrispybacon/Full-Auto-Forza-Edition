# ============================================================
#  capture.py — Screenshot capture, template management,
#               node position recording
# ============================================================

import cv2
import numpy as np
import json
import os
import threading
import time
import ctypes
from ctypes import wintypes as _wintypes
import mss

import config


# ── IME / input-language helper ───────────────────────────────

_LANG_ENGLISH = 0x09   # primary language id for English


def force_english_ime() -> bool:
    """If a non-English input language is active on the foreground (game)
    window, switch it to English (US); otherwise leave it completely alone.

    A CJK IME in native mode can consume keystrokes before the game reads them.
    But forcing a switch *unconditionally* is harmful: users who already set
    English (often the CJK IME toggled to alphanumeric mode) get their state
    clobbered, and Windows can revert them to the IME's default native (Chinese)
    mode — re-introducing the very problem. So we **check first** and only act
    when the current language isn't already English. No-op (returns True)
    when already English, so a user who manages their IME manually is never
    disturbed. Best-effort and non-fatal.
    """
    try:
        u32 = ctypes.windll.user32
        u32.GetForegroundWindow.restype = ctypes.c_void_p
        u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u32.GetWindowThreadProcessId.restype = ctypes.c_ulong
        u32.GetKeyboardLayout.argtypes = [ctypes.c_ulong]
        u32.GetKeyboardLayout.restype = ctypes.c_void_p

        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return False
        tid = u32.GetWindowThreadProcessId(hwnd, None)
        cur = u32.GetKeyboardLayout(tid) or 0
        # Low word of the HKL is the LANGID; primary language is its low 10 bits.
        if (cur & 0x3FF) == _LANG_ENGLISH:
            return True   # already English — do NOT touch the user's setup

        # Non-English active → switch the game window to English (US).
        u32.LoadKeyboardLayoutW.restype  = ctypes.c_void_p
        u32.LoadKeyboardLayoutW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_void_p, ctypes.c_void_p]
        KLF_ACTIVATE = 0x00000001
        WM_INPUTLANGCHANGEREQUEST = 0x0050
        # c_void_p so the 64-bit HKL handle isn't truncated as lParam.
        hkl = u32.LoadKeyboardLayoutW("00000409", KLF_ACTIVATE)  # en-US
        if not hkl:
            return False
        u32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)
        return True
    except Exception:
        return False


def get_foreground_window():
    """Handle of the current foreground window (the game, while it's focused),
    or None. Returned as an opaque int — only ever passed back to
    focus_window()."""
    try:
        u32 = ctypes.windll.user32
        u32.GetForegroundWindow.restype = ctypes.c_void_p
        return u32.GetForegroundWindow()
    except Exception:
        return None


def focus_window(hwnd) -> bool:
    """Best-effort bring `hwnd` to the foreground.

    Why this exists: injected input (SendInput) goes to whatever window has
    focus. When the user stops a script with the FAFE *UI button*, focus moves
    to FAFE — so a key release sent afterwards lands on FAFE and the GAME keeps
    the key (e.g. W) held. Refocusing the game before the release fixes that. On
    the hotkey/normal path the game is already foreground, so this is a no-op
    (returns True immediately).

    Works around Windows' foreground-lock by briefly AttachThreadInput-ing to
    the current foreground thread. Best-effort and non-fatal."""
    if not hwnd:
        return False
    try:
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        u32.GetForegroundWindow.restype = ctypes.c_void_p
        u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u32.GetWindowThreadProcessId.restype = ctypes.c_ulong
        u32.AttachThreadInput.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int]
        u32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        u32.SetForegroundWindow.restype = ctypes.c_int
        u32.BringWindowToTop.argtypes = [ctypes.c_void_p]
        u32.IsIconic.argtypes = [ctypes.c_void_p]
        u32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]

        fg = u32.GetForegroundWindow()
        if fg == hwnd:
            return True   # already focused (hotkey / normal-detection path)
        cur_tid = k32.GetCurrentThreadId()
        fg_tid  = u32.GetWindowThreadProcessId(fg, None) if fg else 0
        tgt_tid = u32.GetWindowThreadProcessId(hwnd, None)
        attached_fg = attached_tgt = False
        if fg_tid and fg_tid != cur_tid:
            attached_fg = bool(u32.AttachThreadInput(cur_tid, fg_tid, True))
        if tgt_tid and tgt_tid != cur_tid and tgt_tid != fg_tid:
            attached_tgt = bool(u32.AttachThreadInput(cur_tid, tgt_tid, True))
        try:
            if u32.IsIconic(hwnd):
                u32.ShowWindow(hwnd, 9)   # SW_RESTORE (only if minimized)
            u32.BringWindowToTop(hwnd)
            ok = bool(u32.SetForegroundWindow(hwnd))
        finally:
            if attached_fg:
                u32.AttachThreadInput(cur_tid, fg_tid, False)
            if attached_tgt:
                u32.AttachThreadInput(cur_tid, tgt_tid, False)
        return ok
    except Exception:
        return False


# ── Mouse click (SendInput) ───────────────────────────────────
# Shared left-click helper for clicking a detected on-screen element (e.g. the
# Super Wheelspin tile, or a menu nav button). Click target is a frame-local
# (x, y) plus the monitor's screen origin offset.

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", _wintypes.DWORD), ("dwFlags", _wintypes.DWORD),
                ("time", _wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _MINPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("_pad", ctypes.c_byte * 28)]


class _MINPUT(ctypes.Structure):
    _fields_ = [("type", _wintypes.DWORD), ("union", _MINPUT_UNION)]


def mouse_click(x: int, y: int, mon_left: int = 0, mon_top: int = 0,
                post_wait: float = 0.5):
    """Left-click at frame-local (x, y), offset to the monitor's screen origin."""
    ctypes.windll.user32.SetCursorPos(int(x + mon_left), int(y + mon_top))
    time.sleep(0.1)
    for flag in (0x0002, 0x0004):   # LEFTDOWN, LEFTUP
        inp = _MINPUT(type=0, union=_MINPUT_UNION(mi=_MOUSEINPUT(
            dx=0, dy=0, mouseData=0, dwFlags=flag, time=0, dwExtraInfo=None)))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_MINPUT))
        time.sleep(0.05)
    time.sleep(post_wait)


_MOUSEEVENTF_WHEEL = 0x0800
_WHEEL_DELTA       = 120

def mouse_scroll(notches: int, post_wait: float = 0.1):
    """Inject a vertical mouse-wheel scroll into the foreground window.

    `notches` > 0 scrolls UP (wheel forward / away from the user), < 0 scrolls
    DOWN — the Windows convention (positive WHEEL_DELTA = away). One notch =
    WHEEL_DELTA (120). Used to scroll long in-game grids (e.g. the Car
    Collection list down to the bottom). mouseData is a DWORD, so a negative
    delta is passed as its unsigned 32-bit two's-complement."""
    data = int(notches) * _WHEEL_DELTA
    if data < 0:
        data += 0x100000000        # unsigned 32-bit wrap for the DWORD field
    inp = _MINPUT(type=0, union=_MINPUT_UNION(mi=_MOUSEINPUT(
        dx=0, dy=0, mouseData=data, dwFlags=_MOUSEEVENTF_WHEEL,
        time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_MINPUT))
    if post_wait:
        time.sleep(post_wait)


# ── Background-window input (PostMessage) ─────────────────────
# EXPERIMENTAL: send input to a specific window WITHOUT giving it focus, so the
# user can keep working in another window while a script runs (game visible but
# unfocused, e.g. on a second monitor). Caveat: many games read GAMEPLAY input
# via DirectInput / Raw Input, which does NOT consume posted window messages —
# so a held key for driving may not register this way even when menu keys (which
# read the window message queue) do. SendInput-to-focused-window stays the
# reliable path; this is opt-in via the background_input config flag.

_WM_KEYDOWN     = 0x0100
_WM_KEYUP       = 0x0101
_WM_MOUSEMOVE   = 0x0200
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP   = 0x0202
_MK_LBUTTON     = 0x0001
# Hover dwell between moving to the target and pressing: posted-message clicks
# don't move the real cursor, so the game only "hovers" the target when it
# processes the WM_MOUSEMOVE. UI elements that highlight-on-hover (top-nav tabs,
# menu rows) need that highlight to settle BEFORE the button-down, or the click
# lands on a stale target / is dropped (the CARS-tab-not-switching bug). We post
# the move twice (so motion is registered) and dwell this long before clicking.
_CLICK_MOVE_DWELL = 0.15


def find_game_window(title_substr: str = "Forza Horizon 6"):
    """First visible top-level window whose title contains `title_substr`
    (case-insensitive), or None. Used for experimental background input."""
    try:
        u32 = ctypes.windll.user32
        u32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        u32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        u32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        target = (title_substr or "").lower()
        found = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _cb(hwnd, _lparam):
            try:
                if not u32.IsWindowVisible(hwnd):
                    return True
                n = u32.GetWindowTextLengthW(hwnd)
                if n <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                if target and target in buf.value.lower():
                    found.append(hwnd)
                    return False   # stop enumeration on first match
            except Exception:
                pass
            return True

        u32.EnumWindows(WNDENUMPROC(_cb), 0)
        return found[0] if found else None
    except Exception:
        return None


def get_client_rect(hwnd):
    """Client (content) area of `hwnd` in absolute screen pixels:
    (left, top, width, height), or None. Excludes the title bar/borders. Used to
    capture and reason about a windowed game whose window doesn't fill the
    monitor — detection must size templates/ROIs to the window, not the screen.
    The process is DPI-aware, so these are physical pixels (matching mss)."""
    if not hwnd:
        return None
    try:
        u32 = ctypes.windll.user32

        class _RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class _PT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        u32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RECT)]
        u32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PT)]
        r = _RECT()
        if not u32.GetClientRect(hwnd, ctypes.byref(r)):
            return None
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            return None
        pt = _PT(0, 0)
        u32.ClientToScreen(hwnd, ctypes.byref(pt))
        return (int(pt.x), int(pt.y), int(w), int(h))
    except Exception:
        return None


def post_key(hwnd, vk: int, key_up: bool = False,
             extended: bool = False, repeat: bool = False):
    """Post a key event (WM_KEYDOWN/WM_KEYUP) to `hwnd` via PostMessage so it
    reaches the window even when unfocused. `repeat` sets the previous-key-down
    bit for sustained/auto-repeat keydowns. See the section note re: DirectInput."""
    if not hwnd:
        return
    try:
        u32 = ctypes.windll.user32
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_size_t]
        u32.MapVirtualKeyW.argtypes = [ctypes.c_uint, ctypes.c_uint]
        scan = u32.MapVirtualKeyW(vk, 0) & 0xFF   # MAPVK_VK_TO_VSC
        lparam = 1 | (scan << 16)                 # repeat count 1 + scancode
        if extended:
            lparam |= (1 << 24)
        if key_up:
            lparam |= (1 << 30) | (1 << 31)       # prev-down + transition(up)
            msg = _WM_KEYUP
        else:
            if repeat:
                lparam |= (1 << 30)               # previous state down
            msg = _WM_KEYDOWN
        u32.PostMessageW(hwnd, msg, vk, lparam)
    except Exception:
        pass


def post_click(hwnd, screen_x: int, screen_y: int, post_wait: float = 0.5):
    """Left-click at absolute screen (x, y) on `hwnd` via PostMessage, converting
    to the window's client coords first — reaches an unfocused window."""
    if not hwnd:
        return
    try:
        u32 = ctypes.windll.user32

        class _PT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        u32.ScreenToClient.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PT)]
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_size_t]
        pt = _PT(int(screen_x), int(screen_y))
        u32.ScreenToClient(hwnd, ctypes.byref(pt))
        lparam = ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF)
        # Move to the target (twice, so motion registers) and dwell so a
        # hover-highlight settles before the press; then click.
        u32.PostMessageW(hwnd, _WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.03)
        u32.PostMessageW(hwnd, _WM_MOUSEMOVE, 0, lparam)
        time.sleep(_CLICK_MOVE_DWELL)
        u32.PostMessageW(hwnd, _WM_LBUTTONDOWN, _MK_LBUTTON, lparam)
        time.sleep(0.05)
        u32.PostMessageW(hwnd, _WM_LBUTTONUP, 0, lparam)
        if post_wait:
            time.sleep(post_wait)
    except Exception:
        pass


def post_client_click(hwnd, client_x: int, client_y: int, post_wait: float = 0.5):
    """Left-click at CLIENT coords (x, y) on `hwnd` via PostMessage — no screen
    conversion, so it's independent of the window's screen POSITION (robust to
    the window being moved). For window-capture mode, where detections are
    already in the window's client space."""
    if not hwnd:
        return
    try:
        u32 = ctypes.windll.user32
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_size_t]
        lparam = ((int(client_y) & 0xFFFF) << 16) | (int(client_x) & 0xFFFF)
        # Move to the target (twice, so motion registers) and dwell so a
        # hover-highlight settles before the press; then click.
        u32.PostMessageW(hwnd, _WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.03)
        u32.PostMessageW(hwnd, _WM_MOUSEMOVE, 0, lparam)
        time.sleep(_CLICK_MOVE_DWELL)
        u32.PostMessageW(hwnd, _WM_LBUTTONDOWN, _MK_LBUTTON, lparam)
        time.sleep(0.05)
        u32.PostMessageW(hwnd, _WM_LBUTTONUP, 0, lparam)
        if post_wait:
            time.sleep(post_wait)
    except Exception:
        pass


_WM_ACTIVATE    = 0x0006
_WM_SETFOCUS    = 0x0007
_WM_ACTIVATEAPP = 0x001C
_WM_NCACTIVATE  = 0x0086
_WA_ACTIVE      = 1


def set_window_active(hwnd):
    """Post the messages that tell a window it has become the active window —
    WITHOUT actually focusing it — to try to stop a game that auto-pauses when
    it loses focus. Best-effort: works only for games that trust these messages;
    games that poll GetForegroundWindow/GetActiveWindow each frame ignore it,
    and there's no external (no-injection) fix for those."""
    if not hwnd:
        return
    try:
        u32 = ctypes.windll.user32
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_size_t]
        u32.PostMessageW(hwnd, _WM_ACTIVATEAPP, 1, 0)
        u32.PostMessageW(hwnd, _WM_NCACTIVATE, 1, 0)
        u32.PostMessageW(hwnd, _WM_ACTIVATE, _WA_ACTIVE, 0)
        u32.PostMessageW(hwnd, _WM_SETFOCUS, 0, 0)
    except Exception:
        pass


_WM_MOUSEWHEEL = 0x020A


def post_scroll(hwnd, notches, post_wait: float = 0.1):
    """Mouse-wheel scroll posted to a specific window (background-safe). Positive
    notches scroll up, negative down (Windows convention). lParam is the cursor
    point in SCREEN coords (per WM_MOUSEWHEEL) — we use the window's centre."""
    if not hwnd:
        return
    try:
        u32 = ctypes.windll.user32
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_size_t]
        rect = get_client_rect(hwnd)
        if rect:
            l, t, w, h = rect
            cx, cy = l + w // 2, t + h // 2
        else:
            cx = cy = 0
        delta = int(notches) * 120                 # WHEEL_DELTA
        wparam = (delta & 0xFFFF) << 16            # HIWORD = signed delta, LOWORD = 0
        lparam = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
        u32.PostMessageW(hwnd, _WM_MOUSEWHEEL, wparam, lparam)
        if post_wait:
            time.sleep(post_wait)
    except Exception:
        pass


def get_window_pid(hwnd):
    """Process id that owns `hwnd`, or None."""
    if not hwnd:
        return None
    try:
        u32 = ctypes.windll.user32
        u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p,
                                                 ctypes.POINTER(ctypes.c_ulong)]
        pid = ctypes.c_ulong(0)
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def set_process_muted(pid, mute: bool) -> bool:
    """Mute/unmute one process's audio session (per-app — other apps' audio is
    untouched). Returns True if a matching session was found and set. Uses
    pycaw/Core Audio; returns False (no-op) if pycaw isn't available. Safe to
    call from a worker thread (initialises COM for that thread)."""
    if not pid:
        return False
    try:
        from pycaw.pycaw import AudioUtilities
        import comtypes
    except Exception:
        return False
    try:
        comtypes.CoInitialize()
    except Exception:
        pass
    try:
        done = False
        for s in AudioUtilities.GetAllSessions():
            try:
                if s.ProcessId == pid and s.SimpleAudioVolume is not None:
                    s.SimpleAudioVolume.SetMute(1 if mute else 0, None)
                    done = True
            except Exception:
                continue
        return done
    except Exception:
        return False
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass


# ── mss screen capture ───────────────────────────────────────

# An mss instance is bound to the thread that created it, so we keep one
# per thread and reuse it across captures. Rebuilding mss.MSS() on every
# frame (the detection loop grabs ~2×/sec, indefinitely) leaks GDI
# device-contexts/bitmaps on Windows and eventually makes grab() return
# black frames — which is why long runs grew more failure-prone.
_tls = threading.local()

# Reusing one mss instance fixes the per-call GDI leak, but some mss versions
# still accumulate native GDI/handles slowly even on a reused instance over many
# thousands of grabs (the detection loop grabs ~2×/sec indefinitely) — which can
# make long runs deteriorate. Periodically rebuild the instance to flush that.
# ~400 grabs ≈ a few minutes; rebuild cost is negligible.
_SCT_REFRESH_EVERY = 400

# ── Overlay self-mask ─────────────────────────────────────────
# The app's own status overlay is a visible on-screen window that the detector
# must NEVER see — it pixel-matches the game's menu/dialog templates AND shows
# log/status text containing template hint words, so capturing it creates a
# self-detection feedback loop.  We do NOT use SetWindowDisplayAffinity
# (WDA_EXCLUDEFROMCAPTURE): on some displays — notably handhelds whose built-in
# screen is driven through a capture/composition path (Xbox/ROG Ally) — it hides
# the window from the USER too, and there's no reliable way to detect that.
# Instead, because the overlay is our own window we know its exact screen rect,
# so we simply blank that rectangle out of every detection frame.  Works on
# every display path and keeps the overlay fully visible to the user.
# Set from the UI thread, read from the detection thread; an immutable-tuple
# global is atomic enough under the GIL (no lock needed).
_overlay_rect = None   # (x, y, w, h) absolute virtual-screen pixels, or None


def set_overlay_mask(x, y, w, h):
    """Register the overlay's absolute screen rect to blank from detection grabs."""
    global _overlay_rect
    try:
        if w > 0 and h > 0:
            _overlay_rect = (int(x), int(y), int(w), int(h))
    except Exception:
        pass


def clear_overlay_mask():
    """Stop masking (overlay hidden)."""
    global _overlay_rect
    _overlay_rect = None


def _get_sct():
    """Return this thread's reusable mss instance, periodically rebuilding it to
    flush any native/GDI accumulation over a long run."""
    sct = getattr(_tls, "sct", None)
    cnt = getattr(_tls, "sct_count", 0) + 1
    if sct is not None and cnt > _SCT_REFRESH_EVERY:
        try:
            sct.close()
        except Exception:
            pass
        sct, cnt = None, 1
    if sct is None:
        sct = _tls.sct = mss.mss()
    _tls.sct_count = cnt
    return sct


def grab_frame(monitor_index: int, mask_overlay: bool = True) -> np.ndarray:
    """Capture game monitor via mss. Returns BGR frame.

    mask_overlay (default True): blank the app's own overlay rect out of the
    frame so the automation never detects its own window (see set_overlay_mask).
    Bug-report capture passes False to grab the real, unmasked screen."""
    sct = _get_sct()
    try:
        monitors = sct.monitors
        if monitor_index >= len(monitors):
            raise RuntimeError(
                f"Monitor {monitor_index} not found. "
                f"Only {len(monitors)-1} monitor(s) available.")
        mon = monitors[monitor_index]
        shot = sct.grab(mon)
    except RuntimeError:
        raise
    except Exception:
        # mss can fail transiently (e.g. display/DC reset). Rebuild once.
        try:
            sct.close()
        except Exception:
            pass
        _tls.sct = None
        sct = _get_sct()
        monitors = sct.monitors
        if monitor_index >= len(monitors):
            raise RuntimeError(
                f"Monitor {monitor_index} not found. "
                f"Only {len(monitors)-1} monitor(s) available.")
        mon = monitors[monitor_index]
        shot = sct.grab(mon)
    if shot is None:
        raise RuntimeError(
            f"Monitor {monitor_index} returned no image. "
            f"Check if the monitor is active.")
    frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
    if mask_overlay:
        rect = _overlay_rect   # atomic read of immutable tuple
        if rect is not None:
            ox, oy, ow, oh = rect
            # Overlay rect is absolute virtual-screen px; frame origin = monitor
            # (left, top). Translate, clip to the frame, then blank to black —
            # a flat region can't match a text template.
            lx, ly = ox - mon["left"], oy - mon["top"]
            fh, fw = frame.shape[:2]
            x0, y0 = max(0, lx), max(0, ly)
            x1, y1 = min(fw, lx + ow), min(fh, ly + oh)
            if x1 > x0 and y1 > y0:
                frame[y0:y1, x0:x1] = 0
    return frame


def grab_region(left: int, top: int, width: int, height: int,
                mask_overlay: bool = True) -> np.ndarray:
    """Capture an arbitrary screen rectangle (absolute px) via mss. Returns BGR.
    Used to capture a windowed game's client area instead of the whole monitor
    (see get_client_rect). mask_overlay blanks the app's own overlay rect, same
    as grab_frame."""
    sct = _get_sct()
    region = {"left": int(left), "top": int(top),
              "width": int(width), "height": int(height)}
    try:
        shot = sct.grab(region)
    except Exception:
        try:
            sct.close()
        except Exception:
            pass
        _tls.sct = None
        sct = _get_sct()
        shot = sct.grab(region)
    if shot is None:
        raise RuntimeError("Region capture returned no image.")
    frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
    if mask_overlay:
        rect = _overlay_rect
        if rect is not None:
            ox, oy, ow, oh = rect
            lx, ly = ox - int(left), oy - int(top)
            fh, fw = frame.shape[:2]
            x0, y0 = max(0, lx), max(0, ly)
            x1, y1 = min(fw, lx + ow), min(fh, ly + oh)
            if x1 > x0 and y1 > y0:
                frame[y0:y1, x0:x1] = 0
    return frame


class _BMIH(ctypes.Structure):
    _fields_ = [("biSize", _wintypes.DWORD), ("biWidth", _wintypes.LONG),
                ("biHeight", _wintypes.LONG), ("biPlanes", _wintypes.WORD),
                ("biBitCount", _wintypes.WORD), ("biCompression", _wintypes.DWORD),
                ("biSizeImage", _wintypes.DWORD), ("biXPelsPerMeter", _wintypes.LONG),
                ("biYPelsPerMeter", _wintypes.LONG), ("biClrUsed", _wintypes.DWORD),
                ("biClrImportant", _wintypes.DWORD)]


class _BMI(ctypes.Structure):
    _fields_ = [("bmiHeader", _BMIH), ("bmiColors", _wintypes.DWORD * 3)]


def grab_window(hwnd) -> np.ndarray:
    """Capture a window's CLIENT area via PrintWindow — works even when the
    window is OCCLUDED by other windows (unlike screen-region capture). Returns
    a BGR ndarray, or None on failure.

    CAVEAT: for hardware-accelerated / DirectX games this often returns an
    all-black image (the 3D swapchain isn't rendered into the GDI DC even with
    PW_RENDERFULLCONTENT). If so, this method isn't viable and the Windows
    Graphics Capture API would be required instead. Window must not be minimized."""
    if not hwnd:
        return None
    rect = get_client_rect(hwnd)
    if not rect:
        return None
    _, _, w, h = rect
    if w <= 0 or h <= 0:
        return None
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetDC.argtypes = [ctypes.c_void_p]; user32.GetDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]; gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; gdi32.SelectObject.restype = ctypes.c_void_p
    user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]; user32.PrintWindow.restype = ctypes.c_int
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    hdc = memdc = bmp = None
    try:
        hdc = user32.GetDC(hwnd)
        memdc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        old = gdi32.SelectObject(memdc, bmp)
        _PW_CLIENTONLY = 1
        _PW_RENDERFULLCONTENT = 2
        ok = user32.PrintWindow(hwnd, memdc, _PW_CLIENTONLY | _PW_RENDERFULLCONTENT)
        bmi = _BMI()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BMIH)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h          # negative = top-down rows
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0      # BI_RGB
        buf = (ctypes.c_ubyte * (w * h * 4))()
        lines = gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        gdi32.SelectObject(memdc, old)
        if not ok or lines == 0:
            return None
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
        return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
    except Exception:
        return None
    finally:
        if bmp:
            gdi32.DeleteObject(bmp)
        if memdc:
            gdi32.DeleteDC(memdc)
        if hdc:
            user32.ReleaseDC(hwnd, hdc)


def list_monitors() -> list:
    with mss.MSS() as sct:
        return [
            {"index": i, "width": m["width"], "height": m["height"],
             "left": m["left"], "top": m["top"]}
            for i, m in enumerate(sct.monitors[1:], start=1)
        ]


def get_monitor_dims(monitor_index: int):
    with mss.MSS() as sct:
        monitors = sct.monitors
        if monitor_index >= len(monitors) or monitor_index < 1:
            # Fall back to primary monitor
            monitor_index = next(
                (i for i, m in enumerate(monitors[1:], 1)
                 if m['left'] == 0 and m['top'] == 0), 1)
        m = monitors[monitor_index]
        return m["width"], m["height"], m["left"], m["top"]


# ── Template save / load ──────────────────────────────────────

def save_template(folder: str, key: str, crop: np.ndarray,
                  screen_w: int, screen_h: int, box=None):
    """Save a BGR crop and its resolution metadata.

    box (x, y, w, h): where the crop sat on the capture screen. Stored so the
    detector can derive an anchor-aware ROI at any resolution (Stage 2), instead
    of a hand-tuned DEFAULT_ROIS entry. Optional/back-compatible: old templates
    without it fall back to DEFAULT_ROIS.
    """
    os.makedirs(folder, exist_ok=True)
    img_path  = os.path.join(folder, f"{key}.png")
    meta_path = os.path.join(folder, f"{key}.json")
    success, buf = cv2.imencode('.png', crop)
    if success:
        with open(img_path, 'wb') as f:
            f.write(buf.tobytes())
    meta = {"screen_width": screen_w, "screen_height": screen_h}
    if box is not None:
        bx, by, bw, bh = box
        meta["box"] = [int(bx), int(by), int(bw), int(bh)]
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)


def load_template(folder: str, key: str,
                  current_w: int, current_h: int,
                  grayscale: bool = True,
                  ref_folder: str = None,
                  prefer_ref: bool = False) -> tuple:
    """
    Load a template and rescale it to the current resolution (by height — game
    UI scales with vertical resolution).
    Returns (img, scale, meta) or raises FileNotFoundError. `meta` is the
    sidecar JSON (screen_width/height, and optional "box" capture geometry).

    Single-reference resolution support (Stage 1): a bundled template authored
    once at the highest resolution can serve every preset resolution by
    downscaling. `ref_folder` is that reference set's folder; the source is
    chosen as:
      • prefer_ref + ref has it  → use ref_folder (downscale to current)
      • else folder has it       → use folder (per-resolution, legacy)
      • else ref has it          → fall back to ref_folder
    Defaults (ref_folder=None, prefer_ref=False) reproduce the old behaviour
    exactly, so existing callers are unaffected.
    """
    def _has(d):
        return d and os.path.exists(os.path.join(d, f"{key}.png")) and \
            os.path.exists(os.path.join(d, f"{key}.json"))

    src = None
    if prefer_ref and _has(ref_folder):
        src = ref_folder
    elif _has(folder):
        src = folder
    elif _has(ref_folder):
        src = ref_folder
    if src is None:
        raise FileNotFoundError(f"Template '{key}' not found in {folder}")
    img_path  = os.path.join(src, f"{key}.png")
    meta_path = os.path.join(src, f"{key}.json")

    flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    with open(img_path, 'rb') as f:
        buf = np.frombuffer(f.read(), dtype=np.uint8)
    img = cv2.imdecode(buf, flag)

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    # Scale by height only: game UIs are laid out relative to vertical
    # resolution, not an average of width and height.  Averaging breaks
    # on mixed aspect ratios (e.g. a 16:9 template used on a 21:9 screen):
    # the width ratio inflates the scale and the template ends up the wrong
    # size even though the actual UI element is pixel-identical in height.
    scale = current_h / meta["screen_height"]
    if abs(scale - 1.0) > 0.02:
        nw = max(1, int(img.shape[1] * scale))
        nh = max(1, int(img.shape[0] * scale))
        img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

    return img, scale, meta


def template_exists(folder: str, key: str) -> bool:
    return (os.path.exists(os.path.join(folder, f"{key}.png")) and
            os.path.exists(os.path.join(folder, f"{key}.json")))


# ── Node save / load ──────────────────────────────────────────

def save_nodes(nodes_file: str, nodes: list,
               screen_w: int, screen_h: int):
    data = {
        "screen_width":  screen_w,
        "screen_height": screen_h,
        "nodes": [{"x_ratio": round(x / screen_w, 6),
                   "y_ratio": round(y / screen_h, 6)}
                  for x, y in nodes]
    }
    os.makedirs(os.path.dirname(nodes_file), exist_ok=True)
    with open(nodes_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


_REF_ASPECT = 16.0 / 9.0


def _content_box(screen_w: int, screen_h: int, ref: float = _REF_ASPECT):
    """Pixel rect (x, y, w, h) of a centred `ref`-aspect UI area fit (contain)
    into the screen.  Forza anchors menu UI to a centred 16:9 box rather than
    stretching it, so on non-16:9 screens the box is pillarboxed (wide screen,
    bars left/right) or letterboxed (tall screen, bars top/bottom).  On a 16:9
    screen the box equals the full screen."""
    if screen_w / max(1, screen_h) >= ref:
        box_h = float(screen_h)
        box_w = screen_h * ref
    else:
        box_w = float(screen_w)
        box_h = screen_w / ref
    box_x = (screen_w - box_w) / 2.0
    box_y = (screen_h - box_h) / 2.0
    return box_x, box_y, box_w, box_h


def load_nodes(nodes_file: str, current_w: int, current_h: int,
               aspect_fix: bool = True) -> list:
    with open(nodes_file, encoding="utf-8") as f:
        data = json.load(f)
    nodes = data["nodes"]
    src_w = data.get("screen_width", current_w)
    src_h = data.get("screen_height", current_h)

    # Naive width/height scaling is only correct when the capture and current
    # screen share an aspect ratio.  When they differ (e.g. a 16:9 preset on a
    # 21:9 ultrawide), the UI is anchored to a centred 16:9 box, not stretched
    # across the extra width — so map each node through the source's content
    # box into the current screen's content box.  This reduces to naive
    # scaling when the aspects match (verified: 5120x2160 custom capture maps
    # to itself), so it's safe to apply unconditionally for same-aspect cases.
    if not aspect_fix or src_w <= 0 or src_h <= 0:
        return [(int(n["x_ratio"] * current_w),
                 int(n["y_ratio"] * current_h)) for n in nodes]

    sx, sy, sw, sh = _content_box(src_w, src_h)
    cx, cy, cw, ch = _content_box(current_w, current_h)
    out = []
    for n in nodes:
        # node pixel within the source's centred 16:9 box -> box fraction
        cfx = (n["x_ratio"] * src_w - sx) / sw
        cfy = (n["y_ratio"] * src_h - sy) / sh
        # map that fraction onto the current screen's centred 16:9 box
        out.append((int(round(cx + cfx * cw)),
                    int(round(cy + cfy * ch))))
    return out


def nodes_exist(nodes_file: str) -> bool:
    return os.path.exists(nodes_file)


# ── Mastery grid spec (keyboard tree-nav) ───────────────────
# An ordered list of [row, col] cells in the 4x4 mastery tree, in unlock order.
# Replaces the old pixel node-click capture: navigation is WASD from the bottom-
# left start, so the spec is just the logical path (resolution-independent).

def save_grid(grid_file: str, order: list):
    """Persist the ordered list of (row, col) cells."""
    import json
    os.makedirs(os.path.dirname(grid_file), exist_ok=True)
    data = {"rows": 4, "cols": 4,
            "order": [[int(r), int(c)] for (r, c) in order]}
    with open(grid_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_grid(grid_file: str) -> list:
    """Return the ordered list of (row, col) tuples, or [] if absent/invalid."""
    import json
    try:
        with open(grid_file, encoding="utf-8") as f:
            data = json.load(f)
        return [(int(p[0]), int(p[1])) for p in data.get("order", [])]
    except Exception:
        return []


def grid_exists(grid_file: str) -> bool:
    return bool(load_grid(grid_file))


# ── Example image window ────────────────────────────────────

import queue as _queue
_example_queue = _queue.Queue()
_example_win_ref = [None]   # holds the CTkToplevel


def show_example(key: str, examples_dir: str):
    """
    Show an example image in a tkinter Toplevel window.
    Called from the main thread via after().
    """
    img_path = os.path.join(examples_dir, f'{key}.png')
    if not os.path.exists(img_path):
        return
    # Store path for main thread to pick up
    _example_queue.put(('show', key, img_path))


def close_example():
    """Signal main thread to close the example window."""
    _example_queue.put(('close', None, None))


# ── Region selection (OpenCV drag window) ─────────────────────

def select_region(frame: np.ndarray, window_title: str):
    """
    Show frame in a window, let user drag-select a region.
    Returns (x, y, w, h) in original resolution, or None if cancelled.
    """
    display_scale = 1.0
    if frame.shape[0] > 860:
        display_scale = 860 / frame.shape[0]
        display = cv2.resize(frame, None,
                             fx=display_scale, fy=display_scale)
    else:
        display = frame.copy()

    dh, dw = display.shape[:2]

    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_title, dw, dh)
    cv2.setWindowProperty(window_title, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # Bring to foreground
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 3)   # SW_MAXIMIZE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass

    roi = cv2.selectROI(window_title, display,
                        showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = roi
    if w == 0 or h == 0:
        return None
    return (int(x / display_scale), int(y / display_scale),
            int(w / display_scale), int(h / display_scale))


# ── Caps Lock capture session ─────────────────────────────────

class CaptureSession:
    """
    Listens for Caps Lock keypresses in a background thread.
    On each press: grabs a frame, opens drag-select, calls callback.

    callback(crop, frame_w, frame_h) is called on successful capture.
    """

    def __init__(self, monitor_index: int, window_title: str,
                 callback, on_cancel=None, capture_key='caps lock',
                 template_key=None, examples_dir=None):
        self.monitor_index = monitor_index
        self.window_title  = window_title
        self.callback      = callback
        self.on_cancel     = on_cancel
        self.capture_key   = capture_key
        self.template_key  = template_key
        self.examples_dir  = examples_dir
        self._stop         = threading.Event()
        self._thread       = None

    def start(self):
        import keyboard
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        try:
            close_example()
        except Exception:
            pass

    def _run(self):
        import keyboard
        triggered  = threading.Event()
        _in_capture = threading.Lock()

        def _caps_pressed():
            # Only set if not already processing a capture
            if not self._stop.is_set() and not _in_capture.locked():
                triggered.set()

        # Show example image if available
        if self.template_key and self.examples_dir:
            show_example(self.template_key, self.examples_dir)

        # Use add_hotkey (same mechanism as the F9 global toggle) so the key
        # fires system-wide even when the game window has focus.
        # on_press_key can be focus-dependent in some Windows configurations.
        cap_hook = keyboard.add_hotkey(self.capture_key, _caps_pressed, suppress=False)

        # ESC cancels at any point during waiting.
        # If we're mid-capture (_in_capture held), the selectROI / waitKey
        # paths already handle cancellation — don't double-fire on_cancel.
        def _on_esc(e):
            self._stop.set()
            if not _in_capture.locked() and self.on_cancel:
                self.on_cancel()
        esc_hook = keyboard.on_press_key('esc', _on_esc, suppress=False)

        while not self._stop.is_set():
            if triggered.wait(timeout=0.1):
                triggered.clear()
                if self._stop.is_set():
                    break
                if not _in_capture.acquire(blocking=False):
                    continue
                try:
                    time.sleep(0.15)
                    triggered.clear()

                    frame = grab_frame(self.monitor_index)
                    h, w  = frame.shape[:2]

                    roi = select_region(frame, self.window_title)
                    if roi is None:
                        self._stop.set()
                        if self.on_cancel:
                            self.on_cancel()
                    else:
                        x, y, rw, rh = roi
                        crop = frame[y:y+rh, x:x+rw]

                        cv2.imshow("Preview — ENTER to save | ESC to cancel", crop)
                        # Bring preview to foreground
                        try:
                            import ctypes as _ct
                            _hw = _ct.windll.user32.FindWindowW(None, "Preview — ENTER to save | ESC to cancel")
                            if _hw:
                                _ct.windll.user32.ShowWindow(_hw, 9)
                                _ct.windll.user32.SetForegroundWindow(_hw)
                        except Exception:
                            pass
                        key = cv2.waitKey(0) & 0xFF
                        cv2.destroyAllWindows()

                        if key in (ord('y'), ord('Y'), 13):
                            # Stop listening before handing off — prevents the
                            # loop from picking up the next CAPS LOCK press
                            # while _advance_session() is still spinning up
                            # the new session, which broke multi-capture.
                            self._stop.set()
                            # Pass the capture box (x,y,w,h) + screen size so the
                            # template can carry its own location (Stage 2 ROI).
                            self.callback(crop, w, h, x, y, rw, rh)
                        else:
                            self._stop.set()
                            if self.on_cancel:
                                self.on_cancel()
                finally:
                    triggered.clear()
                    _in_capture.release()

        try:
            keyboard.remove_hotkey(cap_hook)
        except Exception:
            pass
        try:
            keyboard.unhook(esc_hook)
        except Exception:
            pass


# ── Node click session ────────────────────────────────────────

class NodeSession:
    """
    Shows a screenshot and collects 6 mouse clicks for node positions.
    callback(nodes, screen_w, screen_h) called when all 6 are confirmed.
    """

    def __init__(self, monitor_index: int, callback, on_cancel=None,
                 capture_key='caps lock'):
        self.monitor_index = monitor_index
        self.callback      = callback
        self.on_cancel     = on_cancel
        self.capture_key   = capture_key

    def start(self):
        self._stop = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()
        try:
            close_example()
        except Exception:
            pass

    def _run(self):
        import keyboard
        # Wait for Caps Lock (or ESC/stop to cancel)
        triggered  = threading.Event()
        cancelled  = threading.Event()

        def _cap_pressed():
            triggered.set()
        def _on_esc(e):
            cancelled.set()
            triggered.set()

        # Use add_hotkey for the same reason as CaptureSession — ensures the
        # key fires system-wide regardless of which window has focus.
        cap_hook = keyboard.add_hotkey(self.capture_key, _cap_pressed, suppress=False)
        esc_hook = keyboard.on_press_key('esc', _on_esc, suppress=False)

        # Poll so stop() can also interrupt the wait
        while not triggered.is_set() and not self._stop.is_set():
            triggered.wait(timeout=0.1)

        try:
            keyboard.remove_hotkey(cap_hook)
        except Exception:
            pass
        try:
            keyboard.unhook(esc_hook)
        except Exception:
            pass

        if cancelled.is_set() or self._stop.is_set():
            if self.on_cancel:
                self.on_cancel()
            return
        time.sleep(0.1)

        frame = grab_frame(self.monitor_index)
        h, w  = frame.shape[:2]

        scale = 1.0
        if frame.shape[0] > 860:
            scale   = 860 / frame.shape[0]
            display = cv2.resize(frame, None, fx=scale, fy=scale)
        else:
            display = frame.copy()

        clicks = []

        def on_mouse(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN and len(clicks) < 6:
                clicks.append((int(x / scale), int(y / scale)))

        win = "Click 6 nodes in order | ESC to cancel"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, display.shape[1], display.shape[0])

        # Bring to foreground
        try:
            import ctypes
            hwnd = ctypes.windll.user32.FindWindowW(None, win)
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

        cv2.setMouseCallback(win, on_mouse)

        while len(clicks) < 6:
            img = display.copy()
            for i, (cx, cy) in enumerate(clicks):
                dx, dy = int(cx * scale), int(cy * scale)
                cv2.circle(img, (dx, dy), 14, (0, 255, 0), 3)
                cv2.putText(img, str(i+1), (dx-5, dy+5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(img, f"Click node {len(clicks)+1}/6",
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.9, (0, 220, 255), 2)
            cv2.imshow(win, img)
            k = cv2.waitKey(16)
            if k == 27:
                cv2.destroyAllWindows()
                if self.on_cancel:
                    self.on_cancel()
                return

        # All 6 clicked — show final and ask Y/N
        img = display.copy()
        for i, (cx, cy) in enumerate(clicks):
            dx, dy = int(cx * scale), int(cy * scale)
            cv2.circle(img, (dx, dy), 14, (0, 255, 0), 3)
            cv2.putText(img, str(i+1), (dx-5, dy+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(img, "All 6! Y=save  N=redo",
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        cv2.imshow(win, img)
        key = cv2.waitKey(0) & 0xFF
        cv2.destroyAllWindows()

        if key in (ord('y'), ord('Y'), 13):
            self.callback(clicks, w, h)
        else:  # ESC or anything else cancels
            if self.on_cancel:
                self.on_cancel()
