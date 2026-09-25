"""Small bounded retry helper for transient scanner reads."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_call(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    delay_seconds: float = 0.15,
    retry_on: tuple[type[BaseException], ...] = (ValueError,),
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    """Run an operation with a bounded retry count and re-raise the last error."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")
    if not retry_on:
        raise ValueError("retry_on cannot be empty")

    last_error: BaseException | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except retry_on as exc:
            last_error = exc
            if attempt + 1 < attempts:
                sleeper(delay_seconds)

    assert last_error is not None
    raise last_error
