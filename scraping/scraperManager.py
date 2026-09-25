import os
import sys
import time
import signal
import logging
import multiprocessing
from queue import Empty
from datetime import datetime

from properties.config import FAILED, INVENTORY
from scraping.utils import (
    WindowsInputController, savingScraped
)

from scraping.shellScraper import getShell
from scraping.itemsScraper import itemsScraper
from scraping.charactersScraper import resonatorScraper
from scraping.weaponsScraper import weaponScraper
from scraping.echoesScraper import echoScraper
from scraping.achievementsScraper import achievementScraper
from scraping.result_protocol import ScraperMessageError, parse_scraper_message

from game.menu import MainMenuController
from game.screenInfo import ScreenInfo
from game.foreground import WindowManager
from game.stopKey import KeyPressChecker

logger = logging.getLogger('ScraperManager')


def _applyScraperMessage(message):
    """Apply one validated child-process message to in-memory scan state."""
    global INVENTORY, FAILED

    try:
        messageType, payload = parse_scraper_message(message)
    except ScraperMessageError as exc:
        return (str(exc), False)

    if messageType == 'inventory':
        INVENTORY['items'].update(payload)
        return (None, False)

    if messageType == 'failed':
        FAILED.extend(payload)
        return (None, False)

    if messageType == 'error':
        return (payload, False)

    return (None, True)


def managerStart(scraperEnabled: list):
    global INVENTORY, FAILED
    INVENTORY['date'] = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    INVENTORY['items'].clear()
    FAILED.clear()

    gameManager = WindowManager()
    layoutError = gameManager.getScannerLayoutError()
    if layoutError:
        result = ('error', 'Unsupported scanner layout', layoutError)
    else:
        result = MainMenuController().isInMainMenu()

    if result[0] != 'error':
        time.sleep(1.2)

        completeFLAG = multiprocessing.Event()
        cancelFLAG = multiprocessing.Event()
        queue = multiprocessing.Queue()

        scrapersProcess = multiprocessing.Process(
            target=scrapers,
            args=(
                scraperEnabled,
                gameManager.getScreenInfo(),
                completeFLAG,
                queue,
                INVENTORY['date'],
            ),
        )
        scrapersProcess.start()

        stopMonitor = multiprocessing.Process(
            target=needToStop,
            args=(scrapersProcess.pid, completeFLAG, cancelFLAG),
        )
        stopMonitor.start()

        scraperError = None
        scraperCompleted = False

        try:
            # Consume queue messages while the child is alive. Waiting until
            # after join() can deadlock when the multiprocessing pipe fills.
            while scrapersProcess.is_alive():
                try:
                    message = queue.get(timeout=0.2)
                except Empty:
                    continue

                error, completed = _applyScraperMessage(message)
                if error and scraperError is None:
                    scraperError = error
                scraperCompleted = scraperCompleted or completed

            scrapersProcess.join()

            # Drain messages that were flushed immediately before process exit.
            while True:
                try:
                    message = queue.get_nowait()
                except Empty:
                    break

                error, completed = _applyScraperMessage(message)
                if error and scraperError is None:
                    scraperError = error
                scraperCompleted = scraperCompleted or completed

        except (OSError, ValueError) as e:
            logger.error("Fatal error processing scraper queue: %s", e, exc_info=True)
            scraperError = f"Queue processing error: {e}"
        finally:
            stopMonitor.terminate()
            stopMonitor.join()
            queue.close()
            queue.join_thread()

        if scraperError:
            result = ('error', 'Scan failed', scraperError)
        elif cancelFLAG.is_set():
            result = (
                'warning',
                'Scan cancelled',
                'The scan was cancelled before completion.',
            )
        elif not completeFLAG.is_set() or not scraperCompleted:
            result = (
                'error',
                'Scan failed',
                f'Scanner process exited unexpectedly (exit code {scrapersProcess.exitcode}).',
            )
        else:
            savingScraped(START_DATE=INVENTORY['date'])

            if len(FAILED) > 0:
                result = (
                    'failed',
                    'Failed to recognize',
                    f'Failed to recognize {len(FAILED)} items.',
                )
            else:
                result = (
                    'success',
                    'Complete',
                    'Scan completed without errors.',
                )

    WindowManager('WuWa Inventory Kamera', 'WuWa Inventory Kamera.exe').setForeground()
    return result


def needToStop(tPID, completeFLAG, cancelFLAG):
    keyPress = KeyPressChecker()
    gameManager = WindowManager()

    while not completeFLAG.is_set():
        # Check if the game is no longer in the foreground or if the key is pressed.
        if not gameManager.isForeground() or keyPress.isPressed():
            cancelFLAG.set()
            try:
                os.kill(tPID, signal.SIGTERM)
                logger.debug(
                    "Terminated scraper process due to key press or game not in foreground."
                )
            except Exception as e:
                logger.error("Error terminating scraper process: %s", e, exc_info=True)
            sys.exit(0)
        time.sleep(.1)


def scrapers(
    scraperEnabled: list,
    screenInfo: ScreenInfo,
    FLAG,
    queue: multiprocessing.Queue,
    START_DATE: str,
):
    controller = None
    try:
        controller = WindowsInputController(screenInfo.monitor)
        resonator = dict()
        inventory = dict()
        failed = list()
        weapons = list()
        echoes = list()
        achievements = list()

        for scraper in scraperEnabled:
            controller.pressKey('esc', .5)

            try:
                match(scraper):
                    case 'characters':
                        resonator = resonatorScraper(controller, screenInfo)
                    case 'weapons':
                        i, w = weaponScraper(
                            controller,
                            screenInfo.scrapers.weapons.x,
                            screenInfo.scrapers.weapons.y,
                            screenInfo,
                        )
                        inventory.update(i)
                        weapons.extend(w)
                    case 'echoes':
                        echoes = echoScraper(
                            controller,
                            screenInfo.scrapers.echoes.x,
                            screenInfo.scrapers.echoes.y,
                            screenInfo,
                        )
                    case 'devItems':
                        i, f = itemsScraper(
                            START_DATE,
                            controller,
                            screenInfo.scrapers.devItems.x,
                            screenInfo.scrapers.devItems.y,
                            screenInfo,
                        )
                        inventory.update(i)
                        failed.extend(f)
                    case 'resources':
                        i, f = itemsScraper(
                            START_DATE,
                            controller,
                            screenInfo.scrapers.resources.x,
                            screenInfo.scrapers.resources.y,
                            screenInfo,
                        )
                        inventory.update(i)
                        failed.extend(f)
                    case 'achievements':
                        achievements = achievementScraper(controller, screenInfo)
                    case _:
                        raise ValueError(f"Unknown scraper: {scraper}")

                if scraper not in ['characters', 'achievements']:
                    if '2' not in inventory or inventory.get('2') == 0:
                        shell = getShell(screenInfo)
                        inventory = {**shell, **inventory}
            except Exception as exc:
                raise RuntimeError(
                    f"{scraper} scanner failed: {exc}"
                ) from exc

        chunkSize = 20
        inventoryItems = list(inventory.items())

        for i in range(0, len(inventoryItems), chunkSize):
            chunk = dict(inventoryItems[i:i + chunkSize])
            queue.put({
                'type': 'inventory',
                'inventory': chunk,
            })

        if failed:
            queue.put({
                'type': 'failed',
                'failed': failed,
            })

        savingScraped({
            'characters_wuwainventorykamera.json': (resonator, dict),
            'weapons_wuwainventorykamera.json': (weapons, list),
            'echoes_wuwainventorykamera.json': (echoes, list),
            'achievements_wuwainventorykamera.json': (achievements, list),
        }, START_DATE)

        queue.put({'type': 'complete'})
        FLAG.set()

    except Exception as e:
        logger.error("Error in scrapers: %s", e, exc_info=True)
        try:
            queue.put({
                'type': 'error',
                'error': f'{type(e).__name__}: {e}',
            })
        finally:
            FLAG.set()
    finally:
        if controller is not None:
            try:
                controller.pressKey('esc')
            except Exception:
                logger.warning(
                    "Failed to restore game UI after scanner exit.",
                    exc_info=True,
                )
