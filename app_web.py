"""
app_web.py — pywebview entry point for FAFE's new web UI (Phase 1).

Hosts webui/index.html in an Edge WebView2 window and exposes `Api` to the page
as `pywebview.api`. The automation backend (config, capture, full_auto, …) is
imported and driven UNCHANGED — this file is only the UI bridge.

Phase 1 wires: initial state (config + monitors + license), per-key config
persistence, monitor selection, and Full Auto start/stop with live log + status
streaming (the real full_auto.run on a worker thread). Other tabs come next.

Run:  python app_web.py     (the legacy CTk app still runs via forza_app.py)
"""
import collections
import ctypes
import json
import os
import sys
import threading
import time

import webview

import config
import capture
try:
    import full_auto as _full_auto    # paid feature; OMITTED from teaser/public builds
except Exception:
    _full_auto = None                 # absent → start_full_auto stays locked
from web_overlay import WebOverlay
from version import VERSION
from app_lang import t as _at


def _is_frozen() -> bool:
    """True in a packaged build — PyInstaller (sys.frozen) OR Nuitka (__compiled__).
    Used to turn DevTools off and harden the UI in release."""
    return bool(getattr(sys, "frozen", False) or globals().get("__compiled__"))


def _res_dir() -> str:
    """Directory holding bundled resources (webui/, …). PyInstaller exposes
    _MEIPASS; Nuitka/dev resolve relative to this file."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _webui(*parts) -> str:
    return os.path.join(_res_dir(), "webui", *parts)


# ── Edge WebView2 runtime (required; default on Win11, often missing on Win10) ──
_WV2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"   # WebView2 Evergreen Runtime
_WV2_LINK = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"  # official bootstrapper


def _webview2_installed() -> bool:
    """True if the Edge WebView2 Runtime is registered (per-machine or per-user).
    Non-Windows / unreadable registry → assume present (don't block)."""
    try:
        import winreg
    except Exception:
        return True
    base = r"SOFTWARE\Microsoft\EdgeUpdate\Clients" + "\\" + _WV2_GUID
    wow = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients" + "\\" + _WV2_GUID
    for root, path in ((winreg.HKEY_LOCAL_MACHINE, wow),
                       (winreg.HKEY_LOCAL_MACHINE, base),
                       (winreg.HKEY_CURRENT_USER, base)):
        try:
            with winreg.OpenKey(root, path) as k:
                pv, _ = winreg.QueryValueEx(k, "pv")
                if pv and pv not in ("", "0.0.0.0"):
                    return True
        except OSError:
            continue
    return False


def _msgbox(title: str, text: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)  # MB_ICONINFORMATION
    except Exception:
        pass


def _ensure_webview2() -> bool:
    """Make sure the WebView2 runtime is present before starting the UI. If it's
    missing, run the bundled Evergreen bootstrapper (silent) when shipped beside
    the exe, otherwise point the user to the download — then exit so they relaunch
    after install. Returns True to proceed, False to abort startup."""
    if _webview2_installed():
        return True
    boot = None
    for d in (os.path.dirname(sys.executable), _res_dir(), os.getcwd()):
        p = os.path.join(d, "MicrosoftEdgeWebview2Setup.exe")
        if os.path.exists(p):
            boot = p
            break
    msg = "Full Auto Forza Edition needs the Microsoft Edge WebView2 Runtime.\n\n"
    if boot:
        try:
            import subprocess
            subprocess.Popen([boot, "/silent", "/install"])
            _msgbox("WebView2 Runtime required",
                    msg + "It's installing now — please reopen FAFE once setup finishes.")
            return False
        except Exception:
            boot = None
    if not boot:
        try:
            import webbrowser
            webbrowser.open(_WV2_LINK)
        except Exception:
            pass
        _msgbox("WebView2 Runtime required",
                msg + "Install it from the page that just opened (or " + _WV2_LINK +
                "), then reopen FAFE.")
    return False

try:
    import license_client
except Exception:           # paywall module optional / not present on a build
    license_client = None


class Api:
    """Exposed to JS as `pywebview.api`. Every method is callable from the page;
    Python → JS pushes go through window.evaluate_js (log / status streaming)."""

    def __init__(self):
        self._window = None
        self._stop = threading.Event()
        self._thread = None
        self._cap_session = None
        self._overlay = None
        self._loglines = collections.deque(maxlen=3)
        # Per-function log buffers (name -> recent lines) so the F12 report bundles
        # EACH function's log separately (Full Auto, Auto Wheelspins, …) — the UI
        # log is a single shared stream that's cleared per run, so it alone would
        # only hold the most recent run.
        self._logbuf = {}
        self._status_text = "Ready"
        self._running_flag = False
        self._run_start = None
        self._func = ""
        # First launch = no config existed at startup. Session-level (not just
        # config.HAD_CONFIG) so it stays cleared after the picker even though a
        # page reload re-runs init() within the SAME process (HAD_CONFIG never
        # flips mid-process). Cleared as soon as a language is set (see set_cfg).
        self._first_run = not config.HAD_CONFIG
        # Serializes config read-modify-write so concurrent writers (overlay thread
        # + main window; or the block selector's 3 rapid saves) can't lose each
        # other's keys — without it, each loads the old config, changes one key,
        # and the last full-dict write wins, dropping the others (e.g. middle_cols).
        self._cfg_lock = threading.Lock()

    # ── Python → JS ──────────────────────────────────────────
    def _js(self, expr):
        if self._window:
            try:
                self._window.evaluate_js(expr)
            except Exception:
                pass

    def _log(self, line):
        self._js(f"appendLog({json.dumps(str(line))})")
        self._loglines.append(str(line))
        name = self._func or "General"
        buf = self._logbuf.get(name)
        if buf is None:
            buf = self._logbuf[name] = collections.deque(maxlen=1000)
        buf.append(str(line))
        self._push_overlay()

    def _status(self, text, running):
        self._status_text = str(text)
        running = bool(running)
        if running and not self._running_flag:
            self._run_start = time.time()      # transition idle → running: start clock
        elif not running:
            self._run_start = None
        self._running_flag = running
        self._js(f"setStatus({json.dumps(str(text))}, {str(running).lower()})")
        self._push_overlay()

    def _overlay_data(self):
        cfg = config.load()
        # func_key lets the overlay localize the function name itself (the stored
        # self._func is an English label); reverse-map it back to its key.
        func_key = next((k for k, v in self._FUNC_LABELS.items()
                         if v == self._func), "")
        return {"func": self._func,
                "func_key": func_key,
                "sub": self._status_text,
                "lines": list(self._loglines),
                "key": str(cfg.get("toggle_key", "f9")).upper(),
                "running": self._running_flag,
                "lang": cfg.get("lang", "en"),
                # Only offer Full Auto in the overlay switcher when it's actually
                # runnable (bundled + licensed) — teaser builds omit it.
                "fa_available": (_full_auto is not None and self._licensed()),
                "started": int(self._run_start * 1000) if self._run_start else 0}

    def _push_overlay(self):
        if self._overlay:
            self._overlay.update(self._overlay_data())

    def _running(self):
        return bool(self._thread and self._thread.is_alive())

    # ── JS → Python ──────────────────────────────────────────
    def get_init(self):
        """Initial state for the page: version, license, config snapshot, monitors."""
        cfg = config.load()
        try:
            monitors = capture.list_monitors()
        except Exception:
            monitors = []
        licensed = True
        mid, store = "", None
        try:
            if license_client is not None:
                licensed = bool(license_client.is_allowed())
                mid = license_client.machine_id()
                store = getattr(license_client, "STORE_URL", None)
        except Exception:
            licensed = False
        return {"version": VERSION, "licensed": licensed, "config": cfg,
                "monitors": monitors, "machine_id": mid, "store_url": store,
                "frozen": _is_frozen(),
                "first_run": self._first_run}

    def _update_cfg(self, **kwargs):
        """Apply one or more config keys under a lock (load → update → save), so
        concurrent callers can't clobber each other's keys. Returns save success."""
        with self._cfg_lock:
            cfg = config.load()
            cfg.update(kwargs)
            return config.save(cfg)

    def set_cfg(self, key, value):
        """Persist a single config key (controls call this on change). Surfaces a
        write failure to the log — a silent one looks like the setting 'not taking'
        until restart (e.g. FAFE in a read-only / Controlled-Folder-Access path)."""
        ok = self._update_cfg(**{key: value})
        if key == "lang":
            self._first_run = False   # a language was chosen → never re-show the picker
        if not ok:
            self._log(f"WARNING: couldn't save setting '{key}' to config.json — "
                      f"is FAFE in a write-protected folder (e.g. Downloads)? "
                      f"Move it elsewhere so settings persist.")
        return ok

    def get_templates(self, tab):
        """Template chips for a tab — [{name, threshold, pct}] from the function's
        built-in template folder + its thresh_* config. Read-only for now (capture
        / threshold editing arrives with the setup-panel port). mastery/delete are
        keyboard-driven → no detection templates → []."""
        import os
        import glob
        cfg = config.load()
        lang = config.resolve_template_lang(cfg)
        getters = {
            "race": config.get_race_templates,
            "buy": config.get_buy_templates,
            "wheelspin": config.get_wheelspin_templates,
            "full_auto": config.get_full_auto_templates,
        }
        g = getters.get(tab)
        if g is None:
            return []
        try:
            folder = g(config.REFERENCE_RES, lang)
            names = sorted(os.path.splitext(os.path.basename(p))[0]
                           for p in glob.glob(os.path.join(folder, "*.json")))
        except Exception:
            return []
        out = []
        for n in names:
            thr = float(cfg.get("thresh_" + n, 0.70))
            out.append({"name": n, "threshold": round(thr, 2),
                        "pct": str(int(round(thr * 100))) + "%"})
        return out

    def _tpl_folder(self, tab):
        """Writable built-in template folder for a function tab, or None."""
        getters = {
            "race": config.get_race_templates,
            "buy": config.get_buy_templates,
            "wheelspin": config.get_wheelspin_templates,
            "full_auto": config.get_full_auto_templates,
        }
        g = getters.get(tab)
        if g is None:
            return None
        cfg = config.load()
        return g(config.REFERENCE_RES, config.resolve_template_lang(cfg))

    def capture_template(self, tab, key):
        """Start a CAPS-LOCK region capture for one template and save it.
        CaptureSession draws its own OpenCV windows, so it's independent of the
        webview — the user presses the capture key over the GAME, drag-selects,
        ENTER saves. Streams status/log into the page and refreshes the chips."""
        folder = self._tpl_folder(tab)
        if folder is None:
            return False
        cfg = config.load()
        mon = self._int(cfg.get("monitor_index", 1)) or 1
        cap_key = cfg.get("capture_key", "caps lock")
        try:
            if self._cap_session:
                self._cap_session.stop()
        except Exception:
            pass

        def _done(crop, w, h, bx, by, bw, bh):
            try:
                capture.save_template(folder, key, crop, w, h, box=(bx, by, bw, bh))
                self._log("Captured template: " + key)
            except Exception as e:
                self._log("Capture failed: " + str(e))
            self._status("Ready", False)
            self._js(f"onCaptureDone({json.dumps(tab)})")

        def _cancel():
            self._log("Capture cancelled.")
            self._status("Ready", False)
            self._js(f"onCaptureDone({json.dumps(tab)})")

        self._cap_session = capture.CaptureSession(
            monitor_index=mon,
            window_title="Select region — " + key,
            callback=_done, on_cancel=_cancel,
            capture_key=cap_key, template_key=None, examples_dir=None)
        up = str(cap_key).upper()
        self._status(f"Press {up} over the game to capture '{key}'", False)
        self._log(f"Waiting for {up} — drag-select '{key}', ENTER to save, ESC to cancel.")
        self._cap_session.start()
        return True

    def get_grid(self):
        """Standalone Unlock (mastery) tree path — ordered 4x4 cells. The cursor
        always starts bottom-left (3,0); each cell is walked-to + unlocked in
        order. Empty until the user defines a path."""
        cfg = config.load()
        order = capture.load_grid(
            config.get_mastery_grid_file(config.resolve_template_lang(cfg)))
        return {"rows": 4, "cols": 4, "start": [3, 0],
                "order": [[int(r), int(c)] for (r, c) in order]}

    def save_grid(self, order):
        cfg = config.load()
        try:
            cells = [(int(p[0]), int(p[1])) for p in (order or [])]
            capture.save_grid(
                config.get_mastery_grid_file(config.resolve_template_lang(cfg)),
                cells)
            return True
        except Exception as e:
            self._log("Save grid failed: " + str(e))
            return False

    @staticmethod
    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    def _start(self, runner, **kwargs):
        """Spawn runner(cfg, stop_event, log_cb, status_cb, **kwargs) on a worker
        thread, streaming its log_cb / status_cb into the page. Shared by every
        automation's start_* method."""
        if self._running():
            return False
        self._stop = threading.Event()
        # fresh per-function log buffer for this run (the report keeps each
        # function's latest run; other functions' buffers are untouched)
        self._logbuf[self._func or "General"] = collections.deque(maxlen=1000)
        cfg = config.load()

        def _run():
            lang = cfg.get("lang", "en")
            # 3-second pre-start countdown (stop-aware via F9/Stop). Foreground
            # mode: gives you time to switch to the game. Background mode drives
            # the game window directly, so no switch is needed.
            if not cfg.get("background_input", True):
                self._log(_at("startup_switch_to_game", lang))
            for i in range(3, 0, -1):
                if self._stop.is_set():
                    self._status("Ready", False)
                    return
                self._log(_at("startup_countdown", lang, i=i))
                self._status(_at("startup_countdown", lang, i=i), True)
                time.sleep(1)
            if self._stop.is_set():
                self._status("Ready", False)
                return
            self._log(_at("startup_running", lang))
            if cfg.get("detector_enable_ocr"):
                self._log(_at("log_ocr_enabled", lang))
            self._status("Running", True)
            try:
                runner(cfg, self._stop, self._log,
                       lambda m: self._status(m, True), **kwargs)
            except Exception as e:
                import traceback
                self._log(f"ERROR: {e}")
                self._log(traceback.format_exc())
            self._status("Ready", False)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return True

    def _licensed(self):
        """Authoritative license gate — the UI's state.licensed is cosmetic; THIS
        is what actually permits the paid feature. Fail closed."""
        try:
            return bool(license_client.is_allowed()) if license_client else False
        except Exception:
            return False

    def start_full_auto(self, races):
        # Defense-by-absence: teaser/public builds ship WITHOUT full_auto.pyd, so
        # there's nothing to run even if every gate above is bypassed.
        if _full_auto is None:
            self._log("Full Auto isn't included in this build.")
            self._status("Coming soon", False)
            return False
        # Enforce the paywall in the BACKEND: the JS view-gate is bypassable
        # (plaintext app.js, devtools), so re-check here before running anything.
        if not self._licensed():
            self._log("Full Auto is locked — a valid license is required.")
            self._status("Locked", False)
            return False
        cfg = config.load()
        self._func = "Full Auto"
        return self._start(
            _full_auto.run,
            race_count=self._int(races),
            branch_mode=cfg.get("full_auto_branch_mode", "racing"),
            start_from=cfg.get("full_auto_start_from", "race"),
            grind_type=cfg.get("full_auto_grind_type", "wheelspin"),
            stage_cb=self._fa_stage, progress_cb=self._fa_progress)

    def _fa_stage(self, n):
        """Entering a loop stage — mark it active and reset its fill to 0."""
        self._js(f"setStage({int(n)}, 0)")

    def _fa_progress(self, idx, done, total):
        """Per-step progress → fill the active stage to done/total."""
        frac = (done / total) if total else 0
        self._js(f"setStage({int(idx)}, {frac:.4f})")

    def start_race(self, count):
        import race
        self._func = "AFK Races"
        return self._start(race.run, max_loops=self._int(count))

    def start_buy(self, count):
        import buy
        self._func = "Buy Cars"
        return self._start(buy.run, max_loops=self._int(count))

    def start_wheelspin(self, count):
        import wheelspin
        self._func = "Wheelspins"
        return self._start(wheelspin.run, max_loops=self._int(count))

    def _block_count(self, cfg, prefix):
        """Garage-block car count: first partial column + middle full columns +
        last partial column, in the column-major 3-rows grid (same formula as the
        CTk MasteryCarBlockWidget)."""
        fr = self._int(cfg.get(prefix + "_block_first_row", 1)) or 1
        mid = self._int(cfg.get(prefix + "_block_middle_cols", 0))
        lr = self._int(cfg.get(prefix + "_block_last_row", 3)) or 3
        return max(1, (4 - fr) + mid * 3 + lr)

    def start_mastery(self):
        import mastery
        self._func = "Unlock"
        return self._start(mastery.run,
                           max_cars=self._block_count(config.load(), "mastery"))

    def start_delete(self):
        import delete_cars
        self._func = "Delete"
        return self._start(delete_cars.run,
                           max_cars=self._block_count(config.load(), "delete"))

    def stop(self):
        self._stop.set()
        return True

    def report(self, log_text=""):
        """F12 — build the bug-report bundle on a worker thread, then open it."""
        def _run():
            try:
                import os
                import report as _report
                cfg = config.load()
                # one section per function that has run this session (Full Auto,
                # Auto Wheelspins, …); fall back to the visible UI log if nothing
                # has been buffered yet.
                logs = {name: list(buf) for name, buf in self._logbuf.items() if buf}
                if not logs:
                    logs = {"Activity": (log_text or "").splitlines()}
                self._log("Building bug report…")
                path = _report.generate_report(cfg, cfg.get("monitor_index", 1),
                                               logs, log_cb=self._log)
                if path:
                    self._log("Report saved: " + path)
                    try:
                        os.startfile(os.path.dirname(path) or path)
                    except Exception:
                        pass
            except Exception as e:
                self._log("Report failed: " + str(e))
        threading.Thread(target=_run, daemon=True).start()
        return True

    def _register_hotkeys(self):
        """(Re)bind the global OS hotkeys (work while the GAME is focused, not the
        webview): F9 = start/stop (the safety stop), F12 = report, F10 = overlay.
        Re-callable for live rebinding — removes the previously-registered handles
        first (never unhook_all, which would clobber other hooks). CAPS-LOCK
        capture is NOT a global hotkey — CaptureSession reads capture_key on demand.
        Best-effort — some locked-down Windows setups reject add_hotkey."""
        try:
            import keyboard
        except Exception:
            return
        for h in getattr(self, "_hotkeys", []):
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        self._hotkeys = []
        cfg = config.load()
        mapping = {cfg.get("toggle_key", "f9"): "f9",
                   cfg.get("report_key", "f12"): "f12"}
        for combo, name in mapping.items():
            if not combo:
                continue
            try:
                self._hotkeys.append(keyboard.add_hotkey(
                    combo, lambda n=name: self._js(f"onHotkey({json.dumps(n)})")))
            except Exception:
                pass
        # Overlay toggle is a Python-side window action — bind it straight to the
        # toggle (no JS round-trip), like the old app's F10.
        okey = cfg.get("overlay_key", "f10")
        if okey:
            try:
                self._hotkeys.append(keyboard.add_hotkey(okey, self.toggle_overlay))
            except Exception:
                pass

    _SHORTCUT_KEYS = {"toggle": "toggle_key", "capture": "capture_key",
                      "report": "report_key", "overlay": "overlay_key"}

    def set_shortcut(self, which, keyname):
        """Rebind a shortcut (Settings → Shortcuts). Saves the key to config; for
        the global hotkeys (toggle/report/overlay) re-registers live so the new
        key works immediately. capture just persists — CaptureSession reads it next
        capture."""
        cfgkey = self._SHORTCUT_KEYS.get(which)
        keyname = (keyname or "").strip().lower()
        if not cfgkey or not keyname:
            return False
        self._update_cfg(**{cfgkey: keyname})
        if which in ("toggle", "report", "overlay"):
            self._register_hotkeys()
        return True

    # ── status overlay (second pywebview window) ──────────────
    def _save_overlay_pos(self, x, y):
        self._update_cfg(overlay_x=int(x), overlay_y=int(y))

    def shutdown(self, *args):
        """Tear everything down when the main window closes, so nothing lingers
        (users saw msedgewebview2.exe stay alive). Stops any run, removes the
        global hotkeys, and DESTROYS the overlay window — until the overlay is
        gone, webview.start() won't return and the process (incl. its WebView2
        children) stays up. A short hard-exit timer is the backstop if the GUI
        loop still doesn't unwind."""
        try:
            self._stop.set()
        except Exception:
            pass
        try:
            import keyboard
            for h in getattr(self, "_hotkeys", []):
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
            self._hotkeys = []
        except Exception:
            pass
        try:
            if self._overlay is not None:
                self._overlay.destroy()
        except Exception:
            pass
        # Backstop: if webview's loop doesn't unwind promptly, force the process
        # (and its WebView2 child processes / daemon threads) to exit.
        threading.Timer(1.5, lambda: os._exit(0)).start()

    def create_overlay(self):
        """Create the overlay window ONCE, before webview.start() — hidden unless
        it was left enabled. Toggling later just show()/hide()s it (a window
        created after start from a worker thread never renders on Windows)."""
        cfg = config.load()
        html = _webui("overlay.html")
        self._overlay = WebOverlay(html, on_move=self._save_overlay_pos,
                                   on_func=self._overlay_select_func, log=self._log)
        self._overlay.create(x=cfg.get("overlay_x", 60), y=cfg.get("overlay_y", 60),
                             visible=bool(cfg.get("overlay_enabled", False)))
        self._overlay.update(self._overlay_data())   # seed initial state

    def set_overlay_enabled(self, on):
        """Settings toggle / F10: persist + show/hide the overlay window live."""
        on = bool(on)
        self._update_cfg(overlay_enabled=on)
        if self._overlay is not None:
            cfg = config.load()
            if on:
                self._overlay.show(cfg.get("overlay_x", 60), cfg.get("overlay_y", 60))
                self._overlay.update(self._overlay_data())
            else:
                self._overlay.hide()
            self._log(f"Overlay {'on' if on else 'off'}.")
        self._js(f"setOverlayUI({str(on).lower()})")   # keep the UI in sync (F10)
        return on

    def toggle_overlay(self):
        """F10 / topbar indicator: flip the overlay and persist the new state."""
        cur = bool(config.load().get("overlay_enabled", False))
        return self.set_overlay_enabled(not cur)

    _FUNC_LABELS = {"full_auto": "Full Auto", "race": "AFK Races", "buy": "Buy Cars",
                    "wheelspin": "Wheelspins", "mastery": "Unlock", "delete": "Delete"}

    def set_func(self, key):
        """Called by the main UI's showView() so the overlay header reflects the
        current function. Non-function views (settings) leave it unchanged."""
        label = self._FUNC_LABELS.get(key)
        if label:
            self._func = label
            self._push_overlay()
        return True

    def _overlay_select_func(self, key):
        """Overlay dropdown → switch the main window's view (which calls set_func
        back, syncing the overlay header)."""
        self._js(f"showView({json.dumps(key)})")

    _GUIDE_BASE = "https://leoncrispybacon.github.io/Full-Auto-Forza-Edition/"
    _GUIDE_SLUGS = {"full_auto": "forza-horizon-6-farming-guide",
                    "race": "race-auto-grind", "buy": "auto-buy-cars-in-batch",
                    "wheelspin": "auto-wheelspin",
                    "mastery": "auto-unlock-spin-wheel-mastery-tree",
                    "delete": "delete-used-cars"}

    def howto(self, func=None):
        """Open the web guide — the per-function page when known, else the index."""
        import webbrowser
        slug = self._GUIDE_SLUGS.get(func)
        url = self._GUIDE_BASE + (f"en/guides/{slug}/" if slug else "")
        try:
            webbrowser.open(url)
        except Exception:
            pass

    _LINKS = {
        "discord": "https://discord.com/invite/MNg2g9Pp6K",
        "paypal":  "https://paypal.me/Leonbacon",
        "jko":     "https://service.jkopay.com/r/transfer?j=Transfer:906639236",
    }

    def open_link(self, key):
        """Open an external link (Discord / support) in the system browser."""
        import webbrowser
        url = self._LINKS.get(key)
        if url:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return True

    def buy(self):
        """Open the Lemon Squeezy checkout for the paid Full Auto unlock."""
        import webbrowser
        url = getattr(license_client, "STORE_URL", None) if license_client else None
        if url:
            try:
                webbrowser.open(url)
            except Exception:
                pass

    def activate_license(self, key):
        """Activate a license key on this machine (used by Settings)."""
        if license_client is None:
            return {"ok": False, "message": "License module unavailable."}
        try:
            ok, msg = license_client.activate(key)
            return {"ok": bool(ok), "message": str(msg)}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def deactivate_license(self):
        if license_client is None:
            return {"ok": False, "message": "License module unavailable."}
        try:
            ok, msg = license_client.deactivate()
            return {"ok": bool(ok), "message": str(msg)}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def license_status(self):
        """Snapshot for Settings: state / masked key / offline days / machine id /
        the authoritative allowed flag."""
        out = {"state": "unlicensed", "key": "", "offline_days": 0,
               "machine_id": "", "allowed": False}
        if license_client is None:
            return out
        try:
            out.update(license_client.status())
            out["machine_id"] = license_client.machine_id()
            out["allowed"] = bool(license_client.is_allowed())
        except Exception:
            pass
        return out


def _set_dpi_aware():
    """Mark the process per-monitor-v2 DPI aware BEFORE any window is created, so
    window sizes are real pixels. Without it, a high-DPI handheld (e.g. the XAX)
    bitmap-scales windows up by the display scale — the small overlay balloons to
    cover the screen. Idempotent: if it's already set, the calls just no-op."""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()         # system-aware (oldest fallback)
    except Exception:
        pass


def main():
    _set_dpi_aware()
    if not _ensure_webview2():   # WebView2 missing → bootstrapper/instructions, then exit
        return
    api = Api()
    window = webview.create_window(
        f"Full Auto Forza Edition v{VERSION}",
        _webui("index.html"),
        js_api=api,
        width=1240, height=860,
        background_color="#0A0E14",
        min_size=(1040, 640),   # never thin enough to wrap the loop progress bar
    )
    api._window = window
    api.create_overlay()        # second window (hidden unless overlay was left on)
    api._register_hotkeys()     # global F9 / F12 / F10 (work while the game is focused)
    # Closing the main window must tear down the overlay window + hotkeys too,
    # else webview.start() never returns and msedgewebview2.exe lingers.
    window.events.closing += api.shutdown
    # DevTools (right-click ▸ Inspect) on in dev, OFF in a packaged build.
    webview.start(debug=not _is_frozen())
    # Loop ended (all windows closed) → force a clean full teardown so no daemon
    # thread or WebView2 child process is left behind.
    os._exit(0)


if __name__ == "__main__":
    main()
