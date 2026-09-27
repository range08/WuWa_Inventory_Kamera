"""Scanner layout safety policy.

The current scanner coordinates are monitor-relative. Until client-area offsets
and DPI-aware coordinate transforms are implemented, only layouts that exactly
match an explicit ROI profile are safe to automate.
"""

from __future__ import annotations

from typing import Iterable

Bounds = tuple[int, int, int, int]
Resolution = tuple[int, int]


def validate_scanner_layout(
    *,
    client_bounds: Bounds,
    monitor_bounds: Bounds,
    dpi_scale: float,
    supported_resolutions: Iterable[Resolution],
) -> str | None:
    """Return a user-facing error when the current layout is unsafe."""

    if dpi_scale <= 0:
        return "Unable to determine the game window DPI scale."

    if abs(dpi_scale - 1.0) > 0.01:
        return (
            "Scanner currently requires 100% Windows display scaling. "
            f"Detected {dpi_scale * 100:.0f}%."
        )

    client_left, client_top, client_right, client_bottom = client_bounds
    monitor_left, monitor_top, monitor_right, monitor_bottom = monitor_bounds

    if (
        client_left != monitor_left
        or client_top != monitor_top
        or client_right != monitor_right
        or client_bottom != monitor_bottom
    ):
        return (
            "Scanner currently requires the Wuthering Waves client area to "
            "fill the entire target monitor."
        )

    width = client_right - client_left
    height = client_bottom - client_top
    supported = set(supported_resolutions)
    if (width, height) not in supported:
        formatted = ", ".join(
            f"{supported_width}x{supported_height}"
            for supported_width, supported_height in sorted(supported)
        )
        return (
            f"Unsupported scanner resolution: {width}x{height}. "
            f"Explicit ROI profiles: {formatted}."
        )

    return None
