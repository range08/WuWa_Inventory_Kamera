"""Dependency-free validation capture manifest and path helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from game.navigation.state import NavigationResult, StateObservation
from game.navigation.transitions import CAPTURE_PLAN, CaptureSpec


def iso_timestamp(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def allocate_session_directory(
    output_root: Path | str,
    *,
    started_at: datetime | None = None,
) -> Path:
    """Create a new timestamped directory without ever reusing an existing one."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = started_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    stem = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

    for suffix in range(1000):
        name = stem if suffix == 0 else f"{stem}-{suffix:02d}"
        target = root / name
        try:
            target.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        return target
    raise FileExistsError(
        f"Too many validation sessions already exist for timestamp {stem}."
    )


def build_manifest(
    *,
    game_data_ref: str | None,
    game_version: str | None,
    resource_version: str | None,
    scanner_version: str,
    resolution: tuple[int, int] | list[int] | None = None,
    dpi_scale: float | None = None,
    client_bounds: tuple[int, int, int, int] | list[int] | None = None,
    monitor_bounds: tuple[int, int, int, int] | list[int] | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "game_data_ref": game_data_ref,
        "game_data_language": None,
        "game_version": game_version,
        "resource_version": resource_version,
        "scanner_version": scanner_version,
        "resolution": list(resolution) if resolution is not None else [],
        "dpi_scale": dpi_scale,
        "client_bounds": list(client_bounds) if client_bounds is not None else [],
        "monitor_bounds": list(monitor_bounds) if monitor_bounds is not None else [],
        "started_at": started_at or iso_timestamp(),
        "completed_at": None,
        "status": "running",
        "captures": [],
        "failed_transition": None,
        "privacy_warning": (
            "Full client captures may show a UID or account details. "
            "Review locally before sharing; validation images are not "
            "automatically anonymized."
        ),
    }


def transition_description(spec: CaptureSpec) -> str:
    if not spec.transitions:
        return "initial state verification"
    return " then ".join(item.description for item in spec.transitions)


def failed_capture_filename(
    spec: CaptureSpec,
    *,
    prefix: str = "FAILED",
) -> str:
    if not prefix or not prefix.replace("-", "").isalnum():
        raise ValueError("Diagnostic filename prefix must be alphanumeric.")
    return f"{prefix}-{spec.order:02d}-{spec.state_name}.png"


def build_capture_record(
    spec: CaptureSpec,
    result: NavigationResult,
    *,
    captured_at: str | None = None,
    filename: str | None = None,
    verified: bool | None = None,
) -> dict[str, Any]:
    return {
        "state": spec.state_name,
        "filename": filename or spec.filename,
        "transition": transition_description(spec),
        "timestamp": captured_at or iso_timestamp(),
        "verified": result.observation.verified if verified is None else verified,
        "verification": result.observation.as_dict(),
    }


def finalize_manifest(
    manifest: dict[str, Any],
    *,
    status: str,
    completed_at: str | None = None,
    failed_transition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in {"complete", "failed", "cancelled"}:
        raise ValueError("Manifest status must be complete, failed, or cancelled.")
    if status == "complete":
        captures = manifest.get("captures", [])
        expected = [(item.state_name, item.filename) for item in CAPTURE_PLAN]
        actual = [
            (item.get("state"), item.get("filename"))
            for item in captures
            if isinstance(item, dict)
        ]
        if len(captures) != len(CAPTURE_PLAN) or actual != expected:
            raise ValueError(
                "A complete validation manifest requires the ordered 11-screen capture plan."
            )
        if any(item.get("verified") is not True for item in captures):
            raise ValueError(
                "A complete validation manifest cannot contain unverified captures."
            )
    result = dict(manifest)
    result["completed_at"] = completed_at or iso_timestamp()
    result["status"] = status
    if failed_transition is not None or status == "complete":
        result["failed_transition"] = failed_transition
    else:
        result["failed_transition"] = result.get("failed_transition")
    return result


def failure_details(
    *,
    source: str | None,
    destination: str,
    action: str | None,
    reason: str,
    attempts: int,
    diagnostic_capture: str | None,
    verification: StateObservation | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "destination": destination,
        "action": action,
        "reason": reason,
        "attempts": attempts,
        "diagnostic_capture": diagnostic_capture,
        "verification": verification.as_dict() if verification is not None else None,
    }
