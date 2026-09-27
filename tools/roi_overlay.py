"""Display scanner ROIs as a temporary transparent overlay.

This tool never captures or writes game pixels. It is intended for local
calibration before accepting a live scanner layout.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from game.diagnostic_rois import ROI_GROUPS
from game.foreground import WindowManager
from game.roi_debug import overlay_rectangles


class ROIOverlay(QWidget):
    def __init__(self, rectangles: list[dict], geometry: tuple[int, int, int, int]):
        super().__init__()
        self.rectangles = rectangles

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        left, top, right, bottom = geometry
        self.setGeometry(left, top, right - left, bottom - top)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QPen(QColor(255, 64, 64, 220), 2))

        for item in self.rectangles:
            rect = QRect(
                item["x"],
                item["y"],
                item["width"],
                item["height"],
            )
            painter.drawRect(rect)
            painter.fillRect(
                QRect(rect.x(), rect.y(), min(rect.width(), 240), 22),
                QColor(0, 0, 0, 150),
            )
            painter.setPen(QPen(QColor(255, 255, 255, 240), 1))
            painter.drawText(
                rect.x() + 4,
                rect.y() + 16,
                f'{item["label"]} ({item["roi"]})',
            )
            painter.setPen(QPen(QColor(255, 64, 64, 220), 2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Show a temporary scanner ROI overlay without capturing or "
            "saving game pixels."
        )
    )
    parser.add_argument("screen", choices=sorted(ROI_GROUPS))
    parser.add_argument(
        "--seconds",
        type=float,
        default=10.0,
        help="How long to display the overlay (default: 10 seconds).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.seconds <= 0 or args.seconds > 120:
        raise SystemExit("--seconds must be greater than 0 and at most 120.")

    window = WindowManager()
    if window.window is None:
        raise SystemExit("Wuthering Waves window was not found.")

    dpi_scale = window.getDPI()
    if abs(dpi_scale - 1.0) > 0.01:
        raise SystemExit(
            "ROI overlay currently requires 100% Windows display scaling; "
            f"detected {dpi_scale * 100:.0f}%."
        )

    monitor_bounds = window.getMonitorBounds()
    if monitor_bounds is None:
        raise SystemExit("Unable to determine the target monitor bounds.")

    screen_info = window.getScreenInfo()
    rectangles = overlay_rectangles(screen_info, args.screen)

    app = QApplication.instance() or QApplication(sys.argv)
    overlay = ROIOverlay(rectangles, monitor_bounds)
    overlay.show()

    QTimer.singleShot(int(args.seconds * 1000), app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
