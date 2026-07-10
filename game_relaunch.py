from __future__ import annotations

import ctypes
import subprocess
import time
from dataclasses import dataclass
from typing import Callable


STEAM_URI = "steam://rungameid/2483190"
GAMEPASS_APP_NAME = "Forza Horizon 6"
GAMEPASS_FALLBACK_APPID = "Microsoft.ForteBaseGame_8wekyb3d8bbwe!Forzahorizon6"

_WM_CLOSE = 0x0010
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259


@dataclass(frozen=True)
class LaunchTarget:
    platform: str
    command: list[str]
    appid: str | None = None


def _steam_command(uri: str) -> list[str]:
    return ["cmd", "/c", "start", "", uri or STEAM_URI]


def _xbox_command(appid: str) -> list[str]:
    return ["explorer.exe", fr"shell:AppsFolder\{appid}"]


def infer_platform_from_process_path(path: str | None) -> str | None:
    p = (path or "").lower()
    if not p:
        return None
    if "steamapps" in p or "\\steam\\" in p or "/steam/" in p:
        return "steam"
    if "windowsapps" in p or "microsoft.fortebasegame" in p:
        return "xbox"
    return None


def detect_gamepass_appid(app_name: str = GAMEPASS_APP_NAME,
                          runner: Callable = subprocess.run) -> str | None:
    query = (
        f'Get-StartApps | Where-Object {{ $_.Name -like "*{app_name}*" }} | '
        "Select-Object -First 1 -ExpandProperty AppID"
    )
    try:
        res = runner(
            ["powershell", "-NoProfile", "-Command", query],
            capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    if getattr(res, "returncode", 1) != 0:
        return None
    appid = (getattr(res, "stdout", "") or "").strip().splitlines()
    return appid[0].strip() if appid and appid[0].strip() else None


def resolve_launch_target(cfg: dict, process_path: str | None = None,
                          appid_lookup: Callable[[str], str | None] | None = None
                          ) -> LaunchTarget:
    platform = str(cfg.get("game_platform", "auto") or "auto").lower()
    appid_lookup = appid_lookup or detect_gamepass_appid

    if platform == "auto":
        platform = infer_platform_from_process_path(process_path) or "auto"
        if platform == "auto":
            detected = appid_lookup(cfg.get("gamepass_app_name", GAMEPASS_APP_NAME))
            if detected:
                return LaunchTarget("xbox", _xbox_command(detected), detected)
            platform = "steam"

    if platform == "xbox":
        appid = (appid_lookup(cfg.get("gamepass_app_name", GAMEPASS_APP_NAME))
                 or cfg.get("gamepass_fallback_appid")
                 or GAMEPASS_FALLBACK_APPID)
        return LaunchTarget("xbox", _xbox_command(appid), appid)

    if platform == "custom":
        cmd = str(cfg.get("game_custom_launch", "") or "").strip()
        if cmd:
            return LaunchTarget("custom", ["cmd", "/c", cmd])

    uri = cfg.get("game_steam_uri", STEAM_URI)
    return LaunchTarget("steam", _steam_command(uri))


def get_process_path(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.QueryFullProcessImageNameW.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_uint)]
        k32.QueryFullProcessImageNameW.restype = ctypes.c_int
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return None
        try:
            size = ctypes.c_uint(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
        finally:
            k32.CloseHandle(handle)
    except Exception:
        return None
    return None


def _post_wm_close(hwnd) -> bool:
    try:
        u32 = ctypes.windll.user32
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_size_t]
        return bool(u32.PostMessageW(hwnd, _WM_CLOSE, 0, 0))
    except Exception:
        return False


def _process_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_ulong)]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong(0)
            return bool(k32.GetExitCodeProcess(handle, ctypes.byref(code)) and
                        code.value == _STILL_ACTIVE)
        finally:
            k32.CloseHandle(handle)
    except Exception:
        return False


def _taskkill(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        res = subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                             capture_output=True, text=True, timeout=10)
        return res.returncode == 0
    except Exception:
        return False


def close_game_window(hwnd, pid: int | None, wait_s: float = 10.0,
                      post_close: Callable = _post_wm_close,
                      is_running: Callable[[int | None], bool] = _process_running,
                      kill_process: Callable[[int | None], bool] = _taskkill,
                      sleep: Callable[[float], None] = time.sleep) -> bool:
    closed = post_close(hwnd) if hwnd else False
    deadline = time.monotonic() + max(0.0, float(wait_s or 0.0))
    while pid and time.monotonic() < deadline:
        if not is_running(pid):
            return True
        sleep(0.25)
    if pid and is_running(pid):
        return bool(kill_process(pid))
    return closed or not pid


def launch_game(target: LaunchTarget, popen: Callable = subprocess.Popen) -> bool:
    try:
        popen(target.command)
        return True
    except Exception:
        return False


def _mark_fafe_launched(cfg: dict) -> dict:
    cfg["_game_launched_by_fafe"] = True
    cfg["gameio_disable_letterbox_crop"] = True
    return cfg


def _wait_for_game_window(cfg: dict, log_cb, timeout_s: float = 120.0,
                          find_window=None,
                          sleep: Callable[[float], None] = time.sleep,
                          stop_cb: Callable[[], bool] | None = None):
    import capture
    find_window = find_window or capture.find_game_window
    stop_cb = stop_cb or (lambda: False)
    title = cfg.get("background_window_title", "Forza Horizon 6")
    deadline = time.monotonic() + max(0.0, float(timeout_s or 0.0))
    while time.monotonic() < deadline:
        if stop_cb():
            log_cb("  ! Game launch route stopped while waiting for the game window.")
            return None
        hwnd = find_window(title)
        if hwnd:
            return hwnd
        sleep(1.0)
    log_cb("  ! Relaunched game window was not found in time.")
    return None


def _call_post_launch(post_launch_fn, cfg: dict, log_cb, stop_cb) -> bool:
    try:
        return bool(post_launch_fn(cfg, log_cb, stop_cb=stop_cb))
    except TypeError:
        return bool(post_launch_fn(cfg, log_cb))


def return_to_main_menu_after_launch(cfg: dict, log_cb=None,
                                     stop_cb: Callable[[], bool] | None = None) -> bool:
    """Template-gated route from a freshly launched game back to the main menu."""
    log_cb = log_cb or (lambda _msg: None)
    stop_cb = stop_cb or (lambda: False)
    import numpy as np

    import config
    from capture import load_template
    from detector import ScreenDetector
    from gameio import GameIO

    fresh = config.load()
    fresh.update(cfg or {})
    fresh["gameio_disable_letterbox_crop"] = True
    fresh["gameio_quiet_keepalive_log"] = True
    lang = config.resolve_template_lang(fresh)
    if not _wait_for_game_window(fresh, log_cb, stop_cb=stop_cb):
        return False

    io = GameIO(fresh, log_cb)
    io.start_keepalive(stop_cb, fresh)
    detector = ScreenDetector(fresh, on_auto_ocr=log_cb)
    prefer_ref = fresh.get("template_prefer_reference", True)
    relaunch_folder = config.get_relaunch_templates(config.REFERENCE_RES, lang)
    race_folder = config.get_race_templates(config.REFERENCE_RES, lang)
    full_auto_folder = config.get_full_auto_templates(config.REFERENCE_RES, lang)

    def register_template(folder: str, key: str):
        img, _scale, meta = load_template(
            folder, key, io.width, io.height, grayscale=True,
            ref_folder=folder, prefer_ref=prefer_ref)
        box = meta.get("box")
        if box:
            detector.set_template_geometry(
                key, box, meta.get("screen_width", io.width),
                meta.get("screen_height", io.height))
        if meta.get("roi"):
            detector.set_template_roi(key, meta["roi"],
                                      meta.get("screen_width", 0),
                                      meta.get("screen_height", 0))
        return img

    try:
        templates = {
            "launch_start_prompt": register_template(
                relaunch_folder, "launch_start_prompt"),
            "launch_continue": register_template(
                relaunch_folder, "launch_continue"),
            "cars_tab": register_template(full_auto_folder, "cars_tab"),
            "anna": register_template(full_auto_folder, "anna"),
            "creative_hub": register_template(race_folder, "creative_hub"),
        }
    except FileNotFoundError as e:
        log_cb(f"  ! Relaunch route template missing: {e}")
        io.cleanup()
        return False

    def grab():
        frame = io.grab()
        if frame is not None:
            return frame
        return np.zeros((max(1, io.height), max(1, io.width), 3),
                        dtype=np.uint8)

    def threshold(key: str) -> float:
        return float(fresh.get("thresh_" + key, 0.70))

    def wait_for(key: str, timeout_key: str, label: str) -> bool:
        log_cb(f"  > Relaunch route: waiting for {label}.")
        result = detector.wait_for(
            frame_cb=grab,
            key=key,
            template=templates[key],
            threshold=threshold(key),
            stop_cb=stop_cb,
            interval=0.5,
            timeout=float(fresh.get(timeout_key, 45.0) or 45.0),
            on_warn=lambda best: log_cb(
                f"  ! Still waiting for {label} "
                f"(best {best.source}: {best.score:.0%})."),
        )
        if result.matched:
            log_cb(f"  > Relaunch route: detected {label}.")
            return True
        log_cb(f"  ! Relaunch route failed waiting for {label}.")
        return False

    def press(key: str, post_wait: float = 1.0):
        if stop_cb():
            return
        log_cb(f"  > Relaunch route: pressing {key.upper()}.")
        io.press(key, post_wait=post_wait)

    try:
        if stop_cb():
            return False
        if not wait_for("launch_start_prompt", "game_launch_start_timeout",
                        "launch start prompt"):
            return False
        press("enter")
        if stop_cb():
            return False
        # The launching window resizes as the game loads (small splash → full
        # screen). GameIO registered/height-scaled the templates at that initial
        # SMALL size, but detection now runs on the full-size frame — so
        # launch_continue's template is scaled ~2.4x too small and misses at ~56%
        # even with its ROI correctly on the prompt (the template-test tool never
        # sees this: it registers on the already-settled full-size window). Now
        # that the start prompt has fired, the window is at its final size: refresh
        # it and re-register the remaining templates at the current dimensions.
        io._maybe_refresh_window(force=True)
        log_cb(f"  > Relaunch route: window at {io.width}x{io.height}; "
               f"re-loading templates at current size.")
        for _k, _folder in (("launch_continue", relaunch_folder),
                            ("cars_tab", full_auto_folder),
                            ("anna", full_auto_folder),
                            ("creative_hub", race_folder)):
            try:
                templates[_k] = register_template(_folder, _k)
            except FileNotFoundError:
                pass
        if not wait_for("launch_continue", "game_launch_continue_timeout",
                        "continue menu"):
            return False
        press("enter")
        if stop_cb():
            return False
        if not wait_for("cars_tab", "game_launch_home_timeout", "home menu"):
            return False
        press("escape")
        if stop_cb():
            return False
        if not wait_for("anna", "game_launch_open_world_timeout",
                        "open-world home icon"):
            return False
        press("escape")
        if stop_cb():
            return False
        if not wait_for("creative_hub", "game_launch_main_menu_timeout",
                        "main menu"):
            return False
        log_cb("  > Relaunch route returned to the main menu.")
        return True
    finally:
        io.cleanup()


def relaunch_game(cfg: dict, log_cb=None,
                  find_window=None, get_pid=None,
                  process_path_fn: Callable[[int | None], str | None] = get_process_path,
                  close_fn: Callable = close_game_window,
                  launch_fn: Callable[[LaunchTarget], bool] = launch_game,
                  post_launch_fn: Callable[[dict, Callable], bool] | None = None,
                  sleep: Callable[[float], None] = time.sleep,
                  stop_cb: Callable[[], bool] | None = None) -> bool:
    log_cb = log_cb or (lambda _msg: None)
    stop_cb = stop_cb or (lambda: False)
    if not cfg.get("game_relaunch_enabled", True):
        log_cb("  ! Game relaunch is disabled.")
        return False
    if stop_cb():
        return False

    import capture
    find_window = find_window or capture.find_game_window
    get_pid = get_pid or capture.get_window_pid

    hwnd = find_window(cfg.get("background_window_title", "Forza Horizon 6"))
    pid = get_pid(hwnd) if hwnd else None
    path = process_path_fn(pid)
    target = resolve_launch_target(cfg, process_path=path)

    if hwnd:
        log_cb("  ! Closing stuck game before relaunch.")
        close_fn(hwnd, pid)
        if stop_cb():
            return False
        sleep(float(cfg.get("game_relaunch_delay", 8.0) or 8.0))
        if stop_cb():
            return False

    log_cb(f"  ! Relaunching game via {target.platform}.")
    if not launch_fn(target):
        return False
    _mark_fafe_launched(cfg)
    post_launch_fn = post_launch_fn or return_to_main_menu_after_launch
    return _call_post_launch(post_launch_fn, cfg, log_cb, stop_cb)


def ensure_game_ready_for_start(
        cfg: dict, log_cb=None, find_window=None,
        launch_fn: Callable[[LaunchTarget], bool] = launch_game,
        post_launch_fn: Callable[[dict, Callable], bool] | None = None,
        appid_lookup: Callable[[str], str | None] | None = None,
        stop_cb: Callable[[], bool] | None = None) -> bool:
    """Ensure the game is already open, or launch it and route to main menu."""
    log_cb = log_cb or (lambda _msg: None)
    stop_cb = stop_cb or (lambda: False)

    import capture
    find_window = find_window or capture.find_game_window

    title = cfg.get("background_window_title", "Forza Horizon 6")
    if find_window(title):
        return True
    if stop_cb():
        return False

    if not cfg.get("game_relaunch_enabled", True):
        log_cb("  ! Game is not open and game launch is disabled.")
        return False

    target = resolve_launch_target(cfg, process_path=None,
                                   appid_lookup=appid_lookup)
    log_cb(f"  ! Game window not detected; launching via {target.platform}.")
    if not launch_fn(target):
        return False
    _mark_fafe_launched(cfg)
    post_launch_fn = post_launch_fn or return_to_main_menu_after_launch
    return _call_post_launch(post_launch_fn, cfg, log_cb, stop_cb)
