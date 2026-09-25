"""Generate legacy-compatible scanner mappings from cached Global client data."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MappingGenerationError(RuntimeError):
    """Raised when cached source data cannot be transformed safely."""


GENERATED_MANIFEST_NAME = "mapping_manifest.json"
GENERATED_MAPPING_FILES = (
    "characters.json",
    "weapons.json",
    "items.json",
    "echoes.json",
    "achievements.json",
    "echoStats.json",
    "sonataName.json",
    "definedText.json",
)


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


def _validate_records(
    records: Any,
    label: str,
    required_fields: dict[str, type],
) -> list[dict]:
    if not isinstance(records, list):
        raise MappingGenerationError(f"{label} must be a list")

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise MappingGenerationError(
                f"{label}[{index}] must be an object"
            )

        for field, expected_type in required_fields.items():
            if field not in record:
                raise MappingGenerationError(
                    f"{label}[{index}] is missing required field {field!r}"
                )
            if not isinstance(record[field], expected_type):
                raise MappingGenerationError(
                    f"{label}[{index}].{field} must be "
                    f"{expected_type.__name__}"
                )

    return records


def image_filename(asset_path: str) -> str:
    """Return the legacy assets-relative PNG path for a game UI texture.

    Example:
    /Game/Aki/UI/UIResources/Common/Image/IconA/Foo.T_Foo
    -> IconA/Foo.png

    Keeping the directory component is required because assets with the same
    filename can live in different UI resource folders and the inventory UI
    resolves paths relative to the local assets directory.
    """
    if not asset_path:
        return ""

    marker = "/UIResources/Common/Image/"
    if marker in asset_path:
        relative = asset_path.split(marker, 1)[1]
    else:
        relative = asset_path.rsplit("/", 1)[-1]

    relative = relative.split(".", 1)[0].strip("/")
    return f"{relative}.png" if relative else ""


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


def _insert_unambiguous(
    target: dict,
    ambiguous: set[str],
    normalized: str,
    value: Any,
    source_key: str,
) -> None:
    """Keep only names that identify exactly one source record.

    OCR-based scanners cannot safely choose between different IDs that share the
    same visible name. Once a collision is detected, remove that name entirely
    and remember it so later records cannot reintroduce an arbitrary winner.
    """

    if not normalized:
        raise MappingGenerationError(f"Empty normalized name for {source_key}")
    if normalized in ambiguous:
        return

    if normalized not in target:
        target[normalized] = value
        return

    if target[normalized] != value:
        target.pop(normalized, None)
        ambiguous.add(normalized)


def generate_characters(
    role_info: list[dict],
    textmap: dict[str, str],
    excluded_role_ids: set[int] | None = None,
) -> dict[str, int]:
    role_info = _validate_records(
        role_info,
        "RoleInfo",
        {"Id": int, "Name": str},
    )
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
    weapon_info = _validate_records(
        weapon_info,
        "WeaponConf",
        {"WeaponName": str, "QualityId": int},
    )
    for index, weapon in enumerate(weapon_info):
        weapon_id = weapon.get("ModelId", weapon.get("ItemId"))
        if not isinstance(weapon_id, int):
            raise MappingGenerationError(
                f"WeaponConf[{index}] is missing a valid ModelId/ItemId"
            )

    result: dict[str, dict] = {}
    ambiguous: set[str] = set()
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
        _insert_unambiguous(
            result,
            ambiguous,
            normalize_name(name),
            value,
            str(weapon.get("WeaponName")),
        )
    return result


def generate_items(item_info: list[dict], textmap: dict[str, str]) -> dict[str, dict]:
    item_info = _validate_records(
        item_info,
        "ItemInfo",
        {"Id": int, "Name": str},
    )
    result: dict[str, dict] = {}
    ambiguous: set[str] = set()
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
        _insert_unambiguous(
            result,
            ambiguous,
            normalize_name(name),
            value,
            str(item.get("Name")),
        )
    return result


def generate_echoes(monster_info: list[dict], textmap: dict[str, str]) -> dict[str, int]:
    monster_info = _validate_records(
        monster_info,
        "MonsterInfo",
        {"Id": int, "Name": str},
    )
    result: dict[str, int] = {}
    ambiguous: set[str] = set()
    for monster in monster_info:
        monster_id = monster.get("Id")
        if not isinstance(monster_id, int) or monster_id >= 350_000_000:
            continue
        name = _localized(textmap, monster.get("Name"))
        if name is None:
            continue
        _insert_unambiguous(
            result,
            ambiguous,
            normalize_name(name),
            monster_id,
            str(monster.get("Name")),
        )
    return result


def generate_achievements(achievement_info: list[dict], textmap: dict[str, str]) -> dict[str, int]:
    achievement_info = _validate_records(
        achievement_info,
        "Achievement",
        {"Id": int, "Name": str},
    )
    result: dict[str, int] = {}
    ambiguous: set[str] = set()
    for achievement in achievement_info:
        achievement_id = achievement.get("Id")
        name = _localized(textmap, achievement.get("Name"))
        if name is None or not isinstance(achievement_id, int):
            continue
        _insert_unambiguous(
            result,
            ambiguous,
            name,
            achievement_id,
            str(achievement.get("Name")),
        )
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

    source_manifest = _source_manifest(cache_dir)
    language = _manifest_language(source_manifest)
    textmap = load_textmap(
        cache_dir / "Textmaps" / language / "multi_text" / "MultiText.json"
    )
    main_role_config = _validate_records(
        load_json(cache_dir / "BinData/main_role_change/mainroleconfig.json"),
        "MainRoleConfig",
        {"Id": int},
    )
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
        "weapons.json": generate_weapons(
            load_json(cache_dir / "BinData/weapon/weaponconf.json"),
            textmap,
        ),
        "items.json": generate_items(
            load_json(cache_dir / "BinData/item/iteminfo.json"),
            textmap,
        ),
        "echoes.json": generate_echoes(
            load_json(cache_dir / "BinData/monster_Info/monsterinfo.json"),
            textmap,
        ),
        "achievements.json": generate_achievements(
            load_json(cache_dir / "BinData/achievement/achievement.json"),
            textmap,
        ),
        "echoStats.json": generate_echo_stats(textmap),
        "sonataName.json": generate_sonata_names(textmap),
        "definedText.json": generate_defined_text(textmap),
    }

    for filename, data in outputs.items():
        if not data:
            raise MappingGenerationError(
                f"Generated mapping is empty: {filename}"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    generated_files: dict[str, dict[str, int | str]] = {}

    for filename, data in outputs.items():
        payload = (
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
                sort_keys=isinstance(data, dict),
            )
            + "\n"
        ).encode("utf-8")
        _atomic_write(output_dir / filename, payload)
        counts[filename] = len(data)
        generated_files[filename] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "count": len(data),
        }

    mapping_manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": _source_identity(source_manifest),
        "files": dict(sorted(generated_files.items())),
    }
    _atomic_write(
        output_dir / GENERATED_MANIFEST_NAME,
        (
            json.dumps(
                mapping_manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
    )

    return counts


def generated_mappings_current(
    cache_dir: Path | str,
    output_dir: Path | str,
) -> dict[str, int] | None:
    """Return generated mapping counts when outputs match the source manifest."""

    cache_dir = Path(cache_dir)
    output_dir = Path(output_dir)

    try:
        source_manifest = _source_manifest(cache_dir)
        generated = load_json(output_dir / GENERATED_MANIFEST_NAME)
    except MappingGenerationError:
        return None

    if not isinstance(generated, dict) or generated.get("schema_version") != 1:
        return None
    if generated.get("source") != _source_identity(source_manifest):
        return None

    files = generated.get("files")
    if not isinstance(files, dict):
        return None

    counts: dict[str, int] = {}
    for filename in GENERATED_MAPPING_FILES:
        expected = files.get(filename)
        if not isinstance(expected, dict):
            return None

        path = output_dir / filename
        try:
            payload = path.read_bytes()
        except OSError:
            return None

        if hashlib.sha256(payload).hexdigest() != expected.get("sha256"):
            return None
        if len(payload) != expected.get("size"):
            return None

        count = expected.get("count")
        if not isinstance(count, int) or count < 0:
            return None
        counts[filename] = count

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


def _source_manifest(cache_dir: Path) -> dict:
    manifest = load_json(cache_dir / "manifest.json")
    if not isinstance(manifest, dict):
        raise MappingGenerationError("Source manifest must be an object")
    return manifest


def _manifest_language(manifest: dict) -> str:
    language = manifest.get("language")
    if (
        not isinstance(language, str)
        or not language
        or "/" in language
        or "\\" in language
        or ".." in language
    ):
        raise MappingGenerationError("Manifest contains an invalid language")
    return language


def _source_identity(manifest: dict) -> dict[str, str]:
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise MappingGenerationError("Source manifest is missing source metadata")

    fields = (
        "repository",
        "ref",
        "game_version",
        "resource_version",
        "changelist",
    )
    identity: dict[str, str] = {}
    for field in fields:
        value = source.get(field)
        if not isinstance(value, str) or not value:
            raise MappingGenerationError(
                "Source manifest contains invalid metadata: {}".format(field)
            )
        identity[field] = value

    revision = manifest.get("revision")
    language = manifest.get("language")
    if not isinstance(revision, str) or not revision:
        raise MappingGenerationError("Source manifest contains invalid revision")
    if not isinstance(language, str) or not language:
        raise MappingGenerationError("Source manifest contains invalid language")

    identity["revision"] = revision
    identity["language"] = language
    return identity
