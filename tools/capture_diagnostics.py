"""Capture privacy-minimized scanner ROI diagnostics without sending input.

Open Wuthering Waves to the requested screen first, then run this module.
Only named scanner regions are saved; no full-screen screenshot is written.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import cv2

from game.diagnostic_rois import ROI_GROUPS
from game.foreground import WindowManager
from scraping.exporter import write_json_atomic
from scraping.utils import screenshot



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Capture scanner ROI crops for calibration without clicking or "
            "saving a full-screen screenshot."
        )
    )
    parser.add_argument(
        "screen",
        choices=sorted(ROI_GROUPS),
        help="The game screen currently open.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("logs") / "diagnostics",
        help="Root directory for diagnostic captures.",
    )
    return parser


def resolve_roi(screen_info, dotted_path: str):
    value = screen_info
    for part in dotted_path.split("."):
        value = getattr(value, part)
    return value


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    window = WindowManager()
    if window.window is None:
        raise SystemExit("Wuthering Waves window was not found.")

    screen_info = window.getScreenInfo()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_dir = args.output_dir / f"{timestamp}-{args.screen}"
    target_dir.mkdir(parents=True, exist_ok=False)

    crops = {}
    for label, roi_path in ROI_GROUPS[args.screen]:
        roi = resolve_roi(screen_info, roi_path)
        x, y, width, height = map(int, (roi.x, roi.y, roi.w, roi.h))
        if width <= 0 or height <= 0:
            raise SystemExit(f"Invalid ROI size for {roi_path}: {width}x{height}")

        image = screenshot(
            left=x,
            top=y,
            width=width,
            height=height,
            monitor=screen_info.monitor,
        )
        file_name = f"{label}.png"
        output_path = target_dir / file_name
        if not cv2.imwrite(
            str(output_path),
            cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
        ):
            raise SystemExit(f"Failed to write diagnostic image: {output_path}")

        crops[label] = {
            "roi": roi_path,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "file": file_name,
        }

    manifest = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "screen": args.screen,
        "resolution": [screen_info.width, screen_info.height],
        "monitor": screen_info.monitor,
        "dpi_scale": window.getDPI(),
        "client_bounds": window.getClientBounds(),
        "monitor_bounds": window.getMonitorBounds(),
        "layout_warning": window.getScannerLayoutError(),
        "privacy": {
            "full_screen_saved": False,
            "only_named_scanner_rois_saved": True,
        },
        "crops": crops,
    }
    write_json_atomic(target_dir / "manifest.json", manifest)

    print(f"Diagnostic capture written to: {target_dir}")
    if manifest["layout_warning"]:
        print(f"Layout warning: {manifest['layout_warning']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
