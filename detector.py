"""
Soft-scored screen detection for FAFE.

The detector keeps the existing screenshot templates but makes matching less
fragile by combining ROI-first search, multi-scale matching, contrast
normalization, edge matching, stability, and optional OCR evidence.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Optional
import os
import re
import threading
import time

import cv2
import numpy as np

# Cap OpenCV's internal parallelism.  By default cv2.matchTemplate fans out
# across EVERY logical core, so each detection briefly saturates the whole CPU.
# That's not just high average load — it momentarily steals the very cores the
# game's render thread needs, which is what causes the in-game stutter users see
# while a script polls (worst during wheelspin's ~20 detect/sec loops). ROI-only
# matching is only a few ms, so a 1–2 thread cap costs no real latency while
# leaving the rest of the cores free for the game.  Configurable per run via
# `detector_cv_threads` (0 = OpenCV default / all cores).  Set a safe default at
# import time; ScreenDetector re-applies the config value when constructed.
_DEFAULT_CV_THREADS = 2
_OCR_THREADS = 1   # onnxruntime intra-op cap; OCR is cooldown-gated so 1 is plenty
try:
    cv2.setNumThreads(_DEFAULT_CV_THREADS)
except Exception:
    pass


Rect = tuple[float, float, float, float]
Point = tuple[int, int]

# DEFAULT_ROIS are tuned on 16:9. Template sizes scale by height (so vertical
# layout is invariant across same-height screens), but the horizontal fraction
# of a UI element shifts on non-16:9 aspect ratios — see _roi_for_frame.
REF_ASPECT = 16.0 / 9.0

# Keys whose ROI maps into the centred 16:9 box on non-16:9 screens (UI anchored
# to the content box, e.g. menus). Everything else uses a full-axis band because
# in-game HUD elements anchor to the screen edges. start_menu specifically needs
# the box — on a full-width band it false-matched the loading screen (~85%).
_ROI_BOX_KEYS = frozenset({"start_menu"})


@dataclass
class MatchResult:
    matched: bool
    score: float
    confidence: float
    location: Point
    scale: float
    source: str
    ocr_text: str = ""


DEFAULT_ROIS: dict[str, Rect] = {
    # x, y, width, height ratios. Tuned to where the UI element actually
    # appears on screen, with a small margin for layout variation. Full-screen
    # fallback (with a 0.94 score penalty) catches anything that drifts
    # outside.  Important under OCR-primary mode: a wrong ROI makes OCR read
    # the wrong region of the screen and produces false positives.
    "start_menu":           (0.00, 0.40, 0.30, 0.50),  # menu on left side
    "racing":               (0.00, 0.03, 0.32, 0.22),  # 時間 (race timer) — top-left HUD
    "restart_menu":         (0.00, 0.80, 0.35, 0.20),  # [X] 重新開始 — bottom-left
    "confirm":              (0.20, 0.20, 0.65, 0.65),  # centre dialog
    "mastery_ride_car":     (0.30, 0.30, 0.40, 0.40),  # centre context menu
    "mastery_esc_hint":     (0.00, 0.90, 0.30, 0.10),  # bottom-left hint bar
    "mastery_upgrade_item": (0.00, 0.20, 0.30, 0.60),  # left side menu
    "mastery_mastery_item": (0.00, 0.20, 0.30, 0.75),  # left submenu, full height
    "mastery_anchor":       (0.00, 0.00, 0.25, 0.15),  # top-left title
    "mastery_my_cars":      (0.00, 0.10, 0.30, 0.50),  # top of left menu
    "mastery_sort_recent":  (0.30, 0.20, 0.40, 0.70),  # centre sort menu
    "wheelspin_duplicate":  (0.20, 0.20, 0.65, 0.65),  # centre duplicate-reward menu
    "my_horizon_tab":       (0.00, 0.00, 1.00, 0.15),  # top-nav My Horizon tab
    "super_wheelspin":      (0.00, 0.20, 0.33, 0.65),  # left-column Super Wheelspin tile
    "normal_wheelspin":     (0.00, 0.20, 0.33, 0.65),  # left-column (normal) Wheelspin tile
    "wheelspin_skip":       (0.00, 0.86, 0.40, 0.14),  # bottom-left button prompt
    "wheelspin_collect":    (0.00, 0.86, 0.40, 0.14),  # bottom-left button prompt
    "wheelspin_collect_final": (0.00, 0.86, 0.40, 0.14),  # final-spin single "Collect Prize"
    # ── Race menu navigation (main menu → EventLab → MY HISTORY → Start) ──
    # Fallback ROIs only; user captures carry a geometry box that supplies the
    # real ROI. Generous bands here so a no-box capture still detects.
    "creative_hub":         (0.45, 0.18, 0.45, 0.14),  # top nav bar, right side
    "eventlab":             (0.20, 0.30, 0.45, 0.45),  # centre EventLab tile
    "play_event":           (0.25, 0.10, 0.40, 0.55),  # centre Play Event tile
    "events_arrow":         (0.00, 0.10, 0.12, 0.16),  # ◀ tab arrow, far top-left
    "my_history":           (0.05, 0.04, 0.45, 0.14),  # MY HISTORY tab row, top-left
    "choose_race_type":     (0.20, 0.00, 0.60, 0.30),  # centre yellow header
    "car_select":           (0.00, 0.00, 1.00, 0.30),  # car-selection top band
    # ── Buy (main menu → Car Collection → Subaru → buy) ──
    # Fallback ROIs only; user captures carry a geometry box. Generous bands.
    "collection_log":       (0.00, 0.30, 0.45, 0.55),  # 收藏日記 tile, main menu left
    "discover_japan":       (0.40, 0.10, 0.55, 0.75),  # DISCOVER JAPAN series card, right
    "car_collection":       (0.00, 0.55, 0.45, 0.40),  # 車輛收藏 tile, bottom-left of grid
    "subaru":               (0.00, 0.45, 1.00, 0.55),  # Subaru brand tile (brand view, bottom)
    "buy_target_car":       (0.40, 0.45, 0.60, 0.55),  # target car tile (after 1-notch scroll)
    # ── Race exit (results → main menu) ──
    # The recommended "What's Next" menu shown after Continue. Capture the
    # fixed top-left "接下來做什麼" / "What's Next" heading (invariant position).
    "next_activity":        (0.00, 0.00, 0.45, 0.20),  # top-left heading
    # ── Full Auto: mastery positioning (main menu → My Horizon → My Cars) ──
    # Fallback ROIs only; user captures carry a geometry box. Generous bands.
    "return_home":          (0.20, 0.10, 0.55, 0.60),  # "Return Home" tile, My Horizon
    "cars_tab":             (0.00, 0.00, 1.00, 0.15),  # top-nav CARS tab (home menu)
    "recently_added":       (0.20, 0.05, 0.60, 0.30),  # "Recently Added" sort header/option
    # ── Full Auto: sell re-select grind car (Filter → brand jump → car) ──
    # These elements MOVE (the Manufacturer menu grows/shrinks with the player's
    # favourited brands; the car's row varies), so they use a LARGE confined ROI
    # — NOT a tight geometry box (full_auto skips set_template_geometry for them).
    "grind_brand":          (0.05, 0.05, 0.90, 0.60),  # brand button in Jump-to-Manufacturer menu
    "grind_car":            (0.20, 0.15, 0.80, 0.80),  # car tile in the brand list (visible 3 rows)
    "select_action":        (0.45, 0.10, 0.55, 0.55),  # "Select An Action" menu after clicking the car tile
    # ── Full Auto: sell fallbacks. These templates normally detect via their
    # capture box (geometry ROI); these generous bands are only a SAFETY NET if a
    # re-capture ever lacks a box (otherwise the ROI would be None → full-frame).
    "anna":                 (0.00, 0.82, 0.35, 0.18),  # home icon shown when leaving the home menu (fallback band)
    "my_cars":              (0.00, 0.25, 0.35, 0.55),  # My Cars item, left menu column
    "my_cars_header":       (0.00, 0.00, 0.40, 0.22),  # My Cars page header, top-left
}


OCR_HINTS: dict[str, tuple[str, ...]] = {
    # Hints are substring-matched against OCR output (case-insensitive).
    # Avoid hints that are too short or too generic — they false-positive on
    # unrelated UI text when OCR is the primary detection signal.
    "start_menu": ("start", "race", "開始", "開始賽事", "开始"),
    "racing": ("時間", "时间", "time"),
    "restart_menu": ("restart", "重新開始", "重新开始"),
    "confirm": ("確定", "确定", "重新開始賽事", "重新开始赛事", "confirm"),
    "mastery_ride_car": ("ride", "car", "駕駛", "驾驶"),
    "mastery_esc_hint": ("esc", "Esc", "ESC"),
    "mastery_upgrade_item": ("upgrade", "tuning", "升級", "升级"),
    "mastery_mastery_item": ("mastery", "熟練", "熟练"),
    "mastery_anchor": ("車輛熟練度", "车辆熟练度"),
    "mastery_my_cars": ("my cars", "車庫", "车库"),
    "mastery_sort_recent": ("recent", "recently", "新增", "最近"),
    # Captured prompts are the question/prompt text (see templates). Hints are
    # bilingual so OCR confirm works whichever language the game renders.
    # Template is now the solid-yellow "Car Already Owned" header (invariant bg);
    # hints match that text first. Old menu-body hints ("what would", options)
    # kept as fallback for any capture still on the body text.
    "wheelspin_duplicate": ("already owned", "owned", "already",
                            "這輛車", "什麼操作", "this car", "what would",
                            "garage", "sell", "車庫", "賣出", "贈送"),
    "my_horizon_tab": ("my horizon", "horizon", "我的地平線", "地平線", "地平线"),
    "super_wheelspin": ("super", "wheelspin", "horizon", "超級", "輪盤"),
    "normal_wheelspin": ("wheelspin", "wheel spin", "horizon", "輪盤", "轉輪"),
    "wheelspin_skip": ("略過", "skip", "跳過"),
    "wheelspin_collect": ("collect prize", "spin again", "collect", "prize",
                          "reward", "取得", "獎勵", "抽獎", "再次"),
    "wheelspin_collect_final": ("collect prize", "collect", "prize",
                                "取得獎勵", "取得", "獎勵"),
    # Race menu navigation. Hints are best-effort confirms; at native capture
    # resolution the pixel match is strong enough that OCR is usually skipped.
    "creative_hub": ("creative hub", "creative", "hub", "創意中心", "創意"),
    "eventlab": ("eventlab", "event lab", "create", "browse", "創作"),
    "play_event": ("play event", "play", "event", "遊玩"),
    "events_arrow": (),  # symbol, no text to confirm
    "my_history": ("my history", "history", "歷史", "我的歷史"),
    "choose_race_type": ("choose race type", "race type", "choose how", "賽事類型"),
    "car_select": ("current car", "current", "choose", "car", "vehicle",
                   "目前車輛", "選擇", "車輛"),
    "next_activity": ("what's next", "whats next", "what next", "next",
                      "接下來做什麼", "接下來", "做什麼"),
    # Buy navigation. Hints best-effort; at native capture the pixel match is
    # usually strong enough that OCR is skipped.
    "collection_log": ("collection journal", "collection", "journal",
                       "收藏日記", "收藏日誌", "收藏"),
    "discover_japan": ("discover japan", "discover", "japan",
                       "master explorer", "explorer", "探索大師", "探索"),
    "car_collection": ("car collection", "collection", "車輛收藏", "車輛", "收藏"),
    "subaru": ("subaru", "速霸陸", "速霸陆"),  # brand tile (logo may have no text)
    "buy_target_car": (),  # a specific car tile (image), no reliable text hint
    # Full Auto mastery positioning nav.
    "return_home": ("return home", "home", "fast travel", "返回住宅", "返回", "回家"),
    "cars_tab": ("cars", "car", "車輛", "汽車", "车辆"),
    "recently_added": ("recently added", "recently", "recent", "added",
                       "最近新增", "最近", "新增"),
    # The brand is fixed (Subaru — the name is "Subaru" in Chinese too) so it
    # has a reliable text hint; the car tile varies in framing per capture so it
    # stays pixel-only. (full_auto custom mode disables OCR anyway; these matter
    # only if OCR is on.)
    "grind_brand": ("subaru",),
    "grind_car": (),
    "select_action": ("select an action", "select", "action", "選擇動作", "選擇", "動作"),
    # Sell fallbacks (full_auto custom mode disables OCR, so these only matter
    # if these keys are ever detected in a preset/OCR run).
    "anna": (),  # home icon — no text to confirm
    "my_cars": ("my cars", "我的車輛", "車庫", "车库"),
    "my_cars_header": ("my cars", "我的車輛", "車庫"),
}

# All template images capture text UI elements. Edge matching on text is
# noisy (anti-aliasing artifacts) and adds cost without reliability benefit,
# so these keys all use the fast grayscale-only, 3-scale path.
# Keys NOT listed here fall back to the full multi-scale + edge pipeline.
TEXT_TEMPLATES: frozenset[str] = frozenset(DEFAULT_ROIS.keys())


def _scale_by_anchor(val: float, ref_dim: int, screen_dim: int,
                     scale: float) -> float:
    """Map a coordinate from the reference frame onto the live frame, anchored
    to whichever edge it sits nearest (ok-script's model). A coordinate in the
    right/bottom half is measured from the FAR edge so edge-anchored UI (bottom
    HUD, right-side panels) stays glued to that edge on any screen size;
    otherwise it's measured from the near (left/top) edge."""
    if val > ref_dim / 2:
        return screen_dim - (ref_dim - val) * scale
    return val * scale


_ASPECT_16_9 = 16.0 / 9.0

def _content_box(w: int, h: int) -> tuple[float, float, float, float]:
    """The centred 16:9 region Forza anchors its MENU UI to. Pillarboxed (bars
    left/right) when the screen is wider than 16:9, letterboxed (bars top/
    bottom) when taller. Returns (x, y, w, h) in pixels. Same model as
    capture._content_box used for mastery node clicks."""
    if w <= 0 or h <= 0:
        return 0.0, 0.0, float(w), float(h)
    if w / h > _ASPECT_16_9:                 # wider than 16:9 → limit by height
        bw = h * _ASPECT_16_9
        return (w - bw) / 2.0, 0.0, bw, float(h)
    bh = w / _ASPECT_16_9                     # taller than 16:9 → limit by width
    return 0.0, (h - bh) / 2.0, float(w), bh


# Geometry-ROI anchoring: menu/dialog elements live inside the centred 16:9
# content box (above), so their box must be mapped through that box to survive
# an aspect change (e.g. an ultrawide capture used on a 16:9 screen). Only true
# in-game HUD (the race timer) is anchored to the raw screen edge — listed here
# so it keeps the edge model. Everything else is treated as a centred menu.
_GEOM_EDGE_KEYS: frozenset[str] = frozenset({"racing"})


def _clip_roi(frame: np.ndarray, roi: Optional[Rect]) -> tuple[np.ndarray, int, int]:
    if roi is None:
        return frame, 0, 0
    h, w = frame.shape[:2]
    x = max(0, min(w - 1, int(roi[0] * w)))
    y = max(0, min(h - 1, int(roi[1] * h)))
    rw = max(1, min(w - x, int(roi[2] * w)))
    rh = max(1, min(h - y, int(roi[3] * h)))
    return frame[y:y + rh, x:x + rw], x, y


# ── Debug visualisation (detection snapshots + F12 report) ────────────────
# Module-level so the marker survives across the per-run detector instance and
# is readable from the F12 report's own thread.
_LAST_DETECT = None    # (frame, key, roi, MatchResult, soft_threshold, time)
_LAST_CLICK = None     # (x, y, time) in detection-frame (cropped client) coords
_CLICK_DRAW_AGE = 15.0  # only mark a click on a snapshot if it's this recent


def record_click(x: int, y: int) -> None:
    """Record the most recent mouse click (in detection-frame coords) so debug
    snapshots and the F12 report can mark where it landed. Called by gameio
    after each click. Best-effort — never raises into the caller."""
    global _LAST_CLICK
    try:
        _LAST_CLICK = (int(x), int(y), time.time())
    except Exception:
        pass


def _record_detect(frame, key, roi, result, soft) -> None:
    global _LAST_DETECT
    _LAST_DETECT = (frame, key, roi, result, soft, time.time())


def _draw_debug(img, key, roi, result, soft_threshold) -> None:
    """Annotate `img` (BGR, in place) with the detection context: YELLOW ROI box
    (searched area), GREEN/RED best-match cross (matched/miss), MAGENTA marker
    for the last click, and a header bar of the numbers."""
    h, w = img.shape[:2]
    matched = bool(result.matched)
    col = (0, 200, 0) if matched else (0, 90, 255)   # BGR green / red
    if roi:   # ROI is fractional (x, y, w, h) — same math as _clip_roi
        rx, ry = int(roi[0] * w), int(roi[1] * h)
        rw, rh = int(roi[2] * w), int(roi[3] * h)
        cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), (0, 220, 220), 3)
    if result.location:   # frame-local centre of the best match
        lx, ly = int(result.location[0]), int(result.location[1])
        cv2.drawMarker(img, (lx, ly), col, cv2.MARKER_CROSS, 44, 3)
        cv2.circle(img, (lx, ly), 16, col, 3)
    click = _LAST_CLICK
    if click and time.time() - click[2] <= _CLICK_DRAW_AGE:
        cx, cy = click[0], click[1]
        cv2.circle(img, (cx, cy), 18, (255, 0, 255), 3)       # magenta
        cv2.line(img, (cx - 28, cy), (cx + 28, cy), (255, 0, 255), 2)
        cv2.line(img, (cx, cy - 28), (cx, cy + 28), (255, 0, 255), 2)
        cv2.putText(img, "click", (cx + 22, cy - 12), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 0, 255), 2, cv2.LINE_AA)
    label = (f"{key}  {result.score:.0%} (soft>={soft_threshold:.0%})  "
             f"{result.source}  {'MATCH' if matched else 'miss'}")
    if result.ocr_text:
        label += f"  OCR:'{result.ocr_text[:30]}'"
    cv2.rectangle(img, (0, 0), (w, 48), (0, 0, 0), -1)
    cv2.putText(img, label, (12, 34), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, col, 2, cv2.LINE_AA)


def render_report_image(max_age: float = 30.0):
    """Annotated debug image for the F12 report, built from the most recent
    detection (the frame FAFE last looked at + its ROI/match + last click).
    Returns a BGR ndarray, or None if there's no recent detection (the caller
    then falls back to a plain screenshot)."""
    last = _LAST_DETECT
    if not last:
        return None
    frame, key, roi, result, soft, t = last
    if frame is None or getattr(frame, "size", 0) == 0 or time.time() - t > max_age:
        return None
    try:
        img = frame.copy()
        _draw_debug(img, key, roi, result, soft)
        return img
    except Exception:
        return None


def _prepare_gray(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.equalizeHist(img)


def _prepare_edges(img: np.ndarray) -> np.ndarray:
    gray = _prepare_gray(img)
    return cv2.Canny(gray, 60, 160)


def _scaled_templates(template: np.ndarray, scales: Iterable[float]):
    th, tw = template.shape[:2]
    for scale in scales:
        nw = max(8, int(tw * scale))
        nh = max(8, int(th * scale))
        if nw == tw and nh == th:
            yield scale, template
        else:
            yield scale, cv2.resize(template, (nw, nh), interpolation=cv2.INTER_AREA)


def _best_template_match(screen: np.ndarray, template: np.ndarray,
                         scales: Iterable[float]) -> tuple[float, Point, float]:
    best_conf = -1.0
    best_loc = (0, 0)
    best_scale = 1.0
    sh, sw = screen.shape[:2]
    for scale, tpl in _scaled_templates(template, scales):
        th, tw = tpl.shape[:2]
        if th > sh or tw > sw:
            continue
        result = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
        _, conf, _, loc = cv2.minMaxLoc(result)
        if conf > best_conf:
            best_conf = float(conf)
            best_loc = (int(loc[0] + tw // 2), int(loc[1] + th // 2))
            best_scale = float(scale)
    return max(0.0, best_conf), best_loc, best_scale


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


class OptionalOCR:
    """Tiny lazy OCR facade.

    OCR is deliberately optional. RapidOCR is preferred because it can be
    bundled without a separate Tesseract executable. If no OCR backend is
    installed, detection still runs normally.
    """

    def __init__(self):
        self._loaded = False
        self._reader: Optional[Callable[[np.ndarray], str]] = None

    def available(self) -> bool:
        self._ensure_loaded()
        return self._reader is not None

    def read(self, img: np.ndarray) -> str:
        self._ensure_loaded()
        if self._reader is None:
            return ""
        try:
            return self._reader(img)
        except Exception:
            return ""

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        try:
            from rapidocr_onnxruntime import RapidOCR
            # Cap onnxruntime's intra-op threads — it defaults to ALL cores and
            # cv2.setNumThreads / OMP env don't touch its own pool. Falls back if
            # the installed version doesn't accept the kwarg.
            try:
                engine = RapidOCR(intra_op_num_threads=_OCR_THREADS)
            except TypeError:
                engine = RapidOCR()

            def _read(img):
                result, _ = engine(img)
                if not result:
                    return ""
                return " ".join(str(item[1]) for item in result if len(item) > 1)

            self._reader = _read
            return
        except Exception:
            pass
        try:
            from rapidocr import RapidOCR
            try:
                engine = RapidOCR(intra_op_num_threads=_OCR_THREADS)
            except TypeError:
                engine = RapidOCR()

            def _read(img):
                result = engine(img)
                items = getattr(result, "txts", None)
                if items is not None:
                    return " ".join(str(x) for x in items)
                if not result:
                    return ""
                return " ".join(str(item[1]) for item in result if len(item) > 1)

            self._reader = _read
            return
        except Exception:
            pass
        try:
            import pytesseract
            self._reader = lambda img: pytesseract.image_to_string(img)
        except Exception:
            self._reader = None


class ScreenDetector:
    # OCR can add at most this much to the score. Used to decide whether
    # running OCR could possibly flip the match decision.
    OCR_MAX_BONUS = 0.10

    def __init__(self, cfg: dict | None = None, debug_dir: str | None = None):
        self.cfg = cfg or {}
        self.debug_dir = debug_dir
        # Detection debug: save an annotated snapshot per detection (see
        # save_debug). Default off. When on and no explicit dir was given, write
        # to a `debug/` folder next to the exe.
        self._debug = bool(self.cfg.get("debug_detection", False))
        self._debug_last: dict[str, float] = {}   # key -> last save time (throttle)
        if self._debug and not self.debug_dir:
            try:
                import config as _c
                self.debug_dir = os.path.join(_c.BASE_DIR, "debug")
            except Exception:
                self.debug_dir = "debug"
        # Re-assert the OpenCV thread cap from config (0 = let OpenCV use all
        # cores).  Keeps detection from flooding every core and starving the
        # game — see _DEFAULT_CV_THREADS above.
        try:
            cv2.setNumThreads(int(self.cfg.get("detector_cv_threads",
                                               _DEFAULT_CV_THREADS)))
        except Exception:
            pass
        self._ocr = OptionalOCR()
        self._history: dict[str, list[float]] = {}
        self.scales = self.cfg.get(
            "detector_scales",
            [0.86, 0.92, 0.97, 1.00, 1.03, 1.08, 1.14],
        )
        # Reduced scale set for text-based templates: the game UI renders text
        # at a fixed size per resolution, so 3 nearby scales are sufficient.
        # Configurable via "detector_text_scales" in config.json.
        self._text_scales: list[float] = self.cfg.get(
            "detector_text_scales",
            [0.95, 1.00, 1.05],
        )
        self.stable_frames = int(self.cfg.get("detector_stable_frames", 2))
        # Full-screen fallback gating.  The ROI-miss full-screen search is the
        # single most expensive per-check operation (~85% of wait-state cost).
        # While idly waiting for a screen, the ROI already tells us the target
        # isn't present, so the full sweep just burns CPU confirming "nope".
        # Only run it when the ROI hints the element may be present but drifted
        # (roi_score >= gate) or on a periodic safety sweep (every Nth gated
        # check) so drift outside the ROI is still caught within a bounded
        # number of checks.  Gating applies only to the stable (wait_for) path;
        # single-shot detect (stable=False, used by click ops) always runs the
        # full fallback so one-off clicks never miss a drifted element.
        # Set detector_full_sweep_every <= 1 to disable gating entirely.
        self._full_gate_score: float = float(
            self.cfg.get("detector_full_gate_score", 0.40))
        self._full_sweep_every: int = int(
            self.cfg.get("detector_full_sweep_every", 4))
        self._full_sweep_counter: dict[str, int] = {}
        # Force the Canny edge channel on even for text templates.  Off by
        # default: text edges are noisy (anti-aliasing) and the gray channel
        # alone matches text more reliably — so Custom mode now runs text
        # templates gray-only over the wide scale range instead of gray+edge,
        # roughly halving its matchTemplate count with no accuracy cost on
        # text.  Enable only if a custom non-text/structural template actually
        # benefits from edge matching.
        self._force_edges: bool = bool(
            self.cfg.get("detector_force_edges", False))
        # Ultrawide / non-16:9 ROI handling.  DEFAULT_ROIS are tuned on 16:9;
        # on other aspect ratios the distorted axis is searched in full while
        # the accurate axis keeps its band (see _roi_for_frame).  On by
        # default; disable with detector_roi_aspect_fix=false to force the raw
        # 16:9 ROIs.  detector_roi_aspect_tol is the ± fraction of 16:9 treated
        # as "still 16:9" (0.05 ≈ covers 16:9 exactly but not 16:10 / 21:9).
        self._roi_aspect_fix: bool = bool(
            self.cfg.get("detector_roi_aspect_fix", True))
        self._roi_aspect_tol: float = float(
            self.cfg.get("detector_roi_aspect_tol", 0.05))
        # Hard floor for the soft threshold: no match below this confidence ever
        # fires, regardless of the per-template slider (`thresh_<key>`). Raised
        # from 0.45 → 0.70 because matches in the 45–70% band misfired a lot on
        # real hardware (Ally X). Soft threshold = max(this, slider * 0.92).
        # Tunable via config `detector_min_threshold`.
        self._min_thresh: float = float(
            self.cfg.get("detector_min_threshold", 0.70))
        # Geometry-derived ROI (Stage 2): when a template carries its capture
        # box (x,y,w,h) + capture resolution, derive an anchor-aware search ROI
        # from it instead of the hand-tuned DEFAULT_ROIS. Only applies to keys
        # registered via set_template_geometry(); templates without geometry
        # (e.g. the bundled set) keep DEFAULT_ROIS unchanged. Kill-switch:
        # detector_geometry_roi=false. detector_geom_variance is the ± screen
        # fraction the box is padded by (absorbs anchoring/scale imprecision).
        self._geom_roi_on: bool = bool(
            self.cfg.get("detector_geometry_roi", True))
        self._geom_variance: float = float(
            self.cfg.get("detector_geom_variance", 0.05))
        self._geom: dict[str, dict] = {}
        # Per-template custom detection ROI (ratio tuple), set via
        # set_template_roi() from a template's saved "roi" field. Highest
        # priority — overrides both the geometry box and DEFAULT_ROIS. Used when
        # the search area must differ from where the template was captured
        # (e.g. an element that moves within a menu).
        self._custom_rois: dict[str, tuple] = {}
        # ROI-only matching (default ON): every tracked element is fixed-position
        # and covered by its (geometry-/DEFAULT_) ROI, so the full-screen
        # fallback matchTemplate — the single most expensive per-check op (~680ms
        # over an 11MP 5120x2160 frame; the duplicate poll ran it twice/cycle for
        # ~1.5s of reaction lag) — buys nothing and is skipped. Detection becomes
        # ROI-only (~35ms). Kill-switch: detector_roi_only=false restores the
        # ROI-first + full-screen-fallback behaviour (for setups where an element
        # can land outside its expected ROI).
        self._roi_only: bool = bool(self.cfg.get("detector_roi_only", True))
        # OCR cooldown: minimum seconds between actual OCR calls for the same
        # key.  Without this, a score stuck in the borderline zone triggers
        # rapidocr on every check interval (~0.5 s), causing CPU spikes.
        # Under OCR-primary mode, a confirmation is also cached for this
        # duration so the stability filter doesn't break during cooldown.
        # Set to 0 to restore the original per-frame OCR behaviour.
        self._ocr_cooldown: float = float(
            self.cfg.get("detector_ocr_cooldown", 1.0))
        self._ocr_last_run: dict[str, float] = {}
        # OCR confirmation tuning. When pixel-matching scores poorly (e.g. the
        # built-in templates run on a different machine than they were captured
        # on), text content is what's actually invariant across hardware. OCR is
        # a first-class confirmation signal rather than a +0.10 bonus — finding
        # the hint text promotes the score to _ocr_confirm_score regardless of
        # how low the pixel match was. (Gated by detector_enable_ocr.)
        #   _ocr_skip_above:      pixel score high enough that OCR is skipped
        #                         (we trust the pixel match)
        #   _ocr_skip_below:      pixel score so low that OCR is also skipped
        #                         (screen is almost certainly not the target;
        #                         saves the ~150 ms OCR call during wait loops
        #                         on unrelated screens)
        #   _ocr_confirm_score:   score floor when OCR confirms a match
        #   _ocr_cache_duration:  how long an OCR confirmation stays cached
        #                         (decoupled from cooldown — cooldown caps
        #                         the OCR call rate, cache caps how long the
        #                         result is reused)
        #   _ocr_cache_pixel_min: minimum pixel score for a cached OCR
        #                         confirmation to still apply (safeguards
        #                         against the screen having changed during
        #                         the cache window)
        # OCR runs only on text templates (those with hints) in the borderline
        # band, and only when enabled via `detector_enable_ocr` (Settings → OCR
        # text detection). There is a single detection path now — the old
        # "Custom mode" (ocr_primary=false; built-in templates are reliable
        # enough that the separate pixel-only path was dropped).
        # Pixel score at/above which we trust the pixel match and skip OCR.
        # Must be HIGH: small text templates scanned multi-scale over a large
        # ROI can hit ~0.80 TM_CCOEFF on unrelated scenes, and on hardware where
        # even genuine matches only score ~0.75–0.80 the pixel score can't tell
        # them apart — so anything below this is gated by OCR (confirm/veto)
        # rather than trusted.  Only a near-perfect pixel match (>= this) is
        # taken on pixels alone.
        self._ocr_skip_above: float = float(
            self.cfg.get("detector_ocr_skip_above", 0.90))
        self._ocr_skip_below: float = float(
            self.cfg.get("detector_ocr_skip_below", 0.20))
        # OCR VETO — OFF by default.  When on, a coincidental pixel match is
        # rejected if OCR reads the ROI and the text does NOT contain the hint.
        # It is DEFAULT OFF and, even when on, only fires when OCR actually read
        # something (`ocr_text` non-empty) — never on a silent/failed OCR.  Why:
        # a *hard* veto (reject whenever the hint isn't confirmed) breaks
        # detection on any machine where OCR can't reliably read the game text —
        # every genuine screen then gets vetoed and the script stalls on every
        # step (a real regression report).  So by default OCR can only *confirm*
        # (promote a weak pixel match), never block one; the overlay
        # capture-exclusion (see overlay.py) handles the common ghost cause.
        # Users who still see phantom matches on the game scene itself and whose
        # OCR reads their UI text well can enable `detector_ocr_veto`.
        self._ocr_veto: bool = bool(
            self.cfg.get("detector_ocr_veto", False))
        # When the veto is on and triggers, cap the score to this (below the
        # 0.45 soft-threshold floor) so the coincidental match can't fire.
        self._ocr_veto_ceiling: float = float(
            self.cfg.get("detector_ocr_veto_ceiling", 0.40))
        self._ocr_confirm_score: float = float(
            self.cfg.get("detector_ocr_confirm_score", 0.85))
        self._ocr_cache_duration: float = float(
            self.cfg.get("detector_ocr_cache_duration", 5.0))
        self._ocr_cache_pixel_min: float = float(
            self.cfg.get("detector_ocr_cache_pixel_min", 0.15))
        # Cache of recent OCR confirmations per key — (timestamp, text).
        # Lets us bridge the cooldown gap so the stability filter still
        # passes on the frame(s) where OCR is cooling down.
        self._ocr_confirmed: dict[str, tuple[float, str]] = {}
        # Cache prepared (gray, edge) versions of each template — keyed by
        # id(template) — to skip equalizeHist + Canny on every frame.
        self._template_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        # Pre-warm OCR in the background so the first detection call doesn't
        # eat the 1–2 s onnxruntime model-load cost.
        threading.Thread(
            target=self._ocr._ensure_loaded, daemon=True).start()

    def _prepared_template(
            self, template: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Returns (gray, edges), cached per id(template)."""
        cache_key = id(template)
        cached = self._template_cache.get(cache_key)
        if cached is None:
            cached = (_prepare_gray(template), _prepare_edges(template))
            self._template_cache[cache_key] = cached
        return cached

    def set_template_roi(self, key: str, roi):
        """Register a custom detection ROI (x, y, w, h as fractions of the frame)
        for a template — overrides the geometry box and DEFAULT_ROIS in detect().
        Used directly (no aspect remap): it's captured on the user's own frame, so
        it's already correct for their aspect. No-op on malformed input."""
        try:
            x, y, w, h = (float(v) for v in roi)
        except (TypeError, ValueError):
            return
        if w <= 0 or h <= 0:
            return
        self._custom_rois[key] = (x, y, w, h)

    def set_template_geometry(self, key: str, box, cap_w: int, cap_h: int):
        """Register a template's capture box (x, y, w, h on a cap_w×cap_h
        screen) so detect() uses an anchor-aware, resolution-adaptive ROI for
        it instead of DEFAULT_ROIS. No-op on incomplete geometry."""
        try:
            x, y, w, h = box
        except (TypeError, ValueError):
            return
        if w <= 0 or h <= 0 or cap_w <= 0 or cap_h <= 0:
            return
        self._geom[key] = {"box": (int(x), int(y), int(w), int(h)),
                           "cap_w": int(cap_w), "cap_h": int(cap_h)}

    def _geom_roi(self, key: str, frame_w: int, frame_h: int):
        """Anchor-aware ROI (ratio tuple) from a registered capture box, scaled
        to the live frame. Returns None if the key has no geometry. Scales by
        height (UI scales with vertical resolution, matching load_template) and
        anchors x/y to the nearest edge, then pads by detector_geom_variance."""
        g = self._geom.get(key)
        if g is None:
            return None
        bx, by, bw, bh = g["box"]
        cap_w, cap_h = g["cap_w"], g["cap_h"]
        if key in _GEOM_EDGE_KEYS:
            # Edge-anchored HUD: scale by height, anchor to the nearest screen
            # edge (the timer/HUD stays glued to the edge on any aspect).
            scale = frame_h / cap_h
            x = _scale_by_anchor(bx, cap_w, frame_w, scale)
            y = _scale_by_anchor(by, cap_h, frame_h, scale)
            w = bw * scale
            h = bh * scale
        else:
            # Centred-16:9 menu element: map the box through the content box of
            # BOTH the capture and the live frame, so the pillarbox/letterbox
            # offset is handled across aspect changes — e.g. a 5120x2160
            # ultrawide capture (menu pillarboxed ~640px in) used on a 1920x1080
            # 16:9 screen would otherwise land the ROI ~320px off and miss. The
            # element's fraction WITHIN the capture box is preserved into the
            # live box. (capture box ≥16:9 → height-limited → scale == frame_h/
            # cap_h, matching load_template's height-based template scaling.)
            ccx, ccy, ccw, cch = _content_box(cap_w, cap_h)
            lcx, lcy, lcw, lch = _content_box(frame_w, frame_h)
            sx = lcw / ccw if ccw else 1.0     # == lch/cch (both 16:9)
            x = lcx + (bx - ccx) * sx
            y = lcy + (by - ccy) * sx
            w = bw * sx
            h = bh * sx
        vx = frame_w * self._geom_variance
        vy = frame_h * self._geom_variance
        rx = max(0.0, x - vx)
        ry = max(0.0, y - vy)
        rw = min(frame_w - rx, w + 2 * vx)
        rh = min(frame_h - ry, h + 2 * vy)
        if rw <= 0 or rh <= 0:
            return None
        return (rx / frame_w, ry / frame_h, rw / frame_w, rh / frame_h)

    def detect(self, frame: np.ndarray, key: str, template: np.ndarray,
               threshold: float, stable: bool = True) -> MatchResult:
        # Prefer a geometry-derived ROI (anchor-aware, from the template's own
        # capture box) when available; else the hand-tuned DEFAULT_ROIS. The
        # geometry ROI already accounts for aspect ratio, so it bypasses the
        # 16:9 _roi_for_frame remap.
        # Priority: custom ROI (user-drawn, used as-is) > geometry box >
        # DEFAULT_ROIS. The custom ROI bypasses the 16:9 _roi_for_frame remap
        # for the same reason geometry does — it was captured on this frame.
        roi = self._custom_rois.get(key)
        if roi is None:
            roi = self._geom_roi(key, frame.shape[1], frame.shape[0]) \
                if self._geom_roi_on else None
        if roi is None:
            roi = self._roi_for_frame(
                key, DEFAULT_ROIS.get(key), frame.shape[1], frame.shape[0])
        roi_result = self._detect_in_area(
            frame, key, template, threshold, roi, "roi", stable)
        # Record the latest detection (always — cheap) so the F12 report can
        # render an annotated snapshot even when debug snapshots are off.
        _record_detect(frame, key, roi, roi_result,
                       max(self._min_thresh, threshold * 0.92))
        if self._debug:
            self.save_debug(frame, key, roi, roi_result, threshold)
        if roi_result.matched:
            return roi_result

        # ROI-only mode (default): elements are fixed-position within their ROI,
        # so the full-screen fallback is pure cost — skip it entirely. This is
        # what makes detection fast enough to react promptly (see _roi_only).
        if self._roi_only:
            return roi_result

        # Skip the costly full-screen fallback on stable (wait_for) checks
        # where the ROI score is clearly low — see _should_run_full. Single
        # shot detect (stable=False) always runs it so click ops never miss.
        if stable and not self._should_run_full(key, roi_result.score):
            return roi_result

        full_result = self._detect_in_area(
            frame, key, template, threshold, None, "full", False)
        # We trust DEFAULT_ROIS, so the full-screen fallback is discounted to
        # keep ROI hits ranked above coincidental matches elsewhere on screen.
        full_result.score *= 0.94
        full_result.matched = (
            self._stable_match(f"{key}:full", full_result.score, threshold)
            if stable else full_result.score >= max(self._min_thresh, threshold * 0.92)
        )
        return full_result

    def _roi_for_frame(self, key: str, roi: Optional[Rect],
                       frame_w: int, frame_h: int) -> Optional[Rect]:
        """Remap a 16:9-tuned ROI onto a non-16:9 screen — per element anchor.

        Forza anchors UI two different ways on ultrawide:
          • **Menus/dialogs** (e.g. start_menu) live in a **centred 16:9 box**.
          • **In-game HUD** (e.g. the race timer `racing`/時間) anchors to the
            **screen edges**, OUTSIDE that box.
        So `_ROI_BOX_KEYS` map their ROI *into the centred box* (tight — avoids
        look-alike false matches, needed for start_menu which matched the
        loading screen at ~85% on a full-width band); every other key uses a
        **full-axis band** (so edge-anchored HUD is still found wherever it
        sits). Reduces to the original ROI when the screen is ~16:9.
        """
        if roi is None or not self._roi_aspect_fix:
            return roi
        x, y, w, h = roi
        ref = REF_ASPECT
        aspect = frame_w / max(1, frame_h)
        box = key in _ROI_BOX_KEYS
        if aspect > ref * (1 + self._roi_aspect_tol):       # ultrawide
            if not box:
                return (0.0, y, 1.0, h)                     # full-width band
            bw = (frame_h * ref) / frame_w
            bx = (1.0 - bw) / 2.0
            return (bx + x * bw, y, w * bw, h)              # centred box (x)
        if aspect < ref * (1 - self._roi_aspect_tol):       # taller than 16:9
            if not box:
                return (x, 0.0, w, 1.0)                     # full-height band
            bh = (frame_w / ref) / frame_h
            by = (1.0 - bh) / 2.0
            return (x, by + y * bh, w, h * bh)              # centred box (y)
        return roi

    def _should_run_full(self, key: str, roi_score: float) -> bool:
        """Whether to run the expensive full-screen fallback this check.

        True when the ROI score suggests the element may be present but
        drifted (>= gate), or on a periodic safety sweep so drift outside the
        ROI is still caught within `_full_sweep_every` checks. Otherwise the
        full search is skipped — it's the dominant cost while idly waiting.
        """
        if roi_score >= self._full_gate_score:
            return True
        n = self._full_sweep_every
        if n <= 1:
            return True   # gating disabled
        c = self._full_sweep_counter.get(key, 0) + 1
        self._full_sweep_counter[key] = c
        return (c % n) == 0

    def _reset_match_state(self, key: str):
        """Drop stability history + OCR confirmation for `key` so a fresh
        wait_for must see genuinely consecutive frames and can't fire on scores
        left over from a previous loop/wait. Without this, the stability filter
        carries state across loops: loop 1 (empty history) needs real
        consecutive frames, but loops 2+ start with the prior loop's high scores
        still in history, so a single transient/look-alike frame satisfies the
        'N consecutive' rule and fires early — which then desyncs the flow and
        makes the next step's detection fail. (Detection should be stateless
        per wait — every loop the same.)"""
        self._history.pop(f"{key}:roi", None)
        self._history.pop(f"{key}:full", None)
        self._ocr_confirmed.pop(key, None)
        # Also clear the OCR cooldown so the first frame of a fresh wait can run
        # OCR immediately — otherwise a stale cooldown from this key's previous
        # wait could veto a genuine screen (no cache yet) until it expires.
        self._ocr_last_run.pop(key, None)

    def wait_for(self, frame_cb: Callable[[], np.ndarray], key: str,
                 template: np.ndarray, threshold: float,
                 stop_cb: Callable[[], bool], interval: float,
                 timeout: float = float("inf"),
                 on_warn: Callable[[MatchResult], None] | None = None) -> MatchResult:
        self._reset_match_state(key)   # start each wait with a clean slate
        start = time.time()
        warned = False
        best = MatchResult(False, 0.0, 0.0, (0, 0), 1.0, "none")
        while time.time() - start < timeout:
            if stop_cb():
                return best
            result = self.detect(frame_cb(), key, template, threshold)
            if result.score > best.score:
                best = result
            if result.matched:
                return result
            if not warned and time.time() - start >= 10.0:
                warned = True
                if on_warn:
                    on_warn(best)
            time.sleep(interval)
        return best

    def _detect_in_area(self, frame: np.ndarray, key: str, template: np.ndarray,
                        threshold: float, roi: Optional[Rect],
                        source: str, stable: bool) -> MatchResult:
        area, off_x, off_y = _clip_roi(frame, roi)
        soft_threshold = max(self._min_thresh, threshold * 0.92)

        gray_area = _prepare_gray(area)
        gray_tpl, edge_tpl = self._prepared_template(template)

        # Text templates (those with OCR hints) don't benefit from edge matching
        # — anti-aliasing makes text edges noisy — and the game UI renders at a
        # fixed scale, so 3 scale variants suffice. This drops from 14
        # matchTemplate calls (7 scales × 2 channels) to 3, ~4–5× faster on the
        # common path. Non-text templates use the full 7-scale + Canny pipeline.
        # `_force_edges` restores edges for all templates if ever needed.
        key_is_text = key in TEXT_TEMPLATES
        use_edges = self._force_edges or not key_is_text
        scales = self._text_scales if key_is_text else self.scales

        gray_conf, gray_loc, gray_scale = _best_template_match(
            gray_area, gray_tpl, scales)
        if use_edges:
            edge_area = _prepare_edges(area)
            edge_conf, _, _ = _best_template_match(edge_area, edge_tpl, scales)
            image_score = (gray_conf * 0.62) + (edge_conf * 0.28)
        else:
            image_score = gray_conf

        # OCR gate (text templates with hints only; gated by detector_enable_ocr
        # inside _ocr_bonus). OCR is a first-class confirmation signal, not a
        # +0.10 bonus — pixel matching gives location/fast-path, but text content
        # is what's invariant across hardware. The result is cached for
        # _ocr_cooldown seconds so frames within the cooldown still benefit
        # (keeps the stability filter intact); cached confirms only apply when
        # image_score >= _ocr_cache_pixel_min (safeguard vs the screen changing).
        ocr_text = ""
        has_hints = key in OCR_HINTS

        # For text templates in Default mode, OCR is a first-class CONFIRMATION
        # signal: pixel matching of game UI text is fragile across hardware (GPU
        # AA, HDR, font hinting all change pixels), so finding the hint text
        # promotes a weak pixel match to a confident one. In the decision band
        # (skip_below ≤ score < skip_above) we run OCR (or use a cached confirm)
        # and, if the hint is present, promote to _ocr_confirm_score.
        #   image_score >= skip_above → trust the pixel match, skip OCR
        #   image_score <  skip_below → almost certainly absent, skip OCR
        #   in between                → OCR confirms (promote) if hint present
        # A confirmation is cached per key for _ocr_cache_duration so the OCR
        # cooldown doesn't break the stability filter.
        #
        # VETO (reject) is DEFAULT OFF (`detector_ocr_veto`).  A *hard* veto —
        # rejecting whenever the hint isn't confirmed — breaks detection on any
        # machine where OCR can't reliably read the game text: every genuine
        # screen gets vetoed and the script stalls on every step (a real
        # regression).  So by default OCR can only CONFIRM, never block, and a
        # screen that OCR can't confirm keeps its pixel score (original, working
        # behaviour).  When the veto IS enabled it only fires on a POSITIVE
        # contradiction — OCR actually read text (`ocr_text` non-empty) that
        # doesn't contain the hint — never on a silent/failed OCR.  If no OCR
        # backend is installed the whole gate is skipped (pixel-only).
        if (key_is_text and has_hints
                and self._ocr_skip_below <= image_score < self._ocr_skip_above
                and self._ocr.available()):
            now = time.time()
            cached = self._ocr_confirmed.get(key)
            cache_valid = (
                cached is not None
                and (now - cached[0]) < self._ocr_cache_duration
                and image_score >= self._ocr_cache_pixel_min
            )
            if cache_valid:
                # Recent OCR confirmation still applies — skip the OCR call.
                image_score = max(image_score, self._ocr_confirm_score)
                ocr_text = cached[1] + " [cached]"
            else:
                bonus, ocr_text = self._ocr_bonus(area, key)
                if bonus > 0:
                    # Hint text confirmed on screen — genuine match.
                    image_score = max(image_score, self._ocr_confirm_score)
                    self._ocr_confirmed[key] = (now, ocr_text)
                elif self._ocr_veto and ocr_text.strip():
                    # Opt-in veto, and only on a positive contradiction: OCR
                    # read real text that isn't the hint → coincidental pixel
                    # match → cap below threshold. Never vetoes a silent OCR.
                    image_score = min(image_score, self._ocr_veto_ceiling)

        score = image_score
        loc = (gray_loc[0] + off_x, gray_loc[1] + off_y)
        matched = (score >= soft_threshold if not stable
                   else self._stable_match(f"{key}:{source}", score, threshold))
        return MatchResult(matched, score, gray_conf, loc, gray_scale, source,
                           ocr_text=ocr_text)

    def _ocr_bonus(self, area: np.ndarray, key: str) -> tuple[float, str]:
        hints = OCR_HINTS.get(key)
        if not hints or not self.cfg.get("detector_enable_ocr", False):
            return 0.0, ""
        # Cooldown gate: skip OCR if it ran too recently for this key.
        # Prevents repeated 100–300 ms rapidocr calls when the score is stuck
        # in the borderline zone during a long failed-detection streak.
        if self._ocr_cooldown > 0:
            now = time.time()
            if now - self._ocr_last_run.get(key, 0.0) < self._ocr_cooldown:
                return 0.0, ""
            self._ocr_last_run[key] = now
        text = self._ocr.read(area)
        if not text:
            return 0.0, ""
        norm = _normalize_text(text)
        if any(_normalize_text(hint) in norm for hint in hints):
            return 0.10, text.strip()
        return 0.0, text.strip()

    def _stable_match(self, key: str, score: float, threshold: float) -> bool:
        needed = max(1, self.stable_frames)
        hist = self._history.setdefault(key, [])
        hist.append(score)
        del hist[:-needed]
        if len(hist) < needed:
            return False
        soft_threshold = max(self._min_thresh, threshold * 0.92)
        return all(v >= soft_threshold for v in hist)

    def save_debug(self, frame: np.ndarray, key: str, roi: Optional[Rect],
                   result: MatchResult, threshold: float):
        """Save an annotated detection snapshot to debug_dir/<key>.png (overwritten
        each call, throttled). Draws on a COPY of the captured frame (post-crop,
        so a wrong letterbox crop is visible too):
          - YELLOW box  = the ROI that was searched ("where it looked")
          - GREEN/RED cross = best-match centre, green if matched else red
          - header bar = key, score, soft-threshold, source, MATCH/miss, OCR text
        For diagnosing why a step mis-detected. No-op unless debug_dir is set."""
        if not self.debug_dir or frame is None or getattr(frame, "size", 0) == 0:
            return
        now = time.time()
        if now - self._debug_last.get(key, 0.0) < 0.2:   # throttle I/O storms
            return
        self._debug_last[key] = now
        try:
            os.makedirs(self.debug_dir, exist_ok=True)
            img = frame.copy()
            soft = max(self._min_thresh, threshold * 0.92)
            _draw_debug(img, key, roi, result, soft)
            h, w = img.shape[:2]
            if w > 1280:   # downscale for small, fast-to-write files
                img = cv2.resize(img, (1280, int(h * 1280.0 / w)))
            ok, buf = cv2.imencode(".png", img)
            if ok:
                # tofile (not imwrite) so non-ASCII / CJK paths work.
                buf.tofile(os.path.join(self.debug_dir, f"{key}.png"))
        except Exception:
            pass
