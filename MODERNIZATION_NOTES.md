# Modernization audit notes

Baseline repository: `Psycho-Marcus/WuWa_Inventory_Kamera`

## Confirmed observations

- Windows-only scanner using screen capture, OCR, simulated input, PySide6 UI, and cx_Freeze.
- Existing scan coverage includes resonators, weapons, echoes, development items, resources, achievements, and Shell Credit.
- Explicit ROI data exists for 1920x1080 and 1680x1050, with scaled fallback logic.
- README claims 2560x1440 support, but the inspected ROI table has no explicit 2560x1440 profile; revalidate this.
- OCR currently discards recognition confidence in `imageToString()`.
- Several scanner paths use broad exceptions and silent fallback values.
- Data updater is coupled to legacy `Dimbreath/WutheringData` paths.
- Asset updater is coupled to `Stormy-Waves/WW_Icon`.
- `setup.py` currently reports version 1.7.1.

## Confirmed correctness defect

In `scraping/charactersScraper.py`, `scrapeSkills()` checks `buttonHash in _cache` but reads `_cache[button]`. The lookup must use `buttonHash`.

## Release strategy

Do not claim 3.6 compatibility based only on data regeneration. Current-game ROI and end-to-end scanning must be verified, especially Korean UI at 1920x1080.
