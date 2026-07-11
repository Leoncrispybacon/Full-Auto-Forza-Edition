import unittest
import os
import tempfile


class CutsceneSettleRoundTripTests(unittest.TestCase):
    """Prove a slider change persists and a fresh load (what run() does at the
    start of every run) returns the NEW value — i.e. it applies next run."""

    def test_set_then_fresh_load_returns_new_value(self):
        import config
        orig = config.CONFIG_FILE
        with tempfile.TemporaryDirectory() as d:
            config.CONFIG_FILE = os.path.join(d, "config.json")
            try:
                # fresh install → default is 2.0
                self.assertEqual(config.load()["mastery_cutscene_settle"], 2.0)
                # mirror set_cfg/_update_cfg: load → update → save
                cfg = config.load()
                cfg["mastery_cutscene_settle"] = 2.75
                self.assertTrue(config.save(cfg))
                # mirror run(): a brand-new fresh load from disk
                self.assertEqual(config.load()["mastery_cutscene_settle"], 2.75)
            finally:
                config.CONFIG_FILE = orig

    def test_mastery_clamp_bounds(self):
        # Mirrors the inline clamp in mastery._press_cutscene_escape:
        #   wait(max(1.0, min(3.0, float(cfg.get("mastery_cutscene_settle", ...)))))
        clamp = lambda x: max(1.0, min(3.0, float(x)))
        self.assertEqual(clamp(2.75), 2.75)   # in-range slider value passes through
        self.assertEqual(clamp(5.0), 3.0)     # above cap clamps down
        self.assertEqual(clamp(0.25), 1.0)    # below floor clamps up


class MasteryCutsceneSettleTests(unittest.TestCase):
    def test_config_default_is_two_seconds(self):
        import config
        self.assertIn("mastery_cutscene_settle", config.DEFAULTS)
        self.assertEqual(config.DEFAULTS["mastery_cutscene_settle"], 2.0)

    def test_mastery_reads_the_config_key(self):
        # The post-cutscene settle must be driven by the config key, not the
        # bare _CUTSCENE_SETTLE constant.
        src = open("mastery.py", encoding="utf-8").read()
        self.assertIn("mastery_cutscene_settle", src)

    def test_timing_slider_registered(self):
        src = open("webui/app.js", encoding="utf-8").read()
        self.assertIn("mastery_cutscene_settle", src)

    def test_i18n_label_both_languages(self):
        src = open("webui/i18n.js", encoding="utf-8").read()
        # one occurrence per language section for the label + hint keys
        self.assertGreaterEqual(src.count("tm_mastery_cutscene_settle:"), 2)
        self.assertGreaterEqual(src.count("tm_mastery_cutscene_settle_h:"), 2)
