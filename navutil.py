# ============================================================
#  navutil.py — shared menu-navigation failsafe.
#
#  click_until_advanced(): click a menu element, then VERIFY the menu actually
#  advanced to the next screen. If it didn't (a dropped/ignored click on a
#  stuttering game) and the clicked element is STILL on screen past a short
#  grace, the click never landed — re-detect it (fresh coords) and click again,
#  bounded. Once the clicked element goes absent we know the click took, so we
#  just wait for the next screen.
#
#  This is the reactive complement to the per-key hold time: the hold makes a
#  press more likely to land; this catches the ones that still don't. Used by
#  race / buy / wheelspin nav. The happy path (next screen appears promptly) is
#  unchanged — no extra latency, no extra clicks; the retry only fires on failure.
# ============================================================

import time


def click_until_advanced(grab, detector, click, prev, nxt, stop,
                         log_retry=None, grace=2.0,
                         ceiling=12.0, interval=0.15, retries=2):
    """Click `prev`, then ensure the menu advanced to `nxt`.

      grab()        -> frame
      detector      -> ScreenDetector (uses .detect)
      click((x, y)) -> perform a click at a frame-local location (posted, fast)
      prev / nxt    -> (key, template, threshold) tuples
      stop()        -> True to abort (F9)
      log_retry(n)  -> optional; called just before re-click attempt n (1-based)

    Every click — first attempt AND retries — is the posted click; a dropped
    click is simply re-posted (kept background-safe, no real cursor movement).

    Behaviour:
      • detect `prev` (fresh coords) → click it
      • poll for `nxt`:
          - `nxt` found                         → return its MatchResult ✓
          - `prev` still present past `grace`
            (two consecutive polls)             → click didn't land → re-click
          - `prev` absent                       → click took; keep waiting for
                                                  `nxt` up to `ceiling`
      • bounded at `retries` re-clicks, then give up.

    Returns the `nxt` MatchResult on success, or None if it never advanced
    (the caller aborts — never guesses). The grace exists because `prev` always
    lingers briefly right after a *working* click; only persistence BEYOND the
    grace means the click failed.
    """
    pkey, ptpl, pthr = prev
    nkey, ntpl, nthr = nxt

    def _find(key, tpl, thr):
        try:
            r = detector.detect(grab(), key, tpl, thr, stable=False)
            return r if r.matched else None
        except Exception:
            return None

    clicks = 0
    while clicks <= retries and not stop():
        if clicks > 0 and log_retry:
            log_retry(clicks)                   # re-click attempt #clicks
        pr = _find(pkey, ptpl, pthr)
        if pr is None:
            # `prev` isn't on screen: either we already advanced (nxt is up) or
            # we're somewhere unexpected. Return whatever `nxt` is (None → abort);
            # never click blindly into an unknown screen.
            return _find(nkey, ntpl, nthr)
        click(pr.location)                      # posted click (first try + retries)
        clicks += 1
        t0 = time.time()
        stuck = 0
        while not stop():
            nr = _find(nkey, ntpl, nthr)
            if nr is not None:
                return nr                       # advanced ✓
            elapsed = time.time() - t0
            if elapsed >= ceiling:
                return None                     # waited long enough, no advance
            if _find(pkey, ptpl, pthr) is not None:
                if elapsed >= grace:
                    stuck += 1
                    if stuck >= 2:              # prev solidly stuck → re-click
                        break
                # within grace: normal post-click lingering — keep polling
            else:
                stuck = 0                       # prev gone → click took; await nxt
            time.sleep(interval)
        else:
            return None                         # stopped
    return None                                 # retries exhausted


if __name__ == "__main__":
    # Self-check: drive click_until_advanced against a fake detector whose screen
    # only changes when click() "lands". No game, no deps beyond this file.
    class _M:
        def __init__(self, matched): self.matched, self.location = matched, (5, 6)

    class _Det:
        def __init__(self): self.visible = {"A"}
        def detect(self, frame, key, tpl, thr, stable=True):
            return _M(key in self.visible)

    def _run(click_effect, retries=2):
        d = _Det(); grab = lambda: None
        calls = {"clicks": 0, "retries": []}
        def click(loc):
            calls["clicks"] += 1
            click_effect(d, calls["clicks"])
        res = click_until_advanced(
            grab, d, click, ("A", None, 0.6), ("B", None, 0.6),
            stop=lambda: False, log_retry=lambda n: calls["retries"].append(n),
            grace=0.0, ceiling=0.3, interval=0.0, retries=retries)
        return res, calls

    # 1. Happy path: first click advances A→B.
    r, c = _run(lambda d, n: d.visible.__init__({"B"}))
    assert r is not None and c["clicks"] == 1 and c["retries"] == [], (r, c)

    # 2. First click dropped, second lands.
    def _drop_once(d, n):
        if n >= 2: d.visible = {"B"}      # only the 2nd click works
    r, c = _run(_drop_once)
    assert r is not None and c["clicks"] == 2 and c["retries"] == [1], (r, c)

    # 3. Deterministic ignore: click never changes the screen → give up.
    r, c = _run(lambda d, n: None)
    assert r is None and c["clicks"] == 3 and c["retries"] == [1, 2], (r, c)

    # 4. Neither prev nor next on screen → abort without clicking.
    d = _Det(); d.visible = set()
    r = click_until_advanced(lambda: None, d, lambda loc: None,
                             ("A", None, 0.6), ("B", None, 0.6),
                             stop=lambda: False, grace=0.0, ceiling=0.3,
                             interval=0.0)
    assert r is None, r

    print("navutil self-check OK")
