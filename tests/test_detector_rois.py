import unittest
from unittest import mock


class DetectorRoiTests(unittest.TestCase):
    def test_wheelspin_duplicate_is_ocr_confirmed_by_default(self):
        # wheelspin_duplicate pixel-matches weakly on low-res/weak hardware, so it
        # must be OCR-confirmed or the dup modal is missed there — regressing to a
        # spin miscount. OCR is ON by default, and the key is a text template with
        # hints, so it gets confirmed in the borderline band like any other.
        import detector
        d = detector.ScreenDetector({"detector_ocr_prewarm": False})
        self.assertTrue(d._enable_ocr)                          # OCR on by default
        self.assertIn("wheelspin_duplicate", detector.TEXT_TEMPLATES)
        self.assertTrue(detector.OCR_HINTS.get("wheelspin_duplicate"))

    def test_wheelspin_skip_has_short_ocr_cooldown_override(self):
        # The skip prompt only shows ~3s. On low_impact (3s cooldown) OCR would get
        # one shot at it; a 0.5s per-key override lets it retry through the window.
        # A normal key stays on the global cooldown.
        import time
        import numpy as np
        import detector

        class FakeOCR:
            def __init__(self):
                self.reads = 0

            def available(self):
                return True

            def read(self, img):
                self.reads += 1
                return "skip"

        d = detector.ScreenDetector({
            "detector_ocr_prewarm": False,
            "detector_ocr_cooldown": 999,   # global: effectively blocks re-runs
        })
        d._ocr = FakeOCR()
        self.assertEqual(d._ocr_cooldown_by_key["wheelspin_skip"], 0.5)

        area = np.zeros((30, 200, 3), dtype=np.uint8)
        # last OCR run 0.6s ago: > the 0.5s skip override, but << the 999s global.
        # Both keys have OCR_HINTS, so a 0-read proves the COOLDOWN gated it.
        d._ocr_last_run["wheelspin_skip"] = time.time() - 0.6
        d._ocr_last_run["start_menu"] = time.time() - 0.6
        self.assertGreater(d._ocr_bonus(area, "wheelspin_skip")[0], 0)  # override → OCR ran
        self.assertEqual(d._ocr.reads, 1)
        d._ocr_bonus(area, "start_menu")                               # global cooldown → gated
        self.assertEqual(d._ocr.reads, 1)                              # no extra read

    def test_duplicate_fe_is_case_sensitive_and_matches_anywhere(self):
        # FE keep = the car name contains UPPERCASE "FE" ANYWHERE (not just the
        # end); lowercase "fe" does NOT count. None when no name is read.
        import numpy as np
        import detector

        class _OCR:
            def available(self):
                return True

        d = detector.ScreenDetector({"detector_ocr_prewarm": False})
        d._ocr = _OCR()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        def fe_verdict(name_tokens):
            def fake_region(_frame, key):
                if key == "wheelspin_dup_name":
                    return ([(t, None) for t in name_tokens], (0.0, 0.0, 1.0, 1.0))
                return ([], (0.0, 0.0, 1.0, 1.0))   # price band empty
            d._ocr_region = fake_region
            fe, _price, _txt = d.duplicate_info(frame)
            return fe

        self.assertIs(fe_verdict(["Impreza 22B FE"]), True)   # FE at end
        self.assertIs(fe_verdict(["GT FE Racer"]), True)      # FE in the middle
        self.assertIs(fe_verdict(["Alfa Cafe"]), False)       # lowercase 'fe' → not FE
        self.assertIs(fe_verdict(["Golf Life"]), False)       # no FE at all
        self.assertIsNone(fe_verdict([]))                     # no name read

    def test_ocr_mandatory_identity_confirms_at_zero_pixel(self):
        # buy_detail_* are OCR-mandatory identity screens: at 0% pixel (template/
        # background mismatch) OCR must still run — the car-name read alone decides
        # the match (right name → match, wrong/none → no match).
        import numpy as np
        import detector

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        template = np.zeros((10, 20), dtype=np.uint8)

        def matched(ocr_text):
            class FakeOCR:
                def available(self):
                    return True

                def read(self, img, max_scale=None):
                    return ocr_text
            d = detector.ScreenDetector({"detector_enable_ocr": True,
                                         "detector_ocr_prewarm": False,
                                         "detector_ocr_cooldown": 0})
            d._ocr = FakeOCR()
            with mock.patch.object(detector, "_best_template_match",
                                   return_value=(0.0, (5, 5), 1.0)):
                return d._detect_in_area(frame, "buy_detail_22b", template,
                                         0.70, None, "roi", False).matched

        self.assertTrue(matched("1998 SUBARU Impreza 22B-STi Version"))
        self.assertFalse(matched("Dodge Viper GTS ACR"))   # wrong car → no match
        self.assertFalse(matched(""))                       # silent OCR → no match

    def test_final_collect_ocr_rejects_normal_spin_again_prompt(self):
        # wheelspin_collect_final must confirm ONLY the single "Collect Prize"
        # screen, not the normal "Collect Prize and Spin Again" (whose text
        # contains the final hint as a substring) — otherwise it presses the wrong
        # button. The OCR_EXCLUDE spin-again markers must be absent.
        import numpy as np
        import detector

        d = detector.ScreenDetector({"detector_enable_ocr": True,
                                     "detector_ocr_prewarm": False,
                                     "detector_ocr_cooldown": 0})
        area = np.zeros((30, 200, 3), dtype=np.uint8)

        class FakeOCR:
            def __init__(self, t):
                self.t = t

            def available(self):
                return True

            def read(self, img):
                return self.t

        def bonus(txt):
            d._ocr = FakeOCR(txt)
            return d._ocr_bonus(area, "wheelspin_collect_final")[0]

        self.assertGreater(bonus("Collect Prize"), 0)                 # final → pass
        self.assertEqual(bonus("Collect Prize and Spin Again"), 0)    # normal → reject
        self.assertGreater(bonus("取得獎勵"), 0)                       # final zh → pass
        self.assertEqual(bonus("取得獎勵並再次抽獎"), 0)               # normal zh → reject

    def test_bottom_prompts_mixed_anchor_on_16_10(self):
        # Bottom-of-screen prompts (restart_menu, wheelspin_collect, …) are MIXED:
        # horizontal follows the centred-16:9 content box, vertical hugs the screen
        # bottom edge. On 16:10 (2560x1600) Y must stay at the bottom (not ride up
        # via content-box) AND X must stay content-box (not shoot right via pure
        # edge). Unchanged on 16:9.
        import detector

        for key in ("restart_menu", "wheelspin_collect", "wheelspin_collect_final",
                    "wheelspin_skip", "launch_start_prompt", "launch_continue",
                    "mastery_esc_hint", "ride_cutscene_end"):
            self.assertIn(key, detector._GEOM_EDGE_Y_KEYS)
        # corner HUD stays full-edge
        self.assertIn("racing", detector._GEOM_EDGE_KEYS)

        d = detector.ScreenDetector({"detector_ocr_prewarm": False})
        # box [1225,1989,155,50] on 5120x2160 → x-frac 0.239 (of ref width)
        d.set_template_roi("restart_menu", [0.21719, 0.9125, 0.07012, 0.03565],
                           5120, 2160)
        rx, ry, rw, rh = d._custom_roi_for_frame("restart_menu", 2560, 1600)
        self.assertGreater(ry, 0.90)          # Y hugs the bottom (edge), not ~0.88
        self.assertLess(rx, 0.25)             # X stays content-box (~0.15), not ~0.35
        # no 16:9 regression (content-box == edge there)
        r9 = d._custom_roi_for_frame("restart_menu", 1920, 1080)
        self.assertAlmostEqual(r9[1], 0.912, places=2)
        self.assertLess(r9[0], 0.25)

    def test_default_rois_are_numeric_rects(self):
        import detector

        for key, roi in detector.DEFAULT_ROIS.items():
            with self.subTest(key=key):
                self.assertEqual(len(roi), 4)
                self.assertTrue(all(isinstance(v, (int, float)) for v in roi))

    def test_flat_template_cannot_match_flat_screen(self):
        import numpy as np
        import detector

        screen = np.zeros((100, 200), dtype=np.uint8)
        template = np.zeros((20, 50), dtype=np.uint8)

        score, _loc, _scale = detector._best_template_match(
            screen, template, [1.0])

        self.assertEqual(score, 0.0)

    def test_custom_roi_cross_aspect_uses_content_box_remap(self):
        import detector

        # eventlab is a centred menu tile (content-box model), not an edge key.
        d = detector.ScreenDetector({"detector_ocr_prewarm": False})
        d.set_template_roi("eventlab", (0.10, 0.80, 0.10, 0.10),
                           cap_w=5120, cap_h=2160)

        roi = d._custom_roi_for_frame("eventlab", 1920, 1080)

        self.assertEqual(roi[0], 0.0)
        self.assertAlmostEqual(roi[1], 0.8)
        self.assertAlmostEqual(roi[2], 256 / 1920)
        self.assertAlmostEqual(roi[3], 0.1)

    def test_anna_cross_aspect_uses_screen_edge_x(self):
        import detector

        d = detector.ScreenDetector({"detector_ocr_prewarm": False})
        d.set_template_roi("anna", (100 / 5120, 1800 / 2160, 450 / 5120, 120 / 2160),
                           cap_w=5120, cap_h=2160)

        roi = d._custom_roi_for_frame("anna", 1920, 1080)

        self.assertAlmostEqual(roi[0], 50 / 1920)
        self.assertAlmostEqual(roi[2], 225 / 1920)

    def test_ocr_confirm_reads_the_whole_roi(self):
        # OCR always reads the WHOLE ROI now (no best-match sub-crop). Here roi is
        # None → the area IS the whole frame, so OCR reads the entire frame.
        import numpy as np
        import detector

        class FakeOCR:
            def __init__(self):
                self.shape = None

            def available(self):
                return True

            def read(self, img):
                self.shape = img.shape[:2]
                return "start"

        d = detector.ScreenDetector({
            "detector_enable_ocr": True,
            "detector_ocr_prewarm": False,
            "detector_ocr_cooldown": 0,
        })
        fake = FakeOCR()
        d._ocr = fake

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        template = np.zeros((10, 20), dtype=np.uint8)
        with mock.patch.object(detector, "_best_template_match",
                               return_value=(0.50, (30, 40), 1.0)):
            result = d._detect_in_area(
                frame, "start_menu", template, 0.70, None, "roi", False)

        self.assertTrue(result.matched)
        # whole area read (not a small patch centered on the match location)
        self.assertEqual(fake.shape[0], frame.shape[0])
        self.assertEqual(fake.shape[1], frame.shape[1])
        self.assertEqual(result.ocr_crop, (0, 0, frame.shape[1], frame.shape[0]))

    def test_reset_ocr_cache_clears_confirms_and_cooldowns(self):
        import detector

        d = detector.ScreenDetector({"detector_ocr_prewarm": False})
        d._ocr_confirmed["start_menu"] = (12345.0, "start")
        d._ocr_last_run["start_menu"] = 12345.0
        d.reset_ocr_cache()
        self.assertEqual(d._ocr_confirmed, {})
        self.assertEqual(d._ocr_last_run, {})

    def _collect_detector(self, no_cache_keys):
        import detector

        class FakeOCR:
            def available(self):
                return True

            def read(self, img):
                return "collect prize and spin again"

        d = detector.ScreenDetector({
            "detector_enable_ocr": True,
            "detector_ocr_prewarm": False,
            "detector_ocr_cooldown": 999,   # blocks OCR on the 2nd detect
            "detector_ocr_no_cache_keys": no_cache_keys,
        })
        d._ocr = FakeOCR()
        return d

    def test_wheelspin_collect_does_not_reuse_cached_ocr_confirm(self):
        # Default: wheelspin_collect never caches → once OCR is on cooldown, a
        # non-collect frame no longer "matches" via a stale confirm (the phantom
        # spin-count bug).
        import numpy as np
        import detector

        d = self._collect_detector(["wheelspin_collect", "wheelspin_collect_final"])
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        template = np.zeros((10, 20), dtype=np.uint8)
        with mock.patch.object(detector, "_best_template_match",
                               return_value=(0.50, (30, 40), 1.0)):
            r1 = d._detect_in_area(frame, "wheelspin_collect", template, 0.70, None, "roi", False)
            r2 = d._detect_in_area(frame, "wheelspin_collect", template, 0.70, None, "roi", False)

        self.assertTrue(r1.matched)     # fresh OCR confirms
        self.assertFalse(r2.matched)    # cooldown + no cache → no phantom match

    def test_cache_would_match_second_frame_when_not_excluded(self):
        # Same setup but caching allowed for the key → the 2nd detect matches via
        # the cached confirm. Proves the exclusion (not something else) is what
        # stops the phantom match.
        import numpy as np
        import detector

        d = self._collect_detector([])   # no keys excluded from caching
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        template = np.zeros((10, 20), dtype=np.uint8)
        with mock.patch.object(detector, "_best_template_match",
                               return_value=(0.50, (30, 40), 1.0)):
            r1 = d._detect_in_area(frame, "wheelspin_collect", template, 0.70, None, "roi", False)
            r2 = d._detect_in_area(frame, "wheelspin_collect", template, 0.70, None, "roi", False)

        self.assertTrue(r1.matched)
        self.assertTrue(r2.matched)     # cached confirm reused
        self.assertIn("[cached]", r2.ocr_text)

    def test_detect_sets_ocr_crop_on_matched_confirm(self):
        import numpy as np
        import detector

        class FakeOCR:
            def available(self):
                return True

            def read(self, img):
                return "start"

        d = detector.ScreenDetector({
            "detector_enable_ocr": True,
            "detector_ocr_prewarm": False,
            "detector_ocr_cooldown": 0,
        })
        d._ocr = FakeOCR()

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        template = np.zeros((10, 20), dtype=np.uint8)
        with mock.patch.object(detector, "_best_template_match",
                               return_value=(0.50, (30, 40), 1.0)):
            result = d._detect_in_area(
                frame, "start_menu", template, 0.70, None, "roi", False)

        self.assertTrue(result.matched)
        self.assertIsNotNone(result.ocr_crop)   # the whole-ROI box OCR read
        self.assertEqual(len(result.ocr_crop), 4)

    def test_ocr_read_waits_for_background_load_to_finish(self):
        import sys
        import threading
        import time
        import types

        import numpy as np
        import detector

        class FakeRapidOCR:
            def __init__(self, *args, **kwargs):
                time.sleep(0.05)

            def __call__(self, img):
                return [([[0, 0], [1, 0], [1, 1], [0, 1]], "929", 0.99)], None

        fake_module = types.SimpleNamespace(RapidOCR=FakeRapidOCR)
        old_module = sys.modules.get("rapidocr_onnxruntime")
        sys.modules["rapidocr_onnxruntime"] = fake_module
        try:
            ocr = detector.OptionalOCR(target_h=16, max_scale=1)
            t = threading.Thread(target=ocr._ensure_loaded)
            t.start()
            text = ocr.read(np.zeros((8, 8, 3), dtype=np.uint8))
            t.join()
        finally:
            if old_module is None:
                sys.modules.pop("rapidocr_onnxruntime", None)
            else:
                sys.modules["rapidocr_onnxruntime"] = old_module

        self.assertEqual(text, "929")
        self.assertEqual(ocr.backend, "rapidocr_onnxruntime")


if __name__ == "__main__":
    unittest.main()
