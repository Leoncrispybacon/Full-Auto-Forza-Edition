"""
updater.py — checks GitHub releases for a newer version.

IMPORTANT: FAFE no longer downloads or installs anything itself.
  - Nexus Mods prohibits bundled executables from downloading/sending files
    over the internet (auto-update is explicitly NOT considered "crucial").
  - A self-updater that downloads a zip, runs a .bat and overwrites its own exe
    is also the single biggest antivirus false-positive trigger (Defender was
    quarantining FAFE on users' machines because of it).

So this module only CHECKS whether a newer release exists. If one does, the UI
shows a notice and the user opens the releases page in their browser to download
manually (opening a URL hands off to the browser — the exe itself makes no
download). The version check can be disabled entirely via the `update_check`
config flag for a fully offline / Nexus-safe build.

The opt-out `auto_update` config flag (default true on packaged builds) changes
this: when enabled, FAFE DOES download the installer asset and hand it off to
run — the check-only behavior above remains exactly as-is when auto_update is
off.
"""

import os
import ssl
import sys
import threading
import urllib.request
import json

from version import VERSION

GITHUB_API    = "https://api.github.com/repos/Leoncrispybacon/Full-Auto-Forza-Edition/releases/latest"
RELEASES_PAGE = "https://github.com/Leoncrispybacon/Full-Auto-Forza-Edition/releases/latest"
TIMEOUT       = 8   # seconds for the version-check request

INSTALLER_NAME = "FAFE_Setup.exe"
INSTALLER_URL = ("https://github.com/Leoncrispybacon/Full-Auto-Forza-Edition"
                 "/releases/latest/download/FAFE_Setup.exe")
_MIN_INSTALLER_BYTES = 1_000_000   # a real installer is ~100MB; reject truncated


def _make_ssl_context():
    """SSL context backed by certifi's CA bundle so the version check works on
    machines whose OS root-cert store is incomplete (e.g. some handhelds), which
    otherwise fail with CERTIFICATE_VERIFY_FAILED."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return None


_SSL_CTX = _make_ssl_context()

# Reason the last fetch_latest() failed (None on success), so the UI can log WHY
# a check came back empty instead of failing silently.
_last_error = None


def _parse_version(tag: str):
    """'v1.0.2' → (1, 0, 2)"""
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def fetch_latest():
    """Return (latest_tag, releases_page_url) or (None, None) on any error.
    Only reads the tag name — it does NOT download any asset."""
    global _last_error
    _last_error = None
    try:
        req = urllib.request.Request(
            GITHUB_API, headers={"User-Agent": "FAFE-updater"})
        with urllib.request.urlopen(req, timeout=TIMEOUT,
                                    context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode())
        tag = data.get("tag_name", "")
        if not tag:
            _last_error = "GitHub returned no tag_name (rate-limited?)"
        return tag, RELEASES_PAGE
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        return None, None


def is_newer(latest_tag: str) -> bool:
    try:
        return _parse_version(latest_tag) > _parse_version(VERSION)
    except Exception:
        return False


def check_async(on_update_available, on_status=None):
    """Check for a newer release in a background thread (read-only — no download).
    Calls on_update_available(latest_tag, releases_page_url) if a newer version
    exists. on_status(msg) reports the outcome for diagnostics."""
    def _say(msg):
        if on_status:
            try:
                on_status(msg)
            except Exception:
                pass

    def _check():
        _say(f"checking for updates (installed v{VERSION})…")
        tag, page = fetch_latest()
        if not tag:
            _say(f"update check failed: {_last_error or 'unknown error'}")
            return
        if not is_newer(tag):
            _say(f"up to date (latest {tag})")
            return
        _say(f"update available: {tag}")
        on_update_available(tag, page)

    threading.Thread(target=_check, daemon=True).start()


def find_installer_asset(release: dict):
    """(download_url, size) for the FAFE_Setup.exe asset in a GitHub release
    JSON, or (None, None) if absent."""
    for a in (release.get("assets") or []):
        if a.get("name") == INSTALLER_NAME:
            return a.get("browser_download_url"), a.get("size")
    return None, None


def fetch_installer_asset():
    """(url, size) for the latest installer. Uses the API to read the asset size
    (for integrity); falls back to the stable releases/latest/download URL with
    size=None if the API is unavailable. (None, None) only if even that is
    unusable."""
    try:
        req = urllib.request.Request(
            GITHUB_API, headers={"User-Agent": "FAFE-updater"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
            release = json.loads(resp.read().decode())
        url, size = find_installer_asset(release)
        if url:
            return url, size
    except Exception:
        pass
    return INSTALLER_URL, None


def verify_installer(path: str, expected_size) -> bool:
    """A downloaded installer is trustworthy iff: it exists, matches the API size
    (when known), is a plausibly-full size, and begins with the PE 'MZ' magic.
    No code-signature check — the installer isn't signed yet."""
    try:
        actual = os.path.getsize(path)
    except OSError:
        return False
    if expected_size is not None and actual != int(expected_size):
        return False
    if actual < _MIN_INSTALLER_BYTES:
        return False
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def download_installer(url: str, dest: str, on_progress=None) -> str:
    """Stream the installer to dest via HTTPS (certifi). Writes a .part file then
    renames on success so a partial download never masquerades as complete.
    on_progress(done, total) is best-effort. Raises on network error."""
    part = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "FAFE-updater"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(part, "wb") as f:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress:
                    try:
                        on_progress(done, total)
                    except Exception:
                        pass
    os.replace(part, dest)
    return dest


# ── Installed-copy detection ─────────────────────────────────
# Auto-update runs the installer, which updates FAFE at its REGISTERED install
# location (Inno reuses the prior-install dir — default OR a custom one the user
# picked). A PORTABLE copy (ran the zip, never installed) has no registry record,
# so the installer would drop a separate copy elsewhere and never touch/relaunch
# the running one. So auto-update is offered ONLY when the running exe lives at
# the registered install dir. AppId is unset in the .iss, so Inno's uninstall key
# is derived from AppName ("Full Auto Forza Edition") — do NOT switch to an
# explicit AppId GUID: it would orphan already-installed users.
_UNINSTALL_KEY = (r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
                  r"\Full Auto Forza Edition_is1")


def _dir_matches(exe_dir: str, install_loc: str) -> bool:
    """True if exe_dir is the same folder as install_loc (case/slash-insensitive).
    Pure helper (no registry) so it's unit-testable."""
    if not exe_dir or not install_loc:
        return False
    def _norm(p):
        return os.path.normcase(os.path.normpath(p.strip().rstrip(r"\/")))
    return _norm(exe_dir) == _norm(install_loc)


def installed_install_dir():
    """The registered Inno install directory (per-user then machine), or None if
    FAFE isn't recorded as installed (portable/dev)."""
    try:
        import winreg
    except ImportError:
        return None
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, _UNINSTALL_KEY) as k:
                for value in ("InstallLocation", "Inno Setup: App Path"):
                    try:
                        loc, _ = winreg.QueryValueEx(k, value)
                        if loc:
                            return loc
                    except OSError:
                        continue
        except OSError:
            continue
    return None


def running_from_installed_copy() -> bool:
    """True if the running exe is the registered installed copy (so the installer
    can update it in place + relaunch it). False for portable/dev runs."""
    loc = installed_install_dir()
    if not loc:
        return False
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    except Exception:
        return False
    return _dir_matches(exe_dir, loc)
