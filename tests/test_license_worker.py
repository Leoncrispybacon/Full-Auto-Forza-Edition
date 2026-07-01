from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LicenseWorkerTests(unittest.TestCase):
    def test_fulfillment_idempotency_uses_order_id_not_email(self):
        source = (ROOT / "licensing" / "worker.js").read_text(encoding="utf-8")

        self.assertIn("const orderId =", source)
        self.assertIn('"assigned:order:" + orderId', source)
        self.assertNotIn('LICENSES.get("assigned:" + email)', source)


if __name__ == "__main__":
    unittest.main()
