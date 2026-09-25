"""Privacy-minimized OCR review artifact helpers."""

from __future__ import annotations

from pathlib import Path

from scraping.exporter import write_json_atomic
from scraping.ocr_engine import OCRResult


DEFAULT_REVIEW_CONFIDENCE = 0.75


def review_reasons(
    *,
    recognized: bool,
    quantity_valid: bool,
    confidence: float,
    min_confidence: float = DEFAULT_REVIEW_CONFIDENCE,
) -> tuple[str, ...]:
    """Return fail-closed reasons that require manual item review."""
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0.0 and 1.0")

    reasons: list[str] = []
    if not recognized:
        reasons.append("unknown_name")
    if not quantity_valid:
        reasons.append("invalid_quantity")
    if confidence < min_confidence:
        reasons.append("low_confidence")
    return tuple(reasons)


def write_review_metadata(
    path: Path | str,
    *,
    scanner: str,
    reason: str,
    fingerprint: str,
    crop_file: str,
    ocr_result: OCRResult,
    owned: int | None,
    candidate: str | None = None,
) -> None:
    """Write metadata beside a failed OCR crop without account identifiers."""
    if not scanner or not reason or not fingerprint or not crop_file:
        raise ValueError("Review metadata fields must be non-empty.")

    payload = {
        "schema_version": 1,
        "scanner": scanner,
        "reason": reason,
        "fingerprint": fingerprint,
        "crop_file": crop_file,
        "owned": owned,
        "candidate": candidate,
        "ocr": {
            "text": ocr_result.text,
            "confidence": ocr_result.confidence,
            "profile": ocr_result.profile,
            "token_count": len(ocr_result.tokens),
        },
        "privacy": {
            "full_screen_saved": False,
            "account_identifier_region_saved": False,
        },
    }
    write_json_atomic(path, payload)
