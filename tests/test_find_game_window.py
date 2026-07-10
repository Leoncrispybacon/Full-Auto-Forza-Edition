import unittest

import capture

TARGET = "forza horizon 6"


class TitleMatchTests(unittest.TestCase):
    def test_exact_title_only_not_substring(self):
        self.assertTrue(capture._title_is_game("Forza Horizon 6", TARGET))
        self.assertTrue(capture._title_is_game("  forza horizon 6 ", TARGET))
        # a browser tab / wiki page that merely CONTAINS the name must NOT match
        self.assertFalse(capture._title_is_game(
            "Forza Horizon 6 奇幻生活 - Google Chrome", TARGET))
        self.assertFalse(capture._title_is_game(
            "奇幻生活 | Forza Horizon 6 Wiki — Fandom", TARGET))
        self.assertFalse(capture._title_is_game(
            "Forza Horizon 6 at Nexus Mods", TARGET))
        self.assertFalse(capture._title_is_game("", TARGET))


class PickGameHwndTests(unittest.TestCase):
    def test_browser_tab_loses_to_the_game(self):
        # A Forza-titled browser tab + the real game → pick the game, never the
        # browser (the bug: OCR was reading the web page).
        cands = [
            (1, "Forza Horizon 6 奇幻生活 - Google Chrome", "chrome.exe"),
            (2, "Forza Horizon 6", "ForzaHorizon6.exe"),
        ]
        self.assertEqual(capture._pick_game_hwnd(cands, TARGET), 2)

    def test_game_wins_regardless_of_enumeration_order(self):
        cands = [
            (2, "Forza Horizon 6", "ForzaHorizon6.exe"),
            (1, "Forza Horizon 6 at Nexus Mods — Microsoft​ Edge", "msedge.exe"),
        ]
        self.assertEqual(capture._pick_game_hwnd(cands, TARGET), 2)

    def test_only_browser_matches_returns_none(self):
        # No game window → None (so FAFE relaunches / reports no game), NOT the
        # browser hwnd.
        cands = [(1, "Forza Horizon 6 - YouTube - Google Chrome", "chrome.exe")]
        self.assertIsNone(capture._pick_game_hwnd(cands, TARGET))

    def test_explorer_folder_window_is_excluded(self):
        # The game folder open in File Explorer also matches the title substring.
        cands = [(1, "Forza Horizon 6", "explorer.exe"),
                 (2, "Forza Horizon 6", "ForzaHorizon6.exe")]
        self.assertEqual(capture._pick_game_hwnd(cands, TARGET), 2)

    def test_exact_title_preferred_over_substring_among_non_browsers(self):
        cands = [(4, "Forza Horizon 6 Demo", "game.exe"),
                 (5, "Forza Horizon 6", "game.exe")]
        self.assertEqual(capture._pick_game_hwnd(cands, TARGET), 5)

    def test_unreadable_process_name_is_kept(self):
        # If the exe can't be read ('' ), don't drop it — the game must not be lost
        # just because its process image was inaccessible.
        cands = [(9, "Forza Horizon 6", "")]
        self.assertEqual(capture._pick_game_hwnd(cands, TARGET), 9)


if __name__ == "__main__":
    unittest.main()
