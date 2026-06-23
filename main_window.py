# ============================================================
#  ui/main_window.py — Main application window
# ============================================================

import customtkinter as ctk
import threading
import queue
import json
import os
import sys

import config
import theme
from app_lang import t as _at
from config import (load, save, resolve_template_lang,
                    get_race_templates, get_mastery_templates,
                    get_wheelspin_templates, get_buy_templates,
                    get_full_auto_templates,
                    get_mastery_grid_file)
from grid_widget import MasteryGridWidget, MasteryCarBlockWidget
from log_widget import LogWidget
from setup_panel import SetupPanel
from updater import check_async, RELEASES_PAGE
from version import VERSION


# ── Race template definitions ─────────────────────────────────
# Template label keys looked up via app_lang at runtime
# Full Auto is a WIP (race+buy+mastery wired; sell/wheelspin-branch are TODO).
# Shown again while resuming the chain work so the tab can be used to capture the
# chain-only nav templates and test. Flip to False to hide the sidebar nav entry
# for a release; the tab frame is still built either way (handlers stay valid).
SHOW_FULL_AUTO = True

# Show the Setup & Templates panel on Race / Buy / Auto Spin Wheel. These ship
# pre-captured templates, but the panel stays visible so users can switch
# resolution or recapture. Set False to hide it (templates still work via the
# bundled set). Mastery always shows its panel — it needs node positions.
SHOW_SETUP_PANELS = True

# Race Auto detects two screens: the Start Race screen (start_menu) and the
# race-END screen (restart_menu). racing/confirm are blind timing, so only
# these two need capturing.
RACE_TEMPLATE_KEYS = [
    ("start_menu",       "race_tpl_start_menu"),
    ("restart_menu",     "race_tpl_restart_menu"),
    # Menu-navigation templates: let the script walk main menu → CREATIVE HUB →
    # EventLab → Play Event → MY HISTORY → Solo → car → Start screen before the
    # AFK loop. Best-effort: if these aren't captured, race just waits for the
    # Start screen (today's behavior). This is the bridge for chaining other
    # functions (sell/spin) into racing.
    ("creative_hub",     "race_tpl_creative_hub"),
    ("eventlab",         "race_tpl_eventlab"),
    ("play_event",       "race_tpl_play_event"),
    ("events_arrow",     "race_tpl_events_arrow"),
    ("my_history",       "race_tpl_my_history"),
    ("choose_race_type", "race_tpl_choose_race_type"),
    ("car_select",       "race_tpl_car_select"),
    # Race exit: the recommended "What's Next" menu shown after pressing
    # Continue at the results screen — gates the ESC back to the main menu so
    # the run ENDS on the main menu (the chaining hand-off point).
    ("next_activity",    "race_tpl_next_activity"),
]
# Auto Spin Wheel: the Super Wheelspin tile (detected + clicked to start each
# run from the My Horizon menu) and the duplicate-reward menu (detect-only).
SPIN_TEMPLATE_KEYS = [
    # My Horizon top-nav tab: lets the run START from the main menu (detect +
    # click it → My Horizon menu → Super Wheelspin tile). Best-effort — if it's
    # not captured, wheelspin assumes you're already on the My Horizon menu.
    ("my_horizon_tab",      "spin_tpl_my_horizon"),
    ("super_wheelspin",     "spin_tpl_super"),
    ("normal_wheelspin",    "spin_tpl_normal"),
    ("wheelspin_skip",      "spin_tpl_skip"),
    ("wheelspin_collect",   "spin_tpl_collect"),
    ("wheelspin_collect_final", "spin_tpl_collect_final"),
    ("wheelspin_duplicate", "spin_tpl_duplicate"),
]
# NOTE: wheelspin_skip is a BEST-EFFORT fast-forward — wheelspin.py loads it only
# if present and falls back to waiting for the collect prompt when it's missing
# or the prompt is missed, so a missing capture never breaks a run.
# Auto Buy: optional menu-navigation templates — let the run START and END on
# the main menu (main menu → Car Collection → target car; Esc chain back). All
# best-effort: if not captured, buy just runs the macro where you are.
BUY_TEMPLATE_KEYS = [
    ("collection_log",  "buy_tpl_collection_log"),
    ("discover_japan",  "buy_tpl_discover_japan"),
    ("car_collection",  "buy_tpl_car_collection"),
    ("subaru",          "buy_tpl_subaru"),
    ("buy_target_car",  "buy_tpl_target_car"),
    # Purchase-confirmation gating (optional): capture BOTH to switch from the
    # blind macro to a confirmed/retrying loop. buy_confirm = the solid "Buy Car"
    # popup header; buy_detail = a stable car-detail-view element (price / Buy).
    ("buy_confirm",     "buy_tpl_confirm"),
    ("buy_detail",      "buy_tpl_detail"),
]
# Mastery is keyboard-driven (no detection), so it has no template list — the
# Setup panel shows node capture only.

# Full Auto chain-only templates, grouped by category (section_label_key,
# [(key, label_key), ...]). Full Auto keeps its OWN copy of every template it
# uses — even ones also used elsewhere (my_horizon_tab) — so the set is self-
# contained and managed entirely in the Full Auto tab, separate from other
# functions' folders.
FULL_AUTO_TEMPLATE_KEYS = [
    ("fa_cat_mastery", [
        ("my_horizon_tab", "spin_tpl_my_horizon"),
        ("return_home",    "fa_tpl_return_home"),
        ("cars_tab",       "fa_tpl_cars_tab"),
        ("recently_added", "fa_tpl_recently_added"),
    ]),
    # Sell reuses recently_added from the mastery set above. cars_tab_sell is
    # sell-specific (the CARS tab is ACTIVE/highlighted on the sell exit, a
    # different look than the inactive cars_tab captured in the mastery nav).
    ("fa_cat_sell", [
        ("grind_brand",     "fa_tpl_grind_brand"),
        ("grind_car",       "fa_tpl_grind_car"),
        ("select_action",   "fa_tpl_select_action"),
        ("my_cars",         "fa_tpl_my_cars"),
        ("my_cars_header",  "fa_tpl_my_cars_header"),
        ("cars_tab_sell",   "fa_tpl_cars_tab_sell"),
        ("anna",            "fa_tpl_anna"),
    ]),
    # Auto-count mode: read available tech points from the MAIN-MENU CARS tab
    # (車輛, top nav — distinct from the home-menu CARS tab in the mastery set).
    ("fa_cat_points", [
        ("cars_top_tab",   "fa_tpl_cars_top_tab"),
        ("story_top_tab",  "fa_tpl_story_top_tab"),
        ("tech_points",    "fa_tpl_tech_points"),
    ]),
    # Money grind (Dodge Viper GTS ACR). dodge = the brand tile in the brand list
    # after Backspace (OCR-located primary, pixel fallback — like Subaru). gts_acr
    # = the black car tile, captured AFTER the one-notch scroll (NOT the FE).
    ("fa_cat_money", [
        ("dodge",          "fa_tpl_dodge"),
        ("gts_acr",        "fa_tpl_gts_acr"),
    ]),
]




class Tooltip:
    """Click-based info popup — no hover issues."""
    def __init__(self, widget, text: str):
        self._widget = widget
        self._text   = text
        self._win    = None
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", self._toggle)

    def _toggle(self, event=None):
        if self._win and self._win.winfo_exists():
            self._win.destroy()
            self._win = None
            return
        x = self._widget.winfo_rootx()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tw = ctk.CTkToplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        ctk.CTkLabel(
            tw, text=self._text,
            justify="left",
            fg_color=("gray90", "gray20"),
            corner_radius=6,
            font=(theme.UI_FAMILY, 11),
            padx=10, pady=8,
        ).pack()
        # Click anywhere to close
        tw.bind("<Button-1>", lambda e: (tw.destroy(), setattr(self, '_win', None)))
        # Also close if focus lost
        tw.bind("<FocusOut>", lambda e: (tw.destroy(), setattr(self, '_win', None)))

    def update_text(self, text: str):
        self._text = text


class MainWindow(ctk.CTk):

    def __init__(self):
        import config as _cfgmod
        _had_config       = os.path.exists(_cfgmod.CONFIG_FILE)
        self._cfg         = load()
        # First run = either no config existed yet, OR the config hasn't recorded
        # a language choice (the shipped config.json sets lang_chosen=false).
        # Either one shows the first-launch picker. Existing users (config
        # present AND lang_chosen back-filled True) never see it. Detected before
        # any UI is built so the UI comes up in the chosen language (no restart).
        self._first_run   = (not _had_config) or (not self._cfg.get('lang_chosen', True))
        # Apply UI scaling BEFORE the Tk root is created so geometry + widgets
        # come up at the right size. Scales the whole UI (widgets + fonts) for
        # high-res displays where the app would otherwise be tiny.
        self._apply_scaling()
        super().__init__()
        self._lang        = self._cfg.get('lang', 'en')
        self._tpl_lang    = resolve_template_lang(self._cfg)  # game-menu lang
        self._restarting   = False
        self._toggle_key   = self._cfg.get('toggle_key', 'f9')
        self._capture_key  = self._cfg.get('capture_key', 'caps lock')
        self._binding_key  = None   # which key is being rebound
        self._stop_event  = threading.Event()
        self._auto_thread = None
        self._in_settings = False
        self._in_support  = False

        self._apply_theme()
        # First-launch language picker — runs before the UI is built so the UI
        # comes up in the chosen language (no restart). We do NOT withdraw the
        # root here: building the UI on a withdrawn window and then deiconify()ing
        # made CTk paint a blank/white window (its canvas isn't drawn while
        # hidden). The root stays visible (empty) behind the modal picker, then
        # _build_ui fills it. init_fonts('zh-tw') first so the picker's CJK option
        # label (繁體中文) renders in a real CJK font.
        if self._first_run:
            self._setup_window()   # size/title the (empty) root behind the modal
            theme.init_fonts('zh-tw', root=self)
            self.update_idletasks()
            picked = self._ask_first_run_language()
            self._lang = picked
            self._cfg['lang'] = picked
            self._cfg['lang_chosen'] = True
            self._tpl_lang = resolve_template_lang(self._cfg)
            save(self._cfg)
        # Lock the UI font family to a guaranteed-installed Windows face for
        # this language (繁中 → JhengHei, English → Segoe UI). MUST run
        # AFTER _apply_theme(): set_default_color_theme() reloads the theme JSON
        # and would reset CTk's default font family back to Roboto (no CJK
        # glyphs), clobbering the override and leaving font=None widgets (e.g.
        # the tab buttons) rendering in a fallback/brush font. Runs before
        # _build_ui so widgets are born with the right family; the post-build
        # _apply_ui_fonts() walk then also fixes widgets with hardcoded
        # ('Arial'/'Segoe UI', N) font tuples.
        theme.init_fonts(self._lang, root=self)
        # Resolve the active theme tokens now that fonts are locked, so
        # self._t("font_*") returns the CJK-correct family. self._t(key) is the
        # single lookup used in place of hardcoded colors/corners across the UI.
        self._theme = theme.get_theme(self._cfg.get("theme_preset", "default"))
        self._setup_window()
        self._build_ui()
        self._set_window_icon()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Start example window queue poller
        self._example_win = None
        self._poll_example_queue()
        # Register global toggle hotkey at startup. Wrapped like the report/
        # overlay hotkeys below: on devices that restrict global keyboard hooks
        # (some handhelds / locked-down Windows), add_hotkey can raise — and an
        # UNGUARDED failure here aborted the rest of __init__, so the overlay
        # (after 1200ms) and the update check (after 2000ms) scheduled below
        # never ran. Hotkeys are best-effort; the on-screen Start/Stop buttons
        # still work without them.
        try:
            import keyboard as _kb
        except Exception:
            _kb = None
        try:
            if _kb is not None:
                _kb.add_hotkey(self._toggle_key, self._toggle_auto)
        except Exception:
            pass
        # Register global bug-report hotkey (default F12)
        self._report_key = self._cfg.get('report_key', 'f12')
        self._report_in_progress = False
        try:
            _kb.add_hotkey(self._report_key, self._trigger_report)
        except Exception:
            pass

        # Game status overlay + its toggle hotkey (default F10)
        self._overlay = None
        self._overlay_pos = None
        self._overlay_key = self._cfg.get('overlay_key', 'f10')
        try:
            _kb.add_hotkey(self._overlay_key, self._toggle_overlay)
        except Exception:
            pass
        self.after(1200, self._refresh_overlay)

        # Check for updates in background (silent if up to date or offline)
        self.after(2000, self._check_for_updates)

        self._diag_init()

    # ── Update check ──────────────────────────────────────────

    def _check_for_updates(self):
        # The check is a read-only version ping (no download). It can be turned
        # off entirely for a fully offline / Nexus-safe build via update_check.
        if not self._cfg.get('update_check', True):
            return
        def _on_found(tag, url):
            self.after(0, lambda: self._show_update_dialog(tag, url))
        def _on_status(msg):
            # Log the outcome so a silent/failed check is diagnosable from a bug
            # report (network/SSL/rate-limit/up-to-date all surface here).
            self.after(0, lambda: self._log(f"[Updater] {msg}"))
            self._diag(f"[Updater] {msg}")   # also to the persistent file
        check_async(_on_found, on_status=_on_status)

        # Refresh the Full Auto license in the background at launch: re-validates
        # the stored key online (if any), resetting the offline-grace timer and
        # catching a revoked/expired key. Best-effort — failures leave the cache
        # alone so the grace window still applies offline.
        def _license_refresh():
            try:
                import license_client
                if license_client.status().get("state") != "unlicensed":
                    license_client.validate()
            except Exception:
                pass
        threading.Thread(target=_license_refresh, daemon=True).start()

    def _show_update_dialog(self, tag: str, url: str):
        lang = self._lang
        dialog = ctk.CTkToplevel(self)
        dialog.title(_at("update_title", lang))
        dialog.geometry("420x220")
        dialog.resizable(False, False)
        dialog.grab_set()
        # Force it to the front + focus. On some setups (e.g. a handheld's
        # full-screen shell) a plain Toplevel can open behind the main window
        # and look like "the updater never popped up".
        try:
            dialog.lift()
            dialog.attributes("-topmost", True)
            dialog.after(100, lambda: dialog.attributes("-topmost", False))
            dialog.focus_force()
        except Exception:
            pass

        ctk.CTkLabel(
            dialog,
            text=_at("update_available", lang, tag=tag),
            font=("Arial", 14, "bold")
        ).pack(pady=(28, 6))

        ctk.CTkLabel(
            dialog,
            text=_at("update_prompt", lang),
            font=("Arial", 12),
            text_color=self._t("text_muted")
        ).pack(pady=(0, 20))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def _open_page():
            # Hand the download page to the default browser. The app itself does
            # NOT download/install anything (Nexus-compliant + avoids the AV
            # false-positives that the old self-updater caused).
            try:
                import webbrowser
                webbrowser.open(url or RELEASES_PAGE)
            except Exception:
                pass
            dialog.destroy()

        yes_btn = ctk.CTkButton(
            btn_row,
            text=_at("update_yes", lang),
            command=_open_page,
            width=160
        )
        yes_btn.pack(side="left", padx=8)

        no_btn = ctk.CTkButton(
            btn_row,
            text=_at("update_no", lang),
            command=dialog.destroy,
            fg_color="transparent",
            border_width=1,
            width=100
        )
        no_btn.pack(side="left", padx=8)
        theme.apply_font_family_to_tree(dialog)

    # ── Window setup ──────────────────────────────────────────

    def _apply_scaling(self):
        """Scale the whole UI by the resolved ui_scale factor.

        We drive scaling ourselves (resolution- or user-chosen) rather than
        relying on CustomTkinter's automatic per-monitor DPI scaling, so the
        size is predictable across machines and the percentages mean the same
        thing regardless of the user's Windows display-scaling setting. The
        process is still marked DPI-aware so text stays crisp (no bitmap
        stretching). Must run before the Tk root exists.
        """
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
        try:
            ctk.deactivate_automatic_dpi_awareness()
        except Exception:
            pass
        self._ui_scale = config.resolve_ui_scale(self._cfg)
        ctk.set_widget_scaling(self._ui_scale)
        ctk.set_window_scaling(self._ui_scale)

    def _apply_theme(self):
        theme_mode = self._cfg.get("theme", "system")
        preset = self._cfg.get("theme_preset", "default")
        if preset != "default":
            # Theme presets are dark-only; force dark (the light/dark switch was
            # replaced by the preset picker).
            ctk.set_appearance_mode("dark")
        elif theme_mode == "system":
            ctk.set_appearance_mode("system")
        else:
            ctk.set_appearance_mode(theme_mode)
        ctk.set_default_color_theme("blue")
        # Push the preset's colors into CTk's ThemeManager AFTER
        # set_default_color_theme() (which reloads the JSON and would otherwise
        # wipe them) — same ordering rule as init_fonts(). "default" is a no-op.
        theme.apply_preset(preset)

    def _t(self, key):
        """Look up a theme design token (color / corner radius / font) for the
        active preset. Use this instead of hardcoding colors/corners."""
        return self._theme[key]

    def _setup_window(self):
        self.title(f"Full Auto Forza Edition v{VERSION}")
        self.geometry("900x650")
        # Min height fits the full sidebar (5 nav items + the 4-button bottom
        # group) with margin, so the bottom group never clips when shortened.
        self.minsize(700, 560)
        self.resizable(True, True)

    def _icon_path(self):
        """Locate FAFE_icon.ico in dev and frozen (--onedir) layouts."""
        name = "FAFE_icon.ico"
        candidates = []
        if (getattr(sys, "frozen", False) or "__compiled__" in globals()):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(os.path.join(meipass, name))  # _internal
            candidates.append(os.path.join(os.path.dirname(sys.executable), name))
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), name))
        return next((p for p in candidates if os.path.exists(p)), None)

    def _set_window_icon(self):
        """Set the title-bar / taskbar icon to match the exe icon.

        The PyInstaller --icon flag only sets the *exe* icon; the running
        window's icon is Tk's default unless we set it. CustomTkinter also
        applies its own default icon shortly after init, so we re-assert ours
        on a short delay to make it stick.
        """
        path = self._icon_path()
        if not path:
            return

        def _apply():
            try:
                self.iconbitmap(path)
            except Exception:
                pass

        _apply()
        self.after(300, _apply)

    # ── UI construction ───────────────────────────────────────

    def _build_ui(self):
        # Status bar pinned to the very bottom (full width, under everything).
        self._status_var = ctk.StringVar(value=_at("status_ready", self._lang))
        status_bar = ctk.CTkLabel(
            self, textvariable=self._status_var,
            anchor="w", font=theme.HINT_FONT,
            fg_color=self._t("surface_alt"),
            text_color=self._t("text_muted"),
            corner_radius=0)
        status_bar.pack(side="bottom", fill="x")
        status_bar.configure(height=26)

        # Body: left sidebar (fixed width) + main column (fills remaining).
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="top", fill="both", expand=True)
        body.grid_columnconfigure(0, weight=0)   # sidebar (fixed)
        body.grid_columnconfigure(1, weight=1)   # main (grows)
        body.grid_rowconfigure(0, weight=1)

        self._sidebar = self._build_sidebar(body)
        self._sidebar.grid(row=0, column=0, sticky="ns", padx=(10, 5), pady=10)

        # Main column is a themed surface panel (not the near-black window bg),
        # with a small gutter (window bg) separating it from the sidebar.
        self._main = ctk.CTkFrame(body, fg_color=self._t("surface"),
                                  corner_radius=self._t("corner"))
        self._main.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self._build_header(self._main)

        # Content area — tab frames AND the inline panels (settings / support /
        # report help) all live here, shown one at a time via _show_main().
        self._main_content = ctk.CTkFrame(self._main, fg_color="transparent")
        self._main_content.pack(side="top", fill="both", expand=True)

        # Tab content frames (parented to the content area).
        self._full_auto_frame = self._build_full_auto_tab()
        self._full_auto_locked_frame = self._build_full_auto_locked_tab()
        self._race_frame    = self._build_race_tab()
        self._mastery_frame = self._build_mastery_tab()
        self._buy_frame     = self._build_buy_tab()
        self._delete_frame  = self._build_delete_tab()
        self._spin_frame    = self._build_spin_tab()

        self._cur_main    = None
        self._current_tab = None
        self._switch_tab("race")

        self._apply_ui_fonts()

    def _apply_ui_fonts(self):
        """Force every widget's font family to the locked UI family. Many
        widgets use hardcoded ('Arial'/'Segoe UI', N) tuples that lack CJK
        glyphs, so on a Chinese UI they'd render in a fallback/brush font;
        this normalises the whole tree (incl. on-demand panels) in one pass.
        Idempotent — safe to call after every build."""
        try:
            theme.apply_font_family_to_tree(self)
        except Exception:
            pass

    def _build_sidebar(self, parent):
        """Left vertical nav as a rounded bordered card: FAFE wordmark + accent
        underline, the 4 function nav items (active = subtle fill + accent left
        bar), then a bottom group (Report/Discord compact, Settings, Support)."""
        sb = ctk.CTkFrame(parent, fg_color=self._t("sidebar_bg"),
                          corner_radius=self._t("corner"),
                          border_width=1, border_color=self._t("border"),
                          width=210)
        sb.pack_propagate(False)   # honour the fixed width

        # Wordmark + accent underline
        wm = ctk.CTkFrame(sb, fg_color="transparent")
        wm.pack(anchor="w", fill="x", padx=18, pady=(18, 14))
        ctk.CTkLabel(wm, text=_at("app_title", self._lang),
                     font=theme.TITLE_FONT,
                     text_color=self._t("text")).pack(anchor="w")
        ul = ctk.CTkFrame(wm, height=3, width=70, corner_radius=2,
                          fg_color=self._t("accent"))
        ul.pack(anchor="w", pady=(3, 0))
        ul.pack_propagate(False)

        # Function nav items — full-width buttons; the active one gets a subtle
        # fill + an accent left bar. The bar is an OVERLAY (place), so active and
        # inactive items sit at the exact same position (no off-centre shift).
        self._nav_buttons = {}
        self._nav_bars = {}
        _nav_keys = (("full_auto",) if SHOW_FULL_AUTO else ()) + \
                    ("race", "mastery", "buy", "delete", "spin")
        for key in _nav_keys:
            item = ctk.CTkFrame(sb, fg_color="transparent", height=42)
            item.pack(fill="x", padx=10, pady=2)
            item.pack_propagate(False)
            btn = ctk.CTkButton(
                item, text=_at(f"nav_{key}", self._lang),
                anchor="w", corner_radius=self._t("corner_sm"),
                fg_color="transparent", text_color=self._t("text_muted"),
                hover_color=self._t("surface_alt"), font=theme.BODY_FONT,
                command=lambda k=key: self._switch_tab(k))
            btn.place(x=0, y=0, relwidth=1, relheight=1)
            # Inset the label so the first glyph clears the rounded corner and
            # the accent left-bar (logical x 4–8); without this the leading
            # character is clipped (default corner_sm=4). Also nudge the CJK
            # line-box up on high-DPI displays where it rounds low (0 at 1×).
            S = getattr(self, "_ui_scale", 1.0) or 1.0
            _padx = round(10 * S)
            _nudge = max(0, round((S - 1.0) * 6))
            try:
                btn.update_idletasks()
                btn._text_label.grid_configure(padx=(_padx, 0), pady=(0, _nudge))
            except Exception:
                pass
            bar = ctk.CTkFrame(item, width=4, corner_radius=2,
                               fg_color="transparent")
            bar.place(x=4, rely=0.5, anchor="w", relheight=0.6)
            self._nav_buttons[key] = btn
            self._nav_bars[key] = bar

        # No spacer needed: the bottom group is packed side="bottom" (below),
        # the nav items side="top", so the middle gap is automatic and the
        # bottom group stays pinned to the bottom edge at any window height.

        # Bottom group: compact filled buttons sharing the accent border,
        # stacked Settings → Report a Bug → Discord → Support Me.
        # NOTE: compound is always "left" — compound="center" hides the label
        # text in CustomTkinter (it's meant for image-over-text), which left the
        # text-only buttons looking empty.
        # Left-aligned (matching the nav above) with a uniform leading inset,
        # so all four labels start at the same x. Each button carries a leading
        # icon (gear/bug/Discord-logo/cup) so the words line up in a column.
        def _bottom_btn(text, cmd, fill, txt, hover, image=None, pady=2):
            S = getattr(self, "_ui_scale", 1.0) or 1.0
            b = ctk.CTkButton(
                sb, text=text, image=image, compound="left", anchor="w",
                height=30, corner_radius=self._t("corner_sm"),
                fg_color=fill, text_color=txt, hover_color=hover,
                border_width=2, border_color=self._t("accent"),
                font=theme.LABEL_FONT, command=cmd)
            # side="bottom": anchor the group to the sidebar's bottom edge so it
            # can't be pushed off-screen by the nav list above (the 5th nav item
            # used to shove the flush group past the frame, clipping Support Me).
            # Packed bottom-up, so callers are issued in reverse visual order.
            b.pack(side="bottom", fill="x", padx=12, pady=pady)
            b.update_idletasks()
            _lead = round(14 * S)
            _ny = max(0, round((S - 1.0) * 3))
            try:
                # Inset the leading element (icon if present, else text) so the
                # content starts at the same x on every button.
                if image is not None:
                    b._image_label.grid_configure(padx=(_lead, 0))
                    if _ny:
                        b._text_label.grid_configure(pady=(0, _ny))
                else:
                    b._text_label.grid_configure(padx=(_lead, 0), pady=(0, _ny))
            except Exception:
                pass
            return b

        # Packed side="bottom", so issue them in REVERSE visual order:
        # Support (bottom-most) → Discord → Report → Settings (top of group).
        discord_img = self._load_ctk_image("assets", "discord_logo.png", size=(15, 15))
        self._discord_img = discord_img   # keep a ref so it isn't GC'd
        _bottom_btn("☕  " + _at("support_btn", self._lang), self._open_support,
                    self._t("support_fill"), self._t("support_text"),
                    self._t("support_hover"), pady=(2, 12))
        _bottom_btn("Discord", lambda: __import__("webbrowser").open(
            "https://discord.com/invite/MNg2g9Pp6K"),
            "#5865F2", "#ffffff", "#4752c4", image=discord_img)
        _bottom_btn("🐞  " + _at("report_help_btn", self._lang),
                    self._open_report_help, self._t("surface_alt"),
                    self._t("text"), self._t("surface"))
        _bottom_btn("⚙  " + _at("settings_window_title", self._lang),
                    self._open_settings,
                    self._t("surface_alt"), self._t("text"), self._t("surface"),
                    pady=(2, 2))

        return sb

    def _build_header(self, parent):
        """Main-column header: page title (left) + monitor picker & overlay
        on/off indicator (right)."""
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(side="top", fill="x", padx=theme.PAD_SECTION, pady=(12, 6))

        self._page_title_var = ctk.StringVar(value="")
        ctk.CTkLabel(hdr, textvariable=self._page_title_var,
                     font=theme.TITLE_FONT).pack(side="left")

        # Overlay status indicator (rightmost) — click to toggle.
        self._overlay_indicator = ctk.CTkButton(
            hdr, text="", width=104, height=28, font=theme.HINT_FONT,
            fg_color=self._t("surface_alt"), hover_color=self._t("border"),
            command=lambda: self._set_overlay_enabled(
                not self._cfg.get('overlay_enabled', False)))
        self._overlay_indicator.pack(side="right", padx=(8, 0))
        self._update_overlay_indicator()

        # Monitor picker (left of the overlay indicator).
        from capture import list_monitors
        _monitors = list_monitors()
        _mon_options = [
            f"{m['index']} — {m['width']}x{m['height']}" +
            (" " + _at('monitor_primary_tag', self._lang)
             if m['left'] == 0 and m['top'] == 0 else "")
            for m in _monitors]
        _saved_idx = self._cfg.get('monitor_index', 1)
        _primary_opt = next((o for o in _mon_options if
                             _at('monitor_primary_tag', self._lang) in o),
                            _mon_options[0] if _mon_options else '1')
        _saved_opt = next((o for o in _mon_options
                           if o.startswith(str(_saved_idx) + ' —')), _primary_opt)
        self._mon_var = ctk.StringVar(value=_saved_opt)
        self._mon_menu = ctk.CTkOptionMenu(
            hdr, variable=self._mon_var,
            values=_mon_options if _mon_options else ['1'],
            command=self._on_monitor_change, width=200)
        self._mon_menu.pack(side="right", padx=8)
        ctk.CTkLabel(hdr, text=_at('label_monitor', self._lang),
                     font=theme.LABEL_FONT).pack(side="right", padx=(0, 4))
        save(self._cfg)

    def _build_race_tab(self) -> ctk.CTkFrame:
        # Solid bg (not transparent): a transparent CTkScrollableFrame canvas
        # has nothing to repaint over old child positions while scrolling, so
        # widgets ghost/smear. "surface" is what sits behind it anyway, so the
        # look is unchanged — just solid enough to clear cleanly on scroll.
        frame = ctk.CTkScrollableFrame(self._main_content, fg_color=self._t("surface"))

        # Description
        ctk.CTkLabel(frame, text=_at("race_description", self._lang),
                     anchor="w", wraplength=480, justify="left",
                     font=("Arial", 12)).pack(fill="x", padx=12, pady=(8, 0))

        # Setup panel
        self._race_setup = SetupPanel(
            frame,
            template_defs=[(k, _at(lk, self._lang)) for k, lk in RACE_TEMPLATE_KEYS],
            folder=get_race_templates('custom', self._tpl_lang),
            nodes_file=None,
            res_cfg_key='race_resolution',
            mode='race',
            log_cb=self._log,
            status_cb=self._set_status,
            lang=self._lang,
            capture_key=self._capture_key,
            main_cfg=self._cfg,
            tpl_lang=self._tpl_lang,
            allow_roi=True,   # per-row "Detection area" override (dev fine-tuning)
            fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"),
        )
        if SHOW_SETUP_PANELS:
            self._race_setup.pack(fill="x", padx=8, pady=(4, 8))

        # Race count row (0 = unlimited)
        count_row = ctk.CTkFrame(frame, fg_color="transparent")
        count_row.pack(fill="x", padx=12, pady=(4, 0))
        ctk.CTkLabel(count_row, text=_at("race_count_label", self._lang),
                     font=("Arial", 12)).pack(side="left")
        self._race_count_var = ctk.StringVar(value="0")
        ctk.CTkEntry(count_row, textvariable=self._race_count_var,
                     width=70, justify="center").pack(side="left", padx=8)
        ctk.CTkLabel(count_row, text=_at("delete_count_hint", self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side="left")

        # Run controls
        self._build_run_controls(frame, mode="race")

        # Log
        self._race_log = LogWidget(frame,
                                    placeholder=_at('log_placeholder', self._lang),
                                    warn_color=self._t("warn"),
            title=_at("label_activity", self._lang),
            title_color=self._t("text"), loop_color=self._t("log_accent"),
            sep_color=self._t("border"), fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._race_log.pack(fill="both", expand=True,
                            padx=8, pady=(4, 8))

        return frame

    def _build_mastery_tab(self) -> ctk.CTkFrame:
        # Solid bg (not transparent): a transparent CTkScrollableFrame canvas
        # has nothing to repaint over old child positions while scrolling, so
        # widgets ghost/smear. "surface" is what sits behind it anyway, so the
        # look is unchanged — just solid enough to clear cleanly on scroll.
        frame = ctk.CTkScrollableFrame(self._main_content, fg_color=self._t("surface"))

        # Description
        ctk.CTkLabel(frame, text=_at("mastery_description", self._lang),
                     anchor="w", wraplength=480, justify="left",
                     font=("Arial", 12)).pack(fill="x", padx=12, pady=(8, 0))

        # Mastery is keyboard-driven and walks the tree with WASD, so its only
        # config is the unlock-path grid (no templates, no node-click capture).
        self._mastery_setup = self._make_mastery_setup(frame)
        self._mastery_setup.pack(fill="x", padx=8, pady=(4, 8))

        # Garage block selector — which contiguous run of cars to unlock
        # (replaces the old count + start-row inputs; see MasteryCarBlockWidget).
        self._mastery_block = MasteryCarBlockWidget(
            frame,
            first_row=self._cfg.get("mastery_block_first_row", 1),
            middle_cols=self._cfg.get("mastery_block_middle_cols", 0),
            last_row=self._cfg.get("mastery_block_last_row", 3),
            on_change=self._on_mastery_block_change, lang=self._lang,
            fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._mastery_block.pack(fill="x", padx=8, pady=(4, 8))

        # Run controls
        self._build_run_controls(frame, mode="mastery")

        # Log
        self._mastery_log = LogWidget(frame,
                                      placeholder=_at('log_placeholder', self._lang),
                                      warn_color=self._t("warn"),
            title=_at("label_activity", self._lang),
            title_color=self._t("text"), loop_color=self._t("log_accent"),
            sep_color=self._t("border"), fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._mastery_log.pack(fill="both", expand=True,
                               padx=8, pady=(4, 8))

        return frame

    def _build_settings_fields(self, frame, fields):
        # fields: (label, cfg_key, lo, hi, step, tip_key)
        for label, key, lo, hi, step, tip_key in fields:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            # Label text (no tooltip)
            ctk.CTkLabel(row, text=label, width=160,
                         anchor="w").pack(side="left")
            # ? icon — tooltip only fires here
            q_lbl = ctk.CTkLabel(row, text="?", width=18,
                                 font=("Segoe UI", 11),
                                 text_color=self._t("text_muted"),
                                 cursor="question_arrow")
            q_lbl.pack(side="left", padx=(0, 6))
            Tooltip(q_lbl, _at(tip_key, self._lang))
            raw = self._cfg.get(key, lo)
            clamped = max(lo, min(hi, float(raw)))
            var = ctk.DoubleVar(value=clamped)
            val_lbl = ctk.CTkLabel(row, text=f"{var.get():.2f}",
                                   width=52, anchor="e",
                                   font=("Segoe UI", 12))
            val_lbl.pack(side="right", padx=(4, 0))
            # Update label while dragging
            var.trace_add("write",
                          lambda *a, vl=val_lbl, va=var:
                          vl.configure(text=f"{va.get():.2f}"))
            slider = ctk.CTkSlider(
                row, variable=var,
                from_=lo, to=hi,
                **theme.slider_kwargs(self._cfg))
            # Save only on mouse release
            slider.bind('<ButtonRelease-1>',
                        lambda e, k=key, va=var: self._on_setting_change(k, va))
            slider.pack(side="left", fill="x", expand=True, padx=4)

    def _build_full_auto_tab(self) -> ctk.CTkFrame:
        # Solid bg (not transparent): a transparent CTkScrollableFrame canvas
        # has nothing to repaint over old child positions while scrolling, so
        # widgets ghost/smear. "surface" is what sits behind it anyway, so the
        # look is unchanged — just solid enough to clear cleanly on scroll.
        frame = ctk.CTkScrollableFrame(self._main_content, fg_color=self._t("surface"))

        # Description
        ctk.CTkLabel(frame, text=_at("full_auto_description", self._lang),
                     anchor="w", wraplength=480, justify="left",
                     font=("Arial", 12)).pack(fill="x", padx=12, pady=(8, 0))

        # Races-per-cycle count row (user-defined; for mastery points)
        count_row = ctk.CTkFrame(frame, fg_color="transparent")
        count_row.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(count_row, text=_at("full_auto_count_label", self._lang),
                     font=("Arial", 12)).pack(side="left")
        self._full_auto_count_var = ctk.StringVar(value="0")
        ctk.CTkEntry(count_row, textvariable=self._full_auto_count_var,
                     width=70, justify="center").pack(side="left", padx=8)

        # Start-cycle-from selector (first cycle only) — for users who already
        # have points/cars lined up and want to skip ahead.
        start_row = ctk.CTkFrame(frame, fg_color="transparent")
        start_row.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(start_row, text=_at("full_auto_start_label", self._lang),
                     font=theme.LABEL_FONT).pack(side="left")
        self._fa_start_labels = {
            "race":    _at("full_auto_start_race", self._lang),
            "buy":     _at("full_auto_start_buy", self._lang),
            "mastery": _at("full_auto_start_mastery", self._lang),
            "sell":    _at("full_auto_start_sell", self._lang),
            "spin":    _at("full_auto_start_spin", self._lang),
        }
        start_keys = self._fa_start_keys()
        cur_start = self._cfg.get("full_auto_start_from", "race")
        if cur_start not in start_keys:
            cur_start = "race"
        self._fa_start_var = ctk.StringVar(value=self._fa_start_labels[cur_start])
        self._fa_start_menu = ctk.CTkOptionMenu(
            start_row,
            variable=self._fa_start_var,
            values=[self._fa_start_labels[k] for k in start_keys],
            command=self._on_fa_start_change,
            width=200, height=30, corner_radius=theme.token("corner_sm"),
            fg_color=theme.token("surface"), text_color=theme.token("text"),
            button_color=theme.token("accent"),
            button_hover_color=theme.token("accent_hover"),
        )
        self._fa_start_menu.pack(side="left", padx=theme.PAD_INLINE)

        # Grind type: what the chain farms — Wheelspin (22B), Money (GTS ACR), or
        # Mixed (alternate each cycle).
        grind_row = ctk.CTkFrame(frame, fg_color="transparent")
        grind_row.pack(fill="x", padx=12, pady=(8, 0))
        self._fa_grind_row = grind_row
        ctk.CTkLabel(grind_row, text=_at("full_auto_grind_label", self._lang),
                     font=theme.LABEL_FONT).pack(side="left")
        self._fa_grind_labels = {
            "wheelspin": _at("full_auto_grind_wheelspin", self._lang),
            "money":     _at("full_auto_grind_money", self._lang),
            "mixed":     _at("full_auto_grind_mixed", self._lang),
        }
        cur_grind = self._cfg.get("full_auto_grind_type", "wheelspin")
        if cur_grind not in self._fa_grind_labels:
            cur_grind = "wheelspin"
        self._fa_grind_var = ctk.StringVar(value=self._fa_grind_labels[cur_grind])
        ctk.CTkSegmentedButton(
            grind_row,
            values=[self._fa_grind_labels["wheelspin"],
                    self._fa_grind_labels["money"],
                    self._fa_grind_labels["mixed"]],
            variable=self._fa_grind_var,
            command=self._on_fa_grind_change,
            height=32,
            **theme.segbtn_kwargs(self._cfg),
        ).pack(side="left", padx=theme.PAD_INLINE)

        # Branch toggle: spin wheels each cycle, or straight back to racing.
        # Shown only for grind types that spin (wheelspin / mixed) — see
        # _apply_fa_branch_visibility; it doesn't apply to money grind.
        branch_row = ctk.CTkFrame(frame, fg_color="transparent")
        branch_row.pack(fill="x", padx=12, pady=(8, 0))
        self._fa_branch_row = branch_row
        ctk.CTkLabel(branch_row, text=_at("full_auto_branch_label", self._lang),
                     font=theme.LABEL_FONT).pack(side="left")
        self._fa_branch_labels = {
            "racing":    _at("full_auto_branch_racing", self._lang),
            "wheelspin": _at("full_auto_branch_wheelspin", self._lang),
        }
        cur_branch = self._cfg.get("full_auto_branch_mode", "racing")
        if cur_branch not in self._fa_branch_labels:
            cur_branch = "racing"
        self._fa_branch_var = ctk.StringVar(
            value=self._fa_branch_labels[cur_branch])
        ctk.CTkSegmentedButton(
            branch_row,
            values=[self._fa_branch_labels["racing"],
                    self._fa_branch_labels["wheelspin"]],
            variable=self._fa_branch_var,
            command=self._on_fa_branch_change,
            height=32,
            **theme.segbtn_kwargs(self._cfg),
        ).pack(side="left", padx=theme.PAD_INLINE)
        ctk.CTkLabel(branch_row, text=_at("full_auto_branch_note", self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side="left",
                                                            padx=theme.PAD_INLINE)
        self._apply_fa_branch_visibility(cur_grind)   # hide for money grind

        # Setup panel — chain-only nav templates, grouped by category.
        self._full_auto_setup = self._make_full_auto_setup(frame)
        self._full_auto_setup.pack(fill="x", padx=8, pady=(4, 8))

        # No mastery-grid widgets here: Full Auto's grind cars are pre-determined
        # (22B-STi / Dodge Viper GTS ACR), so their unlock paths are HARD-CODED in
        # full_auto.py (_GRID_22B / _GRID_GTSACR) — nothing for the user to capture.

        # Pre-flight checklist — gates Start until every requirement is ticked.
        self._build_fa_checklist(frame)

        # Run controls
        self._build_run_controls(frame, mode="full_auto")
        # Start begins disabled unless the (persisted) checklist is already
        # fully satisfied.
        self._update_fa_start_enabled()

        # Log
        self._full_auto_log = LogWidget(frame,
            placeholder=_at('log_placeholder', self._lang),
            warn_color=self._t("warn"),
            title=_at("label_activity", self._lang),
            title_color=self._t("text"), loop_color=self._t("log_accent"),
            sep_color=self._t("border"), fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._full_auto_log.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        return frame

    def _build_full_auto_locked_tab(self) -> ctk.CTkFrame:
        """Paywall view shown in place of the Full Auto tab when unlicensed:
        a description of what Full Auto does + a Buy button (store link, set via
        license_client.STORE_URL) + a hint to enter a key in Settings."""
        frame = ctk.CTkScrollableFrame(self._main_content, fg_color=self._t("surface"))

        ctk.CTkLabel(frame, text="🔒 " + _at("fa_lock_title", self._lang),
                     anchor="w", font=("Arial", 18, "bold")).pack(
                         fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(frame, text=_at("fa_lock_desc", self._lang),
                     anchor="w", wraplength=520, justify="left",
                     font=("Arial", 13), text_color=self._t("text")).pack(
                         fill="x", padx=16, pady=(0, 12))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkButton(
            btn_row, text=_at("fa_lock_buy_btn", self._lang),
            height=40, width=200, font=("Arial", 13, "bold"),
            command=self._on_fa_buy).pack(side="left")

        ctk.CTkLabel(frame, text=_at("fa_lock_have_key", self._lang),
                     anchor="w", font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(
                         fill="x", padx=16, pady=(8, 2))
        ctk.CTkButton(
            frame, text=_at("fa_lock_settings_btn", self._lang),
            height=30, width=160, fg_color="transparent", border_width=1,
            border_color=self._t("border"), text_color=self._t("text"),
            hover_color=self._t("surface_alt"),
            command=self._open_settings).pack(anchor="w", padx=16, pady=(0, 12))
        return frame

    def _on_fa_buy(self):
        """Open the store page, or note it's not live yet (awaiting LS review)."""
        import license_client
        if license_client.STORE_URL:
            __import__("webbrowser").open(license_client.STORE_URL)
        else:
            self._set_status(_at("fa_lock_soon", self._lang))

    def _fa_start_keys(self):
        """Start-cycle-from options. Only race/buy are auto-count-compatible:
        both flow through the buy step, where the per-cycle count is read from
        the tech points (race earns them first; buy uses points already banked).
        Mastery/sell/spin starts would have no count basis, so they're not
        offered."""
        return ["race", "buy"]

    def _refresh_fa_start_options(self):
        """Rebuild the start-from dropdown for the current branch; if the chosen
        start is no longer available (e.g. 'spin' after leaving wheelspin), reset
        it to race."""
        if not hasattr(self, "_fa_start_menu"):
            return
        keys = self._fa_start_keys()
        self._fa_start_menu.configure(
            values=[self._fa_start_labels[k] for k in keys])
        if self._cfg.get("full_auto_start_from", "race") not in keys:
            self._cfg["full_auto_start_from"] = "race"
            save(self._cfg)
            self._fa_start_var.set(self._fa_start_labels["race"])

    def _on_fa_branch_change(self, val: str):
        rev = {v: k for k, v in getattr(self, "_fa_branch_labels", {}).items()}
        self._cfg["full_auto_branch_mode"] = rev.get(val, "racing")
        save(self._cfg)
        self._refresh_fa_start_options()

    def _on_fa_grind_change(self, val: str):
        rev = {v: k for k, v in getattr(self, "_fa_grind_labels", {}).items()}
        grind = rev.get(val, "wheelspin")
        self._cfg["full_auto_grind_type"] = grind
        save(self._cfg)
        self._apply_fa_branch_visibility(grind)

    def _apply_fa_branch_visibility(self, grind: str):
        """The 'After selling' branch toggle only applies to grind types that
        spin (wheelspin / mixed). Hide it for money grind, where it's irrelevant."""
        row = getattr(self, "_fa_branch_row", None)
        if row is None:
            return
        if grind in ("wheelspin", "mixed"):
            row.pack(fill="x", padx=12, pady=(8, 0), after=self._fa_grind_row)
        else:
            row.pack_forget()

    def _on_fa_start_change(self, val: str):
        rev = {v: k for k, v in getattr(self, "_fa_start_labels", {}).items()}
        self._cfg["full_auto_start_from"] = rev.get(val, "race")
        save(self._cfg)

    # ── Full Auto pre-flight checklist ────────────────────────
    # The chain makes destructive, garage-state-dependent assumptions, so Start
    # is gated until every box is ticked. (key, label_string, persist):
    #   map     → per-session state, reset each launch.
    #   driving → per-session: the FIRST cycle never sell-drives the grind car
    #             (the sell step that auto-drives it runs AFTER the first race),
    #             so the user must already be driving it at the start.
    #   favorite/stock_paint → one-time garage state, persisted via
    #             fa_check_<key>_ok. stock_paint: a custom livery changes the
    #             car tile's pixels and breaks grind_car template matching.
    _FA_CHECKLIST = [
        ("map",         "fa_check_map",         False),
        ("driving",     "fa_check_driving",     False),
        ("favorite",    "fa_check_favorite",    True),
        ("stock_paint", "fa_check_stock_paint", True),
    ]

    def _build_fa_checklist(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self._t("surface_alt"),
                            border_width=1, border_color=self._t("border"),
                            corner_radius=self._t("corner"))
        card.pack(fill="x", padx=12, pady=(4, 4))
        ctk.CTkLabel(card, text=_at("fa_check_title", self._lang),
                     anchor="w", font=theme.LABEL_FONT,
                     text_color=self._t("text")).pack(fill="x", padx=12,
                                                       pady=(10, 2))
        self._fa_check_vars = {}
        for key, lbl_key, persist in self._FA_CHECKLIST:
            init = bool(self._cfg.get(f"fa_check_{key}_ok", False)) if persist else False
            var = ctk.BooleanVar(value=init)
            self._fa_check_vars[key] = (var, persist)
            ctk.CTkCheckBox(
                card, text=_at(lbl_key, self._lang), variable=var,
                onvalue=True, offvalue=False, font=("Arial", 12),
                command=lambda k=key: self._on_fa_check(k),
            ).pack(fill="x", anchor="w", padx=16, pady=4)
        ctk.CTkLabel(card, text="", height=2).pack()

    def _on_fa_check(self, key):
        var, persist = self._fa_check_vars[key]
        if persist:
            self._cfg[f"fa_check_{key}_ok"] = bool(var.get())
            save(self._cfg)
        self._update_fa_start_enabled()

    def _fa_checklist_ok(self) -> bool:
        vars_ = getattr(self, "_fa_check_vars", None)
        if not vars_:
            return True   # checklist not built yet — don't block
        return all(v.get() for v, _ in vars_.values())

    def _update_fa_start_enabled(self):
        # Respect an active run (Start stays disabled while running).
        if self._auto_thread and self._auto_thread.is_alive():
            return
        if hasattr(self, "_full_auto_start_btn"):
            self._full_auto_start_btn.configure(
                state="normal" if self._fa_checklist_ok() else "disabled")

    def _build_buy_tab(self) -> ctk.CTkFrame:
        # Solid bg (not transparent): a transparent CTkScrollableFrame canvas
        # has nothing to repaint over old child positions while scrolling, so
        # widgets ghost/smear. "surface" is what sits behind it anyway, so the
        # look is unchanged — just solid enough to clear cleanly on scroll.
        frame = ctk.CTkScrollableFrame(self._main_content, fg_color=self._t("surface"))

        # Description
        desc = ctk.CTkFrame(frame, fg_color="transparent")
        desc.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(desc, text=_at("buy_description", self._lang),
                     anchor="w", wraplength=480, justify="left",
                     font=("Arial", 12)).pack(fill="x")

        # Setup panel — optional menu-navigation templates (start/end on the
        # main menu). All best-effort: empty/partial → buy runs the macro where
        # the user already positioned (legacy behaviour).
        self._buy_setup = self._make_buy_setup(frame)
        if SHOW_SETUP_PANELS:
            self._buy_setup.pack(fill="x", padx=8, pady=(4, 8))

        # Count row
        count_row = ctk.CTkFrame(frame, fg_color="transparent")
        count_row.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(count_row, text=_at("buy_count_label", self._lang),
                     font=("Arial", 12)).pack(side="left")
        self._buy_count_var = ctk.StringVar(value="0")
        ctk.CTkEntry(count_row, textvariable=self._buy_count_var,
                     width=70, justify="center").pack(side="left", padx=8)
        ctk.CTkLabel(count_row, text=_at("delete_count_hint", self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side="left")

        # Run controls
        self._build_run_controls(frame, mode="buy")

        # Log
        self._buy_log = LogWidget(frame, warn_color=self._t("warn"),
            title=_at("label_activity", self._lang),
            title_color=self._t("text"), loop_color=self._t("log_accent"),
            sep_color=self._t("border"), fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._buy_log.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        return frame

    def _build_delete_tab(self) -> ctk.CTkFrame:
        # Scrollable + solid bg (the garage-block picker makes the tab taller;
        # solid surface avoids CTkScrollableFrame scroll-ghosting).
        frame = ctk.CTkScrollableFrame(self._main_content,
                                       fg_color=self._t("surface"))

        desc = ctk.CTkFrame(frame, fg_color="transparent")
        desc.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(desc, text=_at("delete_description", self._lang),
                     anchor="w", wraplength=480,
                     font=("Arial", 12), justify="left").pack(fill="x")

        # Car count via the garage-block picker (same widget as mastery). The
        # delete loop is UNCHANGED — this just derives the count visually, and
        # makes "all cars between the first and last get deleted" explicit.
        self._delete_block = MasteryCarBlockWidget(
            frame,
            first_row=self._cfg.get("delete_block_first_row", 1),
            middle_cols=self._cfg.get("delete_block_middle_cols", 0),
            last_row=self._cfg.get("delete_block_last_row", 3),
            on_change=self._on_delete_block_change, lang=self._lang,
            title_key="delete_block_title", hint_key="delete_block_hint",
            fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._delete_block.pack(fill="x", padx=8, pady=(4, 8))

        # Destructive-action confirmation. Per-session (NOT persisted) — the user
        # re-confirms each launch before the blind sell macro can run. Gates Start.
        confirm = ctk.CTkFrame(frame, fg_color="transparent")
        confirm.pack(fill="x", padx=12, pady=(0, 4))
        self._delete_confirm_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            confirm, text=_at("delete_confirm", self._lang),
            variable=self._delete_confirm_var, onvalue=True, offvalue=False,
            font=("Arial", 12), command=self._on_delete_confirm,
        ).pack(fill="x", anchor="w")

        self._build_run_controls(frame, mode="delete")

        self._delete_log = LogWidget(frame, warn_color=self._t("warn"),
            title=_at("label_activity", self._lang),
            title_color=self._t("text"), loop_color=self._t("log_accent"),
            sep_color=self._t("border"), fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._delete_log.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self._update_delete_start_enabled()   # Start gated until confirm is ticked
        return frame

    def _on_delete_block_change(self, first_row, middle_cols, last_row):
        self._cfg["delete_block_first_row"]   = int(first_row)
        self._cfg["delete_block_middle_cols"] = int(middle_cols)
        self._cfg["delete_block_last_row"]    = int(last_row)
        save(self._cfg)

    def _on_delete_confirm(self):
        self._update_delete_start_enabled()

    def _delete_confirm_ok(self) -> bool:
        var = getattr(self, "_delete_confirm_var", None)
        return bool(var.get()) if var is not None else False

    def _update_delete_start_enabled(self):
        # Don't override the disabled state while a run is active.
        if self._auto_thread and self._auto_thread.is_alive():
            return
        if hasattr(self, "_delete_start_btn"):
            self._delete_start_btn.configure(
                state="normal" if self._delete_confirm_ok() else "disabled")

    def _build_spin_tab(self) -> ctk.CTkFrame:
        # Solid bg (not transparent): a transparent CTkScrollableFrame canvas
        # has nothing to repaint over old child positions while scrolling, so
        # widgets ghost/smear. "surface" is what sits behind it anyway, so the
        # look is unchanged — just solid enough to clear cleanly on scroll.
        frame = ctk.CTkScrollableFrame(self._main_content, fg_color=self._t("surface"))

        # Description — includes the explicit unattended-Sell warning.
        ctk.CTkLabel(frame, text=_at("spin_description", self._lang),
                     anchor="w", wraplength=480, justify="left",
                     font=("Arial", 12)).pack(fill="x", padx=12, pady=(8, 0))

        # Setup panel — ONE detect-only template (the duplicate-reward menu).
        self._spin_setup = self._make_spin_setup(frame)
        if SHOW_SETUP_PANELS:
            self._spin_setup.pack(fill="x", padx=8, pady=(4, 8))

        # Wheel-type toggle (Super Wheelspin / normal Wheelspin) — only changes
        # which tile is clicked to start; the rest of the flow is identical.
        type_row = ctk.CTkFrame(frame, fg_color="transparent")
        type_row.pack(fill="x", padx=12, pady=(4, 0))
        ctk.CTkLabel(type_row, text=_at("spin_type_label", self._lang),
                     font=theme.LABEL_FONT).pack(side="left")
        self._spin_type_labels = {
            "super":  _at("spin_type_super", self._lang),
            "normal": _at("spin_type_normal", self._lang),
        }
        cur_type = self._cfg.get("wheelspin_type", "super")
        if cur_type not in self._spin_type_labels:
            cur_type = "super"
        self._spin_type_var = ctk.StringVar(
            value=self._spin_type_labels[cur_type])
        ctk.CTkSegmentedButton(
            type_row,
            values=[self._spin_type_labels["super"],
                    self._spin_type_labels["normal"]],
            variable=self._spin_type_var,
            command=self._on_spin_type_change,
            height=32,
            **theme.segbtn_kwargs(self._cfg),
        ).pack(side="left", padx=theme.PAD_INLINE)

        # Duplicate-handling mode toggle (garage / sell)
        mode_row = ctk.CTkFrame(frame, fg_color="transparent")
        mode_row.pack(fill="x", padx=12, pady=(4, 0))
        self._spin_mode_row = mode_row
        ctk.CTkLabel(mode_row, text=_at("spin_mode_label", self._lang),
                     font=theme.LABEL_FONT).pack(side="left")
        self._spin_mode_labels = {
            "garage": _at("spin_mode_garage", self._lang),
            "sell":   _at("spin_mode_sell", self._lang),
        }
        cur_mode = self._cfg.get("wheelspin_dup_mode", "garage")
        if cur_mode not in self._spin_mode_labels:
            cur_mode = "garage"
        self._spin_mode_var = ctk.StringVar(
            value=self._spin_mode_labels[cur_mode])
        ctk.CTkSegmentedButton(
            mode_row,
            values=[self._spin_mode_labels["garage"],
                    self._spin_mode_labels["sell"]],
            variable=self._spin_mode_var,
            command=self._on_spin_mode_change,
            height=32,
            **theme.segbtn_kwargs(self._cfg),
        ).pack(side="left", padx=theme.PAD_INLINE)
        ctk.CTkLabel(mode_row, text=_at("spin_mode_hint", self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side="left")

        # Keep Forza Edition (FE) duplicates instead of selling them. Sell mode
        # only (Garage keeps everything anyway), so the row is shown only when
        # Sell is selected — see _apply_spin_fe_visibility.
        fe_row = ctk.CTkFrame(frame, fg_color="transparent")
        self._spin_fe_row = fe_row
        self._spin_keep_fe_var = ctk.BooleanVar(
            value=bool(self._cfg.get("wheelspin_keep_fe", True)))
        ctk.CTkCheckBox(
            fe_row, text=_at("spin_keep_fe_label", self._lang),
            variable=self._spin_keep_fe_var, onvalue=True, offvalue=False,
            font=("Arial", 12), command=self._on_spin_keep_fe_change,
        ).pack(side="left")
        ctk.CTkLabel(fe_row, text=_at("spin_keep_fe_hint", self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side="left",
                                                             padx=theme.PAD_INLINE)
        self._apply_spin_fe_visibility(cur_mode)   # show only in sell mode

        # Spin count row (0 = unlimited)
        count_row = ctk.CTkFrame(frame, fg_color="transparent")
        count_row.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(count_row, text=_at("spin_count_label", self._lang),
                     font=("Arial", 12)).pack(side="left")
        self._spin_count_var = ctk.StringVar(value="0")
        ctk.CTkEntry(count_row, textvariable=self._spin_count_var,
                     width=70, justify="center").pack(side="left", padx=8)
        ctk.CTkLabel(count_row, text=_at("delete_count_hint", self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side="left")

        # Run controls
        self._build_run_controls(frame, mode="spin")

        # Log
        self._spin_log = LogWidget(frame,
                                   placeholder=_at('log_placeholder', self._lang),
                                   warn_color=self._t("warn"),
            title=_at("label_activity", self._lang),
            title_color=self._t("text"), loop_color=self._t("log_accent"),
            sep_color=self._t("border"), fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"))
        self._spin_log.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        return frame

    def _make_spin_setup(self, parent) -> SetupPanel:
        """Auto Spin Wheel Setup panel — ONE detect-only template
        (wheelspin_duplicate); no node capture."""
        return SetupPanel(
            parent,
            template_defs=[(k, _at(lk, self._lang))
                           for k, lk in SPIN_TEMPLATE_KEYS],
            folder=get_wheelspin_templates('custom', self._tpl_lang),
            nodes_file=None,
            res_cfg_key='wheelspin_resolution',
            mode='wheelspin',
            log_cb=self._log,
            status_cb=self._set_status,
            lang=self._lang,
            capture_key=self._capture_key,
            main_cfg=self._cfg,
            tpl_lang=self._tpl_lang,
            allow_roi=True,   # per-row "Detection area" override (dev fine-tuning)
            fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"),
        )

    def _make_buy_setup(self, parent) -> SetupPanel:
        """Auto Buy Setup panel — optional menu-navigation templates (start/end
        on the main menu). All best-effort; no node capture."""
        return SetupPanel(
            parent,
            template_defs=[(k, _at(lk, self._lang))
                           for k, lk in BUY_TEMPLATE_KEYS],
            folder=get_buy_templates('custom', self._tpl_lang),
            nodes_file=None,
            res_cfg_key='buy_resolution',
            mode='buy',
            log_cb=self._log,
            status_cb=self._set_status,
            lang=self._lang,
            capture_key=self._capture_key,
            main_cfg=self._cfg,
            tpl_lang=self._tpl_lang,
            allow_roi=True,   # per-row "Detection area" override (dev fine-tuning)
            fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"),
        )

    def _make_full_auto_setup(self, parent) -> SetupPanel:
        """Full Auto Setup panel — chain-only nav templates, grouped by category
        (currently the mastery positioning nav). custom-only; no node capture."""
        return SetupPanel(
            parent,
            template_defs=[(_at(cat, self._lang),
                            [(k, _at(lk, self._lang)) for k, lk in items])
                           for cat, items in FULL_AUTO_TEMPLATE_KEYS],
            folder=get_full_auto_templates('custom', self._tpl_lang),
            nodes_file=None,
            res_cfg_key='full_auto_resolution',
            mode='full_auto',
            log_cb=self._log,
            status_cb=self._set_status,
            lang=self._lang,
            capture_key=self._capture_key,
            main_cfg=self._cfg,
            tpl_lang=self._tpl_lang,
            allow_roi=True,   # per-row "Detection area" override (Full Auto only)
            fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"),
        )

    def _on_spin_type_change(self, val: str):
        rev = {v: k for k, v in getattr(self, "_spin_type_labels", {}).items()}
        self._cfg["wheelspin_type"] = rev.get(val, "super")
        save(self._cfg)

    def _on_spin_mode_change(self, val: str):
        rev = {v: k for k, v in getattr(self, "_spin_mode_labels", {}).items()}
        mode = rev.get(val, "garage")
        self._cfg["wheelspin_dup_mode"] = mode
        save(self._cfg)
        self._apply_spin_fe_visibility(mode)   # FE toggle is sell-mode only

    def _apply_spin_fe_visibility(self, mode: str):
        """Show the Keep-FE checkbox only in Sell mode (no effect in Garage)."""
        row = getattr(self, "_spin_fe_row", None)
        if row is None:
            return
        if mode == "sell":
            row.pack(fill="x", padx=12, pady=(4, 0),
                     after=self._spin_mode_row)
        else:
            row.pack_forget()

    def _on_spin_keep_fe_change(self):
        self._cfg["wheelspin_keep_fe"] = bool(self._spin_keep_fe_var.get())
        save(self._cfg)

    def _build_run_controls(self, parent, mode: str):
        # Bordered card wrapping the Start / Stop buttons + the F9 hint.
        card = ctk.CTkFrame(parent, fg_color=self._t("surface_alt"),
                            border_width=1, border_color=self._t("border"),
                            corner_radius=self._t("corner"))
        card.pack(fill="x", padx=12, pady=(4, 4))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=12)

        if mode == "full_auto":
            self._full_auto_start_btn = ctk.CTkButton(
                row, text=theme.ICON_START + _at("btn_start", self._lang),
                command=self._start_full_auto,
                width=120, font=theme.BUTTON_FONT,
                fg_color=theme.START_FG, hover_color=theme.START_HOVER,
                text_color=self._t("start_text"))
            self._full_auto_start_btn.pack(side="left", padx=(0, 8))

            self._full_auto_stop_btn = ctk.CTkButton(
                row, text=theme.ICON_STOP + _at("btn_stop", self._lang),
                command=self._stop_auto,
                fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER,
                text_color=self._t("stop_text"),
                width=100, font=theme.BUTTON_FONT, state="disabled")
            self._full_auto_stop_btn.pack(side="left")

            self._full_auto_shortcut_lbl = ctk.CTkLabel(
                row,
                text=_at("shortcut_toggle", self._lang,
                         key=self._toggle_key.upper()),
                font=theme.HINT_FONT,
                text_color=self._t("text_muted"))
            self._full_auto_shortcut_lbl.pack(side="left", padx=(16, 0))

        elif mode == "race":
            self._race_start_btn = ctk.CTkButton(
                row, text=theme.ICON_START + _at("btn_start", self._lang),
                command=self._start_race,
                width=120, font=theme.BUTTON_FONT,
                fg_color=theme.START_FG, hover_color=theme.START_HOVER, text_color=self._t("start_text"))
            self._race_start_btn.pack(side="left", padx=(0, 8))

            self._race_stop_btn = ctk.CTkButton(
                row, text=theme.ICON_STOP + _at("btn_stop", self._lang),
                command=self._stop_auto,
                fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER, text_color=self._t("stop_text"),
                width=100, font=theme.BUTTON_FONT, state="disabled")
            self._race_stop_btn.pack(side="left")

            self._race_shortcut_lbl = ctk.CTkLabel(
                row,
                text=_at("shortcut_toggle", self._lang,
                         key=self._toggle_key.upper()),
                font=theme.HINT_FONT,
                text_color=self._t("text_muted"))
            self._race_shortcut_lbl.pack(side="left", padx=(16, 0))

        elif mode == "mastery":
            self._mastery_start_btn = ctk.CTkButton(
                row, text=theme.ICON_START + _at("btn_start", self._lang),
                command=self._start_mastery,
                width=120, font=theme.BUTTON_FONT,
                fg_color=theme.START_FG, hover_color=theme.START_HOVER, text_color=self._t("start_text"))
            self._mastery_start_btn.pack(side="left", padx=(0, 8))

            self._mastery_stop_btn = ctk.CTkButton(
                row, text=theme.ICON_STOP + _at("btn_stop", self._lang),
                command=self._stop_auto,
                fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER, text_color=self._t("stop_text"),
                width=100, font=theme.BUTTON_FONT, state="disabled")
            self._mastery_stop_btn.pack(side="left")

            self._mastery_shortcut_lbl = ctk.CTkLabel(
                row,
                text=_at("shortcut_toggle", self._lang,
                         key=self._toggle_key.upper()),
                font=theme.HINT_FONT,
                text_color=self._t("text_muted"))
            self._mastery_shortcut_lbl.pack(side="left", padx=(16, 0))

        elif mode == "buy":
            self._buy_start_btn = ctk.CTkButton(
                row, text=theme.ICON_START + _at("btn_start", self._lang),
                command=self._start_buy,
                width=120, font=theme.BUTTON_FONT,
                fg_color=theme.START_FG, hover_color=theme.START_HOVER, text_color=self._t("start_text"))
            self._buy_start_btn.pack(side="left", padx=(0, 8))

            self._buy_stop_btn = ctk.CTkButton(
                row, text=theme.ICON_STOP + _at("btn_stop", self._lang),
                command=self._stop_auto,
                fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER, text_color=self._t("stop_text"),
                width=100, font=theme.BUTTON_FONT, state="disabled")
            self._buy_stop_btn.pack(side="left")

            self._buy_shortcut_lbl = ctk.CTkLabel(
                row,
                text=_at("shortcut_toggle", self._lang,
                         key=self._toggle_key.upper()),
                font=theme.HINT_FONT,
                text_color=self._t("text_muted"))
            self._buy_shortcut_lbl.pack(side="left", padx=(16, 0))

        elif mode == "spin":
            self._spin_start_btn = ctk.CTkButton(
                row, text=theme.ICON_START + _at("btn_start", self._lang),
                command=self._start_spin,
                width=120, font=theme.BUTTON_FONT,
                fg_color=theme.START_FG, hover_color=theme.START_HOVER, text_color=self._t("start_text"))
            self._spin_start_btn.pack(side="left", padx=(0, 8))

            self._spin_stop_btn = ctk.CTkButton(
                row, text=theme.ICON_STOP + _at("btn_stop", self._lang),
                command=self._stop_auto,
                fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER, text_color=self._t("stop_text"),
                width=100, font=theme.BUTTON_FONT, state="disabled")
            self._spin_stop_btn.pack(side="left")

            self._spin_shortcut_lbl = ctk.CTkLabel(
                row,
                text=_at("shortcut_toggle", self._lang,
                         key=self._toggle_key.upper()),
                font=theme.HINT_FONT,
                text_color=self._t("text_muted"))
            self._spin_shortcut_lbl.pack(side="left", padx=(16, 0))

        else:  # delete
            self._delete_start_btn = ctk.CTkButton(
                row, text=theme.ICON_START + _at("btn_start", self._lang),
                command=self._start_delete,
                width=120, font=theme.BUTTON_FONT,
                fg_color=theme.START_FG, hover_color=theme.START_HOVER, text_color=self._t("start_text"))
            self._delete_start_btn.pack(side="left", padx=(0, 8))

            self._delete_stop_btn = ctk.CTkButton(
                row, text=theme.ICON_STOP + _at("btn_stop", self._lang),
                command=self._stop_auto,
                fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER, text_color=self._t("stop_text"),
                width=100, font=theme.BUTTON_FONT, state="disabled")
            self._delete_stop_btn.pack(side="left")

            self._delete_shortcut_lbl = ctk.CTkLabel(
                row,
                text=_at("shortcut_toggle", self._lang,
                         key=self._toggle_key.upper()),
                font=theme.HINT_FONT,
                text_color=self._t("text_muted"))
            self._delete_shortcut_lbl.pack(side="left", padx=(16, 0))

    # ── Tab switching ─────────────────────────────────────────

    def _show_main(self, frame):
        """Show one main-column view (a tab frame or an inline panel), hiding
        whatever was shown before. Everything lives in self._main_content."""
        cur = getattr(self, "_cur_main", None)
        if cur is not None and cur is not frame:
            cur.pack_forget()
        frame.pack(fill="both", expand=True, padx=4, pady=4)
        self._cur_main = frame

    def _set_nav_active(self, key):
        """Highlight the active function-nav item: subtle surface fill + bright
        text + an accent left bar (overlay). Settings is a bottom filled button,
        not a nav item, so opening it just clears the function-nav highlight."""
        for k, btn in self._nav_buttons.items():
            active = (k == key)
            btn.configure(
                fg_color=self._t("surface_alt") if active else "transparent",
                text_color=self._t("text") if active else self._t("text_muted"))
        for k, bar in getattr(self, "_nav_bars", {}).items():
            bar.configure(fg_color=self._t("accent") if k == key
                          else "transparent")

    def _switch_tab(self, tab: str):
        # Always re-show (don't early-return on same tab): a panel may be open
        # with _current_tab still set, and clicking the tab must exit the panel.
        frame = {"full_auto": self._full_auto_frame,
                 "race": self._race_frame, "mastery": self._mastery_frame,
                 "buy": self._buy_frame, "delete": self._delete_frame,
                 "spin": self._spin_frame}[tab]
        # Paywall: show the locked/purchase view in place of the Full Auto tab
        # until a license is active (re-checked on every switch, so activating a
        # key then re-clicking the tab unlocks it without a restart).
        if tab == "full_auto":
            import license_client
            if not license_client.is_allowed():
                frame = self._full_auto_locked_frame
        self._show_main(frame)
        self._current_tab = tab
        self._in_settings = False
        self._in_support = False
        if hasattr(self, "_in_report_help"):
            self._in_report_help = False
        self._set_nav_active(tab)
        self._page_title_var.set(_at(f"page_title_{tab}", self._lang))

        self._active_log = {"full_auto": self._full_auto_log,
                            "race": self._race_log, "mastery": self._mastery_log,
                            "buy": self._buy_log, "delete": self._delete_log,
                            "spin": self._spin_log}[tab]
        self._active_setup_panel = {
            "full_auto": getattr(self, "_full_auto_setup", None),
            "race":    getattr(self, "_race_setup", None),
            "mastery": getattr(self, "_mastery_setup", None),
            "spin":    getattr(self, "_spin_setup", None),
            "buy":     getattr(self, "_buy_setup", None),
        }.get(tab)

    # ── Automation control ────────────────────────────────────

    def _start_race(self):
        if self._auto_thread and self._auto_thread.is_alive():
            return
        self._stop_event.clear()
        self._set_status(_at("status_starting_race", self._lang))
        self._race_start_btn.configure(state="disabled")
        self._race_stop_btn.configure(state="normal")
        self._race_log.clear()

        cfg = self._cfg   # reference so monitor changes are picked up

        def _race_safe():
            log_cb = self._race_log.log
            try:
                from race import run as race_run
                lang = cfg.get('lang', 'en')
                log_cb(_at('startup_switch_to_game', lang))
                import time as _t
                for i in range(3, 0, -1):
                    if self._stop_event.is_set(): return
                    log_cb(_at('startup_countdown', lang, i=i))
                    self._set_status(_at('startup_countdown', lang, i=i))
                    _t.sleep(1)
                if self._stop_event.is_set(): return
                log_cb(_at('startup_running', lang))
                try:
                    max_loops = int(self._race_count_var.get())
                except ValueError:
                    max_loops = 0
                race_run(cfg, self._stop_event,
                         self._race_log.log, self._set_status,
                         max_loops=max_loops,
                         warn_cb=self._race_log.log_warning,
                         section_cb=self._race_log.log_section)
            except Exception as e:
                import traceback
                self._race_log.log(f'ERROR: {e}')
                self._race_log.log(traceback.format_exc())
                self._set_status(f'Error: {e}')

        self._auto_thread = threading.Thread(
            target=_race_safe, daemon=True)
        self._auto_thread.start()
        self._poll_thread()

    def _start_mastery(self):
        if self._auto_thread and self._auto_thread.is_alive():
            return
        self._stop_event.clear()
        self._set_status(_at("status_starting_mastery", self._lang))
        self._mastery_start_btn.configure(state="disabled")
        self._mastery_stop_btn.configure(state="normal")
        self._mastery_log.clear()

        cfg = self._cfg   # reference so monitor changes are picked up

        def _mastery_safe():
            log_cb = self._mastery_log.log
            try:
                from mastery import run as mastery_run
                lang = cfg.get('lang', 'en')
                log_cb(_at('startup_switch_to_game', lang))
                import time as _t
                for i in range(3, 0, -1):
                    if self._stop_event.is_set(): return
                    log_cb(_at('startup_countdown', lang, i=i))
                    self._set_status(_at('startup_countdown', lang, i=i))
                    _t.sleep(1)
                if self._stop_event.is_set(): return
                log_cb(_at('startup_running', lang))
                # Derive the car count + start row from the garage-block picker.
                fr = max(1, min(3, int(cfg.get("mastery_block_first_row", 1))))
                lr = max(1, min(3, int(cfg.get("mastery_block_last_row", 3))))
                mc = max(0, int(cfg.get("mastery_block_middle_cols", 0)))
                max_cars = MasteryCarBlockWidget.count(fr, mc, lr)
                mastery_run(cfg, self._stop_event,
                            self._mastery_log.log, self._set_status,
                            max_cars=max_cars, start_loop=fr,
                            warn_cb=self._mastery_log.log_warning,
                            section_cb=self._mastery_log.log_section)
            except Exception as e:
                import traceback
                self._mastery_log.log(f'ERROR: {e}')
                self._mastery_log.log(traceback.format_exc())
                self._set_status(f'Error: {e}')

        self._auto_thread = threading.Thread(
            target=_mastery_safe, daemon=True)
        self._auto_thread.start()
        self._poll_thread()

    def _start_buy(self):
        if self._auto_thread and self._auto_thread.is_alive():
            return
        self._stop_event.clear()
        self._set_status(_at("status_starting_buy", self._lang))
        self._buy_start_btn.configure(state="disabled")
        self._buy_stop_btn.configure(state="normal")
        self._buy_log.clear()

        def _buy_safe():
            log_cb = self._buy_log.log
            lang = self._cfg.get('lang', 'en')
            try:
                import time as _t
                log_cb(_at('startup_switch_to_game', lang))
                for i in range(3, 0, -1):
                    if self._stop_event.is_set(): return
                    log_cb(_at('startup_countdown', lang, i=i))
                    self._set_status(_at('startup_countdown', lang, i=i))
                    _t.sleep(1)
                if self._stop_event.is_set(): return
                import config as _cfg_mod
                from buy import run as buy_run
                try:
                    max_buy = int(self._buy_count_var.get())
                except ValueError:
                    max_buy = 0
                buy_run(
                    cfg=_cfg_mod.load(),
                    stop_event=self._stop_event,
                    log_cb=log_cb,
                    status_cb=self._set_status,
                    max_loops=max_buy,
                    section_cb=self._buy_log.log_section,
                )
            except Exception as e:
                import traceback
                log_cb(f'ERROR: {e}')
                log_cb(traceback.format_exc())
                self._set_status(f'Error: {e}')

        self._auto_thread = threading.Thread(
            target=_buy_safe, daemon=True)
        self._auto_thread.start()
        self._poll_thread()

    def _start_delete(self):
        if self._auto_thread and self._auto_thread.is_alive():
            return
        # Destructive — block if the confirmation isn't ticked (also covers the
        # F9 hotkey path, which bypasses the disabled Start button).
        if not self._delete_confirm_ok():
            self._set_status(_at("status_delete_confirm", self._lang))
            self._delete_log.log(_at("log_delete_confirm_block", self._lang))
            return
        self._stop_event.clear()
        self._set_status(_at("status_starting_delete", self._lang))
        self._delete_start_btn.configure(state="disabled")
        self._delete_stop_btn.configure(state="normal")
        self._delete_log.clear()

        def _delete_safe():
            log_cb = self._delete_log.log
            lang = self._cfg.get('lang', 'en')
            try:
                import time as _t
                log_cb(_at('startup_switch_to_game', lang))
                for i in range(3, 0, -1):
                    if self._stop_event.is_set(): return
                    log_cb(_at('startup_countdown', lang, i=i))
                    self._set_status(_at('startup_countdown', lang, i=i))
                    _t.sleep(1)
                if self._stop_event.is_set(): return
                import config as _cfg_mod
                from delete_cars import run as delete_run
                # Derive the car count from the garage-block picker (same model
                # as mastery). The delete loop itself is unchanged.
                fr = max(1, min(3, int(self._cfg.get("delete_block_first_row", 1))))
                lr = max(1, min(3, int(self._cfg.get("delete_block_last_row", 3))))
                mc = max(0, int(self._cfg.get("delete_block_middle_cols", 0)))
                max_cars = MasteryCarBlockWidget.count(fr, mc, lr)
                delete_run(
                    cfg=_cfg_mod.load(),
                    stop_event=self._stop_event,
                    log_cb=log_cb,
                    status_cb=self._set_status,
                    max_cars=max_cars,
                )
            except Exception as e:
                import traceback
                log_cb(f'ERROR: {e}')
                log_cb(traceback.format_exc())
                self._set_status(f'Error: {e}')

        self._auto_thread = threading.Thread(
            target=_delete_safe, daemon=True)
        self._auto_thread.start()
        self._poll_thread()

    def _start_spin(self):
        if self._auto_thread and self._auto_thread.is_alive():
            return
        self._stop_event.clear()
        self._set_status(_at("status_starting_spin", self._lang))
        self._spin_start_btn.configure(state="disabled")
        self._spin_stop_btn.configure(state="normal")
        self._spin_log.clear()

        def _spin_safe():
            log_cb = self._spin_log.log
            lang = self._cfg.get('lang', 'en')
            try:
                import time as _t
                log_cb(_at('startup_switch_to_game', lang))
                for i in range(3, 0, -1):
                    if self._stop_event.is_set(): return
                    log_cb(_at('startup_countdown', lang, i=i))
                    self._set_status(_at('startup_countdown', lang, i=i))
                    _t.sleep(1)
                if self._stop_event.is_set(): return
                import config as _cfg_mod
                from wheelspin import run as spin_run
                try:
                    max_loops = int(self._spin_count_var.get())
                except ValueError:
                    max_loops = 0
                spin_run(
                    cfg=_cfg_mod.load(),
                    stop_event=self._stop_event,
                    log_cb=log_cb,
                    status_cb=self._set_status,
                    max_loops=max_loops,
                    section_cb=self._spin_log.log_section,
                )
            except Exception as e:
                import traceback
                log_cb(f'ERROR: {e}')
                log_cb(traceback.format_exc())
                self._set_status(f'Error: {e}')

        self._auto_thread = threading.Thread(
            target=_spin_safe, daemon=True)
        self._auto_thread.start()
        self._poll_thread()

    def _poll_example_queue(self):
        """Poll capture.py example queue and manage CTkToplevel on main thread."""
        try:
            from capture import _example_queue
            while True:
                action, key, img_path = _example_queue.get_nowait()
                if action == 'show' and img_path:
                    self._show_example_win(key, img_path)
                elif action == 'close':
                    self._close_example_win()
        except Exception:
            pass
        self.after(100, self._poll_example_queue)

    def _show_example_win(self, key, img_path):
        """Open a CTkToplevel showing the example image, scaled to fit
        the user's screen so it doesn't overflow on small displays."""
        self._close_example_win()   # close any existing
        try:
            from PIL import Image as _PIL
            import customtkinter as _ctk

            img = _PIL.open(img_path)
            ow, oh = img.size

            # Constrain to ~80% of the screen, preserving aspect ratio.
            # CTk multiplies CTkImage sizes AND CTkToplevel geometry by the UI
            # scaling factor, so divide the screen budget by it — otherwise the
            # example renders ~scale× oversized on high-DPI / scaled setups.
            CAPTION_RESERVED = 80   # scaled units
            S = getattr(self, '_ui_scale', 1.0) or 1.0
            max_w = int(self.winfo_screenwidth()  * 0.80 / S)
            max_h = int(self.winfo_screenheight() * 0.80 / S) - CAPTION_RESERVED
            scale = min(max_w / ow, max_h / oh, 1.0)
            w = max(1, int(ow * scale))
            h = max(1, int(oh * scale))
            # Pass the ORIGINAL image to CTkImage at the target size — CTk
            # renders it at size×scale from the source (crisp), so no pre-resize.

            win = _ctk.CTkToplevel(self)
            win.title(f'Example: {key}')
            win.geometry(f'{w}x{h + CAPTION_RESERVED}')
            win.resizable(False, False)
            win.after(200, lambda: win.attributes('-topmost', False))

            # Closing the example window cancels the capture session
            def _on_example_close():
                self._close_example_win()
                active = getattr(self, '_active_setup_panel', None)
                if active and hasattr(active, '_stop_session'):
                    active._stop_session()

            win.protocol('WM_DELETE_WINDOW', _on_example_close)

            ctk_img = _ctk.CTkImage(light_image=img, dark_image=img,
                                    size=(w, h))
            _ctk.CTkLabel(win, image=ctk_img, text='').pack()
            _ctk.CTkLabel(
                win,
                text=_at('capture_instruction', self._lang),
                font=('Segoe UI', 16, 'bold'),
                text_color=self._t("warn"),
                wraplength=max(200, w - 20),
                justify='center'
            ).pack(pady=10)
            theme.apply_font_family_to_tree(win)
            self._example_win = win
        except Exception as e:
            print(f'Example window error: {e}')

    def _close_example_win(self):
        """Close the example window if open."""
        if self._example_win is not None:
            try:
                self._example_win.destroy()
            except Exception:
                pass
            self._example_win = None

    def _is_game_focused(self) -> bool:
        """Check if Forza Horizon 6 is the active foreground window."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return "Forza Horizon 6" in buf.value
        except Exception:
            return True   # assume focused if check fails

    def _toggle_auto(self):
        """Toggle key: start if stopped, stop if running."""
        if self._auto_thread and self._auto_thread.is_alive():
            self._stop_auto()
        else:
            if self._current_tab == 'full_auto':
                self._start_full_auto()
            elif self._current_tab == 'race':
                self._start_race()
            elif self._current_tab == 'mastery':
                self._start_mastery()
            elif self._current_tab == 'buy':
                self._start_buy()
            elif self._current_tab == 'spin':
                self._start_spin()
            else:
                self._start_delete()

    def _start_full_auto(self):
        if self._auto_thread and self._auto_thread.is_alive():
            return
        # F9 can reach here even when the Start button is disabled — refuse and
        # tell the user which preconditions are unmet.
        if not self._fa_checklist_ok():
            self._set_status(_at("status_fa_checklist", self._lang))
            self._full_auto_log.log(_at("log_fa_checklist_block", self._lang))
            return
        # Paywall gate (fast, cache-based — no network). Unlicensed/expired →
        # refuse and send the user to Settings to enter/activate a key.
        import license_client
        if not license_client.is_allowed():
            self._set_status(_at("status_license_required", self._lang))
            self._full_auto_log.log(_at("log_license_required", self._lang))
            self._open_settings()
            return
        self._stop_event.clear()
        self._set_status(_at("status_starting_full_auto", self._lang))
        self._full_auto_start_btn.configure(state="disabled")
        self._full_auto_stop_btn.configure(state="normal")
        self._full_auto_log.clear()

        def _fa_safe():
            log_cb = self._full_auto_log.log
            lang = self._cfg.get('lang', 'en')
            try:
                import time as _t
                log_cb(_at('startup_switch_to_game', lang))
                for i in range(3, 0, -1):
                    if self._stop_event.is_set(): return
                    log_cb(_at('startup_countdown', lang, i=i))
                    self._set_status(_at('startup_countdown', lang, i=i))
                    _t.sleep(1)
                if self._stop_event.is_set(): return
                import config as _cfg_mod
                from full_auto import run as fa_run
                try:
                    race_count = int(self._full_auto_count_var.get())
                except ValueError:
                    race_count = 0
                branch = self._cfg.get('full_auto_branch_mode', 'racing')
                start_from = self._cfg.get('full_auto_start_from', 'race')
                grind_type = self._cfg.get('full_auto_grind_type', 'wheelspin')
                # car_count is AUTO (read from tech points before each buy), so we
                # don't pass it — run() uses its default as the initial fallback.
                fa_run(
                    cfg=_cfg_mod.load(),
                    stop_event=self._stop_event,
                    log_cb=log_cb,
                    status_cb=self._set_status,
                    race_count=race_count,
                    branch_mode=branch,
                    start_from=start_from,
                    grind_type=grind_type,
                    section_cb=self._full_auto_log.log_section,
                )
            except Exception as e:
                import traceback
                log_cb(f'ERROR: {e}')
                log_cb(traceback.format_exc())
                self._set_status(f'Error: {e}')

        self._auto_thread = threading.Thread(target=_fa_safe, daemon=True)
        self._auto_thread.start()
        self._poll_thread()

    def _stop_auto(self):
        self._stop_event.set()
        self._set_status(_at("status_stopping", self._lang))

    def _poll_thread(self):
        """Check if automation thread has finished and re-enable buttons."""
        if self._auto_thread and self._auto_thread.is_alive():
            self.after(300, self._poll_thread)
        else:
            # Re-register the toggle hotkey (automation threads may have
            # cleared keyboard hooks internally — always restore it here)
            try:
                import keyboard
                keyboard.remove_hotkey(self._toggle_key)
            except Exception:
                pass
            try:
                import keyboard
                keyboard.add_hotkey(self._toggle_key, self._toggle_auto)
            except Exception:
                pass
            self._race_start_btn.configure(state="normal")
            self._race_stop_btn.configure(state="disabled")
            self._mastery_start_btn.configure(state="normal")
            self._mastery_stop_btn.configure(state="disabled")
            self._buy_start_btn.configure(state="normal")
            self._buy_stop_btn.configure(state="disabled")
            self._delete_stop_btn.configure(state="disabled")
            self._update_delete_start_enabled()   # respect the confirm gate
            self._spin_start_btn.configure(state="normal")
            self._spin_stop_btn.configure(state="disabled")
            self._full_auto_stop_btn.configure(state="disabled")
            # Re-enable Start only if the checklist is still satisfied.
            self._update_fa_start_enabled()

    # ── Helpers ───────────────────────────────────────────────

    def _log(self, msg: str):
        if hasattr(self, '_active_log'):
            self._active_log.log(msg)

    def report_callback_exception(self, exc, val, tb):
        """Tk calls this for exceptions raised inside event/after callbacks —
        which sys.excepthook does NOT see. Log them (the default just prints to
        stderr, a void in a --windowed build) so a mid-mainloop crash is
        captured, then keep running."""
        import traceback as _tb
        msg = ''.join(_tb.format_exception(exc, val, tb))
        try:
            self._diag('CALLBACK EXC:\n' + msg)
        except Exception:
            pass
        try:
            import config as _c, time as _t
            with open(os.path.join(_c.BASE_DIR, 'fafe_crash.log'),
                      'a', encoding='utf-8') as f:
                f.write(_t.strftime('%H:%M:%S CALLBACK EXC\n') + msg + '\n')
        except Exception:
            pass

    def _diag(self, msg: str):
        """Append a line to a persistent diagnostics file next to the exe.
        Survives the bounded/trimmed UI log and works in a --windowed build
        (where stderr is a void) — used to diagnose device-specific issues like
        the overlay/updater not appearing on handhelds."""
        try:
            import config as _c, time as _t
            with open(os.path.join(_c.BASE_DIR, 'fafe_diag.log'),
                      'a', encoding='utf-8') as f:
                f.write(f"{_t.strftime('%H:%M:%S')} {msg}\n")
        except Exception:
            pass

    def _diag_init(self):
        """Truncate + seed the diagnostics file with version/env/monitors."""
        try:
            import config as _c, time as _t
            with open(os.path.join(_c.BASE_DIR, 'fafe_diag.log'),
                      'w', encoding='utf-8') as f:
                f.write(f"FAFE diag v{VERSION} {_t.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"lang={self._lang} ui_scale={getattr(self,'_ui_scale',None)} "
                        f"overlay_enabled={self._cfg.get('overlay_enabled')} "
                        f"monitor_index={self._cfg.get('monitor_index')}\n")
        except Exception:
            pass
        try:
            from capture import list_monitors
            self._diag(f"monitors={list_monitors()}")
        except Exception as e:
            self._diag(f"list_monitors error: {e!r}")

    def _set_status(self, msg: str):
        self.after(0, lambda: self._status_var.set(f"  {msg}"))

    @staticmethod
    def _vk_for_keyname(keyname: str):
        """Resolve a key name (e.g. 'f9', 'enter', 'a') to its Windows
        virtual-key code, or None if it can't be resolved."""
        name = (keyname or '').strip().lower()
        if name.startswith('f') and name[1:].isdigit():
            n = int(name[1:])
            if 1 <= n <= 24:
                return 0x70 + (n - 1)            # VK_F1..VK_F24
        if len(name) == 1:
            return ord(name.upper())             # letters / digits
        return {'enter': 0x0D, 'return': 0x0D, 'escape': 0x1B, 'esc': 0x1B,
                'space': 0x20, 'tab': 0x09}.get(name)

    def _is_stopkey_crossfire(self) -> bool:
        """True if THIS hotkey callback is almost certainly a cross-fire from the
        stop/toggle key, not a genuine press of its own key.

        Why: while the race holds W (~33 injected keydowns/sec), the `keyboard`
        library's global hook can mis-dispatch the F9 STOP press to the wrong
        handler — e.g. fire the F12 bug-report when F9 was the key actually
        pressed. The reliable tell is that the stop/toggle key is physically DOWN
        at that instant, so we check THAT — NOT "is my own key still down". The
        old self-check was racy: the hotkey callback runs just after the key
        event, so a normal quick F12 tap is already released by the time we'd
        check, and it wrongly rejected genuine presses (F12 did nothing at all).

        Fails CLOSED (returns False = not a cross-fire) on any error / unresolved
        toggle key, so a genuine press is NEVER blocked by a resolver gap."""
        try:
            import ctypes
            vk = self._vk_for_keyname(self._toggle_key)
            if vk is None:
                return False
            return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return False

    def _trigger_report(self):
        """Hotkey handler: build a bug-report bundle in the background."""
        if self._is_stopkey_crossfire():
            return   # F9 stop mis-dispatched here during the race W-hold flood
        if getattr(self, '_report_in_progress', False):
            return
        self._report_in_progress = True
        # Snapshot each tab's log on the UI side (copy = safe to read off-thread)
        logs = {}
        for label, attr in [('Full Auto', '_full_auto_log'),
                            ('Race Auto', '_race_log'),
                            ('Auto Unlock 22B', '_mastery_log'),
                            ('Auto Buy', '_buy_log'),
                            ('Auto Spin Wheel', '_spin_log'),
                            ('Delete Used Cars', '_delete_log')]:
            w = getattr(self, attr, None)
            if w is not None:
                logs[label] = list(getattr(w, '_lines', []))

        def _run():
            try:
                import report
                report.generate_report(
                    self._cfg, self._cfg.get('monitor_index', 1), logs,
                    log_cb=self._log, status_cb=self._set_status)
            except Exception as e:
                self._log(f'Report error: {e}')
            finally:
                self._report_in_progress = False

        threading.Thread(target=_run, daemon=True).start()

    def _set_overlay_enabled(self, enabled):
        """Single source of truth for the overlay on/off state. Keeps the
        settings switch + topbar indicator in sync; _refresh_overlay handles
        actual show/hide on its next tick."""
        enabled = bool(enabled)
        self._cfg['overlay_enabled'] = enabled
        save(self._cfg)
        if hasattr(self, '_overlay_var') and bool(self._overlay_var.get()) != enabled:
            self._overlay_var.set(enabled)
        self._update_overlay_indicator()

    def _update_overlay_indicator(self):
        btn = getattr(self, '_overlay_indicator', None)
        if btn is None:
            return
        on = bool(self._cfg.get('overlay_enabled', False))
        btn.configure(
            text=("● " if on else "○ ") + _at('overlay_indicator', self._lang),
            text_color=(self._t("status_dot") if on else self._t("text_muted")))

    def _on_overlay_toggle(self):
        self._set_overlay_enabled(self._overlay_var.get())

    def _on_mute_toggle(self):
        """Persist the 'mute game while running' setting (applied at run start)."""
        self._cfg['mute_game'] = bool(self._mute_var.get())
        save(self._cfg)

    def _on_ocr_toggle(self):
        """Persist OCR on/off (applied at run start). Off = lighter, pixel-only
        detection that won't spike CPU / stutter the game."""
        self._cfg['detector_enable_ocr'] = bool(self._ocr_var.get())
        save(self._cfg)

    def _on_debug_toggle(self):
        """Persist debug-snapshot mode. Picked up at the next run start (each run
        builds a fresh detector from fresh config), so it takes effect WITHOUT an
        app restart. On = annotated detection PNGs written to debug/<key>.png."""
        self._cfg['debug_detection'] = bool(self._debug_var.get())
        save(self._cfg)

    # ── Full Auto license (paywall) ─────────────────────────
    def _build_license_section(self, parent):
        """Settings → Full Auto license: status, key field, Activate/Deactivate,
        and a Buy link. Network calls run on daemon threads (never block the UI)."""
        import license_client
        self._license_status_lbl = ctk.CTkLabel(
            parent, text="", anchor='w', font=("Arial", 12))
        self._license_status_lbl.pack(fill='x', padx=12, pady=(2, 4))

        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=12, pady=4)
        self._license_key_var = ctk.StringVar(value="")
        ctk.CTkEntry(row, textvariable=self._license_key_var, width=240,
                     placeholder_text=_at('license_key_placeholder', self._lang)
                     ).pack(side='left')
        ctk.CTkButton(row, text=_at('license_activate_btn', self._lang), width=90,
                      command=self._on_activate_license).pack(side='left', padx=6)
        ctk.CTkButton(row, text=_at('license_deactivate_btn', self._lang), width=90,
                      fg_color='transparent', border_width=1,
                      border_color=self._t("border"), text_color=self._t("text"),
                      hover_color=self._t("surface_alt"),
                      command=self._on_deactivate_license).pack(side='left')

        if license_client.STORE_URL:
            ctk.CTkButton(
                parent, text=_at('license_buy_btn', self._lang), width=160,
                command=lambda: __import__("webbrowser").open(license_client.STORE_URL)
            ).pack(anchor='w', padx=12, pady=(4, 2))

        # Machine id (helps support match a key to a seat)
        ctk.CTkLabel(parent,
                     text=_at('license_machine_id', self._lang,
                              id=license_client.machine_id()[:18]),
                     font=("Arial", 10), text_color=self._t("text_muted"),
                     anchor='w').pack(fill='x', padx=12, pady=(0, 2))
        self._refresh_license_status()

    def _refresh_license_status(self):
        import license_client
        st = license_client.status()
        state = st["state"]
        ok = state == "licensed"
        txt = _at('license_status_' + state, self._lang)
        if st.get("key"):
            txt += f"  ({st['key']})"
        try:
            self._license_status_lbl.configure(
                text=txt,
                text_color=("#3fbf6f" if ok else self._t("text_muted")))
        except Exception:
            pass

    def _on_activate_license(self):
        key = self._license_key_var.get().strip()
        if not key:
            return
        self._license_status_lbl.configure(
            text=_at('license_activating', self._lang),
            text_color=self._t("text_muted"))
        def _work():
            import license_client
            license_client.activate(key)
            self.after(0, self._refresh_license_status)
        threading.Thread(target=_work, daemon=True).start()

    def _on_deactivate_license(self):
        def _work():
            import license_client
            license_client.deactivate()
            self.after(0, self._refresh_license_status)
        threading.Thread(target=_work, daemon=True).start()

    def _on_overlay_move(self, x, y):
        """Persist the overlay position after the user drags it."""
        self._cfg['overlay_x'] = int(x)
        self._cfg['overlay_y'] = int(y)
        self._overlay_pos = (int(x), int(y))
        save(self._cfg)
        self._update_overlay_mask()   # re-blank at the new position immediately

    def _update_overlay_mask(self):
        """Tell the capture layer the overlay's current screen rect so it's
        blanked from detection frames (the overlay must never be self-detected)."""
        try:
            import capture as _cap
            if self._overlay is None:
                _cap.clear_overlay_mask()
                return
            b = self._overlay.bounds()
            if b:
                _cap.set_overlay_mask(*b)
        except Exception:
            pass

    def _toggle_overlay(self):
        """Overlay-toggle hotkey (default F10). Runs on the keyboard thread, so
        marshal the actual state change onto the main thread."""
        if self._is_stopkey_crossfire():
            return   # F9 stop mis-dispatched here during the race W-hold flood
        new = not self._cfg.get('overlay_enabled', False)
        self.after(0, lambda: self._set_overlay_enabled(new))

    def _refresh_overlay(self):
        """Show/refresh the floating game overlay whenever it's enabled (via the
        settings switch or the F10 toggle); hide it otherwise. Polled ~2x/sec."""
        try:
            enabled = self._cfg.get('overlay_enabled', False)
            if enabled:
                if self._overlay is None:
                    import overlay as _ov
                    tabs = [
                        ('race',    _at('ov_func_race',    self._lang)),
                        ('mastery', _at('ov_func_mastery', self._lang)),
                        ('buy',     _at('ov_func_buy',     self._lang)),
                        ('delete',  _at('ov_func_delete',  self._lang)),
                        ('spin',    _at('ov_func_spin',    self._lang)),
                    ]
                    self._overlay = _ov.GameOverlay(
                        self, on_move=self._on_overlay_move,
                        icon_path=self._icon_path(),
                        tabs=tabs, on_tab=self._switch_tab)
                    self._diag("overlay: GameOverlay created OK")
                if self._overlay_pos is None:
                    sx, sy = self._cfg.get('overlay_x'), self._cfg.get('overlay_y')
                    if sx is not None and sy is not None:
                        self._overlay_pos = (sx, sy)   # user-dragged position
                    else:
                        import overlay as _ov2
                        from capture import get_monitor_dims
                        w, h, left, top = get_monitor_dims(
                            self._cfg.get('monitor_index', 1))
                        # Default to the TOP-RIGHT corner: clear of the detection
                        # ROIs (racing top-left, restart bottom-left, confirm
                        # centre, start left) so the overlay self-mask (which
                        # blanks the overlay's rect from detection frames) doesn't
                        # blank a needed UI element. User can drag it anywhere.
                        self._overlay_pos = (left + w - _ov2._WIDTH - 24, top + 24)
                lines = []
                log = getattr(self, '_active_log', None)
                if log is not None:
                    lines = list(getattr(log, '_lines', []))[-5:]
                running = (self._auto_thread is not None
                           and self._auto_thread.is_alive())
                k = self._cfg.get('toggle_key', 'f9').upper()
                hint = _at('overlay_hint_stop' if running
                           else 'overlay_hint_start', self._lang, key=k)
                self._overlay.update(self._status_var.get(), lines, hint)
                self._overlay.set_current_tab(self._current_tab)
                self._overlay.show(*self._overlay_pos)
                # Register the overlay's live rect so the detector blanks it out
                # of captured frames (never self-detect). Re-read each poll so a
                # drag is picked up within ~500ms.
                self._update_overlay_mask()
                # One-time durable diagnostic: requested position vs. the actual
                # mapped window geometry, so we can tell off-screen vs. not-shown
                # vs. compositor-hidden on devices where it doesn't appear.
                if not getattr(self, '_overlay_diag_done', False):
                    self._overlay_diag_done = True
                    try:
                        win = self._overlay._win
                        self._diag(
                            f"overlay shown: requested_pos={self._overlay_pos} "
                            f"bounds={self._overlay.bounds()} "
                            f"mapped={win.winfo_ismapped()} "
                            f"viewable={win.winfo_viewable()} "
                            f"override={win.overrideredirect()}")
                    except Exception as de:
                        self._diag(f"overlay show-diag error: {de!r}")
            else:
                self._overlay_pos = None
                if self._overlay is not None:
                    self._overlay.hide()
                import capture as _cap
                _cap.clear_overlay_mask()
        except Exception as e:
            # Surface once so overlay problems aren't invisible.
            if not getattr(self, '_overlay_err_logged', False):
                self._overlay_err_logged = True
                try:
                    self._log(f'Overlay error: {e!r}')
                except Exception:
                    pass
                import traceback
                self._diag("overlay EXC:\n" + traceback.format_exc())
                traceback.print_exc()
        self.after(500, self._refresh_overlay)

    def _build_key_bindings(self, parent):
        """Add toggle key and capture key binding rows to a settings frame."""
        for cfg_key, label_key in [
            ('toggle_key',  'setting_toggle_key'),
            ('capture_key', 'setting_capture_key'),
            ('report_key',  'setting_report_key'),
            ('overlay_key', 'setting_overlay_key'),
        ]:
            row = ctk.CTkFrame(parent, fg_color='transparent')
            row.pack(fill='x', padx=12, pady=4)
            ctk.CTkLabel(row,
                         text=_at(label_key, self._lang),
                         width=190, anchor='w').pack(side='left')
            btn = ctk.CTkButton(
                row,
                text=self._cfg.get(cfg_key, 'f9').upper(),
                width=120,
                command=lambda k=cfg_key, b=None: self._start_key_bind(k))
            btn.pack(side='left', padx=8)
            # Store button ref for updating text
            setattr(self, f'_keybtn_{cfg_key}', btn)

    def _start_key_bind(self, cfg_key):
        """Start listening for a key press to rebind."""
        if self._binding_key is not None:
            return   # already binding
        self._binding_key = cfg_key
        btn = getattr(self, f'_keybtn_{cfg_key}', None)
        if btn:
            btn.configure(text=_at('shortcut_press_any_key', self._lang),
                          fg_color='#d97706')
        import keyboard
        keyboard.hook(self._on_key_bind_press)

    def _on_key_bind_press(self, event):
        """Called when a key is pressed during rebind."""
        if event.event_type != 'down':
            return
        import keyboard
        keyboard.unhook(self._on_key_bind_press)
        key_name = event.name.lower()
        cfg_key  = self._binding_key
        self._binding_key = None
        if key_name == 'escape':
            # Cancelled
            btn = getattr(self, f'_keybtn_{cfg_key}', None)
            if btn:
                btn.configure(
                    text=self._cfg.get(cfg_key, '').upper(),
                    fg_color=('gray75', 'gray25'))
            return
        # Save new key
        self._cfg[cfg_key] = key_name
        save(self._cfg)
        if cfg_key == 'toggle_key':
            self._toggle_key = key_name
            self._update_shortcut_hints()
        elif cfg_key == 'capture_key':
            self._capture_key = key_name
        elif cfg_key == 'report_key':
            import keyboard as _kb
            try:
                _kb.remove_hotkey(self._report_key)
            except Exception:
                pass
            self._report_key = key_name
            try:
                _kb.add_hotkey(key_name, self._trigger_report)
            except Exception:
                pass
        elif cfg_key == 'overlay_key':
            import keyboard as _kb
            try:
                _kb.remove_hotkey(self._overlay_key)
            except Exception:
                pass
            self._overlay_key = key_name
            try:
                _kb.add_hotkey(key_name, self._toggle_overlay)
            except Exception:
                pass
        btn = getattr(self, f'_keybtn_{cfg_key}', None)
        if btn:
            self.after(0, lambda: btn.configure(
                text=key_name.upper(),
                fg_color=('gray75', 'gray25')))

    def _update_shortcut_hints(self):
        """Refresh shortcut hint labels after key change."""
        txt = _at('shortcut_toggle', self._lang, key=self._toggle_key.upper())
        for lbl in [getattr(self, '_race_shortcut_lbl', None),
                    getattr(self, '_mastery_shortcut_lbl', None)]:
            if lbl:
                self.after(0, lambda l=lbl, t=txt: l.configure(text=t))

    def _open_settings(self):
        """Show settings in the main column (sidebar stays visible)."""
        if not hasattr(self, '_settings_frame'):
            self._build_settings_panel()
            self._apply_ui_fonts()
        self._show_main(self._settings_frame)
        self._in_settings = True
        self._in_support = False
        self._set_nav_active("settings")
        self._page_title_var.set(_at("settings_window_title", self._lang))

    def _close_settings(self):
        """Return from settings to the previously-active tab."""
        self._switch_tab(self._current_tab or "race")

    # ── Resource / image helpers ──────────────────────────────

    def _resource_path(self, *parts):
        """Locate a bundled resource in dev and frozen (--onedir) layouts."""
        bases = []
        if (getattr(sys, "frozen", False) or "__compiled__" in globals()):
            mp = getattr(sys, "_MEIPASS", None)
            if mp:
                bases.append(mp)
            bases.append(os.path.dirname(sys.executable))
        bases.append(os.path.dirname(os.path.abspath(__file__)))
        for b in bases:
            p = os.path.join(b, *parts)
            if os.path.exists(p):
                return p
        return None

    def _load_ctk_image(self, *parts, size):
        """Return a CTkImage for a bundled asset, or None if missing/unreadable.

        `size` (keyword-only) is treated as a bounding box: the image is fit
        inside it preserving aspect ratio, so non-square logos/QRs aren't
        squished. Callers pass the path parts then size=(w, h).
        """
        path = self._resource_path(*parts)
        if not path:
            return None
        try:
            from PIL import Image
            img = Image.open(path)
            iw, ih = img.size
            bw, bh = size
            if iw and ih:
                scale = min(bw / iw, bh / ih)
                size = (max(1, round(iw * scale)), max(1, round(ih * scale)))
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception:
            return None

    # ── Support panel (inline, like settings) ─────────────────

    def _open_support(self):
        """Show the Support Me panel in the main column (sidebar stays)."""
        if not hasattr(self, "_support_frame"):
            self._build_support_panel()
            self._apply_ui_fonts()
        self._show_main(self._support_frame)
        self._in_support = True
        self._in_settings = False
        self._set_nav_active(None)
        self._page_title_var.set(_at("support_btn", self._lang))

    def _close_support(self):
        """Return from the support panel to the previously-active tab."""
        self._switch_tab(self._current_tab or "race")

    def _build_support_panel(self):
        """Build the inline Support Me panel once. Two ways to support: a
        clickable 街口支付 (JKOPAY) logo (opens a transfer link — the old QR
        expired) and a PayPal button sized to match it."""
        QR = 260   # QR display size; the PayPal button matches this width
        self._support_frame = ctk.CTkFrame(self._main_content, fg_color="transparent")

        header = ctk.CTkFrame(self._support_frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkButton(
            header, text="← " + _at("settings_back", self._lang),
            width=90, command=self._close_support,
            fg_color="transparent", border_width=1,
            border_color=self._t("border"), text_color=self._t("text"),
            hover_color=self._t("surface_alt")).pack(side="left")

        body = ctk.CTkScrollableFrame(self._support_frame, fg_color=self._t("surface"))
        body.pack(fill="both", expand=True, padx=12, pady=8)

        ctk.CTkLabel(body, text=_at("support_btn", self._lang),
                     font=theme.H2_FONT).pack(pady=(4, 2))
        ctk.CTkLabel(body, text=_at("support_thanks", self._lang),
                     font=theme.BODY_FONT, text_color=self._t("text_muted"),
                     wraplength=320, justify="center").pack(pady=(0, 14))

        # ── 街口支付 (JKOPAY) — clickable logo opening a transfer link ──
        # (Replaces the old QR image, which expired.) The whole logo is a button.
        JKO_URL = "https://service.jkopay.com/r/transfer?j=Transfer:906639236"
        _open_jko = lambda: __import__("webbrowser").open(JKO_URL)
        ctk.CTkLabel(body, text=_at("support_jkopay", self._lang),
                     font=theme.LABEL_FONT).pack(pady=(0, 4))
        # Fit the (landscape) logo inside a QR×QR box → renders QR px wide,
        # aspect preserved, matching the PayPal button width.
        jko_img = self._load_ctk_image("assets", "support_jkopay.png", size=(QR, QR))
        if jko_img:
            self._support_jko_img = jko_img   # keep a ref so it isn't GC'd
            ctk.CTkButton(
                body, image=jko_img, text="", width=QR,
                fg_color="transparent", hover_color=self._t("surface_alt"),
                command=_open_jko).pack(pady=(0, 14))
        else:
            ctk.CTkButton(
                body, text="JKOPAY", width=QR, height=46,
                font=("Segoe UI", 14, "bold"),
                fg_color=self._t("support_fill"), hover_color=self._t("support_hover"),
                text_color=self._t("support_text"),
                command=_open_jko).pack(pady=(0, 14))

        # ── PayPal (button sized to match the QR width) ──
        pp_img = self._load_ctk_image("assets", "paypal_logo.png", size=(20, 20))
        self._support_pp_img = pp_img
        ctk.CTkButton(
            body, text=" PayPal", image=pp_img, compound="left",
            width=QR, height=46, font=("Segoe UI", 14, "bold"),
            fg_color=self._t("support_fill"), hover_color=self._t("support_hover"), text_color=self._t("support_text"),
            command=lambda: __import__("webbrowser").open(
                "https://paypal.me/Leonbacon")).pack(pady=(0, 8))

    # ── Report-a-bug help panel (inline tutorial, like support) ──

    def _open_report_help(self):
        if not hasattr(self, "_report_help_frame"):
            self._build_report_help_panel()
            self._apply_ui_fonts()
        self._show_main(self._report_help_frame)
        self._in_report_help = True
        self._in_settings = False
        self._in_support = False
        self._set_nav_active(None)
        self._page_title_var.set(_at("report_help_btn", self._lang))

    def _close_report_help(self):
        """Return from the report-help panel to the previously-active tab."""
        self._switch_tab(self._current_tab or "race")

    def _build_report_help_panel(self):
        """Inline tutorial explaining the F12 bug-report flow. (A capture
        button can't work — clicking it foregrounds FAFE; the hotkey is pressed
        while the game is in focus. So this teaches the hotkey instead.)"""
        self._report_help_frame = ctk.CTkFrame(self._main_content, fg_color="transparent")
        header = ctk.CTkFrame(self._report_help_frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkButton(
            header, text="← " + _at("settings_back", self._lang),
            width=90, command=self._close_report_help,
            fg_color="transparent", border_width=1,
            border_color=self._t("border"), text_color=self._t("text"),
            hover_color=self._t("surface_alt")).pack(side="left")

        body = ctk.CTkScrollableFrame(self._report_help_frame, fg_color=self._t("surface"))
        body.pack(fill="both", expand=True, padx=16, pady=8)

        ctk.CTkLabel(body, text=_at("report_help_title", self._lang),
                     font=theme.H2_FONT).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(body, text=_at("report_help_intro", self._lang),
                     font=theme.BODY_FONT, justify="left",
                     wraplength=560).pack(anchor="w", pady=(0, 12))

        key = self._cfg.get("report_key", "f12").upper()
        steps = [
            _at("report_help_step1", self._lang),
            _at("report_help_step2", self._lang),
            _at("report_help_step3", self._lang, key=key),
            _at("report_help_step4", self._lang),
            _at("report_help_step5", self._lang),
        ]
        for i, s in enumerate(steps, 1):
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=str(i), width=26, height=26,
                         fg_color=("gray75", "gray30"), corner_radius=13,
                         font=theme.BUTTON_FONT).pack(side="left", padx=(0, 10))
            ctk.CTkLabel(row, text=s, font=theme.BODY_FONT, justify="left",
                         wraplength=510, anchor="w").pack(
                             side="left", fill="x", expand=True)

        ctk.CTkLabel(body, text=_at("report_privacy", self._lang),
                     font=theme.HINT_FONT, text_color=self._t("text_muted"),
                     justify="left", wraplength=560).pack(anchor="w", pady=(14, 10))

        di = self._load_ctk_image("assets", "discord_logo.png", size=(18, 18))
        self._report_help_discord_img = di
        ctk.CTkButton(
            body, text=" " + _at("report_help_discord", self._lang),
            image=di, compound="left", width=200, height=40,
            fg_color="#5865F2", hover_color="#4752c4", text_color="#ffffff",
            command=lambda: __import__("webbrowser").open(
                "https://discord.com/invite/MNg2g9Pp6K")).pack(anchor="w", pady=(0, 8))

    def _build_settings_panel(self):
        """Build the inline settings panel once."""
        self._settings_frame = ctk.CTkFrame(self._main_content, fg_color='transparent')

        # Header with back button
        header = ctk.CTkFrame(self._settings_frame, fg_color='transparent')
        header.pack(fill='x', padx=8, pady=(6, 0))
        ctk.CTkButton(
            header, text='← ' + _at('settings_back', self._lang),
            width=90, height=28,
            fg_color='transparent',
            border_width=1,
            border_color=self._t("border"), text_color=self._t("text"),
            hover_color=self._t("surface_alt"),
            font=('Segoe UI', 12),
            command=self._close_settings
        ).pack(side='left')
        ctk.CTkLabel(
            header,
            text=_at('settings_window_title', self._lang),
            font=('Segoe UI', 14, 'bold')
        ).pack(side='left', padx=12)

        scroll = ctk.CTkScrollableFrame(self._settings_frame, fg_color=self._t("surface"))
        scroll.pack(fill='both', expand=True, padx=12, pady=8)

        def section(label_key):
            ctk.CTkLabel(scroll,
                         text=_at(label_key, self._lang),
                         font=('Segoe UI', 13, 'bold'),
                         anchor='w').pack(fill='x', pady=(12, 4))
            ctk.CTkFrame(scroll, height=1,
                         fg_color=self._t("border")).pack(fill='x')

        # ── Appearance ────────────────────────────────────
        section('settings_appearance_section')
        # Theme preset (full color scheme). Replaces the old light/dark switch
        # and accent-colour picker. Changing it restarts the app — CTk can't
        # restyle every widget live (same as the language switch).
        _app_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _app_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_app_row, text=_at('label_theme_preset', self._lang),
                     width=160, anchor='w').pack(side='left')
        self._preset_labels = dict(theme.THEME_PRESET_LABELS)   # key -> label
        _cur_preset = self._cfg.get('theme_preset', 'default')
        if _cur_preset not in self._preset_labels:
            _cur_preset = 'default'
        self._preset_var = ctk.StringVar(value=self._preset_labels[_cur_preset])
        self._preset_menu = ctk.CTkOptionMenu(
            _app_row, variable=self._preset_var,
            values=list(self._preset_labels.values()),
            command=self._on_preset_change,
            width=200)
        self._preset_menu.pack(side='left', padx=8)

        _lang_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _lang_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_lang_row, text=_at('label_language', self._lang),
                     width=160, anchor='w').pack(side='left')
        _lang_map = {'en': 'English', 'zh-tw': '繁體中文'}
        self._lang_var = ctk.StringVar(
            value=_lang_map.get(self._cfg.get('lang', 'en'), 'English'))
        self._lang_menu = ctk.CTkOptionMenu(
            _lang_row, variable=self._lang_var,
            values=list(_lang_map.values()),
            command=self._on_lang_change,
            width=160)
        self._lang_menu.pack(side='left', padx=8)

        # Game-menu language (which template set to use). Separate from the app
        # UI language; defaults to "auto" (follow it).
        _glang_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _glang_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_glang_row, text=_at('setting_game_lang', self._lang),
                     width=160, anchor='w').pack(side='left')
        # display label -> stored template_lang value
        self._glang_opts = {
            _at('game_lang_auto', self._lang): 'auto',
            '繁體中文': 'cht', 'English': 'en',
        }
        _glang_rev = {v: k for k, v in self._glang_opts.items()}
        self._glang_var = ctk.StringVar(
            value=_glang_rev.get(self._cfg.get('template_lang', 'auto'),
                                 list(self._glang_opts)[0]))
        self._glang_menu = ctk.CTkOptionMenu(
            _glang_row, variable=self._glang_var,
            values=list(self._glang_opts.keys()),
            command=self._on_game_lang_change,
            width=160)
        self._glang_menu.pack(side='left', padx=8)

        # UI scale
        _scale_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _scale_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_scale_row, text=_at('label_ui_scale', self._lang),
                     width=160, anchor='w').pack(side='left')
        _auto_lbl = _at('scale_auto', self._lang)
        _cur_scale = str(self._cfg.get('ui_scale', 'auto'))
        self._scale_var = ctk.StringVar(
            value=_auto_lbl if _cur_scale.lower() == 'auto' else _cur_scale)
        ctk.CTkOptionMenu(
            _scale_row, variable=self._scale_var,
            values=[_auto_lbl, '100%', '125%', '150%', '175%', '200%', '250%'],
            command=self._on_scale_change,
            width=160).pack(side='left', padx=8)

        # Game overlay toggle
        _ov_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _ov_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_ov_row, text=_at('setting_overlay', self._lang),
                     width=160, anchor='w').pack(side='left')
        self._overlay_var = ctk.BooleanVar(
            value=bool(self._cfg.get('overlay_enabled', False)))
        ctk.CTkSwitch(_ov_row, text='', variable=self._overlay_var,
                      command=self._on_overlay_toggle).pack(side='left', padx=8)

        # ── System ────────────────────────────────────────
        section('settings_system_section')
        # Mute the game while a run is active (per-app, leaves other apps alone)
        _mute_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _mute_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_mute_row, text=_at('setting_mute', self._lang),
                     width=160, anchor='w').pack(side='left')
        self._mute_var = ctk.BooleanVar(
            value=bool(self._cfg.get('mute_game', False)))
        ctk.CTkSwitch(_mute_row, text='', variable=self._mute_var,
                      command=self._on_mute_toggle).pack(side='left', padx=8)

        # OCR detection toggle — onnxruntime OCR is CPU-heavy and can stutter
        # the game; turn off for pixel-only (lighter) detection.
        _ocr_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _ocr_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_ocr_row, text=_at('setting_ocr', self._lang),
                     width=160, anchor='w').pack(side='left')
        self._ocr_var = ctk.BooleanVar(
            value=bool(self._cfg.get('detector_enable_ocr', False)))
        ctk.CTkSwitch(_ocr_row, text='', variable=self._ocr_var,
                      command=self._on_ocr_toggle).pack(side='left', padx=8)
        ctk.CTkLabel(_ocr_row, text=_at('setting_ocr_hint', self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side='left')

        # Debug-snapshot toggle — write annotated detection PNGs to debug/<key>.png
        # for diagnosing mis-detections. Applies at the next run start (no restart).
        _dbg_row = ctk.CTkFrame(scroll, fg_color='transparent')
        _dbg_row.pack(fill='x', padx=12, pady=4)
        ctk.CTkLabel(_dbg_row, text=_at('setting_debug', self._lang),
                     width=160, anchor='w').pack(side='left')
        self._debug_var = ctk.BooleanVar(
            value=bool(self._cfg.get('debug_detection', False)))
        ctk.CTkSwitch(_dbg_row, text='', variable=self._debug_var,
                      command=self._on_debug_toggle).pack(side='left', padx=8)
        ctk.CTkLabel(_dbg_row, text=_at('setting_debug_hint', self._lang),
                     font=("Arial", 11),
                     text_color=self._t("text_muted")).pack(side='left')

        # ── Full Auto license ─────────────────────────────
        section('settings_license_section')
        self._build_license_section(scroll)

        # ── Shortcuts ─────────────────────────────────────
        section('settings_shortcuts_section')
        self._build_key_bindings(scroll)

        # ── Race settings ─────────────────────────────────
        section('settings_race_section')
        self._build_settings_fields(
            scroll,
            fields=[
                (_at('setting_race_check_interval', self._lang), 'race_check_interval', 0.1, 2.0, 0.1, 'tip_race_check_interval'),
                (_at('setting_race_post_key_wait',  self._lang), 'race_post_key_wait',  0.75, 3.0, 0.05, 'tip_race_post_key_wait'),
            ])

        # ── Mastery settings ──────────────────────────────
        section('settings_mastery_section')
        self._build_settings_fields(
            scroll,
            fields=[
                (_at('setting_mastery_cutscene_wait', self._lang), 'mastery_cutscene_wait', 11.0, 25.0, 0.5, 'tip_mastery_cutscene_wait'),
                (_at('setting_mastery_grid_unlock_wait', self._lang), 'mastery_grid_unlock_wait', 1.0, 2.0, 0.25, 'tip_mastery_grid_unlock_wait'),
                (_at('setting_menu_tap_wait', self._lang), 'menu_tap_wait', 0.1, 0.5, 0.05, 'tip_menu_tap_wait'),
            ])

        section('settings_buy_section')
        self._build_settings_fields(
            scroll,
            fields=[
                (_at('setting_buy_post_key_wait', self._lang), 'buy_post_key_wait', 0.4, 3.0, 0.1, 'tip_buy_post_key_wait'),
            ])

        section('settings_delete_section')
        self._build_settings_fields(
            scroll,
            fields=[
                (_at('setting_delete_post_key_wait', self._lang), 'delete_post_key_wait', 0.2, 3.0, 0.1, 'tip_delete_post_key_wait'),
            ])

        section('settings_wheelspin_section')
        self._build_settings_fields(
            scroll,
            fields=[
                (_at('setting_wheelspin_post_key_wait', self._lang), 'wheelspin_post_key_wait', 0.4, 3.0, 0.1, 'tip_wheelspin_post_key_wait'),
            ])

    def _on_monitor_change(self, val: str):
        try:
            self._cfg['monitor_index'] = int(val.split('—')[0].strip())
        except Exception:
            self._cfg['monitor_index'] = 1
        save(self._cfg)
        # Push the new monitor index to EVERY setup panel so template/ROI
        # captures use the freshly-selected monitor without a relaunch — not
        # just race/mastery (buy, spin and full_auto were being left stale).
        for attr in ('_race_setup', '_mastery_setup', '_buy_setup',
                     '_spin_setup', '_full_auto_setup'):
            panel = getattr(self, attr, None)
            if panel is not None and hasattr(panel, '_monitor_index'):
                panel._monitor_index = self._cfg['monitor_index']

    def _on_setting_change(self, key: str, var):
        self._cfg[key] = round(var.get(), 4)
        save(self._cfg)

    def _on_mastery_block_change(self, first_row, middle_cols, last_row):
        self._cfg["mastery_block_first_row"]  = int(first_row)
        self._cfg["mastery_block_middle_cols"] = int(middle_cols)
        self._cfg["mastery_block_last_row"]   = int(last_row)
        save(self._cfg)

    def _make_mastery_setup(self, parent) -> MasteryGridWidget:
        """Mastery is keyboard-driven and walks the tree with WASD, so the only
        config is the unlock-path grid (no templates, no node-click capture)."""
        return MasteryGridWidget(
            parent,
            grid_file=get_mastery_grid_file(self._tpl_lang),
            lang=self._lang,
            fg_color=self._t("surface_alt"),
            border_width=1, border_color=self._t("border"),
            corner_radius=self._t("corner"),
        )

    def _on_preset_change(self, val: str):
        """Theme preset changed — persist and restart (CTk can't restyle live)."""
        if self._restarting:
            return
        rev = {v: k for k, v in self._preset_labels.items()}
        new = rev.get(val, 'default')
        if new == self._cfg.get('theme_preset', 'default'):
            return
        self._restarting = True
        if hasattr(self, '_preset_menu'):
            self._preset_menu.configure(state="disabled")
        self._cfg['theme_preset'] = new
        save(self._cfg)
        self._restart_app()

    def _on_scale_change(self, val: str):
        # Map the localized "Auto" label back to the stored "auto" sentinel.
        stored = 'auto' if val == _at('scale_auto', self._lang) else val
        self._cfg["ui_scale"] = stored
        save(self._cfg)
        scale = config.resolve_ui_scale(self._cfg)
        ctk.set_widget_scaling(scale)
        ctk.set_window_scaling(scale)
        self._ui_scale = scale
        # Re-apply the base geometry so the window resizes to fit the new
        # scale (set_window_scaling multiplies it). Otherwise scaling up can
        # clip content inside the old window size.
        self.geometry("900x650")

    # ── Accent picker (always-visible swatch grid) ────────────

    def _ask_first_run_language(self):
        """First-launch modal: choose the UI language. Returns 'en'/'zh-tw'.

        Built with PLAIN Tk (not CTk): CTk multiplies CTkToplevel.geometry() by
        the widget-scaling factor, which on multi-monitor / high-DPI setups put
        the dialog off-screen (it rendered but the user never saw it). Plain Tk
        geometry is real pixels, so centering is reliable. Uses the locked CJK
        font so all three labels render."""
        import tkinter as tk
        result = {'lang': 'en'}
        fam = theme.UI_FAMILY
        BG, FG, ACC, ACC2 = "#1b1b1b", "#f0f0f0", "#3B82F6", "#2563EB"
        win = tk.Toplevel(self)
        win.title("Language  /  語言")
        win.configure(bg=BG)
        win.resizable(False, False)
        try:
            win.attributes('-topmost', True)
        except Exception:
            pass

        W, H = 400, 300
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{W}x{H}+{max(0, (sw - W) // 2)}+{max(0, (sh - H) // 2)}")

        tk.Label(win, text="Choose your language\n選擇您的語言",
                 bg=BG, fg=FG, font=(fam, 15, 'bold'),
                 justify='center').pack(pady=(30, 20))

        def pick(code):
            result['lang'] = code
            try:
                win.grab_release()
            except Exception:
                pass
            # Defer the destroy: tearing the window down synchronously from
            # inside the button's own click handler raises in Tk's event
            # dispatch, and in a frozen --windowed build (sys.stderr is None)
            # the default error handler then crashes the app while trying to
            # print the traceback. after_idle runs it once the click is done.
            win.after_idle(win.destroy)

        for code, label in (('en', 'English'),
                            ('zh-tw', '繁體中文')):
            tk.Button(win, text=label, font=(fam, 13), width=18,
                      bg=ACC, fg="#ffffff", activebackground=ACC2,
                      activeforeground="#ffffff", relief='flat', bd=0,
                      cursor='hand2',
                      command=lambda c=code: pick(c)).pack(pady=7, ipady=7)

        win.protocol("WM_DELETE_WINDOW", lambda: pick('en'))
        win.update_idletasks()
        win.lift()
        try:
            win.focus_force()
            win.grab_set()       # modal
        except Exception:
            pass
        self.wait_window(win)
        return result['lang']

    def _on_lang_change(self, val: str):
        if self._restarting:
            return   # already restarting, ignore
        lang_map = {"English": "en", "繁體中文": "zh-tw"}
        new_lang = lang_map.get(val, "en")
        if new_lang == self._cfg.get("lang", "en"):
            return   # no change
        self._restarting = True
        # Disable immediately to prevent double-trigger
        if hasattr(self, '_lang_menu'):
            self._lang_menu.configure(state="disabled")
        self._cfg["lang"] = new_lang
        self._lang = new_lang
        save(self._cfg)
        self._restart_app()

    def _on_game_lang_change(self, val: str):
        """Change which game-menu template set is used. Restarts the app so the
        Setup panels rebuild against the new language's template folders (the
        automation itself reads the value fresh at each run regardless)."""
        if self._restarting:
            return
        new = self._glang_opts.get(val, 'auto')
        if new == self._cfg.get('template_lang', 'auto'):
            return
        self._restarting = True
        if hasattr(self, '_glang_menu'):
            self._glang_menu.configure(state="disabled")
        self._cfg['template_lang'] = new
        save(self._cfg)
        self._restart_app()

    def _restart_app(self):
        """Save config, relaunch the app, close this instance."""
        if not self._restarting:
            return
        import subprocess
        import os
        cwd = os.path.dirname(sys.executable) if (getattr(sys, 'frozen', False) or "__compiled__" in globals()) \
              else os.path.dirname(os.path.abspath(sys.argv[0]))
        if (getattr(sys, 'frozen', False) or "__compiled__" in globals()):
            subprocess.Popen([sys.executable], cwd=cwd)
        else:
            subprocess.Popen([sys.executable] + sys.argv, cwd=cwd)
        self.after(200, self.destroy)  # slight delay so config flush completes

    def _on_close(self):
        self._stop_event.set()
        self.destroy()
