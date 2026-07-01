import unittest


class OcrChineseVariantTests(unittest.TestCase):
    def test_normalize_text_allows_mixed_traditional_simplified_chars(self):
        import detector

        text = detector._normalize_text(
            "\u6211\u7684\u8f66\u8f86 \u5347\u7ea7\u5957\u4ef6\u8207\u8abf\u6821")

        self.assertIn(detector._normalize_text("\u6211\u7684\u8eca\u8f1b"), text)
        self.assertIn(detector._normalize_text("\u5347\u7d1a"), text)
        self.assertIn(detector._normalize_text("\u8abf\u6821"), text)

    def test_existing_hints_match_mixed_chinese_ocr_reads(self):
        import detector

        norm = detector._normalize_text(
            "\u6211\u7684\u8f66\u8f86 \u5347\u7ea7\u5957\u4ef6\u8207\u8abf\u6821")

        self.assertTrue(any(
            detector._normalize_text(hint) in norm
            for hint in detector.OCR_HINTS["my_cars"]))
        self.assertTrue(any(
            detector._normalize_text(hint) in norm
            for hint in detector.OCR_HINTS["upgrade_tuning"]))

    def test_english_hint_matching_tolerates_ocr_word_reordering(self):
        import detector

        self.assertTrue(detector._ocr_hint_matches(
            "Type Choose Race", detector.OCR_HINTS["choose_race_type"]))
        self.assertFalse(detector._ocr_hint_matches(
            "Choose Race", detector.OCR_HINTS["choose_race_type"]))


if __name__ == "__main__":
    unittest.main()
