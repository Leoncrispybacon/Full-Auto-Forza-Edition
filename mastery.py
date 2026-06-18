# ============================================================
#  automation/mastery.py — Full Mastery automation logic
#  Snake navigation: 12 cars in 3x4 grid, no detection needed
#  All output via log_cb / status_cb instead of print()
# ============================================================

import time
import threading
import ctypes
from ctypes import wintypes
import pydirectinput

from app_lang import t as _at
import config
from config import get_mastery_grid_file
from capture import load_grid, get_monitor_dims, force_english_ime
from gameio import GameIO

# The mastery tree is a 4x4 grid; the in-game cursor always starts bottom-left.
# We navigate it with WASD (one cell per press) + Enter to unlock — no mouse, so
# it's fully background-safe (see grid_widget.py for the picker UI).
_GRID_ROWS, _GRID_COLS = 4, 4
_GRID_START = (_GRID_ROWS - 1, 0)   # bottom-left
# Grid-nav pacing. The post-Enter unlock settle (pause after unlocking a node,
# before moving to the next) is Settings-tunable — weaker hardware needs the
# unlock to register before the cursor moves on; default 1.25s, adjustable 1–2s
# via mastery_grid_unlock_wait. The WASD move interval stays fixed.
_GRID_MOVE_WAIT   = 0.25
_GRID_UNLOCK_WAIT = 1.25   # default for mastery_grid_unlock_wait




_VK_MAP = {
    'enter':  0x0D, 'return': 0x0D,
    'esc':    0x1B, 'escape': 0x1B,
    'x':      0x58,
    # Arrows (keys mode): in _EXTENDED_VKS, so _send_vk sets
    # KEYEVENTF_EXTENDEDKEY — without it Down collides with numpad-2.
    'up':     0x26, 'down':   0x28,
}

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 28)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]

_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP       = 0x0002
_EXTENDED_VKS = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                           0x2D, 0x2E, 0xA3, 0xA5})

def _send_vk(key_name, key_up=False):
    vk = _VK_MAP.get(key_name.lower())
    if vk is None:
        return
    # Send BOTH the virtual key (wVk) and the hardware scancode (wScan) so the
    # game receives input whether it reads the Windows message / VK path
    # (WM_KEYDOWN / GetAsyncKeyState) or the DirectInput / Raw Input scancode
    # path. Scancode-only (wVk=0) regressed VK-path games; VK-only (wScan=0)
    # leaves DirectInput games with scancode 0. Both populated is the most
    # compatible. CJK IME is handled by capture.force_english_ime() at run start.
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
    flags = _KEYEVENTF_KEYUP if key_up else 0
    if vk in _EXTENDED_VKS:
        flags |= _KEYEVENTF_EXTENDEDKEY
    inp = _INPUT(type=1, union=_INPUT_UNION(
        ki=_KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags,
                       time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

def _key_press(key, post_wait=1.2):
    _send_vk(key, key_up=False)
    time.sleep(0.05)
    _send_vk(key, key_up=True)
    time.sleep(post_wait)


def _mouse_click(x, y, mon_left=0, mon_top=0, post_wait=0.8):
    ctypes.windll.user32.SetCursorPos(x + mon_left, y + mon_top)
    time.sleep(0.1)

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class _MINPUT_UNION(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT), ("_pad", ctypes.c_byte * 28)]

    class _MINPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", _MINPUT_UNION)]

    for flag in (0x0002, 0x0004):
        inp = _MINPUT(type=0, union=_MINPUT_UNION(mi=_MOUSEINPUT(
            dx=0, dy=0, mouseData=0, dwFlags=flag,
            time=0, dwExtraInfo=None)))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_MINPUT))
        time.sleep(0.05)
    time.sleep(post_wait)


# My Cars garage grid: rows per column. The garage fills COLUMN-MAJOR,
# TOP→BOTTOM (col 1 rows 1,2,3; col 2 rows 1,2,3; …), confirmed in-game. We
# walk a contiguous block of cars in that same top→bottom order — NOT a
# boustrophedon snake: with a partial first/last column, alternating direction
# would enter a partial column from the wrong end and hit non-target cars.
_GARAGE_ROWS = 3


def _cell_at(first_row: int, index: int):
    """(row, col) of the index-th car (0-based) in a top→bottom column-major
    fill that starts at `first_row` (1-based) of column 0. Columns after the
    first always start at row 1."""
    first_col_count = _GARAGE_ROWS - first_row + 1
    if index < first_col_count:
        return (first_row + index, 0)
    rem = index - first_col_count
    return (1 + rem % _GARAGE_ROWS, 1 + rem // _GARAGE_ROWS)


def _moves_between(prev, cur) -> list:
    """WASD moves from prev (row,col) to cur for the top→bottom traversal:
    down within a column (S), or — crossing to the next column — Right then
    Up back to the top row (the user-confirmed inter-column move: from the
    bottom of a column, D then W×2 to the top of the next)."""
    pr, pc = prev
    r, c = cur
    if c == pc:
        return ['s'] * (r - pr)                      # down within the column
    return ['d'] * (c - pc) + ['w'] * (pr - r)       # right, then up to the top



# ── Mastery automation (keyboard-driven) ─────────────────────
# Blind timed key presses — NO screen detection. The menu layout is fixed, so
# each step is a known key sequence + wait; no templates are loaded and the red
# "not detected" warning can't occur. Only the 6 mastery-node positions remain
# coordinate-driven (mouse clicks). This is the ONLY mastery mode (the old
# detection flow was removed).
#
# Step waits are FIXED constants (no UI option, baked from tuning) EXCEPT the
# cutscene wait, which is user-raisable via the mastery_cutscene_wait Setting:
#   _POST_KEY_WAIT          menu-step transitions (action-menu Enter, ESC×2, X/Enter)
#   _POST_CUTSCENE_ESC_WAIT step 4: gap after the post-cutscene ESC before Down
#   _KEYS_CUTSCENE_WAIT     step 4: default cutscene wait (overridable in Settings)
#   _KEYS_SCREEN_WAIT       step 7: wait for the Car Mastery screen before clicking
#   _TAP_WAIT               gap between repeated Down/Up cursor taps within a menu
_POST_KEY_WAIT          = 1.25
_POST_CUTSCENE_ESC_WAIT = 1.75
_KEYS_CUTSCENE_WAIT     = 11.0
_KEYS_SCREEN_WAIT       = 1.5
_TAP_WAIT               = 0.25   # matches grid move rate; 0.1 dropped taps on slow PCs


def run(cfg: dict, stop_event: threading.Event,
        log_cb, status_cb, max_cars: int = 0, warn_cb=None, section_cb=None,
        grid_file: str = None, end_at_mycars: bool = False,
        start_loop: int = None):
    # warn_cb is accepted for call-site compatibility but unused — this flow
    # never detects, so there's no "not detected" warning to raise.
    # grid_file: which mastery-tree path spec to use. None → the Mastery tab's
    # own spec; Full Auto passes its separate spec.
    # end_at_mycars: chained-into-sell mode. On the FINAL car, stop right after
    # entering My Cars (step 10) and SKIP step 11's X-sort — the Full Auto sell
    # step starts by riding the non-target car, so the sort would only reposition
    # the cursor and is redundant before the sell re-sort. Standalone = False.
    # start_loop: which garage row the FIRST car is on (1-3). None → use the
    # standalone mastery_start_loop setting. Full Auto passes 1 because its
    # positioning nav always lands on the newest car at the top-left (row 1),
    # so the standalone setting must NOT leak in (it would offset the snake and
    # trigger the column-transition D one car early).
    section       = section_cb or log_cb
    lang          = cfg.get("lang", "en")
    monitor_index = cfg.get("monitor_index", 1)

    # Always read settings fresh from config.json at start.
    import config as _cfg_mod
    _fresh = _cfg_mod.load()
    post_kw    = _POST_KEY_WAIT          # fixed (menu-step transitions)
    if start_loop is None:
        start_loop = _fresh.get("mastery_start_loop", 1)
    start_loop = max(1, min(3, int(start_loop)))
    # Step waits — fixed constants (see top of section), except the cutscene
    # wait which is user-raisable (default 11, floor 11) via Settings.
    cut_wait    = max(_KEYS_CUTSCENE_WAIT,
                      float(_fresh.get("mastery_cutscene_wait", _KEYS_CUTSCENE_WAIT)))
    screen_wait = _KEYS_SCREEN_WAIT
    # Menu cursor tap delay (Up/Down) — Settings-tunable (default 0.25, slider
    # 0.1–0.5s), shared with Delete Cars. Higher helps weak hardware register taps.
    tap_wait    = max(0.1, min(0.5, float(_fresh.get("menu_tap_wait", _TAP_WAIT))))
    # Grid node-unlock settle (after Enter, before the next node) — Settings-
    # tunable for weaker hardware (default 1.25, slider 1–2s).
    grid_unlock_wait = max(0.25,
                           float(_fresh.get("mastery_grid_unlock_wait",
                                            _GRID_UNLOCK_WAIT)))

    io = GameIO(_fresh, log_cb)
    current_w, current_h = io.width, io.height
    mon_left, mon_top = io.cap_left, io.cap_top

    # The mastery-tree unlock path (ordered 4x4 cells) is the only config this
    # mode needs — navigated by keyboard, not clicked. Resolution-independent.
    tpl_lang   = _cfg_mod.resolve_template_lang(_fresh)
    gfile      = grid_file or get_mastery_grid_file(tpl_lang)
    grid_order = load_grid(gfile)
    if not grid_order:
        log_cb(_at("log_grid_missing", lang))
        status_cb(_at("status_setup_incomplete", lang))
        return

    def stop():
        return stop_event.is_set()

    def wait(seconds):
        """Stop-aware sleep so F9/Stop isn't blocked by the long fixed waits."""
        end = time.time() + seconds
        while time.time() < end:
            if stop():
                return
            time.sleep(0.1)

    def taps(key, n):
        """n quick presses of a menu-cursor key (Down/Up)."""
        for _ in range(n):
            if stop():
                return
            io.press(key, post_wait=tap_wait)

    def announce(msg):
        """Log a step AND reflect it in the status bar / overlay. Keys mode has
        long gaps between log lines, so without per-step status the bar/overlay
        froze on the first message — this keeps them tracking the live step."""
        log_cb(msg)
        status_cb(msg)

    if max_cars > 0:
        log_cb(_at("log_mastery_started_count", lang, n=max_cars))
    else:
        log_cb(_at("log_mastery_started", lang))
    # Switch the game to English input only if it isn't already (see
    # capture.force_english_ime). Disable with auto_english_ime=false.
    if not io.bg and _fresh.get("auto_english_ime", True):
        force_english_ime()
        time.sleep(0.2)
    io.mute(_fresh)
    io.start_keepalive(stop, _fresh)

    car_num    = 0

    while not stop():
        car_num    += 1
        is_first   = (car_num == 1)

        # ── 1. Navigate to next car (top→bottom column-major) ──
        # The first car needs no nav (we start positioned on it). Otherwise emit
        # the moves from the previous car's grid cell to this one. start_loop is
        # the first car's row; Full Auto forces 1 (newest car, top-left).
        idx = car_num - 1
        nav_keys = ([] if is_first
                    else _moves_between(_cell_at(start_loop, idx - 1),
                                        _cell_at(start_loop, idx)))
        section(_at("log_car", lang, n=car_num) +
                (f" / {max_cars}" if max_cars > 0 else ""))

        if nav_keys:
            announce(_at("log_navigating", lang,
                         keys=' '.join(k.upper() for k in nav_keys)))
            for key in nav_keys:
                io.press(key, scancode=True)
                time.sleep(0.4)
            time.sleep(0.3)
        else:
            announce(_at("log_loop1_start", lang, row=start_loop))

        # ── 2. Enter → open action menu ───────────────────────
        announce(_at("log_open_action_menu", lang))
        io.press('enter', post_wait=post_kw)
        if stop(): break

        # ── 3. Enter → Ride This Car ──────────────────────────
        announce(_at("log_mkeys_ride", lang))
        io.press('enter', post_wait=0.0)

        # ── 4. Timed cutscene skip → ESC ──────────────────────
        announce(_at("log_mkeys_cutscene", lang))
        wait(cut_wait)
        if stop(): break
        io.press('esc', post_wait=_POST_CUTSCENE_ESC_WAIT)

        # ── 5. Down ×1 + Enter → Upgrade & Tuning ─────────────
        announce(_at("log_mkeys_upgrade", lang))
        taps('down', 1)
        if stop(): break
        io.press('enter', post_wait=post_kw)

        # ── 6. Down ×7 + Enter → Car Mastery ──────────────────
        announce(_at("log_mkeys_mastery", lang))
        taps('down', 7)
        if stop(): break
        io.press('enter', post_wait=0.0)

        # ── 7. Wait for the Mastery screen to load ────────────
        announce(_at("log_mkeys_wait_mastery", lang))
        wait(screen_wait)
        if stop(): break

        # ── 8. Unlock nodes via keyboard (WASD from bottom-left + Enter) ──
        # The cursor starts bottom-left; for each cell in the saved path we press
        # the single W/A/S/D move to reach it (consecutive cells are adjacent),
        # then Enter to unlock. Scancode path — same as the snake nav, and
        # background-safe (no mouse). Pacing: _GRID_MOVE_WAIT after each move
        # (incl. move→Enter), grid_unlock_wait after Enter before the next node.
        announce(_at("log_grid_unlock", lang, n=len(grid_order)))
        cur = _GRID_START
        for i, (gr, gc) in enumerate(grid_order, start=1):
            if stop(): break
            keys = []
            dr, dc = gr - cur[0], gc - cur[1]
            keys += ['w'] * (-dr) if dr < 0 else ['s'] * dr
            keys += ['a'] * (-dc) if dc < 0 else ['d'] * dc
            log_cb(_at("log_grid_step", lang, i=i, n=len(grid_order),
                       keys=' '.join(k.upper() for k in keys + ['enter'])))
            for k in keys:
                if stop(): break
                io.press(k, scancode=True, post_wait=_GRID_MOVE_WAIT)
            if stop(): break
            io.press('enter', post_wait=grid_unlock_wait)   # unlock this node
            cur = (gr, gc)
        if stop(): break

        # ── 9. ESC ×2 to exit ─────────────────────────────────
        announce(_at("log_esc_back", lang))
        io.press('esc', post_wait=post_kw)
        io.press('esc', post_wait=post_kw)
        if stop(): break

        # ── 10. Up ×1 + Enter → My Cars ───────────────────────
        announce(_at("log_mkeys_mycars", lang))
        taps('up', 1)
        if stop(): break
        io.press('enter', post_wait=post_kw)

        is_last = max_cars > 0 and car_num >= max_cars
        # Chained-into-sell: the final car stops here in My Cars (unsorted). The
        # sell step rides the non-target car first, then re-sorts itself, so we
        # skip step 11 (it would only reposition the cursor) and break.
        if is_last and end_at_mycars:
            log_cb(_at("log_mastery_limit_reached", lang, n=max_cars))
            break

        # ── 11. X + Down ×6 + Enter → sort by Recently Added ──
        announce(_at("log_mkeys_sort", lang))
        io.press('x', post_wait=post_kw)
        taps('down', 6)
        if stop(): break
        io.press('enter', post_wait=post_kw)

        if is_last:
            log_cb(_at("log_mastery_limit_reached", lang, n=max_cars))
            break

    io.cleanup()
    log_cb(_at("log_mastery_stopped", lang))
    status_cb(_at("status_stopped", lang))
