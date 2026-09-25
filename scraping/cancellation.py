"""Cooperative scanner cancellation helpers."""

from __future__ import annotations


class ScanCancelled(RuntimeError):
    """Raised inside a scanner when cooperative cancellation is requested."""


def check_cancelled(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ScanCancelled("Scan cancellation requested.")
