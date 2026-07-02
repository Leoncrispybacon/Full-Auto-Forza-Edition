"""Windows HDR / Advanced Color detection.

FAFE's pixel templates are SDR-authored. When the game monitor is in HDR,
Windows' tonemapping can shift text/contrast enough that OCR confirmation is a
better fallback, so startup can auto-enable OCR.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


QDC_ONLY_ACTIVE_PATHS = 0x00000002
ERROR_SUCCESS = 0
ERROR_INSUFFICIENT_BUFFER = 122
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9
DISPLAYCONFIG_PATH_MODE_IDX_INVALID = 0xFFFFFFFF
ADVANCED_COLOR_ENABLED = 0x2


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD),
                ("HighPart", wintypes.LONG)]


class DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", wintypes.UINT),
                ("Denominator", wintypes.UINT)]


class DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID),
                ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT),
                ("statusFlags", wintypes.UINT)]


class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID),
                ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT),
                ("outputTechnology", wintypes.UINT),
                ("rotation", wintypes.UINT),
                ("scaling", wintypes.UINT),
                ("refreshRate", DISPLAYCONFIG_RATIONAL),
                ("scanLineOrdering", wintypes.UINT),
                ("targetAvailable", wintypes.BOOL),
                ("statusFlags", wintypes.UINT)]


class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
                ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
                ("flags", wintypes.UINT)]


class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG),
                ("y", wintypes.LONG)]


class DISPLAYCONFIG_2DREGION(ctypes.Structure):
    _fields_ = [("cx", wintypes.UINT),
                ("cy", wintypes.UINT)]


class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(ctypes.Structure):
    _fields_ = [("pixelRate", ctypes.c_uint64),
                ("hSyncFreq", DISPLAYCONFIG_RATIONAL),
                ("vSyncFreq", DISPLAYCONFIG_RATIONAL),
                ("activeSize", DISPLAYCONFIG_2DREGION),
                ("totalSize", DISPLAYCONFIG_2DREGION),
                ("videoStandard", wintypes.UINT),
                ("scanLineOrdering", wintypes.UINT)]


class DISPLAYCONFIG_TARGET_MODE(ctypes.Structure):
    _fields_ = [("targetVideoSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO)]


class DISPLAYCONFIG_SOURCE_MODE(ctypes.Structure):
    _fields_ = [("width", wintypes.UINT),
                ("height", wintypes.UINT),
                ("pixelFormat", wintypes.UINT),
                ("position", POINTL)]


class RECTL(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG)]


class DISPLAYCONFIG_DESKTOP_IMAGE_INFO(ctypes.Structure):
    _fields_ = [("PathSourceSize", POINTL),
                ("DesktopImageRegion", RECTL),
                ("DesktopImageClip", RECTL)]


class DISPLAYCONFIG_MODE_UNION(ctypes.Union):
    _fields_ = [("targetMode", DISPLAYCONFIG_TARGET_MODE),
                ("sourceMode", DISPLAYCONFIG_SOURCE_MODE),
                ("desktopImageInfo", DISPLAYCONFIG_DESKTOP_IMAGE_INFO)]


class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    _fields_ = [("infoType", wintypes.UINT),
                ("id", wintypes.UINT),
                ("adapterId", LUID),
                ("mode", DISPLAYCONFIG_MODE_UNION)]


class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [("type", wintypes.UINT),
                ("size", wintypes.UINT),
                ("adapterId", LUID),
                ("id", wintypes.UINT)]


class DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
                ("value", wintypes.UINT),
                ("colorEncoding", wintypes.UINT),
                ("bitsPerColorChannel", wintypes.UINT)]


def maybe_enable_ocr_for_hdr(cfg: dict | None, hdr_enabled: bool) -> tuple[dict, bool]:
    """Return an updated config copy and whether OCR was changed."""
    out = dict(cfg or {})
    if hdr_enabled and not out.get("detector_enable_ocr", False):
        out["detector_enable_ocr"] = True
        return out, True
    return out, False


def is_hdr_enabled(monitor_index: int | None = None, monitors: list[dict] | None = None) -> bool:
    """Best-effort Windows HDR/Advanced Color detection.

    When `monitor_index` and `monitors` are supplied, prefer the matching display
    path by desktop rectangle. If that mapping cannot be made, fall back to any
    active HDR path. Non-Windows or API failures return False.
    """
    if os.name != "nt":
        return False
    try:
        paths, modes = _query_display_config()
        wanted = _monitor_rect(monitor_index, monitors)
        any_enabled = False
        matched_monitor = False
        for path in paths:
            enabled = _path_hdr_enabled(path)
            any_enabled = any_enabled or enabled
            if wanted is not None and _path_rect(path, modes) == wanted:
                matched_monitor = True
                return enabled
        return any_enabled if wanted is None or not matched_monitor else False
    except Exception:
        return False


def _query_display_config():
    user32 = ctypes.windll.user32
    path_count = wintypes.UINT()
    mode_count = wintypes.UINT()
    while True:
        err = user32.GetDisplayConfigBufferSizes(
            QDC_ONLY_ACTIVE_PATHS,
            ctypes.byref(path_count),
            ctypes.byref(mode_count),
        )
        if err != ERROR_SUCCESS:
            raise OSError(err)
        paths = (DISPLAYCONFIG_PATH_INFO * path_count.value)()
        modes = (DISPLAYCONFIG_MODE_INFO * mode_count.value)()
        topology = wintypes.UINT()
        err = user32.QueryDisplayConfig(
            QDC_ONLY_ACTIVE_PATHS,
            ctypes.byref(path_count),
            paths,
            ctypes.byref(mode_count),
            modes,
            ctypes.byref(topology),
        )
        if err == ERROR_INSUFFICIENT_BUFFER:
            continue
        if err != ERROR_SUCCESS:
            raise OSError(err)
        return list(paths)[:path_count.value], list(modes)[:mode_count.value]


def _path_hdr_enabled(path: DISPLAYCONFIG_PATH_INFO) -> bool:
    info = DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO()
    info.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO
    info.header.size = ctypes.sizeof(info)
    info.header.adapterId = path.targetInfo.adapterId
    info.header.id = path.targetInfo.id
    err = ctypes.windll.user32.DisplayConfigGetDeviceInfo(ctypes.byref(info))
    if err != ERROR_SUCCESS:
        return False
    return bool(info.value & ADVANCED_COLOR_ENABLED)


def _monitor_rect(monitor_index: int | None, monitors: list[dict] | None):
    if not monitor_index or not monitors:
        return None
    for mon in monitors:
        if int(mon.get("index", 0)) == int(monitor_index):
            return (int(mon["left"]), int(mon["top"]),
                    int(mon["width"]), int(mon["height"]))
    return None


def _path_rect(path: DISPLAYCONFIG_PATH_INFO, modes: list[DISPLAYCONFIG_MODE_INFO]):
    idx = path.sourceInfo.modeInfoIdx
    if idx == DISPLAYCONFIG_PATH_MODE_IDX_INVALID or idx >= len(modes):
        return None
    mode = modes[idx]
    src = mode.mode.sourceMode
    return (int(src.position.x), int(src.position.y),
            int(src.width), int(src.height))
