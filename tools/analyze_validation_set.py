"""Annotate validation screenshots with the repository's current scanner ROIs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from game.diagnostic_rois import ROI_GROUPS
from game.gameROI import Coordinates
from game.screenInfo import ScreenInfo


STATE_ROI_GROUPS = {
    "main-menu": "main-menu",
    "inventory-weapons": "inventory-weapons",
    "inventory-echoes": "inventory-echoes",
    "inventory-development-items": "inventory-items",
    "inventory-resources": "inventory-items",
    "resonator-overview": "resonator-overview",
    "resonator-weapon": "resonator-weapon",
    "resonator-skills": "resonator-skills",
    "resonator-chain": "resonator-chain",
    "achievements": "achievements",
    "shell-credit": "shell-credit",
}


def _resolve_roi(screen_info: ScreenInfo, dotted_path: str) -> Coordinates:
    value = screen_info
    for part in dotted_path.split("."):
        value = getattr(value, part)
    return value


def build_analysis_report(manifest: dict[str, Any]) -> dict[str, Any]:
    """Associate every captured state with the currently configured ROI set."""

    resolution = manifest.get("resolution")
    if resolution != [1920, 1080]:
        raise ValueError("ROI analysis requires a 1920x1080 validation manifest.")
    captures = manifest.get("captures")
    if not isinstance(captures, list):
        raise ValueError("Validation manifest captures must be an array.")

    screen_info = ScreenInfo(1920, 1080)
    report_captures = []
    for capture in captures:
        if not isinstance(capture, dict):
            raise ValueError("Validation capture records must be objects.")
        state = capture.get("state")
        filename = capture.get("filename")
        if not isinstance(state, str) or state not in STATE_ROI_GROUPS:
            raise ValueError(f"No configured ROI group for state {state!r}.")
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or "/" in filename
            or "\\" in filename
            or not filename.lower().endswith(".png")
        ):
            raise ValueError(f"Unsafe or invalid capture filename: {filename!r}.")

        group_name = STATE_ROI_GROUPS[state]
        roi_records = []
        for label, dotted_path in ROI_GROUPS[group_name]:
            roi = _resolve_roi(screen_info, dotted_path)
            x, y, width, height = map(
                int,
                (roi.x, roi.y, roi.w, roi.h),
            )
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid configured ROI dimensions: {dotted_path}")
            roi_records.append(
                {
                    "label": label,
                    "roi": dotted_path,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                }
            )

        report_captures.append(
            {
                "state": state,
                "filename": filename,
                "verified": capture.get("verified") is True,
                "roi_group": group_name,
                "rois": roi_records,
                "annotated_filename": f"annotated/{Path(filename).stem}-rois.png",
                "annotation_status": "pending",
            }
        )

    return {
        "schema_version": 1,
        "source_manifest": "manifest.json",
        "session_status": manifest.get("status", "unknown"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roi_coordinates_are_live_validated": False,
        "note": (
            "These are the currently configured scanner ROIs. This does not "
            "mark live ROI validation complete; their placement is not yet "
            "confirmed against Global 3.6."
        ),
        "captures": report_captures,
        "warnings": [],
    }


def annotate_frame(image, rois: list[dict[str, Any]], cv2_module):
    """Return a marked-up copy, leaving the original screenshot untouched."""

    annotated = image.copy()
    for roi in rois:
        top_left = (roi["x"], roi["y"])
        bottom_right = (
            roi["x"] + roi["width"],
            roi["y"] + roi["height"],
        )
        cv2_module.rectangle(annotated, top_left, bottom_right, (32, 64, 255), 2)
        cv2_module.putText(
            annotated,
            f"{roi['label']} ({roi['roi']})",
            (roi["x"] + 3, max(14, roi["y"] - 4)),
            cv2_module.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2_module.LINE_AA,
        )
    return annotated


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Validation ROI analysis",
        "",
        f"Session status: `{report['session_status']}`",
        "",
        f"> {report['note']}",
        "",
    ]
    for capture in report["captures"]:
        lines.extend(
            [
                f"## {capture['state']}",
                "",
                f"Capture: `{capture['filename']}`; verified: `{str(capture['verified']).lower()}`",
                f"Annotated copy: `{capture['annotated_filename']}` ({capture['annotation_status']})",
                "",
                "| ROI | x | y | width | height |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for roi in capture["rois"]:
            lines.append(
                f"| `{roi['roi']}` | {roi['x']} | {roi['y']} | "
                f"{roi['width']} | {roi['height']} |"
            )
        lines.append("")
    if report["warnings"]:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
        lines.append("")
    return "\n".join(lines)


def _write_report(directory: Path, report: dict[str, Any]) -> None:
    from scraping.exporter import write_json_atomic

    write_json_atomic(directory / "analysis_report.json", report)
    markdown_path = directory / "analysis_report.md"
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")


def analyze_directory(directory: Path | str) -> dict[str, Any]:
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read validation manifest: {manifest_path}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported validation manifest schema.")

    report = build_analysis_report(manifest)
    annotated_dir = directory / "annotated"
    annotated_dir.mkdir(exist_ok=True)

    try:
        import cv2
    except ImportError as exc:
        report["warnings"].append(
            "OpenCV is required to render annotation images; the coordinate report was written."
        )
        _write_report(directory, report)
        raise RuntimeError("OpenCV is required for annotated comparison images.") from exc

    for capture in report["captures"]:
        source_path = directory / capture["filename"]
        image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
        if image is None:
            capture["annotation_status"] = "missing-or-unreadable"
            report["warnings"].append(
                f"Could not read capture image {capture['filename']}."
            )
            continue
        if tuple(image.shape[:2]) != (1080, 1920):
            capture["annotation_status"] = "unexpected-image-dimensions"
            report["warnings"].append(
                f"Capture {capture['filename']} is not 1920x1080."
            )
            continue
        annotated = annotate_frame(image, capture["rois"], cv2)
        output_path = directory / capture["annotated_filename"]
        if not cv2.imwrite(str(output_path), annotated):
            capture["annotation_status"] = "write-failed"
            report["warnings"].append(
                f"Could not write annotated image {capture['annotated_filename']}."
            )
            continue
        capture["annotation_status"] = "written"

    _write_report(directory, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Overlay configured scanner ROI rectangles on a validation "
            "capture set and report their coordinates."
        )
    )
    parser.add_argument("directory", type=Path, help="Validation session directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = analyze_directory(args.directory)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Validation analysis failed: {exc}", file=sys.stderr)
        return 1
    print(f"Annotated screenshots: {args.directory / 'annotated'}")
    print(f"ROI report: {args.directory / 'analysis_report.md'}")
    return 0 if not report["warnings"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
