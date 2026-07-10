import unittest
from pathlib import Path


class ImeManagedTests(unittest.TestCase):
    def test_one_shot_latch_skips_after_first_switch(self):
        import capture

        capture.set_ime_managed(False)
        self.addCleanup(capture.set_ime_managed, False)
        self.assertFalse(capture._ime_managed)
        self.assertFalse(capture._ime_switched)

        # Arming resets the one-shot so the next call performs the single switch.
        capture.set_ime_managed(True)
        self.assertTrue(capture._ime_managed)
        self.assertFalse(capture._ime_switched)

        # Once the switch has happened, further calls no-op (return True) without
        # touching the layout — the point of one-shot management.
        capture._ime_switched = True
        self.assertTrue(capture.force_english_ime())

        # Disarming resets, so standalone runs switch normally again.
        capture.set_ime_managed(False)
        self.assertFalse(capture._ime_switched)

    def test_full_auto_arms_and_releases_ime_management(self):
        p = Path("full_auto.py")
        if not p.exists():
            self.skipTest("full_auto.py is protected local source and not in the public repo")
        src = p.read_text(encoding="utf-8")
        self.assertIn("set_ime_managed(True)", src)     # armed for the chain
        self.assertIn("set_ime_managed(False)", src)    # released (in finally)


if __name__ == "__main__":
    unittest.main()
