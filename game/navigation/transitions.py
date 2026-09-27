"""Current validation-capture plan using existing scanner UI controls."""

from __future__ import annotations

import re
from dataclasses import dataclass

from game.navigation.state import GameState, TransitionSpec


@dataclass(frozen=True)
class CaptureSpec:
    order: int
    state_name: str
    filename: str
    expected_state: GameState
    transitions: tuple[TransitionSpec, ...] = ()

    def __post_init__(self) -> None:
        if self.order < 1:
            raise ValueError("Capture order must be positive.")
        if not self.state_name or not self.filename:
            raise ValueError("Capture state and filename must be non-empty.")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.state_name):
            raise ValueError("Capture state must be a lowercase slug.")
        if "/" in self.filename or "\\" in self.filename:
            raise ValueError("Capture filename must be a plain filename.")
        if self.filename in {".", ".."} or not self.filename.lower().endswith(".png"):
            raise ValueError("Capture filename must be a PNG file.")


OPEN_INVENTORY = TransitionSpec(
    GameState.MAIN_MENU,
    GameState.INVENTORY,
    "open_inventory",
    "open inventory with the configured in-game key",
)
SELECT_WEAPONS = TransitionSpec(
    GameState.INVENTORY,
    GameState.INVENTORY_WEAPONS,
    "select_weapons",
    "select the Weapons inventory category",
)
SELECT_ECHOES = TransitionSpec(
    GameState.INVENTORY_WEAPONS,
    GameState.INVENTORY_ECHOES,
    "select_echoes",
    "select the Echoes inventory category",
)
REVEAL_ECHO_DETAILS = TransitionSpec(
    GameState.INVENTORY_ECHOES,
    GameState.INVENTORY_ECHOES,
    "hover_echo_details",
    "move the pointer to the scanner's Echo detail view",
)
SELECT_DEVELOPMENT_ITEMS = TransitionSpec(
    GameState.INVENTORY_ECHOES,
    GameState.INVENTORY_ITEMS,
    "select_development_items",
    "select the Development Items inventory category",
    changed_roi="items.info",
)
SELECT_RESOURCES = TransitionSpec(
    GameState.INVENTORY_ITEMS,
    GameState.INVENTORY_ITEMS,
    "select_resources",
    "select the Resources inventory category",
    changed_roi="items.info",
)
CLOSE_INVENTORY = TransitionSpec(
    GameState.INVENTORY_ITEMS,
    GameState.MAIN_MENU,
    "escape",
    "return from inventory to the Terminal menu",
)
OPEN_RESONATOR = TransitionSpec(
    GameState.MAIN_MENU,
    GameState.RESONATOR_OVERVIEW,
    "open_resonator",
    "open the Resonator screen with the configured in-game key",
)
SELECT_RESONATOR_WEAPON = TransitionSpec(
    GameState.RESONATOR_OVERVIEW,
    GameState.RESONATOR_WEAPON,
    "select_resonator_weapon",
    "select the Equipped Weapon section",
)
SELECT_RESONATOR_SKILLS_PAGE = TransitionSpec(
    GameState.RESONATOR_WEAPON,
    GameState.RESONATOR_SKILLS_PAGE,
    "select_resonator_skills",
    "select the Forte and Skills section",
    changed_roi="characters.skillButton",
)
SELECT_RESONATOR_SKILL_DETAIL = TransitionSpec(
    GameState.RESONATOR_SKILLS_PAGE,
    GameState.RESONATOR_SKILLS,
    "select_resonator_skill_detail",
    "open the current skill detail panel",
)
CLOSE_RESONATOR_SKILL_DETAIL = TransitionSpec(
    GameState.RESONATOR_SKILLS,
    GameState.RESONATOR_SKILLS_PAGE,
    "escape",
    "close the skill detail panel",
)
SELECT_RESONATOR_CHAIN = TransitionSpec(
    GameState.RESONATOR_SKILLS_PAGE,
    GameState.RESONATOR_CHAIN,
    "select_resonator_chain",
    "select the Resonance Chain section",
    changed_roi="characters.chainButton",
)
SELECT_RESONANCE_CHAIN_NODE = TransitionSpec(
    GameState.RESONATOR_CHAIN,
    GameState.RESONATOR_CHAIN,
    "select_resonance_chain_node",
    "select the scanner's initial Resonance Chain node to expose its status",
)
CLOSE_RESONATOR = TransitionSpec(
    GameState.RESONATOR_CHAIN,
    GameState.MAIN_MENU,
    "escape",
    "return from Resonator to the Terminal menu",
)
OPEN_ACHIEVEMENTS = TransitionSpec(
    GameState.MAIN_MENU,
    GameState.ACHIEVEMENTS,
    "open_achievements",
    "open Achievements from the Terminal menu",
    changed_roi="achievements.status",
)
SELECT_ACHIEVEMENTS_TAB = TransitionSpec(
    GameState.ACHIEVEMENTS,
    GameState.ACHIEVEMENTS,
    "select_achievements_tab",
    "select the current Achievements tab",
)
CLOSE_ACHIEVEMENTS = TransitionSpec(
    GameState.ACHIEVEMENTS,
    GameState.MAIN_MENU,
    "escape",
    "return from Achievements to the Terminal menu",
)


CAPTURE_PLAN = (
    CaptureSpec(
        1,
        "main-menu",
        "01-main-menu.png",
        GameState.MAIN_MENU,
    ),
    CaptureSpec(
        2,
        "inventory-weapons",
        "02-inventory-weapons.png",
        GameState.INVENTORY_WEAPONS,
        (OPEN_INVENTORY, SELECT_WEAPONS),
    ),
    CaptureSpec(
        3,
        "inventory-echoes",
        "03-inventory-echoes.png",
        GameState.INVENTORY_ECHOES,
        (SELECT_ECHOES, REVEAL_ECHO_DETAILS),
    ),
    CaptureSpec(
        4,
        "inventory-development-items",
        "04-inventory-development-items.png",
        GameState.INVENTORY_ITEMS,
        (SELECT_DEVELOPMENT_ITEMS,),
    ),
    CaptureSpec(
        5,
        "inventory-resources",
        "05-inventory-resources.png",
        GameState.INVENTORY_ITEMS,
        (SELECT_RESOURCES,),
    ),
    CaptureSpec(
        6,
        "resonator-overview",
        "06-resonator-overview.png",
        GameState.RESONATOR_OVERVIEW,
        (CLOSE_INVENTORY, OPEN_RESONATOR),
    ),
    CaptureSpec(
        7,
        "resonator-weapon",
        "07-resonator-weapon.png",
        GameState.RESONATOR_WEAPON,
        (SELECT_RESONATOR_WEAPON,),
    ),
    CaptureSpec(
        8,
        "resonator-skills",
        "08-resonator-skills.png",
        GameState.RESONATOR_SKILLS,
        (SELECT_RESONATOR_SKILLS_PAGE, SELECT_RESONATOR_SKILL_DETAIL),
    ),
    CaptureSpec(
        9,
        "resonator-chain",
        "09-resonator-chain.png",
        GameState.RESONATOR_CHAIN,
        (
            CLOSE_RESONATOR_SKILL_DETAIL,
            SELECT_RESONATOR_CHAIN,
            SELECT_RESONANCE_CHAIN_NODE,
        ),
    ),
    CaptureSpec(
        10,
        "achievements",
        "10-achievements.png",
        GameState.ACHIEVEMENTS,
        (CLOSE_RESONATOR, OPEN_ACHIEVEMENTS, SELECT_ACHIEVEMENTS_TAB),
    ),
    CaptureSpec(
        11,
        "shell-credit",
        "11-shell-credit.png",
        GameState.SHELL_CREDIT,
        (CLOSE_ACHIEVEMENTS,),
    ),
)
