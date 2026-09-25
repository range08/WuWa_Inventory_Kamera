import time
import string
import logging
import numpy as np
from collections import defaultdict

from scraping.utils import charactersID, weaponsID, definedText
from scraping.utils import (
    screenshot, convertToBlackWhite, imageToString,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from properties.config import cfg
from scraping.ocr_engine import (
    INTEGER_PROFILE,
    LEVEL_PROFILE,
    NAME_PROFILE,
)
from scraping.matching import (
    EQUIPPED_WEAPON_NAME_CUTOFF,
    RESONATOR_NAME_CUTOFF,
    best_match,
)
from scraping.parsing import (
    ScanParseError,
    ascension_from_level_cap,
    parse_level_pair,
)

logger = logging.getLogger('CharacterScraper')

# Constants
SKILL_LEGENDS = {
    0: 'normal',
    1: 'resonance',
    2: 'forte',
    3: 'liberation',
    4: 'intro'
}
ASCENSION_LEVELS = [20, 40, 50, 60, 70, 80, 90]
MAX_RESONATOR_VIEWPORTS = 128

def scrapeResonator(image: np.ndarray, screenInfo: ScreenInfo, characters: dict, nameCache: dict, _cache: dict) -> tuple[str, bool]:
    resonatorNameImage = image[screenInfo.characters.resonatorName.y:screenInfo.characters.resonatorName.y + screenInfo.characters.resonatorName.h, screenInfo.characters.resonatorName.x:screenInfo.characters.resonatorName.x + screenInfo.characters.resonatorName.w]
    resonatorNameImage = convertToBlackWhite(resonatorNameImage)
    resonatorNameHash = hash(resonatorNameImage.tobytes())

    if resonatorNameHash in nameCache:
        resonatorID = nameCache[resonatorNameHash]
    else:
        resonatorName = imageToString(resonatorNameImage, profile=NAME_PROFILE).lower()

        result = best_match(
            resonatorName,
            charactersID,
            cutoff=RESONATOR_NAME_CUTOFF,
        )
        if result:
            resonatorName = result

        roverName = cfg.get(cfg.roverName).replace(' ', '').lower()
        if resonatorName == roverName:
            resonatorID = '1502'
        elif resonatorName in charactersID:
            resonatorID = charactersID[resonatorName]
        else:
            raise ValueError(
                f"Unable to identify resonator from OCR result: {resonatorName!r}"
            )
        nameCache[resonatorNameHash] = resonatorID

    if resonatorID in characters:
        return resonatorID, True

    levelImage = image[screenInfo.characters.resonatorLevel.y:screenInfo.characters.resonatorLevel.y + screenInfo.characters.resonatorLevel.h, screenInfo.characters.resonatorLevel.x:screenInfo.characters.resonatorLevel.x + screenInfo.characters.resonatorLevel.w]
    levelImage = convertToBlackWhite(levelImage)
    levelHash = hash(levelImage.tobytes())

    if levelHash in _cache:
        levelText = _cache[levelHash]
    else:
        levelText = imageToString(levelImage, profile=LEVEL_PROFILE)
        _cache[levelHash] = levelText

    try:
        characterLvl, levelCap = parse_level_pair(levelText)
        ascensionLvl = ascension_from_level_cap(levelCap, ASCENSION_LEVELS)
    except ScanParseError as exc:
        raise ValueError(
            f"Unable to parse resonator level from OCR result: {levelText!r}"
        ) from exc

    characters[resonatorID]['level'] = characterLvl
    characters[resonatorID]['ascension'] = ascensionLvl

    return resonatorID, False

def scrapeWeapon(image: np.ndarray, screenInfo: ScreenInfo, characters: dict, resonatorID: str, _cache: dict):
    weaponNameImage = image[screenInfo.characters.weaponName.y:screenInfo.characters.weaponName.y + screenInfo.characters.weaponName.h, screenInfo.characters.weaponName.x:screenInfo.characters.weaponName.x + screenInfo.characters.weaponName.w]
    weaponNameImage = convertToBlackWhite(weaponNameImage)
    weaponNameHash = hash(weaponNameImage.tobytes())

    if weaponNameHash in _cache:
        weaponID = _cache[weaponNameHash]
    else:
        weaponName = imageToString(weaponNameImage, profile=NAME_PROFILE).lower()
    
        result = best_match(
            weaponName,
            weaponsID,
            cutoff=EQUIPPED_WEAPON_NAME_CUTOFF,
        )
        if result:
            weaponName = result
        
        if weaponName not in weaponsID:
            raise ValueError(
                f"Unable to identify equipped weapon from OCR result: {weaponName!r}"
            )
        weaponID = weaponsID[weaponName]['id']
        _cache[weaponNameHash] = weaponID
    
    levelImage = image[screenInfo.characters.weaponLevel.y:screenInfo.characters.weaponLevel.y + screenInfo.characters.weaponLevel.h, screenInfo.characters.weaponLevel.x:screenInfo.characters.weaponLevel.x + screenInfo.characters.weaponLevel.w]
    levelImage = convertToBlackWhite(levelImage)
    levelHash = hash(levelImage.tobytes())
    
    if levelHash in _cache:
        levelText = _cache[levelHash]
    else:
        levelText = imageToString(levelImage, profile=LEVEL_PROFILE)
        _cache[levelHash] = levelText
    
    rankImage = image[screenInfo.characters.weaponRank.y:screenInfo.characters.weaponRank.y + screenInfo.characters.weaponRank.h, screenInfo.characters.weaponRank.x:screenInfo.characters.weaponRank.x + screenInfo.characters.weaponRank.w]
    rankImage = convertToBlackWhite(rankImage)
    rankHash = hash(rankImage.tobytes())

    if rankHash in _cache:
        rank = _cache[rankHash]
    else:
        rank = imageToString(rankImage, profile=INTEGER_PROFILE)
        _cache[rankHash] = rank

    try:
        weaponLevel, levelCap = parse_level_pair(levelText)
        weaponAscension = ascension_from_level_cap(levelCap, ASCENSION_LEVELS)
        weaponRank = int(rank)
    except (ScanParseError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Unable to parse equipped weapon values: level={levelText!r}, rank={rank!r}"
        ) from exc

    characters[resonatorID]['weapon']['id'] = weaponID
    characters[resonatorID]['weapon']['level'] = weaponLevel
    characters[resonatorID]['weapon']['ascension'] = weaponAscension
    characters[resonatorID]['weapon']['rank'] = weaponRank

def scrapeSkills(controller: WindowsInputController, screenInfo: ScreenInfo, characters: dict, resonatorID: str, _cache: dict):
    controller.leftClick(screenInfo.characters.skillClick.x, screenInfo.characters.skillClick.y, .5)

    try:
        for index, skills in enumerate(screenInfo.characters.skillPositions):
            controller.leftClick(skills.x, skills.y)

            image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor, bw=True)

            levelImage = image[screenInfo.characters.skillLevel.y:screenInfo.characters.skillLevel.y + screenInfo.characters.skillLevel.h, screenInfo.characters.skillLevel.x:screenInfo.characters.skillLevel.x + screenInfo.characters.skillLevel.w]
            levelHash = hash(levelImage.tobytes())

            if levelHash in _cache:
                level = _cache[levelHash]
            else:
                level = imageToString(levelImage, profile=INTEGER_PROFILE)
                _cache[levelHash] = level

            try:
                level = int(level)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Unable to parse skill level from OCR result: {level!r}"
                ) from exc

            characters[resonatorID]['skills'][SKILL_LEGENDS[index]] = level

            for y in range(1, 3):
                controller.leftClick(
                    skills.x,
                    skills.y - (screenInfo.characters.offsets.skillPosition.y * y),
                    .6,
                )

                buttonImage = screenshot(
                    screenInfo.characters.skillButton.x,
                    screenInfo.characters.skillButton.y,
                    screenInfo.characters.skillButton.w,
                    screenInfo.characters.skillButton.h,
                    monitor=screenInfo.monitor,
                    bw=True,
                )
                buttonHash = hash(buttonImage.tobytes())

                if buttonHash in _cache:
                    button = _cache[buttonHash]
                else:
                    button = imageToString(buttonImage).lower()
                    _cache[buttonHash] = button

                if button.lower() == definedText['PrefabTextItem_3963945691_Text']: # MULTILANG
                    key = 'inherent' if index == 2 else f'stats{index}'
                    characters[resonatorID]['skills'][key] += 1
                else:
                    break
    finally:
        controller.pressKey('esc')

def scrapeChain(controller: WindowsInputController, screenInfo: ScreenInfo, characters: dict, resonatorID: str, _cache: dict):
    controller.leftClick(screenInfo.characters.chainClick.x, screenInfo.characters.chainClick.y, .7)

    try:
        for position in screenInfo.characters.chainPositions:
            controller.leftClick(position.x, position.y, .2)

            statusImage = screenshot(
                screenInfo.characters.chainButton.x,
                screenInfo.characters.chainButton.y,
                screenInfo.characters.chainButton.w,
                screenInfo.characters.chainButton.h,
                monitor=screenInfo.monitor,
            )
            statusHash = hash(statusImage.tobytes())

            if statusHash in _cache:
                status = _cache[statusHash]
            else:
                status = imageToString(
                    statusImage,
                    '',
                    bannedChars=f'{string.punctuation} ',
                ).lower()
                _cache[statusHash] = status

            if status.lower() != definedText['PrefabTextItem_3963945691_Text']: # MULTILANG
                break

            characters[resonatorID]['chain'] += 1
    finally:
        controller.pressKey('esc')

def resonatorScraper(controller: WindowsInputController, screenInfo: ScreenInfo):
    characters = defaultdict(
        lambda: defaultdict(
            int,
            {
                'level': 0,
                'ascension': 0,
                'weapon': defaultdict(
                    int,
                    {
                        'id': 0,
                        'level': 1,
                        'ascension': 0,
                        'rank': 0
                    }
                ),
                'echoes': dict(),
                'skills': defaultdict(
                    int,
                    {
                        'normal': 1,
                        'resonance': 1,
                        'forte': 1,
                        'liberation': 1,
                        'intro': 1,
                        'stats0': 0,
                        'stats1': 0,
                        'inherent': 0,
                        'stats3': 0,
                        'stats4': 0
                    }
                ),
                'chain': 0
            }
        )
    )
    _cache = dict()
    nameCache = dict()

    controller.pressKey(cfg.get(cfg.resonatorKeybind), 2, False)

    xLeftSide, yLeftSide = screenInfo.characters.leftSide.x, screenInfo.characters.leftSide.y
    xRightSide, yRightSide = screenInfo.characters.rightSide.x, screenInfo.characters.rightSide.y

    for _ in range(MAX_RESONATOR_VIEWPORTS):
        newResonators = 0

        for resonatorIndex in range(7):
            controller.leftClick(
                xRightSide,
                yRightSide + (screenInfo.characters.offsets.rightSide.y * resonatorIndex),
                .7,
            )
            resonatorID = str()
            alreadySeen = False

            for section in range(5):
                controller.leftClick(
                    xLeftSide,
                    yLeftSide + (screenInfo.characters.offsets.leftSide.y * section),
                    .8,
                )

                image = screenshot(
                    width=screenInfo.width,
                    height=screenInfo.height,
                    monitor=screenInfo.monitor,
                    bw=True,
                )

                match(section):
                    case 0:
                        resonatorID, alreadySeen = scrapeResonator(
                            image,
                            screenInfo,
                            characters,
                            nameCache,
                            _cache,
                        )
                        if alreadySeen:
                            break
                        newResonators += 1
                    case 1:
                        scrapeWeapon(image, screenInfo, characters, resonatorID, _cache)
                    case 2:
                        pass  # Skip echoes for now
                    case 3:
                        scrapeSkills(controller, screenInfo, characters, resonatorID, _cache)
                    case 4:
                        scrapeChain(controller, screenInfo, characters, resonatorID, _cache)

                time.sleep(.5)

        # Overlapping scroll positions can repeat some characters. Only stop
        # once an entire seven-slot viewport contains no unseen resonator.
        if newResonators == 0:
            return dict(characters)

        controller.moveMouse(xRightSide, yRightSide, .3)
        controller.mouseScroll(screenInfo.scroll.characters.y, .5)

    raise RuntimeError(
        f"Character scanner exceeded {MAX_RESONATOR_VIEWPORTS} viewports without detecting the end of the resonator list."
    )

