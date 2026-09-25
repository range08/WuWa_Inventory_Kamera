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
