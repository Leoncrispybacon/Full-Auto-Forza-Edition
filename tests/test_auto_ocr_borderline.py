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

        # prewarm OFF: otherwise a real-OCR loader daemon lingers and, when its
        # import finalizes, overwrites sys.modules['rapidocr_onnxruntime'] —
        # clobbering the fake injected by test_detector_rois' OCR-race test.
        d = detector.ScreenDetector({"detector_enable_ocr": True,
                                     "detector_ocr_prewarm": False})

        self.assertEqual(d._ocr_skip_below, 0.30)

    def test_ocr_always_reads_full_roi_no_matched_crop(self):
        # The best-match sub-crop OCR path was removed entirely: OCR always reads
        # the whole ROI (ROIs are drawn tight around their scan item). Guard that
        # the machinery is gone so it isn't reintroduced.
        import detector

        d = detector.ScreenDetector({"detector_enable_ocr": True,
                                     "detector_ocr_prewarm": False})
        self.assertFalse(hasattr(d, "_full_roi_ocr_keys"))
        self.assertFalse(hasattr(d, "_ocr_full_roi_all"))
        self.assertFalse(hasattr(detector.ScreenDetector, "_matched_ocr_area"))

    def test_automations_forward_auto_ocr_note_to_logs(self):
        for path in ("race.py", "buy.py", "wheelspin.py", "mastery.py", "full_auto.py"):
            with self.subTest(path=path):
                if path == "full_auto.py" and not Path(path).exists():
                    continue
                source = Path(path).read_text(encoding="utf-8")
                self.assertIn("on_auto_ocr=log_cb", source)


if __name__ == "__main__":
    unittest.main()
