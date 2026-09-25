import logging

from scraping.utils import (
    screenshot, imageToResult
)
from game.screenInfo import ScreenInfo
from scraping.ocr_engine import INTEGER_PROFILE, require_confidence
from scraping.retry import retry_call

logger = logging.getLogger('ShellScraper')


def getShell(screenInfo: ScreenInfo):
    xShell, yShell, wShell, hShell = (
        screenInfo.shell.x,
        screenInfo.shell.y,
        screenInfo.shell.w,
        screenInfo.shell.h,
    )

    def read_shell() -> int:
        image = screenshot(
            xShell,
            yShell,
            wShell,
            hShell,
            screenInfo.monitor,
            True,
        )
        shellResult = require_confidence(
            imageToResult(image, profile=INTEGER_PROFILE),
            field="shell-credit",
        )
        shellText = shellResult.text.strip()

        try:
            return int(shellText)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Unable to parse Shell Credit quantity: {shellText!r}"
            ) from exc

    shell = retry_call(read_shell, attempts=3, delay_seconds=0.2)
    return {'2': shell}
