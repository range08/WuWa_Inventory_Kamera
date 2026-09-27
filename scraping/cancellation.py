"""Cooperative scanner cancellation helpers."""

from __future__ import annotations

import math
import time
from collections.abc import Callable


class ScanCancelled(RuntimeError):
    """Raised inside a scanner when cooperative cancellation is requested."""


def check_cancelled(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ScanCancelled("Scan cancellation requested.")


def wait_or_cancel(
    cancel_event,
    delay_seconds: float,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Wait for a bounded delay, raising promptly when cancellation is set."""

    if (
        isinstance(delay_seconds, bool)
        or not isinstance(delay_seconds, (int, float))
        or not math.isfinite(delay_seconds)
        or delay_seconds < 0
    ):
        raise ValueError("delay_seconds must be a finite non-negative number.")

    if delay_seconds == 0:
        return

    if cancel_event is None:
        sleeper(delay_seconds)
        return

    check_cancelled(cancel_event)
    cancel_event.wait(delay_seconds)
    check_cancelled(cancel_event)
