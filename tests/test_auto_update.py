import unittest

class ConfigDefaultTests(unittest.TestCase):
    def test_auto_update_defaults_true(self):
        import config
        self.assertIn("auto_update", config.DEFAULTS)
        self.assertIs(config.DEFAULTS["auto_update"], True)
