import json
import os
import tempfile
import unittest


class CustomRoiScalingTests(unittest.TestCase):
    def test_save_roi_records_its_own_dims_not_the_box_dims(self):
        import capture

        d = tempfile.mkdtemp()
        # Sidecar from a template image captured at ultrawide (the BOX's res).
        with open(os.path.join(d, "k.json"), "w", encoding="utf-8") as f:
            json.dump({"screen_width": 5120, "screen_height": 2160,
                       "box": [100, 200, 50, 20]}, f)
        # Recapture the ROI at 1920x1080.
        capture.save_roi(d, "k", (96, 994, 300, 54), 1920, 1080)
        meta = json.load(open(os.path.join(d, "k.json"), encoding="utf-8"))

        self.assertEqual(meta["roi_dims"], [1920, 1080])   # ROI's own reference
        self.assertEqual(meta["screen_width"], 5120)       # box dims left alone
        self.assertAlmostEqual(meta["roi"][0], 96 / 1920, places=4)

    def test_same_aspect_roi_used_as_is(self):
        import detector

        det = detector.ScreenDetector({"detector_ocr_prewarm": False})
        det._custom_rois["k"] = (0.05, 0.92, 0.28, 0.05)
        det._custom_roi_dims["k"] = (1920, 1080)   # recaptured on the run device
        self.assertEqual(det._custom_roi_for_frame("k", 1920, 1080),
                         (0.05, 0.92, 0.28, 0.05))

    def test_cross_aspect_centered_element_stays_centered(self):
        import detector

        det = detector.ScreenDetector({"detector_ocr_prewarm": False})
        # wheelspin_duplicate header drawn @5120x2160 (centred) → 16:9
        det._custom_rois["k"] = (0.45566, 0.18333, 0.08633, 0.04861)
        det._custom_roi_dims["k"] = (5120, 2160)
        out = det._custom_roi_for_frame("k", 1920, 1080)
        cx = (out[0] + out[2] / 2) * 1920
        self.assertAlmostEqual(cx, 960, delta=20)   # near screen centre

    def test_cross_aspect_corner_element_stays_in_corner(self):
        import detector

        det = detector.ScreenDetector({"detector_ocr_prewarm": False})
        # wheelspin_collect drawn @5120x2160 (bottom-left) → 16:9
        det._custom_rois["k"] = (0.15254, 0.91389, 0.10742, 0.03704)
        det._custom_roi_dims["k"] = (5120, 2160)
        out = det._custom_roi_for_frame("k", 1920, 1080)
        cy = (out[1] + out[3] / 2) * 1080
        self.assertLess(out[0], 0.4)     # stays left
        self.assertGreater(cy, 950)      # stays near the bottom


if __name__ == "__main__":
    unittest.main()
