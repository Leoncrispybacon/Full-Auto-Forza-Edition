from pathlib import Path
import unittest


class StageRouteRecoveryTests(unittest.TestCase):
    def test_retries_failed_route_before_giving_up(self):
        import recovery

        calls = []
        logs = []

        def route():
            calls.append(len(calls) + 1)
            return len(calls) == 2

        ok = recovery.run_stage_route(
            "Buy entry", route, stop=lambda: False, log_cb=logs.append,
            max_retries=1)

        self.assertTrue(ok)
        self.assertEqual(calls, [1, 2])
        self.assertTrue(any("retrying stage route" in line for line in logs))

    def test_purpose_done_result_does_not_retry_same_loop(self):
        import recovery

        calls = []

        def route():
            calls.append(1)
            return recovery.RouteAttempt(ok=False, purpose_done=True)

        ok = recovery.run_stage_route(
            "Wheelspin collect", route, stop=lambda: False, log_cb=lambda _m: None,
            max_retries=3)

        self.assertTrue(ok)
        self.assertEqual(len(calls), 1)

    def test_recovery_action_runs_between_failed_attempts(self):
        import recovery

        recovered = False
        calls = []

        def route():
            calls.append(recovered)
            return recovered

        def recover():
            nonlocal recovered
            recovered = True
            return True

        ok = recovery.run_stage_route(
            "Race entry", route, stop=lambda: False, log_cb=lambda _m: None,
            max_retries=1, recover_fn=recover)

        self.assertTrue(ok)
        self.assertEqual(calls, [False, True])

    def test_successful_recovery_anchor_resets_retry_budget(self):
        import recovery

        calls = []
        route_calls = 0

        def route():
            nonlocal route_calls
            calls.append("route")
            route_calls += 1
            return route_calls == 3

        def recover():
            calls.append("anchor")
            return True

        ok = recovery.run_stage_route(
            "Race entry", route, stop=lambda: False, log_cb=lambda _m: None,
            max_retries=1, recover_fn=recover)

        self.assertTrue(ok)
        self.assertEqual(calls, ["route", "anchor", "route", "anchor", "route"])

    def test_stage_route_recovery_logs_are_localized(self):
        import recovery

        logs = []
        recovery.set_log_lang("zh-tw")
        try:
            ok = recovery.run_stage_route(
                "Race entry", lambda: False, stop=lambda: False,
                log_cb=logs.append, max_retries=0)
        finally:
            recovery.set_log_lang("en")

        self.assertFalse(ok)
        self.assertNotIn("route recovery failed", "\n".join(logs))

    def test_backtrack_anchor_keys_start_at_expected_step(self):
        import recovery

        route = ("a", "b", "c", "d")

        self.assertEqual(
            recovery.backtrack_anchor_keys(route, "c"),
            ("c", "b", "a"))
        self.assertEqual(
            recovery.backtrack_anchor_keys(route, None),
            ("d", "c", "b", "a"))
        self.assertEqual(
            recovery.backtrack_anchor_keys(route, "missing"),
            ("d", "c", "b", "a"))

    def test_safe_stage_routes_are_recovery_wrapped(self):
        expected = {
            "race.py": ["recovery.run_stage_route", "Race entry",
                        "recover_fn=_recover_race_entry_route"],
            "buy.py": ["recovery.run_stage_route", "Buy entry",
                       "recover_fn=_recover_buy_entry_route"],
            "wheelspin.py": ["recovery.run_stage_route", "Wheelspin entry",
                             "recover_fn=_recover_wheelspin_entry_route"],
            "mastery.py": ["recovery.run_stage_route", "Mastery per-car",
                           "_recover_standalone_gated_to_grid"],
            "full_auto.py": ["recovery.run_stage_route", "Full Auto mastery entry",
                             "recover_fn=_recover_mastery_entry_route",
                             "Full Auto tech-point read",
                             "recover_fn=_recover_tech_points_route",
                             "Full Auto mastery per-car",
                             "recover_fn=_recover_mastery_loop_route",
                             "Full Auto sell pre-sale",
                             "recover_fn=_recover_sell_pre_sale_route",
                             "Full Auto sell exit",
                             "recover_fn=_recover_sell_exit_route"],
        }
        for path, needles in expected.items():
            source = Path(path).read_text(encoding="utf-8")
            for needle in needles:
                with self.subTest(path=path, needle=needle):
                    self.assertIn(needle, source)

    def test_full_auto_sell_recovery_does_not_wrap_actual_sale_macro(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")

        pre_sale = source.index('"Full Auto sell pre-sale"')
        sale_macro = source.index('log_fa_sell_macro')
        sell_exit = source.index('"Full Auto sell exit"')

        self.assertLess(pre_sale, sale_macro)
        self.assertLess(sale_macro, sell_exit)

    def test_full_auto_sell_pre_sale_recovery_does_not_anchor_on_my_cars_header(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")
        block = source.split("def _recover_sell_pre_sale_route", 1)[1].split(
            "def _sell_exit_route", 1)[0]

        self.assertNotIn('_detect("my_cars_header"', block)
        self.assertNotIn("anchored at my_cars_header", block)

    def test_full_auto_simple_repress_helper_is_removed(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")

        self.assertNotIn("def _press_to_open", source)
        self.assertNotIn("_press_to_open(", source)

    def test_click_until_advanced_does_not_reclick_by_default(self):
        import navutil

        class Match:
            def __init__(self, matched):
                self.matched = matched
                self.location = (10, 20)

        class Detector:
            def detect(self, _frame, key, _tpl, _thr, stable=True):
                return Match(key == "prev")

        clicks = []
        result = navutil.click_until_advanced(
            lambda: None,
            Detector(),
            lambda _loc: clicks.append("click"),
            ("prev", None, 0.7),
            ("next", None, 0.7),
            stop=lambda: False,
            grace=0.0,
            ceiling=0.01,
            interval=0.0)

        self.assertIsNone(result)
        self.assertEqual(clicks, ["click"])

    def test_full_auto_checks_mastery_run_result_before_selling(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")
        block = source.split("def _step_mastery", 1)[1].split(
            "def _step_sell", 1)[0]

        self.assertIn('"Full Auto mastery per-car"', block)
        self.assertIn("if not recovery.run_stage_route(", block)
        self.assertIn("return False", block.split('"Full Auto mastery per-car"', 1)[1])

    def test_full_auto_mastery_restarts_from_completed_car_after_recovery(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")
        block = source.split("def _step_mastery", 1)[1].split(
            "def _step_sell", 1)[0]

        self.assertIn("mastery_completed", block)
        self.assertIn("initial_completed=mastery_completed", block)
        self.assertIn("Full Auto mastery per-car", block)

    def test_tech_point_read_is_recovery_wrapped(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")
        block = source.split("def _read_tech_points", 1)[1].split(
            "# Ordered linear chain steps", 1)[0]

        self.assertIn("Full Auto tech-point read", block)
        self.assertIn("recover_fn=_recover_tech_points_route", block)
        self.assertIn("_load_recovery_safety_templates", block)

    def test_tech_point_tabs_click_template_box_center(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")
        block = source.split("def _read_tech_points", 1)[1].split(
            "return points", 1)[0]

        self.assertIn('key in ("cars_top_tab", "story_top_tab")', block)
        self.assertIn("_content_box", source)
        self.assertIn("dx + fx * dbox_w", block)
        self.assertIn("_click_template_center(\"cars_top_tab\", r.location)", block)
        self.assertIn("_click_template_center(\"story_top_tab\", rb.location)", block)

    def test_route_helper_no_longer_has_fault_injection_hook(self):
        source = Path("recovery.py").read_text(encoding="utf-8")

        self.assertNotIn("test_point", source)
        self.assertNotIn("Recovery test point hit", source)

    def test_every_stage_recovery_knows_open_world_and_main_menu_safety_anchors(self):
        expected = {
            "race.py": ["anna", "collection_log", "_load_recovery_safety_templates",
                        "_recover_to_main_menu_from_safety_anchor"],
            "buy.py": ["anna", "collection_log", "_load_recovery_safety_templates",
                       "_recover_to_main_menu_from_safety_anchor"],
            "mastery.py": ["recovery.SAFETY_ANCHORS",
                           "load_recovery_safety_templates"],
            "wheelspin.py": ["anna", "collection_log", "_load_recovery_safety_templates",
                             "_recover_to_main_menu_from_safety_anchor"],
            "full_auto.py": ["anna", "collection_log", "_load_recovery_safety_templates",
                             "_recover_to_main_menu_from_safety_anchor"],
        }
        for path, needles in expected.items():
            source = Path(path).read_text(encoding="utf-8")
            for needle in needles:
                with self.subTest(path=path, needle=needle):
                    self.assertIn(needle, source)

    def test_race_exit_accepts_anna_when_next_activity_is_disabled(self):
        source = Path("race.py").read_text(encoding="utf-8")
        block = source.split("def _return_to_menu", 1)[1].split(
            "_PAUSE_RECOVERY_CHECK", 1)[0]

        self.assertIn('_detect_exit_any(("next_activity", "anna")', block)
        self.assertIn('if exit_anchor == "next_activity"', block)
        self.assertIn('elif exit_anchor != "anna"', block)
        self.assertIn('safety_tpls["anna"]', source)

    def test_race_nav_rechecks_previous_step_before_route_recovery(self):
        source = Path("race.py").read_text(encoding="utf-8")
        block = source.split("def _handle_history_enter", 1)[1].split(
            "def _navigate_to_event", 1)[0]

        self.assertIn("_HISTORY_RETRY_CHECK_WINDOW", block)
        self.assertIn("_detect_nav_any((retry_to, key), _HISTORY_RETRY_CHECK_WINDOW)", block)
        self.assertIn('_kp("enter", post_wait=0.0)', block)

    def test_race_recovery_scans_route_anchors_backwards_from_expected_step(self):
        source = Path("race.py").read_text(encoding="utf-8")
        block = source.split("def _recover_race_entry_route", 1)[1].split(
            "if require_nav and not nav_enabled", 1)[0]

        self.assertIn("recovery.backtrack_anchor_keys", block)
        self.assertIn("recovery_expected_step", block)
        self.assertIn("_detect_start_state(1.2, keys=anchor_keys)", block)

    def test_full_auto_mastery_entry_recovery_uses_shared_backtrack_order(self):
        source = Path("full_auto.py").read_text(encoding="utf-8")
        block = source.split("def _find_mastery_entry_recovery_anchor", 1)[1].split(
            "def _recover_mastery_loop_to_start", 1)[0]

        self.assertIn("recovery.backtrack_anchor_keys", block)
        self.assertIn("_MASTERY_ENTRY_ROUTE_STEPS", block)

    def test_buy_and_wheelspin_recovery_use_shared_backtrack_order(self):
        checks = {
            "buy.py": "def _recover_buy_entry_route",
            "wheelspin.py": "def _recover_wheelspin_entry_route",
        }
        for path, marker in checks.items():
            source = Path(path).read_text(encoding="utf-8")
            block = source.split(marker, 1)[1].split("if not recovery.run_stage_route", 1)[0]
            with self.subTest(path=path):
                self.assertIn("recovery.backtrack_anchor_keys", block)

    def test_buy_nav_exit_uses_existing_four_esc_route(self):
        source = Path("buy.py").read_text(encoding="utf-8")

        self.assertIn("_EXIT_ESC_COUNT      = 4", source)

    def test_buy_22b_keyboard_target_opens_after_second_enter(self):
        source = Path("buy.py").read_text(encoding="utf-8")

        self.assertIn('keys="S → Enter → Enter"', source)
        self.assertGreaterEqual(source.count("wait(0.5)"), 2)


if __name__ == "__main__":
    unittest.main()
