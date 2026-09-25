"""Finalize additive scan exports after manual OCR review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scraping.account_export import build_account_export, build_validation_report
from scraping.exporter import write_json_atomic


class ReviewFinalizeError(ValueError):
    """Raised when persisted scan artifacts cannot be finalized safely."""


def _read_json(path: Path, expected_type: type, default: Any = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise ReviewFinalizeError(f"Required scan artifact is missing: {path.name}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewFinalizeError(
            f"Unable to read scan artifact: {path.name}"
        ) from exc

    if not isinstance(payload, expected_type):
        raise ReviewFinalizeError(
            f"Scan artifact has the wrong JSON shape: {path.name}"
        )
    return payload


def refresh_review_exports(
    scan_dir: Path | str,
    *,
    inventory: dict,
    remaining_review_items: int,
) -> dict:
    """Refresh validation/account exports after a manual-review decision."""

    if remaining_review_items < 0:
        raise ReviewFinalizeError("remaining_review_items cannot be negative")

    scan_dir = Path(scan_dir)
    metadata = _read_json(scan_dir / "scan_metadata.json", dict)
    previous_validation = _read_json(
        scan_dir / "validation_report.json",
        dict,
    )
    selected_scanners = previous_validation.get("selected_scanners")
    if (
        not isinstance(selected_scanners, list)
        or not all(isinstance(value, str) for value in selected_scanners)
    ):
        raise ReviewFinalizeError(
            "validation_report.json has invalid selected_scanners."
        )

    characters = _read_json(
        scan_dir / "characters_wuwainventorykamera.json",
        dict,
        default={},
    )
    weapons = _read_json(
        scan_dir / "weapons_wuwainventorykamera.json",
        list,
        default=[],
    )
    echoes = _read_json(
        scan_dir / "echoes_wuwainventorykamera.json",
        list,
        default=[],
    )
    achievements = _read_json(
        scan_dir / "achievements_wuwainventorykamera.json",
        list,
        default=[],
    )

    validation = build_validation_report(
        selected_scanners=selected_scanners,
        inventory=inventory,
        characters=characters,
        weapons=weapons,
        echoes=echoes,
        achievements=achievements,
        failed_count=remaining_review_items,
    )
    write_json_atomic(scan_dir / "validation_report.json", validation)

    account_path = scan_dir / "account.json"
    if remaining_review_items == 0:
        account = build_account_export(
            metadata=metadata,
            validation=validation,
            inventory=inventory,
            characters=characters,
            weapons=weapons,
            echoes=echoes,
            achievements=achievements,
        )
        write_json_atomic(account_path, account)
    else:
        account_path.unlink(missing_ok=True)

    return validation
