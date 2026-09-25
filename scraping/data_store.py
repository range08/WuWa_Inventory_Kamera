"""In-memory store for generated scanner mappings.

Containers keep stable object identity so scanner modules can import references
once while the updater atomically replaces their contents after validation.
No mapping files are read at module import time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GameDataStoreError(ValueError):
    """Raised when generated scanner mappings cannot be loaded safely."""


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
            loaded_dicts[attribute] = payload

        for attribute, filename in self.LIST_FILES.items():
            payload = self._load_json(data_dir / filename)
            if not isinstance(payload, list):
                raise GameDataStoreError(
                    f"Generated mapping must be a JSON array: {filename}"
                )
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
