import unittest


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


if __name__ == "__main__":
    unittest.main()
