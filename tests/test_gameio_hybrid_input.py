import unittest
from unittest import mock

import gameio


class GameIOHybridInputTests(unittest.TestCase):
    def _io(self):
        io = gameio.GameIO.__new__(gameio.GameIO)
        io.cfg = {}
        io._log = lambda _m: None
        io._lang = "en"
        io.hwnd = 100
        io.bg = True
        io.win_capture = True
        io.cap_left = 10
        io.cap_top = 20
        io.width = 800
        io.height = 600
        io._crop_x = 0
        io._crop_y = 0
        io._held = {}
        io._ka_quiet_until = 0.0
        return io

    def test_press_uses_sendinput_when_game_is_foreground(self):
        io = self._io()
        with mock.patch.object(gameio.capture, "get_foreground_window", return_value=100), \
                mock.patch.object(gameio.capture, "post_key") as post_key, \
                mock.patch.object(gameio, "_send_vk") as send_vk:
            io.press("enter")

        post_key.assert_not_called()
        self.assertEqual(send_vk.call_count, 2)

    def test_press_uses_postmessage_when_game_is_background(self):
        io = self._io()
        with mock.patch.object(gameio.capture, "get_foreground_window", return_value=200), \
                mock.patch.object(gameio.capture, "post_key") as post_key, \
                mock.patch.object(gameio, "_send_vk") as send_vk:
            io.press("enter")

        self.assertEqual(post_key.call_count, 2)
        send_vk.assert_not_called()

    def test_held_key_switches_input_method_on_focus_change(self):
        io = self._io()
        focus = {"hwnd": 100}

        with mock.patch.object(gameio.capture, "get_foreground_window",
                               side_effect=lambda: focus["hwnd"]), \
                mock.patch.object(gameio.capture, "post_key") as post_key, \
                mock.patch.object(gameio, "_send_scancode") as send_scancode:
            io.hold_press("w")
            focus["hwnd"] = 200
            io.hold_press("w")

        self.assertEqual(io._held["w"], "post")
        send_scancode.assert_any_call("w", False)
        send_scancode.assert_any_call("w", True)
        post_key.assert_called()

    def test_held_key_switches_back_to_sendinput_on_refocus(self):
        io = self._io()
        focus = {"hwnd": 200}

        with mock.patch.object(gameio.capture, "get_foreground_window",
                               side_effect=lambda: focus["hwnd"]), \
                mock.patch.object(gameio.capture, "post_key") as post_key, \
                mock.patch.object(gameio, "_send_scancode") as send_scancode:
            io.hold_press("w")
            focus["hwnd"] = 100
            io.hold_press("w")

        self.assertEqual(io._held["w"], "send")
        self.assertGreaterEqual(post_key.call_count, 2)
        send_scancode.assert_called_with("w", False)


if __name__ == "__main__":
    unittest.main()
