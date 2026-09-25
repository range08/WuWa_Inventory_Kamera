import re
import cv2
import hashlib
import numpy as np
from pathlib import Path
from difflib import get_close_matches as getMatches

from scraping.utils import itemsID
from scraping.utils import (
    screenshot, imageToString, convertToBlackWhite,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from properties.config import cfg, basePATH

# Constants
ROWS, COLS = 4, 6
MAX_VIEWPORTS = 256

def processItem(path: Path, image: np.ndarray, screenInfo: ScreenInfo, _cache: dict) -> tuple[dict[str, int], list[dict], str, str]:
    inventory = {}
    failed = []

    infoImage = image[screenInfo.items.info.y:screenInfo.items.info.y + screenInfo.items.info.h, screenInfo.items.info.x:screenInfo.items.info.x + screenInfo.items.info.w]
    infoImage = convertToBlackWhite(infoImage)
    infoFingerprint = hashlib.sha256(infoImage.tobytes()).hexdigest()

    if infoFingerprint in _cache:
        info = _cache[infoFingerprint]
    else:
        info = imageToString(infoImage, bannedChars=' ').lower().split('\n')
        _cache[infoFingerprint] = info
    name = info[0]
    result = getMatches(name, itemsID, 1, 0.9)
    if result: name = result[0]
    
    quantityValid = True
    try:
        valueText = re.sub(r'[^0-9]', '', info[2])
        if not valueText:
            raise ValueError("Quantity OCR returned no digits")
        value = int(valueText)
    except (IndexError, TypeError, ValueError):
        value = None
        quantityValid = False

    itemID = itemsID.get(name, {'id': None})['id']
    if itemID is not None and quantityValid:
        inventory[itemID] = value
    else:
        path.mkdir(parents=True, exist_ok=True)
        descImage = image[screenInfo.items.description.y:screenInfo.items.description.y + screenInfo.items.description.h, screenInfo.items.description.x:screenInfo.items.description.x + screenInfo.items.description.w]

        imagePath = path / f'item-{infoFingerprint[:16]}.png'
        if not imagePath.exists():
            cv2.imwrite(imagePath, descImage)

        failed.append({
            'image': imagePath,
            'owned': value
        })

    return inventory, failed, name, infoFingerprint

def itemsScraper(START_DATE: str, controller: WindowsInputController, x: int, y: int, screenInfo: ScreenInfo):
    path: Path = basePATH / 'logs' / 'fail' / START_DATE

    inventory = dict()
    failed = list()
    _cache = dict()
    seenFingerprints = set()
    seenViewports = set()

    controller.pressKey(cfg.get(cfg.inventoryKeybind), 2, False)
    controller.leftClick(x, y)

    for _ in range(MAX_VIEWPORTS):
        viewportFingerprints = []

        for row in range(ROWS):
            for col in range(COLS):
                center_x = screenInfo.items.start.x + (col * (screenInfo.items.start.w + screenInfo.offsets.page.x)) + screenInfo.items.start.w // 2
                center_y = screenInfo.items.start.y + (row * (screenInfo.items.start.h + screenInfo.offsets.page.y)) + screenInfo.items.start.h // 2

                controller.leftClick(center_x, center_y)
                image = screenshot(
                    width=screenInfo.width,
                    height=screenInfo.height,
                    monitor=screenInfo.monitor,
                )

                item_inventory, item_failed, _, fingerprint = processItem(
                    path,
                    image,
                    screenInfo,
                    _cache,
                )
                viewportFingerprints.append(fingerprint)

                # Scrolling can leave part of the previous viewport visible.
                # Only commit a detail card once; repeated cards are overlap,
                # empty slots retaining the previous selection, or a viewport
                # already visited at the end of the scroll range.
                if fingerprint in seenFingerprints:
                    continue

                seenFingerprints.add(fingerprint)
                inventory.update(item_inventory)
                failed.extend(item_failed)

        viewportSignature = tuple(viewportFingerprints)
        if viewportSignature in seenViewports:
            return inventory, failed

        seenViewports.add(viewportSignature)
        controller.mouseScroll(screenInfo.scroll.page.y, 1.2)

    raise RuntimeError(
        f"Item scanner exceeded {MAX_VIEWPORTS} viewports without detecting the end of the inventory."
    )

