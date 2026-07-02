from pathlib import Path
import unittest


class AutoOcrBorderlineTests(unittest.TestCase):
    def test_borderline_band_helper(self):
        import detector

        self.assertTrue(detector._auto_ocr_borderline(0.66, 0.70, 0.05))
        self.assertFalse(detector._auto_ocr_borderline(0.64, 0.70, 0.05))
        self.assertFalse(detector._auto_ocr_borderline(0.70, 0.70, 0.05))

    def test_detector_persists_and_logs_auto_ocr(self):
        source = Path("detector.py").read_text(encoding="utf-8")

        self.assertIn("detector_auto_ocr_on_borderline", source)
        self.assertIn("detector_auto_ocr_hits", source)
        self.assertIn("detector_auto_ocr_margin", source)
        self.assertIn("def _auto_enable_ocr", source)
        self.assertIn('cfg["detector_enable_ocr"] = True', source)
        self.assertIn("_auto_ocr_cb", source)
        self.assertIn("will likely need OCR enabled for every run", source)

    def test_threshold_floor_matches_slider_minimum(self):
        detector_source = Path("detector.py").read_text(encoding="utf-8")
        ui_source = Path("webui/app.js").read_text(encoding="utf-8")

        self.assertIn('get("detector_min_threshold", 0.70)', detector_source)
        self.assertIn("slider.min = '0.70'", ui_source)

    def test_ocr_default_lower_gate_is_not_garbage_low(self):
        import detector

        d = detector.ScreenDetector({"detector_enable_ocr": True})

        self.assertEqual(d._ocr_skip_below, 0.30)

    def test_wheelspin_collect_uses_full_roi_ocr(self):
        import detector

        d = detector.ScreenDetector({"detector_enable_ocr": True})

        self.assertIn("wheelspin_collect", d._full_roi_ocr_keys)
        self.assertIn("wheelspin_collect_final", d._full_roi_ocr_keys)

    def test_automations_forward_auto_ocr_note_to_logs(self):
        for path in ("race.py", "buy.py", "wheelspin.py", "mastery.py", "full_auto.py"):
            with self.subTest(path=path):
                if path == "full_auto.py" and not Path(path).exists():
                    continue
                source = Path(path).read_text(encoding="utf-8")
                self.assertIn("on_auto_ocr=log_cb", source)


if __name__ == "__main__":
    unittest.main()
