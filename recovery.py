from dataclasses import dataclass
from typing import Callable, Union

from app_lang import t as _at


@dataclass(frozen=True)
class RouteAttempt:
    ok: bool
    purpose_done: bool = False


RouteReturn = Union[bool, RouteAttempt]
SAFETY_ANCHORS = ("anna", "collection_log")
_trigger_callback = None
_log_lang = "en"


def set_trigger_callback(callback):
    global _trigger_callback
    _trigger_callback = callback


def set_log_lang(lang):
    global _log_lang
    _log_lang = lang or "en"


def trigger_report(label: str) -> None:
    if _trigger_callback is not None:
        _trigger_callback(label)


def _as_attempt(value: RouteReturn) -> RouteAttempt:
    if isinstance(value, RouteAttempt):
        return value
    return RouteAttempt(ok=bool(value), purpose_done=False)


def route_retries(cfg: dict, default: int = 1) -> int:
    try:
        return max(0, int(cfg.get("recovery_route_retries", default)))
    except (TypeError, ValueError):
        return default


def backtrack_anchor_keys(route_keys, expected=None) -> tuple:
    keys = tuple(route_keys)
    if expected in keys:
        return tuple(reversed(keys[:keys.index(expected) + 1]))
    return tuple(reversed(keys))


def load_recovery_safety_templates(detector, cfg: dict, tpl_lang: str,
                                   width: int, height: int) -> dict:
    """Load universal route recovery anchors.

    `anna` means the open world is visible. `collection_log` means the main menu
    is visible. Both are safe because repeated Esc eventually reaches one of
    these states, and every major route can restart from the main menu.
    """
    import config
    from capture import load_template

    prefer_ref = cfg.get("template_prefer_reference", True)
    sources = {
        "anna": config.get_full_auto_templates(config.REFERENCE_RES, tpl_lang),
        "collection_log": config.get_buy_templates(config.REFERENCE_RES, tpl_lang),
    }
    out = {}
    for key in SAFETY_ANCHORS:
        folder = sources[key]
        try:
            img, _scale, meta = load_template(
                folder, key, width, height, grayscale=True,
                ref_folder=folder, prefer_ref=prefer_ref)
        except FileNotFoundError:
            continue
        box = meta.get("box")
        if box:
            detector.set_template_geometry(
                key, box, meta.get("screen_width", width),
                meta.get("screen_height", height))
        if meta.get("roi"):
            detector.set_template_roi(key, meta["roi"], *(meta.get("roi_dims") or (meta.get("screen_width", 0), meta.get("screen_height", 0))))
        out[key] = img
    return out


def recover_to_main_menu_from_safety_anchor(anchor: str | None,
                                            press_escape: Callable[[], None],
                                            wait: Callable[[], None],
                                            detect_anchor: Callable[[], str | None] | None = None) -> bool:
    if anchor == "collection_log":
        return True
    if anchor != "anna":
        return False
    press_escape()
    wait()
    if detect_anchor is None:
        return True
    return detect_anchor() in ("collection_log", "anna")


def run_stage_route(label: str,
                    route_fn: Callable[[], RouteReturn],
                    stop: Callable[[], bool],
                    log_cb: Callable[[str], None],
                    max_retries: int = 1,
                    recover_fn: Callable[[], bool] | None = None,
                    trigger_cb: Callable[[str], None] | None = None,
                    on_recover: Callable[[], None] | None = None) -> bool:
    """Run one known stage route with bounded retries.

    The helper never presses keys itself. It re-runs the caller's
    detection-gated route, with an optional caller-owned recovery action between
    attempts, so recovery stays inside the current stage route.
    Callers can return RouteAttempt(purpose_done=True) when the loop's real
    work is already complete; that prevents repeating a completed buy/spin/race
    unit just because a later hand-off failed.
    """
    max_retries = max(0, int(max_retries or 0))
    failures_since_anchor = 0
    reported = False
    while True:
        if stop():
            return False
        result = _as_attempt(route_fn())
        if result.ok or result.purpose_done:
            return True
        if stop():
            return False
        if failures_since_anchor < max_retries:
            failures_since_anchor += 1
            # Recovery is activating: the screen is in an unexpected state, so
            # drop any stale OCR confirm cache before re-anchoring (preventive —
            # a leftover confirm could false-match a wrong anchor).
            if on_recover is not None:
                on_recover()
            log_cb(_at("log_route_retry", _log_lang, label=label,
                       n=failures_since_anchor, max=max_retries))
            if not reported:
                reported = True
                if trigger_cb is not None:
                    trigger_cb(f"{label} recovery")
                else:
                    trigger_report(f"{label} recovery")
            if recover_fn is not None:
                if not recover_fn():
                    log_cb(_at("log_route_recovery_action_failed", _log_lang,
                               label=label))
                    return False
                failures_since_anchor = 0
                log_cb(_at("log_route_recovery_anchored", _log_lang,
                           label=label))
            continue
        log_cb(_at("log_route_recovery_failed", _log_lang, label=label))
        return False
