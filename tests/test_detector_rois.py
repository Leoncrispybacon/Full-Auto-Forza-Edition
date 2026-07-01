import unittest


class DetectorRoiTests(unittest.TestCase):
    def test_default_rois_are_numeric_rects(self):
        import detector

        for key, roi in detector.DEFAULT_ROIS.items():
            with self.subTest(key=key):
                self.assertEqual(len(roi), 4)
                self.assertTrue(all(isinstance(v, (int, float)) for v in roi))


if __name__ == "__main__":
    unittest.main()
