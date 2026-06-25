# ============================================================
#  roi_preview.py — DEBUG TOOL (not bundled in the build)
#  Overlays the detection ROI box(es) on a live capture so you
#  can check whether an ROI lines up with the on-screen element.
#
#  Usage (from the project folder, with the game running):
#      python roi_preview.py                  # default: grind_brand grind_car
#      python roi_preview.py grind_brand      # one key
#      python roi_preview.py cars_tab my_cars_header ...
#
#  It captures the SAME frame the detector sees (window capture +
#  letterbox crop), draws each key's ROI, and opens an annotated
#  PNG. Run it while the game is on the screen you want to check
#  (e.g. the Jump-to-Manufacturer menu for grind_brand, the brand
#  car list for grind_car) — a 3s countdown lets you switch back.
#
#  NOTE: this shows the DEFAULT_ROIS fallback ROI (no template
#  geometry is loaded), which is exactly what grind_brand /
#  grind_car use in production (their geometry is skipped). For
#  keys that DO use a capture geometry box, the live ROI may be
#  tighter than what's drawn here.
# ============================================================

import os
import sys
import time

import cv2
import numpy as np

import json

import config
from gameio import GameIO
from detector import ScreenDetector, DEFAULT_ROIS

_COUNTDOWN = 3
_COLORS = [(0, 255, 0), (0, 200, 255), (255, 120, 0), (200, 0, 255)]


def main(keys):
    cfg = config.load()
    io = GameIO(cfg, print)
    det = ScreenDetector(cfg)

    print(f"\nMode: {'window/background' if io.bg else 'foreground/monitor'} "
          f"— capture {io.width}x{io.height}"
          + (f" (letterbox-cropped from a larger client)" if io._crop else ""))
    print(f"Switch to the game screen you want to check. Capturing in "
          f"{_COUNTDOWN}s...")
    for i in range(_COUNTDOWN, 0, -1):
        print(f"  {i}")
        time.sleep(1)

    frame = io.grab()
    io.cleanup()
    if frame is None or frame.size == 0:
        print("ERROR: no frame captured.")
        return
    h, w = frame.shape[:2]
    out = frame.copy()

    # Look up saved ROI/geometry in the Full Auto custom folder so the preview
    # matches detection priority: custom "roi" > geometry "box" > DEFAULT_ROIS.
    try:
        fa_folder = config.get_full_auto_templates(
            "custom", config.resolve_template_lang(cfg))
    except Exception:
        fa_folder = None

    for idx, key in enumerate(keys):
        meta = {}
        if fa_folder:
            mp = os.path.join(fa_folder, f"{key}.json")
            if os.path.exists(mp):
                try:
                    with open(mp, encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    meta = {}
        if meta.get("roi"):                                  # user-drawn ROI
            # Route through the detector so the preview reflects the live-aspect
            # remap (same as detection), not the raw captured fractions.
            det.set_template_roi(key, meta["roi"],
                                 meta.get("screen_width", 0),
                                 meta.get("screen_height", 0))
            roi = det._custom_roi_for_frame(key, w, h); src = "custom roi"
        elif meta.get("box"):                                # geometry box
            bx, by, bw, bh = meta["box"]
            det.set_template_geometry(key, meta["box"],
                                      meta.get("screen_width", w),
                                      meta.get("screen_height", h))
            roi = det._geom_roi(key, w, h); src = "geometry"
        elif DEFAULT_ROIS.get(key) is not None:              # default fallback
            roi = det._roi_for_frame(key, DEFAULT_ROIS[key], w, h)
            src = "default"
        else:
            print(f"  {key}: no ROI (no saved roi/box and no DEFAULT_ROIS) — skipped")
            continue
        if roi is None:
            print(f"  {key}: ROI resolved to None — skipped")
            continue
        rx, ry, rw, rh = roi
        px, py = int(rx * w), int(ry * h)
        pw, ph = int(rw * w), int(rh * h)
        color = _COLORS[idx % len(_COLORS)]
        cv2.rectangle(out, (px, py), (px + pw, py + ph), color, 3)
        cv2.putText(out, f"{key} [{src}]", (px + 6, py + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
        print(f"  {key}: ROI = x{px} y{py} w{pw} h{ph}  (on {w}x{h})  [{src}]")

    path = os.path.join(config.BASE_DIR, "roi_preview.png")
    ok, buf = cv2.imencode(".png", out)            # imencode → file write = CJK-path safe
    if not ok:
        print("ERROR: failed to encode preview.")
        return
    with open(path, "wb") as f:
        f.write(np.asarray(buf).tobytes())
    print(f"\nSaved {path}")
    try:
        os.startfile(path)
    except Exception:
        pass


if __name__ == "__main__":
    main(sys.argv[1:] or ["grind_brand", "grind_car"])
