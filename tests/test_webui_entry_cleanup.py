import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WebUiEntryCleanupTests(unittest.TestCase):
    def test_app_web_sets_native_thread_caps_before_project_imports(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")

        cap_pos = source.index('os.environ.setdefault("OMP_NUM_THREADS", "2")')
        project_imports = [
            "import config",
            "import capture",
            "from web_overlay import WebOverlay",
        ]

        for needle in project_imports:
            with self.subTest(import_statement=needle):
                self.assertLess(cap_pos, source.index(needle))

        self.assertIn('os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")', source)
        self.assertIn('os.environ.setdefault("KMP_BLOCKTIME", "0")', source)

    def test_ctk_legacy_source_files_are_removed(self):
        removed = [
            "forza_app.py",
            "main_window.py",
            "setup_panel.py",
            "grid_widget.py",
            "log_widget.py",
            "overlay.py",
            "preview_theme.py",
            "theme.py",
        ]

        for rel in removed:
            with self.subTest(path=rel):
                self.assertFalse((ROOT / rel).exists())

    def test_repository_no_longer_imports_removed_ui_toolkit(self):
        offenders = []
        for path in ROOT.rglob("*.py"):
            rel = path.relative_to(ROOT)
            if rel.parts[0] in {"build", "dist", "FAFE_dist", "compiled", "tests"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "custom" + "tkinter" in text:
                offenders.append(str(rel))

        self.assertEqual([], offenders)

    def test_log_warning_lines_render_red(self):
        app_js = (ROOT / "webui" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "webui" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("log-warn", app_js)
        self.assertIn("innerText", app_js)
        self.assertIn(".log-line.log-warn", css)


if __name__ == "__main__":
    unittest.main()
