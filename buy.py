# ============================================================
#  automation/buy.py — Auto Buy automation logic
#  Buys a target car repeatedly from the Discover Japan → Car
#  Collection grid (for mastery-point farming).
#
#  The BUY MACRO (per loop) is unchanged from the old inline
#  version: space, down, enter, enter, enter — run on the car's
#  focus/detail view (Space = 購買 / Buy).
#
#  Optional menu-navigation (template-gated, best-effort) lets the
#  run START and END on the main menu (the chaining hand-off):
#    ENTRY  main menu → click 收藏日記 (Collection Log) → click
#           探索大師 (Discover Japan) card → Down+Enter (車輛收藏 /
#           Car Collection) → Backspace (jump to brand) → scroll to
#           the bottom of the list → click the target car tile
#           (now at a fixed bottom position) → focuses it → macro.
#    EXIT   4× Esc (back through the menus) → main menu (confirmed
#           by re-detecting 收藏日記).
#  If the 4 nav templates aren't captured, buy just runs the macro
#  where you are (the legacy behaviour) — nothing breaks.
#
#  Each nav step is detection-GATED and TIME-BOXED (abort, don't
#  hang — a wrong/stuck menu won't self-correct). Output via
#  log_cb / status_cb; stop via stop_event.
# ============================================================

import time
import threading

import config
from config import get_buy_templates
from app_lang import t as _at
from capture import (grab_frame, load_template, get_monitor_dims,
                     force_english_ime, mouse_click, mouse_scroll)
# IME-safe (dual VK+scancode) key sender shared by Delete/Buy.
from delete_cars import key_press
from detector import ScreenDetector
from gameio import GameIO


# Buy macro per loop (unchanged from the old inline implementation).
BUY_MACRO = ['space', 'down', 'enter', 'enter', 'enter']

# buy_target_car is intentionally NOT here: the target car is now reached by
# keyboard (S → Enter from the BRAT GL tile that's selected after picking
# Subaru), not template detection — the tile collided with look-alike Subaru
# tiles. So nav only needs the four screens it clicks/gates on.
NAV_KEYS = ["collection_log", "discover_japan", "car_collection", "subaru"]
_LABELS = {
    "collection_log": "buy_tpl_collection_log",
    "discover_japan": "buy_tpl_discover_japan",
    "car_collection": "buy_tpl_car_collection",
    "subaru":         "buy_tpl_subaru",
    "buy_target_car": "buy_tpl_target_car",
}

_NAV_STEP_WINDOW     = 12.0   # per-step detection window before aborting
_START_STATE_WINDOW  = 8.0    # detect the main menu (collection_log) at start
_SCROLL_NOTCHES      = 12     # generous: scroll past the bottom (list clamps)
_SCROLL_PAUSE        = 0.12   # gap between scroll notches
_TARGET_SETTLE       = 2.0    # settle after the 1-notch scroll before clicking the target car
_EXIT_ESC_COUNT      = 4      # Esc presses from the detail view → main menu
_EXIT_ESC_GAP        = 0.5    # gap between Esc presses
_EXIT_CONFIRM_WINDOW = 10.0   # detect the main menu after the Esc chain


def run(cfg: dict, stop_event: threading.Event,
        log_cb, status_cb, max_loops: int = 0,
        warn_cb=None, section_cb=None):
    """
    Auto Buy loop.
    cfg: config dict
    stop_event: set to stop
    log_cb(msg) / status_cb(msg): log line / status bar
    max_loops: stop after this many purchases (0 = unlimited)
    section_cb(msg): start a bounded log section; falls back to log_cb
    warn_cb: accepted for call-site parity; unused (nav is time-boxed).
    """
    section       = section_cb or log_cb
    lang          = cfg.get("lang", "en")
    monitor_index = cfg.get("monitor_index", 1)

    # Always read settings fresh from config.json at start.
    import config as _cfg_mod
    _fresh   = _cfg_mod.load()
    post_kw  = _fresh.get("buy_post_key_wait", 0.5)
    tpl_lang = _cfg_mod.resolve_template_lang(_fresh)

    def _thr(key):
        return _fresh.get(f"thresh_{key}", 0.60)

    io = GameIO(_fresh, log_cb)
    current_w, current_h = io.width, io.height
    mon_left, mon_top = io.cap_left, io.cap_top
    # Single built-in template set (REFERENCE_RES), auto-scaled to the monitor.
    folder   = get_buy_templates(_cfg_mod.REFERENCE_RES, tpl_lang)
    ref_folder = folder
    prefer_ref = _fresh.get('template_prefer_reference', True)
    detector = ScreenDetector(_fresh)

    def _load(key):
        img, scale, meta = load_template(folder, key, current_w, current_h,
                                         grayscale=True, ref_folder=ref_folder,
                                         prefer_ref=prefer_ref)
        box = meta.get("box")
        if box:
            detector.set_template_geometry(
                key, box, meta.get("screen_width", current_w),
                meta.get("screen_height", current_h))
        log_cb(_at("log_template_loaded", lang, key=key, scale=f"{scale:.2f}"))
        return img

    # Nav templates are best-effort: present → start/end on the main menu;
    # absent → run the macro where the user already positioned (legacy).
    nav_tpls = {}
    for key in NAV_KEYS:
        try:
            nav_tpls[key] = _load(key)
        except FileNotFoundError:
            pass
    nav_enabled = all(k in nav_tpls for k in NAV_KEYS)

    def stop():
        return stop_event.is_set()

    def wait(seconds):
        """Stop-aware sleep so F9/Stop isn't blocked by fixed waits."""
        end = time.time() + seconds
        while time.time() < end:
            if stop():
                return
            time.sleep(0.1)

    def announce(msg):
        log_cb(msg)
        status_cb(msg)

    def press(key, post_wait=None):
        io.press(key, post_wait=post_kw if post_wait is None else post_wait)

    def _detect(key, window_s):
        """TIME-BOXED detection: poll detect() up to window_s, return the
        MatchResult the instant it matches, else None."""
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return None
            try:
                r = detector.detect(io.grab(), key,
                                    nav_tpls[key], _thr(key), stable=False)
                if r.matched:
                    return r
            except Exception:
                pass
            time.sleep(0.15)
        return None

    def _nav_click(key, pre_click_wait=0.0):
        """Detect a clickable nav element (time-boxed) and click its centre.
        pre_click_wait pauses AFTER detection, BEFORE the click — lets the screen
        finish settling so the click lands on the right tile. Returns True on
        success, False if it never appears (abort) or stopped."""
        lbl = _at(_LABELS[key], lang)
        t0 = time.time()
        r = _detect(key, _NAV_STEP_WINDOW)
        secs = f"{time.time() - t0:.1f}"
        if r is None:
            if not stop():
                log_cb(_at("log_buy_nav_fail", lang, label=lbl, secs=secs))
            return False
        log_cb(_at("log_buy_nav_detected", lang, label=lbl,
                   conf=f"{r.score:.0%}, {r.source}", secs=secs))
        if pre_click_wait:
            wait(pre_click_wait)
            if stop():
                return False
        log_cb(_at("log_buy_nav_click", lang, label=lbl))
        io.click(r.location[0], r.location[1], post_kw)
        return True

    def _navigate_to_target(start_hit):
        """Main menu → Collection Log → Discover Japan → Car Collection →
        Backspace (brand) → scroll to bottom → target car focused. start_hit =
        the collection_log match already in hand. Returns True on success,
        False if a step's element never appears (abort) or stopped."""
        announce(_at("log_buy_nav_begin", lang))
        # 1. Collection Log (already detected — click it)
        lbl = _at("buy_tpl_collection_log", lang)
        log_cb(_at("log_buy_nav_click", lang, label=lbl))
        io.click(start_hit.location[0], start_hit.location[1], post_kw)
        if stop():
            return False
        # 2. Discover Japan card
        if not _nav_click("discover_japan"):
            return False
        # 3. Car Collection — detect the grid (gate), then Down + Enter
        lbl = _at("buy_tpl_car_collection", lang)
        t0 = time.time()
        r = _detect("car_collection", _NAV_STEP_WINDOW)
        secs = f"{time.time() - t0:.1f}"
        if r is None:
            if not stop():
                log_cb(_at("log_buy_nav_fail", lang, label=lbl, secs=secs))
            return False
        log_cb(_at("log_buy_nav_detected", lang, label=lbl,
                   conf=f"{r.score:.0%}, {r.source}", secs=secs))
        log_cb(_at("log_buy_nav_key", lang, keys="Down → Enter", label=lbl))
        press('down')
        if stop():
            return False
        press('enter')
        if stop():
            return False
        # 4. Backspace — switch to the manufacturer/brand view
        log_cb(_at("log_buy_backspace", lang))
        press('backspace')
        if stop():
            return False
        # 5. Scroll to the bottom of the brand view (generous; clamps at the
        #    end), so the Subaru brand tile sits at a fixed bottom position.
        log_cb(_at("log_buy_scroll", lang, n=_SCROLL_NOTCHES))
        for _ in range(_SCROLL_NOTCHES):
            if stop():
                return False
            io.scroll(-1, post_wait=_SCROLL_PAUSE)
        wait(0.3)   # let the brand view settle at the bottom
        if stop():
            return False
        # 6. Click Subaru → drops into the car-list view; the cursor reliably
        #    lands on the BRAT GL tile.
        if not _nav_click("subaru"):
            return False
        # 7. From BRAT GL the 22B-STi is one row down, so move down once and
        #    select it with Enter. Keyboard nav is reliable here — detecting the
        #    tile collided with the look-alike Subaru tiles (BRAT GL etc.), so the
        #    template detection for the target car is ditched in favour of S→Enter.
        log_cb(_at("log_buy_nav_key", lang, keys="S → Enter",
                   label=_at("buy_tpl_target_car", lang)))
        press('s')
        if stop():
            return False
        press('enter')
        if stop():
            return False
        log_cb(_at("log_buy_macro_start", lang))
        return True

    def _return_to_menu():
        """Detail view → main menu: a fixed number of Esc presses, then confirm
        the main menu (collection_log). Best-effort / time-boxed."""
        announce(_at("log_buy_exit_begin", lang))
        for i in range(_EXIT_ESC_COUNT):
            if stop():
                return
            log_cb(_at("log_buy_exit_esc", lang, i=i + 1, n=_EXIT_ESC_COUNT))
            press('escape', post_wait=_EXIT_ESC_GAP)
        if stop():
            return
        t0 = time.time()
        r = _detect("collection_log", _EXIT_CONFIRM_WINDOW)
        if r is None:
            if not stop():
                log_cb(_at("log_buy_exit_fail", lang,
                           secs=f"{time.time() - t0:.1f}"))
            return
        log_cb(_at("log_buy_at_menu", lang))

    log_cb(_at("buy_running", lang))
    # Switch the game to English input only if it isn't already (foreground
    # only — background mode would target the wrong window).
    if not io.bg and _fresh.get("auto_english_ime", True):
        force_english_ime()
        time.sleep(0.2)
    io.mute(_fresh)
    io.start_keepalive(stop, _fresh)

    # ── Optional entry navigation ──
    did_nav = False
    if nav_enabled and not stop():
        # On the main menu (collection_log visible)? Then navigate. Otherwise
        # assume the user pre-positioned on the target car (legacy) and just
        # run the macro — no exit nav in that case (unknown menu depth).
        start_hit = _detect("collection_log", _START_STATE_WINDOW)
        if start_hit is not None:
            if not _navigate_to_target(start_hit):
                io.cleanup()
                log_cb(_at("log_buy_stopped", lang))
                status_cb(_at("status_stopped", lang))
                return
            did_nav = True
    elif not nav_enabled:
        log_cb(_at("log_buy_nav_skip", lang))

    # ── Buy macro loop ──
    loop = 0
    while not stop():
        loop += 1
        section(f"-- {_at('buy_loop', lang)} #{loop}" +
                (f" / {max_loops}" if max_loops > 0 else "") + " --")
        for key in BUY_MACRO:
            if stop():
                break
            log_cb(_at('log_buy_key', lang, key=key.upper()))
            press(key)
        if max_loops > 0 and loop >= max_loops:
            log_cb(_at('log_buy_limit_reached', lang, n=max_loops))
            break

    # ── Optional exit navigation — only if we entered via nav (so we know
    #    we're on the detail view / can count the Esc chain back to the menu). ──
    if did_nav and not stop():
        _return_to_menu()

    io.cleanup()     # stop keep-alive + unmute
    log_cb(_at("log_buy_stopped", lang))
    status_cb(_at("status_stopped", lang))
