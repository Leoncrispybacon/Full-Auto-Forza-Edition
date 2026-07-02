import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FullAutoChecklistTests(unittest.TestCase):
    def test_one_time_full_auto_checks_are_persisted(self):
        import config

        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")

        self.assertIs(config.DEFAULTS["fa_check_favorite_ok"], False)
        self.assertIs(config.DEFAULTS["fa_check_stock_paint_ok"], False)
        self.assertIs(config.DEFAULTS["fa_check_collection_unlock_ok"], False)
        self.assertIn("fa_check_favorite_ok", js)
        self.assertIn("fa_check_stock_paint_ok", js)
        self.assertIn("fa_check_collection_unlock_ok", js)
        self.assertIn("item.cfg ? state.cfg[item.cfg] === true : false", js)
        self.assertIn("API('set_cfg', item.cfg, checked[i])", js)

    def test_per_session_full_auto_checks_still_reset(self):
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")

        self.assertIn("{ key:'chk_driving' }", js)
        self.assertIn("{ key:'chk_map' }", js)


if __name__ == "__main__":
    unittest.main()
