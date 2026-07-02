import importlib
import sys
import unittest


class MasteryStartDependencyTests(unittest.TestCase):
    def test_mastery_import_does_not_require_pydirectinput(self):
        sys.modules.pop("mastery", None)
        try:
            importlib.import_module("mastery")
        except ModuleNotFoundError as exc:
            if exc.name == "pydirectinput":
                self.fail("mastery import should not require stale pydirectinput")
            raise


if __name__ == "__main__":
    unittest.main()
