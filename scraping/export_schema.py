"""Validation helpers for legacy-compatible scanner exports."""

from __future__ import annotations

from typing import Any


class ExportValidationError(ValueError):
    """Raised when an export cannot be interpreted safely."""


def normalize_inventory_payload(payload: Any) -> dict[str, int]:
    """Validate and normalize a legacy inventory export.

    Metadata keys beginning with an underscore are ignored for compatibility
    with older documented examples. Item IDs are normalized to decimal strings.
    """

    if not isinstance(payload, dict):
        raise ExportValidationError("Inventory export must be a JSON object.")

    result: dict[str, int] = {}
    for raw_id, quantity in payload.items():
        if isinstance(raw_id, str) and raw_id.startswith("_"):
            continue

        if isinstance(raw_id, bool):
            raise ExportValidationError("Inventory item ID cannot be boolean.")

        try:
            item_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ExportValidationError(
                f"Inventory item ID is not numeric: {raw_id!r}"
            ) from exc

        if item_id < 0:
            raise ExportValidationError(
                f"Inventory item ID cannot be negative: {item_id}"
            )

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ExportValidationError(
                f"Inventory quantity must be an integer for item {item_id}."
            )
        if quantity < 0:
            raise ExportValidationError(
                f"Inventory quantity cannot be negative for item {item_id}."
            )

        result[str(item_id)] = quantity

    return result


def _require_int_range(
    value: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExportValidationError(f"{field} must be an integer.")
    if not minimum <= value <= maximum:
        raise ExportValidationError(
            f"{field} must be between {minimum} and {maximum}: {value}"
        )
    return value


def _require_numeric_id(value: Any, *, field: str) -> None:
    if isinstance(value, bool):
        raise ExportValidationError(f"{field} cannot be boolean.")
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise ExportValidationError(f"{field} is not numeric: {value!r}") from exc
    if numeric <= 0:
        raise ExportValidationError(f"{field} must be positive: {value!r}")


def validate_character_export(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ExportValidationError("Character export must be a JSON object.")

    for resonator_id, record in payload.items():
        _require_numeric_id(resonator_id, field="resonator ID")
        if not isinstance(record, dict):
            raise ExportValidationError("Character record must be an object.")

        _require_int_range(
            record.get("level"),
            field=f"character {resonator_id} level",
            minimum=1,
            maximum=90,
        )
        _require_int_range(
            record.get("ascension"),
            field=f"character {resonator_id} ascension",
            minimum=0,
            maximum=6,
        )
        _require_int_range(
            record.get("chain"),
            field=f"character {resonator_id} chain",
            minimum=0,
            maximum=6,
        )

        weapon = record.get("weapon")
        if not isinstance(weapon, dict):
            raise ExportValidationError(
                f"character {resonator_id} weapon must be an object."
            )
        _require_numeric_id(
            weapon.get("id"),
            field=f"character {resonator_id} weapon ID",
        )
        _require_int_range(
            weapon.get("level"),
            field=f"character {resonator_id} weapon level",
            minimum=1,
            maximum=90,
        )
        _require_int_range(
            weapon.get("ascension"),
            field=f"character {resonator_id} weapon ascension",
            minimum=0,
            maximum=6,
        )
        _require_int_range(
            weapon.get("rank"),
            field=f"character {resonator_id} weapon rank",
            minimum=1,
            maximum=5,
        )

        skills = record.get("skills")
        if not isinstance(skills, dict):
            raise ExportValidationError(
                f"character {resonator_id} skills must be an object."
            )
        for skill_name, skill_value in skills.items():
            _require_int_range(
                skill_value,
                field=f"character {resonator_id} skill {skill_name}",
                minimum=0,
                maximum=20,
            )


def validate_weapon_export(payload: Any) -> None:
    if not isinstance(payload, list):
        raise ExportValidationError("Weapon export must be a JSON array.")

    for index, entry in enumerate(payload):
        if not isinstance(entry, dict) or len(entry) != 1:
            raise ExportValidationError(
                f"Weapon export entry {index} must contain exactly one weapon."
            )
        weapon_id, record = next(iter(entry.items()))
        _require_numeric_id(weapon_id, field=f"weapon entry {index} ID")
        if not isinstance(record, dict):
            raise ExportValidationError(
                f"Weapon export entry {index} data must be an object."
            )
        _require_int_range(
            record.get("level"),
            field=f"weapon {weapon_id} level",
            minimum=1,
            maximum=90,
        )
        _require_int_range(
            record.get("ascension"),
            field=f"weapon {weapon_id} ascension",
            minimum=0,
            maximum=6,
        )
        _require_int_range(
            record.get("rank"),
            field=f"weapon {weapon_id} rank",
            minimum=1,
            maximum=5,
        )


def validate_echo_export(payload: Any) -> None:
    if not isinstance(payload, list):
        raise ExportValidationError("Echo export must be a JSON array.")

    for index, entry in enumerate(payload):
        if not isinstance(entry, dict) or len(entry) != 1:
            raise ExportValidationError(
                f"Echo export entry {index} must contain exactly one Echo."
            )
        echo_id, record = next(iter(entry.items()))
        _require_numeric_id(echo_id, field=f"Echo entry {index} ID")
        if not isinstance(record, dict):
            raise ExportValidationError(
                f"Echo export entry {index} data must be an object."
            )

        _require_int_range(
            record.get("level"),
            field=f"Echo {echo_id} level",
            minimum=0,
            maximum=25,
        )
        _require_int_range(
            record.get("tuneLv"),
            field=f"Echo {echo_id} tune level",
            minimum=0,
            maximum=5,
        )
        _require_int_range(
            record.get("rarity"),
            field=f"Echo {echo_id} rarity",
            minimum=1,
            maximum=5,
        )
        sonata = record.get("sonata")
        if not isinstance(sonata, str) or not sonata:
            raise ExportValidationError(
                f"Echo {echo_id} sonata must be a non-empty string."
            )
        stats = record.get("stats")
        if not isinstance(stats, dict):
            raise ExportValidationError(
                f"Echo {echo_id} stats must be an object."
            )
        for group_name, group in stats.items():
            if group_name not in {"main", "sub"} or not isinstance(group, dict):
                raise ExportValidationError(
                    f"Echo {echo_id} contains invalid stat group {group_name!r}."
                )
            for stat_name, stat_value in group.items():
                if (
                    not isinstance(stat_name, str)
                    or not stat_name
                    or isinstance(stat_value, bool)
                    or not isinstance(stat_value, (int, float))
                ):
                    raise ExportValidationError(
                        f"Echo {echo_id} contains invalid stat {stat_name!r}."
                    )


def validate_achievement_export(payload: Any) -> None:
    if not isinstance(payload, list):
        raise ExportValidationError("Achievement export must be a JSON array.")
    for index, achievement_id in enumerate(payload):
        _require_numeric_id(
            achievement_id,
            field=f"achievement entry {index} ID",
        )


def validate_scan_sections(
    *,
    inventory: Any,
    characters: Any,
    weapons: Any,
    echoes: Any,
    achievements: Any,
) -> None:
    normalize_inventory_payload(inventory)
    validate_character_export(characters)
    validate_weapon_export(weapons)
    validate_echo_export(echoes)
    validate_achievement_export(achievements)
