# ============================================================
#  config.py — Central configuration and path management
# ============================================================

import os
import mss
import sys
import json
import time
import ctypes
import threading

# ── Base path (works both frozen exe and dev; PyInstaller→sys.frozen, Nuitka→__compiled__) ──
if getattr(sys, 'frozen', False) or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Flat structure — config.py sits alongside app_web.py
    BASE_DIR = os.path.dirname(os.path.abspath(
        sys.argv[0] if '__file__' not in dir() else __file__))
    # If we're inside an app/ subfolder, go up one level
    if os.path.basename(BASE_DIR).lower() == 'app':
        BASE_DIR = os.path.dirname(BASE_DIR)

CONFIG_FILE       = os.path.join(BASE_DIR, "config.json")
# Whether a config file existed BEFORE this launch — captured at import, before
# load() can create one. Drives the web app's first-run language picker (a fresh
# install has no config, so we ask the language instead of silently defaulting).
HAD_CONFIG        = os.path.exists(CONFIG_FILE)
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


def get_delete_templates(res: str = REFERENCE_RES,
                         lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    # Delete is keyboard-driven; the only (optional) template is delete_confirm,
    # used to gate the final irreversible "confirm delete" keypress.
    path = os.path.join(_lang_dir(lang), "delete", res)
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


def get_relaunch_templates(res: str = REFERENCE_RES,
                           lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    """Templates used by the post-relaunch route from splash/intro screens back
    to the main menu. Surfaced under Race setup because the relaunch watchdog is
    triggered by race entry navigation."""
    path = os.path.join(_lang_dir(lang), "relaunch", res)
    os.makedirs(path, exist_ok=True)
    return path


def custom_dir(built_in_folder: str) -> str:
    """Sibling 'custom' folder for a 'built-in' template folder. User recaptures
    are written here (not into built-in) so an installer upgrade — which wipes &
    refreshes built-in — can't destroy them. capture.load_template prefers custom
    over built-in, so a local recapture overrides the shipped template."""
    parent = os.path.dirname(os.path.normpath(built_in_folder))
    path = os.path.join(parent, "custom")
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


def get_mastery_presets_file(lang: str = DEFAULT_TEMPLATE_LANG) -> str:
    """User-saved mastery-tree route presets for the standalone Mastery tab.

    Routes are logical 4x4 cell paths, not language-specific template assets, so
    they live once under templates/ instead of under templates/<lang>/.
    """
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    return os.path.join(TEMPLATES_DIR, "mastery_presets.json")


# Full Auto's mastery unlock paths are HARD-CODED in full_auto.py (its grind cars
# are fixed), so there's no per-car grid-file helper here anymore.


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
    for _mode in ("race", "mastery_full", "full_auto", "relaunch"):
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


# Config migration version. Bump when a DEFAULT value changes and existing
# users should pick up the new value. `_migrate()` applies each step once, and
# only to a setting still on the OLD default (so customizations are preserved).
# Stored in config.json as "config_schema"; deliberately NOT in DEFAULTS, so the
# missing-key back-fill can't stamp it current before _migrate() runs.
CONFIG_SCHEMA = 2


DEFAULTS = {
    "lang":              "en",
    # First-run language picker gate. DEFAULTS=True so existing users (whose
    # config.json predates this key) are back-filled True and never see the
    # picker. The SHIPPED config.json sets it false, so a fresh download shows
    # the picker once, then sets it True.
    "lang_chosen":       True,
    "theme":             "system",
    "toggle_key":        "f9",
    "pause_key":         "f8",
    "capture_key":       "caps lock",
    "report_key":        "f12",
    "overlay_key":       "f10",
    "monitor_index":     _get_primary_monitor_index(),
    # Detection debug: when true, every detection saves an annotated snapshot
    # (ROI searched + best-match cross + score/threshold/source/matched) to a
    # `debug/` folder next to the exe — one image per template key, overwritten
    # live. For diagnosing why a step mis-detected. Off for normal use.
    "debug_detection":   False,
    # Developer mode: reveals template recapture + detection tools in the Setup
    # panels (and the Capture shortcut). Off for normal users so they can't break
    # the built-in templates; toggle in Settings → Developer.
    "dev_mode":          False,
    # OCR confirmation during detection. Default ON because CPU-aware presets
    # now reduce OCR scale/rate on stutter-prone hybrid Intel CPUs, and many
    # displays/setups need OCR to confirm text templates reliably. The Settings
    # UI stays a simple ON/OFF switch.
    "detector_enable_ocr": True,
    # OCR runtime preset. "auto" = pick from the CPU (Balanced, or Low Impact on
    # stutter-prone hybrid Intel CPUs); "balanced"/"low_impact" force one. Exposed
    # under Settings -> Developer so a slow non-Intel PC can opt into Low Impact.
    "ocr_cpu_profile": "auto",
    # Recovery stays route-local: when a major detection-gated stage route fails
    # before its purpose is complete, retry that same route this many times.
    "recovery_route_retries": 1,
    # Stuck-loading recovery: only used by narrow watchdog paths that cannot be
    # recovered through menu anchors. Platform is user-selected in Settings;
    # "auto" is still accepted for older configs/tests.
    "game_relaunch_enabled": True,
    "game_platform": "steam",
    "game_launch_path_answered": False,
    "game_steam_uri": "steam://rungameid/2483190",
    "game_custom_launch": "",
    "gamepass_app_name": "Forza Horizon 6",
    "gamepass_fallback_appid": "Microsoft.ForteBaseGame_8wekyb3d8bbwe!Forzahorizon6",
    "game_relaunch_delay": 8.0,
    "game_launch_start_timeout": 180.0,
    "game_launch_continue_timeout": 120.0,
    "game_launch_home_timeout": 240.0,
    "game_launch_open_world_timeout": 45.0,
    "game_launch_main_menu_timeout": 45.0,
    # First-run style DLC question. `answered` is separate from `owned` so
    # "No" persists and the app does not keep asking on every launch.
    "car_pass_dlc_answered": False,
    "car_pass_dlc_owned": False,
    "thresh_launch_start_prompt": 0.70,
    "thresh_launch_continue":     0.70,
    # Game-menu language for templates: "auto" (follow app UI lang) / cht / en
    "template_lang":      "auto",
    # Race settings
    "race_threshold":    0.60,
    # Per-template thresholds. Race Auto detects start_menu + restart_menu
    # (racing/confirm are blind timing). Mastery is keyboard-driven — no
    # templates, so no mastery thresholds.
    "thresh_start_menu":           0.70,
    "thresh_restart_menu":         0.70,
    # Race menu-navigation templates (optional — used to auto-walk from the main
    # menu to the Start screen before the AFK loop; skipped if not captured).
    "thresh_creative_hub":         0.70,
    "thresh_eventlab":             0.70,
    "thresh_play_event":           0.70,
    "thresh_events_arrow":         0.70,
    "thresh_my_history":           0.70,
    "thresh_choose_race_type":     0.70,
    "thresh_car_select":           0.70,
    # Race exit: the recommended "What's Next" menu shown after Continue.
    "thresh_next_activity":        0.70,
    "race_check_interval":    0.5,
    "race_post_key_wait":     0.75,
    # Mastery is template-gated (the only path). The ride cutscene is handled by
    # detecting the post-cutscene screen (ride_cutscene_end), so there's no
    # cutscene timer any more; the other step waits stay FIXED in mastery.py.
    "mastery_start_loop":     1,
    # Grid node-unlock settle (after Enter, before the next node's move) for the
    # keyboard mastery-tree nav. Higher helps weaker hardware register the
    # unlock; default 1.25, Settings slider 1–2s.
    "mastery_grid_unlock_wait": 1.25,
    "thresh_ride_this_car":       0.70,
    "thresh_upgrade_tuning":      0.70,
    "thresh_car_mastery":         0.70,
    "thresh_mastery_tree":        0.70,
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
    # Full Auto grind type — what the chain farms each cycle:
    #   "wheelspin" → Subaru 22B (mastery wheelspin node); branch toggle applies.
    #   "money"     → Dodge Viper GTS ACR (mastery 150k-credit node); no spin.
    #   "mixed"     → alternate per cycle, starting money → wheelspin → money …
    # (branch_mode only affects "wheelspin" grind.)
    "full_auto_grind_type":   "wheelspin",
    # How many cars the chain buys, unlocks mastery on, and sells per cycle.
    # Which step the FIRST cycle starts at — "race" (full cycle) | "buy" (use
    # points already banked). Both flow through buy, where the per-cycle count is
    # read from tech points. Cycle 2 onward always runs the full loop from racing.
    "full_auto_start_from":   "race",
    # Auto-restart the game every N completed Full Auto cycles (0 = off). FH6
    # performance degrades over a long unattended run; relaunching between cycles
    # mitigates it. Reuses the game_relaunch path (needs game_relaunch_enabled).
    "full_auto_restart_cycles": 0,
    # Per-function Setup-tab run counts — persisted so they carry over a relaunch.
    # 0 = unlimited (run until stopped/detection caps it); full_auto_races = FA cycles.
    "full_auto_races":        2,
    "race_count":             0,
    "buy_count":              0,
    "wheelspin_count":        0,
    # Full Auto chain-only navigation templates (grouped by category in the
    # Setup panel). Currently the mastery positioning nav: main menu → My
    # Horizon → Return Home → CARS → My Cars → sort Recently Added → newest car.
    # my_horizon_tab is reused from the wheelspin set, so it isn't listed here.
    "thresh_return_home":     0.70,
    "thresh_cars_tab":        0.70,
    "thresh_recently_added":  0.70,
    # Sell step (chained-only): My Cars option clicked after riding the
    # non-target car (re-enters the grid before the re-sort + sell block).
    "thresh_my_cars":         0.70,
    # Sell step: the "My Cars" header (top-left) — confirms the grid finished
    # loading before pressing X (pressing X mid-load drops the sort menu).
    "thresh_my_cars_header":  0.70,
    # Sell exit: the home icon shown when leaving the home menu — confirms we
    # backed out to the open world so the final ESC opens the main menu.
    "thresh_anna":            0.70,
    # Sell re-select grind car: the "Select An Action" menu that opens after
    # clicking the car tile — gates the "Get In Car" Enter (was a blind press).
    "thresh_select_action":   0.70,
    # Sell re-select grind car: brand button (manufacturer jump) + car tile.
    "thresh_grind_brand":     0.70,
    "thresh_grind_car":       0.70,
    # Full Auto pre-flight checklist: one-time garage/car setup checks persist;
    # driving/map confirmations are per-session and reset each launch.
    "fa_check_neighbor_ok":   False,
    "fa_check_favorite_ok":   False,
    "fa_check_stock_paint_ok": False,
    "fa_check_collection_unlock_ok": False,
    # Buy / Delete settings. 0.75 (not 0.5) because these run keys back-to-back
    # (Buy macro; Delete's Enter/Down×N/Enter; sell Down×2/Enter) — a 0.5s gap was
    # marginal and an FPS dip during a consecutive run dropped a key. 0.75 adds the
    # margin. Gated single-presses elsewhere pass their own (often 0) post-wait.
    "buy_post_key_wait":      0.75,
    "delete_post_key_wait":   0.75,
    # Buy menu-navigation (optional — start/end the buy run on the main menu;
    # skipped if these templates aren't captured).
    "thresh_collection_log":      0.70,
    "thresh_discover_japan":      0.70,
    "thresh_car_collection":      0.70,
    "thresh_subaru":              0.70,
    "thresh_buy_target_car":      0.70,
    # Buy gating anchors (optional — if both captured, each purchase is confirmed
    # by the "Buy Car" popup and a dropped key is retried; absent → blind macro).
    "thresh_buy_confirm":         0.70,
    "thresh_buy_detail_22b":      0.70,
    "thresh_buy_detail_gts_acr":  0.70,
    "thresh_buy_detail_mad_mike": 0.70,
    # Auto Spin Wheel settings. Duplicate cars are SOLD by default (unattended);
    # two independent keep-exceptions: keep_fe and keep_above_price (below).
    "thresh_wheelspin_duplicate": 0.70,
    "thresh_super_wheelspin":     0.70,
    "thresh_normal_wheelspin":    0.70,
    "thresh_my_horizon_tab":      0.70,
    "thresh_wheelspin_skip":      0.70,
    "thresh_wheelspin_collect":   0.70,
    "thresh_wheelspin_collect_final": 0.70,
    "wheelspin_post_key_wait":   0.75,  # see buy/delete note — used by the sell Down×2/Enter run
    # Keep Forza Edition (FE) duplicates (name ends in "FE") instead of selling.
    # OCR-read from the duplicate modal; errs toward keep.
    "wheelspin_keep_fe":         True,
    # Keep a duplicate when its read sell price >= this many credits (0 = off →
    # sell regardless of price). OCR-read; an unreadable price errs toward keep.
    "wheelspin_keep_above_price": 0,
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
    "theme_preset":           "default",
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
    # Mute ONLY the game's audio while an automation run is active (per-app;
    # leaves other apps' sound alone), and unmute when it stops. Settings toggle.
    "mute_game":              False,
    "overlay_enabled":        False,
    # Cutscene skip mod integration: whether the mod is installed and where.
    "cutscene_skip_installed": False,
    "cutscene_skip_game_dir": "",
    # Read-only version check on startup (no download — opens the releases page
    # if a newer version exists). Set false for a fully offline build that makes
    # zero network requests (e.g. to satisfy Nexus's no-internet policy).
    "update_check":           True,
    # One-click auto-update: download the release installer and run it silently.
    # Packaged (sys.frozen) builds only. Disable for Nexus/offline builds.
    "auto_update":            True,
}


def load() -> dict:
    if os.path.exists(CONFIG_FILE):
        # Retry a few times before giving up: a read can briefly fail if it lands
        # mid-write from another thread/window (the overlay saves its position
        # while the main window saves settings). Falling straight back to DEFAULTS
        # here is dangerous — callers do `save({**load(), key: val})`, so a
        # defaulted load would PERSIST defaults and reset e.g. the language. Atomic
        # writes (see save) make a partial read unlikely; this is the safety net.
        data = None
        for _attempt in range(4):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                break
            except Exception:
                time.sleep(0.04)
        if data is None:
            # Genuinely unreadable — fall back to defaults but DON'T overwrite the
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
        # Version-gated value migrations: when a DEFAULT changes between releases,
        # update an existing user's value too — but ONLY if they're still on the
        # OLD default (an untouched setting), so intentional customizations are
        # kept. config_schema records the last step applied; absent = pre-schema.
        schema = data.get("config_schema", 0)
        if schema < 1:
            # 1.8.x consecutive-key drop fix: the macro post-key gaps were
            # marginal at 0.5 and an FPS dip dropped a key — raise to 0.75.
            for _k in ("buy_post_key_wait", "delete_post_key_wait",
                       "wheelspin_post_key_wait"):
                if abs(float(data.get(_k, 0.75)) - 0.5) < 1e-6:
                    data[_k] = 0.75
                    added = True
        if schema < 2:
            if "recovery_test_point" in data:
                data.pop("recovery_test_point", None)
                added = True
        if schema < CONFIG_SCHEMA:
            data["config_schema"] = CONFIG_SCHEMA
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
    # Stamp it current so the one-time migrations don't re-touch a fresh file.
    data = dict(DEFAULTS)
    data["config_schema"] = CONFIG_SCHEMA
    save(data)
    return data


def save(data: dict) -> bool:
    """Write config.json ATOMICALLY (temp file + os.replace). Returns True on
    success, False if it couldn't be written.

    Atomic matters here: the overlay window writes config on its own thread
    (position) while the main window writes settings — a plain in-place write can
    be READ half-finished, making load() hit a JSON error and fall back to
    DEFAULTS (lang='en'); the next `save({**load(), ...})` would then persist that
    default and silently reset the user's language. With temp+replace, a reader
    always sees either the complete old file or the complete new one."""
    # UNIQUE temp name per writer (pid+thread) so two concurrent saves (overlay
    # thread + main window) don't fight over the same temp file → WinError 32.
    tmp = "%s.%d.%d.tmp" % (CONFIG_FILE, os.getpid(), threading.get_ident())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Retry the rename: a concurrent reader/replacer can briefly lock the
        # target on Windows. The file content is always complete, so worst case
        # is last-writer-wins — never a partial/defaulted write.
        for _attempt in range(6):
            try:
                os.replace(tmp, CONFIG_FILE)   # atomic on Windows (same volume)
                return True
            except Exception:
                time.sleep(0.03)
        raise OSError("config.json replace kept failing (locked)")
    except Exception as e:
        print(f"[config] Failed to save: {e}")
        try:
            os.remove(tmp)
        except Exception:
            pass
        return False


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
    """Resolve the saved `ui_scale` setting to a numeric scaling factor.

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
