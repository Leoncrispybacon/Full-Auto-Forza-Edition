"""Optional new-car cutscene skip.

Derives loose cinematic-override files from the user's OWN game data
(`Cinematics.zip`) and writes them where the engine loads overrides. FAFE ships
only this transform logic — never any third-party mod file. Install is additive
and fully reversible: the packed originals are never modified.
"""

from __future__ import annotations

import os
import shutil
import zipfile
import xml.etree.ElementTree as ET

# The six home-space cutscenes we speed up (car appearing / departing / being
# purchased), matched by basename inside Cinematics.zip. The reference mod applies
# the identical edit to all six. The two freeroam_intro cinematics the mod also
# ships take a DIFFERENT edit (duration 0.1, keep the camera track) and aren't the
# new-car cutscene, so they're deliberately excluded.
TARGET_BASENAMES = (
    "pgc3002_homespace_car_start_01.xml",
    "pgc3003_homespace_car_start_02.xml",
    "pgc3004_homespace_depart_01.xml",
    "pgc3290_homespace_car_purchase_01.xml",
    "pgc3292_homespace_depart_02_garage.xml",
    "pgc3293_homespace_car_purchase_02_garage.xml",
)

# Loose-override root (relative to the game dir) the engine reads instead of the
# packed copy. Confirm on first real install; resolved paths are logged.
_OVERRIDE_ROOT = ("mediapc", "Cinematics")

# Pristine-original backup made before the first zip edit; uninstall restores it.
_BACKUP_SUFFIX = ".fafe-backup"

# Director edits: kill the fade + push the letterbox bars off-screen.
_DIRECTOR_ATTRS = {
    "FadeA": "0.000000",
    "MotionBlur": "0",
    "BorderTop": "-1.100000",
    "BorderBottom": "1.100000",
    "CurrentCamera": "ForzaCamera001",
    "GSRLocatorName": "",
    "GSRRoute": "-1",
}
# ALL Director animation tracks are dropped — they never play at duration 0, and
# the reference mod strips every one (camera / fade / border / exposure / …).


class CutsceneModError(Exception):
    """Install/uninstall/resolution failure (localized upstream)."""


class TransformError(CutsceneModError):
    """The XML wasn't shaped as expected — never write a guess."""


def transform_xml(raw: bytes) -> bytes:
    """Apply the cutscene-skip edit set to one cinematic XML. Raises
    TransformError if the expected <Timeline>/<Director> are absent."""
    root = ET.fromstring(raw)
    timelines = list(root.iter("Timeline"))
    directors = list(root.iter("Director"))
    if not timelines or not directors:
        raise TransformError("expected <Timeline> and <Director> not found")
    for tl in timelines:
        tl.set("duration", "0.0")
    for d in directors:
        for k, v in _DIRECTOR_ATTRS.items():
            d.set(k, v)
        for anims in d.findall("Animations"):
            for track in [t for t in anims if t.tag == "Track"]:
                anims.remove(track)
    return ET.tostring(root, encoding="utf-8")


def find_cinematics_zip(game_dir: str) -> str | None:
    """Locate Cinematics.zip under the game dir. Checks the known
    Content\\media path first, then walks as a fallback. None if absent."""
    default = os.path.join(game_dir, "Content", "media", "Cinematics.zip")
    if os.path.isfile(default):
        return default
    for base, _dirs, files in os.walk(game_dir):
        for name in files:
            if name.lower() == "cinematics.zip":
                return os.path.join(base, name)
    return None


def override_dest(game_dir: str, entry: str) -> str:
    """Absolute path of the loose override for a zip entry (e.g.
    'forte/autoshow/pgc3002_...xml')."""
    return os.path.join(game_dir, *_OVERRIDE_ROOT, *entry.split("/"))


def resolve_game_dir(cfg: dict) -> str | None:
    """Best-effort game directory: the running game window's exe dir. Falls back
    to a stored cutscene_skip_game_dir. None if neither is available (caller then
    prompts the user to browse). Windows-only (ctypes)."""
    stored = (cfg or {}).get("cutscene_skip_game_dir", "")
    exe = _exe_of_game_window(cfg)
    if exe and os.path.isfile(exe):
        return os.path.dirname(exe)
    if stored and os.path.isdir(stored):
        return stored
    return None


def game_running(cfg: dict) -> bool:
    """True if the FH6 window is open. Editing Cinematics.zip requires the game
    CLOSED (it holds the archive open, and would re-verify/replace it on exit)."""
    try:
        import capture
        title = (cfg or {}).get("background_window_title", "Forza Horizon 6")
        return bool(capture.find_game_window(title))
    except Exception:
        return False


def _exe_of_game_window(cfg: dict) -> str | None:
    try:
        import ctypes
        from ctypes import wintypes
        import capture
        title = (cfg or {}).get("background_window_title", "Forza Horizon 6")
        hwnd = capture.find_game_window(title)
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buf))
            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                h, 0, buf, ctypes.byref(size))
            return buf.value if ok else None
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        return None


def _zip_entry_for(names: list[str], basename: str) -> str | None:
    """Find the full zip entry whose basename matches (case-insensitive)."""
    b = basename.lower()
    for n in names:
        if n.rsplit("/", 1)[-1].lower() == b:
            return n
    return None


def _backup_path(zpath: str) -> str:
    return zpath + _BACKUP_SUFFIX


def _rm_quiet(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def install(game_dir: str) -> list[str]:
    """Speed the two car_start cinematics by editing them IN PLACE inside
    Cinematics.zip (FH6 does not honour the loose-override path). A one-time
    pristine backup (`<zip>.fafe-backup`) is made first so uninstall can restore.
    A zip can't be edited in place, so the whole archive is rewritten (every
    other entry copied through unchanged) and atomically swapped in. Raises
    CutsceneModError on any failure WITHOUT leaving a half-written zip. Returns
    [zip_path]. Idempotent: transform is a no-op on already-edited entries, and an
    existing backup is never overwritten (keeps the pristine copy)."""
    zpath = find_cinematics_zip(game_dir)
    if not zpath:
        raise CutsceneModError(
            f"Cinematics.zip not found under {game_dir} "
            f"(looked in Content\\media and every subfolder)")
    bak = _backup_path(zpath)
    tmp = zpath + ".fafe-tmp"
    try:
        # Back up the pristine original ONCE (never overwrite with a modified zip).
        if not os.path.exists(bak):
            shutil.copy2(zpath, bak)
        with zipfile.ZipFile(zpath) as zin:
            names = zin.namelist()
            edits: dict[str, bytes] = {}
            for base in TARGET_BASENAMES:
                entry = _zip_entry_for(names, base)
                if entry is None:
                    raise CutsceneModError(f"{base} not found in Cinematics.zip")
                edits[entry] = transform_xml(zin.read(entry))
            with zipfile.ZipFile(tmp, "w") as zout:
                for info in zin.infolist():
                    data = edits.get(info.filename)
                    if data is None:
                        data = zin.read(info.filename)
                    zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    zi.compress_type = info.compress_type
                    zi.external_attr = info.external_attr
                    zi.internal_attr = info.internal_attr
                    zi.create_system = info.create_system
                    zout.writestr(zi, data)
        os.replace(tmp, zpath)          # atomic swap
        return [zpath]
    except CutsceneModError:
        _rm_quiet(tmp)
        raise
    except (OSError, zipfile.BadZipFile, ET.ParseError) as e:
        _rm_quiet(tmp)
        raise CutsceneModError(str(e)) from e


def _override_paths(game_dir: str) -> list[str]:
    """Dead loose-override files from the earlier (non-working) approach —
    cleaned up on uninstall."""
    return [override_dest(game_dir, f"forte/autoshow/{b}")
            for b in TARGET_BASENAMES]


def uninstall(game_dir: str) -> None:
    """Restore Cinematics.zip from the pristine backup (if present), then clean up
    any dead loose-override files from the earlier approach. Tolerates a missing
    backup / missing files."""
    zpath = find_cinematics_zip(game_dir)
    if zpath:
        bak = _backup_path(zpath)
        if os.path.exists(bak):
            try:
                os.replace(bak, zpath)   # restore pristine; removes the backup
            except OSError as e:
                raise CutsceneModError(str(e)) from e
    for p in _override_paths(game_dir):
        _rm_quiet(p)
    root = os.path.join(game_dir, *_OVERRIDE_ROOT)
    for base, dirs, files in os.walk(root, topdown=False):
        if not dirs and not files:
            try:
                os.rmdir(base)
            except OSError:
                pass


def _is_transformed(raw: bytes) -> bool:
    """True if a cinematic entry already carries the skip edit (all Timelines 0)."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return False
    tls = list(root.iter("Timeline"))
    return bool(tls) and all(tl.get("duration") == "0.0" for tl in tls)


def status(game_dir: str) -> dict:
    """Whether the two car_start entries INSIDE Cinematics.zip currently carry the
    skip edit. 'files_present' keeps its name for the Api layer; 'backup_present'
    shows a restore point exists."""
    zpath = find_cinematics_zip(game_dir)
    installed = False
    if zpath and os.path.isfile(zpath):
        try:
            with zipfile.ZipFile(zpath) as z:
                names = z.namelist()
                checks = []
                for base in TARGET_BASENAMES:
                    entry = _zip_entry_for(names, base)
                    checks.append(bool(entry) and _is_transformed(z.read(entry)))
                installed = bool(checks) and all(checks)
        except (OSError, zipfile.BadZipFile):
            installed = False
    bak = _backup_path(zpath) if zpath else None
    return {"files_present": installed,
            "backup_present": bool(bak and os.path.exists(bak)),
            "paths": [zpath] if zpath else []}
