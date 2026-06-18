# ============================================================
#  ui/setup_panel.py — Collapsible setup panel with
#  per-template capture buttons and status dots
# ============================================================

import customtkinter as ctk
import threading
from app_lang import t as _at
from capture import (CaptureSession, NodeSession,
                      save_template, save_nodes,
                      template_exists, nodes_exist,
                      list_monitors, show_example, close_example)
from config import (RESOLUTION_SETS, get_examples_dir,
                    get_race_templates, get_mastery_templates,
                    get_wheelspin_templates, get_buy_templates,
                    get_full_auto_templates, get_nodes_file)
import config
import theme


class TemplateRow(ctk.CTkFrame):
    """One row in the setup panel: label + status dot."""

    DOT_OK  = "#22c55e"   # green
    DOT_MISSING = "#ef4444"  # red

    def __init__(self, parent, label: str, folder_fn, key: str,
                 on_recapture=None, on_set_roi=None, main_cfg=None, lang='en',
                 **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.folder_fn = folder_fn
        self.key       = key
        self._main_cfg = main_cfg
        self._cfg_key  = f'thresh_{key}'

        # ── Top row: dot + label + recapture btn ──────────
        top = ctk.CTkFrame(self, fg_color='transparent')
        top.pack(fill='x')

        self._dot = ctk.CTkLabel(top, text='●', width=20,
                                  font=("Segoe UI", 14))
        self._dot.pack(side='left', padx=(0, theme.PAD_INLINE - 2))

        ctk.CTkLabel(top, text=label, font=theme.LABEL_FONT,
                     anchor='w').pack(side='left', fill='x', expand=True)

        if on_recapture:
            self._recapture_btn = ctk.CTkButton(
                top, text='↺', width=28,
                command=on_recapture,
                fg_color='transparent',
                hover_color=('gray80', 'gray30'),
                text_color=('gray40', 'gray70'),
                font=("Segoe UI", 14))
            self._recapture_btn.pack(side='right', padx=theme.PAD_TIGHT)

        # Optional "Detection area" button — set a custom search ROI separate
        # from the template's capture box (Full Auto only). The capture label
        # explains it on click.
        if on_set_roi:
            self._roi_btn = ctk.CTkButton(
                top, text='⊡', width=28,
                command=on_set_roi,
                fg_color='transparent',
                hover_color=('gray80', 'gray30'),
                text_color=('gray40', 'gray70'),
                font=("Segoe UI", 14))
            self._roi_btn.pack(side='right', padx=theme.PAD_TIGHT)

        # ── Bottom row: threshold slider ───────────────────
        thresh_row = ctk.CTkFrame(self, fg_color='transparent')
        thresh_row.pack(fill='x', padx=(26, theme.PAD_TIGHT),
                        pady=(2, theme.PAD_INLINE - 2))
        ctk.CTkLabel(thresh_row, text=_at('label_threshold', lang),
                     font=theme.HINT_FONT,
                     text_color=('gray50', 'gray55')).pack(side='left')
        init_val = 0.80
        if main_cfg:
            init_val = main_cfg.get(self._cfg_key, 0.80)
        # The slider minimum matches the hard match-floor (detector_min_threshold,
        # 0.70): a target below that has no effect, since detection applies
        # max(0.70, target × 0.92). Clamp a stale stored value into range.
        init_val = min(0.90, max(0.70, init_val))
        self._thresh_var = ctk.DoubleVar(value=init_val)
        _thresh_slider = ctk.CTkSlider(
            thresh_row,
            variable=self._thresh_var,
            from_=0.70, to=0.90,
            command=self._on_thresh_move,
            height=14,
            **theme.slider_kwargs(main_cfg or {}),
        )
        _thresh_slider.pack(side='left', fill='x', expand=True,
                            padx=theme.PAD_INLINE - 2)
        _thresh_slider.bind('<ButtonRelease-1>', self._on_thresh_release)
        self._thresh_lbl = ctk.CTkLabel(
            thresh_row, text=f'{init_val:.0%}',
            width=36, font=theme.VALUE_FONT,
            text_color=('gray50', 'gray55'))
        self._thresh_lbl.pack(side='left')

        self.refresh()

    def _on_thresh_move(self, val):
        """Update label while dragging — no save."""
        if hasattr(self, '_thresh_lbl'):
            self._thresh_lbl.configure(text=f'{float(val):.0%}')

    def _on_thresh_release(self, event=None):
        """Save on mouse release."""
        if self._main_cfg is not None:
            self._main_cfg[self._cfg_key] = round(float(self._thresh_var.get()), 2)
            config.save(self._main_cfg)

    def get_threshold(self) -> float:
        return round(self._thresh_var.get(), 2)

    def refresh(self):
        ok = template_exists(self.folder_fn(), self.key)
        self._dot.configure(
            text_color=self.DOT_OK if ok else self.DOT_MISSING)

    def set_recapture_visible(self, visible: bool):
        if hasattr(self, '_recapture_btn'):
            self._recapture_btn.pack(side='right', padx=4) if visible \
                else self._recapture_btn.pack_forget()

    def set_capturing(self, active: bool):
        self._dot.configure(
            text_color="#f59e0b" if active else (
                self.DOT_OK if template_exists(self.folder_fn(), self.key)
                else self.DOT_MISSING))


class SetupPanel(ctk.CTkFrame):
    """
    Collapsible setup panel.

    template_defs: either a FLAT list of (key, label) tuples, or a CATEGORIZED
        list of (section_label, [(key, label), ...]) tuples (detected by the
        second element being a list). Categorized renders a bold sub-header per
        section; capture/complete logic flattens it transparently.
    folder: path where templates are stored
    nodes_file: path to nodes JSON (None if not applicable)
    log_cb: function(msg) for log output
    status_cb: function(msg) for status bar
    """

    def __init__(self, parent, template_defs: list, folder: str,
                 nodes_file=None, log_cb=None, status_cb=None,
                 lang='en', capture_key='caps lock',
                 res_cfg_key='race_resolution', mode='race',
                 main_cfg=None, tpl_lang='cht', allow_roi=False,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self._mode        = mode
        self._allow_roi   = allow_roi   # show per-row "Detection area" button
        self._tpl_lang    = tpl_lang   # game-menu template language (cht/en)
        self._main_cfg    = main_cfg   # reference to main window cfg dict
        # Single built-in (auto-scaled) template set — the user-capture "custom"
        # mode was removed. res_cfg_key is accepted for caller compatibility but
        # unused. Captures go into the built-in set.
        self._resolution  = config.REFERENCE_RES
        # Set folder based on resolution
        self.folder      = self._get_folder()
        self.nodes_file  = self._get_nodes_file()
        self.log_cb      = log_cb or (lambda m: None)
        self.status_cb   = status_cb or (lambda m: None)
        self._session    = None
        self._lang        = lang
        self._capture_key = capture_key
        self._tpl_defs    = template_defs
        # template_defs may be flat [(key, label), ...] or categorized
        # [(section_label, [(key, label), ...]), ...]. Detect by the 2nd element
        # being a list; keep a flattened [(key, label)] for capture/complete logic.
        self._categorized = bool(template_defs) and isinstance(template_defs[0][1], list)
        if self._categorized:
            self._flat_defs = [(k, lb) for _sec, items in template_defs
                               for k, lb in items]
        else:
            self._flat_defs = list(template_defs)
        # Load saved monitor index from config
        _saved_cfg = config.load()
        self._monitor_index = _saved_cfg.get('monitor_index', 1)
        self._rows       = {}
        self._collapsed  = True

        self._build_header()
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._build_content(template_defs, nodes_file)
        # Start collapsed
        self._content.pack_forget()

    def _get_folder(self) -> str:
        if self._mode == 'race':
            return get_race_templates(self._resolution, self._tpl_lang)
        if self._mode == 'wheelspin':
            return get_wheelspin_templates(self._resolution, self._tpl_lang)
        if self._mode == 'buy':
            return get_buy_templates(self._resolution, self._tpl_lang)
        if self._mode == 'full_auto':
            return get_full_auto_templates(self._resolution, self._tpl_lang)
        return get_mastery_templates(self._resolution, self._tpl_lang)

    def _get_nodes_file(self):
        if self._mode != 'mastery': return None
        return get_nodes_file(self._resolution, self._tpl_lang)

    def _is_custom(self) -> bool:
        # Single built-in set now; capture/retake is always available for it.
        return True

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 0))

        self._toggle_btn = ctk.CTkButton(
            hdr, text=_at("setup_header", self._lang),
            command=self._toggle,
            fg_color="transparent",
            text_color=theme.token("text"),
            hover_color=theme.token("surface"),
            anchor="w",
            font=("Arial", 13, "bold"),
        )
        self._toggle_btn.pack(side="left", fill="x", expand=True)

        # Overall status dot
        self._overall_dot = ctk.CTkLabel(hdr, text="●", width=20,
                                          font=("Arial", 14))
        self._overall_dot.pack(side="right", padx=8)
        self.refresh_all()

    def _build_content(self, template_defs, nodes_file):
        c = self._content
        c.pack(fill="x", padx=16, pady=4)

        # (Resolution selector removed — single built-in auto-scaled set.)

        # Template rows (none in mastery keys mode — nodes are the only capture).
        # Categorized defs render a bold sub-header per section; flat defs keep
        # the single "Templates" header.
        def _add_row(key, label):
            row = TemplateRow(c, label, lambda: self.folder, key,
                              on_recapture=lambda k=key: self._recapture_one(k),
                              on_set_roi=((lambda k=key: self._set_roi_one(k))
                                          if self._allow_roi else None),
                              main_cfg=self._main_cfg,
                              lang=self._lang)
            row.pack(fill="x", pady=1)
            self._rows[key] = row

        if self._categorized:
            for sec_label, items in template_defs:
                ctk.CTkLabel(c, text=sec_label, anchor="w",
                             font=("Arial", 11, "bold"),
                             text_color=theme.token("accent")).pack(
                                 fill="x", pady=(8, 2))
                for key, label in items:
                    _add_row(key, label)
        else:
            if template_defs:
                ctk.CTkLabel(c, text=_at("label_templates", self._lang),
                             anchor="w",
                             font=("Arial", 11)).pack(fill="x", pady=(4, 2))
            for key, label in template_defs:
                _add_row(key, label)

        # Nodes row
        if nodes_file:
            nf = ctk.CTkFrame(c, fg_color="transparent")
            nf.pack(fill="x", pady=(8, 2))
            self._node_dot = ctk.CTkLabel(nf, text="●", width=20,
                                           font=("Arial", 14))
            self._node_dot.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(nf, text=_at("label_nodes", self._lang),
                         anchor="w").pack(side="left")
            self._node_recapture_btn = ctk.CTkButton(
                nf, text='↺', width=28,
                command=self._recapture_nodes,
                fg_color='transparent',
                hover_color=('gray80', 'gray30'),
                text_color=('gray40', 'gray70'),
                font=('Arial', 14))
            self._node_recapture_btn.pack(side="right", padx=4)
            self._refresh_node_dot()

        # Capture controls
        self.after(100, self._update_capture_visibility)
        # (placeholder, actual build below)
        # (placeholder end)
        ctrl = ctk.CTkFrame(c, fg_color="transparent")
        ctrl.pack(fill="x", pady=(12, 4))

        self._cap_btn = ctk.CTkButton(
            ctrl, text=_at("btn_start_capture", self._lang),
            command=self._start_session, width=180,
            fg_color=theme.token("accent"),
            hover_color=theme.token("accent_hover"),
            text_color=theme.token("accent_text"))
        self._cap_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = ctk.CTkButton(
            ctrl, text=_at("btn_stop_capture", self._lang),
            command=self._stop_session,
            fg_color=theme.STOP_FG, hover_color=theme.STOP_HOVER,
            text_color=theme.token("stop_text"),
            width=120, state="disabled")
        self._stop_btn.pack(side="left")

        self._cap_label = ctk.CTkLabel(
            c, text="", anchor="w",
            font=("Arial", 11), text_color="gray")
        self._cap_label.pack(fill="x", pady=(2, 4))

    def _update_capture_visibility(self):
        """Bulk capture only in custom mode; individual ↺ buttons always visible."""
        if hasattr(self, '_cap_btn'):
            self._cap_btn.configure(
                state='normal' if self._is_custom() else 'disabled')
        if hasattr(self, '_node_recapture_btn'):
            self._node_recapture_btn.pack(side="right", padx=4)
        for row in self._rows.values():
            row.set_recapture_visible(True)

    def _toggle(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._content.pack_forget()
            self._toggle_btn.configure(text=_at("setup_header", self._lang))
        else:
            self._content.pack(fill="x", padx=16, pady=4)
            self._toggle_btn.configure(text=_at("setup_header_open", self._lang))

    def _on_monitor_change(self, val):
        try:
            self._monitor_index = int(val.split("—")[0].strip())
        except Exception:
            self._monitor_index = 1
        # Persist to config immediately
        cfg = config.load()
        cfg["monitor_index"] = self._monitor_index
        config.save(cfg)

    # ── Capture session ───────────────────────────────────────

    def _recapture_nodes(self):
        """Immediately start a node capture session."""
        if self._collapsed:
            self._toggle()
        if self._session:
            self._session.stop()
            self._session = None
        self._pending = ["__nodes__"]
        self._cap_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._advance_session()

    def _recapture_one(self, key):
        """Immediately start a capture session for one specific template."""
        # Expand panel if collapsed so user can see the capture label
        if self._collapsed:
            self._toggle()
        if self._session:
            self._session.stop()
            self._session = None
        self._pending = [key]
        self._cap_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._advance_session()

    def _set_roi_one(self, key):
        """Capture a custom DETECTION AREA (search ROI) for one template — the
        rectangle is saved (as fractions) into the template's JSON and overrides
        its capture-box geometry at detect time. Saves no image."""
        if self._collapsed:
            self._toggle()
        if self._session:
            self._session.stop()
            self._session = None
        label = next((lb for k, lb in self._flat_defs if k == key), key)
        self._cap_label.configure(
            text=_at("set_roi_instruction", self._lang, label=label) + " — " +
                 _at("shortcut_capture", self._lang, key=self._capture_key.upper()))
        self.status_cb(f"Waiting for {self._capture_key.upper()} — "
                       f"detection area: {label}")
        sess = CaptureSession(
            monitor_index=self._monitor_index,
            window_title=f"Select detection area — {label}",
            callback=lambda crop, w, h, bx, by, bw, bh, k=key:
                self._on_roi_captured(k, w, h, (bx, by, bw, bh)),
            on_cancel=self._on_capture_cancel,
            capture_key=self._capture_key,
            template_key=None,            # no example image for an area select
            examples_dir=None,
        )
        self._session = sess
        self._cap_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        sess.start()

    def _on_roi_captured(self, key, screen_w, screen_h, box):
        from capture import save_roi
        save_roi(self.folder, key, box, screen_w, screen_h)
        self.after(0, lambda: self._post_roi(key))

    def _post_roi(self, key):
        if self._session is not None:
            self._session.stop()
            self._session = None
        self.log_cb(_at("roi_saved", self._lang, key=key))
        self._cap_label.configure(text="")
        self._cap_btn.configure(
            state="normal" if self._is_custom() else "disabled")
        self._stop_btn.configure(state="disabled")
        if key in self._rows:
            self._rows[key].refresh()

    def _start_session(self):
        """Start listening for Caps Lock captures, cycling through templates."""
        self._pending = [k for k, _ in self._flat_defs
                         if not template_exists(self.folder, k)]
        # Also add nodes if missing
        if self.nodes_file and not nodes_exist(self.nodes_file):
            self._pending.append("__nodes__")

        if not self._pending:
            self.status_cb(_at("all_templates_done", self._lang))
            return

        self._cap_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._advance_session()

    def _advance_session(self):
        if not self._pending:
            self._end_session()
            return

        next_key = self._pending[0]

        # Stop any existing session cleanly before starting new one
        if self._session is not None:
            self._session.stop()
            self._session = None

        if next_key == "__nodes__":
            self._cap_label.configure(
                text=_at("capture_nodes_instruction", self._lang))
            self.status_cb(f"Waiting for {self._capture_key.upper()} — node capture")
            show_example('nodes', get_examples_dir(self._tpl_lang))
            sess = NodeSession(
                monitor_index=self._monitor_index,
                callback=self._on_nodes_captured,
                on_cancel=self._on_capture_cancel,
                capture_key=self._capture_key,
            )
            self._session = sess
            sess.start()
        else:
            label = next((lb for k, lb in self._flat_defs if k == next_key), next_key)
            if next_key in self._rows:
                self._rows[next_key].set_capturing(True)
            self._cap_label.configure(
                text=_at("capturing_label", self._lang, label=label) + " — " +
                     _at("shortcut_capture", self._lang, key=self._capture_key.upper()))
            self.status_cb(f"Waiting for {self._capture_key.upper()} — {label}")

            from capture import get_monitor_dims
            try:
                sw, sh, _, _ = get_monitor_dims(self._monitor_index)
            except Exception:
                sw, sh = 1920, 1080

            sess = CaptureSession(
                monitor_index=self._monitor_index,
                window_title=f"Select region — {label}",
                callback=lambda crop, w, h, bx, by, bw, bh, k=next_key:
                    self._on_captured(k, crop, w, h, (bx, by, bw, bh)),
                on_cancel=self._on_capture_cancel,
                capture_key=self._capture_key,
                template_key=next_key,
                examples_dir=get_examples_dir(self._tpl_lang),
            )
            self._session = sess
            sess.start()

    def _on_captured(self, key, crop, screen_w, screen_h, box=None):
        save_template(self.folder, key, crop, screen_w, screen_h, box=box)
        self.after(0, lambda: self._post_capture(key))

    def _post_capture(self, key):
        if key in self._rows:
            self._rows[key].set_capturing(False)
            self._rows[key].refresh()
        self.log_cb(_at("template_saved", self._lang, key=key))
        if key in self._pending:
            self._pending.remove(key)
        self.refresh_all()
        self._advance_session()

    def _on_nodes_captured(self, nodes, screen_w, screen_h):
        save_nodes(self.nodes_file, nodes, screen_w, screen_h)
        self.after(0, lambda: self._post_nodes())

    def _post_nodes(self):
        self.log_cb(_at("nodes_saved", self._lang))
        close_example()
        if "__nodes__" in self._pending:
            self._pending.remove("__nodes__")
        # Stop the NodeSession before advancing
        if self._session is not None:
            self._session.stop()
            self._session = None
        if hasattr(self, '_node_dot'):
            self._refresh_node_dot()
        self.refresh_all()
        self._advance_session()

    def _on_capture_cancel(self, reason="cancelled"):
        self.after(0, lambda r=reason: self._do_cancel(r))

    def _do_cancel(self, reason):
        self._pending = []
        if self._session is not None:
            self._session.stop()
            self._session = None
        self._cap_label.configure(
            text=_at("capture_cancelled", self._lang, reason=reason))
        self._end_session()

    def _stop_session(self):
        if self._session:
            self._session.stop()
            self._session = None
        self._end_session()

    def _end_session(self):
        if self._session is not None:
            self._session.stop()
            self._session = None
        for row in self._rows.values():
            row.set_capturing(False)
            row.refresh()
        self._cap_btn.configure(
            state="normal" if self._is_custom() else "disabled")
        self._stop_btn.configure(state="disabled")
        self._cap_label.configure(text="")
        self.refresh_all()
        self.status_cb(_at("setup_complete", self._lang) if self.is_complete() else _at("setup_in_progress", self._lang))

    # ── Status helpers ────────────────────────────────────────

    def refresh_all(self):
        for row in self._rows.values():
            row.refresh()
        if hasattr(self, '_node_dot'):
            self._refresh_node_dot()
        ok = self.is_complete()
        self._overall_dot.configure(
            text_color=TemplateRow.DOT_OK if ok else TemplateRow.DOT_MISSING)

    def _refresh_node_dot(self):
        ok = nodes_exist(self.nodes_file) if self.nodes_file else True
        self._node_dot.configure(
            text_color=TemplateRow.DOT_OK if ok else TemplateRow.DOT_MISSING)

    def is_complete(self) -> bool:
        templates_ok = all(template_exists(self.folder, k)
                           for k, _ in self._flat_defs)
        nodes_ok     = (not self.nodes_file or
                        nodes_exist(self.nodes_file))
        return templates_ok and nodes_ok
