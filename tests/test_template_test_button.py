import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TemplateTestButtonTests(unittest.TestCase):
    def test_backend_template_test_is_detection_only(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")
        self.assertIn("def _run_template_test_once(self, tab, key):", source)
        block = source.split("def _run_template_test_once(self, tab, key):", 1)[1]
        block = block.split("def test_template", 1)[0]
        self.assertIn("ScreenDetector", block)
        self.assertIn("debug_detection", block)
        self.assertIn("detector.detect", block)
        self.assertNotIn(".press(", block)
        self.assertNotIn(".click(", block)

    def test_backend_template_test_is_dev_only_and_caps_armed(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")
        block = source.split("def test_template(self, tab, key):", 1)[1]
        block = block.split("def capture_roi", 1)[0]
        self.assertIn('cfg.get("dev_mode"', block)
        self.assertIn('cfg.get("capture_key"', block)
        self.assertIn("keyboard.add_hotkey", block)
        self.assertIn("_run_template_test_once(tab, key)", block)

    def test_webui_has_developer_template_test_button(self):
        app = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")
        self.assertIn("API('test_template', tab, tpl.name)", app)
        self.assertIn("tpl_testing", app)
        self.assertIn("tpl_waiting", app)
        self.assertIn("tpl_test", i18n)
        self.assertIn("tpl_testing", i18n)
        self.assertIn("tpl_waiting", i18n)


if __name__ == "__main__":
    unittest.main()
