"""CPU-aware OCR runtime presets.

FAFE keeps the user-facing OCR setting simple (ON/OFF). This module chooses the
runtime shape behind that switch so hybrid Intel mobile/desktop CPUs get a
cooler OCR path without exposing another setting.
"""

from __future__ import annotations

import copy
import platform
import re


PROFILE_BALANCED = "balanced"
PROFILE_LOW_IMPACT = "low_impact"


_PROFILE_DEFAULTS = {
    PROFILE_BALANCED: {
        "detector_ocr_cooldown": 1.0,
        "detector_ocr_cache_duration": 5.0,
        "detector_ocr_target_h": 640,
        "detector_ocr_max_scale": 3.0,
        "detector_ocr_prewarm": True,
    },
    PROFILE_LOW_IMPACT: {
        "detector_ocr_cooldown": 3.0,
        "detector_ocr_cache_duration": 8.0,
        "detector_ocr_target_h": 480,
        "detector_ocr_max_scale": 2.0,
        "detector_ocr_prewarm": False,
    },
}


def get_cpu_name() -> str:
    """Best-effort local CPU name, with Windows registry first."""
    try:
        import winreg

        path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if value:
                return str(value).strip()
    except Exception:
        pass
    try:
        return platform.processor().strip()
    except Exception:
        return ""


def _normalized_cpu_name(cpu_name: str | None) -> str:
    return re.sub(r"\s+", " ", str(cpu_name or "")).strip().casefold()


def profile_for_cpu(cpu_name: str | None = None) -> str:
    """Map known stutter-prone hybrid Intel CPUs to the low-impact OCR profile."""
    name = _normalized_cpu_name(cpu_name if cpu_name is not None else get_cpu_name())
    if not name:
        return PROFILE_BALANCED
    if "intel" not in name:
        return PROFILE_BALANCED
    if re.search(r"\b1[234](?:th)?\s+gen\b", name):
        return PROFILE_LOW_IMPACT
    if re.search(r"\bi[3579]-1[234]\d{3}[a-z]*\b", name):
        return PROFILE_LOW_IMPACT
    if "core ultra" in name:
        return PROFILE_LOW_IMPACT
    return PROFILE_BALANCED


def profile_defaults(profile: str) -> dict:
    """Return a copy of the defaults for a profile name."""
    return copy.deepcopy(_PROFILE_DEFAULTS.get(profile, _PROFILE_DEFAULTS[PROFILE_BALANCED]))


def profile_label(profile: str) -> str:
    if profile == PROFILE_LOW_IMPACT:
        return "Low Impact"
    return "Balanced"


def apply_ocr_profile_defaults(cfg: dict | None, cpu_name: str | None = None) -> dict:
    """Return a config copy with CPU-profile detector defaults filled in.

    Existing detector_* values are preserved so dev/testing overrides in
    config.json still win over the automatic preset.
    """
    out = dict(cfg or {})
    detected = cpu_name if cpu_name is not None else get_cpu_name()
    requested = str(out.get("ocr_cpu_profile") or "").strip().lower()
    profile = requested if requested in _PROFILE_DEFAULTS else profile_for_cpu(detected)
    out["ocr_cpu_profile"] = profile
    out["ocr_cpu_name"] = detected or "Unknown CPU"
    for key, value in profile_defaults(profile).items():
        out.setdefault(key, value)
    return out


def describe_effective_profile(cfg: dict | None, cpu_name: str | None = None) -> str:
    effective = apply_ocr_profile_defaults(cfg, cpu_name=cpu_name)
    cpu = str(effective.get("ocr_cpu_name") or "Unknown CPU")
    if len(cpu) > 72:
        cpu = cpu[:69].rstrip() + "..."
    return f"OCR preset: {profile_label(effective.get('ocr_cpu_profile'))} ({cpu})"
