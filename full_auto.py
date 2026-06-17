# ============================================================
#  full_auto.py — Full Auto chained orchestrator
#  Loops the existing automations as one continuous farm:
#    AFK race (user count, for mastery points) → buy N cars →
#    unlock mastery on N cars → sell those N cars → branch:
#      • "wheelspin" → run wheelspin each cycle
#      • "racing"    → straight back to racing (no wheelspin)
#  …repeating until Stop/F9. Every step starts AND ends on the
#  game's main menu (the hand-off point), so the steps chain
#  cleanly. See each module's start/end-on-menu navigation.
#
#  SCAFFOLD STATUS: race + buy are wired (both done + validated).
#  The mastery positioning nav and the mastery→sell transition
#  are CHAINED-ONLY and not yet implemented — they're logged as
#  TODO placeholders so the orchestrator/loop is testable now
#  (race → buy → race → buy …) and the remaining steps slot in.
# ============================================================

import time
import threading

import config
from config import (get_full_auto_templates, get_full_auto_grid_file,
                    resolve_template_lang, REFERENCE_RES)
from app_lang import t as _at
from capture import load_template, force_english_ime
from detector import ScreenDetector
from gameio import GameIO
import race as _race
import buy as _buy
import mastery as _mastery
import wheelspin as _wheelspin

# Buy / master / sell count: 999 max mastery points ÷ 30 per Subaru 22B = 33.
CAR_COUNT = 33

# Mastery positioning nav (chained-only): per-step detection window before
# aborting, and a settle pause before each click/key so it doesn't land
# mid-transition (mirrors race.py's nav). The fast-travel-home load can be slow,
# so the CARS-tab detection (which gates it) gets a wider window.
_NAV_STEP_WINDOW  = 12.0
_NAV_SETTLE       = 0.4
_HOME_LOAD_WINDOW = 30.0
# After confirming Return Home, the game plays a fade/transition before the home
# menu renders. Wait this long before starting CARS-tab detection so we don't
# match a transitional frame and fire the tab-switch too early.
_HOME_TRANSITION_WAIT = 3.0
# Home top-nav tabs switch on the A/D keys (D = next tab). A tab transition
# animation locks out the next switch for ~1s+, so consecutive switches must be
# paced by at least this long (1.0s proved too short in testing).
_TAB_SWITCH_WAIT  = 1.5

# my_horizon_tab is reused from the wheelspin set; the rest are full-auto-only.
_MASTERY_NAV_LABELS = {
    "my_horizon_tab": "spin_tpl_my_horizon",
    "return_home":    "fa_tpl_return_home",
    "cars_tab":       "fa_tpl_cars_tab",
    "recently_added": "fa_tpl_recently_added",
}


def _navigate_to_mastery_start(cfg: dict, stop_event: threading.Event,
                               log_cb, status_cb) -> bool:
    """Chained-only mastery positioning prelude. From the main menu (where Buy
    leaves us), walk to My Cars and land the cursor on the newest car so the
    per-car mastery loop's first iteration starts there:

      My Horizon tab → Return Home tile → Enter (Yes → fast-travel) →
      CARS tab → Enter (My Cars) → X (sort) → Recently Added →
      Backspace (ALL CARS menu) → Enter (newest car)

    Detection-gated + time-boxed (a stuck/wrong screen aborts rather than
    hanging — we're mid-chain, not in the in-race infinite-wait). Best-effort:
    if the nav templates aren't captured it returns False and the caller skips
    the mastery step. Returns True only when positioned on the newest car."""
    fresh = config.load()
    lang  = fresh.get("lang", "en")
    res   = fresh.get("full_auto_resolution", "custom")
    # Detection mode follows the template type (preset → OCR-confirm, custom →
    # pixel-only), same rule as race/buy/wheelspin.
    fresh["detector_ocr_primary"] = (res != "custom")
    tpl_lang = resolve_template_lang(fresh)

    def stop():
        return stop_event.is_set()

    def _thr(key):
        return fresh.get(f"thresh_{key}", 0.60)

    io = GameIO(fresh, log_cb)
    cw, ch = io.width, io.height
    detector = ScreenDetector(fresh)

    fa_folder = get_full_auto_templates(res, tpl_lang)
    ref_folder = prefer_ref = None
    if res != "custom":
        ref_folder = get_full_auto_templates(REFERENCE_RES, tpl_lang)
        prefer_ref = fresh.get("template_prefer_reference", True)

    def _load(folder, key, rf=None, pr=False):
        img, scale, meta = load_template(folder, key, cw, ch, grayscale=True,
                                         ref_folder=rf, prefer_ref=pr)
        box = meta.get("box")
        if box:
            detector.set_template_geometry(
                key, box, meta.get("screen_width", cw),
                meta.get("screen_height", ch))
        return img

    # Full Auto keeps its OWN copy of every template it uses (incl.
    # my_horizon_tab, duplicated from the wheelspin set), so they all load from
    # the full_auto folder and are detected under one consistent mode. Any
    # missing → nav disabled (best-effort).
    tpls = {}
    try:
        for key in ("my_horizon_tab", "return_home", "cars_tab", "recently_added"):
            tpls[key] = _load(fa_folder, key, ref_folder, prefer_ref)
    except FileNotFoundError:
        log_cb(_at("log_fa_mastery_nav_skip", lang))
        io.cleanup()
        return False

    def _wait(secs):
        end = time.time() + secs
        while time.time() < end:
            if stop():
                return
            time.sleep(0.1)

    def _detect(key, window_s):
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return None
            try:
                r = detector.detect(io.grab(), key, tpls[key],
                                    _thr(key), stable=False)
                if r.matched:
                    return r
            except Exception:
                pass
            time.sleep(0.15)
        return None

    def _click_step(key, window_s) -> bool:
        lbl = _at(_MASTERY_NAV_LABELS[key], lang)
        t0  = time.time()
        r   = _detect(key, window_s)
        secs = f"{time.time() - t0:.1f}"
        if r is None:
            if not stop():
                log_cb(_at("log_fa_mastery_nav_fail", lang, label=lbl, secs=secs))
            return False
        log_cb(_at("log_fa_mastery_nav_detected", lang, label=lbl,
                   conf=f"{r.score:.0%}, {r.source}", secs=secs))
        _wait(_NAV_SETTLE)
        if stop():
            return False
        log_cb(_at("log_fa_mastery_nav_click", lang, label=lbl))
        io.click(r.location[0], r.location[1], _NAV_SETTLE)
        return True

    # Foreground only: align IME so the Enter/X/Backspace keys reach the game.
    if not io.bg and fresh.get("auto_english_ime", True):
        force_english_ime()
        time.sleep(0.2)
    io.mute(fresh)
    io.start_keepalive(stop, fresh)
    log_cb(_at("log_fa_mastery_nav_begin", lang))
    status_cb(_at("log_fa_mastery_nav_begin", lang))

    try:
        # 1. My Horizon tab → My Horizon menu
        if not _click_step("my_horizon_tab", _NAV_STEP_WINDOW):
            return False
        # 2. Return Home tile → "Travel To Home" dialog
        if not _click_step("return_home", _NAV_STEP_WINDOW):
            return False
        # 3. Enter (Yes is the default highlight) → fast-travel home (loading)
        io.press("enter", post_wait=_NAV_SETTLE)
        if stop():
            return False
        # 4. We land on the home CAMPAIGN tab. Switch to CARS with the keyboard
        #    (D = next tab), NOT a mouse click — a posted click didn't reliably
        #    switch the tab after the fast-travel load. Detect the home top nav
        #    ONCE (the CARS label is visible whether or not it's the active tab),
        #    confirming the menu has loaded, then: settle → D → settle → D
        #    (CAMPAIGN → BUY & SELL → CARS). _TAB_SWITCH_WAIT (1.5s) covers both
        #    the post-load input-ready delay and the ~1s tab-transition lockout.
        #
        # Confirming Return Home plays a fade/transition before the home menu
        # appears; detecting during it caught a transitional frame and fired the
        # D presses too early. Hold off detection until the transition settles.
        _wait(_HOME_TRANSITION_WAIT)
        if stop():
            return False
        _t_cars = time.time()
        r_cars = _detect("cars_tab", _HOME_LOAD_WINDOW)
        if r_cars is None:
            if not stop():
                log_cb(_at("log_fa_mastery_nav_fail", lang,
                           label=_at("fa_tpl_cars_tab", lang),
                           secs=f"{_HOME_LOAD_WINDOW:.0f}"))
            return False
        log_cb(_at("log_fa_mastery_nav_detected", lang,
                   label=_at("fa_tpl_cars_tab", lang),
                   conf=f"{r_cars.score:.0%}, {r_cars.source}",
                   secs=f"{time.time() - _t_cars:.1f}"))
        log_cb(_at("log_fa_mastery_tab_right", lang))
        _wait(_TAB_SWITCH_WAIT)                                   # menu input-ready
        if stop():
            return False
        io.press("d", post_wait=_TAB_SWITCH_WAIT, scancode=True)  # → BUY & SELL
        if stop():
            return False
        io.press("d", post_wait=_TAB_SWITCH_WAIT, scancode=True)  # → CARS
        if stop():
            return False
        # 5. Enter (My Cars is the default highlight) → My Cars grid. Wait for the
        #    grid to settle before X — pressing X too early (while My Cars is
        #    still opening) drops the sort-menu open.
        log_cb(_at("log_fa_mastery_mycars", lang))
        io.press("enter", post_wait=_TAB_SWITCH_WAIT)
        if stop():
            return False
        # 6. X opens the sort menu → click "Recently Added"
        log_cb(_at("log_fa_mastery_sort", lang))
        io.press("x", post_wait=_NAV_SETTLE)
        if stop():
            return False
        if not _click_step("recently_added", _NAV_STEP_WINDOW):
            return False
        # 7. Backspace → enter the Recently Added menu ("ALL CARS" view)
        io.press("backspace", post_wait=_NAV_SETTLE)
        if stop():
            return False
        # 8. Enter (ALL CARS is the default highlight) → jumps to the newest car
        io.press("enter", post_wait=_NAV_SETTLE)
        if stop():
            return False
        log_cb(_at("log_fa_mastery_at_grid", lang))
        return True
    finally:
        io.cleanup()


# Ordered linear chain steps. The branch (wheelspin/racing) runs after these
# each cycle. start_from selects which of these the FIRST cycle begins at.
STEP_ORDER = ["race", "buy", "mastery", "sell"]


def run(cfg: dict, stop_event: threading.Event,
        log_cb, status_cb, race_count: int = 0,
        car_count: int = CAR_COUNT, branch_mode: str = "racing",
        start_from: str = "race", section_cb=None):
    """
    Full Auto loop.
    race_count: AFK races per cycle (user-defined). 0 = unlimited, which would
                never advance the cycle — the UI nudges a positive value.
    car_count:  how many cars to buy / unlock mastery on / sell per cycle
                (default CAR_COUNT = 33).
    branch_mode: "racing" (no wheelspin) | "wheelspin" (spin each cycle).
    start_from: which STEP_ORDER step the FIRST cycle begins at (for users who
                already have points/cars lined up). Cycle 2+ always runs the
                full loop from racing.
    """
    section = section_cb or log_cb
    lang    = cfg.get("lang", "en")
    if car_count <= 0:
        car_count = CAR_COUNT
    start_idx = STEP_ORDER.index(start_from) if start_from in STEP_ORDER else 0

    def stop():
        return stop_event.is_set()

    # ── Individual chain steps (each starts AND ends on the main menu) ──
    # Each returns True to continue the chain, or False if it could NOT proceed —
    # in which case the orchestrator STOPS (it does not fall through to the next
    # cycle). race/buy/sell don't yet report failure, so they return True;
    # mastery reports a failed positioning nav.
    def _step_race():
        status_cb(_at("log_fa_step_race", lang))
        log_cb(_at("log_fa_step_race", lang))
        _race.run(cfg, stop_event, log_cb, status_cb,
                  max_loops=race_count, section_cb=section_cb)
        return True

    def _step_buy():
        status_cb(_at("log_fa_step_buy", lang))
        log_cb(_at("log_fa_step_buy", lang, n=car_count))
        _buy.run(cfg, stop_event, log_cb, status_cb,
                 max_loops=car_count, section_cb=section_cb)
        return True

    def _step_mastery():
        # Navigate main menu → My Cars → newest car, then run the per-car loop.
        status_cb(_at("log_fa_step_mastery", lang, n=car_count))
        log_cb(_at("log_fa_step_mastery", lang, n=car_count))
        if not _navigate_to_mastery_start(cfg, stop_event, log_cb, status_cb):
            # Nav failed (templates missing / a step never appeared) → can't
            # position for mastery. Don't silently skip into the next cycle; stop.
            return False
        if stop():
            return True   # stopped mid-nav — the outer loop handles it
        # Full Auto uses its OWN mastery-tree grid spec (the 22B tree).
        grid_file = get_full_auto_grid_file(resolve_template_lang(cfg))
        _mastery.run(cfg, stop_event, log_cb, status_cb,
                     max_cars=car_count, section_cb=section_cb,
                     grid_file=grid_file)
        return True

    def _step_sell():
        # TODO: mastery→sell transition not yet wired.
        log_cb(_at("log_fa_step_sell_todo", lang, n=car_count))
        return True

    _steps = {"race": _step_race, "buy": _step_buy,
              "mastery": _step_mastery, "sell": _step_sell}

    log_cb(_at("log_fa_started", lang))
    if race_count <= 0:
        # Unlimited race never returns to the menu, so the cycle can't progress.
        log_cb(_at("log_fa_race_count_warn", lang))

    cycle   = 0
    aborted = False
    while not stop() and not aborted:
        cycle += 1
        section(_at("log_fa_cycle", lang, n=cycle))

        # Cycle 1 begins at the chosen start step; later cycles run the full loop.
        begin = start_idx if cycle == 1 else 0
        for step_key in STEP_ORDER[begin:]:
            if stop():
                break
            ok = _steps[step_key]()
            if stop():
                break
            if not ok:
                # A step couldn't proceed and we weren't stopped — abort the whole
                # run rather than fall through into another cycle.
                aborted = True
                break
        if stop() or aborted:
            break

        # Branch: wheelspin each cycle, or straight back to racing.
        if branch_mode == "wheelspin":
            # TODO: the wheelspin step needs a per-cycle spin count (finalised
            # when the branch is wired); for now it's a placeholder so the
            # scaffold never hangs on an unlimited spin loop.
            log_cb(_at("log_fa_step_spin_todo", lang))
            if stop():
                break
        # else "racing": fall through and loop back to the top.

    if aborted:
        log_cb(_at("log_fa_aborted", lang))
    log_cb(_at("log_fa_stopped", lang))
    status_cb(_at("status_stopped", lang))
