from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LicenseWorkerTests(unittest.TestCase):
    def test_fulfillment_idempotency_uses_order_id_not_email(self):
        path = ROOT / "licensing" / "worker.js"
        if not path.exists():
            self.skipTest("licensing/worker.js is protected local tooling and is not in the public repo")
        source = path.read_text(encoding="utf-8")

        self.assertIn("const orderId =", source)
        self.assertIn('"assigned:order:" + orderId', source)
        self.assertNotIn('LICENSES.get("assigned:" + email)', source)


if __name__ == "__main__":
    unittest.main()
