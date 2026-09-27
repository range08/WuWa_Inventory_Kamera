"""Dependency-free game-window selection and activation policy helpers."""

from __future__ import annotations

import math
import ntpath
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class WindowCandidate:
    """Facts collected from one visible top-level window."""

    hwnd: int
    process_name: str
    title: str
    visible: bool
    width: int
    height: int
    owned: bool = False
    tool_window: bool = False

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)


def select_game_window(
    candidates: list[WindowCandidate] | tuple[WindowCandidate, ...],
    *,
    process_name: str,
    title_hint: str | None = None,
) -> WindowCandidate | None:
    """Choose the largest visible unowned window from the exact game process.

    The executable name is the identity check. A localized or changed window
    title is only a tie-breaker when that process owns multiple main-sized
    top-level windows.
    """

    expected_process = ntpath.basename(process_name).strip().casefold()
    if not expected_process:
        raise ValueError("process_name must identify an executable.")

    title_hint = title_hint.strip().casefold() if title_hint else ""
    eligible = [
        candidate
        for candidate in candidates
        if candidate.visible
        and not candidate.owned
        and not candidate.tool_window
        and candidate.area > 0
        and isinstance(candidate.process_name, str)
        and ntpath.basename(candidate.process_name).strip().casefold()
        == expected_process
    ]
    if not eligible:
        return None

    return max(
        eligible,
        key=lambda candidate: (
            candidate.area,
            bool(
                title_hint
                and isinstance(candidate.title, str)
                and title_hint in candidate.title.casefold()
            ),
            bool(isinstance(candidate.title, str) and candidate.title.strip()),
            -candidate.hwnd,
        ),
    )


def activate_and_verify(
    activate: Callable[[], object],
    is_foreground: Callable[[], bool],
    *,
    attempts: int = 10,
    delay_seconds: float = 0.05,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[bool, str | None]:
    """Request ordinary window activation and verify the foreground result.

    A failed activation call is not treated as proof of failure; the actual
    foreground window is checked for a bounded period before returning.
    """

    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ValueError("attempts must be a positive integer.")
    if not math.isfinite(delay_seconds) or delay_seconds < 0:
        raise ValueError("delay_seconds must be finite and non-negative.")

    activation_error = None
    try:
        activate()
    except Exception as exc:  # The foreground check remains authoritative.
        activation_error = f"Activation request failed: {type(exc).__name__}: {exc}"

    for attempt in range(attempts):
        try:
            if is_foreground():
                return True, None
        except Exception as exc:
            return (
                False,
                f"Unable to verify foreground window: {type(exc).__name__}: {exc}",
            )

        if attempt + 1 < attempts and delay_seconds:
            sleeper(delay_seconds)

    reason = "The game window did not become the foreground window."
    if activation_error:
        reason = f"{reason} {activation_error}"
    return False, reason
