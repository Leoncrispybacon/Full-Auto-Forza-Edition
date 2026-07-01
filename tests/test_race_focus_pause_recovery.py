import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RaceFocusPauseRecoveryTests(unittest.TestCase):
    def test_driving_wait_checks_pause_menu_after_focus_loss(self):
        source = (ROOT / "race.py").read_text(encoding="utf-8")

        self.assertIn("def _wait_for_restart_while_driving", source)
        self.assertIn("get_foreground_window() != io.hwnd", source)
        self.assertIn('"creative_hub" in nav_tpls', source)
        self.assertIn("log_race_pause_resume", source)
        self.assertIn("io.fresh_hold('w')", source)
        self.assertIn("_kp('escape'", source)
        self.assertIn("io.hold_press('w')", source)
        self.assertIn("_wait_for_restart_while_driving()", source)

    def test_gameio_exposes_fresh_hold_for_pause_recovery(self):
        source = (ROOT / "gameio.py").read_text(encoding="utf-8")

        self.assertIn("def fresh_hold", source)
        self.assertIn("self.release(key)", source)
        self.assertIn("self.hold_press(key)", source)


if __name__ == "__main__":
    unittest.main()
