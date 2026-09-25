import os
import hashlib
from pathlib import Path

import cv2
import logging
import numpy as np
from collections import defaultdict

from scraping.utils import (
    echoesID, echoStats, sonataName
)
from scraping.utils import (
    screenshot, imageToResult, imageToString, convertToBlackWhite,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from properties.config import basePATH, cfg
from scraping.cancellation import check_cancelled
from scraping.ocr_engine import (
    LEVEL_PROFILE,
    STAT_NAME_PROFILE,
    STAT_VALUE_PROFILE,
    require_confidence,
)
from scraping.matching import ECHO_NAME_CUTOFF, best_match
from scraping.parsing import ScanParseError, parse_stat_value
from scraping.retry import retry_call
from scraping.review_queue import (
    DEFAULT_REVIEW_CONFIDENCE,
    write_review_metadata,
)

logger = logging.getLogger('EchoScraper')

# Constants
ROWS, COLS = 4, 6

def matchStats(text):
    stats = set(echoStats)
    results = []
    i = 0
    while i < len(text):
        if i < len(text) - 1:
            combinedWord = text[i] + text[i + 1]
            if combinedWord in stats:
                results.append(combinedWord)
                i += 2
                continue
        if text[i] in stats:
            results.append(text[i])
        i += 1
    return results

def setupRarityDetection():
    rarityColors = {
        5: np.array([90, 230, 255]),
        4: np.array([255, 109, 202]),
        3: np.array([211, 180, 89]),
        2: np.array([94, 195, 92]),
        1: np.array([225, 236, 239])
    }

    tolerance = 10
    bounds = {rarity: (color - tolerance, color + tolerance) for rarity, color in rarityColors.items()}

    return bounds

RARITY_BOUNDS = setupRarityDetection()

def getRarity(image: np.ndarray):
    for rarity, (lower, upper) in RARITY_BOUNDS.items():
        if np.any(cv2.inRange(image, lower, upper)):
            return rarity
    return None

def getEchoPages(screenInfo: ScreenInfo) -> int:
    def read_count() -> int:
        image = screenshot(
            width=screenInfo.width,
            height=screenInfo.height,
            monitor=screenInfo.monitor,
        )[
            screenInfo.echoes.page.y:
            screenInfo.echoes.page.y + screenInfo.echoes.page.h,
            screenInfo.echoes.page.x:
            screenInfo.echoes.page.x + screenInfo.echoes.page.w,
        ]
        echoCountText = imageToString(
            image,
            profile=LEVEL_PROFILE,
        ).split('/')[0]

        try:
            return int(echoCountText)
        except ValueError as exc:
            raise ValueError(
                f"Unable to parse echo inventory count: {echoCountText!r}"
            ) from exc

    echoCount = retry_call(read_count, attempts=3, delay_seconds=0.2)
    return echoCount, int(np.ceil(echoCount / 24))

def processEcho(name: str, level: int, tuneLv: int, sonata: str, rarity: int, stats: dict) -> dict[str, dict[int, int, dict]]:
    if name not in echoesID:
        raise ValueError(f"Unknown echo mapping key: {name!r}")

    echoID = str(echoesID[name])
    return {
        echoID: {
            'level': level,
            'tuneLv': tuneLv,
            'sonata': sonata,
            'rarity': rarity,
            'stats': stats
        }
    }

def processStats(image: np.ndarray, screenInfo: ScreenInfo, _cache: dict) -> dict[str:int]:
    stats = defaultdict(dict)
    tuneLv = 0

    nameImage = image[
        screenInfo.echoes.fullStatsName.y:screenInfo.echoes.fullStatsName.y + screenInfo.echoes.fullStatsName.h,
        screenInfo.echoes.fullStatsName.x:screenInfo.echoes.fullStatsName.x + screenInfo.echoes.fullStatsName.w
    ]
    nameImage = convertToBlackWhite(nameImage)
    nameHash = hash(nameImage.tobytes())

    valueImage = image[
        screenInfo.echoes.fullStatsValue.y:screenInfo.echoes.fullStatsValue.y + screenInfo.echoes.fullStatsValue.h,
        screenInfo.echoes.fullStatsValue.x:screenInfo.echoes.fullStatsValue.x + screenInfo.echoes.fullStatsValue.w
    ]
    valueImage = convertToBlackWhite(valueImage)
    valueHash = hash(valueImage.tobytes())

    if nameHash in _cache:
        names = _cache[nameHash]
    else:
        names = imageToString(nameImage, profile=STAT_NAME_PROFILE).lower().split('\n')
        names = matchStats(names)
        _cache[nameHash] = names

    if valueHash in _cache:
        values = _cache[valueHash]
    else:
        values = imageToString(valueImage, profile=STAT_VALUE_PROFILE).split()
        _cache[valueHash] = values
    if len(names) != len(values) or len(names) < 2:
        raise ValueError(
            "Echo stat OCR produced mismatched fields: "
            f"names={names!r}, values={values!r}"
        )

    tuneLv = max(0, len(values) - 2)

    for index, (statName, statValue) in enumerate(zip(names, values)):
        statName = echoStats.get(statName, statName)

        if index < 2: stat = 'main'
        else: stat = 'sub'
        
        try:
            value, isPercentage = parse_stat_value(statValue)
        except ScanParseError as exc:
            raise ValueError(
                f"Unable to parse echo stat value {statValue!r} for {statName!r}"
            ) from exc

        key = f"{statName}%" if isPercentage else statName
        stats[stat].update({key: value})

    return tuneLv, dict(stats)

def getSonata(controller: WindowsInputController, screenInfo: ScreenInfo, _cache: dict):
    controller.moveMouse(screenInfo.echoes.mouseMovement.x, screenInfo.echoes.mouseMovement.y, .2)
    controller.mouseScroll(-screenInfo.scroll.sonata.y, .3)

    try:
        image = screenshot(
            screenInfo.echoes.sonata.x,
            screenInfo.echoes.sonata.y,
            screenInfo.echoes.sonata.w,
            screenInfo.echoes.sonata.h,
            monitor=screenInfo.monitor,
        )
        sonataHash = hash(image.tobytes())

        if sonataHash in _cache:
            return _cache[sonataHash]

        sonataResult = require_confidence(
            imageToResult(image, '', bannedChars=' '),
            field="echo-sonata",
        )
        ocrText = sonataResult.text.lower()
        for name in sonataName:
            if name in ocrText:
                _cache[sonataHash] = name
                return name

        raise ValueError(
            f"Unable to identify echo sonata from OCR result: {ocrText!r}"
        )
    finally:
        controller.moveMouse(
            screenInfo.echoes.mouseMovement.x,
            screenInfo.echoes.mouseMovement.y,
            .2,
        )
        controller.mouseScroll(screenInfo.scroll.sonata.y, .3)

def processGridEcho(
    controller: WindowsInputController,
    screenInfo: ScreenInfo,
    echoes: list,
    reviews: list,
    review_path: Path,
    image: np.ndarray,
    _cache: dict,
) -> bool:

    echoCard = image[
        screenInfo.echoes.echoCard.y:
        screenInfo.echoes.echoCard.y + screenInfo.echoes.echoCard.h,
        screenInfo.echoes.echoCard.x:
        screenInfo.echoes.echoCard.x + screenInfo.echoes.echoCard.w,
    ]
    echoFingerprint = hashlib.sha256(echoCard.tobytes()).hexdigest()
    infoKey = ("echo-info", echoFingerprint)
    resultKey = ("echo-ocr", echoFingerprint)

    if infoKey in _cache:
        info = _cache[infoKey]
        echoCardResult = _cache[resultKey]
    else:
        echoCardResult = imageToResult(
            echoCard,
            '',
            bannedChars=' +',
        )
        info = [echoCardResult.text.lower().split('\n')]
        _cache[infoKey] = info
        _cache[resultKey] = echoCardResult

    rawName = info[0][0] if info and info[0] else ""
    result = best_match(rawName, echoesID, cutoff=ECHO_NAME_CUTOFF)

    reviewReasons = []
    if result is None:
        reviewReasons.append("unknown_name")
    if echoCardResult.confidence < DEFAULT_REVIEW_CONFIDENCE:
        reviewReasons.append("low_confidence")

    if reviewReasons:
        review_path.mkdir(parents=True, exist_ok=True)
        stem = f"echo-{echoFingerprint[:16]}"
        imagePath = review_path / f"{stem}.png"
        metadataPath = review_path / f"{stem}.json"
        if not imagePath.exists():
            if echoCard.size == 0 or not cv2.imwrite(str(imagePath), echoCard):
                raise OSError(f"Unable to save Echo review crop: {imagePath}")

        write_review_metadata(
            metadataPath,
            scanner="echoes",
            reason="+".join(reviewReasons),
            fingerprint=echoFingerprint,
            crop_file=imagePath.name,
            ocr_result=echoCardResult,
            owned=None,
            candidate=result,
        )
        reviews.append({
            "kind": "echo",
            "image": imagePath,
            "metadata": metadataPath,
            "owned": None,
            "candidate": result,
            "confidence": echoCardResult.confidence,
            "reasons": tuple(reviewReasons),
        })
        return True

    name = result

    if name in echoesID:
        if len(info) > 1:
            rarity = info[1]
        else:
            rarity = getRarity(echoCard)
            if rarity is None:
                raise ValueError(f"Unable to determine echo rarity for {name!r}")
            _cache[infoKey].append(rarity)

        if rarity >= cfg.get(cfg.echoMinRarity):
            if len(info[0]) <= 2:
                raise ValueError(
                    f"Echo level OCR was incomplete for {name!r}: {info[0]!r}"
                )
            levelText = info[0][2]
            
            try:
                level = int(levelText)
            except ValueError as exc:
                raise ValueError(
                    f"Unable to parse echo level from OCR result: {levelText!r}"
                ) from exc
            level = min(25, level)

            if level >= cfg.get(cfg.echoMinLevel):
                tuneLv, stats = processStats(image, screenInfo, _cache)
                sonata = getSonata(controller, screenInfo, _cache)
                echoes.append(processEcho(name, level, tuneLv, sonata, rarity, stats))

        # Rarity/level filters decide whether this echo is exported; they must
        # not terminate scanning because later slots may still qualify.
        return True

    return True

def echoScraper(
    controller: WindowsInputController,
    x: float,
    y: float,
    screenInfo: ScreenInfo,
    cancel_event=None,
    start_date: str = "",
) -> tuple[list[dict], list[dict]]:
    echoes = list()
    reviews = list()
    _cache = dict()
    review_path = basePATH / "logs" / "fail" / start_date

    check_cancelled(cancel_event)
    controller.pressKey(cfg.get(cfg.inventoryKeybind), 2, False)
    controller.leftClick(x, y)

    echoCount, pages = getEchoPages(screenInfo)
    continueScraping = False

    for page in range(pages):
        check_cancelled(cancel_event)
        for row in range(ROWS):
            for col in range(COLS):
                check_cancelled(cancel_event)
                global_index = page * (ROWS * COLS) + row * COLS + col
                if global_index >= echoCount:
                    del _cache
                    return echoes, reviews
                center_x = screenInfo.echoes.start.x + (col * (screenInfo.echoes.start.w + screenInfo.offsets.page.x)) + screenInfo.echoes.start.w // 2
                center_y = screenInfo.echoes.start.y + (row * (screenInfo.echoes.start.h + screenInfo.offsets.page.y)) + screenInfo.echoes.start.h // 2
                
                controller.leftClick(center_x, center_y)
                image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor)
                
                continueScraping = processGridEcho(
                    controller,
                    screenInfo,
                    echoes,
                    reviews,
                    review_path,
                    image,
                    _cache,
                )
                if not continueScraping:
                    del _cache
                    return echoes, reviews

        if page < pages - 1 and continueScraping:
            controller.mouseScroll(screenInfo.scroll.page.y, 1.2)

    del _cache
    return echoes, reviews
