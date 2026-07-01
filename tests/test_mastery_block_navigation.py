import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MasteryBlockNavigationTests(unittest.TestCase):
    def test_standalone_mastery_uses_block_selector_first_row_for_navigation(self):
        source = (ROOT / "mastery.py").read_text(encoding="utf-8")

        start_default = source.split("if start_loop is None:", 1)[1].split("start_loop = max", 1)[0]
        self.assertIn("mastery_block_first_row", start_default)
        self.assertNotIn('mastery_start_loop", 1', start_default)

    def test_row_two_block_moves_third_car_to_next_column_top(self):
        import mastery

        previous = mastery._cell_at(2, 1)
        current = mastery._cell_at(2, 2)

        self.assertEqual(previous, (3, 0))
        self.assertEqual(current, (1, 1))
        self.assertEqual(mastery._moves_between(previous, current), ["d", "w", "w"])


if __name__ == "__main__":
    unittest.main()
