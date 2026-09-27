"""Dependency-free parsing helpers for scanner OCR text."""

from __future__ import annotations

import re
from collections.abc import Sequence


class ScanParseError(ValueError):
    """Raised when OCR text cannot be converted into a scanner value."""


def parse_quantity(text: str) -> int:
    """Parse an owned-item quantity while tolerating visual separators."""
    if not isinstance(text, str):
        raise ScanParseError(f"Quantity text must be a string, got {type(text).__name__}")

    digits = re.sub(r"[^0-9]", "", text)
    if not digits:
        raise ScanParseError(f"Quantity contains no digits: {text!r}")
    return int(digits)


def parse_level_pair(text: str) -> tuple[int, int]:
    """Parse a current/max level pair such as 80/90."""
    if not isinstance(text, str):
        raise ScanParseError(f"Level text must be a string, got {type(text).__name__}")

    parts = [part.strip() for part in text.split("/")]
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ScanParseError(f"Invalid level pair: {text!r}")

    current, maximum = map(int, parts)
    if current < 0 or maximum <= 0 or current > maximum:
        raise ScanParseError(f"Invalid level range: {text!r}")
    return current, maximum


def ascension_from_level_cap(maximum: int, caps: Sequence[int]) -> int:
    """Return the ascension index associated with a displayed maximum level."""
    try:
        return tuple(caps).index(maximum)
    except ValueError as exc:
        raise ScanParseError(
            f"Unknown ascension level cap: {maximum!r}"
        ) from exc


def parse_stat_value(text: str) -> tuple[int | float, bool]:
    """Parse an Echo stat value and report whether it is a percentage."""
    if not isinstance(text, str):
        raise ScanParseError(
            f"Stat value must be a string, got {type(text).__name__}"
        )

    normalized = text.strip().replace(",", "").replace(" ", "")
    if not normalized:
        raise ScanParseError("Stat value is empty.")

    is_percentage = normalized.endswith("%")
    numeric = normalized[:-1] if is_percentage else normalized
    if not numeric:
        raise ScanParseError(f"Stat value contains no number: {text!r}")

    try:
        value = float(numeric) if is_percentage else int(numeric)
    except ValueError as exc:
        raise ScanParseError(f"Invalid stat value: {text!r}") from exc

    return value, is_percentage
