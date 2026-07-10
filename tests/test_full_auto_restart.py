from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FullAutoRestartTests(unittest.TestCase):
    """Auto-restart the game every N completed Full Auto cycles."""

    def test_should_restart_off_when_every_is_zero_or_negative(self):
        import full_auto
        for n in range(0, 5):
            self.assertFalse(full_auto._should_restart(n, 0))
            self.assertFalse(full_auto._should_restart(n, -3))

    def test_should_restart_fires_on_exact_multiples_only(self):
        import full_auto
        # every=3 → fire after 3, 6, 9; not on 0/1/2/4/5.
        fired = [n for n in range(0, 10) if full_auto._should_restart(n, 3)]
        self.assertEqual(fired, [3, 6, 9])

    def test_should_restart_every_one_fires_each_completed_cycle(self):
        import full_auto
        self.assertFalse(full_auto._should_restart(0, 1))
        self.assertTrue(all(full_auto._should_restart(n, 1) for n in range(1, 5)))

    def test_config_default_is_off(self):
        import config
        self.assertEqual(config.DEFAULTS["full_auto_restart_cycles"], 0)

    def test_run_wires_restart_via_relaunch_and_aborts_on_failure(self):
        source = (ROOT / "full_auto.py").read_text(encoding="utf-8")
        # Fires at the cycle boundary via the shared relaunch path…
        self.assertIn("_should_restart(completed_cycles, restart_cycles)", source)
        self.assertIn("game_relaunch.relaunch_game(cfg, log_cb, stop_cb=stop)", source)
        # …and a failed relaunch aborts the run (does not fall through).
        self.assertIn("aborted = True", source)


if __name__ == "__main__":
    unittest.main()
