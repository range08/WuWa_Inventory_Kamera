"""Generate legacy-compatible scanner mappings from cached Global client data."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


class MappingGenerationError(RuntimeError):
    """Raised when cached source data cannot be transformed safely."""


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise MappingGenerationError(f"Unable to load source JSON: {path}") from exc


def load_textmap(path: Path) -> dict[str, str]:
    raw = load_json(path)
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}

    if not isinstance(raw, list):
        raise MappingGenerationError("Textmap must be an object or a list of Id/Content entries")

    result: dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict) or "Id" not in entry or "Content" not in entry:
            raise MappingGenerationError("Malformed textmap entry")
        key = str(entry["Id"])
        value = str(entry["Content"])
        if key in result and result[key] != value:
            raise MappingGenerationError(f"Conflicting textmap key: {key}")
        result[key] = value
    return result


def image_filename(asset_path: str) -> str:
    if not asset_path:
        return ""
    leaf = asset_path.rsplit("/", 1)[-1]
    stem = leaf.split(".", 1)[0]
    return f"{stem}.png" if stem else ""


def _localized(textmap: dict[str, str], key: Any) -> str | None:
    if not isinstance(key, str) or not key:
        return None
    value = textmap.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _insert_unique(target: dict, normalized: str, value: Any, source_key: str) -> None:
    if not normalized:
        raise MappingGenerationError(f"Empty normalized name for {source_key}")
    if normalized in target and target[normalized] != value:
        raise MappingGenerationError(f"Duplicate normalized name: {normalized}")
    target[normalized] = value


def generate_characters(
    role_info: list[dict],
    textmap: dict[str, str],
    excluded_role_ids: set[int] | None = None,
) -> dict[str, int]:
    result: dict[str, int] = {}
    excluded_role_ids = excluded_role_ids or set()

    for role in role_info:
        role_id = role.get("Id")
        if not isinstance(role_id, int) or role_id >= 5000:
            continue
        if role_id in excluded_role_ids:
            continue
        if role.get("ParentId", 0) != 0:
            continue
        if "RoleType" in role and role.get("RoleType") != 1:
            continue

        name = _localized(textmap, role.get("Name"))
        if name is None:
            continue
        _insert_unique(result, normalize_name(name), role_id, str(role.get("Name")))
    return result


def generate_weapons(weapon_info: list[dict], textmap: dict[str, str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for weapon in weapon_info:
        name = _localized(textmap, weapon.get("WeaponName"))
        weapon_id = weapon.get("ModelId", weapon.get("ItemId"))
        rarity = weapon.get("QualityId")
        if name is None or not isinstance(weapon_id, int) or not isinstance(rarity, int):
            continue
        value = {
            "id": weapon_id,
            "name": name,
            "rarity": rarity,
            "image": image_filename(str(weapon.get("Icon", ""))),
        }
        _insert_unique(result, normalize_name(name), value, str(weapon.get("WeaponName")))
    return result


def generate_items(item_info: list[dict], textmap: dict[str, str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in item_info:
        item_id = item.get("Id")
        name = _localized(textmap, item.get("Name"))
        if name is None or not isinstance(item_id, int):
            continue
        value = {
            "id": item_id,
            "name": name,
            "image": image_filename(str(item.get("Icon", ""))),
        }
        _insert_unique(result, normalize_name(name), value, str(item.get("Name")))
    return result


def generate_echoes(monster_info: list[dict], textmap: dict[str, str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for monster in monster_info:
        monster_id = monster.get("Id")
        if not isinstance(monster_id, int) or monster_id >= 350_000_000:
            continue
        name = _localized(textmap, monster.get("Name"))
        if name is None:
            continue
        _insert_unique(result, normalize_name(name), monster_id, str(monster.get("Name")))
    return result


def generate_achievements(achievement_info: list[dict], textmap: dict[str, str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for achievement in achievement_info:
        achievement_id = achievement.get("Id")
        name = _localized(textmap, achievement.get("Name"))
        if name is None or not isinstance(achievement_id, int):
            continue
        if name in result and result[name] != achievement_id:
            raise MappingGenerationError(f"Duplicate achievement name: {name}")
        result[name] = achievement_id
    return result


ECHO_STAT_KEYS = {
    "PropertyIndex_10003_Name": "hp",
    "PropertyIndex_10007_Name": "atk",
    "PropertyIndex_10008_Name": "cr",
    "PropertyIndex_10009_Name": "cd",
    "PropertyIndex_10010_Name": "def",
    "PropertyIndex_10011_Name": "er",
    "PropertyIndex_10014_Name": "skillDmg",
    "PropertyIndex_10017_Name": "basicAttack",
    "PropertyIndex_10018_Name": "heavyAttack",
    "PropertyIndex_10019_Name": "liberationDmg",
    "PropertyIndex_10022_Name": "glacio",
    "PropertyIndex_10023_Name": "fusion",
    "PropertyIndex_10024_Name": "electro",
    "PropertyIndex_10025_Name": "aero",
    "PropertyIndex_10026_Name": "spectro",
    "PropertyIndex_10027_Name": "havoc",
    "PropertyIndex_10035_Name": "healing",
}

DEFINED_TEXT_KEYS = (
    "PrefabTextItem_1547656443_Text",
    "PrefabTextItem_128820487_Text",
    "PrefabTextItem_3963945691_Text",
)


def generate_echo_stats(textmap: dict[str, str]) -> dict[str, str]:
    result = {}
    for key, canonical in ECHO_STAT_KEYS.items():
        value = _localized(textmap, key)
        if value is not None:
            result[normalize_name(value).replace(".", "")] = canonical
    return result


def generate_sonata_names(textmap: dict[str, str]) -> list[str]:
    names = []
    pattern = re.compile(r"^PhantomFetter_(\d+)_Name$")
    for key, value in textmap.items():
        if pattern.match(key) and value.strip():
            names.append(normalize_name(value))
    return sorted(set(names))


def generate_defined_text(textmap: dict[str, str]) -> dict[str, str]:
    result = {}
    for key in DEFINED_TEXT_KEYS:
        value = _localized(textmap, key)
        if value is not None:
            result[key] = normalize_name(value).replace("-", "")
    return result


def generate_from_cache(cache_dir: Path | str, output_dir: Path | str) -> dict[str, int]:
    cache_dir = Path(cache_dir)
    output_dir = Path(output_dir)

    textmap = load_textmap(cache_dir / "Textmaps" / _manifest_language(cache_dir) / "multi_text" / "MultiText.json")
    main_role_config = load_json(
        cache_dir / "BinData/main_role_change/mainroleconfig.json"
    )
    if not isinstance(main_role_config, list):
        raise MappingGenerationError("Main-role configuration must be a list")
    main_role_ids = {
        entry["Id"]
        for entry in main_role_config
        if isinstance(entry, dict) and isinstance(entry.get("Id"), int)
    }

    outputs = {
        "characters.json": generate_characters(
            load_json(cache_dir / "BinData/role/roleinfo.json"),
            textmap,
            excluded_role_ids=main_role_ids,
        ),
        "weapons.json": generate_weapons(load_json(cache_dir / "BinData/weapon/weaponconf.json"), textmap),
        "items.json": generate_items(load_json(cache_dir / "BinData/item/iteminfo.json"), textmap),
        "echoes.json": generate_echoes(load_json(cache_dir / "BinData/monster_Info/monsterinfo.json"), textmap),
        "achievements.json": generate_achievements(load_json(cache_dir / "BinData/achievement/achievement.json"), textmap),
        "echoStats.json": generate_echo_stats(textmap),
        "sonataName.json": generate_sonata_names(textmap),
        "definedText.json": generate_defined_text(textmap),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for filename, data in outputs.items():
        payload = (
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=isinstance(data, dict)) + "\n"
        ).encode("utf-8")
        _atomic_write(output_dir / filename, payload)
        counts[filename] = len(data)

    return counts


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as temp:
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _manifest_language(cache_dir: Path) -> str:
    manifest = load_json(cache_dir / "manifest.json")
    language = manifest.get("language") if isinstance(manifest, dict) else None
    if not isinstance(language, str) or not language or "/" in language or "\\" in language or ".." in language:
        raise MappingGenerationError("Manifest contains an invalid language")
    return language
