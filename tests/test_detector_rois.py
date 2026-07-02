import unittest
from unittest import mock


class DetectorRoiTests(unittest.TestCase):
    def test_default_rois_are_numeric_rects(self):
        import detector

        for key, roi in detector.DEFAULT_ROIS.items():
            with self.subTest(key=key):
                self.assertEqual(len(roi), 4)
                self.assertTrue(all(isinstance(v, (int, float)) for v in roi))

    def test_flat_template_cannot_match_flat_screen(self):
        import numpy as np
        import detector

        screen = np.zeros((100, 200), dtype=np.uint8)
        template = np.zeros((20, 50), dtype=np.uint8)

        score, _loc, _scale = detector._best_template_match(
            screen, template, [1.0])

        self.assertEqual(score, 0.0)

    def test_ocr_confirm_reads_matched_patch_not_whole_roi(self):
        import numpy as np
        import detector

        class FakeOCR:
            def __init__(self):
                self.shape = None

            def available(self):
                return True

            def read(self, img):
                self.shape = img.shape[:2]
                return "start"

        d = detector.ScreenDetector({
            "detector_enable_ocr": True,
            "detector_ocr_prewarm": False,
            "detector_ocr_cooldown": 0,
        })
        fake = FakeOCR()
        d._ocr = fake

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        template = np.zeros((10, 20), dtype=np.uint8)
        with mock.patch.object(detector, "_best_template_match",
                               return_value=(0.50, (30, 40), 1.0)):
            result = d._detect_in_area(
                frame, "start_menu", template, 0.70, None, "roi", False)

        self.assertTrue(result.matched)
        self.assertLess(fake.shape[0], frame.shape[0])
        self.assertLess(fake.shape[1], frame.shape[1])


if __name__ == "__main__":
    unittest.main()
