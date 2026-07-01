from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FullAutoTeaserPreviewTests(unittest.TestCase):
    def test_teaser_copy_sells_distinct_full_auto_features_and_pricing(self):
        html = (ROOT / "webui" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")

        self.assertIn("lockedModes", html)
        self.assertIn("lockedPrice", html)
        self.assertIn("locked_mode_money", i18n)
        self.assertIn("locked_mode_wheelspin", i18n)
        self.assertIn("locked_feat_points", i18n)
        self.assertIn("locked_feat_progress", i18n)
        self.assertIn("locked_feat_branch", i18n)
        self.assertIn("$5.99", i18n)
        self.assertIn("NT$190", i18n)
        self.assertIn("lockedModes", js)
        self.assertIn("lockedPrice", js)

    def test_start_paths_do_not_resave_recovery_test_point(self):
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("persistRecoveryTestPoint", js)
        self.assertNotIn("recovery_test_point", js)


if __name__ == "__main__":
    unittest.main()
