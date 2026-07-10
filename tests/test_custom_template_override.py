import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class CustomTemplateOverrideTests(unittest.TestCase):
    """User recaptures live in a sibling custom\\ folder that survives installer
    upgrades; load_template prefers them over the shipped built-in set."""

    def _write_template(self, folder, key, screen_h, fill):
        import cv2
        os.makedirs(folder, exist_ok=True)
        img = np.full((20, 20, 3), fill, dtype=np.uint8)
        cv2.imwrite(os.path.join(folder, key + ".png"), img)
        with open(os.path.join(folder, key + ".json"), "w", encoding="utf-8") as f:
            json.dump({"screen_width": 100, "screen_height": screen_h}, f)

    def test_config_custom_dir_is_built_in_sibling(self):
        import config
        with tempfile.TemporaryDirectory() as d:
            built_in = os.path.join(d, "race", "built-in")
            os.makedirs(built_in)
            custom = config.custom_dir(built_in)
            self.assertEqual(os.path.normpath(custom),
                             os.path.normpath(os.path.join(d, "race", "custom")))
            self.assertTrue(os.path.isdir(custom))       # created

    def test_load_template_prefers_custom_over_built_in(self):
        import capture
        with tempfile.TemporaryDirectory() as d:
            built_in = os.path.join(d, "race", "built-in")
            custom = os.path.join(d, "race", "custom")
            # built-in authored at 2160; custom recapture at 1080 (distinguishable)
            self._write_template(built_in, "start_menu", 2160, 10)
            self._write_template(custom, "start_menu", 1080, 200)

            _img, _s, meta = capture.load_template(
                built_in, "start_menu", 1080, 1080, ref_folder=built_in,
                prefer_ref=True)
            self.assertEqual(meta["screen_height"], 1080)   # custom won

    def test_load_template_falls_back_to_built_in_when_no_custom(self):
        import capture
        with tempfile.TemporaryDirectory() as d:
            built_in = os.path.join(d, "race", "built-in")
            self._write_template(built_in, "start_menu", 2160, 10)
            _img, _s, meta = capture.load_template(
                built_in, "start_menu", 2160, 2160, ref_folder=built_in,
                prefer_ref=True)
            self.assertEqual(meta["screen_height"], 2160)   # built-in used

    def test_recapture_routes_to_custom_only_when_not_dev(self):
        src = (ROOT / "app_web.py").read_text(encoding="utf-8")
        # capture_template redirects to custom_dir when dev mode is off.
        self.assertIn('if not cfg.get("dev_mode", False):', src)
        self.assertIn("folder = config.custom_dir(folder)", src)

    def test_installer_preserves_custom_folders(self):
        iss = (ROOT / "build_installer.iss").read_text(encoding="utf-8")
        # built-in is cleared on upgrade; custom is NEVER listed for deletion.
        self.assertIn(r"{app}\templates\en\race\built-in", iss)
        self.assertNotIn(r"\custom", iss)

    def test_recapture_and_test_not_dev_gated_in_ui(self):
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        # The recapture/test buttons are appended OUTSIDE the state.dev block;
        # only the ROI tuner stays dev-gated.
        i_append = js.index("chip.append(cap, test);")
        i_dev = js.index("if (state.dev) {   // detection-area", i_append)
        self.assertLess(i_append, i_dev)             # cap+test appended first, unconditionally


if __name__ == "__main__":
    unittest.main()
