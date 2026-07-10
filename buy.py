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
import logfmt
import navutil
import recovery
from config import get_buy_templates
from app_lang import t as _at
from capture import (grab_frame, load_template, get_monitor_dims,
                     force_english_ime, mouse_click, mouse_scroll)
# IME-safe (dual VK+scancode) key sender shared by Delete/Buy.
from delete_cars import key_press
from detector import ScreenDetector
from gameio import GameIO


# Buy macro per loop (blind-fallback path, used when the confirmation gate
# templates aren't captured — unchanged from the old inline implementation).
BUY_MACRO = ['space', 'down', 'enter', 'enter', 'enter']

# Gated path: the keys that bring up the "Buy Car" confirmation popup (Space=Buy,
# Down=select the correct one of the two buy options, Enter+Enter=confirm). The
# popup is then dismissed with a single Enter (user-confirmed timing). On a miss
# (a dropped key — most often Space) Esc reliably backs out of any buy sub-menu
# to the car detail view, so the retry always restarts from a known screen.
BUY_INIT          = ['space', 'down', 'enter', 'enter']
# buy_detail_22b (the target car's identity template) doubles as the detail-view
# anchor: it gates the confirmed/retry loop AND is the safe-to-retry re-anchor
# after an Esc. Per-route by design — each buy target (22b / gts_acr / mad_mike)
# uses its OWN identity template, so there's no generic buy_detail anymore.
GATE_KEYS         = ["buy_confirm", "buy_detail_22b"]
TARGET_DETAIL_KEYS = ("buy_detail_22b",)
_CONFIRM_WINDOW   = 4.0   # wait for the "Buy Car" popup after BUY_INIT
_RECOVER_WINDOW   = 3.0   # wait for the detail-view anchor after an Esc
_MAX_BUY_ATTEMPTS = 3     # consecutive misses on one car before aborting

# buy_target_car is intentionally NOT here: the target car is now reached by
# keyboard (S → Enter from the BRAT GL tile that's selected after picking
# Subaru), not template detection — the tile collided with look-alike Subaru
# tiles. So nav only needs the four screens it clicks/gates on.
NAV_KEYS = ["collection_log", "discover_japan", "car_collection", "subaru"]
_RECOVERY_SAFETY_ANCHOR_KEYS = ("anna", "collection_log")
_LABELS = {
    "collection_log": "buy_tpl_collection_log",
    "discover_japan": "buy_tpl_discover_japan",
    "car_collection": "buy_tpl_car_collection",
    "subaru":         "buy_tpl_subaru",
    "buy_target_car": "buy_tpl_target_car",
    "buy_detail_22b": "buy_tpl_detail_22b",
}

_NAV_STEP_WINDOW     = 12.0   # per-step detection window before aborting
_START_STATE_WINDOW  = 8.0    # detect the main menu (collection_log) at start
_SCROLL_NOTCHES      = 12     # generous: scroll past the bottom (list clamps)
_SCROLL_PAUSE        = 0.12   # gap between scroll notches
_TARGET_SETTLE       = 2.0    # settle after the 1-notch scroll before clicking the target car
_EXIT_ESC_COUNT      = 4      # Esc presses from the detail view → main menu
_EXIT_ESC_GAP        = 0.5    # gap between Esc presses
_EXIT_CONFIRM_WINDOW = 10.0   # detect the main menu after the Esc chain


def _load_recovery_safety_templates(detector, cfg, tpl_lang, width, height):
    return recovery.load_recovery_safety_templates(
        detector, cfg, tpl_lang, width, height)


def _recover_to_main_menu_from_safety_anchor(anchor, press_escape, wait,
                                             detect_anchor=None):
    return recovery.recover_to_main_menu_from_safety_anchor(
        anchor, press_escape, wait, detect_anchor)


def run(cfg: dict, stop_event: threading.Event,
        log_cb, status_cb, max_loops: int = 0,
        warn_cb=None, section_cb=None, require_nav: bool = False,
        target_nav=None, progress_cb=None, pause_event: threading.Event | None = None):
    """
    Auto Buy loop.
    cfg: config dict
    stop_event: set to stop
    log_cb(msg) / status_cb(msg): log line / status bar
    max_loops: stop after this many purchases (0 = unlimited)
    section_cb(msg): start a bounded log section; falls back to log_cb
    warn_cb: accepted for call-site parity; unused (nav is time-boxed).
    require_nav: Full Auto mode — buy MUST start by navigating from the main menu
        (collection_log). The legacy "assume pre-positioned, run the macro only"
        fallback is disabled; not finding the main menu aborts (returns False) so
        the chain doesn't fire the buy macro on an unknown screen.
    target_nav: optional callback that REPLACES the default Subaru→22B brand/target
        selection (the part AFTER the shared menu nav + Backspace). Called as
        target_nav(io, detector, press, wait, log_cb, stop, post_kw) and must leave
        the target car FOCUSED on its detail view, returning True on success / False
        to abort. None → the built-in Subaru→22B path. The caller supplies any
        target-specific templates (this keeps brand/car specifics out of buy.py).
    Returns True on normal completion, False if it couldn't start (require_nav).
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
    detector = ScreenDetector(_fresh, on_auto_ocr=log_cb)

    def _load(key):
        img, scale, meta = load_template(folder, key, current_w, current_h,
                                         grayscale=True, ref_folder=ref_folder,
                                         prefer_ref=prefer_ref)
        box = meta.get("box")
        if box:
            detector.set_template_geometry(
                key, box, meta.get("screen_width", current_w),
                meta.get("screen_height", current_h))
        if meta.get("roi"):                           # user-drawn ROI overrides
            detector.set_template_roi(key, meta["roi"], *(meta.get("roi_dims") or (meta.get("screen_width", 0), meta.get("screen_height", 0))))
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
    safety_tpls = _load_recovery_safety_templates(
        detector, _fresh, tpl_lang, current_w, current_h)

    # Gate templates (best-effort, loaded into the same dict _detect indexes):
    # both present → confirmed/retrying buy loop; either absent → blind macro.
    for key in GATE_KEYS:
        try:
            nav_tpls[key] = _load(key)
        except FileNotFoundError:
            pass
    for key in TARGET_DETAIL_KEYS:
        if key in nav_tpls:
            continue
        try:
            nav_tpls[key] = _load(key)
        except FileNotFoundError:
            pass
    gating = all(k in nav_tpls for k in GATE_KEYS)

    def stop():
        return stop_event.is_set()

    def paused():
        return bool(pause_event and pause_event.is_set())

    def wait(seconds):
        """Stop-aware sleep so F9/Stop isn't blocked by fixed waits."""
        end = time.time() + seconds
        while time.time() < end:
            if stop():
                return
            while paused() and not stop():
                time.sleep(0.1)
            time.sleep(0.1)

    def announce(msg):
        log_cb(msg)
        status_cb(msg)

    def press(key, post_wait=None):
        while paused() and not stop():
            time.sleep(0.1)
        io.press(key, post_wait=post_kw if post_wait is None else post_wait)

    def _detect(key, window_s):
        """TIME-BOXED detection: poll detect() up to window_s, return the
        MatchResult the instant it matches, else None."""
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return None
            if paused():
                paused_at = time.time()
                while paused() and not stop():
                    time.sleep(0.1)
                end += time.time() - paused_at
                continue
            try:
                r = detector.detect(io.grab(), key,
                                    nav_tpls[key], _thr(key), stable=False)
                if r.matched:
                    return r
            except Exception:
                pass
            time.sleep(0.15)
        return None

    def _confirm_target_detail(key):
        try:
            nav_tpls[key] = _load(key)
        except FileNotFoundError:
            log_cb(_at("log_template_missing", lang, key=key))
            return False
        r = _detect(key, _NAV_STEP_WINDOW)
        if r is None:
            log_cb(_at("log_buy_nav_fail", lang,
                       label=_at(_LABELS.get(key, "buy_tpl_detail"), lang),
                       secs=f"{_NAV_STEP_WINDOW:.0f}"))
            _back_out_wrong_detail()
            return False
        log_cb(_at("log_buy_nav_detected", lang,
                   label=_at(_LABELS.get(key, "buy_tpl_detail"), lang),
                   conf=logfmt.detail(r, lang), secs="-"))
        return True

    def _back_out_wrong_detail():
        for _ in range(2):
            if stop():
                return
            press('escape', post_wait=0.5)

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
                   conf=logfmt.detail(r, lang), secs=secs))
        if pre_click_wait:
            wait(pre_click_wait)
            if stop():
                return False
        log_cb(_at("log_buy_nav_click", lang, label=lbl))
        io.click(r.location[0], r.location[1], post_kw)
        return True

    def _navigate_to_target(start_hit=None, start_step="collection_log"):
        """Main menu → Collection Log → Discover Japan → Car Collection →
        Backspace (brand) → scroll to bottom → target car focused. start_hit =
        the collection_log match already in hand. Returns True on success,
        False if a step's element never appears (abort) or stopped."""
        announce(_at("log_buy_nav_begin", lang))
        click_fn = lambda loc: io.click(loc[0], loc[1], post_kw)

        def _advance(prev_key, next_key):
            """Click prev_key and confirm we reached next_key, re-clicking prev_key
            if a dropped click leaves the menu stuck (navutil failsafe)."""
            log_cb(_at("log_buy_nav_click", lang, label=_at(_LABELS[prev_key], lang)))
            return navutil.click_until_advanced(
                io.grab, detector, click_fn,
                (prev_key, nav_tpls[prev_key], _thr(prev_key)),
                (next_key, nav_tpls[next_key], _thr(next_key)),
                stop,
                pause_cb=paused,
                log_retry=lambda n: log_cb(_at("log_nav_reclick", lang,
                                               label=_at(_LABELS[prev_key], lang), n=n)))

        # 1. Collection Log → Discover Japan card
        if start_step in TARGET_DETAIL_KEYS:
            log_cb(_at("log_buy_macro_start", lang))
            return True

        if start_step == "collection_log" and _advance("collection_log", "discover_japan") is None:
            if not stop():
                log_cb(_at("log_buy_nav_fail", lang,
                           label=_at("buy_tpl_discover_japan", lang), secs="-"))
            return False
        if stop():
            return False
        # 2. Discover Japan → Car Collection grid
        if start_step in ("collection_log", "discover_japan") and _advance("discover_japan", "car_collection") is None:
            if not stop():
                log_cb(_at("log_buy_nav_fail", lang,
                           label=_at("buy_tpl_car_collection", lang), secs="-"))
            return False
        if stop():
            return False
        # 3. Car Collection grid reached → Down + Enter
        if start_step == "subaru":
            if target_nav is not None:
                return False
            sub = detector.locate_text(io.grab(), "subaru")
            if sub is not None:
                log_cb(_at("log_buy_nav_click", lang, label=_at("buy_tpl_subaru", lang)))
                io.click(sub.location[0], sub.location[1], post_kw)
            elif not _nav_click("subaru"):
                return False
            log_cb(_at("log_buy_nav_key", lang, keys="S → Enter → Enter",
                       label=_at("buy_tpl_target_car", lang)))
            press('s')
            if stop():
                return False
            press('enter')
            wait(0.5)
            if stop():
                return False
            press('enter')
            if stop():
                return False
            if not _confirm_target_detail("buy_detail_22b"):
                return False
            log_cb(_at("log_buy_macro_start", lang))
            return True
        lbl = _at("buy_tpl_car_collection", lang)
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
        # 4b. Custom target nav (e.g. Full Auto money grind → Dodge → GTS ACR):
        #     replaces the built-in Subaru→22B selection below. Must leave the
        #     target car focused on its detail view; the macro then runs as usual.
        if target_nav is not None:
            return bool(target_nav(io, detector, press, wait, log_cb, stop, post_kw))
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
        # 6. Click the Subaru BRAND tile → drops into the car-list view; the
        #    cursor reliably lands on the BRAT GL tile. The brand list order
        #    varies with the player's favourites, so a pixel match can peak on the
        #    wrong tile (OCR would still region-confirm "subaru" and pass). So use
        #    OCR to LOCATE the "Subaru" text and click ITS box; fall back to the
        #    pixel nav-click if OCR can't place it.
        sub = detector.locate_text(io.grab(), "subaru")
        if sub is not None:
            log_cb(_at("log_buy_nav_click", lang, label=_at("buy_tpl_subaru", lang)))
            io.click(sub.location[0], sub.location[1], post_kw)
        elif not _nav_click("subaru"):
            return False
        # 7. From BRAT GL the 22B-STi is one row down, so move down once and
        #    select it with Enter. Keyboard nav is reliable here — detecting the
        #    tile collided with the look-alike Subaru tiles (BRAT GL etc.), so the
        #    template detection for the target car is ditched in favour of S→Enter→Enter.
        log_cb(_at("log_buy_nav_key", lang, keys="S → Enter → Enter",
                   label=_at("buy_tpl_target_car", lang)))
        press('s')
        if stop():
            return False
        press('enter')
        wait(0.5)
        if stop():
            return False
        press('enter')
        if stop():
            return False
        if not _confirm_target_detail("buy_detail_22b"):
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
    route_retries = recovery.route_retries(_fresh)
    recovered_anchor = None

    def _detect_buy_anchor(window_s, include_detail=False, keys=None):
        keys = list(keys) if keys is not None else list(NAV_KEYS)
        if target_nav is not None and "subaru" in keys:
            keys.remove("subaru")
        if include_detail:
            keys.extend(k for k in TARGET_DETAIL_KEYS if k in nav_tpls)
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return (None, None)
            try:
                frame = io.grab()
                for key in keys:
                    r = detector.detect(frame, key, nav_tpls[key],
                                        _thr(key), stable=False)
                    if r.matched:
                        return (key, r)
            except Exception:
                pass
            time.sleep(0.15)
        return (None, None)

    def _detect_safety_anchor(window_s):
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return None
            try:
                frame = io.grab()
                for key in _RECOVERY_SAFETY_ANCHOR_KEYS:
                    if key not in safety_tpls:
                        continue
                    r = detector.detect(frame, key, safety_tpls[key],
                                        _thr(key), stable=False)
                    if r.matched:
                        return key
            except Exception:
                pass
            time.sleep(0.15)
        return None

    def _buy_entry_route():
        nonlocal did_nav, recovered_anchor
        if recovered_anchor is not None:
            which, start_hit = recovered_anchor, None
            recovered_anchor = None
        else:
            which, start_hit = _detect_buy_anchor(_START_STATE_WINDOW)
        if which in NAV_KEYS or which in TARGET_DETAIL_KEYS:
            if not _navigate_to_target(start_hit, start_step=which):
                return False
            did_nav = True
            return True
        if require_nav:
            log_cb(_at("log_buy_nav_fail", lang,
                       label=_at("buy_tpl_collection_log", lang),
                       secs=f"{_START_STATE_WINDOW:.0f}"))
            return False
        return True

    def _recover_buy_entry_route():
        nonlocal recovered_anchor
        rec_label = "Buy entry"
        log_cb(_at("log_recovery_search", lang, label=rec_label))
        for attempt in range(7):
            anchor_keys = recovery.backtrack_anchor_keys(
                (*NAV_KEYS, *TARGET_DETAIL_KEYS))
            which, _hit = _detect_buy_anchor(1.2, keys=anchor_keys)
            if which is not None:
                recovered_anchor = which
                log_cb(_at("log_recovery_anchored", lang,
                           label=rec_label, anchor=which))
                return True
            safety = _detect_safety_anchor(0.8)
            if safety is not None:
                log_cb(_at("log_recovery_anchored_safety", lang,
                           label=rec_label, anchor=safety))
                if _recover_to_main_menu_from_safety_anchor(
                        safety,
                        lambda: press('escape', post_wait=0.5),
                        lambda: wait(0.5),
                        lambda: _detect_safety_anchor(1.2)):
                    recovered_anchor = "collection_log"
                    return True
            if attempt >= 6 or stop():
                break
            log_cb(_at("log_recovery_esc", lang, label=rec_label))
            press('escape', post_wait=0.5)
        log_cb(_at("log_recovery_no_anchor", lang, label=rec_label))
        return False

    if require_nav and not nav_enabled:
        # Full Auto: buy must navigate from the main menu, but the nav templates
        # aren't all captured — can't proceed in the chain.
        log_cb(_at("log_buy_nav_fail", lang,
                   label=_at("buy_tpl_collection_log", lang), secs="0"))
        io.cleanup()
        return False
    if nav_enabled and not stop():
        # On the main menu (collection_log visible)? Then navigate. Otherwise
        # assume the user pre-positioned on the target car (legacy) and just
        # run the macro — no exit nav in that case (unknown menu depth).
        if not recovery.run_stage_route("Buy entry", _buy_entry_route, stop,
                                        log_cb, route_retries,
                                        recover_fn=_recover_buy_entry_route,
                                        on_recover=detector.reset_ocr_cache):
            io.cleanup()
            log_cb(_at("log_buy_stopped", lang))
            status_cb(_at("status_stopped", lang))
            return False
    elif not nav_enabled:
        log_cb(_at("log_buy_nav_skip", lang))

    def _buy_one():
        """Buy ONE car with confirmation + Esc recovery. Returns the confirm
        match score on a verified purchase, or None if it had to abort (couldn't
        recover to the detail view, attempts exhausted, or stopped)."""
        for attempt in range(1, _MAX_BUY_ATTEMPTS + 1):
            if stop():
                return None
            for key in BUY_INIT:
                if stop():
                    return None
                log_cb(_at('log_buy_key', lang, key=key.upper()))
                press(key)
            r = _detect("buy_confirm", _CONFIRM_WINDOW)
            if r is not None:               # popup → the car was really bought
                press('enter')              # dismiss "Enter ▸ Ok" → detail view
                return r.score
            if stop():
                return None
            # No confirmation: a key was dropped and we may be sitting on the
            # wrong buy option / a sub-menu. Esc always returns to the car detail
            # view; confirm we're there before re-pressing (never guess).
            log_cb(_at("log_buy_retry", lang, a=attempt, m=_MAX_BUY_ATTEMPTS))
            press('escape')
            if _detect("buy_detail_22b", _RECOVER_WINDOW) is None:
                if not stop():
                    log_cb(_at("log_buy_recover_fail", lang))
                return None
            # back on the detail view → loop retries from a known state
        log_cb(_at("log_buy_attempts_exhausted", lang, m=_MAX_BUY_ATTEMPTS))
        return None

    # ── Buy loop ──
    run_ok = True
    loop = 0
    if gating:
        log_cb(_at("log_buy_gated_on", lang))
    while not stop():
        section(f"-- {_at('buy_loop', lang)} #{loop + 1}" +
                (f" / {max_loops}" if max_loops > 0 else "") + " --")
        if gating:
            score = _buy_one()
            if score is None:               # aborted — don't snowball
                run_ok = False
                break
            loop += 1
            log_cb(_at("log_buy_confirmed", lang, conf=f"{score:.0%}", n=loop))
        else:
            # Blind fallback (gate templates not captured): old behaviour.
            for key in BUY_MACRO:
                if stop():
                    break
                log_cb(_at('log_buy_key', lang, key=key.upper()))
                press(key)
            loop += 1
        if progress_cb:
            progress_cb(loop, max_loops)
        if max_loops > 0 and loop >= max_loops:
            log_cb(_at('log_buy_limit_reached', lang, n=max_loops))
            break

    # ── Optional exit navigation — only if we entered via nav AND finished
    #    cleanly (an abort leaves an unknown screen; don't fire the Esc chain). ──
    if did_nav and run_ok and not stop():
        _return_to_menu()

    io.cleanup()     # stop keep-alive + unmute
    log_cb(_at("log_buy_stopped", lang))
    status_cb(_at("status_stopped", lang))
    return run_ok
