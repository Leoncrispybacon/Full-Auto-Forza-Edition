from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeleteConfirmGateTests(unittest.TestCase):
    """The optional delete_confirm template gates the irreversible final confirm
    keypress: press it only when the dialog is detected, else bail. Absent →
    unchanged blind macro."""

    def test_delete_gates_final_confirm_on_template(self):
        src = (ROOT / "delete_cars.py").read_text(encoding="utf-8")
        self.assertIn("def _confirm_present():", src)
        self.assertIn('"delete_confirm"', src)
        # bail (break) before the final Enter when the dialog isn't confirmed
        gate = src.split("def _confirm_present", 1)[1]
        self.assertIn("if _confirm_tpl is None:", gate)   # optional: blind pass-through
        loop = src.split("Select option", 1)[1].split("Confirm delete", 1)[0]
        self.assertIn("_confirm_present()", loop)
        self.assertIn("log_delete_confirm_fail", loop)
        self.assertIn("break", loop)

    def test_delete_gate_is_optional_no_ocr_prewarm(self):
        src = (ROOT / "delete_cars.py").read_text(encoding="utf-8")
        # optional load (FileNotFoundError → blind), and no wasted OCR prewarm
        self.assertIn("except FileNotFoundError:", src)
        self.assertIn('"detector_ocr_prewarm": False', src)

    def test_delete_confirm_registered_everywhere(self):
        import config
        import detector
        import app_web

        self.assertTrue(callable(config.get_delete_templates))
        self.assertIn("delete_confirm", detector.OCR_HINTS)
        self.assertIn("remove car from garage", detector.OCR_HINTS["delete_confirm"])
        self.assertIn("從車庫移除車輛", detector.OCR_HINTS["delete_confirm"])
        self.assertIn("delete_confirm", detector.TEXT_TEMPLATES)
        self.assertIn("delete_confirm", app_web.DELETE_EXPECTED_TEMPLATE_KEYS)

    def test_delete_tab_wired_for_capture(self):
        src = (ROOT / "app_web.py").read_text(encoding="utf-8")
        # delete tab routed to the folder getter in BOTH get_templates + _tpl_folder
        self.assertEqual(src.count('"delete": config.get_delete_templates'), 2)
        self.assertIn("DELETE_EXPECTED_TEMPLATE_KEYS", src)


if __name__ == "__main__":
    unittest.main()
