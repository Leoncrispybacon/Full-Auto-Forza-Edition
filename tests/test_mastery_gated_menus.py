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
    def test_mastery_is_always_template_gated_no_toggle(self):
        import config

        # Legacy blind path + the mastery_gated_menus toggle were removed —
        # the template-gated flow is now the only path.
        self.assertNotIn("mastery_gated_menus", config.DEFAULTS)
        self.assertNotIn("mastery_gated_menus",
                         (ROOT / "mastery.py").read_text(encoding="utf-8"))

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
        self.assertIn("announce, post_kw, grid_unlock_wait", source)

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

    def test_mastery_gated_cutscene_escape_has_local_retry_and_resume(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")
        block = source.split("def _run_gated_menus", 1)[1].split(
            "def _recover_standalone_gated_to_grid", 1)[0]

        self.assertIn("def _press_cutscene_escape():", block)
        self.assertIn("_detect(\"upgrade_tuning\", 5.0)", block)
        self.assertGreaterEqual(block.count("io.press('esc'"), 2)
        self.assertIn("resume_step = \"upgrade_tuning\"", block)
        self.assertIn("if resume_step == \"car_mastery\":", block)

    def test_cutscene_escape_gated_on_optional_post_cutscene_template(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")
        block = source.split("def _press_cutscene_escape():", 1)[1].split(
            "def ", 1)[0]

        # Esc is gated on the post-cutscene template when captured.
        self.assertIn("_CUTSCENE_END_KEY in templates", block)
        self.assertIn("_detect(_CUTSCENE_END_KEY", block)
        self.assertIn('_CUTSCENE_END_KEY = "ride_cutscene_end"', source)
        # ...but it's OPTIONAL — never in the REQUIRED gated set.
        self.assertNotIn("ride_cutscene_end", str(GATED_KEYS))
        self.assertIn('"ride_cutscene_end"',
                      (ROOT / "app_web.py").read_text(encoding="utf-8"))

    def test_post_cutscene_template_is_never_a_recovery_anchor(self):
        import mastery

        # Recovery re-anchors from GATED_TEMPLATE_KEYS (via
        # _recover_standalone_gated_to_grid). ride_cutscene_end is a ONE-WAY
        # screen — you can't Esc back to it — so it must NEVER be an anchor.
        self.assertEqual(mastery._CUTSCENE_END_KEY, "ride_cutscene_end")
        self.assertNotIn("ride_cutscene_end", mastery.GATED_TEMPLATE_KEYS)
        # and it isn't named in either recovery anchor set
        src = (ROOT / "mastery.py").read_text(encoding="utf-8")
        recov = src.split("def _recover_standalone_gated_to_grid", 1)[1]
        self.assertNotIn("ride_cutscene_end", recov)

    def test_post_cutscene_template_has_ocr_hints(self):
        import detector

        self.assertIn("ride_cutscene_end", detector.OCR_HINTS)
        self.assertIn("back", detector.OCR_HINTS["ride_cutscene_end"])
        self.assertIn("返回", detector.OCR_HINTS["ride_cutscene_end"])
        self.assertIn("ride_cutscene_end", detector.TEXT_TEMPLATES)

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

    def test_mycars_step_has_inline_recovery_before_giving_up(self):
        # A dropped ESC after the tree can strand us one menu level too deep (e.g.
        # the Upgrades screen), so my_cars isn't found. The my_cars step must
        # self-heal (back out + re-check) like the mastery-menu steps do, instead
        # of breaking straight to the one-shot route recovery.
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")
        self.assertIn("def _recover_to_mycars", source)
        block = source.split("def _recover_to_mycars", 1)[1].split(
            "\n    def ", 1)[0]
        self.assertIn("io.press('esc'", block)
        self.assertIn('_detect("my_cars"', block)
        # wired into the my_cars step (called before the fail/break)
        self.assertIn("r = _recover_to_mycars()", source)

        import app_lang
        self.assertTrue(app_lang.t("log_mastery_recover_mycars", "en"))
        self.assertTrue(app_lang.t("log_mastery_recover_mycars", "zh-tw"))


if __name__ == "__main__":
    unittest.main()
