"""Automatically navigate and capture the Global 3.6 validation screens.

Run on Windows with Wuthering Waves at the ESC Terminal menu. This tool saves
full 1920x1080 client captures for local calibration; review them before
sharing because the game UI can display account identifiers.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from game.navigation.manifest import (
    allocate_session_directory,
    build_capture_record,
    build_manifest,
    failed_capture_filename,
    failure_details,
    finalize_manifest,
    iso_timestamp,
    transition_description,
)
from game.navigation.navigator import Navigator
from game.navigation.stability import wait_until_stable
from game.navigation.state import GameState, StateObservation
from game.navigation.transitions import CAPTURE_PLAN, CaptureSpec
from game.navigation.validation_detectors import ValidationStateDetector, resolve_roi


SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
GAME_VERSION_PREFIX = "3.6"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Navigate the supported 1920x1080 Wuthering Waves UI and create "
            "a local validation screenshot set."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("logs") / "validation",
        help="Root directory for timestamped validation sessions.",
    )
    return parser


def _load_game_data_metadata(data_dir: Path) -> dict[str, str]:
    from scraping.data_store import reload_generated_mappings

    manifest_path = data_dir / "mapping_manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Validated generated game mappings are missing. Run the existing "
            "game-data setup before validation capture."
        ) from exc

    source = payload.get("source") if isinstance(payload, dict) else None
    if not isinstance(source, dict):
        raise RuntimeError("The game-data mapping manifest has no source metadata.")

    required = (
        "ref",
        "game_version",
        "resource_version",
        "repository",
        "language",
    )
    result: dict[str, str] = {}
    for field in required:
        value = source.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(
                f"The game-data mapping manifest has no valid {field!r}."
            )
        result[field] = value.strip()

    if not result["game_version"].startswith(GAME_VERSION_PREFIX):
        raise RuntimeError(
            "Validation capture is pinned to Global 3.6 data; generated "
            f"mappings report game version {result['game_version']!r}."
        )
    if result["repository"].lower() != "arikatsu/wutheringwaves_data":
        raise RuntimeError(
            "Validation capture requires mappings from the verified Global "
            f"data source, found {result['repository']!r}."
        )

    reload_generated_mappings(data_dir)
    return result


def _map_capture_action(action: str, *, controller, screen_info, config, cancel_event) -> None:
    if action == "open_inventory":
        controller.pressKey(
            config.get(config.inventoryKeybind),
            waitTime=0,
            cancel_event=cancel_event,
        )
        return
    if action == "open_resonator":
        controller.pressKey(
            config.get(config.resonatorKeybind),
            waitTime=0,
            cancel_event=cancel_event,
        )
        return
    if action == "escape":
        controller.pressKey("esc", waitTime=0, cancel_event=cancel_event)
        return
    if action == "hover_echo_details":
        point = screen_info.echoes.mouseMovement
        controller.moveMouse(point.x, point.y, 0.1)
        return

    if action in {
        "select_weapons",
        "select_echoes",
        "select_development_items",
        "select_resources",
    }:
        category = {
            "select_weapons": "weapons",
            "select_echoes": "echoes",
            "select_development_items": "devItems",
            "select_resources": "resources",
        }[action]
        point = getattr(screen_info.scrapers, category)
        controller.leftClick(point.x, point.y, 0.1)
        return

    if action in {
        "select_resonator_weapon",
        "select_resonator_skills",
        "select_resonator_chain",
    }:
        section = {
            "select_resonator_weapon": 1,
            "select_resonator_skills": 3,
            "select_resonator_chain": 4,
        }[action]
        point = screen_info.characters.leftSide
        offset = screen_info.characters.offsets.leftSide.y
        controller.leftClick(point.x, point.y + offset * section, 0.1)
        return

    if action == "select_resonator_skill_detail":
        point = screen_info.characters.skillClick
        controller.leftClick(point.x, point.y, 0.1)
        return
    if action == "open_achievements":
        point = screen_info.achievements.achievementsButton
        controller.leftClick(point.x, point.y, 0.1)
        return
    if action == "select_achievements_tab":
        point = screen_info.achievements.achievementsTab
        controller.leftClick(point.x, point.y, 0.1)
        return
    raise ValueError(f"Unknown validation navigation action: {action}")


def _save_full_frame(cv2, frame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)):
        raise OSError(f"Unable to write validation capture: {output_path}")


def _strict_layout_error(window, screen_info) -> str | None:
    warning = window.getScannerLayoutError()
    if warning:
        return warning
    if abs(window.getDPI() - 1.0) > 0.01:
        return "Validation capture requires 100% Windows display scaling."
    client_bounds = window.getClientBounds()
    monitor_bounds = window.getMonitorBounds()
    if client_bounds is None or monitor_bounds is None:
        return "Unable to determine game client and monitor bounds."
    if client_bounds != monitor_bounds:
        return "The Wuthering Waves client must fill the target monitor."
    width = client_bounds[2] - client_bounds[0]
    height = client_bounds[3] - client_bounds[1]
    if (width, height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
        return "Validation capture requires a 1920x1080 client area."
    if (screen_info.width, screen_info.height) != (SCREEN_WIDTH, SCREEN_HEIGHT):
        return "No exact 1920x1080 scanner coordinate profile is active."
    return None


def _run_windows(output_root: Path) -> int:
    import cv2

    from game.foreground import WindowManager
    from game.screenInfo import ScreenInfo
    from game.stopKey import KeyPressChecker
    from properties.config import cfg
    from scraping.cancellation import ScanCancelled, check_cancelled
    from scraping.exporter import write_json_atomic
    from scraping.utils import WindowsInputController, screenshot
    from version import __version__

    started = datetime.now(timezone.utc)
    session_dir = allocate_session_directory(output_root, started_at=started)
    manifest = build_manifest(
        game_data_ref=None,
        game_version=None,
        resource_version=None,
        scanner_version=__version__,
        started_at=iso_timestamp(started),
    )
    manifest_path = session_dir / "manifest.json"
    write_json_atomic(manifest_path, manifest)

    window = None
    controller = None
    navigator = None
    cancel_event = threading.Event()
    monitor_stop = threading.Event()
    monitor_thread = None
    current_capture = CAPTURE_PLAN[0]
    failure: dict[str, Any] | None = None
    status = "failed"
    cleanup_attempted = False
    cleanup_succeeded: bool | None = None

    def write_manifest() -> None:
        write_json_atomic(manifest_path, manifest)

    try:
        window = WindowManager()
        if window.window is None:
            raise RuntimeError("Wuthering Waves window was not found.")

        dpi_scale = float(window.getDPI())
        client_bounds = window.getClientBounds()
        monitor_bounds = window.getMonitorBounds()
        if client_bounds is not None and monitor_bounds is not None:
            width = client_bounds[2] - client_bounds[0]
            height = client_bounds[3] - client_bounds[1]
            screen_info = ScreenInfo(width, height, window.getScreenInfo().monitor)
            manifest.update(
                {
                    "resolution": [width, height],
                    "dpi_scale": dpi_scale,
                    "client_bounds": list(client_bounds),
                    "monitor_bounds": list(monitor_bounds),
                }
            )
        else:
            screen_info = window.getScreenInfo()
            manifest["dpi_scale"] = dpi_scale
        write_manifest()

        layout_error = _strict_layout_error(window, screen_info)
        if layout_error:
            raise RuntimeError(layout_error)

        data_dir = Path("data")
        metadata = _load_game_data_metadata(data_dir)
        manifest.update(
            {
                "game_data_ref": metadata["ref"],
                "game_version": metadata["game_version"],
                "resource_version": metadata["resource_version"],
                "game_data_language": metadata["language"],
            }
        )
        write_manifest()

        focus_result = window.setForeground()
        if not focus_result or focus_result[0] == "error":
            raise RuntimeError(focus_result[2] if focus_result else "Unable to focus game window.")
        time.sleep(0.25)
        if not window.isForeground():
            raise RuntimeError("Wuthering Waves did not become the foreground window.")

        cancel_event.clear()
        controller = WindowsInputController(
            screen_info.monitor,
            cancel_event=cancel_event,
        )

        def monitor_stop_conditions() -> None:
            key_checker = KeyPressChecker()
            while not monitor_stop.wait(0.1):
                if key_checker.isPressed() or not window.isForeground():
                    cancel_event.set()
                    return

        monitor_thread = threading.Thread(
            target=monitor_stop_conditions,
            name="validation-capture-stop-monitor",
            daemon=True,
        )
        monitor_thread.start()

        def capture_frame():
            check_cancelled(cancel_event)
            return capture_diagnostic_frame()

        def capture_diagnostic_frame():
            frame = screenshot(
                width=SCREEN_WIDTH,
                height=SCREEN_HEIGHT,
                monitor=screen_info.monitor,
            )
            if tuple(frame.shape[:2]) != (SCREEN_HEIGHT, SCREEN_WIDTH):
                raise RuntimeError(
                    "Captured frame does not match the validated 1920x1080 client."
                )
            return frame

        def stable_capture():
            return wait_until_stable(
                capture_frame,
                cancel_event=cancel_event,
                timeout_seconds=12.0,
                poll_seconds=0.25,
                stable_intervals=3,
            )

        def ensure_safe_action():
            check_cancelled(cancel_event)
            error = _strict_layout_error(window, screen_info)
            if error:
                raise RuntimeError(error)
            if not window.isForeground():
                cancel_event.set()
                raise ScanCancelled("Game focus was lost before the next UI action.")

        detector = ValidationStateDetector(screen_info)

        def roi_signature(frame, roi_path: str):
            from hashlib import sha256

            roi = resolve_roi(screen_info, roi_path)
            left, top, width, height = map(
                int,
                (roi.x, roi.y, roi.w, roi.h),
            )
            crop = frame[top : top + height, left : left + width]
            return sha256(crop.tobytes()).hexdigest()

        navigator = Navigator(
            stable_capture=stable_capture,
            detect_state=detector,
            perform_action=lambda action: _map_capture_action(
                action,
                controller=controller,
                screen_info=screen_info,
                config=cfg,
                cancel_event=cancel_event,
            ),
            ensure_safe_action=ensure_safe_action,
            roi_signature=roi_signature,
            cancel_event=cancel_event,
        )

        print(
            "Warning: full validation screenshots may show your UID or other "
            "account details. Review the local captures before sharing them."
        )
        print("Leave the game untouched. Press Enter or move focus away to stop.")

        for current_capture in CAPTURE_PLAN:
            check_cancelled(cancel_event)
            for transition in current_capture.transitions:
                navigator.go_to(transition)
            result = navigator.require_state(current_capture.expected_state)
            output_path = session_dir / current_capture.filename
            _save_full_frame(cv2, result.frame, output_path)
            manifest["captures"].append(
                build_capture_record(
                    current_capture,
                    result,
                    captured_at=iso_timestamp(),
                )
            )
            write_manifest()
            print(
                f"Captured {current_capture.order:02d}/11 "
                f"{current_capture.state_name}."
            )

        status = "complete"

    except (ScanCancelled, KeyboardInterrupt) as exc:
        status = "cancelled"
        transition = (
            navigator.last_transition
            if navigator and navigator.action_in_flight
            else None
        )
        destination = (
            transition.destination.value
            if transition
            else current_capture.expected_state.value
        )
        diagnostic_file, verification = _save_failure_diagnostic(
            cv2=cv2,
            session_dir=session_dir,
            window=window,
            screen_info=locals().get("screen_info"),
            frame=getattr(exc, "last_frame", None),
            capture_frame_fn=locals().get("capture_diagnostic_frame"),
            filename=failed_capture_filename(current_capture, prefix="CANCELLED"),
        )
        if diagnostic_file and verification is None:
            verification = StateObservation(
                state=(
                    transition.destination
                    if transition and navigator.action_in_flight
                    else current_capture.expected_state
                ),
                verified=False,
                detector="capture-cancelled",
                details={"reason": str(exc) or "Validation capture was cancelled."},
            )
        failure = failure_details(
            source=transition.source.value if transition else None,
            destination=destination,
            action=transition.action if transition else None,
            reason=str(exc) or "Validation capture was cancelled.",
            attempts=getattr(exc, "attempts", 0),
            diagnostic_capture=diagnostic_file,
            verification=verification,
        )
        if diagnostic_file and verification:
            manifest["captures"].append(
                _diagnostic_record(
                    current_capture,
                    diagnostic_file,
                    verification,
                    transition_description(current_capture),
                )
            )
        print(f"Validation capture cancelled: {exc}", file=sys.stderr)

    except Exception as exc:
        status = "failed"
        transition = getattr(exc, "transition", None)
        if transition is None and navigator and navigator.action_in_flight:
            transition = navigator.last_transition
        expected = getattr(
            exc,
            "expected",
            transition.destination if transition else current_capture.expected_state,
        )
        diagnostic_frame = getattr(exc, "frame", None)
        if diagnostic_frame is None:
            diagnostic_frame = getattr(exc, "last_frame", None)
        verification = getattr(exc, "observation", None)
        diagnostic_file, fallback_observation = _save_failure_diagnostic(
            cv2=cv2,
            session_dir=session_dir,
            window=window,
            screen_info=locals().get("screen_info"),
            frame=diagnostic_frame,
            capture_frame_fn=locals().get("capture_diagnostic_frame"),
            filename=failed_capture_filename(current_capture),
        )
        verification = verification or fallback_observation
        if diagnostic_file and verification is None:
            verification = StateObservation(
                state=(
                    transition.destination
                    if transition
                    else expected
                    if isinstance(expected, GameState)
                    else current_capture.expected_state
                ),
                verified=False,
                detector="transition-check-failed",
                details={"reason": f"{type(exc).__name__}: {exc}"},
            )
        failure = failure_details(
            source=transition.source.value if transition else (
                navigator.current_state.value
                if navigator and navigator.current_state
                else None
            ),
            destination=(
                transition.destination.value
                if transition
                else expected.value
                if isinstance(expected, GameState)
                else str(expected)
            ),
            action=transition.action if transition else None,
            reason=f"{type(exc).__name__}: {exc}",
            attempts=getattr(exc, "attempts", 1),
            diagnostic_capture=diagnostic_file,
            verification=verification,
        )
        if diagnostic_file and verification:
            manifest["captures"].append(
                _diagnostic_record(
                    current_capture,
                    diagnostic_file,
                    verification,
                    transition_description(current_capture),
                )
            )
        print(f"Validation capture failed: {exc}", file=sys.stderr)

    finally:
        monitor_stop.set()
        if monitor_thread is not None:
            monitor_thread.join(timeout=1.0)

        if (
            controller is not None
            and window is not None
            and navigator is not None
            and (
                navigator.action_in_flight
                or navigator.current_state not in {None, GameState.MAIN_MENU, GameState.SHELL_CREDIT}
            )
            and not (
                navigator.last_transition is not None
                and navigator.last_transition.action == "escape"
            )
            and _safe_for_cleanup(window, locals().get("screen_info"))
        ):
            cleanup_attempted = True
            try:
                controller.pressKey("esc", waitTime=0, cancel_event=None)
                cleanup_succeeded = True
            except Exception:
                cleanup_succeeded = False

        if controller is not None:
            try:
                controller.sct.close()
            except Exception:
                pass

        manifest["cleanup"] = {
            "attempted": cleanup_attempted,
            "succeeded": cleanup_succeeded,
        }
        manifest = finalize_manifest(
            manifest,
            status=status,
            failed_transition=failure,
        )
        write_manifest()

    print(f"Validation output: {session_dir}")
    print(f"Manifest: {manifest_path}")
    return 0 if status == "complete" else 130 if status == "cancelled" else 1


def _safe_for_cleanup(window, screen_info) -> bool:
    if window is None or screen_info is None:
        return False
    try:
        return window.isForeground() and _strict_layout_error(window, screen_info) is None
    except Exception:
        return False


def _save_failure_diagnostic(
    *,
    cv2,
    session_dir: Path,
    window,
    screen_info,
    frame,
    capture_frame_fn,
    filename: str,
) -> tuple[str | None, StateObservation | None]:
    if not _safe_for_cleanup(window, screen_info):
        return None, None
    if frame is None and capture_frame_fn is not None:
        try:
            frame = capture_frame_fn()
        except Exception:
            return None, None
    if frame is None:
        return None, None
    try:
        output_path = session_dir / filename
        _save_full_frame(cv2, frame, output_path)
        return filename, None
    except (OSError, ValueError, cv2.error):
        return None, None


def _diagnostic_record(
    spec: CaptureSpec,
    filename: str,
    observation: StateObservation,
    transition: str,
) -> dict[str, Any]:
    return {
        "state": spec.state_name,
        "filename": filename,
        "transition": transition,
        "timestamp": iso_timestamp(),
        "verified": False,
        "verification": observation.as_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if platform.system() != "Windows":
        print(
            "Validation capture requires native Windows screen capture and "
            "input. Run this module with Windows Python, not from WSL.",
            file=sys.stderr,
        )
        return 2
    return _run_windows(args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
