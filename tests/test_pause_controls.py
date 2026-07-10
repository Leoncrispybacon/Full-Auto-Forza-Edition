from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PauseControlsTests(unittest.TestCase):
    def test_pause_shortcut_and_api_are_wired(self):
        import config
        import app_web

        self.assertEqual(config.DEFAULTS["pause_key"], "f8")
        self.assertEqual(app_web.Api._SHORTCUT_KEYS["pause"], "pause_key")
        self.assertTrue(hasattr(app_web.Api, "pause"))
        self.assertTrue(hasattr(app_web.Api, "resume"))
        self.assertTrue(hasattr(app_web.Api, "toggle_pause"))

        app_source = (ROOT / "app_web.py").read_text(encoding="utf-8")
        self.assertIn("while self._pause.is_set() and not self._stop.is_set()", app_source)

    def test_webui_has_single_start_stop_and_pause_resume_controls(self):
        app = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        index = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")

        self.assertIn("let isPaused = false", app)
        self.assertIn("toggle_pause", app)
        self.assertIn("['pause',", app)
        self.assertIn("data-i18n=\"pause\"", index)
        self.assertIn("pause:", i18n)
        self.assertIn("resume:", i18n)

    def test_buy_press_waits_before_sending_input_when_paused(self):
        for filename, start, end in (
            ("buy.py", "    def press(key, post_wait=None):", "    def _detect"),
            ("wheelspin.py", "    def press(key, post_wait=None):", "    def _detect"),
            ("race.py", "    def _kp(key, post_wait=post_kw):", "    def _click"),
        ):
            source = (ROOT / filename).read_text(encoding="utf-8")
            press = source.split(start, 1)[1].split(end, 1)[0]

            self.assertLess(press.index("while paused() and not stop()"),
                            press.index("io.press("), filename)

    def test_race_pause_release_uses_gameio_release_signature(self):
        source = (ROOT / "race.py").read_text(encoding="utf-8")

        self.assertNotIn("release('w', post_wait", source)
        self.assertIn("io.release('w')", source)


if __name__ == "__main__":
    unittest.main()
