import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GATED_KEYS = {
    "ride_this_car",
    "upgrade_tuning",
    "car_mastery",
    "mastery_tree",
    "my_cars",
    "my_cars_header",
    "recently_added",
}


class MasteryGatedMenusTests(unittest.TestCase):
    def test_config_default_uses_template_gated_mastery_mode(self):
        import config

        self.assertIs(config.DEFAULTS["mastery_gated_menus"], True)

    def test_webui_exposes_mastery_gated_templates_for_capture(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "webui" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("MASTERY_GATED_TEMPLATE_KEYS", source)
        self.assertIn('"mastery": config.get_mastery_templates', source)
        self.assertIn('"exists": os.path.exists', source)
        self.assertIn("tpl.exists === false", js)
        self.assertIn("missing", js)
        self.assertIn("tpl_missing_pill", js)
        self.assertIn("ready.classList.toggle('missing'", js)
        self.assertIn(".tpl-chip.missing .dot", css)
        self.assertIn("var(--danger)", css)
        self.assertIn(".ready-pill.missing", css)
        self.assertIn("tpl_missing_pill", (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8"))
        for key in GATED_KEYS:
            with self.subTest(key=key):
                self.assertIn(f'"{key}"', source)

    def test_mastery_path_is_template_driven_by_default(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")

        self.assertIn("GATED_TEMPLATE_KEYS", source)
        self.assertIn('mastery_gated_menus', source)
        self.assertIn('_fresh.get("mastery_gated_menus", True)', source)
        self.assertIn("def _run_gated_menus", source)
        self.assertIn("load_template(", source)
        for key in GATED_KEYS:
            with self.subTest(key=key):
                self.assertIn(f'"{key}"', source)

    def test_mastery_gated_mode_is_keyboard_only(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")
        block = source.split("def _run_gated_menus", 1)[1].split(
            "def run(", 1)[0]

        self.assertNotIn("io.click(", block)
        self.assertIn("io.press('enter'", block)
        self.assertIn("taps('down', 7)", block)
        self.assertIn("taps('up', 1)", block)

    def test_mastery_gated_runner_receives_taps_helper(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")

        self.assertIn("progress_cb, stop, wait, taps, announce", source)
        self.assertIn("announce, cut_wait, post_kw, grid_unlock_wait", source)

    def test_mastery_accepts_resume_after_completed_cars(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")

        self.assertIn("initial_completed: int = 0", source)
        self.assertIn("completed = max(0, int(initial_completed or 0))", source)
        self.assertIn("first_attempt = car_num == initial_completed + 1", source)

    def test_mastery_gated_press_confirm_is_single_shot(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")

        self.assertIn("def _press_for_template(key, target, post_wait=None):", source)
        self.assertNotIn("log_timed_out_retry", source)
        self.assertNotIn("attempts=", source)

    def test_mastery_gated_templates_have_ocr_hints(self):
        import detector

        for key in GATED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, detector.OCR_HINTS)
                self.assertTrue(detector.OCR_HINTS[key])
                self.assertIn(key, detector.TEXT_TEMPLATES)

    def test_mastery_tree_hints_accept_short_chinese_ocr_read(self):
        import detector

        short_traditional = "\u8eca\u719f\u5ea6"
        short_simplified = "\u8f66\u719f\u5ea6"

        self.assertIn(short_traditional, detector.OCR_HINTS["mastery_tree"])
        self.assertIn(short_simplified, detector.OCR_HINTS["mastery_tree"])
        self.assertIn(short_traditional, detector.OCR_HINTS["car_mastery"])
        self.assertIn(short_simplified, detector.OCR_HINTS["car_mastery"])

    def test_mastery_gated_hints_match_fh6_menu_text(self):
        import detector

        ride_hints = detector.OCR_HINTS["ride_this_car"]
        self.assertIn("乘坐車輛", ride_hints)
        self.assertIn("乘坐车辆", ride_hints)
        self.assertIn("乘东", ride_hints)
        self.assertIn("get in car", ride_hints)

        self.assertIn("升級與調校", detector.OCR_HINTS["upgrade_tuning"])
        self.assertIn("升级与调校", detector.OCR_HINTS["upgrade_tuning"])
        self.assertIn("車輛熟練度", detector.OCR_HINTS["car_mastery"])
        self.assertIn("车辆熟练度", detector.OCR_HINTS["mastery_tree"])


if __name__ == "__main__":
    unittest.main()
