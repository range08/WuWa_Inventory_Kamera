"""Reusable fail-closed navigation over injected game-state detectors."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from scraping.cancellation import check_cancelled
from scraping.retry import retry_call

from game.navigation.state import (
    GameState,
    NavigationResult,
    StateObservation,
    TransitionSpec,
)


class StateVerificationError(RuntimeError):
    """Raised when the current screen does not match the required state."""

    def __init__(
        self,
        expected: GameState,
        frame: Any,
        observation: StateObservation,
        *,
        attempts: int = 1,
    ) -> None:
        super().__init__(
            f"Expected {expected.value}, but screen verification failed "
            f"after {attempts} attempt(s): {observation.details.get('reason', 'no matching state evidence')}"
        )
        self.expected = expected
        self.frame = frame
        self.observation = observation
        self.attempts = attempts


class TransitionVerificationError(RuntimeError):
    """Raised after an action whose destination could not be verified."""

    def __init__(
        self,
        transition: TransitionSpec,
        frame: Any,
        observation: StateObservation,
        *,
        attempts: int,
    ) -> None:
        super().__init__(
            f"Unable to verify transition to {transition.destination.value} "
            f"after {attempts} bounded check(s): "
            f"{observation.details.get('reason', 'no matching state evidence')}"
        )
        self.transition = transition
        self.frame = frame
        self.observation = observation
        self.attempts = attempts


class _DestinationNotReady(RuntimeError):
    def __init__(self, frame: Any, observation: StateObservation) -> None:
        super().__init__(
            observation.details.get("reason", "Destination state is not ready.")
        )
        self.frame = frame
        self.observation = observation


class Navigator:
    """Run ordinary UI actions only between verified states.

    ``stable_capture`` returns a fresh stable frame. ``ensure_safe_action`` is
    called immediately before every action; the injected detector owns the
    screen-specific evidence and can be expanded when calibrated markers are
    available.
    """

    def __init__(
        self,
        *,
        stable_capture: Callable[[], Any],
        detect_state: Callable[[Any, GameState], StateObservation],
        perform_action: Callable[[str], None],
        ensure_safe_action: Callable[[], None],
        roi_signature: Callable[[Any, str], Any] | None = None,
        cancel_event=None,
    ) -> None:
        self.stable_capture = stable_capture
        self.detect_state = detect_state
        self.perform_action = perform_action
        self.ensure_safe_action = ensure_safe_action
        self.roi_signature = roi_signature
        self.cancel_event = cancel_event
        self.current_state: GameState | None = None
        self.last_transition: TransitionSpec | None = None
        self.action_in_flight = False

    def _observe(self, frame: Any, expected: GameState) -> StateObservation:
        observation = self.detect_state(frame, expected)
        if not isinstance(observation, StateObservation):
            raise TypeError("State detector must return StateObservation.")
        if observation.state != expected:
            return StateObservation(
                state=observation.state,
                verified=False,
                detector=observation.detector,
                confidence=observation.confidence,
                roi=observation.roi,
                details={
                    **observation.details,
                    "reason": (
                        f"detector identified {observation.state.value}, "
                        f"expected {expected.value}"
                    ),
                },
            )
        return observation

    def require_state(self, expected: GameState) -> NavigationResult:
        check_cancelled(self.cancel_event)
        frame = self.stable_capture()
        check_cancelled(self.cancel_event)
        observation = self._observe(frame, expected)
        if not observation.verified:
            raise StateVerificationError(expected, frame, observation)
        self.current_state = expected
        self.action_in_flight = False
        return NavigationResult(frame, observation)

    def go_to(self, transition: TransitionSpec) -> NavigationResult:
        check_cancelled(self.cancel_event)
        source = self.require_state(transition.source)
        baseline_signature = None
        if transition.changed_roi is not None:
            if self.roi_signature is None:
                raise ValueError(
                    "Transition requires changed_roi but no ROI signature "
                    "provider was supplied."
                )
            baseline_signature = self.roi_signature(
                source.frame,
                transition.changed_roi,
            )

        check_cancelled(self.cancel_event)
        self.ensure_safe_action()
        self.last_transition = transition
        self.action_in_flight = True
        self.perform_action(transition.action)

        attempts = 0

        def verify_destination() -> NavigationResult:
            nonlocal attempts
            attempts += 1
            check_cancelled(self.cancel_event)
            frame = self.stable_capture()
            check_cancelled(self.cancel_event)
            observation = self._observe(frame, transition.destination)
            changed = True
            if transition.changed_roi is not None and observation.verified:
                after_signature = self.roi_signature(
                    frame,
                    transition.changed_roi,
                )
                changed = after_signature != baseline_signature
                if not changed:
                    observation = StateObservation(
                        state=observation.state,
                        verified=False,
                        detector=observation.detector,
                        confidence=observation.confidence,
                        roi=observation.roi,
                        details={
                            **observation.details,
                            "reason": (
                                f"destination evidence at {transition.changed_roi} "
                                "did not change after the action"
                            ),
                            "changed_roi": transition.changed_roi,
                            "roi_changed": False,
                        },
                    )
            if observation.verified and changed:
                return NavigationResult(
                    frame,
                    observation,
                    attempts=attempts,
                    transition=transition,
                )
            raise _DestinationNotReady(frame, observation)

        try:
            result = retry_call(
                verify_destination,
                attempts=transition.verification_attempts,
                delay_seconds=transition.retry_delay_seconds,
                retry_on=(_DestinationNotReady,),
                cancel_event=self.cancel_event,
            )
        except _DestinationNotReady as exc:
            self.current_state = None
            raise TransitionVerificationError(
                transition,
                exc.frame,
                exc.observation,
                attempts=transition.verification_attempts,
            ) from exc

        self.current_state = transition.destination
        self.action_in_flight = False
        return NavigationResult(
            result.frame,
            result.observation,
            attempts=attempts,
            transition=transition,
        )
