import threading
import unittest

from game.navigation.navigator import (
    Navigator,
    StateVerificationError,
    TransitionVerificationError,
)
from game.navigation.stability import (
    FrameSignature,
    frame_signature,
    signatures_are_stable,
    wait_until_stable,
)
from game.navigation.state import GameState, StateObservation, TransitionSpec
from scraping.cancellation import ScanCancelled


class NavigatorTests(unittest.TestCase):
    @staticmethod
    def make_observation(state, verified=True, reason="test evidence"):
        return StateObservation(
            state=state,
            verified=verified,
            detector="test-detector",
            confidence=0.9,
            details={"reason": reason},
        )

    def test_requires_source_state_before_action(self):
        actions = []
        navigator = Navigator(
            stable_capture=lambda: "menu-frame",
            detect_state=lambda _frame, expected: self.make_observation(
                expected,
                verified=False,
                reason="not terminal",
            ),
            perform_action=actions.append,
            ensure_safe_action=lambda: None,
        )

        with self.assertRaises(StateVerificationError):
            navigator.go_to(
                TransitionSpec(
                    GameState.MAIN_MENU,
                    GameState.INVENTORY,
                    "open-inventory",
                    "open inventory",
                )
            )

        self.assertEqual(actions, [])

    def test_destination_retry_limit_does_not_repeat_action(self):
        frames = iter(["source", "failed-1", "failed-2", "failed-3"])
        checks = []
        actions = []

        def detect(frame, expected):
            checks.append((frame, expected))
            return self.make_observation(
                expected,
                verified=frame == "source",
                reason="unrecognized",
            )

        navigator = Navigator(
            stable_capture=lambda: next(frames),
            detect_state=detect,
            perform_action=actions.append,
            ensure_safe_action=lambda: None,
        )
        transition = TransitionSpec(
            GameState.MAIN_MENU,
            GameState.INVENTORY,
            "open-inventory",
            "open inventory",
            verification_attempts=3,
            retry_delay_seconds=0,
        )

        with self.assertRaises(TransitionVerificationError) as raised:
            navigator.go_to(transition)

        self.assertEqual(actions, ["open-inventory"])
        self.assertEqual(raised.exception.attempts, 3)
        self.assertEqual(raised.exception.frame, "failed-3")
        self.assertEqual(len(checks), 4)  # Source plus three destination checks.
        self.assertTrue(navigator.action_in_flight)

    def test_successful_destination_stops_retries(self):
        frames = iter(["source", "first", "destination"])
        actions = []
        checks = []

        def detect(frame, expected):
            checks.append(frame)
            return self.make_observation(
                expected,
                verified=frame in {"source", "destination"},
            )

        navigator = Navigator(
            stable_capture=lambda: next(frames),
            detect_state=detect,
            perform_action=actions.append,
            ensure_safe_action=lambda: None,
        )
        result = navigator.go_to(
            TransitionSpec(
                GameState.MAIN_MENU,
                GameState.INVENTORY,
                "open-inventory",
                "open inventory",
                verification_attempts=3,
                retry_delay_seconds=0,
            )
        )

        self.assertEqual(result.frame, "destination")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(actions, ["open-inventory"])
        self.assertEqual(len(checks), 3)
        self.assertFalse(navigator.action_in_flight)

    def test_changed_roi_must_change_before_transition_is_accepted(self):
        frames = iter(["before", "after-1", "after-2"])
        actions = []
        navigator = Navigator(
            stable_capture=lambda: next(frames),
            detect_state=lambda _frame, expected: self.make_observation(expected),
            perform_action=actions.append,
            ensure_safe_action=lambda: None,
            roi_signature=lambda _frame, _roi: "same-content",
        )

        with self.assertRaises(TransitionVerificationError) as raised:
            navigator.go_to(
                TransitionSpec(
                    GameState.INVENTORY,
                    GameState.INVENTORY_ITEMS,
                    "select-resource-tab",
                    "select Resources",
                    verification_attempts=2,
                    retry_delay_seconds=0,
                    changed_roi="items.info",
                )
            )

        self.assertEqual(actions, ["select-resource-tab"])
        self.assertEqual(raised.exception.attempts, 2)
        self.assertFalse(raised.exception.observation.verified)
        self.assertFalse(raised.exception.observation.details["roi_changed"])

    def test_cancellation_prevents_action(self):
        cancellation = threading.Event()
        cancellation.set()
        actions = []
        navigator = Navigator(
            stable_capture=lambda: "source",
            detect_state=lambda _frame, expected: self.make_observation(expected),
            perform_action=actions.append,
            ensure_safe_action=lambda: None,
            cancel_event=cancellation,
        )

        with self.assertRaises(ScanCancelled):
            navigator.go_to(
                TransitionSpec(
                    GameState.MAIN_MENU,
                    GameState.INVENTORY,
                    "open-inventory",
                    "open inventory",
                )
            )
        self.assertEqual(actions, [])

    def test_cancellation_during_destination_check_does_not_repeat_action(self):
        cancellation = threading.Event()
        actions = []
        frame_count = 0

        def capture():
            nonlocal frame_count
            frame_count += 1
            if frame_count == 2:
                cancellation.set()
            return f"frame-{frame_count}"

        navigator = Navigator(
            stable_capture=capture,
            detect_state=lambda _frame, expected: self.make_observation(expected),
            perform_action=actions.append,
            ensure_safe_action=lambda: None,
            cancel_event=cancellation,
        )

        with self.assertRaises(ScanCancelled):
            navigator.go_to(
                TransitionSpec(
                    GameState.MAIN_MENU,
                    GameState.INVENTORY,
                    "open-inventory",
                    "open inventory",
                )
            )
        self.assertEqual(actions, ["open-inventory"])


class _FakeSample:
    def __init__(self, data):
        self.data = data

    def tobytes(self):
        return self.data


class _FakeFrame:
    shape = (32, 32, 3)

    def __init__(self, data):
        self.data = data

    def __getitem__(self, _slice):
        return _FakeSample(self.data)


class StabilityTests(unittest.TestCase):
    def test_frame_signature_samples_without_external_image_dependencies(self):
        signature = frame_signature(_FakeFrame(b"abcd"), stride=2)
        self.assertEqual(signature, FrameSignature((32, 32, 3), b"abcd"))

    def test_small_sparse_animation_delta_is_stable_but_layout_change_is_not(self):
        first = FrameSignature((10, 10, 3), bytes([10] * 100))
        almost_same = FrameSignature((10, 10, 3), bytes([10] * 99 + [12]))
        different_shape = FrameSignature((20, 10, 3), bytes([10] * 100))
        self.assertTrue(signatures_are_stable(first, almost_same))
        self.assertFalse(signatures_are_stable(first, different_shape))

    def test_waits_for_configured_number_of_stable_intervals(self):
        now = [0.0]
        frames = []

        def capture():
            frames.append(len(frames))
            return _FakeFrame(b"same")

        result = wait_until_stable(
            capture,
            timeout_seconds=1.0,
            poll_seconds=0.1,
            stable_intervals=2,
            stride=1,
            monotonic=lambda: now[0],
            sleeper=lambda delay: now.__setitem__(0, now[0] + delay),
        )
        self.assertIsInstance(result, _FakeFrame)
        self.assertEqual(len(frames), 3)

    def test_cancellation_during_frame_capture_is_observed(self):
        cancellation = threading.Event()

        def capture():
            cancellation.set()
            return _FakeFrame(b"same")

        with self.assertRaises(ScanCancelled):
            wait_until_stable(
                capture,
                cancel_event=cancellation,
                timeout_seconds=1,
                poll_seconds=0.1,
                stable_intervals=1,
                stride=1,
            )


if __name__ == "__main__":
    unittest.main()
