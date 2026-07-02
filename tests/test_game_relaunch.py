import unittest
from pathlib import Path


class GameRelaunchTests(unittest.TestCase):
    def test_config_defaults_enable_auto_relaunch(self):
        import config

        self.assertIs(config.DEFAULTS["game_relaunch_enabled"], True)
        self.assertEqual(config.DEFAULTS["game_platform"], "steam")
        self.assertEqual(config.DEFAULTS["game_steam_uri"], "steam://rungameid/2483190")
        self.assertIn("game_custom_launch", config.DEFAULTS)
        self.assertEqual(
            config.DEFAULTS["gamepass_fallback_appid"],
            "Microsoft.ForteBaseGame_8wekyb3d8bbwe!Forzahorizon6")
        self.assertIn("thresh_launch_start_prompt", config.DEFAULTS)
        self.assertIn("thresh_launch_continue", config.DEFAULTS)

    def test_auto_uses_steam_when_process_path_is_steam(self):
        import game_relaunch

        target = game_relaunch.resolve_launch_target(
            {"game_platform": "auto", "game_steam_uri": "steam://rungameid/2483190"},
            process_path=r"D:\SteamLibrary\steamapps\common\Forza Horizon 6\Forza.exe",
            appid_lookup=lambda _name: "Microsoft.ForteBaseGame_8wekyb3d8bbwe!Forzahorizon6")

        self.assertEqual(target.platform, "steam")
        self.assertEqual(target.command, ["cmd", "/c", "start", "", "steam://rungameid/2483190"])

    def test_auto_uses_gamepass_when_process_path_is_windowsapps(self):
        import game_relaunch

        target = game_relaunch.resolve_launch_target(
            {"game_platform": "auto"},
            process_path=r"C:\Program Files\WindowsApps\Microsoft.ForteBaseGame_8wekyb3d8bbwe\Forza.exe",
            appid_lookup=lambda _name: None)

        self.assertEqual(target.platform, "xbox")
        self.assertEqual(
            target.command,
            ["explorer.exe", r"shell:AppsFolder\Microsoft.ForteBaseGame_8wekyb3d8bbwe!Forzahorizon6"])

    def test_auto_uses_detected_gamepass_appid_when_no_process_hint(self):
        import game_relaunch

        target = game_relaunch.resolve_launch_target(
            {"game_platform": "auto", "gamepass_app_name": "Forza Horizon 6"},
            process_path=None,
            appid_lookup=lambda name: "Detected.Package!Forza" if name == "Forza Horizon 6" else None)

        self.assertEqual(target.platform, "xbox")
        self.assertEqual(target.command, ["explorer.exe", r"shell:AppsFolder\Detected.Package!Forza"])

    def test_auto_falls_back_to_steam_when_no_xbox_install_detected(self):
        import game_relaunch

        target = game_relaunch.resolve_launch_target(
            {"game_platform": "auto", "game_steam_uri": "steam://rungameid/2483190"},
            process_path=None,
            appid_lookup=lambda _name: None)

        self.assertEqual(target.platform, "steam")
        self.assertEqual(target.command, ["cmd", "/c", "start", "", "steam://rungameid/2483190"])

    def test_explicit_xbox_uses_known_fallback_when_detection_fails(self):
        import game_relaunch

        target = game_relaunch.resolve_launch_target(
            {"game_platform": "xbox"},
            process_path=None,
            appid_lookup=lambda _name: None)

        self.assertEqual(target.platform, "xbox")
        self.assertEqual(
            target.command,
            ["explorer.exe", r"shell:AppsFolder\Microsoft.ForteBaseGame_8wekyb3d8bbwe!Forzahorizon6"])

    def test_close_posts_wm_close_before_force_kill(self):
        import game_relaunch

        calls = []

        ok = game_relaunch.close_game_window(
            hwnd=100,
            pid=200,
            wait_s=0,
            post_close=lambda hwnd: calls.append(("close", hwnd)) or True,
            is_running=lambda pid: True,
            kill_process=lambda pid: calls.append(("kill", pid)) or True,
            sleep=lambda _s: None)

        self.assertTrue(ok)
        self.assertEqual(calls, [("close", 100), ("kill", 200)])

    def test_race_history_loading_dead_zone_uses_relaunch_helper(self):
        source = Path("race.py").read_text(encoding="utf-8")

        self.assertIn("import game_relaunch", source)
        self.assertIn('key == "my_history" and retry_to == "choose_race_type"', source)
        self.assertIn("game_relaunch.relaunch_game", source)
        self.assertIn("_RACE_HISTORY_DEAD_ZONE_WINDOW = 60.0", source)
        self.assertIn("_HISTORY_RETRY_CHECK_WINDOW = 3.0", source)
        self.assertIn("_HISTORY_POST_RETRY_RECOVERY_WINDOW = 10.0", source)

    def test_race_history_retries_only_when_still_on_history(self):
        source = Path("race.py").read_text(encoding="utf-8")
        block = source.split("def _handle_history_enter", 1)[1].split(
            "def _navigate_to_event", 1)[0]

        self.assertNotIn("def _enter_until", source)
        self.assertNotIn("log_race_nav_retry", source)
        self.assertIn('_detect_nav_any((retry_to, key), _HISTORY_RETRY_CHECK_WINDOW)', block)
        self.assertIn("_HISTORY_POST_RETRY_RECOVERY_WINDOW", block)
        self.assertIn('_kp("enter", post_wait=0.0)', block)
        self.assertIn("_RACE_HISTORY_DEAD_ZONE_WINDOW", block)

    def test_race_relaunch_waits_until_entry_recovery_fails(self):
        source = Path("race.py").read_text(encoding="utf-8")
        entry_block = source.split("def _handle_history_enter", 1)[1].split(
            "route_retries =", 1)[0]
        recovery_block = source.split(
            'if not recovery.run_stage_route("Race entry"', 1)[1].split(
            "loop_count = 0", 1)[0]

        self.assertNotIn("game_relaunch.relaunch_game", entry_block)
        self.assertIn("pending_history_relaunch = True", entry_block)
        self.assertIn("if pending_history_relaunch and not stop():", recovery_block)
        self.assertIn("game_relaunch.relaunch_game", recovery_block)

    def test_race_setup_exposes_relaunch_templates(self):
        import app_web
        import config

        self.assertIn("launch_start_prompt", app_web.RELAUNCH_TEMPLATE_KEYS)
        self.assertIn("launch_continue", app_web.RELAUNCH_TEMPLATE_KEYS)
        self.assertIn('"race": config.get_race_templates', Path("app_web.py").read_text(encoding="utf-8"))
        self.assertTrue(config.get_relaunch_templates(config.REFERENCE_RES, "cht").endswith(
            r"templates\cht\relaunch\built-in"))

    def test_relaunch_game_runs_post_launch_route_after_launch(self):
        import game_relaunch

        calls = []

        ok = game_relaunch.relaunch_game(
            {"game_relaunch_enabled": True, "game_platform": "steam"},
            log_cb=lambda _m: None,
            find_window=lambda _title: 100,
            get_pid=lambda _hwnd: 200,
            process_path_fn=lambda _pid: r"D:\SteamLibrary\steamapps\common\Forza Horizon 6\Forza.exe",
            close_fn=lambda hwnd, pid: calls.append(("close", hwnd, pid)) or True,
            launch_fn=lambda target: calls.append(("launch", target.platform)) or True,
            post_launch_fn=lambda cfg, log_cb: calls.append(("post", cfg["game_platform"])) or True,
            sleep=lambda _s: None)

        self.assertTrue(ok)
        self.assertEqual(calls, [("close", 100, 200), ("launch", "steam"), ("post", "steam")])
        self.assertTrue(calls)

    def test_relaunch_game_passes_stop_callback_to_post_launch_route(self):
        import game_relaunch

        seen = {}
        stopped = [False]

        ok = game_relaunch.relaunch_game(
            {"game_relaunch_enabled": True, "game_platform": "steam"},
            log_cb=lambda _m: None,
            find_window=lambda _title: None,
            launch_fn=lambda _target: stopped.__setitem__(0, True) or True,
            post_launch_fn=lambda cfg, log_cb, stop_cb=None: seen.update(
                {"stopped": stop_cb()}) or False,
            stop_cb=lambda: stopped[0],
            sleep=lambda _s: None)

        self.assertFalse(ok)
        self.assertEqual(seen, {"stopped": True})

    def test_ensure_game_ready_noops_when_window_exists(self):
        import game_relaunch

        calls = []

        ok = game_relaunch.ensure_game_ready_for_start(
            {"game_relaunch_enabled": True},
            log_cb=lambda _m: None,
            find_window=lambda _title: 100,
            launch_fn=lambda target: calls.append(("launch", target.platform)) or True,
            post_launch_fn=lambda cfg, log_cb: calls.append(("post", None)) or True)

        self.assertTrue(ok)
        self.assertEqual(calls, [])
        self.assertNotIn("_game_launched_by_fafe", {})

    def test_ensure_game_ready_launches_when_window_is_missing(self):
        import game_relaunch

        calls = []
        cfg = {"game_relaunch_enabled": True, "game_platform": "auto",
               "game_steam_uri": "steam://rungameid/2483190"}

        ok = game_relaunch.ensure_game_ready_for_start(
            cfg,
            log_cb=lambda _m: None,
            find_window=lambda _title: None,
            launch_fn=lambda target: calls.append(("launch", target.platform)) or True,
            post_launch_fn=lambda cfg, log_cb: calls.append(("post", cfg["game_platform"])) or True,
            appid_lookup=lambda _name: None)

        self.assertTrue(ok)
        self.assertEqual(calls, [("launch", "steam"), ("post", "auto")])
        self.assertIs(cfg["_game_launched_by_fafe"], True)
        self.assertIs(cfg["gameio_disable_letterbox_crop"], True)

    def test_ensure_game_ready_is_stoppable_during_post_launch_route(self):
        import game_relaunch

        seen = {}
        stopped = [False]

        ok = game_relaunch.ensure_game_ready_for_start(
            {"game_relaunch_enabled": True, "game_platform": "steam"},
            log_cb=lambda _m: None,
            find_window=lambda _title: None,
            launch_fn=lambda _target: stopped.__setitem__(0, True) or True,
            post_launch_fn=lambda cfg, log_cb, stop_cb=None: seen.update(
                {"stopped": stop_cb()}) or False,
            stop_cb=lambda: stopped[0])

        self.assertFalse(ok)
        self.assertEqual(seen, {"stopped": True})

    def test_relaunch_game_marks_launch_route_as_fafe_launched(self):
        import game_relaunch

        seen = {}

        ok = game_relaunch.relaunch_game(
            {"game_relaunch_enabled": True, "game_platform": "steam"},
            log_cb=lambda _m: None,
            find_window=lambda _title: None,
            launch_fn=lambda _target: True,
            post_launch_fn=lambda cfg, _log: seen.update(cfg) or True,
            sleep=lambda _s: None)

        self.assertTrue(ok)
        self.assertIs(seen["_game_launched_by_fafe"], True)
        self.assertIs(seen["gameio_disable_letterbox_crop"], True)

    def test_gameio_refreshes_window_rect_after_interval(self):
        import numpy as np
        import gameio

        now = [0.0]
        rects = [(0, 0, 640, 360), (10, 20, 1920, 1080)]
        idx = [0]
        originals = {
            "get_monitor_dims": gameio.capture.get_monitor_dims,
            "find_game_window": gameio.capture.find_game_window,
            "get_client_rect": gameio.capture.get_client_rect,
            "grab_window": gameio.capture.grab_window,
            "monotonic": gameio.time.monotonic,
        }
        try:
            gameio.capture.get_monitor_dims = lambda _mon: (1920, 1080, 0, 0)
            gameio.capture.find_game_window = lambda _title: 100
            gameio.capture.get_client_rect = lambda _hwnd: rects[idx[0]]
            gameio.capture.grab_window = lambda _hwnd: np.zeros(
                (rects[idx[0]][3], rects[idx[0]][2], 3), dtype=np.uint8)
            gameio.time.monotonic = lambda: now[0]

            io = gameio.GameIO(
                {"background_input": True, "gameio_window_refresh_interval": 5.0},
                log_cb=lambda _m: None)
            self.assertEqual((io.cap_left, io.cap_top, io.width, io.height),
                             (0, 0, 640, 360))

            idx[0] = 1
            now[0] = 4.9
            io.grab()
            self.assertEqual((io.cap_left, io.cap_top, io.width, io.height),
                             (0, 0, 640, 360))

            now[0] = 5.1
            io.grab()
            self.assertEqual((io.cap_left, io.cap_top, io.width, io.height),
                             (10, 20, 1920, 1080))
        finally:
            gameio.capture.get_monitor_dims = originals["get_monitor_dims"]
            gameio.capture.find_game_window = originals["find_game_window"]
            gameio.capture.get_client_rect = originals["get_client_rect"]
            gameio.capture.grab_window = originals["grab_window"]
            gameio.time.monotonic = originals["monotonic"]

    def test_gameio_warns_when_game_window_is_below_1080p(self):
        import gameio

        logs = []
        originals = {
            "get_monitor_dims": gameio.capture.get_monitor_dims,
            "find_game_window": gameio.capture.find_game_window,
            "get_client_rect": gameio.capture.get_client_rect,
        }
        try:
            gameio.capture.get_monitor_dims = lambda _mon: (1920, 1080, 0, 0)
            gameio.capture.find_game_window = lambda _title: 100
            gameio.capture.get_client_rect = lambda _hwnd: (0, 0, 1280, 720)

            gameio.GameIO({"background_input": True}, log_cb=logs.append)
        finally:
            gameio.capture.get_monitor_dims = originals["get_monitor_dims"]
            gameio.capture.find_game_window = originals["find_game_window"]
            gameio.capture.get_client_rect = originals["get_client_rect"]

        joined = "\n".join(logs)
        self.assertIn("!!! WARNING !!!", joined)
        self.assertIn("under 1080p", joined)

    def test_race_and_full_auto_launch_missing_game_before_routes(self):
        self.assertIn("ensure_game_ready_for_start", Path("race.py").read_text(encoding="utf-8"))
        self.assertIn("ensure_game_ready_for_start", Path("full_auto.py").read_text(encoding="utf-8"))

    def test_launch_on_start_setting_is_exposed_in_webui(self):
        app_js = Path("webui/app.js").read_text(encoding="utf-8")
        i18n = Path("webui/i18n.js").read_text(encoding="utf-8")
        app_web = Path("app_web.py").read_text(encoding="utf-8")

        system_block = app_js.split("const SYSTEM_TOGGLES", 1)[1].split("];", 1)[0]
        self.assertIn("game_relaunch_enabled", system_block)
        self.assertIn("renderLaunchPathSettings", app_js)
        self.assertIn("game_platform", app_js)
        self.assertIn("state.cfg.game_platform = current", app_js)
        self.assertIn("game_custom_launch", app_js)
        self.assertIn("browse_game_custom_launch", app_js)
        self.assertIn("browse_game_custom_launch", app_web)
        self.assertIn("create_file_dialog", app_web)
        for key in ("launch_path_label", "launch_path_steam",
                    "launch_path_xbox", "launch_path_custom",
                    "launch_custom_browse"):
            self.assertIn(key, i18n)
        self.assertIn("sys_game_relaunch_enabled", i18n)
        self.assertIn("sys_game_relaunch_enabled_h", i18n)

    def test_relaunch_route_ocr_hints_match_captured_templates(self):
        import detector

        self.assertIn("start game", detector.OCR_HINTS["launch_start_prompt"])
        self.assertIn("continue", detector.OCR_HINTS["launch_continue"])
        self.assertIn("anna", detector.OCR_HINTS["anna"])

    def test_post_launch_route_sequence_is_template_gated(self):
        source = Path("game_relaunch.py").read_text(encoding="utf-8")
        gameio = Path("gameio.py").read_text(encoding="utf-8")

        for needle in (
            "def return_to_main_menu_after_launch",
            "gameio_quiet_keepalive_log",
            '"launch_start_prompt"',
            '"launch_continue"',
            '"cars_tab"',
            '"anna"',
            '"creative_hub"',
            'press("enter"',
            'press("escape"',
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, source)
        self.assertNotIn("force_foreground_input", source)
        self.assertNotIn("gameio_log_postmessage", source)
        self.assertNotIn("log_window_state", source)
        self.assertNotIn("via PostMessage", source)
        self.assertNotIn("describe_window", source)
        self.assertNotIn("force_foreground_input", gameio)
        self.assertIn("io.start_keepalive(stop_cb, fresh)", source)


if __name__ == "__main__":
    unittest.main()
