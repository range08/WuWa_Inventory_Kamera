import numpy as np

from scraping.utils import weaponsID, itemsID
from scraping.utils import (
    screenshot, convertToBlackWhite, imageToString,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from properties.config import cfg
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

# Constants
ROWS, COLS = 4, 6
WEAPON_ASCENSION_LEVELS = [20, 40, 50, 60, 70, 80, 90]

def getWeaponPages(screenInfo: ScreenInfo) -> int:
    image = convertToBlackWhite(screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor)[screenInfo.weapons.page.y:screenInfo.weapons.page.y + screenInfo.weapons.page.h, screenInfo.weapons.page.x:screenInfo.weapons.page.x + screenInfo.weapons.page.w])
    weaponCountText = imageToString(
        image, profile=LEVEL_PROFILE
    ).split('/')[0]
    try:
        weaponCount = int(weaponCountText)
    except ValueError as exc:
        raise ValueError(
            f"Unable to parse weapon inventory count: {weaponCountText!r}"
        ) from exc
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

def processGridItem(inventory: dict, weapons: list, image: np.ndarray, screenInfo: ScreenInfo, _cache: dict) -> tuple[dict[str, int], list[dict[str, dict[str, int]]]]:

    nameImage = image[screenInfo.weapons.name.y:screenInfo.weapons.name.y + screenInfo.weapons.name.h, screenInfo.weapons.name.x:screenInfo.weapons.name.x + screenInfo.weapons.name.w]
    nameImage = convertToBlackWhite(nameImage)
    nameHash = hash(nameImage.tobytes())

    if nameHash in _cache:
        name = _cache[nameHash]
    else:
        name = imageToString(nameImage, profile=NAME_PROFILE).lower()
        result = best_match(
            name,
            weaponsID,
            cutoff=WEAPON_INVENTORY_NAME_CUTOFF,
        )
        if result is None:
            result = best_match(
                name,
                itemsID,
                cutoff=ITEM_NAME_CUTOFF,
            )
        if result is None:
            raise ValueError(
                f"Unable to identify weapon inventory entry from OCR result: {name!r}"
            )

        _cache[nameHash] = result
        name = result
    
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

def weaponScraper(controller: WindowsInputController, x: float, y: float, screenInfo: ScreenInfo) -> tuple[dict[str, int], list[dict[str, dict[str, int]]]]:
    inventory = dict()
    weapons = list()
    _cache = dict()

    controller.pressKey(cfg.get(cfg.inventoryKeybind), 2, False)
    controller.leftClick(x, y)

    weaponCount, pages = getWeaponPages(screenInfo)
    continueScraping = False

    for page in range(pages):
        for row in range(ROWS):
            for col in range(COLS):
                global_index = page * (ROWS * COLS) + row * COLS + col
                if global_index >= weaponCount:
                    del _cache
                    return inventory, weapons

                center_x = screenInfo.weapons.start.x + (col * (screenInfo.weapons.start.w + screenInfo.offsets.page.x)) + screenInfo.weapons.start.w // 2
                center_y = screenInfo.weapons.start.y + (row * (screenInfo.weapons.start.h + screenInfo.offsets.page.y)) + screenInfo.weapons.start.h // 2
                
                controller.leftClick(center_x, center_y)
                image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor)
                
                continueScraping = processGridItem(inventory, weapons, image, screenInfo, _cache)
                if not continueScraping:
                    del _cache
                    return inventory, weapons

        if page < pages - 1 and continueScraping:
            controller.mouseScroll(screenInfo.scroll.page.y, 1.2)

    del _cache
    return inventory, weapons