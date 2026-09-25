"""Dependency-free validation for scraper subprocess messages."""

from __future__ import annotations

from typing import Any


class ScraperMessageError(ValueError):
    """Raised when a scraper subprocess message is malformed."""


def parse_scraper_message(message: Any) -> tuple[str, Any]:
    if not isinstance(message, dict):
        raise ScraperMessageError("Scanner returned a malformed result message.")

    message_type = message.get("type")

    if message_type == "inventory":
        payload = message.get("inventory")
        if not isinstance(payload, dict):
            raise ScraperMessageError("Scanner returned malformed inventory data.")
        return (message_type, payload)

    if message_type == "failed":
        payload = message.get("failed")
        if not isinstance(payload, list):
            raise ScraperMessageError(
                "Scanner returned malformed recognition-failure data."
            )
        return (message_type, payload)

    if message_type == "error":
        payload = message.get("error")
        if not isinstance(payload, str) or not payload:
            raise ScraperMessageError(
                "Scanner subprocess failed without an error message."
            )
        return (message_type, payload)

    if message_type == "complete":
        return (message_type, None)

    raise ScraperMessageError("Scanner returned an unknown result message.")
