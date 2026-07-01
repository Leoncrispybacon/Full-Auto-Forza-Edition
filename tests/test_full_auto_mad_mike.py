from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FullAutoMadMikeTests(unittest.TestCase):
    def test_config_tracks_car_pass_answer_separately_from_owned_value(self):
        import config

        self.assertIs(config.DEFAULTS["car_pass_dlc_answered"], False)
        self.assertIs(config.DEFAULTS["car_pass_dlc_owned"], False)

    def test_webui_prompts_for_car_pass_until_answered_and_updates_grind_label(self):
        html = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")

        self.assertIn("carPassPicker", html)
        self.assertIn("showCarPassPicker", js)
        self.assertIn("car_pass_dlc_answered", js)
        self.assertIn("car_pass_dlc_owned", js)
        self.assertIn("grind_mad_mike", i18n)
        self.assertIn("grind_mixed_mad_mike", i18n)

    def test_dlc_grind_labels_stay_generic(self):
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")
        self.assertIn('grind_mad_mike: "Wheelspin"', i18n)
        self.assertIn('grind_mixed_mad_mike: "Mixed"', i18n)
        self.assertNotIn('grind_mad_mike: "#123 Mad Mike"', i18n)
        self.assertNotIn('grind_mixed_mad_mike: "Mixed (Viper + Mad Mike)"', i18n)

    def test_first_time_setup_pickers_are_numbered_and_translucent(self):
        html = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "webui" / "styles.css").read_text(encoding="utf-8")
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        import config

        self.assertIn('<div id="launchPathPicker">', html)
        lang_picker = html.split('<div id="langPicker">', 1)[1].split('<div id="launchPathPicker">', 1)[0]
        launch_picker = html.split('<div id="launchPathPicker">', 1)[1].split('<div id="carPassPicker">', 1)[0]
        car_pass_picker = html.split('<div id="carPassPicker">', 1)[1].split('<script src="i18n.js">', 1)[0]

        self.assertIn('data-i18n="setup_step_1"', lang_picker)
        self.assertIn('data-i18n="setup_step_2"', launch_picker)
        self.assertIn('data-i18n="setup_step_3"', car_pass_picker)
        self.assertIn('data-i18n="first_time_setup"', lang_picker)
        self.assertIn('data-i18n="first_time_setup"', launch_picker)
        self.assertIn('data-i18n="first_time_setup"', car_pass_picker)
        self.assertNotIn("FAFE", car_pass_picker)
        self.assertNotIn("car_pass_title", car_pass_picker)
        self.assertIn('data-launch-platform="steam"', launch_picker)
        self.assertIn('data-launch-platform="xbox"', launch_picker)
        self.assertIn('data-launch-platform="custom"', launch_picker)
        self.assertIn("showLaunchPathPicker", js)
        self.assertIn("game_launch_path_answered", js)
        self.assertIs(config.DEFAULTS["game_launch_path_answered"], False)
        self.assertIn("rgba(", css)
        self.assertIn("first_time_setup", i18n)
        self.assertIn("setup_step_1", i18n)
        self.assertIn("setup_step_2", i18n)
        self.assertIn("setup_step_3", i18n)
        self.assertIn("launch_path_prompt", i18n)

    def test_full_auto_has_mad_mike_target_grid_and_21_point_math(self):
        source = (ROOT / "full_auto.py").read_text(encoding="utf-8")

        self.assertIn("_GRID_MAD_MIKE", source)
        self.assertIn("MAD_MIKE_PRESET_NAME", source)
        self.assertIn("def _mad_mike_target_nav", source)
        self.assertIn('"mazda"', source)
        self.assertIn('"mad_mike_808"', source)
        self.assertIn('"mad_mike": 21', source)
        self.assertIn("target = _target_for_grind", source)

    def test_tech_points_666_ocr_read_is_treated_as_999(self):
        import full_auto

        logs = []
        self.assertEqual(
            full_auto._parse_tech_points_ocr("技術點數：666", logs.append),
            999)
        self.assertTrue(any("666" in line and "999" in line for line in logs))

    def test_full_auto_exposes_mad_mike_templates_for_capture(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")

        self.assertIn("FULL_AUTO_EXPECTED_TEMPLATE_KEYS", source)
        self.assertIn('"mazda"', source)
        self.assertIn('"mad_mike_808"', source)

    def test_mad_mike_templates_have_ocr_hints(self):
        import detector

        self.assertIn("mazda", detector.OCR_HINTS)
        self.assertIn("mad_mike_808", detector.OCR_HINTS)
        self.assertIn("mazda", detector.TEXT_TEMPLATES)
        self.assertIn("mad_mike_808", detector.TEXT_TEMPLATES)
        self.assertIn("mazda", detector.OCR_HINTS["mazda"])
        self.assertIn("mad mike", detector.OCR_HINTS["mad_mike_808"])
        self.assertIn("808 wagon", detector.OCR_HINTS["mad_mike_808"])

    def test_full_auto_money_and_sell_templates_have_ocr_hints(self):
        import detector

        expected = {
            "dodge": "dodge",
            "gts_acr": "viper gts acr",
            "grind_car": "22b-sti",
        }
        for key, hint in expected.items():
            with self.subTest(key=key):
                self.assertIn(key, detector.OCR_HINTS)
                self.assertIn(key, detector.TEXT_TEMPLATES)
                self.assertIn(hint, detector.OCR_HINTS[key])

    def test_chinese_mad_mike_templates_use_shared_hint_keys(self):
        for key in ("mazda", "mad_mike_808"):
            with self.subTest(key=key):
                self.assertTrue(
                    (ROOT / "templates" / "cht" / "full_auto" / "built-in"
                     / f"{key}.json").exists()
                )
                self.assertTrue(
                    (ROOT / "templates" / "cht" / "full_auto" / "built-in"
                     / f"{key}.png").exists()
                )


if __name__ == "__main__":
    unittest.main()
