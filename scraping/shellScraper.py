import logging

from scraping.utils import (
    screenshot, imageToString
)
from game.screenInfo import ScreenInfo
from scraping.ocr_engine import INTEGER_PROFILE

logger = logging.getLogger('ShellScraper')


def getShell(screenInfo: ScreenInfo):
    xShell, yShell, wShell, hShell = (
        screenInfo.shell.x,
        screenInfo.shell.y,
        screenInfo.shell.w,
        screenInfo.shell.h,
    )

    image = screenshot(xShell, yShell, wShell, hShell, screenInfo.monitor, True)
    shellText = imageToString(image, profile=INTEGER_PROFILE).strip()

    try:
        shell = int(shellText)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Unable to parse Shell Credit quantity: {shellText!r}"
        ) from exc

    return {'2': shell}
