from pathlib import Path
import unittest


class HowtoGuideLinkTests(unittest.TestCase):
    def test_full_auto_howto_opens_full_auto_guide_in_current_language(self):
        source = Path("app_web.py").read_text(encoding="utf-8")

        self.assertIn('"full_auto": "full-auto"', source)
        self.assertIn('"zh-tw" if cfg.get("lang") == "zh-tw" else "en"', source)
        self.assertIn('f"{lang}/guides/{slug}/"', source)


if __name__ == "__main__":
    unittest.main()
