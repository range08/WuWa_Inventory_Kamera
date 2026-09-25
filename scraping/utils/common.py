import logging
import mss
import cv2
import json
import numpy as np
import win32clipboard
from pathlib import Path

from properties.config import cfg, INVENTORY
from scraping.exporter import write_json_atomic
from scraping.ocr_engine import (
    OCREngine,
    OCRError,
    OCRProfile,
    OCRResult,
)

logger = logging.getLogger('OCR')
ocrEngine = OCREngine()

def loadFile(filePATH: str, default = None) -> dict | list:
    if default is None:
        default = {}

    try:
        with open(filePATH, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if isinstance(default, list):
                data = list(data)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return default

itemsID: dict = loadFile('./data/items.json')
charactersID: dict = loadFile('./data/characters.json')
weaponsID: dict = loadFile('./data/weapons.json')
echoesID: dict = loadFile('./data/echoes.json')
achievementsID: dict = loadFile('./data/achievements.json')
echoStats: dict = loadFile('./data/echoStats.json')
definedText: dict = loadFile('./data/definedText.json')
sonataName: list = loadFile('./data/sonataName.json', [])

def savingScraped(scannedData: dict | None = None, START_DATE: str = ''):
    if scannedData is None:
        scannedData = {
            'inventory_wuwainventorykamera.json': (INVENTORY['items'], dict)
        }

    savePATH: Path = Path(cfg.get(cfg.exportFolder)) / START_DATE
    
    if any(data != emptyType() for data, emptyType in scannedData.values()):
        savePATH.mkdir(parents=True, exist_ok=True)

        for filename, (data, emptyType) in scannedData.items():
            if data != emptyType():
                filePATH = savePATH / filename
                write_json_atomic(filePATH, data)

def screenshot(left: int = 0, top: int = 0, width: int = 0, height: int = 0, monitor: int = 1, bw: bool = False):

    with mss.mss() as sct:
        mon = sct.monitors[monitor]
        if all(coord == 0 for coord in [top, left, width, height]):
            left, top, width, height = tuple(coord for coord in mon.values())

        region = {
            'left': mon['left'] + left,
            'top': mon['top'] + top,
            'width': width,
            'height': height,
            'mon': monitor
        }
        image = np.array(sct.grab(region))
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
    
    if bw:
        image = convertToBlackWhite(image)

    return image

def convertToBlackWhite(image: np.ndarray):
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    elif len(image.shape) == 2:
        gray = image
    else:
        raise ValueError(f"Unsupported image format. Image shape: {image.shape}")
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    contrasted = clahe.apply(gray)
    
    blurred = cv2.GaussianBlur(contrasted, (3, 3), 0)
    
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    if np.mean(thresh) > 127: thresh = cv2.bitwise_not(thresh)
    
    kernel = np.ones((2,2), np.uint8)
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    sharpen_kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(morph, -1, sharpen_kernel)

    return sharpened

def imageToResult(
    image: np.ndarray,
    divisor: str = ' ',
    allowedChars: str = None,
    bannedChars: str = None,
    profile: OCRProfile | None = None,
) -> OCRResult:
    if profile is None:
        profile = OCRProfile(
            name='legacy',
            divisor=divisor,
            allowed_chars=allowedChars,
            banned_chars=bannedChars,
        )

    try:
        return ocrEngine.recognize(image, profile)
    except OCRError:
        logger.debug("OCR failed", exc_info=True)
        return OCRResult.empty(profile.name)


def imageToString(
    image: np.ndarray,
    divisor: str = ' ',
    allowedChars: str = None,
    bannedChars: str = None,
    profile: OCRProfile | None = None,
) -> str:
    return imageToResult(
        image,
        divisor=divisor,
        allowedChars=allowedChars,
        bannedChars=bannedChars,
        profile=profile,
    ).text



def copyToClipboard(text):
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text)
    finally:
        win32clipboard.CloseClipboard()