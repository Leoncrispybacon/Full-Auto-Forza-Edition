import sys
import types
import unittest
from unittest import mock


class _FakeSimpleAudioVolume:
    def __init__(self, volume=0.42):
        self.volume = volume
        self.muted = 0
        self.calls = []

    def GetMasterVolume(self):
        return self.volume

    def SetMasterVolume(self, volume, _ctx):
        self.calls.append(("SetMasterVolume", volume))
        self.volume = volume

    def SetMute(self, muted, _ctx):
        self.calls.append(("SetMute", muted))
        self.muted = muted


class _FakeSession:
    def __init__(self, pid, volume=0.42):
        self.ProcessId = pid
        self.SimpleAudioVolume = _FakeSimpleAudioVolume(volume)


class GameAudioMuteTests(unittest.TestCase):
    def setUp(self):
        import capture

        capture._MUTED_PROCESS_VOLUMES.clear()

    def _install_fake_pycaw(self, sessions):
        fake_audio_utilities = types.SimpleNamespace(
            GetAllSessions=lambda: sessions)
        fake_pycaw_module = types.ModuleType("pycaw.pycaw")
        fake_pycaw_module.AudioUtilities = fake_audio_utilities
        fake_pkg = types.ModuleType("pycaw")
        fake_comtypes = types.ModuleType("comtypes")
        fake_comtypes.CoInitialize = lambda: None
        fake_comtypes.CoUninitialize = lambda: None

        return mock.patch.dict(sys.modules, {
            "pycaw": fake_pkg,
            "pycaw.pycaw": fake_pycaw_module,
            "comtypes": fake_comtypes,
        })

    def test_unmute_restores_original_session_volume(self):
        import capture

        session = _FakeSession(pid=1234, volume=0.37)
        with self._install_fake_pycaw([session]):
            self.assertTrue(capture.set_process_muted(1234, True))
            session.SimpleAudioVolume.volume = 1.0
            self.assertTrue(capture.set_process_muted(1234, False))

        self.assertEqual(session.SimpleAudioVolume.volume, 0.37)
        self.assertIn(("SetMasterVolume", 0.37), session.SimpleAudioVolume.calls)
        self.assertEqual(session.SimpleAudioVolume.muted, 0)

    def test_shutdown_cleanup_unmutes_tracked_processes(self):
        import capture

        session = _FakeSession(pid=4321, volume=0.25)
        with self._install_fake_pycaw([session]):
            self.assertTrue(capture.set_process_muted(4321, True))
            session.SimpleAudioVolume.volume = 1.0
            capture.unmute_tracked_processes()

        self.assertEqual(session.SimpleAudioVolume.volume, 0.25)
        self.assertEqual(session.SimpleAudioVolume.muted, 0)
        self.assertNotIn(4321, capture._MUTED_PROCESS_VOLUMES)

    def test_app_shutdown_flushes_tracked_audio_before_hard_exit(self):
        with open("app_web.py", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("capture.unmute_tracked_processes()", source)
        self.assertLess(
            source.index("capture.unmute_tracked_processes()"),
            source.index("threading.Timer(1.5"),
        )


if __name__ == "__main__":
    unittest.main()
