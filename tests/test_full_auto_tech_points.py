from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FullAutoTechPointsTests(unittest.TestCase):
    """Regression for the tech-point read false-match abort loop: a tech_points
    PIXEL match on the wrong screen (e.g. the Story '推薦內容' panel) must not be
    trusted as 'on the CARS tab' and abort the read — the NUMBER read is the
    real anchor."""

    def _source(self):
        return (ROOT / "full_auto.py").read_text(encoding="utf-8")

    def test_read_settles_then_ocr_reads_the_number(self):
        # The CARS tab slides in on arrival; read only after _POINTS_SETTLE so OCR
        # doesn't catch the mid-animation frame (which reads "推薦內容" placeholder
        # text instead of the number). tech_points is OCR-READ, never pixel-matched
        # (the number varies each run → a fixed-number pixel template scores ~0%),
        # so the number read is itself the cars-tab anchor.
        fn = self._source().split("def _read_points_on_cars_tab", 1)[1].split(
            "def _detect_safety_anchor", 1)[0]
        self.assertIn("_POINTS_SETTLE", fn)
        self.assertIn("_try_read_points()", fn)
        self.assertNotIn('_detect_on_frame(io.grab(), "tech_points")', fn)

    def test_no_pixel_match_abort_shortcut(self):
        # the fragile 'saw the pixel anchor -> abort before navigating' flag is gone
        self.assertNotIn("last_points_anchor_seen", self._source())

    def test_settle_constant_defined(self):
        self.assertIn("_POINTS_SETTLE", self._source())


if __name__ == "__main__":
    unittest.main()
