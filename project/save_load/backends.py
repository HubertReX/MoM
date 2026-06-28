from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from save_load.models import SaveSlot, SaveSlotInfo
from settings import IS_WEB, MAX_SAVE_SLOTS, SAVE_FILE_EXT


class SaveBackend(ABC):
    @abstractmethod
    def read_slot(self, slot_idx: int) -> SaveSlot | None:
        ...

    @abstractmethod
    def write_slot(self, slot: SaveSlot) -> bool:
        ...

    @abstractmethod
    def delete_slot(self, slot_idx: int) -> bool:
        ...

    @abstractmethod
    def list_slots(self) -> list[SaveSlotInfo | None]:
        ...


class FileSaveBackend(SaveBackend):
    def __init__(self) -> None:
        import platform as _platform
        system = _platform.system()
        if system == "Darwin":
            base = Path.home() / "Library" / "Application Support" / "mom" / "saves"
        elif system == "Linux":
            base = Path.home() / ".local" / "share" / "mom" / "saves"
        else:
            base = Path.home() / "AppData" / "Local" / "mom" / "saves"
        self.save_dir: Path = base
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _slot_path(self, slot_idx: int) -> Path:
        return self.save_dir / f"save_{slot_idx}{SAVE_FILE_EXT}"

    def read_slot(self, slot_idx: int) -> SaveSlot | None:
        path = self._slot_path(slot_idx)
        if not path.exists():
            return None
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return SaveSlot.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            print(f"[save] corrupt save file {path}: {e}")
            return None

    def write_slot(self, slot: SaveSlot) -> bool:
        try:
            path = self._slot_path(int(slot.slot_id))
            path.write_text(json.dumps(slot.to_dict(), indent=2), encoding="utf-8")
            return True
        except OSError as e:
            print(f"[save] write error {path}: {e}")
            return False

    def delete_slot(self, slot_idx: int) -> bool:
        path = self._slot_path(slot_idx)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except OSError as e:
            print(f"[save] delete error {path}: {e}")
            return False

    def list_slots(self) -> list[SaveSlotInfo | None]:
        slots: list[SaveSlotInfo | None] = []
        for i in range(MAX_SAVE_SLOTS):
            slot = self.read_slot(i)
            if slot and slot.is_occupied and slot.save_data:
                slots.append(SaveSlotInfo(
                    slot_id=str(i),
                    is_occupied=True,
                    metadata=slot.save_data.metadata,
                ))
            else:
                slots.append(None)
        return slots


class LocalStorageSaveBackend(SaveBackend):
    _STORAGE_PREFIX = "MoM.save_"

    def __init__(self) -> None:
        from platform import window  # type: ignore[attr-defined]
        self._ls = window.localStorage

    def _key(self, slot_idx: int) -> str:
        return f"{self._STORAGE_PREFIX}{slot_idx}"

    def read_slot(self, slot_idx: int) -> SaveSlot | None:
        raw = self._ls.getItem(self._key(slot_idx))
        if raw is None:
            return None
        try:
            data: dict[str, Any] = json.loads(str(raw))
            return SaveSlot.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            print(f"[save] corrupt localStorage slot {slot_idx}: {e}")
            return None

    def write_slot(self, slot: SaveSlot) -> bool:
        try:
            self._ls.setItem(self._key(int(slot.slot_id)), json.dumps(slot.to_dict()))
            return True
        except Exception as e:
            print(f"[save] localStorage write error slot {slot.slot_id}: {e}")
            return False

    def delete_slot(self, slot_idx: int) -> bool:
        try:
            self._ls.removeItem(self._key(slot_idx))
            return True
        except Exception as e:
            print(f"[save] localStorage delete error slot {slot_idx}: {e}")
            return False

    def list_slots(self) -> list[SaveSlotInfo | None]:
        slots: list[SaveSlotInfo | None] = []
        for i in range(MAX_SAVE_SLOTS):
            slot = self.read_slot(i)
            if slot and slot.is_occupied and slot.save_data:
                slots.append(SaveSlotInfo(
                    slot_id=str(i),
                    is_occupied=True,
                    metadata=slot.save_data.metadata,
                ))
            else:
                slots.append(None)
        return slots
