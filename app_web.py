"""
app_web.py — pywebview entry point for FAFE's WebUI.

Hosts webui/index.html in an Edge WebView2 window and exposes `Api` to the page
as `pywebview.api`. The automation backend (config, capture, full_auto, …) is
imported and driven UNCHANGED — this file is only the UI bridge.

The WebUI owns the desktop surface: initial state, settings, shortcuts, template
capture, all public automation tabs, Full Auto gating, logs, reports, and the
status overlay.

Run:  python app_web.py
"""
import collections
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import threading
import time

# Cap native thread pools BEFORE cv2 / numpy / onnxruntime load. The WebUI entry
# is now the only supported app entry point, so these caps live here.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "2")
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
os.environ.setdefault("KMP_BLOCKTIME", "0")

import webview

import config
import capture
import hdr
import ocr_profile
import updater
try:
    import full_auto as _full_auto    # paid feature; OMITTED from teaser/public builds
except Exception:
    _full_auto = None                 # absent → start_full_auto stays locked
from web_overlay import WebOverlay
from version import VERSION
from app_lang import t as _at

_TITLE = f"Full Auto Forza Edition v{VERSION}"
_TITLEBAR_COLORS = {
    "default": ("#121A28", "#F4F8FD", "#243044"),
    "denia": ("#FFFFFF", "#160E1C", "#EFD6E4"),
    "denia_running": ("#150E24", "#F3ECFF", "#30204F"),
    "horizon": ("#1E1710", "#FBF5EC", "#3A2C1A"),
}


def _colorref(hex_color: str) -> int:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return r | (g << 8) | (b << 16)


def _is_dark(hex_color: str) -> bool:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 128


def _hwnd_from_window(window=None):
    native = getattr(window, "native", None)
    for obj in (native, window):
        if obj is None:
            continue
        for name in ("Handle", "handle", "HWND", "hwnd"):
            handle = getattr(obj, name, None)
            if handle:
                try:
                    return int(handle.ToInt64())
                except Exception:
                    try:
                        return int(handle)
                    except Exception:
                        pass
    return 0


def _apply_titlebar_theme(theme: str, running: bool = False, window=None) -> None:
    """Tint the native Windows caption to match the WebUI theme."""
    if os.name != "nt":
        return
    try:
        hwnd = _hwnd_from_window(window)
        if not hwnd:
            ctypes.windll.user32.FindWindowW.restype = ctypes.c_void_p
            hwnd = ctypes.windll.user32.FindWindowW(None, _TITLE)
        if not hwnd:
            return
        dwm = ctypes.windll.dwmapi
        key = "denia_running" if theme == "denia" and running else theme
        colors = _TITLEBAR_COLORS.get(key, _TITLEBAR_COLORS["default"])
        dark = ctypes.c_int(1 if _is_dark(colors[0]) else 0)
        dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 20, ctypes.byref(dark), ctypes.sizeof(dark))
        for attr, color in zip((35, 36, 34), colors):
            value = ctypes.c_int(_colorref(color))
            dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


def _is_frozen() -> bool:
    """True in a packaged build — PyInstaller (sys.frozen) OR Nuitka (__compiled__).
    Used to turn DevTools off and harden the UI in release."""
    return bool(getattr(sys, "frozen", False) or globals().get("__compiled__"))


UPDATE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or config.BASE_DIR, "FAFE", "update")


def _purge_update_dir() -> None:
    """Delete any leftover downloaded installer (unlocked once an update finished
    and FAFE relaunched). Best-effort; self-heals interrupted updates."""
    import glob
    try:
        for p in glob.glob(os.path.join(UPDATE_DIR, "*")):
            try:
                os.remove(p)
            except OSError:
                pass
    except Exception:
        pass


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


def _hotkey_vk(keyname):
    """Map the app's single-key shortcut names to Win32 virtual-key codes."""
    key = str(keyname or "").strip().lower()
    fkeys = {f"f{i}": 0x6F + i for i in range(1, 25)}
    named = {
        "backspace": 0x08,
        "tab": 0x09,
        "enter": 0x0D,
        "esc": 0x1B,
        "escape": 0x1B,
        "space": 0x20,
        "page up": 0x21,
        "page down": 0x22,
        "end": 0x23,
        "home": 0x24,
        "left": 0x25,
        "up": 0x26,
        "right": 0x27,
        "down": 0x28,
        "insert": 0x2D,
        "delete": 0x2E,
        "caps lock": 0x14,
    }
    if key in fkeys:
        return fkeys[key]
    if key in named:
        return named[key]
    if len(key) == 1 and key.isalnum():
        return ord(key.upper())
    return None


class _WinHotkeyThread:
    """System-wide RegisterHotKey backend.

    The `keyboard` package uses a low-level hook; Forza's borderless/foreground
    input path can starve that hook. RegisterHotKey is dispatched by Windows'
    normal hotkey mechanism instead, so use it first and keep `keyboard` only as
    fallback for unsupported/failed registrations.
    """
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012
    MOD_NOREPEAT = 0x4000

    def __init__(self, bindings):
        self._bindings = [(str(k or "").strip().lower(), cb)
                          for k, cb in bindings if k]
        self._registered = set()
        self._ready = threading.Event()
        self._thread_id = 0
        self._thread = None

    @property
    def registered(self):
        return set(self._registered)

    def start(self):
        if os.name != "nt" or not self._bindings:
            return set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(0.75)
        return self.registered

    def stop(self):
        if not self._thread:
            return
        try:
            if self._thread_id:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread_id, self.WM_QUIT, 0, 0)
        except Exception:
            pass
        self._thread.join(timeout=0.75)

    def _run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        # Create the thread message queue before RegisterHotKey/PostThreadMessage.
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        callbacks = {}
        try:
            for idx, (combo, cb) in enumerate(self._bindings, start=1):
                vk = _hotkey_vk(combo)
                if not vk:
                    continue
                if user32.RegisterHotKey(None, idx, self.MOD_NOREPEAT, vk):
                    self._registered.add(combo)
                    callbacks[idx] = cb
            self._ready.set()
            if not callbacks:
                return
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == self.WM_HOTKEY:
                    cb = callbacks.get(int(msg.wParam))
                    if cb:
                        try:
                            cb()
                        except Exception:
                            pass
        finally:
            for idx in callbacks:
                try:
                    user32.UnregisterHotKey(None, idx)
                except Exception:
                    pass
            self._ready.set()

try:
    import license_client
except Exception:           # paywall module optional / not present on a build
    license_client = None


MASTERY_GATED_TEMPLATE_KEYS = (
    "ride_this_car",
    "upgrade_tuning",
    "car_mastery",
    "mastery_tree",
    "my_cars",
    "my_cars_header",
    "recently_added",
    # Post-cutscene screen — the ride-cutscene Esc is gated on detecting it
    # (mastery.py) so the Esc waits for the cutscene to end, not on a timer.
    "ride_cutscene_end",
)

RELAUNCH_TEMPLATE_KEYS = (
    "launch_start_prompt",
    "launch_continue",
)

FULL_AUTO_EXPECTED_TEMPLATE_KEYS = (
    "dodge",
    "gts_acr",
    "buy_detail_gts_acr",
    "mazda",
    "mad_mike_808",
    "buy_detail_mad_mike",
    "tech_points",
)

BUY_EXPECTED_TEMPLATE_KEYS = (
    "buy_detail_22b",
)

# Wheelspin's duplicate modal is read with two OCR-only sub-ROIs (no template
# image is matched): the FE-name band and the sell-price band. Surfaced so the
# user can draw/test/recapture those ROIs; testing one OCR-reads the region.
WHEELSPIN_DUP_OCR_KEYS = (
    "wheelspin_dup_name",
    "wheelspin_dup_price",
)

# Delete is keyboard-driven; the ONE optional template gates the final
# irreversible "confirm delete" keypress (delete_cars.py). Absent → blind macro.
DELETE_EXPECTED_TEMPLATE_KEYS = (
    "delete_confirm",
)

_GRID_22B_FALLBACK = [(3, 0), (3, 1), (2, 1), (1, 1), (0, 1), (0, 0)]
_GRID_GTSACR_FALLBACK = [(3, 0), (3, 1), (2, 1), (1, 1), (0, 1), (0, 2)]
_GRID_MAD_MIKE_FALLBACK = [(3, 0), (3, 1), (3, 2), (2, 2), (1, 2), (0, 2)]


def _grid_as_wire(order):
    return [[int(r), int(c)] for r, c in (order or [])]


def _builtin_mastery_presets():
    return [
        {
            "name": "Subaru 22B-STI",
            "builtin": True,
            "order": _grid_as_wire(getattr(
                _full_auto, "_GRID_22B", _GRID_22B_FALLBACK)),
        },
        {
            "name": "Dodge Viper GTS ACR",
            "builtin": True,
            "order": _grid_as_wire(getattr(
                _full_auto, "_GRID_GTSACR", _GRID_GTSACR_FALLBACK)),
        },
        {
            "name": "#123 Mad Mike 808 Wagon",
            "builtin": True,
            "order": _grid_as_wire(getattr(
                _full_auto, "_GRID_MAD_MIKE", _GRID_MAD_MIKE_FALLBACK)),
        },
    ]


def _legacy_mastery_presets_file(lang):
    d = os.path.join(config.TEMPLATES_DIR, lang, "mastery_full")
    return os.path.join(d, "mastery_presets.json")


def _migrate_legacy_mastery_presets(preset_file):
    presets = capture.load_grid_presets(preset_file)
    seen = {p["name"].lower() for p in presets}
    changed = False
    for lang in getattr(config, "TEMPLATE_LANGS", ()):
        legacy_file = _legacy_mastery_presets_file(lang)
        if os.path.abspath(legacy_file) == os.path.abspath(preset_file):
            continue
        for preset in capture.load_grid_presets(legacy_file):
            key = preset["name"].lower()
            if key in seen:
                continue
            presets.append(preset)
            seen.add(key)
            changed = True
    if changed:
        for preset in presets:
            capture.save_grid_preset(
                preset_file, preset["name"], preset["order"])
    return presets


class Api:
    """Exposed to JS as `pywebview.api`. Every method is callable from the page;
    Python → JS pushes go through window.evaluate_js (log / status streaming)."""

    def __init__(self):
        self._window = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread = None
        self._cap_session = None
        self._template_test_stop = threading.Event()
        self._overlay = None
        self._loglines = collections.deque(maxlen=80)
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
        self._auto_report_lock = threading.Lock()
        self._auto_reported = set()

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
        _apply_titlebar_theme(config.load().get("theme_preset", "default"), running, self._window)
        self._js(f"setStatus({json.dumps(str(text))}, {str(running).lower()})")
        self._push_overlay()

    def _report_logs(self, fallback=""):
        logs = {name: list(buf) for name, buf in self._logbuf.items() if buf}
        return logs or {"Activity": str(fallback or "").splitlines()}

    def _auto_report(self, trigger_name):
        trigger_name = str(trigger_name or "Automation stopped")
        with self._auto_report_lock:
            if trigger_name in self._auto_reported:
                return
            self._auto_reported.add(trigger_name)

        def _run():
            try:
                import report as _report
                cfg = config.load()
                path = _report.generate_report(
                    cfg, cfg.get("monitor_index", 1), self._report_logs(),
                    log_cb=self._log, trigger_name=trigger_name,
                    open_folder=False)
                if path:
                    self._log(_at("auto_report_saved", cfg.get("lang", "en"),
                                  path=path))
            except Exception as e:
                self._log(_at("auto_report_failed", config.load().get("lang", "en"),
                              error=str(e)))

        threading.Thread(target=_run, daemon=True).start()

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
                "pause_key": str(cfg.get("pause_key", "f8")).upper(),
                "running": self._running_flag,
                "paused": self._pause.is_set(),
                "lang": cfg.get("lang", "en"),
                "theme": cfg.get("theme_preset", "default"),
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
        try:
            hdr_on = hdr.is_hdr_enabled(cfg.get("monitor_index", 1), monitors)
            cfg, changed = hdr.maybe_enable_ocr_for_hdr(cfg, hdr_on)
            if changed:
                self._update_cfg(detector_enable_ocr=True)
                self._log("HDR detected on the selected game monitor — "
                          "OCR enabled automatically and saved.")
        except Exception:
            pass
        licensed = False
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
                "auto_update": bool(config.load().get("auto_update", True)),
                "update_installable": bool(_is_frozen()
                                           and updater.running_from_installed_copy()),
                "first_run": self._first_run,
                # Builds without the private Full Auto module are teaser builds.
                # A private build leaves teaser mode only when full_auto is bundled.
                "coming_soon": _full_auto is None,
                "full_auto_bundled": _full_auto is not None}

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
        if ok and key in ("theme_preset", "lang"):
            self._push_overlay()
        if ok and key == "theme_preset":
            _apply_titlebar_theme(str(value), self._running_flag, self._window)
        if ok and key == "monitor_index" and self._overlay is not None and self._overlay.is_visible():
            cfg = config.load()
            self._overlay.show(cfg.get("overlay_x", 60), cfg.get("overlay_y", 60),
                               monitor_index=cfg.get("monitor_index", 1))
        if not ok:
            self._log(f"WARNING: couldn't save setting '{key}' to config.json — "
                      f"is FAFE in a write-protected folder (e.g. Downloads)? "
                      f"Move it elsewhere so settings persist.")
        return ok

    def browse_game_custom_launch(self):
        """Settings → game launch path: pick an exe/shortcut/script target."""
        try:
            win = webview.windows[0] if webview.windows else None
            if not win:
                return ""
            paths = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=(
                    "Launch targets (*.exe;*.lnk;*.bat;*.cmd)",
                    "All files (*.*)",
                ),
            )
            if not paths:
                return ""
            path = paths[0] if isinstance(paths, (list, tuple)) else paths
            path = str(path or "").strip()
            if path:
                self.set_cfg("game_custom_launch", path)
            return path
        except Exception as e:
            self._log("Game launch browse failed: " + str(e))
            return ""

    def cutscene_mod_status(self):
        """State for the Settings control: {installed, files_present, game_dir,
        running}. While the game is OPEN we can read its exe dir — persist it so
        install still works after the user closes the game (no window to read then)."""
        import cutscene_mod
        cfg = config.load()
        running = cutscene_mod.game_running(cfg)
        game_dir = cutscene_mod.resolve_game_dir(cfg)
        if running and game_dir and game_dir != cfg.get("cutscene_skip_game_dir"):
            self._update_cfg(cutscene_skip_game_dir=game_dir)
        files = cutscene_mod.status(game_dir)["files_present"] if game_dir else False
        return {"installed": bool(cfg.get("cutscene_skip_installed", False)),
                "files_present": files,
                "game_dir": game_dir or "",
                "running": running}

    def cutscene_mod_install(self):
        """Edit Cinematics.zip. Returns {ok, msg}. UI shows the warning modal
        BEFORE calling this — this method assumes consent. Refuses while the game
        is running (the archive is locked / would be re-verified on exit)."""
        import cutscene_mod
        cfg = config.load()
        lang = cfg.get("lang", "en")
        if cutscene_mod.game_running(cfg):
            return {"ok": False, "msg": _at("cutscene_skip_close_game", lang)}
        game_dir = cutscene_mod.resolve_game_dir(cfg)
        if not game_dir:
            return {"ok": False, "msg": _at("cutscene_skip_no_game", lang)}
        self._log("Cutscene skip: resolved game dir = " + str(game_dir))
        try:
            paths = cutscene_mod.install(game_dir)
            self._update_cfg(cutscene_skip_installed=True,
                             cutscene_skip_game_dir=game_dir)
            self._log("Cutscene skip installed: " + "; ".join(paths))
            return {"ok": True, "msg": _at("cutscene_skip_installed_ok", lang)}
        except Exception as e:
            self._log("Cutscene skip install failed: " + str(e))
            return {"ok": False, "msg": _at("cutscene_skip_failed", lang, err=str(e))}

    def cutscene_mod_uninstall(self):
        """Restore Cinematics.zip from the backup. Returns {ok, msg}. Refuses
        while the game is running (same file-lock reason as install)."""
        import cutscene_mod
        cfg = config.load()
        lang = cfg.get("lang", "en")
        if cutscene_mod.game_running(cfg):
            return {"ok": False, "msg": _at("cutscene_skip_close_game", lang)}
        game_dir = (cutscene_mod.resolve_game_dir(cfg)
                    or cfg.get("cutscene_skip_game_dir", ""))
        try:
            if game_dir:
                cutscene_mod.uninstall(game_dir)
            self._update_cfg(cutscene_skip_installed=False)
            self._log("Cutscene skip uninstalled")
            return {"ok": True, "msg": _at("cutscene_skip_uninstalled", lang)}
        except Exception as e:
            self._log("Cutscene skip uninstall failed: " + str(e))
            return {"ok": False, "msg": _at("cutscene_skip_failed", lang, err=str(e))}

    def cutscene_mod_browse_game_dir(self):
        """Manual fallback: let the user pick the Forza Horizon 6 folder; persist
        it for resolution. Returns the chosen path ('' if cancelled)."""
        try:
            win = webview.windows[0] if webview.windows else None
            if not win:
                return ""
            paths = win.create_file_dialog(webview.FOLDER_DIALOG)
            if not paths:
                return ""
            path = paths[0] if isinstance(paths, (list, tuple)) else paths
            path = str(path or "").strip()
            if path:
                self.set_cfg("cutscene_skip_game_dir", path)
            return path
        except Exception as e:
            self._log("Cutscene game-dir browse failed: " + str(e))
            return ""

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
            "mastery": config.get_mastery_templates,
            "buy": config.get_buy_templates,
            "wheelspin": config.get_wheelspin_templates,
            "full_auto": config.get_full_auto_templates,
            "delete": config.get_delete_templates,
        }
        g = getters.get(tab)
        if g is None:
            return []
        try:
            folder = g(config.REFERENCE_RES, lang)
            relaunch_folder = config.get_relaunch_templates(
                config.REFERENCE_RES, lang)
            names = sorted(os.path.splitext(os.path.basename(p))[0]
                           for p in glob.glob(os.path.join(folder, "*.json")))
            if tab == "mastery":
                names = sorted(set(names).union(MASTERY_GATED_TEMPLATE_KEYS))
            if tab == "buy":
                names = sorted(set(names).union(BUY_EXPECTED_TEMPLATE_KEYS))
            if tab == "wheelspin":
                names = sorted(set(names).union(WHEELSPIN_DUP_OCR_KEYS))
            if tab == "delete":
                names = sorted(set(names).union(DELETE_EXPECTED_TEMPLATE_KEYS))
            if tab == "full_auto":
                names = sorted(set(names).union(FULL_AUTO_EXPECTED_TEMPLATE_KEYS))
            if tab == "race":
                relaunch_names = (
                    os.path.splitext(os.path.basename(p))[0]
                    for p in glob.glob(os.path.join(relaunch_folder, "*.json"))
                )
                names = sorted(set(names).union(relaunch_names)
                               .union(RELAUNCH_TEMPLATE_KEYS))
        except Exception:
            return []
        out = []
        for n in names:
            thr = float(cfg.get("thresh_" + n, 0.70))
            exists_folder = (
                relaunch_folder
                if tab == "race" and n in RELAUNCH_TEMPLATE_KEYS
                else folder
            )
            out.append({"name": n, "threshold": round(thr, 2),
                        "pct": str(int(round(thr * 100))) + "%",
                        "exists": os.path.exists(
                            os.path.join(exists_folder, n + ".json"))})
        return out

    def _tpl_folder(self, tab, key=None):
        """Writable built-in template folder for a function tab, or None."""
        getters = {
            "race": config.get_race_templates,
            "mastery": config.get_mastery_templates,
            "buy": config.get_buy_templates,
            "wheelspin": config.get_wheelspin_templates,
            "full_auto": config.get_full_auto_templates,
            "delete": config.get_delete_templates,
        }
        g = getters.get(tab)
        if g is None:
            return None
        cfg = config.load()
        lang = config.resolve_template_lang(cfg)
        if tab == "race" and key in RELAUNCH_TEMPLATE_KEYS:
            return config.get_relaunch_templates(config.REFERENCE_RES, lang)
        return g(config.REFERENCE_RES, lang)

    def capture_template(self, tab, key):
        """Start a CAPS-LOCK region capture for one template and save it.
        CaptureSession draws its own OpenCV windows, so it's independent of the
        webview — the user presses the capture key over the GAME, drag-selects,
        ENTER saves. Streams status/log into the page and refreshes the chips."""
        folder = self._tpl_folder(tab, key)
        if folder is None:
            return False
        cfg = config.load()
        # Normal users recapture into the preserved sibling "custom" folder (so an
        # installer upgrade can't wipe it; load_template prefers custom). Dev mode
        # authors the SHIPPED set, so it writes straight to built-in.
        if not cfg.get("dev_mode", False):
            folder = config.custom_dir(folder)
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

    def _run_template_test_once(self, tab, key):
        """Run one detector check for a single template. Sends no input."""
        folder = self._tpl_folder(tab, key)
        if folder is None:
            return False
        cfg = config.load()
        lang = cfg.get("lang", "en")
        io = None
        try:
            from detector import ScreenDetector
            from gameio import GameIO
            from capture import load_template
            import logfmt

            io = GameIO(cfg, self._log, crop_letterbox=True)
            test_cfg = dict(cfg)
            test_cfg["debug_detection"] = True
            debug_dir = os.path.join(config.BASE_DIR, "debug")
            detector = ScreenDetector(
                test_cfg, debug_dir=debug_dir, on_auto_ocr=self._log)

            # The duplicate modal's FE-name / price bands are OCR-only regions
            # (no template image is matched) — test them by OCR-reading the ROI
            # and dumping the annotated band, not by pixel detection.
            if key in WHEELSPIN_DUP_OCR_KEYS:
                return self._run_dup_roi_test(detector, io, folder, key, debug_dir)

            template, _scale, meta = load_template(
                folder, key, io.width, io.height, grayscale=True,
                ref_folder=folder,
                prefer_ref=bool(cfg.get("template_prefer_reference", True)))
            if meta.get("box"):
                detector.set_template_geometry(
                    key, meta["box"],
                    int(meta.get("screen_width", io.width)),
                    int(meta.get("screen_height", io.height)))
            if meta.get("roi"):
                dims = meta.get("roi_dims") or [
                    meta.get("screen_width", 0),
                    meta.get("screen_height", 0),
                ]
                detector.set_template_roi(key, meta["roi"], *dims)

            frame = io.grab()
            threshold = float(cfg.get("thresh_" + key, 0.70))
            result = detector.detect(frame, key, template, threshold, stable=False)
            verdict = "MATCH" if result.matched else "miss"
            self._log(
                f"Template test {key}: {verdict} "
                f"({logfmt.detail(result, lang)}, threshold {threshold:.0%})")
            png_path = os.path.join(debug_dir, key + ".png")
            self._log("Debug snapshot saved: " + png_path)
            # Open the annotated result immediately so it's not a hunt in debug/.
            try:
                if os.path.exists(png_path):
                    os.startfile(png_path)
            except Exception:
                pass
            return bool(result.matched)
        except FileNotFoundError:
            self._log("Template test failed: " + key + " is not captured yet.")
            return False
        except Exception as e:
            self._log("Template test failed: " + str(e))
            return False
        finally:
            try:
                if io is not None:
                    io.cleanup()
            except Exception:
                pass

    def _run_dup_roi_test(self, detector, io, folder, key, debug_dir):
        """OCR-read one duplicate-modal band (FE-name / price) and dump the
        annotated ROI. Applies a user-captured/adjusted sidecar (box -> geometry,
        roi -> custom ROI) so the test reflects the tuned region."""
        import json
        meta_path = os.path.join(folder, key + ".json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}
            if meta.get("box"):
                detector.set_template_geometry(
                    key, meta["box"],
                    int(meta.get("screen_width", io.width)),
                    int(meta.get("screen_height", io.height)))
            if meta.get("roi"):
                dims = meta.get("roi_dims") or [
                    meta.get("screen_width", 0), meta.get("screen_height", 0)]
                detector.set_template_roi(key, meta["roi"], *dims)
        if not detector._ocr.available():
            self._log("ROI test " + key +
                      ": OCR engine unavailable — enable OCR (dev options) to test this ROI.")
            return False
        frame = io.grab()
        fe, price, text = detector.duplicate_info(frame)  # debug on -> dumps bands
        if key == "wheelspin_dup_name":
            self._log(f"ROI test {key}: read '{text}' -> FE={fe}")
        else:
            self._log(f"ROI test {key}: sell price read = {price}")
        png_path = os.path.join(debug_dir, key + ".png")
        if os.path.exists(png_path):
            self._log("Debug snapshot saved: " + png_path)
            try:
                os.startfile(png_path)
            except Exception:
                pass
        return True

    def test_template(self, tab, key):
        """Arm a developer-only one-shot template test.
        The actual frame is captured after the user presses the capture key so
        they can focus/unpause the game first."""
        cfg = config.load()
        if not cfg.get("dev_mode", False):
            return False
        if self._running():
            self._log("Template test unavailable while automation is running.")
            return False
        if self._tpl_folder(tab, key) is None:
            return False
        try:
            self._template_test_stop.set()
        except Exception:
            pass
        stop = threading.Event()
        self._template_test_stop = stop
        cap_key = str(cfg.get("capture_key", "caps lock") or "caps lock")
        up = cap_key.upper()
        self._status(f"Press {up} over the game to test '{key}'", False)
        self._log(f"Template test armed: focus the game, then press {up} for '{key}'. ESC cancels.")

        def _wait():
            try:
                import keyboard
                triggered = threading.Event()
                cap_hook = keyboard.add_hotkey(
                    cap_key, lambda: triggered.set(), suppress=False)
                esc_hook = keyboard.on_press_key(
                    "esc", lambda _e: stop.set(), suppress=False)
                try:
                    while not stop.is_set():
                        if triggered.wait(0.1):
                            break
                    if stop.is_set():
                        self._log("Template test cancelled.")
                        return
                    self._run_template_test_once(tab, key)
                finally:
                    try:
                        keyboard.remove_hotkey(cap_hook)
                    except Exception:
                        pass
                    try:
                        keyboard.unhook(esc_hook)
                    except Exception:
                        pass
            except Exception as e:
                self._log("Template test failed: " + str(e))
            finally:
                if self._template_test_stop is stop:
                    self._template_test_stop = threading.Event()
                self._status("Ready", False)

        threading.Thread(target=_wait, daemon=True).start()
        return True

    def capture_roi(self, tab, key):
        """Start a CAPS-LOCK region drag-select and save it as the template's
        DETECTION AREA (not a new template image). Mirrors capture_template but
        the drawn box is stored via save_roi (merged into the sidecar's "roi"
        field), which overrides the geometry/default ROI at detect time. Dev-only
        (the WebUI only shows the button under Settings -> Developer)."""
        folder = self._tpl_folder(tab, key)
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
                capture.save_roi(folder, key, (bx, by, bw, bh), w, h)
                self._log("Saved detection area: " + key)
            except Exception as e:
                self._log("Detection-area save failed: " + str(e))
            self._status("Ready", False)
            self._js(f"onCaptureDone({json.dumps(tab)})")

        def _cancel():
            self._log("Detection-area capture cancelled.")
            self._status("Ready", False)
            self._js(f"onCaptureDone({json.dumps(tab)})")

        self._cap_session = capture.CaptureSession(
            monitor_index=mon,
            window_title="Select detection area - " + key,
            callback=_done, on_cancel=_cancel,
            capture_key=cap_key, template_key=None, examples_dir=None)
        up = str(cap_key).upper()
        self._status(f"Press {up} over the game to set '{key}' detection area", False)
        self._log(f"Waiting for {up} - drag-select detection area for '{key}', ENTER to save, ESC to cancel.")
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

    def get_mastery_presets(self):
        cfg = config.load()
        preset_file = config.get_mastery_presets_file(
            config.resolve_template_lang(cfg))
        presets = list(_builtin_mastery_presets())
        try:
            for preset in _migrate_legacy_mastery_presets(preset_file):
                presets.append({
                    "name": preset["name"],
                    "builtin": False,
                    "order": _grid_as_wire(preset["order"]),
                })
        except Exception as e:
            self._log("Load mastery presets failed: " + str(e))
        return {"presets": presets}

    def save_mastery_preset(self, name, order):
        cfg = config.load()
        preset_file = config.get_mastery_presets_file(
            config.resolve_template_lang(cfg))
        clean_name = str(name or "").strip()
        builtin_names = {p["name"].lower() for p in _builtin_mastery_presets()}
        if clean_name.lower() in builtin_names:
            return {"ok": False,
                    "error": "That name is reserved by a built-in preset."}
        try:
            cells = [(int(p[0]), int(p[1])) for p in (order or [])]
            capture.save_grid_preset(preset_file, clean_name, cells)
            return {"ok": True,
                    "presets": self.get_mastery_presets().get("presets", [])}
        except Exception as e:
            self._log("Save mastery preset failed: " + str(e))
            return {"ok": False, "error": str(e)}

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
        self._pause = threading.Event()
        self._auto_reported = set()
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
                while self._pause.is_set() and not self._stop.is_set():
                    time.sleep(0.1)
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
                self._log(ocr_profile.describe_effective_profile(cfg))
            self._status("Running", True)
            import recovery as _recovery
            _recovery.set_log_lang(lang)
            _recovery.set_trigger_callback(self._auto_report)
            try:
                result = runner(cfg, self._stop, self._log,
                                lambda m: self._status(m, True),
                                pause_event=self._pause, **kwargs)
                if result is False and not self._stop.is_set():
                    self._auto_report(f"{self._func or 'Automation'} auto stopped")
            except Exception as e:
                import traceback
                self._log(f"ERROR: {e}")
                self._log(traceback.format_exc())
                if not self._stop.is_set():
                    self._auto_report(f"{self._func or 'Automation'} exception")
            finally:
                _recovery.set_trigger_callback(None)
                _recovery.set_log_lang("en")
            self._status("Ready", False)
            self._pause.clear()
            self._js("setPaused(false)")

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
            self._log("Full Auto isn't included in this build — rebuild with "
                      "FAFE_FULLAUTO=1.")
            self._status("Not in build", False)
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
            restart_cycles=self._int(cfg.get("full_auto_restart_cycles", 0)),
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
        old desktop UI used)."""
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
        self._pause.clear()
        self._js("setPaused(false)")
        return True

    def pause(self):
        if not self._running():
            return False
        self._pause.set()
        self._status("Paused", True)
        self._js("setPaused(true)")
        return True

    def resume(self):
        self._pause.clear()
        if self._running():
            self._status("Running", True)
        self._js("setPaused(false)")
        return True

    def toggle_pause(self):
        return self.resume() if self._pause.is_set() else self.pause()

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

    def check_updates(self):
        """WebUI startup check: read GitHub's latest release tag, never download."""
        if not config.load().get("update_check", True):
            return False

        def _found(tag, url):
            self._js(f"showUpdate({json.dumps(str(tag))}, {json.dumps(str(url))})")

        def _status(msg):
            self._log("[Updater] " + str(msg))

        updater.check_async(_found, on_status=_status)
        return True

    def open_update_page(self, url=None):
        """Open the releases page in the browser; the app does not download."""
        import webbrowser
        try:
            webbrowser.open(url or updater.RELEASES_PAGE)
        except Exception:
            pass
        return True

    def install_update(self):
        """Download and silently run the installer; packaged builds only,
        opt-out via auto_update."""
        cfg = config.load()
        lang = cfg.get("lang", "en")
        if not _is_frozen():
            return {"ok": False, "msg": _at("update_not_packaged", lang)}
        if not updater.running_from_installed_copy():
            return {"ok": False, "msg": _at("update_not_installed", lang)}
        if not cfg.get("auto_update", True):
            return {"ok": False, "msg": _at("update_disabled", lang)}
        if self._running():
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=5)
        url, size = updater.fetch_installer_asset()
        if not url:
            return {"ok": False, "msg": _at("update_fetch_fail", lang)}
        dest = os.path.join(UPDATE_DIR, updater.INSTALLER_NAME)
        try:
            os.makedirs(UPDATE_DIR, exist_ok=True)
            updater.download_installer(
                url, dest,
                on_progress=lambda d, t: self._js(f"updateProgress({int(d)},{int(t)})"))
        except Exception as e:
            return {"ok": False, "msg": _at("update_download_fail", lang, err=str(e))}
        if not updater.verify_installer(dest, size):
            try:
                os.remove(dest)
            except OSError:
                pass
            return {"ok": False, "msg": _at("update_verify_fail", lang)}
        self._log("[Updater] launching silent installer")
        try:
            subprocess.Popen([dest, "/VERYSILENT"], close_fds=True)
        except Exception as e:
            return {"ok": False, "msg": _at("update_launch_fail", lang, err=str(e))}
        return {"ok": True, "msg": _at("update_launched", lang)}

    def _clear_hotkeys(self):
        try:
            if getattr(self, "_win_hotkeys", None) is not None:
                self._win_hotkeys.stop()
                self._win_hotkeys = None
        except Exception:
            pass
        try:
            import keyboard
            for h in getattr(self, "_hotkeys", []):
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
        except Exception:
            pass
        self._hotkeys = []

    def _register_hotkeys(self):
        """(Re)bind global hotkeys. Prefer Win32 RegisterHotKey because Forza's
        borderless/foreground input path can starve low-level keyboard hooks;
        keep keyboard.add_hotkey as fallback for unsupported or failed keys."""
        self._clear_hotkeys()
        cfg = config.load()
        bindings = [
            (cfg.get("toggle_key", "f9"),
             lambda: self._js(f"onHotkey({json.dumps('f9')})")),
            (cfg.get("pause_key", "f8"), self.toggle_pause),
            (cfg.get("report_key", "f12"),
             lambda: self._js(f"onHotkey({json.dumps('f12')})")),
            (cfg.get("overlay_key", "f10"), self.toggle_overlay),
        ]

        registered = set()
        try:
            self._win_hotkeys = _WinHotkeyThread(bindings)
            registered = self._win_hotkeys.start()
        except Exception:
            self._win_hotkeys = None
            registered = set()

        fallback = [(str(combo or "").strip().lower(), cb)
                    for combo, cb in bindings
                    if combo and str(combo).strip().lower() not in registered]
        if not fallback:
            return
        try:
            import keyboard
        except Exception:
            return
        for combo, cb in fallback:
            if not combo:
                continue
            try:
                self._hotkeys.append(keyboard.add_hotkey(combo, cb))
            except Exception:
                pass

    _SHORTCUT_KEYS = {"toggle": "toggle_key", "pause": "pause_key", "capture": "capture_key",
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
        if which in ("toggle", "pause", "report", "overlay"):
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
            self._pause.clear()
            self._template_test_stop.set()
        except Exception:
            pass
        try:
            capture.unmute_tracked_processes()
        except Exception:
            pass
        try:
            from gameio import set_mute_held
            set_mute_held(False)
        except Exception:
            pass
        try:
            self._clear_hotkeys()
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
                                   on_func=self._overlay_select_func, log=self._log,
                                   monitor_index=cfg.get("monitor_index", 1))
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
                self._overlay.show(cfg.get("overlay_x", 60), cfg.get("overlay_y", 60),
                                   monitor_index=cfg.get("monitor_index", 1))
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
    _GUIDE_SLUGS = {"full_auto": "full-auto",
                    "race": "race-auto-grind", "buy": "auto-buy-cars-in-batch",
                    "wheelspin": "auto-wheelspin",
                    "mastery": "auto-unlock-spin-wheel-mastery-tree",
                    "delete": "delete-used-cars"}

    def howto(self, func=None):
        """Open the web guide — the per-function page when known, else the index."""
        import webbrowser
        slug = self._GUIDE_SLUGS.get(func)
        cfg = config.load()
        lang = "zh-tw" if cfg.get("lang") == "zh-tw" else "en"
        url = self._GUIDE_BASE + (f"{lang}/guides/{slug}/" if slug else "")
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
        """Open the configured checkout for the paid Full Auto unlock."""
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
        _TITLE,
        _webui("index.html"),
        js_api=api,
        width=1240, height=860,
        background_color="#0A0E14",
        min_size=(1040, 640),   # never thin enough to wrap the loop progress bar
    )
    api._window = window
    window.events.loaded += lambda: _apply_titlebar_theme(
        config.load().get("theme_preset", "default"), api._running_flag, window)
    api.create_overlay()        # second window (hidden unless overlay was left on)
    api._register_hotkeys()     # global F9 / F12 / F10 (work while the game is focused)
    # Closing the main window must tear down the overlay window + hotkeys too,
    # else webview.start() never returns and msedgewebview2.exe lingers.
    window.events.closing += api.shutdown
    # DevTools (right-click ▸ Inspect) on in dev, OFF in a packaged build.
    _purge_update_dir()
    webview.start(debug=not _is_frozen())
    # Loop ended (all windows closed) → force a clean full teardown so no daemon
    # thread or WebView2 child process is left behind.
    os._exit(0)


if __name__ == "__main__":
    main()
