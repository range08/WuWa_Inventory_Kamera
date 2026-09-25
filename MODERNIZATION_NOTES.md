# Modernization audit notes

Baseline repository: `Psycho-Marcus/WuWa_Inventory_Kamera`
Baseline commit: `7b5ecf4eca355d3f4a06fb0d65e8419d1f984883`

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


## Phase 1 progress

- Fixed the skill-button OCR cache to read and write with `buttonHash`.
- Audited cache access patterns in `charactersScraper.py`, `weaponsScraper.py`, `echoesScraper.py`, `itemsScraper.py`, `achievementsScraper.py`, and `shellScraper.py`; no additional mismatched cache-key use was found by inspection.


## Phase 2 initial provider work

- Added `updater/providers.py` as a dependency-free source descriptor layer.
- Added parsing for upstream Game Version, Resource Version, and Changelist metadata.
- Added explicit source-path validation.
- Added unit tests for metadata parsing, required paths, unsafe path rejection, and fail-closed metadata parsing.
- Added `docs/GAME_DATA.md` documenting the no-vendoring boundary for upstream game data.
- The Arikatsu data repository exposes current Global 3.6 data but no explicit LICENSE file was found during this audit; raw BinData/Textmaps therefore remain local update/build inputs and are not to be redistributed by this fork.
- Added a minimal Windows GitHub Actions workflow running `compileall` and dependency-free unit tests.


## Additional Phase 1 fixes

- Fixed an echo rarity cache bug: cached rarity values were stored as integers but later read as if they were indexable lists.
- Item quantity OCR failures are no longer committed to inventory as a confirmed quantity of 1; they are routed through the existing manual-review path.
- Removed the remaining bare `except:` statements from scanner, UI fallback, and legacy updater paths.
- Audited Python function signatures for mutable `{}`/`[]` defaults; no remaining cases were found after the `loadFile()` fix.
- Modernization CI passed on head `f9bdde96d67cf7737c51400fdae86258ac4eb3d2`.
