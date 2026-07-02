import unittest
from pathlib import Path
import sys
import types


class _FakeMss:
    monitors = [{}, {"left": 0, "top": 0, "width": 1920, "height": 1080}]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


sys.modules.setdefault(
    "mss",
    types.SimpleNamespace(mss=lambda: _FakeMss()),
)

import config
import ocr_profile


class OcrCpuProfileTests(unittest.TestCase):
    def test_ocr_is_enabled_by_default(self):
        self.assertIs(config.DEFAULTS["detector_enable_ocr"], True)

    def test_intel_12_13_14_gen_uses_low_impact_profile(self):
        names = [
            "12th Gen Intel(R) Core(TM) i5-12600K",
            "13th Gen Intel(R) Core(TM) i7-13700K",
            "Intel(R) Core(TM) i9-14900HX",
            "Intel Core Ultra 7 155H",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(
                    ocr_profile.profile_for_cpu(name),
                    ocr_profile.PROFILE_LOW_IMPACT,
                )

    def test_non_hybrid_and_unknown_cpus_use_balanced_profile(self):
        names = [
            "AMD Ryzen 7 7800X3D 8-Core Processor",
            "Intel(R) Core(TM) i7-10700K CPU",
            "",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(
                    ocr_profile.profile_for_cpu(name),
                    ocr_profile.PROFILE_BALANCED,
                )

    def test_profile_defaults_are_applied_without_overwriting_explicit_tuning(self):
        cfg = {
            "detector_enable_ocr": True,
            "detector_ocr_cooldown": 9.0,
            "detector_force_ocr_keys": ["wheelspin_collect_final"],
        }
        effective = ocr_profile.apply_ocr_profile_defaults(
            cfg,
            cpu_name="13th Gen Intel(R) Core(TM) i7-13700K",
        )
        self.assertEqual(effective["ocr_cpu_profile"], ocr_profile.PROFILE_LOW_IMPACT)
        self.assertEqual(effective["detector_ocr_cooldown"], 9.0)
        self.assertEqual(
            effective["detector_force_ocr_keys"],
            ["wheelspin_collect_final"],
        )
        self.assertEqual(effective["detector_ocr_target_h"], 480)
        self.assertIs(effective["detector_ocr_prewarm"], False)

    def test_balanced_profile_keeps_current_ocr_shape(self):
        effective = ocr_profile.apply_ocr_profile_defaults(
            {"detector_enable_ocr": True},
            cpu_name="AMD Ryzen 7 7800X3D",
        )
        self.assertEqual(effective["ocr_cpu_profile"], ocr_profile.PROFILE_BALANCED)
        self.assertEqual(effective["detector_ocr_cooldown"], 1.0)
        self.assertEqual(effective["detector_ocr_cache_duration"], 5.0)
        self.assertEqual(effective["detector_ocr_target_h"], 640)
        self.assertIs(effective["detector_ocr_prewarm"], True)

    def test_webui_does_not_add_a_separate_ocr_preset_control(self):
        app_js = Path("webui/app.js").read_text(encoding="utf-8")
        self.assertNotIn("ocr_preset", app_js)
        self.assertNotIn("ocr_cpu_profile", app_js)

    def test_webui_ocr_toggle_is_developer_only(self):
        app_js = Path("webui/app.js").read_text(encoding="utf-8")
        index = Path("webui/index.html").read_text(encoding="utf-8")

        system_block = app_js.split("const SYSTEM_TOGGLES", 1)[1].split("];", 1)[0]
        self.assertNotIn("detector_enable_ocr", system_block)
        self.assertIn('id="setDevOcr"', index)
        self.assertIn("detector_enable_ocr", app_js)
        self.assertIn("devExtras", app_js)

    def test_detector_missing_ocr_key_falls_back_to_enabled(self):
        detector_py = Path("detector.py").read_text(encoding="utf-8")
        self.assertIn('cfg.get("detector_enable_ocr", True)', detector_py)


if __name__ == "__main__":
    unittest.main()
