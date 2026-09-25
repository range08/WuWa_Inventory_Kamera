import time
import logging
import multiprocessing
from queue import Empty
from datetime import datetime

from properties.config import FAILED, INVENTORY, basePATH
from scraping.utils import (
    WindowsInputController, savingScraped
)

from scraping.shellScraper import getShell
from scraping.itemsScraper import itemsScraper
from scraping.charactersScraper import resonatorScraper
from scraping.weaponsScraper import weaponScraper
from scraping.echoesScraper import echoScraper
from scraping.achievementsScraper import achievementScraper
from scraping.account_export import (
    build_account_export,
    build_validation_report,
)
from scraping.cancellation import ScanCancelled, check_cancelled
from scraping.result_protocol import ScraperMessageError, parse_scraper_message
from scraping.scan_metadata import build_scan_metadata

from game.menu import MainMenuController
from game.screenInfo import ScreenInfo
from game.foreground import WindowManager
from game.stopKey import KeyPressChecker

logger = logging.getLogger('ScraperManager')

CANCEL_GRACE_SECONDS = 4.0


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
                cancelFLAG,
                queue,
                INVENTORY['date'],
            ),
        )
        scrapersProcess.start()

        stopMonitor = multiprocessing.Process(
            target=needToStop,
            args=(completeFLAG, cancelFLAG),
        )
        stopMonitor.start()

        scraperError = None
        scraperCompleted = False

        try:
            # Consume queue messages while the child is alive. Waiting until
            # after join() can deadlock when the multiprocessing pipe fills.
            cancelRequestedAt = None
            while scrapersProcess.is_alive():
                if cancelFLAG.is_set():
                    if cancelRequestedAt is None:
                        cancelRequestedAt = time.monotonic()
                        logger.info(
                            "Waiting for scanner process to exit cooperatively."
                        )
                    elif (
                        time.monotonic() - cancelRequestedAt
                        >= CANCEL_GRACE_SECONDS
                    ):
                        logger.warning(
                            "Scanner did not exit within %.1f seconds; "
                            "terminating it.",
                            CANCEL_GRACE_SECONDS,
                        )
                        scrapersProcess.terminate()
                        break

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
            if stopMonitor.is_alive():
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


def needToStop(completeFLAG, cancelFLAG):
    keyPress = KeyPressChecker()
    gameManager = WindowManager()

    while not completeFLAG.is_set() and not cancelFLAG.is_set():
        # Request cooperative cancellation when the game loses focus or the
        # user presses the configured stop key. The parent process retains a
        # bounded hard-termination fallback for an unresponsive child.
        if not gameManager.isForeground() or keyPress.isPressed():
            logger.info(
                "Requesting scanner cancellation due to stop key or focus loss."
            )
            cancelFLAG.set()
            return
        time.sleep(.1)


def scrapers(
    scraperEnabled: list,
    screenInfo: ScreenInfo,
    FLAG,
    cancelFLAG,
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
            check_cancelled(cancelFLAG)
            controller.pressKey('esc', .5)

            try:
                match(scraper):
                    case 'characters':
                        resonator = resonatorScraper(controller, screenInfo, cancelFLAG)
                    case 'weapons':
                        i, w = weaponScraper(
                            controller,
                            screenInfo.scrapers.weapons.x,
                            screenInfo.scrapers.weapons.y,
                            screenInfo,
                            cancelFLAG,
                        )
                        inventory.update(i)
                        weapons.extend(w)
                    case 'echoes':
                        echoes = echoScraper(
                            controller,
                            screenInfo.scrapers.echoes.x,
                            screenInfo.scrapers.echoes.y,
                            screenInfo,
                            cancelFLAG,
                        )
                    case 'devItems':
                        i, f = itemsScraper(
                            START_DATE,
                            controller,
                            screenInfo.scrapers.devItems.x,
                            screenInfo.scrapers.devItems.y,
                            screenInfo,
                            cancelFLAG,
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
                            cancelFLAG,
                        )
                        inventory.update(i)
                        failed.extend(f)
                    case 'achievements':
                        achievements = achievementScraper(controller, screenInfo, cancelFLAG)
                    case _:
                        raise ValueError(f"Unknown scraper: {scraper}")

                if scraper not in ['characters', 'achievements']:
                    if '2' not in inventory or inventory.get('2') == 0:
                        check_cancelled(cancelFLAG)
                        shell = getShell(screenInfo)
                        check_cancelled(cancelFLAG)
                        inventory = {**shell, **inventory}
            except ScanCancelled:
                raise
            except Exception as exc:
                raise RuntimeError(
                    f"{scraper} scanner failed: {exc}"
                ) from exc

        check_cancelled(cancelFLAG)

        chunkSize = 20
        inventoryItems = list(inventory.items())

        for i in range(0, len(inventoryItems), chunkSize):
            check_cancelled(cancelFLAG)
            chunk = dict(inventoryItems[i:i + chunkSize])
            queue.put({
                'type': 'inventory',
                'inventory': chunk,
            })

        check_cancelled(cancelFLAG)
        if failed:
            queue.put({
                'type': 'failed',
                'failed': failed,
            })

        check_cancelled(cancelFLAG)

        # Scanning is complete. Stop the focus/keyboard cancellation monitor
        # before the short atomic-export finalization phase so a late stop key
        # cannot turn a completed scan into a partially written export set.
        FLAG.set()

        scanMetadata = build_scan_metadata(
            basePATH / 'data' / 'mapping_manifest.json'
        )
        validationReport = build_validation_report(
            selected_scanners=scraperEnabled,
            inventory=inventory,
            characters=resonator,
            weapons=weapons,
            echoes=echoes,
            achievements=achievements,
            failed_count=len(failed),
        )

        scannedData = {
            'characters_wuwainventorykamera.json': (resonator, dict),
            'weapons_wuwainventorykamera.json': (weapons, list),
            'echoes_wuwainventorykamera.json': (echoes, list),
            'achievements_wuwainventorykamera.json': (achievements, list),
            'scan_metadata.json': (scanMetadata, dict),
            'validation_report.json': (validationReport, dict),
        }
        if not failed:
            accountExport = build_account_export(
                metadata=scanMetadata,
                validation=validationReport,
                inventory=inventory,
                characters=resonator,
                weapons=weapons,
                echoes=echoes,
                achievements=achievements,
            )
            scannedData['account.json'] = (accountExport, dict)

        savingScraped(scannedData, START_DATE)

        queue.put({'type': 'complete'})

    except ScanCancelled:
        logger.info("Scanner process acknowledged cancellation.")
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
