# ============================================================
#  gameio.py — Window-aware capture + input for every automation module.
#
#  ALWAYS-ON, auto-adapting (no toggle): at run start each module creates a
#  GameIO(cfg). If the game window is found by title, GameIO drives the game
#  through that window — capturing its CLIENT area (so it works whether the game
#  is windowed or borderless, and even if another window covers it) and sending
#  input via PostMessage (so it works whether the game is FOCUSED or NOT). A
#  keep-alive re-asserts "active" so the game doesn't auto-pause while unfocused.
#  If the window ISN'T found, GameIO falls back to the legacy path: whole-monitor
#  capture + SendInput to the focused window (identical to the old behaviour).
#
#  This unifies what used to be per-module input/capture code. The window
#  (PostMessage) path was validated on Forza Horizon 6; `background_input=false`
#  in config forces the legacy path everywhere as a kill-switch.
# ============================================================

import time
import threading
import ctypes
from ctypes import wintypes

import capture
from app_lang import t as _at


# ── Virtual-key map (covers every key any module presses) ─────
_VK_MAP = {
    'enter': 0x0D, 'return': 0x0D,
    'esc': 0x1B, 'escape': 0x1B,
    'space': 0x20,
    'backspace': 0x08, 'back': 0x08,
    'x': 0x58, 'y': 0x59,
    'w': 0x57, 'a': 0x41, 's': 0x53, 'd': 0x44,
    'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
}

_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP       = 0x0002
_KEYEVENTF_SCANCODE    = 0x0008
# VKs that map to an EXTENDED scancode — must set the extended flag or they
# collide with the numpad block (Down's scancode 0x50 == numpad-2).
_EXTENDED_VKS = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                           0x2D, 0x2E, 0xA3, 0xA5})

# How often the keep-alive re-asserts "active" to the game window. 0.5s is the
# sweet spot: frequent enough to keep an unfocused game from auto-pausing, but
# sparse enough not to interfere with menu input (a tighter 0.15s tick fired
# WM_ACTIVATE/SETFOCUS bursts that dropped keystrokes during menu navigation).
_KEEPALIVE_INTERVAL = 0.5

# When True, a longer-lived session (Full Auto) owns the per-app mute for the
# whole run, so per-step GameIO.mute()/unmute() are no-ops (prevents the game
# un-muting for a moment between chained functions). Set via set_mute_held().
_MUTE_HELD = False


def set_mute_held(held: bool):
    """Engage/release session-owned mute. While held, GameIO.mute()/unmute() do
    nothing — the caller is responsible for muting once and unmuting at the end."""
    global _MUTE_HELD
    _MUTE_HELD = bool(held)


# Session-cached letterbox crop. While active, the FIRST GameIO to run
# _detect_letterbox detects the crop and caches it here; every later GameIO
# reuses it instead of re-detecting on its own (arbitrary) start screen. The
# window doesn't resize mid-run, so one detection is valid for the whole session.
_UNSET = object()
_SESSION_CROP_ACTIVE = False
_SESSION_CROP = _UNSET          # _UNSET (not yet detected) | None (no crop) | (x,y,w,h)


def set_session_crop(active: bool):
    """Enable/disable the session-cached letterbox crop, resetting the cache."""
    global _SESSION_CROP_ACTIVE, _SESSION_CROP
    _SESSION_CROP_ACTIVE = bool(active)
    _SESSION_CROP = _UNSET


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 28)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


def _vk(key):
    return _VK_MAP.get(str(key).lower())


def _send_vk(key, key_up=False):
    """Foreground tap via SendInput, BOTH wVk + wScan (no SCANCODE flag) so it
    feeds the VK/message path AND the DirectInput/Raw-Input scancode path."""
    vk = _vk(key)
    if vk is None:
        return
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    flags = _KEYEVENTF_KEYUP if key_up else 0
    if vk in _EXTENDED_VKS:
        flags |= _KEYEVENTF_EXTENDEDKEY
    inp = _INPUT(type=1, union=_INPUT_UNION(
        ki=_KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _send_scancode(key, key_up=False):
    """Foreground scancode injection WITH the SCANCODE flag (wVk=0) — the
    DirectInput/Raw-Input path for gameplay (held W) and grid nav (WASD)."""
    vk = _vk(key)
    if vk is None:
        return
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
    flags = _KEYEVENTF_SCANCODE | (_KEYEVENTF_KEYUP if key_up else 0)
    if vk in _EXTENDED_VKS:
        flags |= _KEYEVENTF_EXTENDEDKEY
    inp = _INPUT(type=1, union=_INPUT_UNION(
        ki=_KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


class GameIO:
    """Per-run capture + input context. See module docstring."""

    def __init__(self, cfg, log_cb=None):
        self._log = log_cb or (lambda m: None)
        self._lang = cfg.get("lang", "en")
        self.monitor_index = cfg.get("monitor_index", 1)
        self._cap_method = cfg.get("background_capture", "window")
        self._ka_stop = threading.Event()
        self._held = {}          # key -> True once first keydown sent (repeat bit)
        self._muted_pid = None

        # Default = legacy whole-monitor path.
        mw, mh, ml, mt = capture.get_monitor_dims(self.monitor_index)
        self.width, self.height = mw, mh
        self.cap_left, self.cap_top = ml, mt
        self.hwnd = None
        self.bg = False
        self.win_capture = False
        # Letterbox/pillarbox crop (detected once at start). _crop = (x,y,w,h)
        # in client-frame px, or None. _crop_x/_crop_y offset frame-local click
        # coords back to client coords.
        self._crop = None
        self._crop_x = 0
        self._crop_y = 0

        if cfg.get("background_input", True):
            title = cfg.get("background_window_title", "Forza Horizon 6")
            hwnd = capture.find_game_window(title)
            if hwnd:
                rect = capture.get_client_rect(hwnd)
                if rect:
                    self.hwnd = hwnd
                    self.bg = True
                    self.cap_left, self.cap_top, self.width, self.height = rect
                    self.win_capture = (self._cap_method == "window")
                    self._log(_at("log_bg_input_on", self._lang))
                    self._log(_at("log_bg_window_size", self._lang,
                                  w=self.width, h=self.height))
                    if self.win_capture:
                        self._log(_at("log_bg_capture_window", self._lang))
                    if cfg.get("crop_letterbox", True):
                        self._detect_letterbox()

    # ── Capture ──────────────────────────────────────────────
    def _grab_raw(self):
        """Raw client-area / monitor frame, BEFORE any letterbox crop."""
        if self.win_capture:
            f = capture.grab_window(self.hwnd)
            if f is not None:
                return f
            # PrintWindow failed this frame → fall back to the screen region.
        if self.bg:
            r = capture.get_client_rect(self.hwnd)
            if r:
                return capture.grab_region(*r)
        return capture.grab_frame(self.monitor_index)

    def grab(self):
        """Current frame: window client area (background) or whole monitor. The
        rect is re-queried each call so MOVING the window is tracked live
        (RESIZING needs a restart — templates are scaled to the start size).
        When black bars were detected at start, the frame is cropped to the
        game content so detection sees a clean image (matches a fullscreen
        capture → template scaling + ROIs line up)."""
        f = self._grab_raw()
        if f is not None and self._crop is not None:
            cx, cy, cw, ch = self._crop
            fh, fw = f.shape[:2]
            if cy + ch <= fh and cx + cw <= fw:
                f = f[cy:cy + ch, cx:cx + cw]
        return f

    def _apply_crop(self, rect):
        """Apply a (x,y,w,h) content rect: store it + shrink width/height to the
        content size (used for template scaling). No-op on a falsy/degenerate rect."""
        if not rect:
            return False
        cx, cy, cw, ch = rect
        if cw <= 0 or ch <= 0:
            return False
        self._crop = rect
        self._crop_x, self._crop_y = cx, cy
        self.width, self.height = cw, ch
        return True

    def _detect_letterbox(self):
        """Detect black pillarbox/letterbox bars ONCE at start; store the crop
        and shrink width/height to the content size (used for template scaling).
        Bars are black on every screen, so any non-black startup frame works.
        No bars / capture failure → no crop (legacy behaviour).

        Session cache: when a session (Full Auto) holds the crop, the FIRST
        GameIO detects + caches it and every later GameIO REUSES that result —
        the window doesn't resize mid-run, so one detection is valid throughout,
        and we avoid re-detecting on an arbitrary per-step screen."""
        global _SESSION_CROP
        if _SESSION_CROP_ACTIVE and _SESSION_CROP is not _UNSET:
            self._apply_crop(_SESSION_CROP)          # reuse cached result (rect or None)
            return
        try:
            raw = self._grab_raw()
        except Exception:
            raw = None
        rect = capture.detect_content_rect(raw) if raw is not None else None
        if _SESSION_CROP_ACTIVE:
            _SESSION_CROP = rect                     # cache for the rest of the session
        if self._apply_crop(rect):
            self._log(_at("log_bg_letterbox", self._lang, w=self.width, h=self.height))

    # ── Keys ─────────────────────────────────────────────────
    def press(self, key, post_wait=0.0, scancode=False):
        """Tap a key. Background → PostMessage to the window; foreground →
        SendInput (dual VK+scan, or scancode-only for grid/gameplay keys)."""
        if self.bg:
            vk = _vk(key)
            if vk is not None:
                ext = vk in _EXTENDED_VKS
                capture.post_key(self.hwnd, vk, key_up=False, extended=ext)
                time.sleep(0.05)
                capture.post_key(self.hwnd, vk, key_up=True, extended=ext)
        elif scancode:
            _send_scancode(key, False)
            time.sleep(0.05)
            _send_scancode(key, True)
        else:
            _send_vk(key, False)
            time.sleep(0.05)
            _send_vk(key, True)
        if post_wait:
            time.sleep(post_wait)

    def hold_press(self, key):
        """One keydown for a SUSTAINED hold (re-call at ~30ms). Background uses
        PostMessage with the auto-repeat bit after the first; foreground uses a
        flagged scancode (the gameplay/driving path)."""
        if self.bg:
            vk = _vk(key)
            if vk is not None:
                capture.post_key(self.hwnd, vk, key_up=False,
                                 extended=vk in _EXTENDED_VKS,
                                 repeat=self._held.get(key, False))
                self._held[key] = True
        else:
            _send_scancode(key, False)

    def release(self, key):
        """Release a held key. Background posts the keyup straight to the window
        (no focus change needed). Foreground sends VK + scancode keyups."""
        if self.bg:
            vk = _vk(key)
            if vk is not None:
                capture.post_key(self.hwnd, vk, key_up=True,
                                 extended=vk in _EXTENDED_VKS)
        else:
            _send_vk(key, True)
            _send_scancode(key, True)
        self._held.pop(key, None)

    # ── Mouse ────────────────────────────────────────────────
    def click(self, fx, fy, post_wait=0.5):
        """Left-click at FRAME-LOCAL (fx, fy) (i.e. MatchResult.location). In
        window-capture mode the frame IS the client area, so we post client
        coords directly (independent of the window's screen position)."""
        # Record the click (in detection-frame coords) for the debug overlay /
        # F12 report — fx,fy match the frame the detector draws on. Best-effort.
        try:
            import detector as _det
            _det.record_click(int(fx), int(fy))
        except Exception:
            pass
        # fx,fy are in the (possibly cropped) frame; add the crop origin back to
        # land on the real client pixel.
        cx, cy = self._crop_x, self._crop_y
        if self.bg and self.win_capture:
            capture.post_client_click(self.hwnd, int(fx) + cx, int(fy) + cy, post_wait)
        elif self.bg:
            r = capture.get_client_rect(self.hwnd) or \
                (self.cap_left, self.cap_top, self.width, self.height)
            capture.post_click(self.hwnd, int(fx) + cx + r[0],
                               int(fy) + cy + r[1], post_wait)
        else:
            capture.mouse_click(fx, fy, self.cap_left, self.cap_top, post_wait)

    def scroll(self, notches, post_wait=0.1):
        if self.bg:
            capture.post_scroll(self.hwnd, notches, post_wait)
        else:
            capture.mouse_scroll(notches, post_wait)

    # ── Keep-alive / mute / cleanup ──────────────────────────
    def start_keepalive(self, stop_cb, cfg):
        """Re-assert 'active' to the window so it doesn't auto-pause while
        unfocused. No-op in the legacy (foreground) path or if disabled."""
        if not self.bg or not cfg.get("background_fake_focus", True):
            return
        self._log(_at("log_bg_keep_active", self._lang))
        def _loop():
            while not self._ka_stop.is_set() and not stop_cb():
                capture.set_window_active(self.hwnd)
                time.sleep(_KEEPALIVE_INTERVAL)
        threading.Thread(target=_loop, daemon=True).start()

    def stop_keepalive(self):
        self._ka_stop.set()

    def mute(self, cfg):
        # When an outer session holds the mute (e.g. Full Auto mutes once for the
        # whole run), per-step GameIOs must NOT mute/unmute — otherwise the game
        # briefly un-mutes between steps. The session owns mute/unmute itself.
        if _MUTE_HELD:
            return False
        if cfg.get("mute_game", False) and self.hwnd:
            pid = capture.get_window_pid(self.hwnd)
            if pid and capture.set_process_muted(pid, True):
                self._muted_pid = pid
                self._log(_at("log_game_muted", self._lang))
                return True
        return False

    def unmute(self):
        if _MUTE_HELD:
            return                      # session owns the mute — don't release it
        if self._muted_pid:
            capture.set_process_muted(self._muted_pid, False)
            self._muted_pid = None

    def cleanup(self):
        """Stop keep-alive and unmute — call once in the run's finally/cleanup."""
        self.stop_keepalive()
        self.unmute()
