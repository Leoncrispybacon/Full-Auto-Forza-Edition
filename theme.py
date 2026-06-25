# ============================================================
#  theme.py — Central design tokens for FAFE.
#
#  Single source of truth for fonts, spacing, semantic colors,
#  icons, and accent presets.  Import from here instead of
#  hardcoding font/color/padding values throughout the app.
# ============================================================


# ── Typography ────────────────────────────────────────────────
# The UI font family is LOCKED per language at startup by init_fonts() so the
# app always renders in a fixed, known-good face. Why this matters: "Segoe UI"
# (and CustomTkinter's default "Roboto") have no CJK glyphs, so when drawing
# Chinese text Windows falls back via its font-linking registry — and on some
# machines that fallback resolves to a decorative/brush font, making the whole
# UI look wrong (this was a real user report). Naming a CJK-capable Windows
# font explicitly (Microsoft JhengHei for 繁中) bypasses that fallback
# entirely. English keeps Segoe UI.
#
# All callers reference these as `theme.X_FONT` (attribute access, never a
# by-value `from theme import X_FONT`), so reassigning them in init_fonts()
# before the UI is built propagates the family everywhere.

UI_FAMILY = "Segoe UI"   # resolved/overwritten by init_fonts()

TITLE_FONT  = (UI_FAMILY, 20, "bold")    # App title
H2_FONT     = (UI_FAMILY, 16, "bold")    # Section headers
BODY_FONT   = (UI_FAMILY, 13, "normal")  # Descriptions / paragraph text
LABEL_FONT  = (UI_FAMILY, 12, "normal")  # Setting labels
HINT_FONT   = (UI_FAMILY, 11, "normal")  # Captions / sub-text
BUTTON_FONT = (UI_FAMILY, 13, "bold")    # Primary action buttons
VALUE_FONT  = (UI_FAMILY, 11, "normal")  # Slider value readouts
ICON_FONT   = (UI_FAMILY, 16, "normal")  # ⚙ etc. — chunky icon

# Preferred families per UI language. All ship with Windows 8+/10/11, so one
# of these is always present; the list ends in a deterministic fallback.
_FAMILY_BY_LANG = {
    "zh-tw": ["Microsoft JhengHei UI", "Microsoft JhengHei", "PMingLiU", "Segoe UI"],
    "en":    ["Segoe UI"],
}


def _first_installed(candidates):
    """First font family in `candidates` that's actually installed; else the
    last candidate (deterministic). Needs a Tk root to query tkfont.families()."""
    try:
        import tkinter.font as tkfont
        available = {f.lower() for f in tkfont.families()}
        for fam in candidates:
            if fam.lower() in available:
                return fam
    except Exception:
        pass
    return candidates[-1] if candidates else "Segoe UI"


def init_fonts(lang="en", root=None):
    """Lock the UI font family for `lang` and rebuild every font token + the
    CustomTkinter/Tk defaults so the whole app renders in a fixed face,
    independent of the user's system font-linking. Call once after the Tk root
    exists and before building widgets. Idempotent."""
    global UI_FAMILY, TITLE_FONT, H2_FONT, BODY_FONT, LABEL_FONT, \
        HINT_FONT, BUTTON_FONT, VALUE_FONT, ICON_FONT

    UI_FAMILY = _first_installed(_FAMILY_BY_LANG.get(lang, ["Segoe UI"]))

    TITLE_FONT  = (UI_FAMILY, 20, "bold")
    H2_FONT     = (UI_FAMILY, 16, "bold")
    BODY_FONT   = (UI_FAMILY, 13, "normal")
    LABEL_FONT  = (UI_FAMILY, 12, "normal")
    HINT_FONT   = (UI_FAMILY, 11, "normal")
    BUTTON_FONT = (UI_FAMILY, 13, "bold")
    VALUE_FONT  = (UI_FAMILY, 11, "normal")
    ICON_FONT   = (UI_FAMILY, 16, "normal")

    # CTk widgets given no explicit font fall back to this default family
    # (out of the box "Roboto" — no CJK glyphs). Point it at our family.
    try:
        import customtkinter as ctk
        ctk.ThemeManager.theme["CTkFont"]["family"] = UI_FAMILY
    except Exception:
        pass

    # Plain-Tk named fonts (menus, default text). Leave TkFixedFont alone so
    # anything that wants monospace still gets it.
    if root is not None:
        try:
            import tkinter.font as tkfont
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                         "TkHeadingFont", "TkTooltipFont"):
                try:
                    tkfont.nametofont(name).configure(family=UI_FAMILY)
                except Exception:
                    pass
        except Exception:
            pass
    return UI_FAMILY


# ── Spacing (base unit: 8 px) ─────────────────────────────────

PAD_TIGHT   = 4   # Cramped — only when two things must hug
PAD_INLINE  = 8   # Default between inline widgets
PAD_SECTION = 12  # Within a logical section
PAD_LARGE   = 16  # Between sections
PAD_MAJOR   = 24  # Top-level panel padding


# ── Semantic colors (Modern muted palette) ────────────────────

START_FG    = "#10B981"  # Emerald 500
START_HOVER = "#059669"  # Emerald 600
STOP_FG     = "#EF4444"  # Red 500
STOP_HOVER  = "#DC2626"  # Red 600

# Status text colors
STATUS_RUNNING = "#10B981"
STATUS_WARN    = "#F59E0B"
STATUS_IDLE    = ("gray50", "gray60")


# ── Icons (always followed by a double space for breathing room) ──

ICON_START = "▶  "
ICON_STOP  = "■  "
ICON_BACK  = "←  "


# ── Accent presets (user-pickable in Settings → Appearance) ───
# (display_name -> (fg, hover))

ACCENT_PRESETS: dict[str, tuple[str, str]] = {
    "Blue":    ("#3B82F6", "#2563EB"),
    "Indigo":  ("#6366F1", "#4F46E5"),
    "Purple":  ("#8B5CF6", "#7C3AED"),
    "Teal":    ("#14B8A6", "#0D9488"),
    "Emerald": ("#10B981", "#059669"),
    "Amber":   ("#F59E0B", "#D97706"),
    "Rose":    ("#F43F5E", "#E11D48"),
    "Slate":   ("#64748B", "#475569"),
}
DEFAULT_ACCENT_NAME = "Blue"


def get_accent(cfg: dict | None = None) -> tuple[str, str, str]:
    """Returns (name, fg, hover) for the current accent.

    The accent now comes from the active THEME PRESET (set via apply_preset);
    the old per-user accent-colour picker was replaced by theme presets. Falls
    back to the default preset's accent before a preset has been applied."""
    if _ACTIVE_THEME is not None:
        return ("preset", _ACTIVE_THEME["accent"], _ACTIVE_THEME["accent_hover"])
    d = THEME_PRESETS[DEFAULT_PRESET]
    return ("default", d["accent"], d["accent_hover"])


def slider_kwargs(cfg: dict) -> dict:
    """Accent kwargs to apply to a CTkSlider."""
    _, fg, hover = get_accent(cfg)
    return {
        "button_color":       fg,
        "button_hover_color": hover,
        "progress_color":     fg,
    }


def segbtn_kwargs(cfg: dict) -> dict:
    """Accent kwargs to apply to a CTkSegmentedButton."""
    _, fg, hover = get_accent(cfg)
    return {
        "selected_color":       fg,
        "selected_hover_color": hover,
    }


def switch_kwargs(cfg: dict) -> dict:
    """Accent kwargs to apply to a CTkSwitch."""
    _, fg, _ = get_accent(cfg)
    return {"progress_color": fg}


def apply_accent_to_tree(root, cfg: dict) -> None:
    """Walk the widget tree from `root` and reconfigure every slider,
    segmented button, and switch to use the current accent color.

    Lets accent picks take effect immediately without an app restart —
    widgets bind to their fg/hover/etc. at construction time, so anything
    already on screen needs to be explicitly reconfigured.
    """
    import customtkinter as ctk  # local import to keep theme.py importable
                                  # in headless contexts

    sk = slider_kwargs(cfg)
    bk = segbtn_kwargs(cfg)
    wk = switch_kwargs(cfg)

    def walk(w):
        try:
            if isinstance(w, ctk.CTkSlider):
                w.configure(**sk)
            elif isinstance(w, ctk.CTkSegmentedButton):
                w.configure(**bk)
            elif isinstance(w, ctk.CTkSwitch):
                w.configure(**wk)
        except Exception:
            # Defensive: a widget might not accept one of these kwargs
            # (e.g. CTk version skew). Skip it rather than crashing.
            pass
        try:
            for child in w.winfo_children():
                walk(child)
        except Exception:
            pass

    walk(root)


# ══════════════════════════════════════════════════════════════
#  Theme presets (full color schemes, picked in Settings → Appearance)
# ══════════════════════════════════════════════════════════════
# Each preset is a flat dict of design tokens. Colors are single dark-only hex
# strings (CTk also accepts (light,dark) tuples, but our presets are dark). The
# font_* tokens are NOT stored here — get_theme() injects them from the locked,
# CJK-safe font tokens above, so fonts stay correct per UI language regardless
# of preset. corner/corner_sm are ints (corner radius in px).
#
# "default" reproduces the current look (so existing users see no change) and is
# the only preset that leaves CustomTkinter's own appearance/colors untouched.
# Other presets override the CTk ThemeManager defaults (see apply_preset) so the
# whole surface palette changes, not just the few explicitly-tokened widgets.
#
# NOTE: bundling custom TTF fonts for fancier presets is a LATER task — for now
# every preset uses the locked Windows family (Segoe UI / JhengHei / YaHei).

THEME_TOKENS = [
    "bg", "surface", "surface_alt", "sidebar_bg", "border",
    "accent", "accent_hover", "accent_text",
    "text", "text_muted",
    "start", "start_hover", "start_text",   # Start button (distinct green)
    "stop", "stop_hover", "stop_text",
    "warn", "log_text", "log_accent", "status_dot",
    "support_fill", "support_hover", "support_text",
    "corner", "corner_sm",
]

THEME_PRESETS: dict[str, dict] = {
    # FAFE design system (dark navy-blue). Tokens from DESIGN.md / the Full Auto
    # design handoff. Start is now the ACCENT blue (primary action), not green —
    # green is reserved for the status dot. Applied app-wide (apply_preset pushes
    # these into CTk's ThemeManager for every preset, default included).
    "default": {
        "bg":           "#0A0E14",   # app background (darkest)
        "surface":      "#121A28",   # cards / panels
        "surface_alt":  "#161E28",   # elevated controls (entries, dropdowns, log)
        "sidebar_bg":   "#0D131E",   # left nav (subtly raised from bg)
        "border":       "#243044",
        "accent":       "#2563EB",
        "accent_hover": "#1D4FD7",
        "accent_text":  "#ffffff",
        "text":         "#F4F8FD",
        "text_muted":   "#82A0B2",   # secondary text (deeper #5f7488 used inline)
        "start":        "#2563EB",   # primary action = accent (per the design)
        "start_hover":  "#1D4FD7",
        "start_text":   "#ffffff",
        "stop":         "#DC2626",
        "stop_hover":   "#B91C1C",
        "stop_text":    "#ffffff",
        "warn":         "#FF7A7A",
        "log_text":     "#cdd9e5",
        "log_accent":   "#7DB2FF",
        "status_dot":   "#22C55E",
        "support_fill": "#2563EB",   # Support Me = filled accent
        "support_hover": "#1D4FD7",
        "support_text": "#ffffff",
        "corner":       8,
        "corner_sm":    6,
    },
    # Showcase — dark navy/purple with a cyan accent and rounder corners.
    "midnight_neon": {
        "bg":           "#0f1020",
        "surface":      "#1a1b2e",
        "surface_alt":  "#23244a",
        "sidebar_bg":   "#141527",
        "border":       "#2d2f55",
        "accent":       "#22d3ee",
        "accent_hover": "#06b6d4",
        "accent_text":  "#06121a",
        "text":         "#e6e8ff",
        "text_muted":   "#8b8fc7",
        "start":        "#34d399",
        "start_hover":  "#10b981",
        "start_text":   "#06121a",
        "stop":         "#f43f5e",
        "stop_hover":   "#e11d48",
        "stop_text":    "#ffffff",
        "warn":         "#fb7185",
        "log_text":     "#cdd0f5",
        "log_accent":   "#22d3ee",
        "status_dot":   "#34d399",
        "support_fill": "#8b5cf6",
        "support_hover": "#7c3aed",
        "support_text": "#ffffff",
        "corner":       12,
        "corner_sm":    6,
    },
}

DEFAULT_PRESET = "default"

# Display names for the Settings dropdown (preset key -> label). Kept ASCII so
# they read the same in every language; could be localized later if wanted.
THEME_PRESET_LABELS = {
    "default":       "Default (Blue)",
    "midnight_neon": "Midnight Neon",
}

# The active resolved theme dict (set by apply_preset). Accent helpers read
# their accent from here so sliders/segmented buttons/switches match the preset.
_ACTIVE_THEME: dict | None = None


def list_themes() -> list[str]:
    """Preset keys, for the settings dropdown."""
    return list(THEME_PRESETS.keys())


def token(key: str, default=None):
    """Read a single token from the ACTIVE preset (set by apply_preset). Lets
    modules without a MainWindow handle (e.g. setup_panel) read theme colors.
    Falls back to the default preset, then `default`."""
    t = _ACTIVE_THEME if _ACTIVE_THEME is not None else get_theme(DEFAULT_PRESET)
    return t.get(key, default)


def get_theme(name: str) -> dict:
    """Resolve a preset name to its full token dict (falls back to default).
    Font tokens are injected from the locked, CJK-safe font tokens so they're
    always correct for the current UI language."""
    preset = THEME_PRESETS.get(name) or THEME_PRESETS[DEFAULT_PRESET]
    t = dict(preset)
    # Locked-family fonts (never hardcode a family — would break CJK rendering).
    t["font_title"]  = TITLE_FONT
    t["font_body"]   = BODY_FONT
    t["font_mono"]   = LABEL_FONT   # logs: keep the CJK-safe family, not Consolas
    t["font_button"] = BUTTON_FONT
    return t


def _apply_ctk_overrides(t: dict) -> None:
    """Push a preset's colors into CustomTkinter's ThemeManager so EXISTING
    widgets (transparent frames, default buttons, etc.) pick up the preset
    palette without per-widget edits. Only called for non-default presets;
    'default' leaves CTk's own defaults alone so it looks exactly as before."""
    import customtkinter as ctk
    th = ctk.ThemeManager.theme

    def setc(widget, key, value):
        try:
            th[widget][key] = [value, value]   # [light, dark]; we run dark
        except Exception:
            pass

    setc("CTk", "fg_color", t["bg"])
    for w in ("CTkToplevel",):
        setc(w, "fg_color", t["bg"])
    setc("CTkFrame", "fg_color", t["surface"])
    setc("CTkFrame", "top_fg_color", t["surface_alt"])
    setc("CTkFrame", "border_color", t["border"])
    setc("CTkButton", "fg_color", t["accent"])
    setc("CTkButton", "hover_color", t["accent_hover"])
    setc("CTkButton", "text_color", t["accent_text"])
    setc("CTkButton", "text_color_disabled", t["text_muted"])
    setc("CTkButton", "border_color", t["border"])
    setc("CTkLabel", "text_color", t["text"])
    for w in ("CTkEntry", "CTkOptionMenu", "CTkComboBox", "CTkTextbox"):
        setc(w, "fg_color", t["surface_alt"])
        setc(w, "text_color", t["text"])
        setc(w, "border_color", t["border"])
    setc("CTkOptionMenu", "button_color", t["accent"])
    setc("CTkOptionMenu", "button_hover_color", t["accent_hover"])
    setc("CTkComboBox", "button_color", t["accent"])
    setc("CTkComboBox", "button_hover_color", t["accent_hover"])
    setc("CTkScrollableFrame", "label_fg_color", t["surface_alt"])
    setc("CTkSegmentedButton", "fg_color", t["surface_alt"])
    setc("CTkSegmentedButton", "selected_color", t["accent"])
    setc("CTkSegmentedButton", "selected_hover_color", t["accent_hover"])
    setc("CTkSegmentedButton", "unselected_color", t["surface_alt"])
    setc("CTkSegmentedButton", "text_color", t["text"])
    setc("CTkSlider", "button_color", t["accent"])
    setc("CTkSlider", "button_hover_color", t["accent_hover"])
    setc("CTkSlider", "progress_color", t["accent"])
    setc("CTkSwitch", "progress_color", t["accent"])
    setc("CTkCheckBox", "fg_color", t["accent"])


def apply_preset(name: str, root=None) -> dict:
    """Activate a theme preset: stash the resolved tokens (so accent helpers use
    them) and, for non-default presets, push colors into CTk's ThemeManager.
    Presets are dark-only, so the appearance mode is forced to dark for them.
    'default' is left untouched (caller's existing light/dark handling stands).
    Returns the resolved token dict. Call BEFORE building widgets."""
    global _ACTIVE_THEME, START_FG, START_HOVER, STOP_FG, STOP_HOVER, \
        STATUS_RUNNING
    t = get_theme(name)
    _ACTIVE_THEME = t
    # Reassign the semantic color constants from the preset so every existing
    # `theme.START_FG` / `theme.STOP_FG` reference (attribute access) themes
    # automatically — same propagation trick init_fonts() uses for fonts.
    START_FG       = t["start"]
    START_HOVER    = t["start_hover"]
    STOP_FG        = t["stop"]
    STOP_HOVER     = t["stop_hover"]
    STATUS_RUNNING = t["status_dot"]
    # Push the palette into CustomTkinter's ThemeManager for EVERY preset
    # (default included) — the FAFE design is now the default look, so even the
    # un-tokened generic widgets must pick it up. The app is dark-only.
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
    except Exception:
        pass
    _apply_ctk_overrides(t)
    return t


def apply_font_family_to_tree(root, family: str | None = None) -> None:
    """Walk the widget tree from `root` and force every widget's font family to
    `family` (defaults to the locked UI_FAMILY), preserving size/weight/slant.

    Why this is needed on top of init_fonts(): lots of widgets are built with a
    hardcoded font tuple like ('Arial', 14) or ('Segoe UI', 11) instead of a
    theme.* token. Those families have NO CJK glyphs, so on a Chinese UI Windows
    substitutes a fallback — on some machines a decorative/brush font — and the
    widget (buttons, dropdowns, segmented buttons, some labels) renders wrong
    while theme.*-token widgets look fine. Rewriting every hardcoded tuple by
    hand is fragile and misses CTk internals (e.g. CTkOptionMenu's separate
    `dropdown_font`) and future additions; this single post-build pass fixes
    them all and is idempotent. Call after _build_ui and after building any
    on-demand panel.
    """
    import customtkinter as ctk

    fam = family or UI_FAMILY

    def _fix_attr(w, attr):
        try:
            f = w.cget(attr)
        except Exception:
            return  # widget doesn't have this option
        try:
            if isinstance(f, ctk.CTkFont):
                if f.cget("family") != fam:
                    f.configure(family=fam)
            elif isinstance(f, tuple) and len(f) >= 1:
                if f[0] != fam:
                    w.configure(**{attr: (fam,) + tuple(f[1:])})
            elif isinstance(f, str) and f and not f.startswith("Tk"):
                # A bare family string (rare). Named Tk fonts ("Tk…") are
                # handled by init_fonts() — don't disturb them.
                parts = f.split()
                if parts and parts[0] != fam:
                    w.configure(**{attr: (fam,) + tuple(parts[1:])})
        except Exception:
            pass

    def walk(w):
        _fix_attr(w, "font")
        _fix_attr(w, "dropdown_font")   # CTkOptionMenu / CTkComboBox popup
        try:
            for child in w.winfo_children():
                walk(child)
        except Exception:
            pass

    walk(root)
