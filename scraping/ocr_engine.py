"""Structured OCR adapter for scanner text recognition.

The RapidOCR dependency is loaded lazily so this module can be unit-tested
without installing the Windows/UI runtime dependency set.
"""

from __future__ import annotations

import re
import string
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class OCRProfile:
    name: str
    divisor: str = " "
    allowed_chars: str | None = None
    banned_chars: str | None = None
    unicode_form: str = "NFKC"


@dataclass(frozen=True)
class OCRToken:
    bbox: tuple[tuple[float, float], ...]
    text: str
    confidence: float


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float
    tokens: tuple[OCRToken, ...]
    profile: str

    @classmethod
    def empty(cls, profile: str) -> "OCRResult":
        return cls(text="", confidence=0.0, tokens=(), profile=profile)


class OCRError(RuntimeError):
    """Raised when the OCR backend returns an unusable result."""


NAME_PROFILE = OCRProfile(
    name="name",
    divisor="",
    banned_chars=" ",
)
INTEGER_PROFILE = OCRProfile(
    name="integer",
    divisor="",
    allowed_chars=string.digits,
)
LEVEL_PROFILE = OCRProfile(
    name="level",
    divisor="",
    allowed_chars=string.digits + "/",
)
PERCENTAGE_PROFILE = OCRProfile(
    name="percentage",
    divisor="",
    allowed_chars=string.digits + ".%",
)
STAT_NAME_PROFILE = OCRProfile(
    name="stat-name",
    divisor="",
    banned_chars=" .",
)
STAT_VALUE_PROFILE = OCRProfile(
    name="stat-value",
    divisor=" ",
    allowed_chars=string.digits + ".%",
)
KOREAN_TEXT_PROFILE = OCRProfile(
    name="korean-text",
)


class OCREngine:
    def __init__(self, backend: Callable[[Any], Any] | None = None) -> None:
        self._backend = backend

    def _get_backend(self) -> Callable[[Any], Any]:
        if self._backend is None:
            try:
                from rapidocr import RapidOCR
            except ImportError:
                # Compatibility fallback for existing development environments.
                # New installs use the unified rapidocr package.
                from rapidocr_onnxruntime import RapidOCR

            self._backend = RapidOCR()
        return self._backend

    def recognize(
        self,
        image: Any,
        profile: OCRProfile,
    ) -> OCRResult:
        try:
            raw = self._get_backend()(image)
        except Exception as exc:
            raise OCRError("OCR backend failed") from exc

        entries = self._extract_entries(raw)
        banned_pattern = (
            re.compile(f"[{re.escape(profile.banned_chars)}]")
            if profile.banned_chars
            else None
        )
        allowed_pattern = (
            re.compile(f"[^{re.escape(profile.allowed_chars)}]")
            if profile.allowed_chars
            else None
        )

        tokens: list[OCRToken] = []
        for entry in entries:
            if not isinstance(entry, (list, tuple)) or len(entry) < 3:
                raise OCRError("OCR backend returned a malformed token")

            bbox_raw, text_raw, confidence_raw = entry[:3]
            if not isinstance(text_raw, str):
                raise OCRError("OCR token text is not a string")

            try:
                confidence = float(confidence_raw)
            except (TypeError, ValueError) as exc:
                raise OCRError("OCR token confidence is invalid") from exc

            text = unicodedata.normalize(profile.unicode_form, text_raw)
            if banned_pattern:
                text = banned_pattern.sub("", text)
            if allowed_pattern:
                text = allowed_pattern.sub("", text)

            if not text:
                continue

            bbox = self._normalize_bbox(bbox_raw)
            tokens.append(
                OCRToken(
                    bbox=bbox,
                    text=text,
                    confidence=confidence,
                )
            )

        if not tokens:
            return OCRResult.empty(profile.name)

        text = self._group_text(tokens, profile.divisor)
        confidence = sum(token.confidence for token in tokens) / len(tokens)
        return OCRResult(
            text=text,
            confidence=confidence,
            tokens=tuple(tokens),
            profile=profile.name,
        )

    @staticmethod
    def _extract_entries(raw: Any) -> list[Any]:
        if raw is None:
            return []

        # rapidocr >= 3 returns a RapidOCROutput dataclass with parallel
        # boxes/txts/scores fields rather than the legacy (results, elapsed)
        # envelope used by rapidocr_onnxruntime.
        if all(hasattr(raw, field) for field in ("boxes", "txts", "scores")):
            boxes = OCREngine._to_sequence(raw.boxes)
            texts = OCREngine._to_sequence(raw.txts)
            scores = OCREngine._to_sequence(raw.scores)

            if boxes is None and texts is None and scores is None:
                return []
            if boxes is None or texts is None or scores is None:
                raise OCRError("RapidOCR output is missing boxes, texts, or scores")
            if not (len(boxes) == len(texts) == len(scores)):
                raise OCRError("RapidOCR output fields have mismatched lengths")

            return [
                [bbox, text, confidence]
                for bbox, text, confidence in zip(boxes, texts, scores)
            ]

        if isinstance(raw, tuple):
            entries = raw[0]
        elif (
            isinstance(raw, list)
            and len(raw) == 2
            and isinstance(raw[0], list)
            and isinstance(raw[1], (int, float))
        ):
            # Some adapters may expose RapidOCR's (results, elapsed) as a list.
            entries = raw[0]
        else:
            entries = raw

        if entries is None:
            return []
        if not isinstance(entries, list):
            raise OCRError("OCR backend returned an unexpected result shape")
        return entries

    @staticmethod
    def _to_sequence(value: Any) -> list[Any] | None:
        if value is None:
            return None
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            return list(value)
        raise OCRError("RapidOCR output field is not a sequence")

    @staticmethod
    def _normalize_bbox(raw_bbox: Any) -> tuple[tuple[float, float], ...]:
        if hasattr(raw_bbox, "tolist"):
            raw_bbox = raw_bbox.tolist()
        if not isinstance(raw_bbox, (list, tuple)) or not raw_bbox:
            raise OCRError("OCR token bounding box is invalid")

        points: list[tuple[float, float]] = []
        for point in raw_bbox:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise OCRError("OCR token bounding box point is invalid")
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError) as exc:
                raise OCRError("OCR token bounding box coordinate is invalid") from exc
        return tuple(points)

    @staticmethod
    def _group_text(tokens: list[OCRToken], divisor: str) -> str:
        grouped_lines: list[list[str]] = []
        current_row: list[str] = []
        last_y: float | None = None

        for token in tokens:
            y_min = min(point[1] for point in token.bbox)
            y_max = max(point[1] for point in token.bbox)

            if last_y is None or y_min < last_y + 10:
                current_row.append(token.text)
            else:
                grouped_lines.append(current_row)
                current_row = [token.text]

            last_y = y_max

        if current_row:
            grouped_lines.append(current_row)

        return "\n".join(divisor.join(row) for row in grouped_lines).strip()
