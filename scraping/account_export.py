"""Non-breaking aggregate and validation exports."""

from __future__ import annotations

from typing import Any


def build_validation_report(
    *,
    selected_scanners: list[str],
    inventory: dict,
    characters: dict,
    weapons: list,
    echoes: list,
    achievements: list,
    failed_count: int,
) -> dict[str, Any]:
    if failed_count < 0:
        raise ValueError("failed_count cannot be negative")

    return {
        "schema_version": 1,
        "status": "ok" if failed_count == 0 else "needs_review",
        "selected_scanners": list(selected_scanners),
        "counts": {
            "inventory_entries": len(inventory),
            "characters": len(characters),
            "weapons": len(weapons),
            "echoes": len(echoes),
            "achievements": len(achievements),
            "manual_review_items": failed_count,
        },
    }


def build_account_export(
    *,
    metadata: dict,
    validation: dict,
    inventory: dict,
    characters: dict,
    weapons: list,
    echoes: list,
    achievements: list,
) -> dict[str, Any]:
    if validation.get("status") != "ok":
        raise ValueError(
            "Aggregate account export requires a scan with no pending review."
        )

    return {
        "schema_version": 1,
        "metadata": metadata,
        "validation": validation,
        "inventory": dict(inventory),
        "characters": dict(characters),
        "weapons": list(weapons),
        "echoes": list(echoes),
        "achievements": list(achievements),
    }
