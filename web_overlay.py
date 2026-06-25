"""
web_overlay.py — the status overlay as a second, always-on-top pywebview window
(webui/overlay.html) that floats over the game.

Replaces the old Tk overlay so the design (FAFE Overlay Variants.dc.html) renders
1:1 in the same web stack as the main app. Kept from the Tk version:
  • capture.set_overlay_mask(rect) → the overlay's own screen rect is blanked from
    detection frames so the bot never matches its own window
Frameless, opaque, FIXED size (the card is a full-height flex column: header /
status / footer pinned, the log region clips its oldest lines). Dragging is our
own implementation (pywebview's easy_drag is broken in this WebView2 build).
Activated once on show so WebView2 routes input to it (a never-activated window is
dead to clicks/drags); shown without grabbing focus otherwise.

Lifecycle: the window is CREATED ONCE before webview.start() (hidden if the
overlay is off) and toggled with show()/hide(). Creating a second window AFTER
start from a worker thread builds the window object (DevTools even opens) but the
Windows/EdgeChromium backend never renders it — show/hide on a pre-created window
is the reliable path.
"""
import ctypes
import json
import threading
import time

import webview

import capture

_TITLE = "FAFE Overlay"
# Initial size is computed from the screen (see _screen_size) so it stays a small
# corner card on any resolution. These are the clamps.
_MIN_WIDTH = 240
_MIN_HEIGHT = 160
_MAX_WIDTH = 340
_MAX_HEIGHT = 300


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _DragApi:
    """js_api for the overlay window — pywebview's easy_drag doesn't work in this
    WebView2 build, so overlay.html drives dragging through these two calls."""
    def __init__(self, owner):
        self._owner = owner

    def drag_begin(self):
        return self._owner._drag_begin()

    def drag_end(self):
        return self._owner._drag_end()

    def select_func(self, key):
        return self._owner._select_func(key)


class WebOverlay:
    def __init__(self, html_path, on_move=None, on_func=None, log=None):
        self._html = html_path
        self._on_move = on_move
        self._on_func = on_func
        self._log = log or (lambda *_: None)
        self._win = None
        self._loaded = False
        self._visible = False
        self._last = {}
        self._pos = (60, 60)
        self._dragging = False
        self._drag_off = (0, 0)

    def is_visible(self):
        return self._visible

    # ── create (once, before webview.start) ──────────────────
    def _screen_size(self):
        """A small overlay sized to the PHYSICAL screen — ~17% wide, ~26% tall,
        clamped — so it's a corner card on a 4K monitor AND on a small handheld,
        instead of a fixed pixel size that's tiny on one and huge on another."""
        sw, sh = 1920, 1080
        try:
            u = ctypes.windll.user32
            sw, sh = int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
        except Exception:
            pass
        w = max(_MIN_WIDTH, min(_MAX_WIDTH, round(sw * 0.17)))
        h = max(_MIN_HEIGHT, min(_MAX_HEIGHT, round(sh * 0.26)))
        return (int(w), int(h))

    def create(self, x=60, y=60, visible=False):
        if self._win is not None:
            return
        self._pos = (int(x), int(y))
        self._visible = bool(visible)
        self._size = self._screen_size()
        w, h = self._size
        self._win = webview.create_window(
            _TITLE, self._html, js_api=_DragApi(self),
            frameless=True, easy_drag=False, on_top=True,
            width=w, height=h, x=int(x), y=int(y),
            min_size=(_MIN_WIDTH, _MIN_HEIGHT),
            background_color="#0B0F17", resizable=True, hidden=not visible)
        self._win.events.loaded += self._on_loaded
        try:
            self._win.events.moved += self._on_moved
        except Exception:
            pass
        try:
            self._win.events.resized += self._on_resized
        except Exception:
            pass

    # ── toggle ───────────────────────────────────────────────
    def show(self, x=None, y=None):
        if self._win is None:
            return
        if x is not None and y is not None:
            self._pos = (int(x), int(y))
        try:
            self._win.show()
        except Exception:
            pass
        self._visible = True
        self._force_onscreen()      # pywebview show()/move() is unreliable here
        if self._loaded:
            self._paint(self._last)
            self._mask_soon()

    def hide(self):
        self._visible = False
        capture.clear_overlay_mask()
        if self._win is not None:
            try:
                self._win.hide()
            except Exception:
                pass

    def destroy(self):
        """Tear the overlay window down for good (app exit). Until this window is
        destroyed, webview.start() won't return — so closing the main window alone
        leaves this one (and its WebView2 process) alive."""
        self._visible = False
        self._dragging = False
        capture.clear_overlay_mask()
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None

    # ── events ───────────────────────────────────────────────
    def _hwnd(self):
        try:
            u = ctypes.windll.user32
            u.FindWindowW.restype = ctypes.c_void_p   # don't truncate the 64-bit HWND
            return u.FindWindowW(None, _TITLE)
        except Exception:
            return 0

    def _force_onscreen(self):
        """Force the overlay to its saved position, topmost, visible — and ACTIVATE
        it once. WebView2 doesn't route mouse/pointer input to a window that has
        never been activated, so a hidden→shown-without-activation window renders
        but is dead to clicks/drags. We activate on show (harmless — the user only
        toggles the overlay during setup, not mid-run); during a run update() never
        re-activates it. Also bypasses pywebview's flaky show()/move() on a
        hidden-created EdgeChromium window (rendered off-screen / behind)."""
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            u = ctypes.windll.user32
            u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            HWND_TOPMOST = ctypes.c_void_p(-1)
            SWP_SHOWWINDOW = 0x0040
            x, y = self._pos
            w, h = getattr(self, "_size", (_MIN_WIDTH, _MIN_HEIGHT))
            # Also SET the size (physical px) — guarantees the small size even if
            # pywebview's create-size is mis-scaled on a high-DPI handheld.
            u.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), int(w), int(h),
                           SWP_SHOWWINDOW)   # no NOACTIVATE → wakes WebView2 input
            u.SetForegroundWindow(ctypes.c_void_p(hwnd))
        except Exception:
            pass

    # ── dragging (own implementation; easy_drag is broken here) ──
    def _drag_begin(self):
        """Record the grab offset and start following the cursor. The follow loop
        runs on a worker thread and stops on its own when the mouse button is
        released, so a missed pointerup can't leave it stuck."""
        hwnd = self._hwnd()
        if not hwnd:
            return False
        try:
            pt = _POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            r = self._rect()
            if not r:
                return False
            self._drag_off = (pt.x - r[0], pt.y - r[1])
        except Exception:
            return False
        if not self._dragging:
            self._dragging = True
            threading.Thread(target=self._drag_loop, daemon=True).start()
        return True

    def _drag_end(self):
        self._dragging = False
        return True

    def _select_func(self, key):
        """Overlay dropdown picked a function → tell the main app to switch to it."""
        if self._on_func:
            try:
                self._on_func(key)
            except Exception:
                pass
        return True

    def _drag_loop(self):
        u = ctypes.windll.user32
        VK_LBUTTON = 0x01
        try:
            while self._dragging and (u.GetAsyncKeyState(VK_LBUTTON) & 0x8000):
                pt = _POINT()
                u.GetCursorPos(ctypes.byref(pt))
                self._pos = (pt.x - self._drag_off[0], pt.y - self._drag_off[1])
                self._move(*self._pos)
                time.sleep(0.008)
        except Exception:
            pass
        self._dragging = False
        rect = self._rect()
        if rect:
            capture.set_overlay_mask(*rect)
            if self._on_move:
                try:
                    self._on_move(rect[0], rect[1])
                except Exception:
                    pass

    def _move(self, x, y):
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            u = ctypes.windll.user32
            u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            HWND_TOPMOST = ctypes.c_void_p(-1)
            SWP_NOSIZE, SWP_NOACTIVATE = 0x0001, 0x0010
            u.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), 0, 0,
                           SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

    def _on_loaded(self):
        self._loaded = True
        # NOTE: we deliberately do NOT set WS_EX_NOACTIVATE. It stops the window
        # ever activating, which means WebView2 never routes mouse/pointer input
        # to the page — the overlay becomes un-draggable / un-clickable. Instead
        # the window is shown with SWP_NOACTIVATE (appears without stealing focus)
        # but stays activatable, so the user can drag it. Focus-steal during a run
        # isn't an issue: background mode uses PostMessage (focus-independent) and
        # the keep-alive re-asserts the game as active.
        self._enable_resize()       # frameless windows need WS_THICKFRAME to resize
        self._paint(self._last)
        if self._visible:
            self._force_onscreen()
            self._mask_soon()

    def _on_resized(self, *args):
        """User dragged a window edge → re-blank the (now different) overlay rect
        from detection frames and report the move so the position stays saved."""
        if not self._visible:
            return
        self._apply_mask()
        rect = self._rect()
        if rect and self._on_move:
            try:
                self._on_move(rect[0], rect[1])
            except Exception:
                pass

    def _on_moved(self, *args):
        if not self._visible:
            return
        rect = self._rect()
        if rect:
            capture.set_overlay_mask(*rect)
            if self._on_move:
                try:
                    self._on_move(rect[0], rect[1])
                except Exception:
                    pass

    # ── state push ───────────────────────────────────────────
    def update(self, data):
        self._last = dict(data)
        if self._win is not None and self._loaded and self._visible:
            self._paint(self._last)
            self._apply_mask()

    def _paint(self, data):
        if not data:
            return
        try:
            self._win.evaluate_js("ovUpdate(" + json.dumps(data) + ")")
        except Exception:
            pass

    # ── sizing + self-mask ───────────────────────────────────
    def _rect(self):
        try:
            hwnd = self._hwnd()
            if not hwnd:
                return None
            r = _RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        except Exception:
            return None

    def _enable_resize(self):
        """The window is frameless (FormBorderStyle.None), which is NOT resizable on
        its own — add WS_THICKFRAME so the OS provides sizing borders (no title bar).
        MinimumSize (min_size) stops the running component from being shrunk away;
        the log fills whatever space is left and vanishes at the minimum height."""
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            u = ctypes.windll.user32
            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            u.GetWindowLongPtrW.restype = ctypes.c_void_p
            u.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            u.SetWindowLongPtrW.restype = ctypes.c_void_p
            u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            style = int(u.GetWindowLongPtrW(hwnd, GWL_STYLE) or 0)
            u.SetWindowLongPtrW(hwnd, GWL_STYLE,
                                ctypes.c_void_p(style | WS_THICKFRAME))
            u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x0002, 0x0001, 0x0004, 0x0020
            u.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                           SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    def _mask_soon(self):
        """Blank the overlay's own rect now and again after render settles. (The
        window is user-resizable now, so we no longer fit it to content height.)"""
        self._apply_mask()
        for delay in (0.3, 0.8):
            threading.Timer(delay, self._apply_mask).start()

    def _apply_mask(self):
        """Blank the overlay's own screen rect from detection frames."""
        if not self._visible:
            return
        rect = self._rect()
        if rect:
            capture.set_overlay_mask(*rect)
