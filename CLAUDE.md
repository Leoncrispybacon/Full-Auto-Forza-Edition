# Full Auto Forza Edition (FAFE) — Project Summary

## What is this?
A Windows desktop automation tool for Forza Horizon 6. Built with Python + CustomTkinter. Uses an OpenCV template-matching pipeline (with optional OCR confirmation) to identify game screens and simulate keyboard/mouse input. Five functions: **Race Auto-Grind, Unlock Spin Wheel (22B mastery), Auto Buy, Auto Spin Wheel, Delete Used Cars.**

## File Structure
```
New APP/
├── forza_app.py          # Entry point (sets native thread-pool caps before heavy imports)
├── main_window.py        # Main UI window (CTk), all tabs, settings panel
├── setup_panel.py        # Collapsible Setup & Templates panel (per-template threshold sliders + capture)
├── capture.py            # Screenshot capture, region/node selection, template (re)scaling, geometry ROIs
├── gameio.py             # Window-aware capture + input (background mode) shared by every automation module
├── detector.py           # ScreenDetector — ROI-first multi-scale matching + optional OCR confirm
├── race.py               # Race Auto-Grind automation logic
├── mastery.py            # Unlock Spin Wheel — keyboard-driven mastery-tree unlock (grid + garage block)
├── delete_cars.py        # Delete Used Cars automation logic
├── buy.py                # Auto Buy automation logic (macro + optional menu-nav)
├── wheelspin.py          # Auto Spin Wheel (super/normal; detect-gated collect + duplicate menu)
├── grid_widget.py        # MasteryGridWidget (unlock-path grid) + MasteryCarBlockWidget (garage block selector)
├── report.py             # One-press bug-report bundle (F12): annotated detection screenshot + log → zip
├── overlay.py            # Opaque draggable status overlay over the game (frame-blanked so it's never self-detected)
├── log_widget.py         # Thread-safe log widget with colored warning support + bounded sections
├── theme.py              # Design tokens — fonts, spacing, semantic colors, theme presets
├── app_lang.py           # All UI strings in zh-tw / en
├── config.py             # Config load/save (self-completing), path helpers
├── updater.py            # GitHub release version check (check-only; opens releases page, never downloads)
├── version.py            # VERSION = "1.8.0"
├── build_app.bat         # PyInstaller build script
├── FAFE_icon.ico         # App icon (exe icon + runtime window/taskbar icon)
├── assets/               # Support panel images (support_jkopay.png, discord_logo.png, paypal_logo.png)
├── templates/            # Built-in template images per language (race/, buy/, wheelspin/ under built-in/ + custom/)
└── index.html            # GitHub Pages intro/tutorial page (zh-tw / en)
```

## Architecture

### UI (main_window.py)
- **Fluent sidebar layout**: col 0 sidebar (fixed 210px), col 1 main; status bar at the window bottom. The **sidebar** is a rounded bordered card with the FAFE wordmark, the function nav items (`_nav_buttons`, labels from `nav_*`), a spacer, then a bottom group — a compact 🐞/Discord row, **Settings**, and **Support Me**. Active nav = `surface_alt` fill + bright text + an accent left bar (`_set_nav_active`). Settings lives in the **bottom-left sidebar** (not a top-right gear).
- **One main view at a time (`_show_main`)**: the tab frames and the settings/support/report panels are all children of `_main_content`, shown one at a time. `_switch_tab(tab)` sets `_current_tab`/`_active_log`/`_active_setup_panel`, highlights the nav, updates the page title. Tabs stay clickable while a panel is open (clicking one exits the panel).
- Each tab: description label, count/range input, Start/Stop buttons, log widget. **Unlock Spin Wheel** and **Delete** use a `MasteryCarBlockWidget` (garage-block selector) instead of a plain count.
- **Theme presets** (Settings → Appearance, `theme_preset`): `"default"` and `"midnight_neon"`. Changing restarts the app (CTk can't restyle live), same as the language switch.
- **App icon**: `FAFE_icon.ico` is both the exe icon (PyInstaller `--icon`) and the runtime window icon, re-asserted via `iconbitmap` on a `self.after(300, …)` delay (CTk overrides it ~200ms after init). `_icon_path()` resolves in dev + frozen `--onedir`.
- **Fonts — locked per language** (`theme.init_fonts(lang, root)` + `theme.apply_font_family_to_tree(root)`): the UI font is pinned to a guaranteed-installed CJK-capable Windows face per language (**繁中 → `Microsoft JhengHei UI`**, **en → `Segoe UI`**), because Roboto/Segoe UI/Arial have no CJK glyphs and Windows font-linking can fall back to a decorative/brush font. Three font paths are covered: `theme.*_FONT` tokens, CTk's `CTkFont` family default, and hardcoded `('Arial', N)` tuples (rewritten tree-walk post-build). **Ordering**: `init_fonts` must run *after* `_apply_theme()` (which resets `CTkFont.family` to Roboto) and after the Tk root exists.
- **UI scale** (Settings → Appearance, `ui_scale`): `Auto` / `100%`–`250%`, drives `ctk.set_widget_scaling` + `set_window_scaling` from a single factor (`config.resolve_ui_scale`). `_apply_scaling()` runs before `super().__init__()`, marks the process DPI-aware, and calls `deactivate_automatic_dpi_awareness()` so a given % is consistent regardless of Windows display-scaling. Gotcha: CTk multiplies `CTkImage`/`CTkToplevel.geometry()` by this factor, so anything sized from raw screen pixels must divide by it.

### Window-aware capture + input (gameio.py) — background mode
- **Always-on, auto-adapting**: each run creates a `GameIO(cfg)`. If the game window is found by title, FAFE drives it **through that window** — capturing its **client area** (`grab_window` via `PrintWindow`/`PW_RENDERFULLCONTENT`, so it works windowed OR borderless **and even when another window covers it**) and sending input via **PostMessage** (so it works whether the game is **focused or not**). This is "background mode": you can run FAFE and use the PC for other things. A **keep-alive** re-asserts "active" (`set_window_active`, every 0.5s) so the game doesn't auto-pause while unfocused. If the window isn't found, GameIO falls back to whole-monitor capture + SendInput (legacy).
- Kill-switch `background_input=false` forces the legacy path. `background_capture` ("window"/"region") and `background_fake_focus` tune it. **Minimised** windows stop rendering frames, so the game must not be minimised (covered/unfocused is fine).
- **Letterbox/pillarbox crop**: detected once at start (`_detect_letterbox` → `capture.detect_content_rect`) and cached; the captured frame is cropped to the game content so detection matches a clean image. Click coords add the crop origin back.
- **Input**: `press`/`hold_press`/`release` (background → PostMessage; foreground → SendInput dual VK+scancode, or flagged scancode for held/gameplay keys), `click` (background → posted client-coord click; foreground → SetCursorPos + SendInput), `scroll`.

### Detection (detector.py)
- `ScreenDetector.detect(frame, key, template, threshold)` → `MatchResult`. Pixel template matching: grayscale `equalizeHist`, multi-scale, ROI-first. All current templates are text → `TEXT_TEMPLATES` covers all keys → the tight **3-scale gray-only** fast path (`detector_text_scales`, default `[0.95, 1.00, 1.05]`); non-text keys would use the 7-scale + Canny pipeline.
- **Single detection path** — the old Default/Custom mode toggle was removed (v1.8.0). One built-in template set, auto-scaled to resolution.
- **OCR is OFF by default (`detector_enable_ocr`, default `false`).** OCR (onnxruntime / RapidOCR) is CPU-heavy and was the main cause of in-game stutter, so detection is pixel-only by default. When enabled (Settings → System), OCR acts as a **confirmation** signal for text templates with `OCR_HINTS` — finding the hint text promotes a weak pixel match, because text content is what's invariant across hardware (GPU AA/HDR/font hinting all change pixels).
- **ROI-only matching (`detector_roi_only`, default `true`)** — the full-screen fallback is OFF by default. Every tracked element is fixed-position and covered by its ROI, so the full-screen matchTemplate (the most expensive op) buys nothing. Measured ~680ms → ~30ms per detection at 4K. Kill-switch `detector_roi_only=false` restores ROI-first + full-screen fallback (gated by `detector_full_gate_score` / `detector_full_sweep_every`).
- **ROI sources, in priority order**: (1) a **user-drawn custom ROI** (`set_template_roi`, from the template's saved `"roi"` field — the Setup panel's "Detection area" button); (2) a **geometry-derived ROI** (`_geom_roi`) when a template carries its capture box; (3) the hand-tuned `DEFAULT_ROIS`. See Capture for the geometry/anchor model.
- **Non-16:9 ROIs** (`_roi_for_frame`): menus anchor to a centred 16:9 box; in-game HUD (e.g. the `racing` timer) anchors to the screen edges. `_ROI_BOX_KEYS` (just `start_menu`) map into the centred box; others use a full-axis band. Toggle off via `detector_roi_aspect_fix=false`.
- **Soft threshold** = `max(self._min_thresh, threshold * 0.92)` — the slider is a target. `_min_thresh` is a **hard floor** (`detector_min_threshold`, default **0.70**; raised from 0.45 because 45–70% matches misfired on real hardware like the Ally X).
- **Stability filter**: N consecutive frames (default 2) above the soft threshold; `stable=False` bypasses it for single-shot click ops. `wait_for` calls `_reset_match_state(key)` at entry so each wait needs genuinely consecutive frames (history must not persist across loops or it fires early).
- `wait_for(...)` waits **indefinitely** until detected or stopped — intentional; F9 is the recovery path. After 3s without detection it fires a red `warn_cb` (with best `source`/`score`, and `OCR:'…'` when OCR ran) for diagnostics.
- **Native CPU caps**: `cv2.setNumThreads(2)`, RapidOCR `intra_op_num_threads=1`, and `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=2` + `OMP_WAIT_POLICY=PASSIVE` set in forza_app.py before native libs load — matchTemplate/OCR otherwise saturate all cores and stutter the game.
- **Debug snapshots** (`debug_detection`, default false; toggle in Settings → System): `_draw_debug` annotates the captured frame — **yellow** ROI box, **green/orange** best-match cross (matched/miss), **magenta** "click" marker — and writes `debug/<key>.png`. `render_report_image()` builds the F12 report screenshot from the last detections.

### Automation modules (race.py, mastery.py, buy.py, wheelspin.py, delete_cars.py)
- Each has `run(cfg, stop_event, log_cb, status_cb, …)`, runs in a daemon thread; `stop_event` signals shutdown.
- **CJK IME handling**: a Traditional Chinese IME in native mode can consume keystrokes (Space/Down/Enter are IME candidate keys) before the game reads them. `capture.force_english_ime()` (gated by `auto_english_ime`, default true) switches the game window to English **only if** a non-English layout is active (no-op otherwise). Key injection sends **both** VK + scancode so it works on VK-path and DirectInput/Raw-Input games.
- **UIPI / run-as-admin**: if the game runs **elevated** and FAFE doesn't, Windows silently drops FAFE's injected input (car won't move, clicks do nothing). The fix is **running FAFE as administrator**. We deliberately don't ship a UAC manifest (auto-elevation is an AV false-positive trigger).
- **Race (race.py)**: detects two screens, times the rest. Per loop: `wait_for(start_menu)` → Enter → wait `_PRE_W_WAIT` then **hold W** (re-asserted ~30ms via flagged scancode — the driving input path) → hold until `restart_menu` detected → release W (focus-aware: refocus the game first so a UI-Stop doesn't leave W stuck) + X → wait → Enter. `max_loops` caps races. Optional template-gated menu nav: main menu → EventLab → Start screen (entry), and results → main menu (exit) for a clean hand-off.
- **Unlock Spin Wheel (mastery.py)** — keyboard-driven, **no detection**, no templates. Walks a **contiguous block of cars top→bottom, column-major (NOT a snake)** — the block is chosen with the `MasteryCarBlockWidget` (first row / middle full columns / last row). Per car: navigate (WASD) → enter car → Ride This Car → cutscene wait → Upgrade & Tuning → Car Mastery → **unlock the mastery-tree nodes by walking the unlock-path grid with WASD+Enter** (the grid is `MasteryGridWidget`, `get_mastery_grid_file`) → back to My Cars → next car. No node-click capture; the only setup is the grid + the garage block. Step waits are fixed constants; `mastery_grid_unlock_wait` / `mastery_cutscene_wait` / `menu_tap_wait` are configurable.
- **Auto Buy (buy.py)**: per loop presses `['space','down','enter','enter','enter']` (`BUY_MACRO`, Space = 購買) on the target car's detail view; `max_loops` caps it. Optional template-gated menu nav (collection log → Discover Japan → Car Collection → Subaru brand → target car) lets it start & end on the main menu.
- **Auto Spin Wheel (wheelspin.py)**: spins **Super OR normal** Wheelspins (`wheelspin_type`). Clicks the tile to start; every later spin auto-continues. Per spin: best-effort **skip** the reveal → detect the **collect** prompt → Enter (a Super Wheelspin collects all 3 prizes at once; normal collects 1) → handle 0–3 **duplicate** menus (`wheelspin_dup_mode`: "garage" keeps, "sell" sells — sell is unattended, warned). Detection-gated throughout; `my_horizon_tab` (best-effort) lets it start from the main menu. Templates: `super_wheelspin`/`normal_wheelspin`, `wheelspin_skip` (best-effort), `wheelspin_collect`, `wheelspin_collect_final`, `wheelspin_duplicate` (captured on the solid-yellow "Car Already Owned" **header**, not the body).
- **Delete Used Cars (delete_cars.py)**: keyboard macro that deletes cars one by one (the game auto-selects the next after each). The count comes from the `MasteryCarBlockWidget` (garage-block range) and Start is gated behind a confirmation checkbox ("all cars between the first and last will be deleted").

### Capture (capture.py)
- `CaptureSession` (CAPS LOCK → fullscreen region selector) and `NodeSession` (click positions). Hooks are targeted (never `unhook_all`, to preserve F9).
- **Template rescaling**: `load_template` scales by **height only** (`scale = current_h / meta["screen_height"]`) — game UI is laid out relative to vertical resolution.
- **Single built-in set, auto-scaled**: built-in templates are authored once at `config.REFERENCE_RES` ("2160p") and downscaled at load time, so one set serves every resolution. The Setup panel resolution picker is **Built-in (auto-scaled) / Custom**.
- **Geometry-derived ROI**: templates carry their **capture box** (`save_template(..., box=(x,y,w,h))` → sidecar JSON). `detector.set_template_geometry` + `_geom_roi` derive an **anchor-aware ROI**, padded by `detector_geom_variance` (0.05). Two models: **menus** map the box through the **centred 16:9 content box** of both capture and live frame (`_content_box`), preserving the element's fraction within the content box so the pillarbox/letterbox offset is handled across aspect changes; **edge HUD** (`_GEOM_EDGE_KEYS`, e.g. `racing`) scale by height + anchor to the nearest edge. Kill-switch `detector_geometry_roi=false`.
- **Custom ROI ("Detection area" button)** saved via `save_roi` as fractions in the sidecar; `set_template_roi` applies it (highest priority). Resolution-adaptive (stored as fractions).
- **Node click rescaling** (`load_nodes`, `nodes_aspect_fix`): maps stored ratios through the centred 16:9 content box so 16:9-authored positions land correctly on ultrawide/tall screens.
- **Frame capture reuse**: `grab_frame` uses a thread-local `mss` instance (`threading.local`), reused and **rebuilt every 400 grabs** to flush native GDI/handle accumulation that otherwise made long runs deteriorate (black frames). One-time rebuild fallback on a non-`RuntimeError` exception.

### Config (config.py)
- JSON next to the exe. **Self-completing on load**: back-fills any keys missing from the user's `config.json` with `DEFAULTS` and writes them back once (so keys added in a new version appear in an existing user's file). Corrupt file is left as-is; missing file is created from `DEFAULTS`. `DEFAULTS` must list every user-facing key; the optional `detector_*` deep-tuning keys are intentionally not in `DEFAULTS`.
- Keys include: `lang`, `template_lang`, `theme_preset`, `ui_scale`, `monitor_index`, `toggle_key`/`capture_key`/`report_key`/`overlay_key`, `overlay_enabled`, `mute_game`, `auto_english_ime`, `background_input`/`background_capture`, `detector_enable_ocr` (default false), `debug_detection` (default false), all per-template `thresh_*`, and per-function timing (`race_check_interval`, `race_post_key_wait`, `mastery_cutscene_wait`, `mastery_grid_unlock_wait`, `menu_tap_wait`, `buy_post_key_wait`, `delete_post_key_wait`, `wheelspin_post_key_wait`).
- Optional detector tuning keys (code-default, not in `DEFAULTS`): `detector_roi_only` (default true), `detector_scales`, `detector_text_scales`, `detector_stable_frames`, `detector_ocr_cooldown`, `detector_min_threshold` (0.70), `detector_geometry_roi`, `detector_geom_variance`, `detector_roi_aspect_fix`, `detector_roi_aspect_tol`, `detector_full_gate_score`, `detector_full_sweep_every`, `template_prefer_reference`.

### Settings (Settings → opened from the bottom-left sidebar)
- **Appearance**: theme preset, app language, game-menu language (template set), UI scale, game overlay toggle.
- **System**: mute game while running, **OCR text detection** (off by default — lighter on CPU), **debug snapshots**.
- **Shortcuts**: Start/Stop (F9), Capture (CAPS LOCK), Report (F12), Overlay (F10) — all rebindable.
- **Per-function timing** sliders (Race / Unlock Spin Wheel / Buy / Delete / Wheelspin). Each setting has a `?` tooltip; all save instantly (theme/language restart the app).

### Game status overlay (overlay.py)
- A borderless **topmost, opaque** `tk.Toplevel` card: header (FAFE icon + a function-switcher dropdown), current status (green), last 5 active-log lines, and a footer hint showing the start/stop key. Toggle via Settings → Appearance, the **F10** hotkey, or the topbar ●/○ indicator (all route through `_set_overlay_enabled`).
- **Never self-detected — frame blanking** (`capture.set_overlay_mask`): the overlay is a dark text card that would pixel-match menu templates (and its text contains hint words OCR could read), so `grab_frame(mask_overlay=True)` blanks the overlay's own screen rect out of every detection frame. (`SetWindowDisplayAffinity` was rejected because it hides the window from the user on some handheld capture/composition paths.) Default position is the top-right corner, clear of detection ROIs; the user drags it elsewhere (position persists).
- **Opaque, draggable, focus-safe**: only `WS_EX_NOACTIVATE` (never steals focus from the game). No layered/transparent styles (they rendered the labels as a black box on the test setup). Works over borderless/windowed games only.

### Bug report (report.py)
- **One-press diagnostic bundle** (global hotkey `report_key`, default **F12**, rebindable). Writes `reports/FAFE_report_<ts>/` with an **annotated detection screenshot** (`detector.render_report_image()` — the debug overlay showing search regions, matches, and the last click; falls back to a plain screenshot) and **`log.txt`** (version + platform/CPU + full config dump + all tab logs), zips it, and opens the folder. A localized privacy notice is logged + written into log.txt (the bundle contains settings + basic system info). **No DxDiag** (removed — it was slow and no longer useful).
- The **🐞 Report a Bug** button opens an inline tutorial, not a capture — clicking a button would foreground FAFE and screenshot the wrong window; the real capture is the global F12 hotkey pressed while the game is focused.

### Update check (updater.py) — CHECK-ONLY, no download/install
- FAFE does **not** download or install updates. It does a read-only version check against the GitHub API; if a newer release exists, the UI shows a notice + a button that opens the releases page in the browser. (The old self-updater was the biggest AV false-positive trigger and is prohibited by Nexus Mods — removed.) Gated by `update_check` (default true); set false for a fully-offline build. HTTPS uses certifi's CA bundle.

### Log widget (log_widget.py)
- Thread-safe via queue. `log` / `log_warning` (red) / `log_section` (bounded loop sections — only the last `MAX_SECTIONS` (3) are kept so the log doesn't grow unbounded). Section headers must not contain embedded newlines.

## Key Design Decisions
- All UI strings go through `_at(key, lang, **kwargs)` in app_lang.py — never hardcode UI text.
- Sliders save on mouse release only; slider minimums are the lowest safe values.
- `keyboard.unhook_all()` is NEVER called — only targeted hook cleanup, to preserve F9.
- `wait_for` is intentionally infinite with no auto-retry — F9 is the recovery path.
- OCR is off by default; pixel matching is the primary signal (OCR confirms when enabled).

## GitHub
- Repo: https://github.com/Leoncrispybacon/Full-Auto-Forza-Edition
- Pages: https://leoncrispybacon.github.io/Full-Auto-Forza-Edition/
- Latest release: v1.8.0

## Build
Run `build_app.bat` — produces `FAFE_dist/` with `FAFE.exe`, `_internal/`, `config.json`. The release zip is the full `FAFE_dist/` contents. The build bundles `rapidocr_onnxruntime` (the ONNX models add ~50 MB) so OCR works if enabled, and `templates/` is copied next to the exe.

<!-- Full Auto + licensing/paywall design notes live in PAID_FUNCTION.md, which is
     gitignored and only on the private Full-auto branch (kept out of CLAUDE.md so
     CLAUDE.md is safe to merge to the public main). -->

