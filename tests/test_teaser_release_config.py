import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TeaserReleaseConfigTests(unittest.TestCase):
    def test_development_version_is_205(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        installer = (ROOT / "build_installer.iss").read_text(encoding="utf-8")

        self.assertIn('VERSION = "2.0.5"', version)
        self.assertIn('#define MyAppVersion "2.0.5"', installer)

    def test_backend_keeps_missing_full_auto_builds_in_teaser_mode(self):
        source = (ROOT / "app_web.py").read_text(encoding="utf-8")

        self.assertIn('"coming_soon": _full_auto is None', source)
        self.assertIn('"full_auto_bundled": _full_auto is not None', source)

    def test_build_entry_points_are_split_by_distribution_type(self):
        teaser = (ROOT / "build_app_teaser.bat").read_text(encoding="utf-8", errors="ignore")
        paid = (ROOT / "build_app_paid.bat").read_text(encoding="utf-8", errors="ignore")

        self.assertFalse((ROOT / "build_app.bat").exists())
        self.assertFalse((ROOT / "build_app_core.bat").exists())
        self.assertIn("set FAFE_FULLAUTO=0", teaser)
        self.assertIn("set FAFE_BUILD_KIND=teaser", teaser)
        self.assertNotIn("build_app_core.bat", teaser)
        self.assertIn("set FAFE_FULLAUTO=1", paid)
        self.assertIn("set FAFE_BUILD_KIND=paid", paid)
        self.assertNotIn("build_app_core.bat", paid)

    def test_teaser_build_omits_paid_modules_and_templates(self):
        build = (ROOT / "build_app_teaser.bat").read_text(encoding="utf-8", errors="ignore")

        self.assertIn("set FA_ADD=", build)
        self.assertIn("set LIC_ADD=", build)
        self.assertRegex(build, re.compile(r'if /i "%FAFE_FULLAUTO%"=="1".*FA_ADD=', re.I))
        self.assertRegex(build, re.compile(r'if /i "%FAFE_FULLAUTO%"=="1".*LIC_ADD=', re.I))
        self.assertIn("--exclude-module full_auto", build)
        self.assertIn("--exclude-module license_client", build)
        self.assertIn("%FA_ADD%", build)
        self.assertIn("%LIC_ADD%", build)
        self.assertIn('if /i not "%FAFE_FULLAUTO%"=="1" for /d %%D', build)

    def test_build_scripts_strip_unused_cuda_ocr_dlls(self):
        for script in ("build_app_teaser.bat", "build_app_paid.bat"):
            with self.subTest(script=script):
                build = (ROOT / script).read_text(encoding="utf-8", errors="ignore")

                self.assertIn("Removing unused CUDA OCR DLLs", build)
                self.assertIn("cublasLt64_13.dll", build)
                self.assertIn("cublas64_13.dll", build)
                self.assertIn("cufft64_12.dll", build)
                self.assertIn("onnxruntime_providers_cuda.dll", build)
                self.assertIn("onnxruntime_providers_tensorrt.dll", build)

    def test_build_scripts_stay_batch_parser_safe(self):
        for script in ("build_app_teaser.bat", "build_app_paid.bat"):
            with self.subTest(script=script):
                raw = (ROOT / script).read_bytes()
                build = raw.decode("utf-8", errors="ignore")

                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn("for %%F in ( ^", build)
                self.assertNotIn("\n::", build)

    def test_build_scripts_fail_if_installer_does_not_build(self):
        for script in ("build_app_teaser.bat", "build_app_paid.bat"):
            with self.subTest(script=script):
                build = (ROOT / script).read_text(encoding="utf-8", errors="ignore")

                self.assertNotIn("WARNING: installer build failed", build)
                self.assertIn("ERROR: installer build failed", build)
                self.assertIn("Output\\FAFE_Setup.exe is locked or in use", build)
                self.assertIn("LSS 10000000", build)

    def test_protected_module_builds_disable_nuitka_ccache(self):
        build = (ROOT / "build_app_paid.bat").read_text(encoding="utf-8", errors="ignore")

        self.assertEqual(build.count("--disable-cache=ccache"), 2)


if __name__ == "__main__":
    unittest.main()
