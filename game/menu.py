import time
import logging
from difflib import get_close_matches as getMatches

from game.foreground import WindowManager
from scraping.utils.common import definedText
from scraping.utils import screenshot
from scraping.ocr_engine import NAME_PROFILE
from scraping.utils import imageToResult

logger = logging.getLogger('MainMenuController')

class MainMenuController:
    """Handles interactions with the screen and performs actions based on visual content."""

    @staticmethod
    def inspect_image(image) -> dict:
        """Return structured OCR evidence for the calibrated Terminal ROI."""
        result = imageToResult(image, profile=NAME_PROFILE)
        expected = definedText.get('PrefabTextItem_1547656443_Text', '')
        candidates = [value.lower() for value in (expected, 'terminal') if value]
        recognized = bool(
            result.text
            and result.confidence >= 0.75
            and candidates
            and getMatches(result.text.lower(), candidates, n=1, cutoff=0.72)
        )
        return {
            'verified': recognized,
            'detector': 'terminal-label-ocr',
            'confidence': result.confidence,
            'roi': 'terminal',
            'reason': None if recognized else 'Terminal label OCR did not match.',
        }

    def isMenu(self) -> bool:
        """
        Checks if the current screen shows the main menu.

        Returns:
            bool: True if the main menu is detected, False otherwise.
        """
        try:
            screenInfo = WindowManager().getScreenInfo()
            image = screenshot(
                screenInfo.terminal.x,
                screenInfo.terminal.y,
                screenInfo.terminal.w,
                screenInfo.terminal.h,
                screenInfo.monitor
            )

            evidence = self.inspect_image(image)
            logger.debug(
                "Terminal state verified=%s confidence=%.3f",
                evidence['verified'],
                evidence['confidence'],
            )
            return 'terminal' if evidence['verified'] else False
        except Exception as e:
            logger.error(f"Failed to capture or process screenshot: {e}", exc_info=True)
            return False

    def isInMainMenu(self):
        """
        Checks if the application is in the main menu and handles errors if not.

        Returns:
            tuple: A tuple of three elements:
                - Status code (str): Empty string on success, 'error' on failure.
                - Status message (str): Descriptive message based on the result.
                - Additional information (str): Empty string on success, error message on failure.
        """
        try:
            result = WindowManager().setForeground()
            if result[0] == 'error':
                return result
            time.sleep(.2)

            if not self.isMenu():
                return 'error', 'Error', 'Not in the main menu. Press ESC in-game and rerun the scanner.'

            return '', '', ''

        except Exception as e:
            logger.error(f"Exception occurred: {e}", exc_info=True)
            return 'error', 'Exception', str(e)
