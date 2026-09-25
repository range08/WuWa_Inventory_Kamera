import cv2
import hashlib
import numpy as np
from pathlib import Path

from scraping.utils import itemsID
from scraping.utils import (
    screenshot, imageToResult, convertToBlackWhite,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from properties.config import cfg, basePATH
from scraping.cancellation import check_cancelled
from scraping.matching import ITEM_NAME_CUTOFF, best_match
from scraping.parsing import ScanParseError, parse_quantity
from scraping.review_queue import (
    review_reasons,
    write_review_metadata,
)

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
        infoResult = _cache[infoFingerprint]
    else:
        infoResult = imageToResult(infoImage, bannedChars=' ')
        _cache[infoFingerprint] = infoResult

    info = infoResult.text.lower().split('\n')
    name = info[0] if info else ""
    result = best_match(name, itemsID, cutoff=ITEM_NAME_CUTOFF)
    if result:
        name = result
    
    quantityValid = True
    try:
        value = parse_quantity(info[2])
    except (IndexError, ScanParseError):
        value = None
        quantityValid = False

    itemID = itemsID.get(name, {'id': None})['id']
    reasons = review_reasons(
        recognized=itemID is not None,
        quantity_valid=quantityValid,
        confidence=infoResult.confidence,
    )

    if not reasons:
        inventory[itemID] = value
    else:
        path.mkdir(parents=True, exist_ok=True)
        descImage = image[
            screenInfo.items.description.y:
            screenInfo.items.description.y + screenInfo.items.description.h,
            screenInfo.items.description.x:
            screenInfo.items.description.x + screenInfo.items.description.w,
        ]

        stem = f'item-{infoFingerprint[:16]}'
        imagePath = path / f'{stem}.png'
        metadataPath = path / f'{stem}.json'

        if not imagePath.exists():
            if not cv2.imwrite(str(imagePath), descImage):
                raise OSError(
                    f"Unable to save failed OCR crop: {imagePath}"
                )

        write_review_metadata(
            metadataPath,
            scanner="items",
            reason="+".join(reasons),
            fingerprint=infoFingerprint,
            crop_file=imagePath.name,
            ocr_result=infoResult,
            owned=value,
            candidate=name if itemID is not None else None,
        )

        failed.append({
            'image': imagePath,
            'metadata': metadataPath,
            'owned': value,
            'candidate': name if itemID is not None else None,
            'confidence': infoResult.confidence,
            'reasons': reasons,
        })

    return inventory, failed, name, infoFingerprint

def itemsScraper(START_DATE: str, controller: WindowsInputController, x: int, y: int, screenInfo: ScreenInfo, cancel_event=None):
    path: Path = basePATH / 'logs' / 'fail' / START_DATE

    inventory = dict()
    failed = list()
    _cache = dict()
    seenFingerprints = set()
    seenViewports = set()

    check_cancelled(cancel_event)
    controller.pressKey(cfg.get(cfg.inventoryKeybind), 2, False)
    controller.leftClick(x, y)

    for _ in range(MAX_VIEWPORTS):
        check_cancelled(cancel_event)
        viewportFingerprints = []

        for row in range(ROWS):
            for col in range(COLS):
                check_cancelled(cancel_event)
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

