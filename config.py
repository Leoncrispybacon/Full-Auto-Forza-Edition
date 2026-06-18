# ============================================================
#  config.py — Central configuration and path management
# ============================================================

import os
import mss
import sys
import json
import ctypes

# ── Base path (works both frozen exe and dev) ────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Flat structure — config.py sits alongside forza_app.py
    BASE_DIR = os.path.dirname(os.path.abspath(
        sys.argv[0] if '__file__' not in dir() else __file__))
    # If we're inside an app/ subfolder, go up one level
    if os.path.basename(BASE_DIR).lower() == 'app':
        BASE_DIR = os.path.dirname(BASE_DIR)

CONFIG_FILE       = os.path.join(BASE_DIR, "config.json")
TEMPLATES_DIR     = os.path.join(BASE_DIR, "templates")

# Only the single built-in (auto-scaled) set now — the user-capture "custom"
# mode was removed (built-in is reliable enough). Kept as a list for the
# dir-creation loop below.
RESOLUTION_SETS = ["built-in"]

# The bundled template set lives in the "built-in" folder. It's authored once at
# the highest resolution (4K) and DOWNSCALED at load time to the detected
# monitor — downscaling preserves edges/text far better than upscaling — so one
# set serves every resolution (see capture.load_template ref_folder /
# template_prefer_reference). The folder was renamed from "2160p" to "built-in"
# once the per-resolution picks (1080p/1440p/2160p) were dropped; config.load
# migrates any stored preset value to this.
REFERENCE_RES = "built-in"

# ── Template languages ───────────────────────────────────────
# Templates are organised by the language of the GAME's on-screen menus (NOT
# the app UI) — the captured images contain that text, so the set must match
# what's rendered in-game. Layout: templates/<lang>/<category>/<res>/ plus
# templates/<lang>/examples/.
#   cht = Traditional Chinese · en = English
TEMPLATE_LANGS = ["cht", "en"]
DEFAULT_TEMPLATE_LANG = "cht"

# Default game-template language per app-UI language (used when the
# `template_lang` setting is "auto").
_APP_LANG_TO_TPL = {"zh-tw": "cht", "en": "en"}


def resolve_template_lang(cfg: dict) -> str:
    """Which game-template language set to use.

    `template_lang` config: "auto" (follow the app UI language) or an explicit
    cht / en. Defaults to auto."""
    val = str(cfg.get("template_lang", "auto") or "auto").lower()
    if val in TEMPLATE_LANGS:
        return val
    return _APP_LANG_TO_TPL.get(cfg.get("lang", "zh-tw"), DEFAULT_TEMPLATE_LANG)


def _lang_dir(lang: str) -> str:
    return os.path.join(TEMPLATES_DIR,
                        lang if lang in TEMPLATE_LANGS else DEFAULT_TEMPLATE_LANG)


def get_race_templates(res: str = REFERENCE_RES,
                       lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    path = os.path.join(_lang_dir(lang), "race", res)
    os.makedirs(path, exist_ok=True)
    return path


def get_mastery_templates(res: str = REFERENCE_RES,
                          lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    path = os.path.join(_lang_dir(lang), "mastery_full", res)
    os.makedirs(path, exist_ok=True)
    return path


def get_nodes_file(res: str = REFERENCE_RES,
                   lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    return os.path.join(get_mastery_templates(res, lang), "mastery_nodes.json")


def get_wheelspin_templates(res: str = REFERENCE_RES,
                            lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    path = os.path.join(_lang_dir(lang), "wheelspin", res)
    os.makedirs(path, exist_ok=True)
    return path


def get_buy_templates(res: str = REFERENCE_RES,
                      lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    path = os.path.join(_lang_dir(lang), "buy", res)
    os.makedirs(path, exist_ok=True)
    return path


def get_full_auto_templates(res: str = REFERENCE_RES,
                            lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    """Templates used ONLY by the Full Auto chained orchestrator's transition
    navigation (e.g. the mastery positioning nav). Reusable per-function nav
    templates (race/buy/wheelspin) live in those functions' own folders;
    this folder holds the chain-only ones, grouped by category in the UI."""
    path = os.path.join(_lang_dir(lang), "full_auto", res)
    os.makedirs(path, exist_ok=True)
    return path


def get_mastery_grid_file(lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    """The mastery-tree unlock path spec (an ordered list of 4x4 grid cells).
    Resolution-independent — it's a logical cell sequence, not pixel coords — so
    it lives directly under the category folder, not a per-resolution subfolder.
    Mastery tab and Full Auto keep SEPARATE specs (different car trees)."""
    d = os.path.join(_lang_dir(lang), "mastery_full")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "mastery_grid.json")


def get_full_auto_grid_file(lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    """Full Auto's own mastery-tree unlock path spec (for the 22B tree)."""
    d = os.path.join(_lang_dir(lang), "full_auto")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "mastery_grid.json")


def get_examples_dir(lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    path = os.path.join(_lang_dir(lang), "examples")
    os.makedirs(path, exist_ok=True)
    return path


def _migrate_flat_templates():
    """Move any pre-language flat layout (templates/{race,mastery_full,examples})
    into templates/cht/, preserving the user's custom captures. The old presets
    were all Traditional Chinese, so cht is the correct destination. Merges
    rather than overwrites (so updater-installed cht presets aren't clobbered),
    then removes the emptied old tree. Idempotent."""
    import shutil
    cht = _lang_dir("cht")
    for sub in ("race", "mastery_full", "examples"):
        old = os.path.join(TEMPLATES_DIR, sub)
        if not os.path.isdir(old):
            continue
        new = os.path.join(cht, sub)
        for root, _dirs, files in os.walk(old):
            rel = os.path.relpath(root, old)
            dst_root = new if rel == "." else os.path.join(new, rel)
            os.makedirs(dst_root, exist_ok=True)
            for fn in files:
                dst_f = os.path.join(dst_root, fn)
                if not os.path.exists(dst_f):
                    try:
                        shutil.move(os.path.join(root, fn), dst_f)
                    except Exception:
                        pass
        try:
            shutil.rmtree(old)
        except Exception:
            pass


# Migrate any old flat layout, THEN ensure the per-language tree exists.
_migrate_flat_templates()
for _lang in TEMPLATE_LANGS:
    for _mode in ("race", "mastery_full", "full_auto"):
        for _res in RESOLUTION_SETS:
            os.makedirs(os.path.join(TEMPLATES_DIR, _lang, _mode, _res),
                        exist_ok=True)
    os.makedirs(os.path.join(TEMPLATES_DIR, _lang, "examples"), exist_ok=True)

# ── Defaults ─────────────────────────────────────────────────
def _get_primary_monitor_index() -> int:
    """Return the mss index of the primary monitor (left=0, top=0)."""
    try:
        with mss.mss() as sct:
            for i, m in enumerate(sct.monitors[1:], start=1):
                if m["left"] == 0 and m["top"] == 0:
                    return i
    except Exception:
        pass
    return 1


DEFAULTS = {
    "lang":              "en",
    # First-run language picker gate. DEFAULTS=True so existing users (whose
    # config.json predates this key) are back-filled True and never see the
    # picker. The SHIPPED config.json sets it false, so a fresh download shows
    # the picker once, then sets it True.
    "lang_chosen":       True,
    "theme":             "system",
    "toggle_key":        "f9",
    "capture_key":       "caps lock",
    "report_key":        "f12",
    "overlay_key":       "f10",
    "monitor_index":     _get_primary_monitor_index(),
    # Detection debug: when true, every detection saves an annotated snapshot
    # (ROI searched + best-match cross + score/threshold/source/matched) to a
    # `debug/` folder next to the exe — one image per template key, overwritten
    # live. For diagnosing why a step mis-detected. Off for normal use.
    "debug_detection":   False,
    # OCR confirmation during detection. Default OFF: the onnxruntime inference
    # is CPU-heavy and stutters the game (esp. on 1080p / lower-core machines),
    # and pixel matching at native res is reliable on its own. Turn ON for more
    # robust matching on atypical hardware (HDR/heavy-AA/non-native scaling).
    "detector_enable_ocr": False,
    # Game-menu language for templates: "auto" (follow app UI lang) / cht / en
    "template_lang":      "auto",
    # Race settings
    "race_threshold":    0.60,
    # Per-template thresholds. Race Auto detects start_menu + restart_menu
    # (racing/confirm are blind timing). Mastery is keyboard-driven — no
    # templates, so no mastery thresholds.
    "thresh_start_menu":           0.60,
    "thresh_restart_menu":         0.60,
    # Race menu-navigation templates (optional — used to auto-walk from the main
    # menu to the Start screen before the AFK loop; skipped if not captured).
    "thresh_creative_hub":         0.60,
    "thresh_eventlab":             0.60,
    "thresh_play_event":           0.60,
    "thresh_events_arrow":         0.60,
    "thresh_my_history":           0.60,
    "thresh_choose_race_type":     0.60,
    "thresh_car_select":           0.60,
    # Race exit: the recommended "What's Next" menu shown after Continue.
    "thresh_next_activity":        0.60,
    "race_check_interval":    0.5,
    "race_post_key_wait":     0.75,
    # Mastery settings (keyboard-driven; no detection)
    "mastery_start_loop":     1,
    # Cutscene ("Ride This Car") wait before ESC — default 11, user-raisable
    # via a Settings slider (min 11). The other mastery step waits
    # (screen/tap + menu-transition delays) stay FIXED constants in mastery.py.
    "mastery_cutscene_wait":  11.0,
    # Grid node-unlock settle (after Enter, before the next node's move) for the
    # keyboard mastery-tree nav. Higher helps weaker hardware register the
    # unlock; default 1.25, Settings slider 1–2s.
    "mastery_grid_unlock_wait": 1.25,
    # Standalone mastery garage block (which contiguous run of cars to unlock).
    # The My Cars grid fills column-major TOP→BOTTOM; the block is the first
    # car's row in column 0, N full columns between, and the last car's row in
    # the final column. Total = (3 - first_row + 1) + middle*3 + last_row.
    "mastery_block_first_row":  1,
    "mastery_block_middle_cols": 0,
    "mastery_block_last_row":   3,
    # Delete Cars uses the same garage-block picker to count cars to delete
    # (the loop is unchanged; this is just a clearer way to set the count).
    "delete_block_first_row":   1,
    "delete_block_middle_cols": 0,
    "delete_block_last_row":    3,
    # Delay after each menu cursor tap (Up/Down arrows) shared by Mastery's
    # in-menu nav and Delete Cars. Higher helps weaker hardware register each
    # tap; default 0.25, Settings slider 0.1–0.5s.
    "menu_tap_wait":          0.25,
    # Full Auto (chained orchestrator): branch after selling — "racing" (loop
    # straight back to racing, no wheelspin) | "wheelspin" (run wheelspin each
    # cycle). The buy/master/sell count is fixed (33) in full_auto.py.
    "full_auto_branch_mode":  "racing",
    # How many cars the chain buys, unlocks mastery on, and sells per cycle.
    # Default 33 (999 max mastery pts ÷ 30 per Subaru 22B); user-adjustable for
    # those who farm differently.
    "full_auto_car_count":    33,
    # Which step the FIRST cycle starts at — "race" (full cycle) | "buy" |
    # "mastery" | "sell" — for users who already have points/cars lined up.
    # Cycle 2 onward always runs the full loop from racing.
    "full_auto_start_from":   "race",
    # Full Auto chain-only navigation templates (grouped by category in the
    # Setup panel). Currently the mastery positioning nav: main menu → My
    # Horizon → Return Home → CARS → My Cars → sort Recently Added → newest car.
    # my_horizon_tab is reused from the wheelspin set, so it isn't listed here.
    "thresh_return_home":     0.60,
    "thresh_cars_tab":        0.60,
    "thresh_recently_added":  0.60,
    # Sell step (chained-only): My Cars option clicked after riding the
    # non-target car (re-enters the grid before the re-sort + sell block).
    "thresh_my_cars":         0.60,
    # Sell step: the "My Cars" header (top-left) — confirms the grid finished
    # loading before pressing X (pressing X mid-load drops the sort menu).
    "thresh_my_cars_header":  0.60,
    # Sell exit: the home icon shown when leaving the home menu — confirms we
    # backed out to the open world so the final ESC opens the main menu.
    "thresh_anna":            0.60,
    # Sell re-select grind car: the "Select An Action" menu that opens after
    # clicking the car tile — gates the "Get In Car" Enter (was a blind press).
    "thresh_select_action":   0.60,
    # Sell re-select grind car: brand button (manufacturer jump) + car tile.
    "thresh_grind_brand":     0.60,
    "thresh_grind_car":       0.60,
    # Full Auto pre-flight checklist: the "car to the right isn't new" item is a
    # one-time garage layout, so it persists (the driving/map/credits items are
    # per-session and reset each launch).
    "fa_check_neighbor_ok":   False,
    # Buy / Delete settings
    "buy_post_key_wait":      0.5,
    "delete_post_key_wait":   0.5,
    # Buy menu-navigation (optional — start/end the buy run on the main menu;
    # skipped if these templates aren't captured).
    "thresh_collection_log":      0.60,
    "thresh_discover_japan":      0.60,
    "thresh_car_collection":      0.60,
    "thresh_subaru":              0.60,
    "thresh_buy_target_car":      0.60,
    # Auto Spin Wheel settings. dup_mode is "garage" (safe) | "sell" (sells
    # duplicates UNATTENDED — warned in the UI).
    "thresh_wheelspin_duplicate": 0.60,
    "thresh_super_wheelspin":     0.60,
    "thresh_normal_wheelspin":    0.60,
    "thresh_my_horizon_tab":      0.60,
    "thresh_wheelspin_skip":      0.60,
    "thresh_wheelspin_collect":   0.60,
    "thresh_wheelspin_collect_final": 0.60,
    "wheelspin_post_key_wait":   0.5,
    "wheelspin_dup_mode":        "garage",
    # Which wheel to spin: "super" (Super Wheelspin, 3 prizes) | "normal"
    # (Wheelspin, 1 prize). Only changes which tile template is clicked to
    # start; the rest of the flow is identical.
    "wheelspin_type":            "super",
    # Use the single REFERENCE_RES template set for ALL preset resolutions
    # (downscaled), instead of per-resolution captures. Reversible kill-switch:
    # set false to go back to using each resolution's own folder. Custom
    # templates are never affected (they're the user's own capture).
    "template_prefer_reference": True,
    # UI / behavior toggles
    "theme_preset":           "default",   # color scheme (see theme.THEME_PRESETS)
    "ui_scale":               "auto",
    "nodes_aspect_fix":       True,
    "auto_english_ime":       True,
    # Window-aware IO (gameio.GameIO), used by EVERY function. When the game
    # window is found by title, FAFE drives it through that window: capturing its
    # client area (works windowed OR borderless, even when covered) and sending
    # input via PostMessage (works whether the game is focused or not). If the
    # window isn't found, it falls back to whole-monitor capture + SendInput to
    # the focused window. KILL-SWITCH: set false to force the legacy path
    # everywhere. No user-facing toggle — it adapts automatically.
    "background_input":       True,
    "background_window_title": "Forza Horizon 6",
    # Re-assert "active" to the window so it doesn't auto-pause while unfocused
    # (best-effort; only works if the game trusts WM_ACTIVATE/ACTIVATEAPP).
    "background_fake_focus":  True,
    # Capture method when driving the window: "window" = PrintWindow the window's
    # content directly (works even when another window covers it) | "region" =
    # grab the screen rectangle it occupies (fast, but blank if occluded).
    # PrintWindow may return black for some DirectX games — switch to "region".
    "background_capture":     "window",
    # When the window's aspect ratio differs from the game's render aspect, the
    # game draws black letterbox/pillarbox bars inside the client. Detect them
    # once at run start and crop the capture to the game content so detection
    # (template scaling + ROIs) lines up. KILL-SWITCH: set false to disable.
    "crop_letterbox":         True,
    # Mute ONLY the game's audio while an automation run is active (per-app;
    # leaves other apps' sound alone), and unmute when it stops. Settings toggle.
    "mute_game":              False,
    "overlay_enabled":        False,
    # Read-only version check on startup (no download — opens the releases page
    # if a newer version exists). Set false for a fully offline build that makes
    # zero network requests (e.g. to satisfy Nexus's no-internet policy).
    "update_check":           True,
}


def load() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # Unreadable/corrupt — fall back to defaults but DON'T overwrite the
            # file (it may be recoverable / the user's).
            return dict(DEFAULTS)
        # Fill in any missing keys with defaults, and persist them back so the
        # file stays complete + self-documenting across app updates. The updater
        # leaves config.json untouched, so without this, keys added in a new
        # version (e.g. auto_english_ime) would never appear in an existing
        # user's file for them to see or toggle.
        added = False
        for k, v in DEFAULTS.items():
            if k not in data:
                data[k] = v
                added = True
        # Migrate dropped Simplified Chinese (zh-cn / chs templates) → Traditional
        # so existing SC users land on a maintained language, not English fallback.
        if data.get("lang") == "zh-cn":
            data["lang"] = "zh-tw"
            added = True
        if data.get("template_lang") == "chs":
            data["template_lang"] = "auto"
            added = True
        # Validate monitor index against available monitors (runtime-only;
        # doesn't itself trigger a rewrite).
        try:
            with mss.mss() as sct:
                n = len(sct.monitors) - 1
            if data['monitor_index'] > n or data['monitor_index'] < 1:
                data['monitor_index'] = _get_primary_monitor_index()
        except Exception:
            pass
        if added:
            save(data)
        return data
    # No config yet — create one from defaults so the file exists + is complete.
    data = dict(DEFAULTS)
    save(data)
    return data


def save(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[config] Failed to save: {e}")


# ── DPI / resolution scaling ─────────────────────────────────
# 1080p is the baseline. We scale UI elements proportionally.

def get_scale_factor() -> float:
    """
    Returns a scale factor relative to 1080p height.
    On a 1440p screen this returns ~1.33, on 4K ~2.0.
    Clamped between 0.8 and 2.5 to avoid extreme sizes.
    """
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        h = user32.GetSystemMetrics(1)   # screen height in physical pixels
        factor = h / 1080.0
        return max(0.8, min(2.5, factor))
    except Exception:
        return 1.0


def s(px: int) -> int:
    """Scale a pixel value relative to 1080p baseline."""
    return int(px * get_scale_factor())


# UI scale options shown in Settings. "auto" = derive from screen resolution
# (get_scale_factor); the rest are explicit multipliers stored as e.g. "150%".
UI_SCALE_OPTIONS = ["auto", "100%", "125%", "150%", "175%", "200%", "250%"]


def resolve_ui_scale(cfg: dict) -> float:
    """Resolve the saved `ui_scale` setting to a CustomTkinter scaling factor.

    Accepts "auto" (resolution-derived), a percentage string like "150%", or a
    raw float. Clamped to a sane range so a stale/bad value can't make the UI
    unusable.
    """
    val = cfg.get("ui_scale", "auto")
    if isinstance(val, (int, float)):
        return max(0.8, min(2.5, float(val)))
    v = str(val).strip().lower()
    if v in ("", "auto"):
        return get_scale_factor()
    try:
        n = float(v.rstrip("%"))
        if n > 5:           # given as a percentage (e.g. 150) not a ratio
            n /= 100.0
        return max(0.8, min(2.5, n))
    except ValueError:
        return get_scale_factor()
