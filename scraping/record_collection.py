"""Collection helpers that preserve distinct inventory copies."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def append_distinct_copy(records: list[T], record: T) -> None:
    """Append every scanned slot; never deduplicate equal record values."""
    records.append(record)
