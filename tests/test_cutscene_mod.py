import unittest
import os
import tempfile
import zipfile
import cutscene_mod

FIXTURE_XML = b"""
<Cinematic Version="2" Name="pgc_test" IsSharedLibrary="0">
  <Scene Version="2" Name="Scene">
    <Group Version="2" Name="SceneRoot">
      <Cinematics3DObject Version="2" Name="Scene_Object">
        <CarProxy Version="2" Name="ForzaCarProxy001" AnimEvent="">
          <Animations Version="2">
            <Track Version="2" path="AnimEvent" timeOffset="0.000000">
              <Key time="0.031250" value="CarEvents_Implode@x100"/>
            </Track>
          </Animations>
        </CarProxy>
        <Director Version="2" Name="ForzaDirector001" CurrentCamera="ForzaCamera003"
          FadeA="1.000000" MotionBlur="1" BorderTop="-0.750000" BorderBottom="0.750000">
          <Animations Version="2">
            <Track Version="2" path="BorderTop" timeOffset="0.000000">
              <Key Time="0.000000" Value="-0.750000"/>
            </Track>
            <Track Version="2" path="BorderBottom" timeOffset="0.000000">
              <Key Time="0.000000" Value="0.750000"/>
            </Track>
            <Track Version="2" path="CurrentCamera" timeOffset="0.000000">
              <Key time="0.000000" value="ForzaCamera003"/>
            </Track>
            <Track Version="2" path="FadeA" timeOffset="0.000000">
              <Key Time="0.000000" Value="1.000000"/>
            </Track>
            <Track Version="2" path="KeepMe" timeOffset="0.000000">
              <Key time="0.000000" value="x"/>
            </Track>
          </Animations>
        </Director>
      </Cinematics3DObject>
    </Group>
  </Scene>
  <Timeline Version="2" duration="8.000000" looping="0"/>
</Cinematic>
"""


class ConfigKeysTests(unittest.TestCase):
    def test_cutscene_skip_defaults_present(self):
        import config
        self.assertIn("cutscene_skip_installed", config.DEFAULTS)
        self.assertIs(config.DEFAULTS["cutscene_skip_installed"], False)
        self.assertIn("cutscene_skip_game_dir", config.DEFAULTS)
        self.assertEqual(config.DEFAULTS["cutscene_skip_game_dir"], "")


class TransformTests(unittest.TestCase):
    def _root(self, raw):
        import xml.etree.ElementTree as ET
        return ET.fromstring(raw)

    def test_timeline_duration_zeroed(self):
        import cutscene_mod
        root = self._root(cutscene_mod.transform_xml(FIXTURE_XML))
        for tl in root.iter("Timeline"):
            self.assertEqual(tl.get("duration"), "0.0")

    def test_director_attrs_set(self):
        import cutscene_mod
        root = self._root(cutscene_mod.transform_xml(FIXTURE_XML))
        d = root.find(".//Director")
        self.assertEqual(d.get("FadeA"), "0.000000")
        self.assertEqual(d.get("MotionBlur"), "0")
        self.assertEqual(d.get("BorderTop"), "-1.100000")
        self.assertEqual(d.get("BorderBottom"), "1.100000")
        self.assertEqual(d.get("CurrentCamera"), "ForzaCamera001")
        self.assertEqual(d.get("GSRLocatorName"), "")
        self.assertEqual(d.get("GSRRoute"), "-1")

    def test_all_director_tracks_dropped_carproxy_kept(self):
        import cutscene_mod
        root = self._root(cutscene_mod.transform_xml(FIXTURE_XML))
        # EVERY Director animation track is removed (incl. the unrelated "KeepMe"),
        # since the mod strips them all and none play at duration 0.
        dir_tracks = root.findall(".//Director/Animations/Track")
        self.assertEqual(dir_tracks, [])
        # ...but tracks OUTSIDE the Director (e.g. the CarProxy AnimEvent) survive.
        carproxy_tracks = root.findall(".//CarProxy/Animations/Track")
        self.assertTrue(carproxy_tracks)

    def test_carproxy_animevent_untouched(self):
        import cutscene_mod
        root = self._root(cutscene_mod.transform_xml(FIXTURE_XML))
        key = root.find(".//CarProxy/Animations/Track/Key")
        self.assertEqual(key.get("value"), "CarEvents_Implode@x100")

    def test_aborts_when_no_timeline(self):
        import cutscene_mod
        with self.assertRaises(cutscene_mod.TransformError):
            cutscene_mod.transform_xml(b"<Cinematic><Director/></Cinematic>")

    def test_aborts_when_no_director(self):
        import cutscene_mod
        with self.assertRaises(cutscene_mod.TransformError):
            cutscene_mod.transform_xml(b'<Cinematic><Timeline duration="8.0"/></Cinematic>')


class PathTests(unittest.TestCase):
    def test_find_cinematics_zip_prefers_content_media(self):
        import cutscene_mod
        with tempfile.TemporaryDirectory() as g:
            want = os.path.join(g, "Content", "media", "Cinematics.zip")
            os.makedirs(os.path.dirname(want))
            open(want, "wb").close()
            self.assertEqual(cutscene_mod.find_cinematics_zip(g), want)

    def test_find_cinematics_zip_walks_when_not_in_default(self):
        import cutscene_mod
        with tempfile.TemporaryDirectory() as g:
            want = os.path.join(g, "weird", "sub", "Cinematics.zip")
            os.makedirs(os.path.dirname(want))
            open(want, "wb").close()
            self.assertEqual(cutscene_mod.find_cinematics_zip(g), want)

    def test_find_cinematics_zip_missing_returns_none(self):
        import cutscene_mod
        with tempfile.TemporaryDirectory() as g:
            self.assertIsNone(cutscene_mod.find_cinematics_zip(g))

    def test_override_dest_mirrors_entry_under_override_root(self):
        import cutscene_mod
        dest = cutscene_mod.override_dest(r"C:\game", "forte/autoshow/pgc3002.xml")
        self.assertEqual(
            dest,
            os.path.join(r"C:\game", "mediapc", "Cinematics",
                         "forte", "autoshow", "pgc3002.xml"),
        )


class InstallTests(unittest.TestCase):
    def _fake_game(self, g):
        """Create Content\\media\\Cinematics.zip with the two targets + a decoy.
        Returns the zip's original bytes."""
        zpath = os.path.join(g, "Content", "media", "Cinematics.zip")
        os.makedirs(os.path.dirname(zpath))
        with zipfile.ZipFile(zpath, "w") as z:
            for base in cutscene_mod.TARGET_BASENAMES:
                z.writestr(f"forte/autoshow/{base}", FIXTURE_XML)
            z.writestr("forte/autoshow/pgc9999_other.xml", FIXTURE_XML)
        with open(zpath, "rb") as f:
            return f.read()

    def _durations(self, raw):
        import xml.etree.ElementTree as ET
        return [tl.get("duration") for tl in ET.fromstring(raw).iter("Timeline")]

    def test_install_edits_zip_entries_and_backs_up(self):
        with tempfile.TemporaryDirectory() as g:
            before = self._fake_game(g)
            cutscene_mod.install(g)
            zpath = cutscene_mod.find_cinematics_zip(g)
            with zipfile.ZipFile(zpath) as z:
                names = z.namelist()
                for base in cutscene_mod.TARGET_BASENAMES:
                    entry = cutscene_mod._zip_entry_for(names, base)
                    self.assertEqual(self._durations(z.read(entry)), ["0.0"])
                # decoy entry copied through untouched (original 8s duration)
                self.assertEqual(
                    self._durations(z.read("forte/autoshow/pgc9999_other.xml")),
                    ["8.000000"])
            bak = cutscene_mod._backup_path(zpath)
            self.assertTrue(os.path.isfile(bak))
            with open(bak, "rb") as f:
                self.assertEqual(f.read(), before)   # pristine original preserved

    def test_status_reflects_install_then_uninstall_restores_zip(self):
        with tempfile.TemporaryDirectory() as g:
            before = self._fake_game(g)
            self.assertFalse(cutscene_mod.status(g)["files_present"])
            self.assertFalse(cutscene_mod.status(g)["backup_present"])
            cutscene_mod.install(g)
            s = cutscene_mod.status(g)
            self.assertTrue(s["files_present"])
            self.assertTrue(s["backup_present"])
            cutscene_mod.uninstall(g)
            s2 = cutscene_mod.status(g)
            self.assertFalse(s2["files_present"])
            self.assertFalse(s2["backup_present"])   # backup consumed by restore
            zpath = cutscene_mod.find_cinematics_zip(g)
            with open(zpath, "rb") as f:
                self.assertEqual(f.read(), before)   # zip restored to pristine

    def test_install_is_idempotent_and_keeps_pristine_backup(self):
        with tempfile.TemporaryDirectory() as g:
            before = self._fake_game(g)
            cutscene_mod.install(g)
            cutscene_mod.install(g)   # 2nd run must NOT re-backup the edited zip
            self.assertTrue(cutscene_mod.status(g)["files_present"])
            bak = cutscene_mod._backup_path(cutscene_mod.find_cinematics_zip(g))
            with open(bak, "rb") as f:
                self.assertEqual(f.read(), before)   # still pristine

    def test_install_raises_when_zip_missing(self):
        with tempfile.TemporaryDirectory() as g:
            with self.assertRaises(cutscene_mod.CutsceneModError):
                cutscene_mod.install(g)

    def test_uninstall_tolerates_already_gone(self):
        with tempfile.TemporaryDirectory() as g:
            self._fake_game(g)
            cutscene_mod.uninstall(g)   # no backup → no-op, must not raise
            self.assertFalse(cutscene_mod.status(g)["files_present"])


class BridgeTests(unittest.TestCase):
    def test_api_exposes_cutscene_methods(self):
        with open("app_web.py", encoding="utf-8-sig") as f:
            src = f.read()
        for m in ("def cutscene_mod_status", "def cutscene_mod_install",
                  "def cutscene_mod_uninstall", "def cutscene_mod_browse_game_dir"):
            self.assertIn(m, src)

    def test_result_strings_defined_both_langs(self):
        # app_lang.py's STRINGS is {key: {"en": ..., "zh-tw": ...}}, i.e. each
        # key appears once as a dict key with both languages nested under it
        # (not two separate en/zh-tw tables) — assert against the loaded
        # structure rather than counting substrings.
        import app_lang
        for k in ("cutscene_skip_installed_ok", "cutscene_skip_uninstalled",
                  "cutscene_skip_no_game", "cutscene_skip_failed"):
            entry = app_lang.STRINGS.get(k)
            self.assertIsNotNone(entry, f"{k} missing from app_lang.STRINGS")
            self.assertIn("en", entry)
            self.assertIn("zh-tw", entry)


class WebuiTests(unittest.TestCase):
    def test_i18n_has_cutscene_keys_both_langs(self):
        src = open("webui/i18n.js", encoding="utf-8").read()
        for k in ("cutscene_skip_title", "cutscene_skip_warn_body",
                  "cutscene_skip_warn_confirm"):
            self.assertGreaterEqual(src.count(k), 2)

    def test_appjs_calls_bridge(self):
        src = open("webui/app.js", encoding="utf-8").read()
        self.assertIn("cutscene_mod_install", src)
        self.assertIn("cutscene_mod_uninstall", src)


if __name__ == "__main__":
    unittest.main()
