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


class MasteryCarBlockWidget(ctk.CTkFrame):
    """Visual picker for the contiguous block of garage cars to unlock in
    STANDALONE mastery. The My Cars grid fills column-major, TOP→BOTTOM. The
    user marks the FIRST car's row (column 0) and the LAST car's row (final
    column), plus how many FULL columns sit between. Total cars =
    (ROWS - first_row + 1) + middle*ROWS + last_row. Reports (first_row,
    middle_cols, last_row) via on_change. Minimum 2 columns (first + last)."""

    ROWS = 3

    def __init__(self, parent, first_row: int = 1, middle_cols: int = 0,
                 last_row: int = 3, on_change=None, lang: str = "en",
                 title_key: str = "carblock_title",
                 hint_key: str = "carblock_hint", **kwargs):
        super().__init__(parent, **kwargs)
        self._lang = lang
        self._title_key = title_key
        self._hint_key = hint_key
        self._on_change = on_change or (lambda *a: None)
        self._first_row = max(1, min(self.ROWS, int(first_row)))
        self._last_row  = max(1, min(self.ROWS, int(last_row)))
        self._middle    = max(0, int(middle_cols))
        self._first_btns = {}
        self._last_btns  = {}
        self._build()

    def _col_picker(self, parent, label_key, btns, handler):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(col, text=_at(label_key, self._lang),
                     font=("Arial", 11)).pack()
        for r in range(1, self.ROWS + 1):
            b = ctk.CTkButton(
                col, text="", width=44, height=38, corner_radius=8,
                font=("Arial", 14, "bold"),
                command=lambda rr=r: handler(rr),
                fg_color=theme.token("surface"),
                hover_color=theme.token("surface_alt"),
                border_width=1, border_color=theme.token("border"))
            b.pack(pady=3)
            btns[r] = b
        ctk.CTkLabel(col, text="↓", font=("Arial", 13),
                     text_color=("gray50", "gray55")).pack()
        return col

    def _build(self):
        ctk.CTkLabel(self, text=_at(self._title_key, self._lang), anchor="w",
                     font=("Arial", 13, "bold"),
                     text_color=theme.token("text")).pack(fill="x", padx=12,
                                                          pady=(10, 2))
        ctk.CTkLabel(self, text=_at(self._hint_key, self._lang), anchor="w",
                     justify="left", wraplength=460, font=("Arial", 11),
                     text_color=("gray50", "gray55")).pack(fill="x", padx=12,
                                                           pady=(0, 8))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=12, pady=2)

        self._col_picker(row, "carblock_first", self._first_btns,
                         self._set_first).pack(side="left", padx=(0, 16))

        mid = ctk.CTkFrame(row, fg_color="transparent")
        mid.pack(side="left", padx=16)
        ctk.CTkLabel(mid, text=_at("carblock_middle", self._lang),
                     font=("Arial", 11)).pack()
        self._mid_var = ctk.StringVar(value=str(self._middle))
        ctk.CTkEntry(mid, textvariable=self._mid_var, width=56,
                     justify="center").pack(pady=8)
        self._mid_var.trace_add("write", lambda *a: self._on_mid())

        self._col_picker(row, "carblock_last", self._last_btns,
                         self._set_last).pack(side="left", padx=(16, 0))

        self._total_lbl = ctk.CTkLabel(self, text="", font=("Arial", 12, "bold"),
                                       text_color=theme.token("text"))
        self._total_lbl.pack(pady=(8, 12))
        self._refresh()

    @staticmethod
    def count(first_row: int, middle: int, last_row: int) -> int:
        """Cars in a column-major block: the FIRST car sits in the first column
        at first_row and the column fills DOWN to the bottom; then `middle` FULL
        columns; then the LAST column fills from the top down to last_row.
        middle=0 → first & last are ADJACENT columns. e.g. first=col1 row3,
        last=col2 row1, middle=0 → (3-3+1) + 0 + 1 = 2 cars."""
        ROWS = MasteryCarBlockWidget.ROWS
        return (ROWS - first_row + 1) + middle * ROWS + last_row

    def total(self) -> int:
        return self.count(self._first_row, self._middle, self._last_row)

    def _set_first(self, r):
        self._first_row = r
        self._emit()

    def _set_last(self, r):
        self._last_row = r
        self._emit()

    def _on_mid(self):
        v = self._mid_var.get().strip()
        try:
            self._middle = max(0, int(v)) if v else 0
        except ValueError:
            return                       # ignore partial / invalid input
        self._emit()

    def _emit(self):
        self._on_change(self._first_row, self._middle, self._last_row)
        self._refresh()

    def _refresh(self):
        # First column: rows at/below first_row are in the block (fills down).
        for r, b in self._first_btns.items():
            self._paint(b, sel=(r == self._first_row), inblk=(r >= self._first_row))
        # Last column: rows at/above last_row are in the block (fills from top).
        for r, b in self._last_btns.items():
            self._paint(b, sel=(r == self._last_row), inblk=(r <= self._last_row))
        self._total_lbl.configure(
            text=_at("carblock_total", self._lang, n=self.total()))

    @staticmethod
    def _paint(b, sel, inblk):
        if sel:
            b.configure(text="●", fg_color=theme.token("accent"),
                        text_color=theme.token("accent_text"))
        elif inblk:
            b.configure(text="·", fg_color=theme.token("surface_alt"),
                        text_color=theme.token("text_muted"))
        else:
            b.configure(text="", fg_color=theme.token("surface"),
                        text_color=theme.token("text_muted"))
