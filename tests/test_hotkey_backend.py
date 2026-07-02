import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class HotkeyBackendTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "app_web.py").read_text(encoding="utf-8")

    def test_win32_register_hotkey_backend_exists(self):
        self.assertIn("RegisterHotKey", self.source)
        self.assertIn("WM_HOTKEY", self.source)
        self.assertIn("MOD_NOREPEAT", self.source)
        self.assertIn("PostThreadMessageW", self.source)

    def test_keyboard_hook_fallback_is_kept(self):
        self.assertIn("keyboard.add_hotkey", self.source)
        self.assertIn("fallback", self.source.lower())

    def test_default_hotkeys_are_mapped_for_win32_backend(self):
        tree = ast.parse(self.source)
        mapper = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_hotkey_vk"
        )
        module = ast.Module(body=[mapper], type_ignores=[])
        ast.fix_missing_locations(module)
        ns = {}
        exec(compile(module, "app_web.py", "exec"), ns)

        expected = {"f9": 0x78, "f10": 0x79, "f12": 0x7B}
        for key, vk in expected.items():
            with self.subTest(key=key):
                self.assertEqual(vk, ns["_hotkey_vk"](key))


if __name__ == "__main__":
    unittest.main()
