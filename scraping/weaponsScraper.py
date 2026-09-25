import hashlib
from pathlib import Path

import cv2
import numpy as np

from scraping.utils import weaponsID, itemsID
from scraping.utils import (
    screenshot, convertToBlackWhite, imageToResult, imageToString,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from properties.config import basePATH, cfg
from scraping.cancellation import check_cancelled
from scraping.ocr_engine import INTEGER_PROFILE, LEVEL_PROFILE, NAME_PROFILE
from scraping.matching import (
    ITEM_NAME_CUTOFF,
    WEAPON_INVENTORY_NAME_CUTOFF,
    best_match,
)
from scraping.parsing import (
    ScanParseError,
    ascension_from_level_cap,
    parse_level_pair,
    parse_quantity,
)
from scraping.retry import retry_call
from scraping.review_queue import (
    DEFAULT_REVIEW_CONFIDENCE,
    write_review_metadata,
)

# Constants
ROWS, COLS = 4, 6


def _weapon_detail_crop(image: np.ndarray, screenInfo: ScreenInfo) -> np.ndarray:
    """Crop only the name/level/rank detail area used for weapon review."""
    regions = (
        screenInfo.weapons.name,
        screenInfo.weapons.level,
        screenInfo.weapons.rank,
    )
    left = min(int(region.x) for region in regions)
    top = min(int(region.y) for region in regions)
    right = max(int(region.x + region.w) for region in regions)
    bottom = max(int(region.y + region.h) for region in regions)
    return image[top:bottom, left:right]


def _save_weapon_review(
    path: Path,
    image: np.ndarray,
    screenInfo: ScreenInfo,
    *,
    fingerprint: str,
    ocr_result,
    reasons: tuple[str, ...],
    candidate: str | None,
) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    stem = f"weapon-{fingerprint[:16]}"
    image_path = path / f"{stem}.png"
    metadata_path = path / f"{stem}.json"

    if not image_path.exists():
        crop = _weapon_detail_crop(image, screenInfo)
        if crop.size == 0 or not cv2.imwrite(str(image_path), crop):
            raise OSError(f"Unable to save weapon review crop: {image_path}")

    write_review_metadata(
        metadata_path,
        scanner="weapons",
        reason="+".join(reasons),
        fingerprint=fingerprint,
        crop_file=image_path.name,
        ocr_result=ocr_result,
        owned=None,
    )
    return {
        "kind": "weapon",
        "image": image_path,
        "metadata": metadata_path,
        "owned": None,
        "candidate": candidate,
        "confidence": ocr_result.confidence,
        "reasons": reasons,
    }

WEAPON_ASCENSION_LEVELS = [20, 40, 50, 60, 70, 80, 90]

def getWeaponPages(screenInfo: ScreenInfo) -> int:
    def read_count() -> int:
        image = screenshot(
            width=screenInfo.width,
            height=screenInfo.height,
            monitor=screenInfo.monitor,
        )[
            screenInfo.weapons.page.y:
            screenInfo.weapons.page.y + screenInfo.weapons.page.h,
            screenInfo.weapons.page.x:
            screenInfo.weapons.page.x + screenInfo.weapons.page.w,
        ]
        image = convertToBlackWhite(image)
        weaponCountText = imageToString(
            image,
            profile=LEVEL_PROFILE,
        ).split('/')[0]
        try:
            return int(weaponCountText)
        except ValueError as exc:
            raise ValueError(
                f"Unable to parse weapon inventory count: {weaponCountText!r}"
            ) from exc

    weaponCount = retry_call(read_count, attempts=3, delay_seconds=0.2)
    return weaponCount, int(np.ceil(weaponCount / 24))

def processItem(name: str, valueText: str) -> tuple[str, int]:
    itemID = itemsID[name]['id']
    try:
        value = parse_quantity(valueText)
    except ScanParseError as exc:
        raise ValueError(
            f"Unable to parse item quantity from weapon inventory: {valueText!r}"
        ) from exc
    return itemID, value

def processWeapon(name: str, levelText: str, rankText: str) -> dict[str, dict[str, int]]:
    weaponID = weaponsID[name]['id']
    try:
        level, levelCap = parse_level_pair(levelText)
        ascension = ascension_from_level_cap(levelCap, WEAPON_ASCENSION_LEVELS)
        rank = int(rankText)
    except (ScanParseError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Unable to parse weapon values: level={levelText!r}, rank={rankText!r}"
        ) from exc

    return {
        weaponID: {
            'level': level,
            'ascension': ascension,
            'rank': rank
        }
    }

def processGridItem(
    inventory: dict,
    weapons: list,
    reviews: list,
    review_path: Path,
    image: np.ndarray,
    screenInfo: ScreenInfo,
    _cache: dict,
) -> bool:

    nameImage = image[
        screenInfo.weapons.name.y:
        screenInfo.weapons.name.y + screenInfo.weapons.name.h,
        screenInfo.weapons.name.x:
        screenInfo.weapons.name.x + screenInfo.weapons.name.w,
    ]
    nameImage = convertToBlackWhite(nameImage)
    nameFingerprint = hashlib.sha256(nameImage.tobytes()).hexdigest()
    nameCacheKey = ("weapon-name", nameFingerprint)

    if nameCacheKey in _cache:
        name, nameResult = _cache[nameCacheKey]
    else:
        nameResult = imageToResult(nameImage, profile=NAME_PROFILE)
        rawName = nameResult.text.lower()
        name = best_match(
            rawName,
            weaponsID,
            cutoff=WEAPON_INVENTORY_NAME_CUTOFF,
        )
        if name is None:
            name = best_match(
                rawName,
                itemsID,
                cutoff=ITEM_NAME_CUTOFF,
            )
        _cache[nameCacheKey] = (name, nameResult)

    reviewReasons = []
    if name is None:
        reviewReasons.append("unknown_name")
    if nameResult.confidence < DEFAULT_REVIEW_CONFIDENCE:
        reviewReasons.append("low_confidence")

    if reviewReasons:
        reviews.append(
            _save_weapon_review(
                review_path,
                image,
                screenInfo,
                fingerprint=nameFingerprint,
                ocr_result=nameResult,
                reasons=tuple(reviewReasons),
                candidate=name,
            )
        )
        return True
    
    if name in itemsID:
        valueImage = image[screenInfo.weapons.value.y:screenInfo.weapons.value.y + screenInfo.weapons.value.h, screenInfo.weapons.value.x:screenInfo.weapons.value.x + screenInfo.weapons.value.w]
        valueImage = convertToBlackWhite(valueImage)
        valueHash = hash(valueImage.tobytes())

        if valueHash in _cache:
            valueText = _cache[valueHash]
        else:
            valueText = imageToString(valueImage, profile=INTEGER_PROFILE)
            _cache[valueHash] = valueText
        
        itemID, value = processItem(name, valueText)
        inventory[itemID] = value
        return True
    elif name in weaponsID:
        if weaponsID[name]['rarity'] >= cfg.get(cfg.weaponsMinRarity):
            levelImage = image[screenInfo.weapons.level.y:screenInfo.weapons.level.y + screenInfo.weapons.level.h, screenInfo.weapons.level.x:screenInfo.weapons.level.x + screenInfo.weapons.level.w]
            # levelImage = convertToBlackWhite(levelImage)
            levelHash = hash(levelImage.tobytes())

            if levelHash in _cache:
                levelText = _cache[levelHash]
            else:
                levelText = imageToString(levelImage, profile=LEVEL_PROFILE)
                _cache[levelHash] = levelText
            
            try:
                currentLevel, _ = parse_level_pair(levelText)
            except ScanParseError as exc:
                raise ValueError(
                    f"Unable to parse weapon level from OCR result: {levelText!r}"
                ) from exc

            if currentLevel >= cfg.get(cfg.weaponsMinLevel):
                rankImage = image[screenInfo.weapons.rank.y:screenInfo.weapons.rank.y + screenInfo.weapons.rank.h, screenInfo.weapons.rank.x:screenInfo.weapons.rank.x + screenInfo.weapons.rank.w]
                rankImage = convertToBlackWhite(rankImage)
                rankHash = hash(rankImage.tobytes())

                if rankHash in _cache:
                    rankText = _cache[rankHash]
                else:
                    rankText = imageToString(rankImage, profile=INTEGER_PROFILE)
                    _cache[rankHash] = rankText
                weapons.append(processWeapon(name, levelText, rankText))
        return True
    return True

def weaponScraper(
    controller: WindowsInputController,
    x: float,
    y: float,
    screenInfo: ScreenInfo,
    cancel_event=None,
    start_date: str = "",
) -> tuple[dict[str, int], list[dict[str, dict[str, int]]], list[dict]]:
    inventory = dict()
    weapons = list()
    reviews = list()
    _cache = dict()
    review_path = basePATH / "logs" / "fail" / start_date

    check_cancelled(cancel_event)
    controller.pressKey(cfg.get(cfg.inventoryKeybind), 2, False)
    controller.leftClick(x, y)

    weaponCount, pages = getWeaponPages(screenInfo)
    continueScraping = False

    for page in range(pages):
        check_cancelled(cancel_event)
        for row in range(ROWS):
            for col in range(COLS):
                check_cancelled(cancel_event)
                global_index = page * (ROWS * COLS) + row * COLS + col
                if global_index >= weaponCount:
                    del _cache
                    return inventory, weapons, reviews

                center_x = screenInfo.weapons.start.x + (col * (screenInfo.weapons.start.w + screenInfo.offsets.page.x)) + screenInfo.weapons.start.w // 2
                center_y = screenInfo.weapons.start.y + (row * (screenInfo.weapons.start.h + screenInfo.offsets.page.y)) + screenInfo.weapons.start.h // 2
                
                controller.leftClick(center_x, center_y)
                image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor)
                
                continueScraping = processGridItem(
                    inventory,
                    weapons,
                    reviews,
                    review_path,
                    image,
                    screenInfo,
                    _cache,
                )
                if not continueScraping:
                    del _cache
                    return inventory, weapons

        if page < pages - 1 and continueScraping:
            controller.mouseScroll(screenInfo.scroll.page.y, 1.2)

    del _cache
    return inventory, weapons