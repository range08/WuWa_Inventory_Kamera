"""Dependency-free fuzzy matching helpers for OCR-visible game names."""

from __future__ import annotations

from difflib import get_close_matches
from typing import Iterable


# Keep thresholds separate even when their initial values match. Real screenshot
# fixtures can tune one field without changing recognition behavior elsewhere.
RESONATOR_NAME_CUTOFF = 0.90
EQUIPPED_WEAPON_NAME_CUTOFF = 0.90
WEAPON_INVENTORY_NAME_CUTOFF = 0.90
ITEM_NAME_CUTOFF = 0.90
ECHO_NAME_CUTOFF = 0.90


def best_match(
    value: str,
    candidates: Iterable[str],
    *,
    cutoff: float,
) -> str | None:
    """Return the best candidate for a value or None when confidence is low."""

    if not 0.0 <= cutoff <= 1.0:
        raise ValueError("cutoff must be between 0.0 and 1.0")

    candidates = tuple(candidates)
    if value in candidates:
        return value

    matches = get_close_matches(value, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None
