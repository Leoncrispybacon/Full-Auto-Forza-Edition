import unittest
from unittest import mock

import web_overlay


class OverlayMonitorTests(unittest.TestCase):
    def test_saved_primary_position_defaults_to_selected_monitor(self):
        with mock.patch.object(web_overlay.capture, "get_monitor_dims",
                               return_value=(2560, 1440, 1920, 0)):
            overlay = web_overlay.WebOverlay("overlay.html", monitor_index=2)
            width, height = overlay._screen_size()

            self.assertFalse(overlay._pos_on_monitor(60, 60))
            self.assertEqual(
                overlay._default_pos(width, height),
                (1920 + 2560 - width - 24, 24),
            )

    def test_clamp_uses_selected_monitor_bounds(self):
        with mock.patch.object(web_overlay.capture, "get_monitor_dims",
                               return_value=(1280, 800, -1280, 120)):
            overlay = web_overlay.WebOverlay("overlay.html", monitor_index=2)

            self.assertEqual(overlay._clamp_pos(9999, 9999, 300, 200),
                             (-1280 + 1280 - 300 - 8, 120 + 800 - 200 - 8))


if __name__ == "__main__":
    unittest.main()
