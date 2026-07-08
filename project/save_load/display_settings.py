"""Display settings persistence — resolution index + fullscreen toggle.

Desktop: ``<data_dir>/mom/settings.json`` (JSON file, same base dir as saves).
Web: localStorage key ``MoM.settings`` (same JSON format).

Fullscreen is silently forced off on web — pygame.FULLSCREEN is not
meaningful inside the pygbag canvas (browser handles fullscreen natively).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import settings as _settings

SETTINGS_FILE = "settings.json"
LOCALSTORAGE_KEY = "MoM.settings"
CURRENT_VERSION = 1


@dataclass
class DisplaySettings:
    resolution_index: int
    fullscreen: bool
    resolution: tuple[int, int] | None = None
    version: int = CURRENT_VERSION


class DisplaySettingsStorage(ABC):
    @abstractmethod
    def load(self) -> DisplaySettings:
        ...

    @abstractmethod
    def save(self, settings: DisplaySettings) -> bool:
        ...


class FileDisplaySettingsStorage(DisplaySettingsStorage):
    def __init__(self) -> None:
        import os
        import platform as _platform

        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            base = Path(xdg_data_home) / "mom"
        else:
            system = _platform.system()
            if system == "Darwin":
                base = Path.home() / "Library" / "Application Support" / "mom"
            elif system == "Linux":
                base = Path.home() / ".local" / "share" / "mom"
            else:
                base = Path.home() / "AppData" / "Local" / "mom"
        self._dir: Path = base
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path: Path = self._dir / SETTINGS_FILE

    def load(self) -> DisplaySettings:
        if not self._path.exists():
            return _default_settings()
        try:
            raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
            return _parse_settings(raw)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError, OSError) as e:
            print(f"[display_settings] corrupt file {self._path}: {e}")
            return _default_settings()

    def save(self, settings: DisplaySettings) -> bool:
        try:
            data: dict[str, Any] = {
                "version": settings.version,
                "resolution_index": settings.resolution_index,
                "fullscreen": settings.fullscreen,
            }
            if settings.resolution is not None:
                data["resolution"] = [settings.resolution[0], settings.resolution[1]]
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        except OSError as e:
            print(f"[display_settings] write error {self._path}: {e}")
            return False


class LocalStorageDisplaySettingsStorage(DisplaySettingsStorage):
    def __init__(self) -> None:
        from platform import window  # type: ignore[attr-defined]

        self._ls = window.localStorage

    def load(self) -> DisplaySettings:
        try:
            raw_str: str | None = self._ls.getItem(LOCALSTORAGE_KEY)
            if raw_str is None:
                return _default_settings()
            raw: dict[str, Any] = json.loads(str(raw_str))
            ds = _parse_settings(raw)
            ds.fullscreen = False
            return ds
        except Exception as e:
            print(f"[display_settings] localStorage load error: {e}")
            return _default_settings()

    def save(self, settings: DisplaySettings) -> bool:
        try:
            data: dict[str, Any] = {
                "version": settings.version,
                "resolution_index": settings.resolution_index,
                "fullscreen": settings.fullscreen,
            }
            if settings.resolution is not None:
                data["resolution"] = [settings.resolution[0], settings.resolution[1]]
            self._ls.setItem(LOCALSTORAGE_KEY, json.dumps(data))
            return True
        except Exception as e:
            print(f"[display_settings] localStorage write error: {e}")
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp_index(index: int) -> int:
    max_idx = len(_settings.DISPLAY_RES_OPTIONS) - 1
    return max(0, min(index, max_idx))


def _parse_resolution(raw: Any) -> tuple[int, int] | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            return (int(raw[0]), int(raw[1]))
        except (ValueError, TypeError):
            return None
    return None


def _parse_settings(raw: dict[str, Any]) -> DisplaySettings:
    raw_version = raw.get("version", 0)
    if raw_version != CURRENT_VERSION:
        return _default_settings()
    return DisplaySettings(
        resolution_index=_clamp_index(raw.get("resolution_index", 0)),
        fullscreen=bool(raw.get("fullscreen", False)),
        resolution=_parse_resolution(raw.get("resolution")),
    )


def _default_settings() -> DisplaySettings:
    return DisplaySettings(resolution_index=0, fullscreen=False)


def create_display_settings_storage() -> DisplaySettingsStorage:
    """Return the correct backend for the current platform."""
    if _settings.IS_WEB and not _settings.USE_WEB_SIMULATOR:
        return LocalStorageDisplaySettingsStorage()
    return FileDisplaySettingsStorage()


def load_display_settings(storage: DisplaySettingsStorage | None = None) -> DisplaySettings:
    """Load and return DisplaySettings from persistent storage.

    If *storage* is ``None`` a platform-appropriate backend is created.
    """
    if storage is None:
        storage = create_display_settings_storage()
    return storage.load()


def save_display_settings(storage: DisplaySettingsStorage | None = None) -> None:
    """Persist the current runtime display settings.

    Uses the values from ``settings._DISPLAY_RES_INDEX`` and
    ``settings._IS_FULLSCREEN``.  If *storage* is ``None`` a
    platform-appropriate backend is created.
    """
    if storage is None:
        storage = create_display_settings_storage()
    ds = DisplaySettings(
        resolution_index=_settings._DISPLAY_RES_INDEX,
        fullscreen=_settings._IS_FULLSCREEN,
    )
    idx = _settings._DISPLAY_RES_INDEX
    if 0 <= idx < len(_settings.DISPLAY_RES_OPTIONS):
        xt, yt = _settings.DISPLAY_RES_OPTIONS[idx]
        ds.resolution = (xt * _settings.TILE_SIZE, yt * _settings.TILE_SIZE)
    storage.save(ds)
