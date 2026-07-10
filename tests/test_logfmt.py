import unittest
from dataclasses import dataclass


@dataclass
class _R:
    score: float
    source: str
    ocr_text: str = ""


class LogfmtTests(unittest.TestCase):
    def test_detail_shows_score_where_and_ocr(self):
        import logfmt
        s = logfmt.detail(_R(0.88, "roi", "...and Spin Again"), "en")
        self.assertEqual(s, "88% in search area, read '...and Spin Again'")

    def test_detail_plain_words_for_source(self):
        import logfmt
        self.assertIn("full screen", logfmt.detail(_R(0.72, "full"), "en"))
        self.assertNotIn("roi", logfmt.detail(_R(0.72, "roi"), "en"))

    def test_no_ocr_no_read_suffix(self):
        import logfmt
        self.assertEqual(logfmt.detail(_R(0.5, "roi"), "en"), "50% in search area")

    def test_best_detail_prefix(self):
        import logfmt
        self.assertTrue(logfmt.best_detail(_R(0.41, "roi"), "en").startswith("best "))

    def test_long_ocr_is_trimmed(self):
        import logfmt
        s = logfmt.detail(_R(0.9, "roi", "x" * 80), "en")
        # trimmed to _OCR_MAX incl. ellipsis, so the read segment stays short
        self.assertLess(len(s), 70)

    def test_ocr_text_with_braces_does_not_break_format(self):
        import logfmt
        # OCR could return braces; they must be treated as data, not format spec
        s = logfmt.detail(_R(0.9, "roi", "{weird}"), "en")
        self.assertIn("{weird}", s)


if __name__ == "__main__":
    unittest.main()
