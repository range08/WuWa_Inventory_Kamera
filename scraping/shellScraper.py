import logging
import string

from scraping.utils import (
    screenshot, imageToString
)
from game.screenInfo import ScreenInfo

logger = logging.getLogger('ShellScraper')


def getShell(screenInfo: ScreenInfo):
    xShell, yShell, wShell, hShell = (
        screenInfo.shell.x,
        screenInfo.shell.y,
        screenInfo.shell.w,
        screenInfo.shell.h,
    )

    image = screenshot(xShell, yShell, wShell, hShell, screenInfo.monitor, True)
    shellText = imageToString(image, allowedChars=string.digits).strip()

    try:
        shell = int(shellText)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Unable to parse Shell Credit quantity: {shellText!r}"
        ) from exc

    return {'2': shell}
