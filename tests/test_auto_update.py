import unittest

class ConfigDefaultTests(unittest.TestCase):
    def test_auto_update_defaults_true(self):
        import config
        self.assertIn("auto_update", config.DEFAULTS)
        self.assertIs(config.DEFAULTS["auto_update"], True)


class UpdaterHelperTests(unittest.TestCase):
    def test_find_installer_asset_returns_url_and_size(self):
        import updater
        release = {"assets": [
            {"name": "other.zip", "browser_download_url": "u0", "size": 1},
            {"name": "FAFE_Setup.exe", "browser_download_url": "u1", "size": 12345},
        ]}
        self.assertEqual(updater.find_installer_asset(release), ("u1", 12345))

    def test_find_installer_asset_missing_returns_none(self):
        import updater
        self.assertEqual(updater.find_installer_asset({"assets": []}), (None, None))

    def test_verify_installer_rejects_size_mismatch(self):
        import updater, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.exe")
            open(p, "wb").write(b"MZ" + b"\0" * 2_000_000)
            self.assertFalse(updater.verify_installer(p, expected_size=999))

    def test_verify_installer_rejects_non_pe(self):
        import updater, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.exe")
            open(p, "wb").write(b"XX" + b"\0" * 2_000_000)
            self.assertFalse(updater.verify_installer(p, expected_size=None))

    def test_verify_installer_rejects_truncated(self):
        import updater, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.exe")
            open(p, "wb").write(b"MZ" + b"\0" * 10)
            self.assertFalse(updater.verify_installer(p, expected_size=None))

    def test_verify_installer_accepts_good(self):
        import updater, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.exe")
            data = b"MZ" + b"\0" * 2_000_000
            open(p, "wb").write(data)
            self.assertTrue(updater.verify_installer(p, expected_size=len(data)))


class AppWebWiringTests(unittest.TestCase):
    def _src(self):
        return open("app_web.py", encoding="utf-8-sig").read()

    def test_install_update_method_present(self):
        self.assertIn("def install_update(self", self._src())

    def test_install_update_gates_on_frozen_and_flag(self):
        s = self._src()
        i = s.index("def install_update(self")
        body = s[i:i + 1500]
        self.assertIn("_is_frozen()", body)
        self.assertIn('"auto_update"', body)
        self.assertIn("/VERYSILENT", body)

    def test_startup_purges_update_dir(self):
        self.assertIn("_purge_update_dir", self._src())

    def test_init_payload_exposes_auto_update(self):
        self.assertIn('"auto_update"', self._src())


class InstallerConfigTests(unittest.TestCase):
    def test_iss_closes_and_restarts_apps(self):
        iss = open("build_installer.iss", encoding="utf-8").read()
        self.assertIn("CloseApplications=yes", iss)
        self.assertIn("RestartApplications=yes", iss)
