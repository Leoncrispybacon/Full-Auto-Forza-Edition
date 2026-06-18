# ============================================================
#  full_auto.py — Full Auto chained orchestrator
#  Loops the existing automations as one continuous farm:
#    AFK race (user count, for mastery points) → buy N cars →
#    unlock mastery on N cars → sell those N cars → branch:
#      • "wheelspin" → N wheelspins each cycle (1 car unlocked = 1 spin)
#      • "racing"    → straight back to racing (no wheelspin)
#  …repeating until Stop/F9. Steps chain via the game's MAIN MENU
#  as the common hand-off point (see each module's start/end-on-
#  menu navigation), except mastery→sell, which hand off via the
#  My Cars grid (mastery ends there with end_at_mycars).
#
#  STATUS: all steps wired.
#    • race / buy / wheelspin — reuse the standalone modules
#      (their own templates + settings); start & end on the menu.
#    • mastery — positioning nav (main menu → My Cars → newest car)
#      + grid-based tree unlock + top-down column-major car nav.
#    • sell — CHAINED-ONLY: re-select grind car (Filter→Favorites→
#      brand→car, also the exclude + the next race's car) → sort →
#      walk to the Nth car → sell N → 3-ESC exit to the main menu.
#  Each step is detection-gated + time-boxed; a step that can't
#  proceed aborts the run (no silent fall-through to the next cycle).
# ============================================================

import time
import threading

import config
from config import (get_full_auto_templates, get_full_auto_grid_file,
                    resolve_template_lang, REFERENCE_RES)
from app_lang import t as _at
from capture import (load_template, force_english_ime,
                     find_game_window, get_window_pid, set_process_muted)
from detector import ScreenDetector
from gameio import GameIO, set_mute_held, set_session_crop
import race as _race
import buy as _buy
import mastery as _mastery
import wheelspin as _wheelspin

# Per-function startup chatter suppressed in the Full Auto log (each chained
# step + its GameIO re-emit these every cycle, which buries the chain log).
# GameIO logs through the SAME log_cb the modules use, so a wrapped log_cb
# catches both. Fragments are derived from the localized templates (below) so
# the filter works in any language.
_QUIET_LOG_KEYS = (
    "log_bg_input_on", "log_bg_window_size", "log_bg_capture_window",
    "log_bg_letterbox", "log_bg_keep_active", "log_game_muted",
    "log_template_loaded",
    "log_race_started", "log_race_started_count",
    "log_mastery_started", "log_mastery_started_count",
    "log_delete_started", "log_delete_started_count",
    "log_spin_started", "log_spin_started_count",
)
_QUIET_SENTINEL = "\x00"
_QUIET_KWARGS = dict(key=_QUIET_SENTINEL, scale=_QUIET_SENTINEL,
                     n=_QUIET_SENTINEL, w=_QUIET_SENTINEL, h=_QUIET_SENTINEL)


def _make_quiet_log(real_log, lang):
    """Wrap a log fn to drop the per-function startup chatter (GameIO bring-up,
    'started', template-loaded). Renders each noise template with a sentinel and
    keeps the stable literal prefix, so a message is dropped iff it starts with
    one of those prefixes. Everything else (per-action logs, nav narration,
    errors, Full Auto's own lines) passes through."""
    frags = []
    for k in _QUIET_LOG_KEYS:
        try:
            s = _at(k, lang, **_QUIET_KWARGS)
        except Exception:
            continue
        if s == f"[{k}]":            # missing key — skip
            continue
        frag = s.split(_QUIET_SENTINEL)[0].strip()
        if len(frag) >= 5:           # avoid over-broad fragments
            frags.append(frag)

    def _log(msg):
        m = (msg or "").strip()
        if any(m.startswith(f) for f in frags):
            return
        real_log(msg)
    return _log


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

# ── Sell step (chained-only) ─────────────────────────────────
# The My Cars garage grid is laid out COLUMN-MAJOR with this many rows per column
# (1,2,3 down column 1; 4,5,6 down column 2; …), confirmed from the in-game grid.
# Jump-to-Recently-Added lands on the newest car (top-left = car #1); to reach
# the Nth car we cross (N-1)//ROWS columns (Right) and step (N-1)%ROWS down.
_GARAGE_ROWS = 3
# After the "get in" Enter that rides the grind car (user-specified ~0.5s),
# before re-entering My Cars. Riding an already-owned car plays NO cutscene.
_SELL_RIDE_SETTLE = 0.5
# Grind-car re-select elements move (Manufacturer menu size varies; car row
# varies), so they use their large DEFAULT_ROI rather than a tight geometry box.
_SELL_NO_GEOM = frozenset({"grind_brand", "grind_car"})


def _grid_moves_for_count(n: int):
    """(rights, downs) to reach the Nth car from the newest in the column-major,
    3-rows-per-column My Cars grid. e.g. 33 → (10, 2); 8 → (2, 1); 1 → (0, 0)."""
    idx = max(1, int(n)) - 1
    return idx // _GARAGE_ROWS, idx % _GARAGE_ROWS


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
        if meta.get("roi"):                       # user-drawn ROI overrides
            detector.set_template_roi(key, meta["roi"])
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


def _sell_sequence(cfg: dict, stop_event: threading.Event,
                   log_cb, status_cb, sell_count: int) -> bool:
    """Chained-only sell step. Mastery (end_at_mycars) leaves us in My Cars
    (unsorted) on the last-mastered car. Sequence:

      Right → Enter → Enter   ride a non-target neighbour (the active car can't
                              be sold, so this protects a throwaway from the block;
                              no cutscene for an already-owned car → no ESC)
      click My Cars           back into the grid
      X → click Recently Added → Backspace → Enter   re-sort, jump to newest (car #1)
      Right ×R, Down ×D       walk to the Nth car (R,D from _grid_moves_for_count)
      sell macro ×N           Enter→Down×4→Enter→Down×1→Enter per car (mirrors
                              delete_cars; the grid auto-advances between sales)
      ESC → confirm cars_tab → ESC   back to the main menu (transition animation,
                              so we confirm the home menu between the two ESCs)

    Detection-gated + time-boxed (best-effort: missing templates → return False
    and the orchestrator stops). Every press is stop/F9-aware. Returns True only
    when the block is sold and we're back on the main menu."""
    fresh = config.load()
    lang  = fresh.get("lang", "en")
    res   = fresh.get("full_auto_resolution", "custom")
    fresh["detector_ocr_primary"] = (res != "custom")
    tpl_lang = resolve_template_lang(fresh)
    # Shared menu cursor-tap delay (same setting as mastery/delete).
    tap_wait = max(0.1, min(0.5, float(fresh.get("menu_tap_wait", 0.25))))

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

    def _load(folder, key, rf=None, pr=False, set_geom=True):
        img, scale, meta = load_template(folder, key, cw, ch, grayscale=True,
                                         ref_folder=rf, prefer_ref=pr)
        box = meta.get("box")
        if box and set_geom:
            detector.set_template_geometry(
                key, box, meta.get("screen_width", cw),
                meta.get("screen_height", ch))
        if meta.get("roi"):                       # user-drawn ROI overrides
            detector.set_template_roi(key, meta["roi"])
        return img

    tpls = {}
    try:
        # grind_brand/grind_car re-select the grind car; recently_added + cars_tab
        # are reused from the positioning-nav set; my_cars/my_cars_header/anna are
        # sell-only. grind_* skip geometry (large ROI — they move).
        for key in ("grind_brand", "grind_car", "my_cars", "my_cars_header",
                    "recently_added", "cars_tab", "anna"):
            tpls[key] = _load(fa_folder, key, ref_folder, prefer_ref,
                              set_geom=(key not in _SELL_NO_GEOM))
    except FileNotFoundError:
        log_cb(_at("log_fa_sell_skip", lang))
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

    def _click(key, window_s, label) -> bool:
        t0 = time.time()
        r  = _detect(key, window_s)
        secs = f"{time.time() - t0:.1f}"
        if r is None:
            if not stop():
                log_cb(_at("log_fa_sell_fail", lang, label=label, secs=secs))
            return False
        log_cb(_at("log_fa_mastery_nav_detected", lang, label=label,
                   conf=f"{r.score:.0%}, {r.source}", secs=secs))
        _wait(_NAV_SETTLE)
        if stop():
            return False
        io.click(r.location[0], r.location[1], _NAV_SETTLE)
        return True

    if not io.bg and fresh.get("auto_english_ime", True):
        force_english_ime()
        time.sleep(0.2)
    io.mute(fresh)
    io.start_keepalive(stop, fresh)
    log_cb(_at("log_fa_sell_begin", lang, n=sell_count))
    status_cb(_at("log_fa_sell_begin", lang, n=sell_count))

    try:
        # 0. Confirm mastery left us in a LOADED My Cars grid before pressing Y.
        #    The mastery→sell handoff (cleanup + fresh GameIO + template load)
        #    plus the grid's own load could otherwise eat the Y, same as the
        #    early-X issue. Gate on the invariant "My Cars" header.
        log_cb(_at("log_fa_sell_wait_grid", lang))
        if _detect("my_cars_header", _NAV_STEP_WINDOW) is None:
            if not stop():
                log_cb(_at("log_fa_sell_fail", lang,
                           label=_at("fa_tpl_my_cars_header", lang),
                           secs=f"{_NAV_STEP_WINDOW:.0f}"))
            return False
        # 1. Re-select the grind car. This does BOTH jobs at once: riding a
        #    non-22B makes the whole block sellable (the active car can't be
        #    sold), AND it leaves us driving the grind car for the next race.
        #    Filter → Favourites, jump to the brand, click the car. (Favourites
        #    resets on leaving My Cars, so the next cycle's mastery still sees
        #    the un-favourited 22Bs.)
        log_cb(_at("log_fa_sell_find_car", lang))
        io.press("y", post_wait=_NAV_SETTLE)             # open Filter
        if stop():
            return False
        io.press("enter", post_wait=0.3)                 # check Favourites (default)
        if stop():
            return False
        io.press("esc", post_wait=_NAV_SETTLE)           # close Filter (favourites applied)
        if stop():
            return False
        io.press("backspace", post_wait=_NAV_SETTLE)     # Jump to Manufacturer
        if stop():
            return False
        if not _click("grind_brand", _NAV_STEP_WINDOW, _at("fa_tpl_grind_brand", lang)):
            return False
        if not _click("grind_car", _NAV_STEP_WINDOW, _at("fa_tpl_grind_car", lang)):
            return False
        io.press("enter", post_wait=_SELL_RIDE_SETTLE)   # get in → CARS tab home
        if stop():
            return False
        # 2. Click My Cars → grid
        if not _click("my_cars", _NAV_STEP_WINDOW, _at("fa_tpl_my_cars", lang)):
            return False
        # 2b. Wait for the grid to finish loading before sorting. Pressing X
        #     mid-load drops the sort menu (observed), so gate it on the
        #     invariant "My Cars" header (top-left) appearing.
        log_cb(_at("log_fa_sell_wait_grid", lang))
        if _detect("my_cars_header", _NAV_STEP_WINDOW) is None:
            if not stop():
                log_cb(_at("log_fa_sell_fail", lang,
                           label=_at("fa_tpl_my_cars_header", lang),
                           secs=f"{_NAV_STEP_WINDOW:.0f}"))
            return False
        # 3. X → Recently Added → Backspace → Enter (jump to newest = car #1)
        log_cb(_at("log_fa_sell_sort", lang))
        io.press("x", post_wait=_NAV_SETTLE)
        if stop():
            return False
        if not _click("recently_added", _NAV_STEP_WINDOW,
                      _at("fa_tpl_recently_added", lang)):
            return False
        io.press("backspace", post_wait=_NAV_SETTLE)
        if stop():
            return False
        io.press("enter", post_wait=_NAV_SETTLE)          # jump to newest car
        if stop():
            return False
        # 4. Walk to the Nth car (column-major, 3 rows): Right ×R, Down ×D.
        rights, downs = _grid_moves_for_count(sell_count)
        log_cb(_at("log_fa_sell_position", lang, n=sell_count, r=rights, d=downs))
        for _ in range(rights):
            if stop():
                return False
            io.press("right", post_wait=tap_wait)
        for _ in range(downs):
            if stop():
                return False
            io.press("down", post_wait=tap_wait)
        if stop():
            return False
        # 5. Sell macro ×N — mirrors delete_cars (the grid auto-advances between
        #    sales, so the cursor stays on a to-sell car each iteration).
        log_cb(_at("log_fa_sell_macro", lang, n=sell_count))
        for i in range(sell_count):
            if stop():
                return False
            io.press("enter", post_wait=1.2)              # open action menu
            if stop():
                return False
            for _ in range(4):
                if stop():
                    return False
                io.press("down", post_wait=tap_wait)      # → Remove / Sell
            io.press("enter", post_wait=1.0)              # select it
            if stop():
                return False
            io.press("down", post_wait=tap_wait)          # → Yes
            io.press("enter", post_wait=1.5)              # confirm sale
            log_cb(_at("log_fa_sell_car", lang, i=i + 1, n=sell_count))
        if stop():
            return False
        # 6. Exit back to the MAIN menu — three ESCs, each gated on an anchor:
        #    ESC → home menu (confirm cars_tab) → ESC → open-world driving
        #    (confirm the ANNA prompt, bottom-left) → ESC → main menu.
        #    (ESC from the home menu backs out to the open world, NOT the main
        #    menu, so the third ESC is required.)
        log_cb(_at("log_fa_sell_exit", lang))
        io.press("esc", post_wait=_NAV_SETTLE)                 # My Cars → home
        if stop():
            return False
        if _detect("cars_tab", _NAV_STEP_WINDOW) is None:
            if not stop():
                log_cb(_at("log_fa_sell_fail", lang,
                           label=_at("fa_tpl_cars_tab", lang),
                           secs=f"{_NAV_STEP_WINDOW:.0f}"))
            return False
        io.press("esc", post_wait=_NAV_SETTLE)                 # home → open world
        if stop():
            return False
        log_cb(_at("log_fa_sell_wait_world", lang))
        if _detect("anna", _NAV_STEP_WINDOW) is None:
            if not stop():
                log_cb(_at("log_fa_sell_fail", lang,
                           label=_at("fa_tpl_anna", lang),
                           secs=f"{_NAV_STEP_WINDOW:.0f}"))
            return False
        io.press("esc", post_wait=_NAV_SETTLE)                 # open world → main
        log_cb(_at("log_fa_sell_at_menu", lang))
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
    branch_mode: "racing" (no wheelspin) | "wheelspin" (spin each cycle). The
                wheelspin step does car_count spins (1 car unlocked = 1 spin).
    start_from: which step the FIRST cycle begins at — a STEP_ORDER step, or
                "spin" (wheelspin branch only) to begin at the spin step. Cycle
                2+ always runs the full loop from racing.
    """
    section = section_cb or log_cb
    lang    = cfg.get("lang", "en")
    # Sub-runs (and their GameIOs) re-emit startup chatter every step — route
    # their logs through a filter so the chain log stays readable. Full Auto's
    # OWN narration uses the raw log_cb (cycle/step headers).
    quiet_log = _make_quiet_log(log_cb, lang)
    if car_count <= 0:
        car_count = CAR_COUNT
    # "spin" start is only meaningful in wheelspin mode; otherwise fall back to
    # race so cycle 1 isn't an empty no-op.
    if start_from == "spin" and branch_mode != "wheelspin":
        start_from = "race"
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
        _race.run(cfg, stop_event, quiet_log, status_cb,
                  max_loops=race_count, section_cb=section_cb)
        return True

    def _step_buy():
        status_cb(_at("log_fa_step_buy", lang))
        log_cb(_at("log_fa_step_buy", lang, n=car_count))
        _buy.run(cfg, stop_event, quiet_log, status_cb,
                 max_loops=car_count, section_cb=section_cb)
        return True

    def _step_mastery():
        # Navigate main menu → My Cars → newest car, then run the per-car loop.
        status_cb(_at("log_fa_step_mastery", lang, n=car_count))
        log_cb(_at("log_fa_step_mastery", lang, n=car_count))
        if not _navigate_to_mastery_start(cfg, stop_event, quiet_log, status_cb):
            # Nav failed (templates missing / a step never appeared) → can't
            # position for mastery. Don't silently skip into the next cycle; stop.
            return False
        if stop():
            return True   # stopped mid-nav — the outer loop handles it
        # Full Auto uses its OWN mastery-tree grid spec (the 22B tree).
        # end_at_mycars: the final car stops in My Cars (no step-11 sort) so the
        # sell step can ride the non-target car first.
        grid_file = get_full_auto_grid_file(resolve_template_lang(cfg))
        # start_loop=1: the positioning nav lands on the newest car (top-left,
        # row 1), so force row 1 — the standalone mastery_start_loop must not
        # leak in (it would offset the snake and fire the column D one car early).
        _mastery.run(cfg, stop_event, quiet_log, status_cb,
                     max_cars=car_count, section_cb=section_cb,
                     grid_file=grid_file, end_at_mycars=True, start_loop=1)
        return True

    def _step_sell():
        # Ride a non-target car → re-sort → walk to the Nth car → sell N → menu.
        status_cb(_at("log_fa_step_sell", lang, n=car_count))
        log_cb(_at("log_fa_step_sell", lang, n=car_count))
        if not _sell_sequence(cfg, stop_event, quiet_log, status_cb, car_count):
            # Templates missing / a step never appeared → can't sell safely. Stop
            # rather than fall through (don't risk an unverified destructive run).
            return False
        return True

    def _step_spin():
        # Branch step: from the main menu (where sell left us), wheelspin clicks
        # the My Horizon tab → Super Wheelspin → spins car_count times (1 car
        # unlocked = 1 wheelspin earned), ending on the My Horizon menu. Reuses
        # the Wheelspin tab's OWN templates + settings (type super/normal, dup
        # garage/sell). The next cycle's race picks up via its creative_hub poll
        # (same top nav, visible from My Horizon). No failure signal — F9 recovers.
        status_cb(_at("log_fa_step_spin", lang, n=car_count))
        log_cb(_at("log_fa_step_spin", lang, n=car_count))
        _wheelspin.run(cfg, stop_event, quiet_log, status_cb,
                       max_loops=car_count, section_cb=section_cb)
        return True

    _steps = {"race": _step_race, "buy": _step_buy,
              "mastery": _step_mastery, "sell": _step_sell}

    log_cb(_at("log_fa_started", lang))
    if race_count <= 0:
        # Unlimited race never returns to the menu, so the cycle can't progress.
        log_cb(_at("log_fa_race_count_warn", lang))

    # Detect the letterbox crop ONCE for the whole run and reuse it across every
    # step (the window doesn't resize mid-run) — avoids re-detecting on each
    # step's arbitrary start screen. Reset in finally.
    set_session_crop(True)

    # Mute ONCE for the whole run (if enabled) and hold it, so per-step GameIOs
    # don't un-mute between functions. Released in finally.
    mute_on  = bool(config.load().get("mute_game", False))
    mute_pid = None
    if mute_on:
        set_mute_held(True)
        try:
            _hwnd = find_game_window(cfg.get("background_window_title",
                                             "Forza Horizon 6"))
            if _hwnd:
                _pid = get_window_pid(_hwnd)
                if _pid and set_process_muted(_pid, True):
                    mute_pid = _pid
                    log_cb(_at("log_fa_muted", lang))
        except Exception:
            pass

    cycle   = 0
    aborted = False
    try:
        while not stop() and not aborted:
            cycle += 1
            section(_at("log_fa_cycle", lang, n=cycle))

            # Cycle 1 begins at the chosen start step; later cycles run the full
            # loop. start_from="spin" skips all linear steps so cycle 1 is the
            # wheelspin branch only (begin past the end → empty linear slice).
            if cycle == 1 and start_from == "spin":
                begin = len(STEP_ORDER)
            else:
                begin = start_idx if cycle == 1 else 0
            for step_key in STEP_ORDER[begin:]:
                if stop():
                    break
                ok = _steps[step_key]()
                if stop():
                    break
                if not ok:
                    # A step couldn't proceed and we weren't stopped — abort the
                    # whole run rather than fall through into another cycle.
                    aborted = True
                    break
            if stop() or aborted:
                break

            # Branch: wheelspin each cycle (car_count spins), or back to racing.
            if branch_mode == "wheelspin":
                _step_spin()
                if stop():
                    break
            # else "racing": fall through and loop back to the top.
    finally:
        # Release the session mute (and the hold) no matter how we exit.
        if mute_on:
            if mute_pid is not None:
                try:
                    set_process_muted(mute_pid, False)
                except Exception:
                    pass
            set_mute_held(False)
        set_session_crop(False)   # drop the cached crop for the next run

    if aborted:
        log_cb(_at("log_fa_aborted", lang))
    log_cb(_at("log_fa_stopped", lang))
    status_cb(_at("status_stopped", lang))
