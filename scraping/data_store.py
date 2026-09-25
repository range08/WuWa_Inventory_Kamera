"""In-memory store for generated scanner mappings.

Containers keep stable object identity so scanner modules can import references
once while the updater atomically replaces their contents after validation.
No mapping files are read at module import time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict, cast


class GameDataStoreError(ValueError):
    """Raised when generated scanner mappings cannot be loaded safely."""


class ItemRecord(TypedDict):
    id: int
    name: str
    image: str


class WeaponRecord(ItemRecord):
    rarity: int


class GeneratedDataStore:
    DICT_FILES = {
        "items": "items.json",
        "characters": "characters.json",
        "weapons": "weapons.json",
        "echoes": "echoes.json",
        "achievements": "achievements.json",
        "echo_stats": "echoStats.json",
        "defined_text": "definedText.json",
    }
    LIST_FILES = {
        "sonata_names": "sonataName.json",
    }

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.characters: dict[str, int] = {}
        self.weapons: dict[str, dict] = {}
        self.echoes: dict[str, int] = {}
        self.achievements: dict[str, int] = {}
        self.echo_stats: dict[str, str] = {}
        self.defined_text: dict[str, str] = {}
        self.sonata_names: list[str] = []

    def reload(self, data_dir: Path | str) -> dict[str, int]:
        """Validate every mapping before mutating any live container."""
        data_dir = Path(data_dir)
        loaded_dicts: dict[str, dict] = {}
        loaded_lists: dict[str, list] = {}

        for attribute, filename in self.DICT_FILES.items():
            payload = self._load_json(data_dir / filename)
            if not isinstance(payload, dict):
                raise GameDataStoreError(
                    f"Generated mapping must be a JSON object: {filename}"
                )
            self._validate_dict_mapping(attribute, filename, payload)
            loaded_dicts[attribute] = payload

        for attribute, filename in self.LIST_FILES.items():
            payload = self._load_json(data_dir / filename)
            if not isinstance(payload, list):
                raise GameDataStoreError(
                    f"Generated mapping must be a JSON array: {filename}"
                )
            self._validate_list_mapping(attribute, filename, payload)
            loaded_lists[attribute] = payload

        counts: dict[str, int] = {}
        for attribute, payload in loaded_dicts.items():
            target = getattr(self, attribute)
            target.clear()
            target.update(payload)
            counts[self.DICT_FILES[attribute]] = len(payload)

        for attribute, payload in loaded_lists.items():
            target = getattr(self, attribute)
            target.clear()
            target.extend(payload)
            counts[self.LIST_FILES[attribute]] = len(payload)

        return counts

    @staticmethod
    def _validate_dict_mapping(
        attribute: str,
        filename: str,
        payload: dict,
    ) -> None:
        if attribute in {"characters", "echoes", "achievements"}:
            if not all(
                isinstance(key, str)
                and key
                and isinstance(value, int)
                and not isinstance(value, bool)
                for key, value in payload.items()
            ):
                raise GameDataStoreError(
                    f"Generated ID mapping contains invalid entries: {filename}"
                )
            return

        if attribute in {"echo_stats", "defined_text"}:
            if not all(
                isinstance(key, str)
                and key
                and isinstance(value, str)
                and value
                for key, value in payload.items()
            ):
                raise GameDataStoreError(
                    f"Generated text mapping contains invalid entries: {filename}"
                )
            return

        if attribute in {"items", "weapons"}:
            for key, value in payload.items():
                if not isinstance(key, str) or not key or not isinstance(value, dict):
                    raise GameDataStoreError(
                        f"Generated record mapping contains invalid entries: {filename}"
                    )
                required = {
                    "id": int,
                    "name": str,
                    "image": str,
                }
                if attribute == "weapons":
                    required["rarity"] = int

                for field, expected_type in required.items():
                    field_value = value.get(field)
                    if (
                        not isinstance(field_value, expected_type)
                        or isinstance(field_value, bool)
                    ):
                        raise GameDataStoreError(
                            f"Generated {filename} entry {key!r} has "
                            f"invalid {field!r}."
                        )
                if attribute == "weapons" and not 1 <= value["rarity"] <= 5:
                    raise GameDataStoreError(
                        f"Generated {filename} entry {key!r} has invalid rarity."
                    )
            return

        raise GameDataStoreError(f"Unknown generated mapping: {filename}")

    @staticmethod
    def _validate_list_mapping(
        attribute: str,
        filename: str,
        payload: list,
    ) -> None:
        if attribute != "sonata_names":
            raise GameDataStoreError(f"Unknown generated mapping: {filename}")
        if not all(isinstance(value, str) and value for value in payload):
            raise GameDataStoreError(
                f"Generated list mapping contains invalid entries: {filename}"
            )

    @staticmethod
    def _load_json(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (
            FileNotFoundError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise GameDataStoreError(
                f"Unable to load generated mapping: {path.name}"
            ) from exc


STORE = GeneratedDataStore()

# Stable compatibility aliases used throughout the existing scanner code.
itemsID = STORE.items
charactersID = STORE.characters
weaponsID = STORE.weapons
echoesID = STORE.echoes
achievementsID = STORE.achievements
echoStats = STORE.echo_stats
definedText = STORE.defined_text
sonataName = STORE.sonata_names


def reload_generated_mappings(data_dir: Path | str) -> dict[str, int]:
    return STORE.reload(data_dir)


def get_item(normalized_name: str) -> ItemRecord | None:
    value = itemsID.get(normalized_name)
    return cast(ItemRecord, value) if value is not None else None


def get_weapon(normalized_name: str) -> WeaponRecord | None:
    value = weaponsID.get(normalized_name)
    return cast(WeaponRecord, value) if value is not None else None


def get_character_id(normalized_name: str) -> int | None:
    return charactersID.get(normalized_name)


def get_echo_id(normalized_name: str) -> int | None:
    return echoesID.get(normalized_name)


def get_achievement_id(display_name: str) -> int | None:
    return achievementsID.get(display_name)


def find_item_by_id(item_id: int) -> ItemRecord | None:
    for value in itemsID.values():
        record = cast(ItemRecord, value)
        if record["id"] == item_id:
            return record
    return None


def find_item_by_display_name(display_name: str) -> ItemRecord | None:
    for value in itemsID.values():
        record = cast(ItemRecord, value)
        if record["name"] == display_name:
            return record
    return None
