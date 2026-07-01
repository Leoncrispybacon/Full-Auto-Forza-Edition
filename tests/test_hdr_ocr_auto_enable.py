import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class HdrOcrAutoEnableTests(unittest.TestCase):
    def test_hdr_enabled_flips_ocr_on_without_adding_ui_control(self):
        import hdr

        cfg, changed = hdr.maybe_enable_ocr_for_hdr(
            {"detector_enable_ocr": False},
            hdr_enabled=True,
        )

        self.assertTrue(changed)
        self.assertIs(cfg["detector_enable_ocr"], True)

        app_web = (ROOT / "app_web.py").read_text(encoding="utf-8")
        app_js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        self.assertIn("import hdr", app_web)
        self.assertIn("hdr.is_hdr_enabled", app_web)
        self.assertIn("detector_enable_ocr=True", app_web)
        self.assertIn("HDR detected on the selected game monitor", app_web)
        self.assertIn("OCR enabled automatically", app_web)
        self.assertNotIn("hdr_ocr", app_js)

    def test_hdr_disabled_or_existing_ocr_setting_is_left_alone(self):
        import hdr

        cfg, changed = hdr.maybe_enable_ocr_for_hdr(
            {"detector_enable_ocr": False},
            hdr_enabled=False,
        )
        self.assertFalse(changed)
        self.assertIs(cfg["detector_enable_ocr"], False)

        cfg, changed = hdr.maybe_enable_ocr_for_hdr(
            {"detector_enable_ocr": True},
            hdr_enabled=True,
        )
        self.assertFalse(changed)
        self.assertIs(cfg["detector_enable_ocr"], True)

    def test_windows_detector_uses_advanced_color_api(self):
        source = (ROOT / "hdr.py").read_text(encoding="utf-8")

        self.assertIn("DisplayConfigGetDeviceInfo", source)
        self.assertIn("DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO", source)
        self.assertIn("ADVANCED_COLOR_ENABLED", source)


if __name__ == "__main__":
    unittest.main()
