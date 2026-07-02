from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RecoveryTestUiTests(unittest.TestCase):
    def test_recovery_test_point_ui_and_config_are_removed(self):
        import config

        self.assertNotIn("recovery_test_point", config.DEFAULTS)

        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")

        self.assertNotIn("RECOVERY_TEST_POINTS", js)
        self.assertNotIn("function recoveryTestRow", js)
        self.assertNotIn("recovery_test_point", js)
        self.assertNotIn("renderRecoveryTest", js)
        self.assertNotIn("recovery_test_label", i18n)
        self.assertNotIn("recovery_test_race_entry", i18n)
        self.assertNotIn("recovery_test_race_start_screen", i18n)
        self.assertNotIn("recovery_test_choose_race_type", i18n)
        self.assertNotIn("recovery_test_wheelspin_entry", i18n)

    def test_race_keeps_left_arrow_route_step_but_not_recovery_anchor(self):
        source = Path("race.py").read_text(encoding="utf-8")

        self.assertNotIn("def _hit_recovery_test", source)
        self.assertIn("choose_race_type", source)
        self.assertIn("def _recover_race_entry_route", source)
        self.assertIn("recover_fn=_recover_race_entry_route", source)
        self.assertIn("_RACE_NAV_ROUTE_STEPS", source)
        self.assertIn("eventlab", source)
        self.assertIn("play_event", source)
        self.assertIn("events_arrow", source)
        self.assertIn("_RACE_RECOVERY_ANCHOR_KEYS", source)
        anchor_block = source.split("_RACE_RECOVERY_ANCHOR_KEYS", 1)[1].split(")", 1)[0]
        self.assertNotIn("events_arrow", anchor_block)
        self.assertIn("my_history", source)
        self.assertIn("car_select", source)

    def test_restart_menu_hints_match_recaptured_restart_button(self):
        import detector

        hints = detector.OCR_HINTS["restart_menu"]
        for hint in ("restart", "重新開始", "重新开始"):
            with self.subTest(hint=hint):
                self.assertIn(hint, hints)
        self.assertNotIn("driver", hints)

    def test_choose_race_type_has_simplified_chinese_hint(self):
        import detector

        self.assertIn("选择比赛类型", detector.OCR_HINTS["choose_race_type"])


if __name__ == "__main__":
    unittest.main()
