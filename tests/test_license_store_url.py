import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
KOFI_URL = "https://ko-fi.com/s/edbeb0552c"


class LicenseStoreUrlTests(unittest.TestCase):
    def test_full_auto_purchase_url_points_to_kofi_key_page(self):
        path = ROOT / "license_client.py"
        if not path.exists():
            self.skipTest("license_client.py is protected local source and is not in the public repo")
        source = path.read_text(encoding="utf-8")
        self.assertIn(f'STORE_URL = "{KOFI_URL}"', source)

    def test_buy_uses_license_store_url(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")
        self.assertIn('getattr(license_client, "STORE_URL", None)', source)


if __name__ == "__main__":
    unittest.main()
