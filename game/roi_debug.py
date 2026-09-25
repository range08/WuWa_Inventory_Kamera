"""Pure helpers for scanner ROI calibration overlays."""

from __future__ import annotations

from typing import Any

from tools.capture_diagnostics import ROI_GROUPS


def resolve_dotted_attribute(root: Any, dotted_path: str) -> Any:
    value = root
    for part in dotted_path.split("."):
        value = getattr(value, part)
    return value


def overlay_rectangles(screen_info: Any, screen: str) -> list[dict]:
    """Return labeled scanner rectangles without capturing any pixels."""
    try:
        regions = ROI_GROUPS[screen]
    except KeyError as exc:
        raise ValueError(f"Unknown diagnostic screen: {screen}") from exc

    rectangles = []
    for label, roi_path in regions:
        roi = resolve_dotted_attribute(screen_info, roi_path)
        x, y, width, height = map(
            int,
            (roi.x, roi.y, roi.w, roi.h),
        )
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Invalid ROI size for {roi_path}: {width}x{height}"
            )
        rectangles.append({
            "label": label,
            "roi": roi_path,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        })
    return rectangles
