"""Pure filtering rules for scanner export thresholds."""

from __future__ import annotations


def _validate_int(
    value: int,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(
            f"{name} must be between {minimum} and {maximum}: {value}"
        )


def include_weapon(
    *,
    rarity: int,
    level: int,
    min_rarity: int,
    min_level: int,
) -> bool:
    _validate_int(rarity, name="rarity", minimum=1, maximum=5)
    _validate_int(level, name="level", minimum=1, maximum=90)
    _validate_int(min_rarity, name="min_rarity", minimum=1, maximum=5)
    _validate_int(min_level, name="min_level", minimum=1, maximum=90)
    return rarity >= min_rarity and level >= min_level


def include_echo(
    *,
    rarity: int,
    level: int,
    min_rarity: int,
    min_level: int,
) -> bool:
    _validate_int(rarity, name="rarity", minimum=1, maximum=5)
    _validate_int(level, name="level", minimum=0, maximum=25)
    _validate_int(min_rarity, name="min_rarity", minimum=1, maximum=5)
    _validate_int(min_level, name="min_level", minimum=0, maximum=25)
    return rarity >= min_rarity and level >= min_level
