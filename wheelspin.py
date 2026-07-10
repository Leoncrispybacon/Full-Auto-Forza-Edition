# ============================================================
#  automation/wheelspin.py — Auto Spin Wheel automation logic
#  ENTRY: from the My Horizon menu, detect the Super Wheelspin tile
#  and click it (starts the first spin; the spin screen then persists).
#  Each spin is DETECTION-GATED, not timed. FAFE never presses to spin
#  (the entry click starts spin #1; every later spin auto-starts from the
#  previous collect's "…and Spin Again"). A Super Wheelspin has 3 wheels and
#  ONE Enter collects all three prizes at once, so per spin:
#    1. BEST-EFFORT skip: if the brief "Skip" prompt shows, Enter to fast-
#       forward the reveal (it lands on the collect prompt). Optional — if the
#       skip template is absent or the prompt is missed, we just wait for the
#       collect prompt as normal, so skip can only save time, never desync.
#    2. wait for the collect prompt → Enter (collects all 3 prizes)
#    3. duplicate-handling inner loop (a dup menu per duplicate car, up to 3,
#       OR the next spin's collect prompt once none are left)
#  Stage waits use detector.wait_for (wait until the screen is actually
#  present — F9/Stop recovers). Skip is viable now that ROI-only detection is
#  ~23ms (fast enough to catch the brief skip window); the older skip attempt
#  was dropped because ~680ms full-screen detection couldn't keep up.
#  Output via log_cb / status_cb; stop via stop_event.
# ============================================================

import time
import threading

import config
import logfmt
import navutil
import recovery
from config import get_wheelspin_templates
from app_lang import t as _at
from capture import (grab_frame, load_template, get_monitor_dims,
                     force_english_ime, mouse_click)
from detector import ScreenDetector
from gameio import GameIO
# Reuse the IME-safe (dual VK+scancode) key sender shared by Delete/Buy.
# wheelspin only presses 'enter' and 'down' (down is an extended VK there).
from delete_cars import key_press


# ── Tunable values (constants; some overridable via Settings) ──
SUPER_FIND_WINDOW = 12.0  # max time to find the Super Wheelspin tile at start
MH_TAB_WINDOW     = 8.0   # max time to find the My Horizon tab (menu-start entry)
# A Super Wheelspin has 3 wheels, so at most 3 duplicates can appear per spin.
# Hard-cap the inner loop at 3 — without this a mis-detection (e.g. a stuck/
# re-matched menu) let it handle 5+ in a real bug report. Reaching the cap
# means something misfired; the per-detection confidence log helps diagnose it.
MAX_DUP_CHAIN    = 3
# Skip is only watched for the first few seconds of each spin's collect-wait (it
# appears during the reveal); after that only collect/final are polled, so a
# missing Skip prompt never pins detection on it forever. collect/final wait
# indefinitely (F9 recovers a screen that genuinely can't be detected).
SKIP_WATCH_S     = 5.0
# After collect/final is pressed, watch for the duplicate menu for this long;
# each duplicate handled REFRESHES the window, and the window expiring with no
# (further) duplicate means none are left. Bounded so the dup phase can't hang.
DUP_WINDOW_S     = 5.0
# Arm the NEXT reveal's Skip on a fixed timer after collect, instead of waiting to
# see the prompt area go CLEAR. The just-collected spin's Skip/collect prompt
# lingers <~1s, so any Skip within this delay is that STALE prompt (ignored); a
# Skip after it is the next reveal. Time-based so a slow device (Ally X) that
# never catches a "clear" frame at the poll rate still arms.
SKIP_ARM_DELAY   = 1.0
# If collect/final never appears, scan every wheelspin-state template before
# giving up to manual Stop. This avoids getting stuck between reward states.
COLLECT_RECOVERY_S = 20.0
# Polling interval for the detection loops (skip/collect/duplicate/tile waits).
# Higher = fewer detections/sec = less CPU contention with the game (each detect
# briefly uses multiple cores). 0.3s is the test value; the brief "Skip" prompt
# is the tightest window, so if skip starts getting missed, lower this.
_DETECT_IV = 0.3

MH_TAB_KEY   = "my_horizon_tab"       # top-nav tab, clicked to start from main menu
SUPER_KEY    = "super_wheelspin"      # left-column tile, clicked to start a run
NORMAL_KEY   = "normal_wheelspin"     # the normal Wheelspin tile (1 prize); chosen
                                      # via wheelspin_type. Only the START tile
                                      # differs from super — the rest is identical.
SKIP_KEY     = "wheelspin_skip"       # reveal "Skip" prompt — Enter fast-forwards
COLLECT_KEY  = "wheelspin_collect"    # prize/result — Enter collects (+ spins again)
FINAL_KEY    = "wheelspin_collect_final"  # last-spin single "Collect Prize" (no spins
                                      # left): Enter collects and leaves, no restart.
                                      # Best-effort, watched only on the final spin.
TEMPLATE_KEY = "wheelspin_duplicate"  # the 3-option duplicate-reward menu
# Skip is BEST-EFFORT: loaded only if the template exists; a missing/missed skip
# falls back to waiting for the collect prompt (no desync, just no speed-up).
_RECOVERY_SAFETY_ANCHOR_KEYS = ("anna", "collection_log")


def _load_recovery_safety_templates(detector, cfg, tpl_lang, width, height):
    return recovery.load_recovery_safety_templates(
        detector, cfg, tpl_lang, width, height)


def _recover_to_main_menu_from_safety_anchor(anchor, press_escape, wait,
                                             detect_anchor=None):
    return recovery.recover_to_main_menu_from_safety_anchor(
        anchor, press_escape, wait, detect_anchor)


def run(cfg: dict, stop_event: threading.Event,
        log_cb, status_cb, max_loops: int = 0,
        warn_cb=None, section_cb=None, progress_cb=None,
        pause_event: threading.Event | None = None,
        force_type: str | None = None):
    """
    Auto Spin Wheel loop.
    cfg: config dict
    stop_event: set to stop
    log_cb(msg) / status_cb(msg): log line / status bar
    max_loops: stop after this many spins (0 = unlimited)
    force_type: override the wheelspin_type setting ("super"/"normal"); used by
                Full Auto to lock the chain to Super Wheelspins regardless of the
                standalone tab's choice. None = use the config setting.
    section_cb(msg): start a bounded log section; falls back to log_cb
    warn_cb: accepted for call-site parity; UNUSED — the duplicate check is
             time-boxed and a non-detection is its NORMAL outcome. The skip /
             collect stage waits surface their own one-time slow hint instead.
    """
    section       = section_cb or log_cb
    lang          = cfg.get("lang", "en")
    monitor_index = cfg.get("monitor_index", 1)

    # Always read settings fresh from config.json at start.
    import config as _cfg_mod
    _fresh   = _cfg_mod.load()
    post_kw  = _fresh.get("wheelspin_post_key_wait", 0.5)
    # Duplicates are SOLD by default. Two independent keep-exceptions:
    #   keep_fe     — keep Forza Edition cars (name contains UPPERCASE "FE")
    #   keep_price  — keep when the read sell price >= this many credits (0 = off)
    # Either needs an OCR read of the modal; with both off we sell unconditionally.
    keep_fe  = _fresh.get("wheelspin_keep_fe", True)
    try:
        keep_price = int(_fresh.get("wheelspin_keep_above_price", 0) or 0)
    except (TypeError, ValueError):
        keep_price = 0
    need_ocr = keep_fe or keep_price > 0
    wtype    = (force_type if force_type in ("super", "normal")
                else _fresh.get("wheelspin_type", "super"))   # "super" | "normal"
    # Which tile starts the run: Super Wheelspin (3 prizes) or normal Wheelspin
    # (1 prize). Only this start tile differs — collect/duplicate flow is the same.
    TILE_KEY = NORMAL_KEY if wtype == "normal" else SUPER_KEY
    tpl_lang = _cfg_mod.resolve_template_lang(_fresh)

    def _thr(key):
        return _fresh.get(f"thresh_{key}", 0.60)

    io = GameIO(_fresh, log_cb, crop_letterbox=True)   # starts on main menu (My Horizon)
    current_w, current_h = io.width, io.height
    mon_left, mon_top = io.cap_left, io.cap_top
    # Single built-in template set (REFERENCE_RES), auto-scaled to the monitor.
    folder   = get_wheelspin_templates(_cfg_mod.REFERENCE_RES, tpl_lang)
    ref_folder = folder
    prefer_ref = _fresh.get('template_prefer_reference', True)
    log_cb(f"  Templates: {tpl_lang} / built-in")
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

    templates = {}
    for key in (TILE_KEY, COLLECT_KEY, TEMPLATE_KEY):
        try:
            templates[key] = _load(key)
        except FileNotFoundError:
            log_cb(_at("log_template_missing", lang, key=key))
            status_cb(_at("status_setup_incomplete", lang))
            return
    tile_tpl              = templates[TILE_KEY]   # super OR normal, per wheelspin_type
    collect_tpl, dup_tpl  = templates[COLLECT_KEY], templates[TEMPLATE_KEY]
    # Label for logs/status, matching the chosen tile.
    tile_label = _at("spin_tpl_normal" if wtype == "normal" else "spin_tpl_super", lang)
    # Skip is best-effort: load it if present, else disable skip-forward (the
    # collect wait alone still works — just no speed-up). Never aborts the run.
    try:
        skip_tpl = _load(SKIP_KEY)
    except FileNotFoundError:
        skip_tpl = None
        log_cb(_at("log_spin_skip_off", lang))
    # Final-spin "Collect Prize" prompt (account out of spins). Best-effort:
    # absent → the last spin falls back to the Esc-collect, exactly as before.
    try:
        final_tpl = _load(FINAL_KEY)
    except FileNotFoundError:
        final_tpl = None
    # My Horizon tab is best-effort too: present → the run can START from the
    # main menu (click the tab → My Horizon menu); absent → assume we're already
    # on the My Horizon menu and go straight to the Super Wheelspin tile.
    try:
        mh_tab_tpl = _load(MH_TAB_KEY)
    except FileNotFoundError:
        mh_tab_tpl = None
        log_cb(_at("log_spin_mh_tab_off", lang))
    # The duplicate modal's OCR bands (FE-name / price) are read via ROI only —
    # no template image is matched — so register any user-captured/adjusted ROI
    # or geometry box from the sidecar (if present) so duplicate_info reads the
    # tuned region instead of the built-in DEFAULT_ROIS fallback.
    def _load_ocr_roi(key):
        import os, json
        meta_path = os.path.join(folder, key + ".json")
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            return
        if meta.get("box"):
            detector.set_template_geometry(
                key, meta["box"], meta.get("screen_width", current_w),
                meta.get("screen_height", current_h))
        if meta.get("roi"):
            detector.set_template_roi(
                key, meta["roi"],
                *(meta.get("roi_dims") or (meta.get("screen_width", 0),
                                           meta.get("screen_height", 0))))
    for _dk in ("wheelspin_dup_name", "wheelspin_dup_price"):
        _load_ocr_roi(_dk)

    safety_tpls = _load_recovery_safety_templates(
        detector, _fresh, tpl_lang, current_w, current_h)

    def stop():
        return stop_event.is_set()

    def paused():
        return bool(pause_event and pause_event.is_set())

    def wait(seconds):
        """Stop-aware sleep so F9/Stop isn't blocked by the fixed waits."""
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

    def _detect(key, tpl, window_s):
        """TIME-BOXED detection: poll detect() for up to window_s seconds and
        return the MatchResult the instant it matches, else None. NOT wait_for
        (which is indefinite) — used where a None is a NORMAL outcome (no
        duplicate, or the Super Wheelspin tile not visible), never an error."""
        end = time.time() + window_s
        best = None
        while time.time() < end:
            if stop():
                break
            if paused():
                paused_at = time.time()
                while paused() and not stop():
                    time.sleep(0.1)
                end += time.time() - paused_at
                continue
            try:
                frame = io.grab()
                r = detector.detect(frame, key, tpl, _thr(key), stable=False)
                if best is None or r.score > best.score:
                    best = r
                if r.matched:
                    _detect.best = r
                    return r
            except Exception:
                pass
            time.sleep(_DETECT_IV)
        _detect.best = best     # remember best miss so not-found lines can show it
        return None

    def _detect_tile_or_tab(window_s, keys=None):
        """First step: poll for the wheel TILE or the My Horizon TAB, TILE
        prioritized. If the tile is already visible we're on the My Horizon menu,
        so we should click the tile — NOT re-navigate via the tab. Returns
        ('tile'|'tab', result) for whichever shows (tile wins ties), or
        (None, None) if the window elapses / stopped."""
        scan_keys = tuple(keys) if keys is not None else ("tile", "tab")
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return (None, None)
            if paused():
                paused_at = time.time()
                while paused() and not stop():
                    time.sleep(0.1)
                end += time.time() - paused_at
                continue
            try:
                frame = io.grab()
                for key in scan_keys:
                    if key == "tile":
                        r = detector.detect(frame, TILE_KEY, tile_tpl,
                                            _thr(TILE_KEY), stable=False)
                    elif key == "tab" and mh_tab_tpl is not None:
                        r = detector.detect(frame, MH_TAB_KEY, mh_tab_tpl,
                                            _thr(MH_TAB_KEY), stable=False)
                    else:
                        continue
                    if r.matched:
                        return (key, r)
            except Exception:
                pass
            time.sleep(_DETECT_IV)
        return (None, None)

    def _detect_safety_anchor(window_s):
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
            time.sleep(_DETECT_IV)
        return None

    def _wait_collect(skip_deadline, is_last=False):
        """Wait until a spin's collect prompt shows; return
        ('skip'|'duplicate'|'collect'|'final', result), or (None, None) if stopped.
          • 'skip'    — the brief reveal "Skip" prompt (Enter fast-forwards).
                        Only watched while now < skip_deadline (it appears only
                        during the reveal), so it's never polled indefinitely.
          • 'collect' — the normal "…and Spin Again" prompt (its OCR hints
                        require the spin-again text). Checked BEFORE 'final'.
          • 'final'   — the single "Collect Prize" prompt (account out of spins),
                        a text subset of collect — so it only wins when collect's
                        spin-again distinguisher is absent (genuinely out of spins).
                        Only polled when is_last is True to avoid false matches
                        on intermediate spins whose "…and Spin Again" overlaps.
        collect/final are watched indefinitely. After 20s with no collect/final,
        trigger recovery reporting and scan all wheelspin in-spin templates
        (skip/duplicate/collect/final) on each frame. One grab serves all checks."""
        started = time.time()
        recovery_reported = False
        while not stop():
            if paused():
                paused_at = time.time()
                while paused() and not stop():
                    time.sleep(0.1)
                delta = time.time() - paused_at
                started += delta
                skip_deadline += delta
                continue
            try:
                frame = io.grab()
                # A leftover duplicate modal from the PREVIOUS spin whose dup
                # phase missed it (slow device): it blocks and persists on screen
                # until dismissed, so the "next spin" never actually starts.
                # Catch it here (OCR-confirmed, same as the dup phase) and hand
                # it to the dup phase; the caller rolls the spin count back for
                # this case so it isn't miscounted as a new spin.
                dr = detector.detect(frame, TEMPLATE_KEY, dup_tpl,
                                     _thr(TEMPLATE_KEY), stable=False)
                if dr.matched:
                    return ('duplicate', dr)
                if skip_tpl is not None and time.time() < skip_deadline:
                    r = detector.detect(frame, SKIP_KEY, skip_tpl,
                                        _thr(SKIP_KEY), stable=False)
                    if r.matched:
                        return ('skip', r)
                r = detector.detect(frame, COLLECT_KEY, collect_tpl,
                                    _thr(COLLECT_KEY), stable=False)
                if r.matched:
                    return ('collect', r)
                if final_tpl is not None and is_last:
                    r = detector.detect(frame, FINAL_KEY, final_tpl,
                                        _thr(FINAL_KEY), stable=False)
                    if r.matched:
                        return ('final', r)
                if time.time() - started >= COLLECT_RECOVERY_S:
                    if not recovery_reported:
                        recovery_reported = True
                        log_cb(_at("log_recovery_search", lang,
                                   label="Wheelspin collect"))
                        recovery.trigger_report("Wheelspin collect recovery")
                    for key, tpl in (
                        (SKIP_KEY, skip_tpl),
                        (TEMPLATE_KEY, dup_tpl),
                        (COLLECT_KEY, collect_tpl),
                        (FINAL_KEY, final_tpl),
                    ):
                        if tpl is None:
                            continue
                        r = detector.detect(frame, key, tpl, _thr(key), stable=False)
                        if r.matched:
                            return ({
                                SKIP_KEY: 'skip',
                                TEMPLATE_KEY: 'duplicate',
                                COLLECT_KEY: 'collect',
                                FINAL_KEY: 'final',
                            }[key], r)
            except Exception:
                pass
            time.sleep(_DETECT_IV)
        return (None, None)

    if max_loops > 0:
        log_cb(_at("log_spin_started_count", lang, n=max_loops))
    else:
        log_cb(_at("log_spin_started", lang))
    log_cb(_at("log_spin_sell_warn", lang))
    if keep_fe:
        log_cb(_at("log_spin_keep_fe_on", lang))
    if keep_price > 0:
        log_cb(_at("log_spin_keep_price_on", lang, price=f"{keep_price:,}"))
    # Switch the game to English input only if it isn't already (foreground
    # only — in background mode it would target the wrong window).
    if not io.bg and _fresh.get("auto_english_ime", True):
        force_english_ime()
        time.sleep(0.2)
    io.mute(_fresh)
    io.start_keepalive(stop, _fresh)

    # ── Optional menu-start (ONCE): if the My Horizon tab template is captured,
    #    click it first so the run can START from the main menu (the chaining
    #    entry point). The tab is in the fixed top nav, visible from any menu, so
    #    this also works if we're already on My Horizon. Best-effort: if the
    #    template is absent or the tab isn't found, we fall straight through to
    #    the Super Wheelspin tile detection (which assumes we're already on the
    #    My Horizon menu and aborts if not). ──
    if mh_tab_tpl is not None and not stop():
        announce(_at("log_spin_select_mh_tab", lang))
        _t_mh = time.time()
        # Prioritize the wheel tile: if it's already on screen we're on the My
        # Horizon menu (both the tile and the top-nav tab are visible there), so
        # clicking the tab would needlessly re-navigate. Only click the tab when
        # the tile ISN'T visible (i.e. we're elsewhere and need to get to My
        # Horizon). When the tile IS visible we skip the tab — the entry step
        # below clicks the tile.
        which_first, r_first = _detect_tile_or_tab(MH_TAB_WINDOW)
        if which_first == 'tab':
            log_cb(_at("log_spin_detected", lang,
                       label=_at("spin_tpl_my_horizon", lang),
                       conf=logfmt.detail(r_first, lang),
                       secs=f"{time.time() - _t_mh:.1f}"))
            # → My Horizon menu (failsafe: re-click the tab if the wheel tile
            #   doesn't show, i.e. the click was dropped). If it never advances,
            #   the entry tile detect below aborts as before.
            navutil.click_until_advanced(
                io.grab, detector,
                lambda loc: io.click(loc[0], loc[1], post_kw),
                (MH_TAB_KEY, mh_tab_tpl, _thr(MH_TAB_KEY)),
                (TILE_KEY, tile_tpl, _thr(TILE_KEY)),
                stop,
                pause_cb=paused,
                log_retry=lambda n: log_cb(_at("log_nav_reclick", lang,
                       label=_at("spin_tpl_my_horizon", lang), n=n)))
        elif which_first == 'tile':
            log_cb(_at("log_spin_on_my_horizon", lang, label=tile_label))

    # ── Entry (ONCE): from the My Horizon menu, find the Super Wheelspin tile
    #    and click its centre. Clicking it starts the first spin and moves to
    #    the spin screen, which then persists. Every later spin auto-starts from
    #    the previous collect ("…and Spin Again"), so FAFE never presses to spin
    #    again — it just waits for each spin's skip/collect prompts. ──
    route_retries = recovery.route_retries(_fresh)

    def _wheelspin_entry_route():
        announce(_at("log_spin_select_tile", lang, label=tile_label))
        _t_super = time.time()
        which_first, r_first = _detect_tile_or_tab(MH_TAB_WINDOW)
        if which_first == 'tab':
            log_cb(_at("log_spin_detected", lang,
                       label=_at("spin_tpl_my_horizon", lang),
                       conf=logfmt.detail(r_first, lang),
                       secs=f"{time.time() - _t_super:.1f}"))
            navutil.click_until_advanced(
                io.grab, detector,
                lambda loc: io.click(loc[0], loc[1], post_kw),
                (MH_TAB_KEY, mh_tab_tpl, _thr(MH_TAB_KEY)),
                (TILE_KEY, tile_tpl, _thr(TILE_KEY)),
                stop,
                pause_cb=paused,
                log_retry=lambda n: log_cb(_at("log_nav_reclick", lang,
                       label=_at("spin_tpl_my_horizon", lang), n=n)))
            res_super = _detect(TILE_KEY, tile_tpl, SUPER_FIND_WINDOW)
        elif which_first == 'tile':
            log_cb(_at("log_spin_on_my_horizon", lang, label=tile_label))
            res_super = r_first
        else:
            res_super = _detect(TILE_KEY, tile_tpl, SUPER_FIND_WINDOW)
        if res_super is None:
            if not stop():
                log_cb(_at("log_spin_tile_not_found", lang, label=tile_label))
                best = getattr(_detect, "best", None)
                if best is not None:
                    log_cb(_at("log_det_best_seen", lang,
                               detail=logfmt.detail(best, lang)))
            return False
        log_cb(_at("log_spin_detected", lang, label=tile_label,
                   conf=logfmt.detail(res_super, lang),
                   secs=f"{time.time() - _t_super:.1f}"))
        # This click starts spin #1. After this point recovery must not repeat
        # the entry route, because a spin has already been spent/started.
        io.click(res_super.location[0], res_super.location[1], post_kw)
        return True

    def _recover_wheelspin_entry_route():
        rec_label = "Wheelspin entry"
        log_cb(_at("log_recovery_search", lang, label=rec_label))
        for attempt in range(5):
            anchor_keys = recovery.backtrack_anchor_keys(("tab", "tile"))
            which, _hit = _detect_tile_or_tab(1.2, keys=anchor_keys)
            if which in ('tile', 'tab'):
                log_cb(_at("log_recovery_anchored", lang,
                           label=rec_label, anchor=which))
                return True
            safety = _detect_safety_anchor(0.8)
            if safety is not None:
                log_cb(_at("log_recovery_anchored_safety", lang,
                           label=rec_label, anchor=safety))
                return _recover_to_main_menu_from_safety_anchor(
                    safety,
                    lambda: press('escape', post_wait=0.5),
                    lambda: wait(0.5),
                    lambda: _detect_safety_anchor(1.2))
            if attempt >= 4 or stop():
                break
            log_cb(_at("log_recovery_esc", lang, label=rec_label))
            press('escape', post_wait=0.5)
        log_cb(_at("log_recovery_no_anchor", lang, label=rec_label))
        return False

    if not recovery.run_stage_route("Wheelspin entry", _wheelspin_entry_route,
                                    stop, log_cb, route_retries,
                                    recover_fn=_recover_wheelspin_entry_route,
                                    on_recover=detector.reset_ocr_cache):
        io.cleanup()
        log_cb(_at("log_spin_stopped", lang))
        status_cb(_at("status_stopped", lang))
        return

    loop_count = 0
    leftover_streak = 0   # consecutive iterations that only cleared a stale dup
    while not stop():
        loop_count += 1
        if progress_cb:                       # spins done so far → UI bar fill
            progress_cb(loop_count - 1, max_loops)
        section(f"-- {_at('spin_loop', lang)} #{loop_count}" +
                (f" / {max_loops}" if max_loops > 0 else "") + " --")
        # Last counted spin: collect with Esc (collects all 3 prizes AND exits
        # to the My Horizon menu) instead of Enter (which would auto-start
        # another spin). Duplicates STILL appear after the Esc, so they're
        # handled the same way — but the "done" signal is the My Horizon menu
        # reappearing, not the next spin. Unlimited runs (max_loops == 0) never
        # hit this; they stop via F9.
        is_last = max_loops > 0 and loop_count >= max_loops

        # ── 1. Collect phase ──────────────────────────────────
        # The spin ALWAYS auto-starts — FAFE never presses to spin (spin #1 was
        # the tile click, every later spin the previous collect's "…and Spin
        # Again"). A Super Wheelspin has 3 wheels and ONE Enter collects all
        # three at once, so collect is pressed exactly ONCE per spin. We wait for
        # the collect prompt, fast-forwarding the reveal via the brief "Skip"
        # prompt if it shows within SKIP_WATCH_S:
        #   • skip   → Enter (fast-forward), then stop watching skip this spin
        #   • collect ("…and Spin Again") → Enter (or Esc on the counted-last
        #             spin, which collects all + exits instead of auto-spinning)
        #   • final  ("Collect Prize", no spin-again) → the ACCOUNT is out of
        #             Wheelspins (can happen BEFORE the target — the "32/33"
        #             report): Enter to collect + leave, end the run after dups.
        # collect/final wait indefinitely (F9 recovers); skip is time-boxed so a
        # missing Skip prompt can't pin detection on it forever.
        if stop(): break
        ran_out = False
        _t0 = time.time()
        announce(_at("log_spin_wait_collect", lang))
        skip_deadline = (_t0 + SKIP_WATCH_S) if skip_tpl is not None else 0.0
        collected = False
        leftover_dup = False   # phase 1 saw a stale dup, not this spin's collect
        while not stop():
            which, r = _wait_collect(skip_deadline, is_last)
            if which is None:
                break
            _el = f"{time.time() - _t0:.1f}"
            if which == 'skip':
                skip_deadline = 0.0                    # don't fast-forward again this spin
                log_cb(_at("log_spin_detected", lang,
                           label=_at("spin_tpl_skip", lang),
                           conf=logfmt.detail(r, lang), secs=_el))
                announce(_at("log_spin_skip", lang))
                press('enter', post_wait=0.0)          # fast-forward reveal
                continue
            if which == 'duplicate':
                log_cb(_at("log_spin_detected", lang,
                           label=_at("spin_tpl_duplicate", lang),
                           conf=logfmt.detail(r, lang), secs=_el))
                collected = True                       # already past collect; handle dup below
                leftover_dup = True                    # stale dup, not a new spin (rolled back below)
                break
            if which == 'final':
                # Account out of spins. ran_out only when EARLIER than the target
                # (is_last already ends the run on its own).
                ran_out = not is_last
                log_cb(_at("log_spin_detected", lang,
                           label=_at("spin_tpl_collect_final", lang),
                           conf=logfmt.detail(r, lang), secs=_el))
                announce(_at("log_spin_end_enter", lang))
                press('enter', post_wait=0.0)          # collect + leave (no restart)
            elif is_last:                              # normal prompt on counted-last
                log_cb(_at("log_spin_detected", lang,
                           label=_at("spin_tpl_collect", lang),
                           conf=logfmt.detail(r, lang), secs=_el))
                announce(_at("log_spin_end_esc", lang))
                press('escape', post_wait=0.0)         # collect all 3 + exit to menu
            else:                                      # normal prompt, more to go
                log_cb(_at("log_spin_detected", lang,
                           label=_at("spin_tpl_collect", lang),
                           conf=logfmt.detail(r, lang), secs=_el))
                announce(_at("log_spin_collect", lang))
                press('enter', post_wait=0.0)
            collected = True
            break
        if not collected:
            break                                      # stopped
        if stop(): break

        # ── 2. Duplicate phase (ONLY after collect/final was pressed) ──────
        # 0–3 duplicate menus appear in sequence after collecting (one per
        # duplicate car). Watch for the duplicate menu for DUP_WINDOW_S; each
        # duplicate handled REFRESHES the window, so a chain of dups keeps it
        # open, and the window elapsing with no (further) duplicate means none
        # are left. Bounded — it can't hang the spin (the old indefinite dup/
        # next/menu wait DID hang, on a screen where nothing matched).
        #
        # Detect-after-settle: handle a duplicate, then the confirming key's
        # post-wait (> the ~0.23s the menu takes to advance) settles before the
        # next poll, so the menu has MOVED ON and the one just handled can't be
        # re-counted (the "Car Already Owned" header lingers continuously across
        # dups, so rising-edge counting would never see dup #2). The just-pressed
        # collect prompt also lingers, but we watch ONLY the duplicate menu here,
        # so it's simply ignored.
        #
        # We ALSO catch the NEXT spin's reveal Skip prompt here, so Skip works on
        # every spin (its reveal starts during this wait, not just spin #1's).
        # ARM TIMER (SKIP_ARM_DELAY): the Skip/collect prompt from THIS spin
        # lingers right after we collect, so any Skip within the delay is that
        # stale prompt (ignored); a Skip after it is the next reveal. Fixed-timer
        # (not "seen the area clear") so a slow device that never catches a clear
        # frame at the poll rate still arms. Without the delay the lingering
        # prompt fires an instant false break and the loop races.
        announce(_at("log_spin_wait_dup", lang))
        chain = 0
        _t_dup = time.time()   # ~= when collect was pressed → the arm-timer anchor
        dup_deadline = _t_dup + DUP_WINDOW_S
        while not stop() and chain < MAX_DUP_CHAIN:
            if paused():
                paused_at = time.time()
                while paused() and not stop():
                    time.sleep(0.1)
                delta = time.time() - paused_at
                dup_deadline += delta
                _t_dup += delta
                continue
            if time.time() >= dup_deadline:           # window elapsed → none left
                log_cb(_at("log_spin_no_dup", lang,
                           secs=f"{time.time() - _t_dup:.1f}"))
                break
            frame = None
            try:
                frame = io.grab()
                dr = detector.detect(frame, TEMPLATE_KEY, dup_tpl,
                                     _thr(TEMPLATE_KEY), stable=False)
            except Exception:
                dr = None
            if dr is None or not dr.matched:
                # No dup this frame — once past the arm delay (the stale prompt
                # has cleared), a Skip is the NEXT reveal → fast-forward it.
                if (skip_tpl is not None and frame is not None
                        and time.time() - _t_dup >= SKIP_ARM_DELAY):
                    try:
                        sr = detector.detect(frame, SKIP_KEY, skip_tpl,
                                             _thr(SKIP_KEY), stable=False)
                    except Exception:
                        sr = None
                    if sr is not None and sr.matched:  # next reveal's Skip
                        log_cb(_at("log_spin_detected", lang,
                                   label=_at("spin_tpl_skip", lang),
                                   conf=logfmt.detail(sr, lang),
                                   secs=f"{time.time() - _t_dup:.1f}"))
                        announce(_at("log_spin_skip", lang))
                        press('enter', post_wait=0.0)  # fast-forward next reveal
                        break                          # dups done → next spin
                time.sleep(_DETECT_IV)
                continue
            log_cb(_at("log_spin_detected", lang,
                       label=_at("spin_tpl_duplicate", lang),
                       conf=logfmt.detail(dr, lang),
                       secs=f"{time.time() - _t_dup:.1f}"))
            chain += 1
            # Decide keep vs sell. Default = sell; keep only if FE (when keep_fe)
            # OR the read sell price >= keep_price (when set). Errs toward KEEP on
            # anything unread (selling is irreversible): an FE verdict of None
            # (no name read) keeps, and an unreadable price keeps when price-keep
            # is on. OCR runs on the same `frame` the dup was detected on (no extra
            # grab); skipped entirely when both exceptions are off → unconditional
            # sell, no OCR cost.
            keep = False
            if need_ocr:
                fe, price, txt = detector.duplicate_info(frame)
                if keep_fe and fe is not False:        # True/None → keep
                    keep = True
                    announce(_at("log_spin_dup_keep_fe", lang, n=chain,
                                 name=(txt or "FE")))
                elif keep_price > 0:
                    if price is None:                  # couldn't read price → keep
                        keep = True
                        announce(_at("log_spin_dup_keep_price_unknown", lang, n=chain))
                    elif price >= keep_price:
                        keep = True
                        announce(_at("log_spin_dup_keep_price", lang, n=chain,
                                     price=f"{price:,}"))
            if keep:
                # Garage = top option: Enter (+ its post-key settle).
                press('enter')
            else:
                # Sell = 3rd option: Down ×2 → Enter (Enter's post-wait settles).
                announce(_at("log_spin_dup_sell", lang, n=chain))
                press('down')
                if stop(): break
                press('down')
                if stop(): break
                press('enter')
            dup_deadline = time.time() + DUP_WINDOW_S  # refresh window after handling
        if stop(): break

        # This iteration only cleared a stale duplicate left by the PREVIOUS
        # spin (a slow device missed it in that spin's dup window) — collect was
        # never seen, so it's NOT a new spin. Roll the count back and redo this
        # number; the real next spin auto-starts once the dup(s) are gone. Guard
        # against a genuinely stuck modal looping forever: after MAX_DUP_CHAIN
        # consecutive rollbacks, stop rolling back and let it advance / recover.
        if leftover_dup and leftover_streak < MAX_DUP_CHAIN:
            leftover_streak += 1
            loop_count -= 1
            continue
        leftover_streak = 0

        # ── 3. End / next spin ────────────────────────────────
        # ran_out / is_last collected + left above; otherwise the next spin auto-
        # starts and the top-of-loop collect-wait picks it up.
        if ran_out:
            log_cb(_at("log_spin_ran_out", lang, n=loop_count))
            break
        if is_last:
            log_cb(_at("log_spin_limit_reached", lang, n=max_loops))
            break

    io.cleanup()     # stop keep-alive + unmute
    log_cb(_at("log_spin_stopped", lang))
    status_cb(_at("status_stopped", lang))
