"""Privacy-minimized OCR review artifact helpers."""

from __future__ import annotations

from pathlib import Path

from scraping.exporter import write_json_atomic
from scraping.ocr_engine import OCRResult


def write_review_metadata(
    path: Path | str,
    *,
    scanner: str,
    reason: str,
    fingerprint: str,
    crop_file: str,
    ocr_result: OCRResult,
    owned: int | None,
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
