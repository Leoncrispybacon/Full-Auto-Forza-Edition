# ============================================================
#  grid_widget.py — interactive 4x4 mastery-tree node picker
#  Click cells in unlock order; each gets a sequence number. The
#  bottom-left cell is the fixed cursor START. Saves an ordered
#  [row, col] list (capture.save_grid) that mastery.py walks with
#  WASD + Enter — no mouse clicks, so it's background-safe.
# ============================================================

import customtkinter as ctk

import theme
from app_lang import t as _at
from capture import load_grid, save_grid

ROWS, COLS = 4, 4
START = (ROWS - 1, 0)   # bottom-left — where the in-game tree cursor starts


class MasteryGridWidget(ctk.CTkFrame):
    """A 4x4 grid of circular cells. Click in unlock order (each cell shows its
    1-based step); click the LAST-added cell again to undo it. The path is saved
    to `grid_file` as an ordered [row, col] list."""

    def __init__(self, parent, grid_file: str, lang: str = "en", **kwargs):
        super().__init__(parent, **kwargs)
        self._grid_file = grid_file
        self._lang = lang
        self._order = load_grid(grid_file)        # list of (row, col)
        self._buttons = {}                        # (r, c) -> CTkButton
        self._build()

    # ── public ────────────────────────────────────────────────
    def set_grid_file(self, grid_file: str):
        """Point at a different spec (e.g. on language change) and reload."""
        self._grid_file = grid_file
        self._order = load_grid(grid_file)
        self._refresh()

    # ── build ─────────────────────────────────────────────────
    DOT_OK, DOT_MISSING = "#22c55e", "#ef4444"

    def _build(self):
        self._collapsed = True

        # Collapsible header (always visible): toggle + status dot.
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 0))
        self._toggle_btn = ctk.CTkButton(
            hdr, text="", command=self._toggle_panel,
            fg_color="transparent", text_color=theme.token("text"),
            hover_color=theme.token("surface"), anchor="w",
            font=("Arial", 13, "bold"))
        self._toggle_btn.pack(side="left", fill="x", expand=True)
        self._dot = ctk.CTkLabel(hdr, text="●", width=20, font=("Arial", 14))
        self._dot.pack(side="right", padx=8)

        # Collapsible content.
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self._content, text=_at("grid_hint", self._lang),
                     anchor="w", justify="left", wraplength=460,
                     font=("Arial", 11),
                     text_color=("gray50", "gray55")).pack(fill="x", padx=12,
                                                           pady=(2, 8))
        board = ctk.CTkFrame(self._content, fg_color="transparent")
        board.pack(padx=12, pady=2)
        for r in range(ROWS):
            for c in range(COLS):
                b = ctk.CTkButton(
                    board, text="", width=48, height=48, corner_radius=24,
                    font=("Arial", 15, "bold"),
                    command=lambda rr=r, cc=c: self._toggle(rr, cc),
                    fg_color=theme.token("surface"),
                    hover_color=theme.token("surface_alt"),
                    text_color=theme.token("text_muted"),
                    border_width=1, border_color=theme.token("border"))
                b.grid(row=r, column=c, padx=6, pady=6)
                self._buttons[(r, c)] = b
        ctk.CTkButton(self._content, text=_at("grid_clear", self._lang),
                      command=self._clear, width=120,
                      fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER,
                      text_color=theme.token("stop_text")).pack(padx=12,
                                                                pady=(6, 12))
        # Start collapsed — content not packed until toggled.
        self._refresh()

    def _header_text(self):
        chev = "▸" if self._collapsed else "▾"   # ▸ / ▾
        return f"{chev}  {_at('grid_title', self._lang)}  ·  {len(self._order)}"

    def _toggle_panel(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._content.pack_forget()
        else:
            self._content.pack(fill="x", padx=4, pady=(0, 4))
        self._toggle_btn.configure(text=self._header_text())

    # ── interaction ───────────────────────────────────────────
    def _toggle(self, r, c):
        cell = (r, c)
        if cell in self._order:
            # Only the last-added cell can be removed, so the remaining sequence
            # stays a valid ordered path (matches the mockup behaviour).
            if self._order[-1] == cell:
                self._order.pop()
        else:
            self._order.append(cell)
        save_grid(self._grid_file, self._order)
        self._refresh()

    def _clear(self):
        self._order = []
        save_grid(self._grid_file, self._order)
        self._refresh()

    def _refresh(self):
        for (r, c), b in self._buttons.items():
            if (r, c) in self._order:
                n = self._order.index((r, c)) + 1
                b.configure(text=str(n), fg_color=theme.token("accent"),
                            text_color=theme.token("accent_text"))
            else:
                b.configure(
                    text="S" if (r, c) == START else "",
                    fg_color=theme.token("surface"),
                    text_color=theme.token("text_muted"))
        # Header label (with live count) + status dot (green once a path is set).
        self._toggle_btn.configure(text=self._header_text())
        self._dot.configure(
            text_color=self.DOT_OK if self._order else self.DOT_MISSING)
