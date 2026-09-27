"""OCR state detectors bound to the existing scanner ROI profiles."""

from __future__ import annotations

import re
from typing import Any

from game.navigation.state import GameState, StateObservation

STATE_MIN_CONFIDENCE = 0.75


def resolve_roi(screen_info, dotted_path: str):
    value = screen_info
    for part in dotted_path.split("."):
        value = getattr(value, part)
    return value


class ValidationStateDetector:
    """Use only existing scanner ROIs and field-format evidence."""

    def __init__(self, screen_info):
        from game.menu import MainMenuController
        from properties.config import cfg
        from scraping.data_store import (
            charactersID,
            definedText,
            echoesID,
            itemsID,
            weaponsID,
        )

        self.screen_info = screen_info
        self.defined_text = definedText
        self.characters = charactersID
        self.echoes = echoesID
        self.items = itemsID
        self.weapons = weaponsID
        self.config = cfg
        self.main_menu = MainMenuController()

    def _crop(self, frame, roi_path: str):
        roi = resolve_roi(self.screen_info, roi_path)
        left, top, width, height = map(
            int,
            (roi.x, roi.y, roi.w, roi.h),
        )
        if min(left, top, width, height) < 0 or width <= 0 or height <= 0:
            raise ValueError(f"Invalid configured ROI: {roi_path}")
        if top + height > frame.shape[0] or left + width > frame.shape[1]:
            raise ValueError(f"Configured ROI is outside the captured frame: {roi_path}")
        return frame[top : top + height, left : left + width]

    @staticmethod
    def _text_result(image, *, profile=None, banned_chars=None):
        from scraping.utils import imageToResult

        options = {}
        if profile is not None:
            options["profile"] = profile
        if banned_chars is not None:
            options["bannedChars"] = banned_chars
        return imageToResult(image, **options)

    def _evidence(
        self,
        state: GameState,
        detector: str,
        roi: str,
        confidence: float,
        *,
        verified: bool,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> StateObservation:
        return StateObservation(
            state=state,
            verified=verified,
            detector=detector,
            confidence=float(confidence),
            roi=roi,
            details={
                "reason": reason,
                **(details or {}),
            },
        )

    def _read_count(self, frame) -> tuple[bool, float, str]:
        from scraping.ocr_engine import LEVEL_PROFILE

        roi_path = "weapons.page"
        result = self._text_result(self._crop(frame, roi_path), profile=LEVEL_PROFILE)
        matches = re.fullmatch(r"\s*\d+\s*/\s*\d+\s*", result.text)
        return (
            bool(matches and result.confidence >= STATE_MIN_CONFIDENCE),
            float(result.confidence),
            roi_path,
        )

    def _read_item_details(self, frame) -> tuple[bool, float, dict[str, Any]]:
        from scraping.parsing import ScanParseError, parse_quantity
        from scraping.matching import ITEM_NAME_CUTOFF, best_match

        roi_path = "items.info"
        result = self._text_result(
            self._crop(frame, roi_path),
            banned_chars=" ",
        )
        lines = [line.strip() for line in result.text.lower().splitlines()]
        candidate = best_match(
            lines[0] if lines else "",
            self.items,
            cutoff=ITEM_NAME_CUTOFF,
        )
        quantity_valid = False
        if len(lines) >= 3 and lines[0] and lines[2]:
            try:
                parse_quantity(lines[2])
                quantity_valid = True
            except ScanParseError:
                pass
        verified = bool(
            result.confidence >= STATE_MIN_CONFIDENCE
            and len(lines) >= 3
            and candidate is not None
            and quantity_valid
        )
        return (
            verified,
            float(result.confidence),
            {
                "item_name_recognized": candidate is not None,
                "quantity_parseable": quantity_valid,
            },
        )

    def _read_weapon_details(self, frame) -> tuple[bool, float, dict[str, Any]]:
        from scraping.ocr_engine import INTEGER_PROFILE, LEVEL_PROFILE, NAME_PROFILE
        from scraping.matching import (
            ITEM_NAME_CUTOFF,
            WEAPON_INVENTORY_NAME_CUTOFF,
            best_match,
        )
        from scraping.parsing import ScanParseError, parse_level_pair

        name_roi = "weapons.name"
        level_roi = "weapons.level"
        rank_roi = "weapons.rank"
        name = self._text_result(self._crop(frame, name_roi), profile=NAME_PROFILE)
        level = self._text_result(self._crop(frame, level_roi), profile=LEVEL_PROFILE)
        rank = self._text_result(self._crop(frame, rank_roi), profile=INTEGER_PROFILE)
        weapon_candidate = best_match(
            name.text.lower(),
            self.weapons,
            cutoff=WEAPON_INVENTORY_NAME_CUTOFF,
        )
        item_candidate = best_match(
            name.text.lower(),
            self.items,
            cutoff=ITEM_NAME_CUTOFF,
        )
        name_recognized = weapon_candidate is not None or item_candidate is not None
        level_valid = False
        rank_valid = False
        try:
            current, cap = parse_level_pair(level.text)
            level_valid = 1 <= current <= cap <= 90
        except ScanParseError:
            pass
        try:
            rank_value = int(rank.text)
            rank_valid = 1 <= rank_value <= 5
        except (TypeError, ValueError):
            pass
        count_valid, count_confidence, count_roi = self._read_count(frame)
        verified = bool(
            name_recognized
            and name.confidence >= STATE_MIN_CONFIDENCE
            and count_valid
        )
        return (
            verified,
            min(float(name.confidence), count_confidence),
            {
                "name_recognized": name_recognized,
                "count_roi": count_roi,
                "level_pair_parseable": level_valid,
                "rank_parseable": rank_valid,
            },
        )

    def _read_echo_details(self, frame) -> tuple[bool, float, dict[str, Any]]:
        from scraping.ocr_engine import (
            NAME_PROFILE,
            STAT_NAME_PROFILE,
            STAT_VALUE_PROFILE,
        )
        from scraping.matching import ECHO_NAME_CUTOFF, best_match

        count_valid, count_confidence, count_roi = self._read_count(frame)
        roi_path = "echoes.echoCard"
        card = self._text_result(self._crop(frame, roi_path), profile=NAME_PROFILE)
        echo_name = card.text.lower().splitlines()[0] if card.text else ""
        echo_candidate = best_match(
            echo_name,
            self.echoes,
            cutoff=ECHO_NAME_CUTOFF,
        )
        stat_names = self._text_result(
            self._crop(frame, "echoes.fullStatsName"),
            profile=STAT_NAME_PROFILE,
        )
        stat_values = self._text_result(
            self._crop(frame, "echoes.fullStatsValue"),
            profile=STAT_VALUE_PROFILE,
        )
        full_stats_visible = bool(
            stat_names.text
            and stat_values.text
            and stat_names.confidence >= STATE_MIN_CONFIDENCE
            and stat_values.confidence >= STATE_MIN_CONFIDENCE
        )
        verified = bool(
            count_valid
            and echo_candidate is not None
            and card.confidence >= STATE_MIN_CONFIDENCE
        )
        return (
            verified,
            min(float(card.confidence), count_confidence),
            {
                "count_roi": count_roi,
                "echo_name_recognized": echo_candidate is not None,
                "full_stats_visible": full_stats_visible,
            },
        )

    def _read_resonator_overview(self, frame) -> tuple[bool, float, dict[str, Any]]:
        from scraping.ocr_engine import LEVEL_PROFILE, NAME_PROFILE
        from scraping.matching import RESONATOR_NAME_CUTOFF, best_match
        from scraping.parsing import ScanParseError, parse_level_pair

        name_roi = "characters.resonatorName"
        level_roi = "characters.resonatorLevel"
        name = self._text_result(self._crop(frame, name_roi), profile=NAME_PROFILE)
        name_text = name.text.lower().replace(" ", "")
        candidate = best_match(
            name_text,
            self.characters,
            cutoff=RESONATOR_NAME_CUTOFF,
        )
        rover_name = self.config.get(self.config.roverName).replace(" ", "").lower()
        name_recognized = candidate is not None or name_text == rover_name
        level = self._text_result(self._crop(frame, level_roi), profile=LEVEL_PROFILE)
        level_valid = False
        try:
            current, cap = parse_level_pair(level.text)
            level_valid = 1 <= current <= cap <= 90
        except ScanParseError:
            pass
        verified = bool(
            name_recognized
            and name.confidence >= STATE_MIN_CONFIDENCE
            and level.confidence >= STATE_MIN_CONFIDENCE
            and level_valid
        )
        return (
            verified,
            min(float(name.confidence), float(level.confidence)),
            {"name_recognized": name_recognized, "level_pair_parseable": level_valid},
        )

    def _read_resonator_weapon(self, frame) -> tuple[bool, float, dict[str, Any]]:
        from scraping.ocr_engine import INTEGER_PROFILE, LEVEL_PROFILE, NAME_PROFILE
        from scraping.matching import EQUIPPED_WEAPON_NAME_CUTOFF, best_match
        from scraping.parsing import ScanParseError, parse_level_pair

        name = self._text_result(
            self._crop(frame, "characters.weaponName"),
            profile=NAME_PROFILE,
        )
        level = self._text_result(
            self._crop(frame, "characters.weaponLevel"),
            profile=LEVEL_PROFILE,
        )
        rank = self._text_result(
            self._crop(frame, "characters.weaponRank"),
            profile=INTEGER_PROFILE,
        )
        weapon_candidate = best_match(
            name.text.lower(),
            self.weapons,
            cutoff=EQUIPPED_WEAPON_NAME_CUTOFF,
        )
        level_valid = False
        rank_valid = False
        try:
            current, cap = parse_level_pair(level.text)
            level_valid = 1 <= current <= cap <= 90
        except ScanParseError:
            pass
        try:
            rank_value = int(rank.text)
            rank_valid = 1 <= rank_value <= 5
        except (TypeError, ValueError):
            pass
        verified = bool(
            weapon_candidate is not None
            and name.confidence >= STATE_MIN_CONFIDENCE
            and level.confidence >= STATE_MIN_CONFIDENCE
            and rank.confidence >= STATE_MIN_CONFIDENCE
            and level_valid
            and rank_valid
        )
        return (
            verified,
            min(float(name.confidence), float(level.confidence), float(rank.confidence)),
            {
                "weapon_name_recognized": weapon_candidate is not None,
                "level_pair_parseable": level_valid,
                "rank_parseable": rank_valid,
            },
        )

    def __call__(self, frame, expected: GameState) -> StateObservation:
        from scraping.ocr_engine import INTEGER_PROFILE, NAME_PROFILE

        if expected == GameState.MAIN_MENU:
            roi_path = "terminal"
            evidence = self.main_menu.inspect_image(self._crop(frame, roi_path))
            return StateObservation(
                expected,
                evidence["verified"],
                evidence["detector"],
                evidence["confidence"],
                roi_path,
                {"reason": evidence["reason"]},
            )

        if expected == GameState.SHELL_CREDIT:
            menu = self(frame, GameState.MAIN_MENU)
            roi_path = "shell"
            result = self._text_result(
                self._crop(frame, roi_path),
                profile=INTEGER_PROFILE,
            )
            value_valid = bool(
                result.text.isdigit()
                and result.confidence >= STATE_MIN_CONFIDENCE
            )
            return StateObservation(
                expected,
                menu.verified and value_valid,
                "terminal-and-shell-credit-ocr",
                min(
                    menu.confidence or 0.0,
                    float(result.confidence),
                ),
                roi_path,
                {
                    "reason": (
                        "Terminal and Shell Credit were recognized."
                        if menu.verified and value_valid
                        else "Terminal or Shell Credit OCR could not be verified."
                    ),
                    "terminal_verified": menu.verified,
                    "shell_value_parseable": value_valid,
                },
            )

        if expected == GameState.INVENTORY:
            count_valid, confidence, roi_path = self._read_count(frame)
            if count_valid:
                return StateObservation(
                    expected,
                    True,
                    "inventory-count-ocr",
                    confidence,
                    roi_path,
                    {"reason": "Inventory count field is visible."},
                )
            # Item categories do not all expose the same page counter. Their
            # own established scanner detail ROIs are a secondary marker.
            for state, reader, roi in (
                (GameState.INVENTORY_WEAPONS, self._read_weapon_details, "weapons.name"),
                (GameState.INVENTORY_ECHOES, self._read_echo_details, "echoes.echoCard"),
                (GameState.INVENTORY_ITEMS, self._read_item_details, "items.info"),
            ):
                verified, candidate_confidence, details = reader(frame)
                if verified:
                    return StateObservation(
                        expected,
                        True,
                        "inventory-detail-ocr",
                        candidate_confidence,
                        roi,
                        {"reason": "A known inventory detail panel is visible.", **details},
                    )
            return StateObservation(
                expected,
                False,
                "inventory-count-or-detail-ocr",
                confidence,
                roi_path,
                {"reason": "No calibrated inventory count or detail marker was recognized."},
            )

        if expected == GameState.INVENTORY_WEAPONS:
            verified, confidence, details = self._read_weapon_details(frame)
            return self._evidence(
                expected,
                "weapon-name-level-rank-ocr",
                "weapons.name",
                confidence,
                verified=verified,
                reason=(
                    "Weapon detail fields are plausible."
                    if verified
                    else "Weapon name, level, and rank were not all verified."
                ),
                details=details,
            )

        if expected == GameState.INVENTORY_ECHOES:
            verified, confidence, details = self._read_echo_details(frame)
            return StateObservation(
                expected,
                verified,
                "echo-card-and-count-ocr",
                confidence,
                "echoes.echoCard",
                {
                    "reason": (
                        "Echo card and inventory count are visible."
                        if verified
                        else "Echo card and count were not both verified."
                    ),
                    **details,
                },
            )

        if expected == GameState.INVENTORY_ITEMS:
            verified, confidence, details = self._read_item_details(frame)
            return StateObservation(
                expected,
                verified,
                "item-name-and-quantity-ocr",
                confidence,
                "items.info",
                {
                    "reason": (
                        "An item detail name and quantity are visible."
                        if verified
                        else "An item detail name and quantity were not verified."
                    ),
                    **details,
                },
            )

        if expected == GameState.RESONATOR_OVERVIEW:
            verified, confidence, details = self._read_resonator_overview(frame)
            return StateObservation(
                expected,
                verified,
                "resonator-name-and-level-ocr",
                confidence,
                "characters.resonatorName",
                {
                    "reason": (
                        "Resonator name and level fields are visible."
                        if verified
                        else "Resonator name and level fields were not both verified."
                    ),
                    **details,
                },
            )

        if expected == GameState.RESONATOR_WEAPON:
            verified, confidence, details = self._read_resonator_weapon(frame)
            return StateObservation(
                expected,
                verified,
                "equipped-weapon-name-level-rank-ocr",
                confidence,
                "characters.weaponName",
                {
                    "reason": (
                        "Equipped weapon fields are visible."
                        if verified
                        else "Equipped weapon name, level, and rank were not all verified."
                    ),
                    **details,
                },
            )

        if expected == GameState.RESONATOR_SKILLS_PAGE:
            roi_path = "characters.skillButton"
            result = self._text_result(self._crop(frame, roi_path), profile=NAME_PROFILE)
            valid = bool(
                result.text
                and result.confidence >= STATE_MIN_CONFIDENCE
            )
            return self._evidence(
                expected,
                "skill-node-status-ocr",
                roi_path,
                result.confidence,
                verified=valid,
                reason=(
                    "Skill node status text is visible."
                    if valid
                    else "Skill node status text was not recognized."
                ),
                details={"status_text_visible": bool(result.text)},
            )

        if expected == GameState.RESONATOR_SKILLS:
            roi_path = "characters.skillLevel"
            result = self._text_result(self._crop(frame, roi_path), profile=INTEGER_PROFILE)
            try:
                skill_level = int(result.text)
            except (TypeError, ValueError):
                skill_level = 0
            valid = bool(
                result.confidence >= STATE_MIN_CONFIDENCE
                and 1 <= skill_level <= 10
            )
            return self._evidence(
                expected,
                "skill-level-integer-ocr",
                roi_path,
                result.confidence,
                verified=valid,
                reason=(
                    "A skill level from 1 to 10 is visible."
                    if valid
                    else "No plausible skill level was recognized."
                ),
                details={"skill_level_visible": valid},
            )

        if expected == GameState.RESONATOR_CHAIN:
            roi_path = "characters.chainButton"
            result = self._text_result(self._crop(frame, roi_path), profile=NAME_PROFILE)
            valid = bool(
                result.text
                and result.confidence >= STATE_MIN_CONFIDENCE
            )
            activated = self.defined_text.get(
                "PrefabTextItem_3963945691_Text",
                "",
            ).lower()
            status_kind = (
                "activated"
                if activated and result.text.lower() == activated
                else "text-visible"
            )
            return self._evidence(
                expected,
                "resonance-chain-button-status-ocr",
                roi_path,
                result.confidence,
                verified=valid,
                reason=(
                    "Resonance Chain status text is visible."
                    if valid
                    else "Resonance Chain status text was not recognized."
                ),
                details={"node_status": status_kind},
            )

        if expected == GameState.ACHIEVEMENTS:
            roi_path = "achievements.status"
            result = self._text_result(self._crop(frame, roi_path))
            progress_visible = bool(re.search(r"\d+\s*/\s*\d+", result.text))
            claimed = self.defined_text.get(
                "PrefabTextItem_128820487_Text",
                "",
            ).lower()
            claimed_visible = bool(claimed and result.text.lower() == claimed)
            valid = bool(
                result.confidence >= STATE_MIN_CONFIDENCE
                and (progress_visible or claimed_visible)
            )
            return self._evidence(
                expected,
                "achievement-status-ocr",
                roi_path,
                result.confidence,
                verified=valid,
                reason=(
                    "Achievement progress or claim status is visible."
                    if valid
                    else "Achievement status was not recognized."
                ),
                details={
                    "progress_visible": progress_visible,
                    "claim_status_visible": claimed_visible,
                },
            )

        raise ValueError(f"No state detector is registered for {expected.value}.")
