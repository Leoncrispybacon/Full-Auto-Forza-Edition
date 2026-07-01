import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


class AutoBugReportTests(unittest.TestCase):
    def test_report_can_use_trigger_name_without_opening_folder(self):
        import config
        import report

        with tempfile.TemporaryDirectory() as td:
            old_base = config.BASE_DIR
            config.BASE_DIR = td
            try:
                with mock.patch("report.grab_frame",
                                return_value=np.zeros((4, 4, 3), dtype=np.uint8)), \
                     mock.patch("report.os.startfile") as startfile:
                    path = report.generate_report(
                        {"lang": "en"}, 1, {"Activity": ["x"]},
                        trigger_name="Race entry recovery",
                        open_folder=False)
            finally:
                config.BASE_DIR = old_base

        self.assertIn("Race entry recovery - ", Path(path).name)
        self.assertTrue(path.endswith(".zip"))
        startfile.assert_not_called()

    def test_recovery_trigger_callback_runs_once_per_stage_route(self):
        import recovery

        calls = []

        def route():
            return len(calls) > 0

        ok = recovery.run_stage_route(
            "Race entry", route, stop=lambda: False, log_cb=lambda _m: None,
            max_retries=2, recover_fn=lambda: True,
            trigger_cb=lambda label: calls.append(label))

        self.assertTrue(ok)
        self.assertEqual(calls, ["Race entry recovery"])


if __name__ == "__main__":
    unittest.main()
