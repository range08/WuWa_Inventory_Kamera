"""Logging redaction for credential-like values."""

from __future__ import annotations

import logging
import re


_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b("
    r"oauth[_-]?code|"
    r"access[_-]?token|"
    r"refresh[_-]?token|"
    r"password|passwd|"
    r"client[_-]?secret"
    r")\b(\s*[:=]\s*)([^\s,;]+)"
)
_AUTH_BEARER_PATTERN = re.compile(
    r"(?i)(\bauthorization\b\s*[:=]\s*bearer\s+)[^\s,;]+"
)
_AUTH_VALUE_PATTERN = re.compile(
    r"(?i)(\bauthorization\b\s*[:=]\s*)(?!bearer\b)[^\s,;]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")


def redact_log_text(text: str) -> str:
    """Redact common credential forms without altering ordinary log text."""
    if not isinstance(text, str):
        text = str(text)

    text = _AUTH_BEARER_PATTERN.sub(
        lambda match: f"{match.group(1)}<redacted>",
        text,
    )
    text = _AUTH_VALUE_PATTERN.sub(
        lambda match: f"{match.group(1)}<redacted>",
        text,
    )
    text = _ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>",
        text,
    )
    return _BEARER_PATTERN.sub("Bearer <redacted>", text)


class RedactingFormatter(logging.Formatter):
    """Apply redaction after normal formatting, including exception text."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_log_text(super().format(record))
