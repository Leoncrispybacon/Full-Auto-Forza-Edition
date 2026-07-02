import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _method_source(path, class_name, method_name):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method)


def _function_source(path, function_name):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return ast.get_source_segment(source, fn)


class KeepaliveFocusTests(unittest.TestCase):
    def test_fake_active_burst_posts_only_activateapp(self):
        fn = _function_source(ROOT / "capture.py", "set_window_active")
        self.assertIn("_WM_ACTIVATEAPP", fn)
        self.assertNotIn("_WM_NCACTIVATE", fn)
        self.assertNotIn("_WM_ACTIVATE,", fn)
        self.assertNotIn("_WM_SETFOCUS", fn)

    def test_keepalive_skips_fake_active_when_game_is_foreground(self):
        method = _method_source(ROOT / "gameio.py", "GameIO", "start_keepalive")
        self.assertIn("capture.get_foreground_window()", method)
        self.assertIn("!= self.hwnd", method)
        self.assertIn("capture.set_window_active(self.hwnd)", method)

    def test_keepalive_pulses_immediately_and_uses_half_second_interval(self):
        source = (ROOT / "gameio.py").read_text(encoding="utf-8")
        method = _method_source(ROOT / "gameio.py", "GameIO", "start_keepalive")

        tree = ast.parse(source)
        interval = next(
            node.value.value for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id == "_KEEPALIVE_INTERVAL"
        )
        self.assertEqual(interval, 0.5)
        self.assertIn("capture.set_window_active(self.hwnd)", method)
        self.assertLess(
            method.index("capture.set_window_active(self.hwnd)"),
            method.index("def _loop"),
        )


if __name__ == "__main__":
    unittest.main()
