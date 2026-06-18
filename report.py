# ============================================================
#  report.py — One-press bug-report bundle.
#  Triggered by a hotkey (default F12). Produces a folder + zip
#  containing a game screenshot and the session logs + environment,
#  ready to drop into Discord.
# ============================================================

import os
import json
import zipfile
import platform
import datetime

import cv2

import config
from version import VERSION
from capture import grab_frame
from app_lang import t as _at


def _write_png(path: str, frame) -> bool:
    """Write a BGR frame to PNG via imencode rather than cv2.imwrite, which
    fails on non-ASCII paths (e.g. CJK usernames in the reports path)."""
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        return False
    with open(path, "wb") as f:
        f.write(buf.tobytes())
    return True


def generate_report(cfg: dict, monitor_index: int, logs: dict,
                    log_cb=None, status_cb=None) -> str:
    """Build the report bundle and return the zip path ('' / folder on
    failure). Runs synchronously — call it from a background thread.

    logs: {tab_label: [log lines]} snapshot taken on the UI side.
    """
    lang = cfg.get("lang", "en")
    log = log_cb or (lambda m: None)
    status = status_cb or (lambda m: None)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    reports = os.path.join(config.BASE_DIR, "reports")
    rdir = os.path.join(reports, f"FAFE_report_{ts}")
    os.makedirs(rdir, exist_ok=True)
    # Surface the whole process in the LOG (not just the status bar) so the user
    # sees it start and gets the final path.
    log(_at("report_started", lang))
    status(_at("report_generating", lang))

    # 1) Game screenshot. Prefer an ANNOTATED detection-debug frame from the
    # most recent detection (the frame FAFE last looked at, with the ROI it
    # searched, the best-match marker, and where the last click landed) — that's
    # far more useful for diagnosing a mis-detection than a plain grab. Falls
    # back to a plain monitor screenshot if no recent detection exists (idle /
    # detector never ran). mask_overlay=False so the plain grab shows the REAL
    # screen (incl. the overlay), not the detector's self-masked view.
    try:
        frame = None
        try:
            import detector
            frame = detector.render_report_image()
        except Exception:
            frame = None
        if frame is None:
            frame = grab_frame(monitor_index, mask_overlay=False)
        _write_png(os.path.join(rdir, "screenshot.png"), frame)
    except Exception as e:
        with open(os.path.join(rdir, "screenshot_error.txt"), "w",
                  encoding="utf-8") as f:
            f.write(repr(e))

    # 2) Session logs + environment + config snapshot
    try:
        with open(os.path.join(rdir, "log.txt"), "w", encoding="utf-8") as f:
            f.write("# FAFE bug report — contains your settings + basic system "
                    "info. Review before sharing publicly.\n\n")
            f.write(f"FAFE v{VERSION}\n")
            f.write(f"Generated : {ts}\n")
            f.write(f"OS        : {platform.platform()}\n")
            f.write(f"Machine   : {platform.machine()}\n")
            f.write(f"Processor : {platform.processor()}\n")
            f.write(f"Python    : {platform.python_version()}\n")
            f.write(f"Monitor   : index {monitor_index}\n")
            f.write("\n----- config.json -----\n")
            f.write(json.dumps(cfg, ensure_ascii=False, indent=2))
            f.write("\n\n----- session logs -----\n")
            for name, lines in logs.items():
                f.write(f"\n=== {name} ===\n")
                f.write("\n".join(lines) if lines else "(empty)")
                f.write("\n")
    except Exception as e:
        log(f"report: log.txt failed: {e!r}")

    # 3) Zip the folder for easy sharing
    zpath = os.path.join(reports, f"FAFE_report_{ts}.zip")
    try:
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in sorted(os.listdir(rdir)):
                zf.write(os.path.join(rdir, fn), fn)
    except Exception as e:
        log(f"report: zip failed: {e!r}")
        zpath = rdir   # fall back to handing over the folder

    log(_at("report_saved", lang, path=zpath))
    log(_at("report_privacy", lang))   # tell the user what's inside before sharing
    status(_at("report_saved", lang, path=zpath))
    try:
        os.startfile(reports)   # open the reports folder in Explorer
    except Exception:
        pass
    return zpath
