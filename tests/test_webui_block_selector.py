import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WebUiBlockSelectorTests(unittest.TestCase):
    def test_middle_column_input_uses_browser_document(self):
        source = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")

        block_selector = re.search(
            r"function blockSelector\(tab, startBtn\) \{(?P<body>.*?)\n\}\n\n// .*mastery",
            source,
            re.S,
        )
        self.assertIsNotNone(block_selector)
        body = block_selector.group("body")

        self.assertNotIn("doc.createElement", body)
        self.assertIn("document.createElement('input')", body)
        self.assertIn("midNum.type = 'number'", body)

    def test_total_car_count_is_editable_without_new_config(self):
        source = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")

        block_selector = re.search(
            r"function blockSelector\(tab, startBtn\) \{(?P<body>.*?)\n\}\n\n// .*mastery",
            source,
            re.S,
        )
        self.assertIsNotNone(block_selector)
        body = block_selector.group("body")

        self.assertIn("totalNum.type = 'number'", body)
        self.assertIn("setTotalCount", body)
        self.assertIn("if (n <= (4 - first)) first = 4 - n", body)
        self.assertNotIn("_block_total", body)


if __name__ == "__main__":
    unittest.main()
