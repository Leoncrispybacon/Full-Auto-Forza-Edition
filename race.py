# ============================================================
#  automation/race.py — Race automation logic
#  All output goes through log_cb(message) instead of print()
#  Stop is signalled via stop_event (threading.Event)
# ============================================================

import cv2
import numpy as np
import time
import threading
import ctypes
from ctypes import wintypes

import config
from config import get_race_templates, get_nodes_file
from app_lang import t as _at
from capture import (grab_frame, load_template, get_monitor_dims,
                     force_english_ime, get_foreground_window, focus_window,
                     mouse_click, find_game_window, post_key, post_click,
                     get_client_rect, grab_region, set_window_active, grab_window,
                     post_client_click, get_window_pid, set_process_muted)
from detector import ScreenDetector
from gameio import GameIO




# Keys
_VK_MAP = {
    'enter':  0x0D, 'return': 0x0D,
    'x':      0x58,
    'w':      0x57,
    'escape': 0x1B, 'esc': 0x1B,
    'f9':     0x78,
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
_KEYEVENTF_SCANCODE    = 0x0008
# VKs that map to an extended scancode (none used here, kept for safety if
# extended keys are ever added — see delete_cars.py for the rationale).
_EXTENDED_VKS = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                           0x2D, 0x2E, 0xA3, 0xA5})

def _vk_for_key(name: str):
    """Virtual-key code for a toggle-key name (e.g. 'f9', 'enter'), for
    GetAsyncKeyState polling. Handles F1–F24 and the keys in _VK_MAP."""
    name = (name or "").strip().lower()
    if name in _VK_MAP:
        return _VK_MAP[name]
    if name.startswith("f") and name[1:].isdigit():
        n = int(name[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)   # VK_F1 = 0x70
    if len(name) == 1:
        return ord(name.upper())    # letters / digits
    return None


def _send_vk(key_name, key_up=False):
    vk = _VK_MAP.get(key_name.lower())
    if vk is None:
        return
    # Send BOTH the virtual key (wVk) and the hardware scancode (wScan) so the
    # game receives input whether it reads the Windows message / VK path
    # (WM_KEYDOWN / GetAsyncKeyState) or the DirectInput / Raw Input scancode
    # path. Scancode-only (wVk=0) regressed VK-path games — notably the held W
    # during a race; VK-only (wScan=0) leaves DirectInput games with scancode
    # 0. Populating both is the most compatible. The CJK IME is handled
    # separately by capture.force_english_ime() at the start of the run.
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
    flags = _KEYEVENTF_KEYUP if key_up else 0
    if vk in _EXTENDED_VKS:
        flags |= _KEYEVENTF_EXTENDEDKEY
    inp = _INPUT(type=1, union=_INPUT_UNION(
        ki=_KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags,
                       time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

def _send_scancode(key_name, key_up=False):
    """Scancode injection WITH the KEYEVENTF_SCANCODE flag (wVk=0) — the
    DirectInput / Raw Input path the game uses for *gameplay* (held W). This is
    the same method pydirectinput uses for mastery's WASD nav, which works
    in-game. The dual `_send_vk` (no SCANCODE flag) is fine for menu taps but
    doesn't register as a true held key for driving."""
    vk = _VK_MAP.get(key_name.lower())
    if vk is None:
        return
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
    flags = _KEYEVENTF_SCANCODE | (_KEYEVENTF_KEYUP if key_up else 0)
    if vk in _EXTENDED_VKS:
        flags |= _KEYEVENTF_EXTENDEDKEY
    inp = _INPUT(type=1, union=_INPUT_UNION(
        ki=_KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags,
                       time=0, dwExtraInfo=None)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

def key_down(key): _send_vk(key, key_up=False)
def key_up(key):   _send_vk(key, key_up=True)

def key_press(key, post_wait=1.5):
    _send_vk(key, key_up=False)
    time.sleep(0.05)
    _send_vk(key, key_up=True)
    time.sleep(post_wait)


# ── Template matching ─────────────────────────────────────────

def _screen_matches(screen, template, threshold):
    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        return False, 0.0
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, best_conf, _, _ = cv2.minMaxLoc(result)
    return best_conf >= threshold, best_conf


# ── Main runner ───────────────────────────────────────────────

# Two detections: the Start Race screen (start_menu) and the race-END screen
# (restart_menu). start_menu is detected — NOT timed — because the load time
# between finishing a race and the next Start Race screen varies. racing /
# confirm remain blind timing.
TEMPLATE_KEYS = ["start_menu", "restart_menu"]

# Fixed step waits (seconds) for the timed steps.
_PRE_W_WAIT   = 4.0    # step 3: after pressing Enter, wait before holding W
_CONFIRM_WAIT = 1.25   # step 6: after pressing X, wait before Enter (confirm)
# Settle before each menu-navigation action: the element is often detected mid-
# animation, but the game drops input until the transition finishes. A short
# wait before acting makes the click/Enter land reliably (esp. in background
# mode, where PostMessage taps can arrive even earlier in the animation).
_NAV_SETTLE   = 0.3


def run(cfg: dict, stop_event: threading.Event,
        log_cb, status_cb, max_loops: int = 0,
        warn_cb=None, section_cb=None):
    """
    Main race automation loop.
    cfg: config dict
    stop_event: set this to stop
    log_cb(msg): append a line to the log
    status_cb(msg): update the status bar
    max_loops: stop after this many completed races (0 = unlimited)
    section_cb(msg): start a new (bounded) log section; falls back to log_cb
    """
    section = section_cb or log_cb

    lang          = cfg.get("lang", "en")
    monitor_index = cfg.get("monitor_index", 1)
    # Per-template thresholds
    def _thresh(key):
        return _fresh.get(f'thresh_{key}', 0.80)

    check_iv      = cfg.get("race_check_interval", 0.5)
    post_kw       = cfg.get("race_post_key_wait", 0.75)

    START_RACE_KEY = 'enter'
    RESTART_KEY    = 'x'
    CONFIRM_KEY    = 'enter'

    # Load templates
    current_w, current_h, mon_left, mon_top = get_monitor_dims(monitor_index)
    templates = {}
    # Always read resolution fresh from config.json at start
    import config as _cfg_mod
    _fresh = _cfg_mod.load()
    tpl_lang = _cfg_mod.resolve_template_lang(_fresh)
    # Single built-in template set (REFERENCE_RES), auto-scaled to the monitor.
    folder   = get_race_templates(_cfg_mod.REFERENCE_RES, tpl_lang)
    ref_folder = folder
    prefer_ref = _fresh.get('template_prefer_reference', True)
    log_cb(f"  Templates: {tpl_lang} / built-in")
    # VK of the stop hotkey, for the hook-independent stop poll in stop().
    _toggle_vk = _vk_for_key(_fresh.get('toggle_key', 'f9'))
    detector = ScreenDetector(_fresh)

    # ── Window-aware IO (gameio.GameIO) — shared by every function ──
    # Auto-adapts: if the game window is found, FAFE drives it through the window
    # (client-area capture + PostMessage) so detection sizes to the window
    # (windowed OR borderless) and input works whether the game is focused or
    # not; a keep-alive stops it auto-pausing while unfocused. If the window
    # isn't found, it falls back to whole-monitor capture + SendInput.
    io = GameIO(_fresh, log_cb)
    current_w, current_h = io.width, io.height
    mon_left, mon_top = io.cap_left, io.cap_top
    io.mute(_fresh)

    def _grab():
        return io.grab()

    def _kp(key, post_wait=post_kw):
        io.press(key, post_wait=post_wait)

    def _click(fx, fy):
        io.click(fx, fy, post_kw)
    for key in TEMPLATE_KEYS:
        try:
            img, scale, meta = load_template(folder, key,
                                       current_w, current_h, grayscale=True,
                                       ref_folder=ref_folder, prefer_ref=prefer_ref)
            templates[key] = img
            _box = meta.get("box")
            if _box:
                detector.set_template_geometry(
                    key, _box, meta.get("screen_width", current_w),
                    meta.get("screen_height", current_h))
            log_cb(_at("log_template_loaded", cfg.get("lang","en"), key=key, scale=f"{scale:.2f}"))
        except FileNotFoundError:
            log_cb(_at("log_template_missing", cfg.get("lang","en"), key=key))
            status_cb(_at("status_setup_incomplete", cfg.get("lang","en")))
            io.cleanup()   # mute already ran above — always unmute on exit
            return

    # ── Optional menu-navigation templates ──
    # If ALL are captured, the script can walk main menu → CREATIVE HUB →
    # EventLab → Play Event → MY HISTORY → Solo → car → Start screen before the
    # AFK loop (the bridge for chaining other functions into racing). Best-
    # effort: missing any of them disables navigation and we just wait for the
    # Start screen as before — so existing race setups are unaffected.
    NAV_KEYS = ["creative_hub", "eventlab", "play_event", "events_arrow",
                "my_history", "choose_race_type", "car_select"]
    nav_tpls = {}
    for key in NAV_KEYS:
        try:
            img, scale, meta = load_template(folder, key, current_w, current_h,
                                       grayscale=True, ref_folder=ref_folder,
                                       prefer_ref=prefer_ref)
            nav_tpls[key] = img
            _box = meta.get("box")
            if _box:
                detector.set_template_geometry(
                    key, _box, meta.get("screen_width", current_w),
                    meta.get("screen_height", current_h))
        except FileNotFoundError:
            pass
    nav_enabled = all(k in nav_tpls for k in NAV_KEYS)

    # ── Optional exit template (results → main menu) ──
    # Lets the run END on the main menu when the race count is reached: press
    # Continue, wait through the loading screen for the recommended "What's
    # Next" menu, then Esc back out to the main menu. This is the chaining
    # hand-off (every function ends on the main menu). Needs next_activity AND
    # creative_hub (the main-menu marker). Best-effort: if either is missing the
    # run just stops on the results screen as before.
    exit_tpl = None
    try:
        img, scale, meta = load_template(folder, "next_activity",
                                   current_w, current_h, grayscale=True,
                                   ref_folder=ref_folder, prefer_ref=prefer_ref)
        exit_tpl = img
        _box = meta.get("box")
        if _box:
            detector.set_template_geometry(
                "next_activity", _box, meta.get("screen_width", current_w),
                meta.get("screen_height", current_h))
    except FileNotFoundError:
        pass
    exit_enabled = exit_tpl is not None and "creative_hub" in nav_tpls

    def stop():
        if stop_event.is_set():
            return True
        # Hook-independent stop. While holding W we inject ~33 keydowns/sec via
        # SendInput; that flood goes through the same low-level keyboard hook the
        # `keyboard` library uses for the F9 hotkey, and under it the hook can
        # fail to deliver F9 — so the script "can't be stopped" mid-race. Reading
        # the physical key state directly (GetAsyncKeyState, high bit = down)
        # bypasses the hook entirely. The W-hold thread calls stop() at ~33Hz so
        # even a quick tap is caught.
        if _toggle_vk:
            try:
                if ctypes.windll.user32.GetAsyncKeyState(_toggle_vk) & 0x8000:
                    stop_event.set()
                    return True
            except Exception:
                pass
        return False

    def wait_for(label, template, key, timeout=float('inf'), warn=True):
        # warn=False suppresses the 10s "not detected" red warning for steps
        # where a long wait is NORMAL — e.g. waiting for the Restart menu, which
        # only appears once the whole race finishes (far more than 10s).
        # Detection still continues; only the noisy warning is silenced.
        status_cb(_at("status_waiting_for", lang, label=label))
        def _warn(best):
            msg = _at("log_warn_not_detected", lang, label=label)
            msg += f" (best {best.source}: {best.score:.0%})"
            (warn_cb or log_cb)(msg)

        result = detector.wait_for(
            frame_cb=_grab,
            key=key,
            template=template,
            threshold=_thresh(key),
            stop_cb=stop,
            interval=check_iv,
            timeout=timeout,
            on_warn=_warn if warn else None,
        )
        if result.matched:
            log_cb(_at("log_detected", lang, label=label,
                       conf=f"{result.score:.0%}"))
            return True
        return False

    def press(key, label):
        log_cb(_at("log_pressing", lang, key=key.upper(), label=label))
        _kp(key, post_wait=post_kw)

    def wait(seconds):
        """Stop-aware sleep so F9/Stop isn't blocked by the fixed timing waits."""
        end = time.time() + seconds
        while time.time() < end:
            if stop():
                return
            time.sleep(0.1)

    def announce(msg):
        """Log a step AND reflect it in the status bar / overlay (the fixed
        waits have no detection to drive status, so set it explicitly)."""
        log_cb(msg)
        status_cb(msg)

    log_cb(_at("log_race_started", cfg.get("lang","en")))
    if max_loops > 0:
        log_cb(_at("log_race_started_count", lang, n=max_loops))
    # Switch the game to English input only if it isn't already (see
    # capture.force_english_ime). Disable entirely with auto_english_ime=false
    # for users who manage their IME themselves.
    # force_english_ime acts on the FOREGROUND window; in background mode the
    # game isn't focused, so skip it (it would target the wrong window).
    if not io.bg and _fresh.get("auto_english_ime", True):
        force_english_ime()
        time.sleep(0.2)

    # Background keep-alive: re-assert "active" to the game window so it doesn't
    # auto-pause while unfocused. Experimental — works only if the game trusts
    # the activation messages (see capture.set_window_active). Runs for the whole
    # run (menus + race) on a daemon thread; stopped in the cleanup below.
    io.start_keepalive(stop, _fresh)

    # ── Optional: navigate the menus to the Start screen ──
    # Each step is detection-GATED and TIME-BOXED (unlike the in-race loop's
    # infinite wait): a wrong/stuck menu state won't self-correct, so aborting
    # beats hanging. Steps detect distinct screens in sequence, so there's no
    # lingering/re-press problem.
    _NAV_STEP_WINDOW = 12.0
    # MY HISTORY → Race type: selecting the history entry loads the event for an
    # uncertain time, and the first Enter can be dropped. We re-press Enter ONLY
    # while MY HISTORY is still on screen (see _enter_until) — never on a blind
    # timer — because every screen here (Race Type, car select, Start) advances
    # on Enter, so a blind re-press could cascade into the race. After each press
    # we wait _NAV_PRESS_COOLDOWN for the menu to transition off the source
    # before re-checking (a registered Enter clears MY HISTORY promptly), up to
    # _NAV_LOAD_WINDOW total (generous, to cover a slow load).
    _NAV_PRESS_COOLDOWN = 1.2
    _NAV_LOAD_WINDOW    = 45.0

    def _detect_nav(key, window_s):
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return None
            try:
                r = detector.detect(_grab(), key,
                                    nav_tpls[key], _thresh(key), stable=False)
                if r.matched:
                    return r
            except Exception:
                pass
            time.sleep(0.15)
        return None

    def _enter_until(source_key, target_key, window):
        """Advance from the SOURCE screen to the TARGET screen by pressing Enter,
        re-pressing ONLY while the source screen is still positively detected —
        never on a blind timer. Failsafe for the MY HISTORY step: the event loads
        for an uncertain time and the confirming Enter can be dropped, so it must
        be re-triggered. But every screen in this stretch (Race Type, car select,
        Start) advances on Enter, so a blind re-press could cascade through all of
        them into the race. Pressing only while `source` is still on screen makes
        overshoot impossible: an already-advanced menu is never pressed.

        Per iteration: target detected → return True. Source still detected → the
        Enter was dropped / not yet processed → press Enter, then wait
        _NAV_PRESS_COOLDOWN for the menu to leave source before re-checking (a
        registered Enter clears MY HISTORY promptly, so this won't double-press).
        Neither (loading/transition) → wait, do NOT press. Returns False on
        timeout/stop (a clean abort, far safer than launching a race)."""
        end = time.time() + window
        presses = 0
        while time.time() < end:
            if stop():
                return False
            on_source = False
            try:
                frame = _grab()
                if detector.detect(frame, target_key, nav_tpls[target_key],
                                   _thresh(target_key), stable=False).matched:
                    return True
                on_source = detector.detect(
                    frame, source_key, nav_tpls[source_key],
                    _thresh(source_key), stable=False).matched
            except Exception:
                on_source = False
            if on_source:
                _kp('enter', post_wait=0.0)
                presses += 1
                if presses > 1:
                    log_cb(_at("log_race_nav_retry", lang,
                               label=_at("race_tpl_" + target_key, lang)))
                wait(_NAV_PRESS_COOLDOWN)   # let a registered Enter clear source
            else:
                time.sleep(0.2)             # loading/transition — wait, don't press
        return False

    def _detect_start_state(window_s):
        """Decide where we are: ('creative_hub'|'start_menu', result) for
        whichever appears first, else (None, None)."""
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return (None, None)
            try:
                frame = _grab()
                rc = detector.detect(frame, "creative_hub",
                                     nav_tpls["creative_hub"],
                                     _thresh("creative_hub"), stable=False)
                if rc.matched:
                    return ("creative_hub", rc)
                rs = detector.detect(frame, "start_menu",
                                     templates["start_menu"],
                                     _thresh("start_menu"), stable=False)
                if rs.matched:
                    return ("start_menu", rs)
            except Exception:
                pass
            time.sleep(0.15)
        return (None, None)

    def _navigate_to_event(ch_hit):
        """Main menu → CREATIVE HUB → EventLab → Play Event → MY HISTORY →
        Solo → car → Start screen. ch_hit = the creative_hub match already in
        hand. Returns True on success, False if a step's element never appears
        (abort) or we were stopped."""
        announce(_at("log_race_nav_begin", lang))
        lbl = _at("race_tpl_creative_hub", lang)
        log_cb(_at("log_race_nav_click", lang, label=lbl))
        wait(_NAV_SETTLE)
        _click(ch_hit.location[0], ch_hit.location[1])
        # Per step: (key, action, pre_wait). pre_wait is a settle BEFORE acting,
        # for screens that animate in — the element is detected mid-transition
        # but the game drops input until the transition finishes. A uniform
        # _NAV_SETTLE before every step keeps the click/Enter from landing too
        # early (the main fix for nav breaking in background mode).
        # 4th field = retry_to: after Entering this step, re-press Enter until
        # that next screen appears (failsafe for an uncertain load). Only
        # MY HISTORY uses it (the event load time varies; a dropped Enter would
        # otherwise time out and abort).
        steps = [("eventlab", "click", _NAV_SETTLE, None),
                 ("play_event", "click", _NAV_SETTLE, None),
                 ("events_arrow", "click", _NAV_SETTLE, None),
                 ("my_history", "enter", _NAV_SETTLE, "choose_race_type"),
                 ("choose_race_type", "enter", _NAV_SETTLE, None),
                 ("car_select", "enter", _NAV_SETTLE, None)]
        for key, action, pre_wait, retry_to in steps:
            lbl = _at("race_tpl_" + key, lang)
            t0 = time.time()
            r = _detect_nav(key, _NAV_STEP_WINDOW)
            secs = f"{time.time() - t0:.1f}"
            if r is None:
                if not stop():
                    log_cb(_at("log_race_nav_fail", lang, label=lbl, secs=secs))
                return False
            log_cb(_at("log_race_nav_detected", lang, label=lbl,
                       conf=f"{r.score:.0%}, {r.source}", secs=secs))
            if pre_wait:
                wait(pre_wait)
                if stop():
                    return False
            if action == "click":
                log_cb(_at("log_race_nav_click", lang, label=lbl))
                _click(r.location[0], r.location[1])
            elif retry_to:
                log_cb(_at("log_race_nav_enter", lang, label=lbl))
                # Source-gated: re-press Enter only while still on this step's
                # screen (`key`, e.g. MY HISTORY), until the target (retry_to)
                # appears — never blindly, so we can't cascade past Race Type /
                # car select / Start into the race.
                if not _enter_until(key, retry_to, _NAV_LOAD_WINDOW):
                    if not stop():
                        log_cb(_at("log_race_nav_fail", lang,
                                   label=_at("race_tpl_" + retry_to, lang),
                                   secs=f"{_NAV_LOAD_WINDOW:.0f}"))
                    return False
            else:
                log_cb(_at("log_race_nav_enter", lang, label=lbl))
                _kp('enter', post_wait=post_kw)
            if stop():
                return False
        log_cb(_at("log_race_nav_done", lang))
        return True

    if nav_enabled and not stop():
        _which, _hit = _detect_start_state(8.0)
        if _which == "creative_hub":
            if not _navigate_to_event(_hit):
                log_cb(_at("log_race_stopped", cfg.get("lang", "en")))
                status_cb(_at("status_stopped", lang))
                io.cleanup()   # always unmute / stop keep-alive on nav abort
                return
        elif _which == "start_menu":
            log_cb(_at("log_race_at_start", lang))
        # else: neither within the window — fall through to the loop's
        # wait_for(start_menu), which handles wherever the user actually is.

    loop_count = 0
    def _release_w():
        # GameIO posts the keyup straight to the game window (background) or sends
        # VK + scancode keyups (foreground) — focus-independent either way.
        io.release('w')

    # ── Race exit → main menu (fires once, on the count-reached clean exit) ──
    # Generous window: after Continue the game shows a ~12s loading screen
    # before the "What's Next" menu appears.
    _EXIT_MENU_WINDOW    = 30.0
    _EXIT_CONFIRM_WINDOW = 12.0
    _EXIT_WORLD_WAIT     = 4.0   # open-world transition after the first Esc

    def _detect_exit(key, tpl, window_s):
        end = time.time() + window_s
        while time.time() < end:
            if stop():
                return None
            try:
                r = detector.detect(_grab(), key, tpl,
                                    _thresh(key), stable=False)
                if r.matched:
                    return r
            except Exception:
                pass
            time.sleep(0.2)
        return None

    def _return_to_menu():
        """Results screen → main menu: Enter (Continue) → wait through the
        loading screen for the "What's Next" menu → Esc (close it → open world)
        → Esc (→ main menu) → confirm creative_hub. Best-effort / time-boxed:
        the run is already finishing, so a failed step logs and returns rather
        than hanging."""
        announce(_at("log_race_exit_begin", lang))
        log_cb(_at("log_race_exit_continue", lang))
        _kp('enter', post_wait=post_kw)                 # Continue, leave the race
        if stop():
            return
        t0 = time.time()
        r = _detect_exit("next_activity", exit_tpl, _EXIT_MENU_WINDOW)
        if r is None:
            if not stop():
                log_cb(_at("log_race_exit_fail", lang, secs=f"{time.time()-t0:.1f}"))
            return
        log_cb(_at("log_race_exit_menu_detected", lang,
                   conf=f"{r.score:.0%}, {r.source}", secs=f"{time.time()-t0:.1f}"))
        # Esc the recommended menu (→ open world), then Esc again (→ main menu).
        log_cb(_at("log_race_exit_esc_menu", lang))
        _kp('escape', post_wait=post_kw)
        if stop():
            return
        # The first Esc plays a transition INTO open-world gameplay; the second
        # Esc only opens the main menu once that transition has settled.
        wait(_EXIT_WORLD_WAIT)
        if stop():
            return
        log_cb(_at("log_race_exit_esc_world", lang))
        _kp('escape', post_wait=post_kw)
        if stop():
            return
        t0 = time.time()
        r = _detect_exit("creative_hub", nav_tpls["creative_hub"],
                         _EXIT_CONFIRM_WINDOW)
        if r is None:
            if not stop():
                log_cb(_at("log_race_exit_fail", lang, secs=f"{time.time()-t0:.1f}"))
            return
        log_cb(_at("log_race_at_menu", lang))

    while not stop():
        loop_count += 1
        section(f"-- {_at('log_loop', lang)} #{loop_count} --")

        # ── 1. Wait for the Start Race screen (DETECTED, not timed — the
        #       load time after a restart varies). On loop 1 the user is
        #       already here, so it detects immediately. ──────────────────
        wait_for("Start Race menu", templates["start_menu"], "start_menu")
        if stop(): break

        # ── 2. Press Enter to start the race ──────────────────────────
        press(START_RACE_KEY, "Start Race")
        if stop(): break

        # ── 3. Wait for the race to begin, then hold W ────────────────
        announce(_at("log_race_wait_start", lang))
        wait(_PRE_W_WAIT)
        if stop(): break

        log_cb(_at("log_holding_w", lang))
        status_cb(_at("status_racing", lang))
        # Hold W by re-asserting the keydown at ~30ms (the keyboard auto-repeat
        # rate) in a background thread. A single SendInput keydown isn't reliably
        # treated as a sustained hold by the game — it can register as a tap, so
        # the car coasts/slows. Re-pressing keeps it at full throttle whether the
        # game reads key STATE or keydown EVENTS. A single key_up at the end
        # releases it (auto-repeat is many keydowns + one keyup).
        _hold = threading.Event(); _hold.set()
        def _hold_w():
            while _hold.is_set() and not stop():
                io.hold_press('w')   # PostMessage (bg) or flagged scancode (fg)
                time.sleep(0.03)
        _ht = threading.Thread(target=_hold_w, daemon=True)
        _ht.start()

        # ── 4. Hold W until the Restart menu appears (ONLY detection) ─
        # The race lasts minutes, so the "not detected" warning is suppressed
        # (warn=False) — a long wait here is normal, not a detection problem.
        wait_for("Restart menu", templates["restart_menu"], "restart_menu",
                 warn=False)
        _hold.clear()
        _ht.join(timeout=0.3)
        _release_w()
        if stop(): break
        log_cb(_at("log_released_w", lang))

        # One full race completed. Stop here (on the results/restart screen)
        # when the requested number of races is reached, rather than kicking
        # off another race we'd immediately abandon.
        if max_loops > 0 and loop_count >= max_loops:
            log_cb(_at("log_race_limit_reached", lang, n=max_loops))
            # End on the main menu (the chaining hand-off) when the exit
            # templates are captured; otherwise stop on the results screen.
            if exit_enabled and not stop():
                _return_to_menu()
            break

        # ── 5. Release W (done above), press X to restart ─────────────
        press(RESTART_KEY, "Restart Race")

        # ── 6. Wait, then press Enter to confirm the restart ──────────
        wait(_CONFIRM_WAIT)
        if stop(): break
        press(CONFIRM_KEY, "Confirm")

    io.cleanup()     # stop keep-alive + unmute
    _release_w()     # safety release (W up to the game)
    log_cb(_at("log_race_stopped", cfg.get("lang","en")))
    status_cb(_at("status_stopped", lang))
