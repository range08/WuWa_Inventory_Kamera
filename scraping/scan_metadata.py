"""Build non-breaking metadata for completed scanner exports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from version import __version__


class ScanMetadataError(ValueError):
    """Raised when generated game-data metadata cannot be read safely."""


def build_scan_metadata(
    mapping_manifest_path: Path | str,
    *,
    scan_time: str | None = None,
) -> dict[str, Any]:
    """Return metadata stored beside, not inside, legacy export files."""
    path = Path(mapping_manifest_path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ScanMetadataError(
            f"Unable to read mapping manifest: {path}"
        ) from exc

    if not isinstance(manifest, dict):
        raise ScanMetadataError("Mapping manifest must be a JSON object.")

    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ScanMetadataError("Mapping manifest is missing source metadata.")

    required = (
        "repository",
        "ref",
        "revision",
        "game_version",
        "resource_version",
        "changelist",
        "language",
    )
    normalized_source: dict[str, str] = {}
    for field in required:
        value = source.get(field)
        if not isinstance(value, str) or not value:
            raise ScanMetadataError(
                f"Mapping manifest contains invalid source field: {field}"
            )
        normalized_source[field] = value

    if scan_time is None:
        scan_time = datetime.now(timezone.utc).isoformat()
    if not isinstance(scan_time, str) or not scan_time:
        raise ScanMetadataError("scan_time must be a non-empty string.")

    return {
        "schema_version": 1,
        "scanner_version": __version__,
        "scan_time": scan_time,
        "game_data": normalized_source,
    }
