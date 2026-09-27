"""Dependency-free state and transition definitions for the game UI."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GameState(str, Enum):
    MAIN_MENU = "main-menu"
    INVENTORY = "inventory"
    INVENTORY_WEAPONS = "inventory-weapons"
    INVENTORY_ECHOES = "inventory-echoes"
    INVENTORY_ITEMS = "inventory-items"
    RESONATOR_OVERVIEW = "resonator-overview"
    RESONATOR_WEAPON = "resonator-weapon"
    RESONATOR_SKILLS_PAGE = "resonator-skills-page"
    RESONATOR_SKILLS = "resonator-skills"
    RESONATOR_CHAIN = "resonator-chain"
    ACHIEVEMENTS = "achievements"
    SHELL_CREDIT = "shell-credit"


@dataclass(frozen=True)
class StateObservation:
    """Evidence returned by a state detector for one captured frame."""

    state: GameState
    verified: bool
    detector: str
    confidence: float | None = None
    roi: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence is not None and (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("State confidence must be between 0 and 1.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "verified": self.verified,
            "detector": self.detector,
            "confidence": self.confidence,
            "roi": self.roi,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class TransitionSpec:
    """One ordinary UI action followed by a verified destination state."""

    source: GameState
    destination: GameState
    action: str
    description: str
    verification_attempts: int = 3
    retry_delay_seconds: float = 0.35
    changed_roi: str | None = None

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("Transition action must be non-empty.")
        if not self.description:
            raise ValueError("Transition description must be non-empty.")
        if (
            isinstance(self.verification_attempts, bool)
            or not isinstance(self.verification_attempts, int)
            or self.verification_attempts < 1
        ):
            raise ValueError("verification_attempts must be at least 1.")
        if (
            isinstance(self.retry_delay_seconds, bool)
            or not isinstance(self.retry_delay_seconds, (int, float))
            or not math.isfinite(self.retry_delay_seconds)
            or self.retry_delay_seconds < 0
        ):
            raise ValueError("retry_delay_seconds must be finite and non-negative.")


@dataclass(frozen=True)
class NavigationResult:
    """A stable frame and the evidence that identifies its current state."""

    frame: Any
    observation: StateObservation
    attempts: int = 1
    transition: TransitionSpec | None = None
