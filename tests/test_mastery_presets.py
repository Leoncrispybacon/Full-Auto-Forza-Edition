import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MasteryPresetTests(unittest.TestCase):
    def test_capture_saves_loads_and_replaces_named_grid_presets(self):
        import capture

        with tempfile.TemporaryDirectory() as td:
            preset_file = pathlib.Path(td) / "mastery_presets.json"

            saved = capture.save_grid_preset(
                str(preset_file), "  Test Route  ", [(3, 0), (2, 0)])
            self.assertEqual(saved, [{
                "name": "Test Route",
                "order": [(3, 0), (2, 0)],
            }])

            saved = capture.save_grid_preset(
                str(preset_file), "test route", [(3, 1)])
            self.assertEqual(saved, [{
                "name": "test route",
                "order": [(3, 1)],
            }])

            self.assertEqual(capture.load_grid_presets(str(preset_file)), saved)

    def test_capture_rejects_blank_preset_names_and_empty_routes(self):
        import capture

        with tempfile.TemporaryDirectory() as td:
            preset_file = pathlib.Path(td) / "mastery_presets.json"

            with self.assertRaises(ValueError):
                capture.save_grid_preset(str(preset_file), " ", [(3, 0)])
            with self.assertRaises(ValueError):
                capture.save_grid_preset(str(preset_file), "Empty", [])

    def test_mastery_presets_file_is_language_neutral(self):
        import config

        preset_path = pathlib.Path(config.get_mastery_presets_file("cht"))

        self.assertEqual(preset_path, pathlib.Path(config.TEMPLATES_DIR) / "mastery_presets.json")
        self.assertNotIn("mastery_full", preset_path.parts)
        self.assertNotIn("cht", preset_path.parts)

    def test_backend_exposes_built_in_and_user_mastery_presets(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")

        self.assertIn("def get_mastery_presets(self):", source)
        self.assertIn("def save_mastery_preset(self, name, order):", source)
        self.assertIn('"Subaru 22B-STI"', source)
        self.assertIn('"Dodge Viper GTS ACR"', source)
        self.assertNotIn("Subaru 22B-STI Super Wheelspin", source)
        self.assertNotIn("Dodge Viper GTS ACR Credits", source)
        self.assertIn("capture.save_grid_preset", source)
        self.assertIn("config.get_mastery_presets_file", source)
        self.assertIn("def _legacy_mastery_presets_file", source)
        self.assertIn("def _migrate_legacy_mastery_presets", source)

    def test_webui_adds_mastery_preset_dropdown_and_save_button(self):
        js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        i18n = (ROOT / "webui" / "i18n.js").read_text(encoding="utf-8")

        self.assertIn("get_mastery_presets", js)
        self.assertIn("save_mastery_preset", js)
        self.assertIn("grid_preset_label", js)
        self.assertIn("grid_save_preset", js)
        self.assertIn("grid_preset_custom", i18n)
        self.assertIn("grid_preset_builtin_name", i18n)


if __name__ == "__main__":
    unittest.main()
