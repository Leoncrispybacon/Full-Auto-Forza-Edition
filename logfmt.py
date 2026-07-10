"""logfmt.py - shared, localized formatting for automation step logs.

Turns a detector MatchResult into a human-readable detail string so every
module logs *what it detected* consistently: the confidence, WHERE it looked
(plain words, not "roi"/"full"), and the OCR text actually read when OCR ran.
Used in place of the ad-hoc f"{r.score:.0%}, {r.source}" strings the modules
used to build inline.
"""
from app_lang import t as _at

_OCR_MAX = 40   # trim long OCR reads so one line can't flood the log


def _where(source: str, lang: str) -> str:
    """Plain-language name for a MatchResult.source ('roi'/'full' -> words)."""
    if source == "roi":
        return _at("det_where_roi", lang)
    if source == "full":
        return _at("det_where_full", lang)
    return source or "?"


def _read_suffix(result, lang: str) -> str:
    """', read '<ocr>'' when OCR read something, else '' (trimmed)."""
    text = (getattr(result, "ocr_text", "") or "").strip()
    if not text:
        return ""
    if len(text) > _OCR_MAX:
        text = text[:_OCR_MAX - 1] + "…"
    return _at("det_read", lang, text=text)


def detail(result, lang: str) -> str:
    """'88% in search area, read '...and spin again'' - confidence, where it
    matched, and any OCR text. Goes inside the existing '(...)' in log lines."""
    return _at("det_detail", lang,
               pct=f"{result.score:.0%}",
               where=_where(result.source, lang)) + _read_suffix(result, lang)


def best_detail(result, lang: str) -> str:
    """detail() framed as the BEST attempt so far - for not-found lines."""
    return _at("det_best", lang, detail=detail(result, lang))
