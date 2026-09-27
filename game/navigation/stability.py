"""Bounded, cooperative waiting for a visually stable game frame."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from scraping.cancellation import check_cancelled, wait_or_cancel


@dataclass(frozen=True)
class FrameSignature:
    shape: tuple[int, ...]
    sample: bytes


class StabilityTimeout(TimeoutError):
    """Raised when frames keep changing until the stability deadline."""

    def __init__(self, message: str, last_frame: Any = None) -> None:
        super().__init__(message)
        self.last_frame = last_frame


def frame_signature(frame: Any, *, stride: int = 16) -> FrameSignature:
    """Sample a frame sparsely so animations do not require full-frame hashing."""

    if isinstance(stride, bool) or not isinstance(stride, int) or stride < 1:
        raise ValueError("stride must be a positive integer.")
    shape = getattr(frame, "shape", None)
    if not isinstance(shape, tuple) or not shape:
        raise ValueError("frame must expose an array-like shape.")
    sampled = frame[::stride, ::stride]
    to_bytes = getattr(sampled, "tobytes", None)
    if not callable(to_bytes):
        raise ValueError("frame samples must expose tobytes().")
    return FrameSignature(tuple(int(value) for value in shape), to_bytes())


def signatures_are_stable(
    left: FrameSignature,
    right: FrameSignature,
    *,
    max_changed_fraction: float = 0.015,
    max_mean_delta: float = 2.0,
    changed_channel_threshold: int = 8,
) -> bool:
    """Treat small, sparse animation changes as stable while rejecting motion."""

    if left.shape != right.shape or len(left.sample) != len(right.sample):
        return False
    if not math.isfinite(max_changed_fraction) or not 0 <= max_changed_fraction <= 1:
        raise ValueError("max_changed_fraction must be between 0 and 1.")
    if not math.isfinite(max_mean_delta) or max_mean_delta < 0:
        raise ValueError("max_mean_delta must be finite and non-negative.")
    if changed_channel_threshold < 0:
        raise ValueError("changed_channel_threshold cannot be negative.")
    if not left.sample:
        return True

    total_delta = 0
    changed = 0
    for first, second in zip(left.sample, right.sample):
        delta = abs(first - second)
        total_delta += delta
        if delta > changed_channel_threshold:
            changed += 1
    return (
        changed / len(left.sample) <= max_changed_fraction
        and total_delta / len(left.sample) <= max_mean_delta
    )


def wait_until_stable(
    capture_frame: Callable[[], Any],
    *,
    cancel_event=None,
    timeout_seconds: float = 12.0,
    poll_seconds: float = 0.25,
    stable_intervals: int = 3,
    stride: int = 16,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> Any:
    """Return a stable frame or fail within a fixed deadline.

    No UI action is retried here. Callers can retry the visual state detector
    against fresh stable frames without repeating an uncertain click or key.
    """

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive.")
    if not math.isfinite(poll_seconds) or poll_seconds <= 0:
        raise ValueError("poll_seconds must be finite and positive.")
    if (
        isinstance(stable_intervals, bool)
        or not isinstance(stable_intervals, int)
        or stable_intervals < 1
    ):
        raise ValueError("stable_intervals must be a positive integer.")

    check_cancelled(cancel_event)
    started = monotonic()
    max_samples = math.ceil(timeout_seconds / poll_seconds) + 2
    previous_signature: FrameSignature | None = None
    stable_count = 0
    last_frame = None

    for sample_index in range(max_samples):
        check_cancelled(cancel_event)
        last_frame = capture_frame()
        check_cancelled(cancel_event)
        current_signature = frame_signature(last_frame, stride=stride)
        if previous_signature is not None and signatures_are_stable(
            previous_signature,
            current_signature,
        ):
            stable_count += 1
            if stable_count >= stable_intervals:
                return last_frame
        else:
            stable_count = 0
        previous_signature = current_signature

        remaining = timeout_seconds - (monotonic() - started)
        if remaining <= 0 or sample_index + 1 >= max_samples:
            break
        delay = min(poll_seconds, remaining)
        if cancel_event is None:
            sleeper(delay)
        else:
            wait_or_cancel(cancel_event, delay)

    raise StabilityTimeout(
        f"Game screen did not stabilize within {timeout_seconds:.1f} seconds.",
        last_frame=last_frame,
    )
