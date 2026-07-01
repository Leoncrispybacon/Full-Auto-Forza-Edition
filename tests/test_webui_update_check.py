import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WebUiUpdateCheckTests(unittest.TestCase):
    def setUp(self):
        self.app_web = (ROOT / "app_web.py").read_text(encoding="utf-8")
        self.app_js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        self.index = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")

    def test_webui_backend_exposes_check_only_update_api(self):
        self.assertIn("import updater", self.app_web)
        self.assertIn("def check_updates(self):", self.app_web)
        self.assertIn("updater.check_async", self.app_web)
        self.assertIn("def open_update_page(self, url=None):", self.app_web)
        self.assertNotIn("urlretrieve", self.app_web)

    def test_webui_calls_update_check_after_init_when_enabled(self):
        self.assertIn("state.cfg.update_check !== false", self.app_js)
        self.assertIn("API('check_updates')", self.app_js)

    def test_webui_has_update_prompt_and_open_action(self):
        self.assertIn('id="updateModal"', self.index)
        self.assertIn("function showUpdate", self.app_js)
        self.assertIn("function openUpdatePage", self.app_js)
        self.assertIn("API('open_update_page'", self.app_js)


if __name__ == "__main__":
    unittest.main()
