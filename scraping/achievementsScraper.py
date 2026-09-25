import numpy as np

from scraping.utils import (
    achievementsID, definedText, copyToClipboard
)
from scraping.utils import (
    screenshot, imageToResult, convertToBlackWhite,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from scraping.cancellation import check_cancelled
from scraping.ocr_engine import require_confidence

def processAchievement(image: np.ndarray, screenInfo: ScreenInfo, achievementName: str, _cache: dict) -> str | None:
    statusImage = image[screenInfo.achievements.status.y:screenInfo.achievements.status.y + screenInfo.achievements.status.h, screenInfo.achievements.status.x:screenInfo.achievements.status.x + screenInfo.achievements.status.w]
    statusImage = convertToBlackWhite(statusImage)
    statusHash = hash(statusImage.tobytes())
    if statusHash in _cache: statusText = _cache[statusHash]
    else:
        statusResult = require_confidence(
            imageToResult(statusImage),
            field="achievement-status",
        )
        statusText = statusResult.text.lower()
        _cache[statusHash] = statusText

    if statusText == definedText['PrefabTextItem_128820487_Text'] or '/' in statusText: # MULTILANG
        return achievementsID[achievementName]
    
    return None

def achievementScraper(controller: WindowsInputController, screenInfo: ScreenInfo, cancel_event=None) -> list[str]:
    achievements = []
    _cache = dict()

    check_cancelled(cancel_event)
    controller.pressKey('esc', 1)
    controller.leftClick(screenInfo.achievements.achievementsButton.x, screenInfo.achievements.achievementsButton.y, 1.2)
    controller.leftClick(screenInfo.achievements.achievementsTab.x, screenInfo.achievements.achievementsTab.y, 1)

    for achievementName in achievementsID:
        check_cancelled(cancel_event)
        copyToClipboard(achievementName)
        controller.leftClick(screenInfo.achievements.searchBar.x, screenInfo.achievements.searchBar.y, .3)
        controller.hotKey('ctrl', 'v', waitTime=.3)
        controller.leftClick(screenInfo.achievements.searchButton.x, screenInfo.achievements.searchButton.y, .6)

        image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor)
        achievement = processAchievement(image, screenInfo, achievementName, _cache)
        if achievement:
            achievements.append(achievement)
        
        controller.leftClick(screenInfo.achievements.searchButton.x, screenInfo.achievements.searchButton.y)
    
    controller.pressKey('esc', .5)
    del _cache
    return achievements