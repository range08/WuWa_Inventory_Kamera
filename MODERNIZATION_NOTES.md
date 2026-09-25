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


## Game-data pipeline integration

- Added a local source cache that resolves the selected upstream ref to an exact commit SHA and records SHA-256/size for every downloaded input.
- Added atomic writes for source files and generated scanner mappings.
- Added a legacy-compatible mapping generator for characters, weapons, items, echoes, achievements, echo stats, sonata names, and scanner-defined text.
- Added `python -m tools.update_game_data --language <code> --ref <ref>`.
- Replaced the runtime implementation of the existing Qt `DataUpdater` adapter with the new Global provider/cache/generator pipeline while keeping its signals stable for `loadingUI.py`.
- Added the known Global language list to configuration so Korean is selectable before a first successful data download.
- Removed the now-unused Babel dependency and explicitly declared pywin32, which is imported directly by the input/clipboard code.


## Real Global 3.6 data validation

A Windows GitHub Actions smoke run validated the modernized pipeline against the actual Global 3.6 Korean source at revision `353f2eaed119bc9f680eab92807d20ac75a79b40`.

Generated mapping counts:

- characters: 54
- weapons: 122
- items: 1776
- echoes: 220
- achievements: 1195

The source manifest reported Game Version 3.6.0 and Resource Version 3.6.6. A second run using `--offline` returned `regenerated: false`, confirming that validated source and generated mappings can be reused without re-downloading or re-parsing the large textmap.

Real data exposed two classes of ambiguity that fixture-only tests had missed:

- protagonist/main-role variants share localized names, so IDs listed by `BinData/main_role_change/mainroleconfig.json` are excluded from the ordinary character-name map and remain handled by the scanner's Rover-specific path;
- unrelated internal items can share the same localized visible string, including placeholder/error text. OCR-visible mappings now remove ambiguous names instead of choosing an arbitrary ID.

Weapon and Echo final-page boundaries were also corrected to stop at `global_index >= total_count`, which handles exact multiples of 24 correctly.


## Additional correctness hardening

- Added strict source-record validation for RoleInfo, WeaponConf, ItemInfo, MonsterInfo, Achievement, and main-role configuration inputs. Malformed records now fail with `MappingGenerationError` instead of being silently skipped.
- Added fail-closed checks that reject empty generated scanner mappings.
- Added dependency-free tests for malformed source data and empty mappings.
- Reworked scraper subprocess result handling so inventory chunks, manual-review failures, normal completion, cancellation, and fatal errors are distinct message types.
- Parent process now consumes queue messages while the scanner child is alive, avoiding a potential multiprocessing pipe/join deadlock on larger inventories.
- Recognition failures are sent separately from inventory chunks, so they are not lost when no inventory item was successfully recognized.
- Added a cancellation event so user cancellation/game-focus loss is not misreported as success.
- Added per-scanner exception context (for example, `weapons scanner failed: ...`) before propagating failures to the UI.
- Removed several remaining plausible-value OCR fallbacks: invalid character/skill/weapon values, weapon and echo counts, echo stat values/rarity/level, and Shell Credit now fail closed rather than being stored as 0/1/24 defaults.
- Modernization CI passed after these changes on the latest modernization head.


## Structured OCR modernization

- Added a lazy `OCREngine` adapter around RapidOCR so OCR behavior is testable without importing the runtime backend in unit tests.
- Added structured `OCRResult` / `OCRToken` data carrying recognized text, average confidence, token confidence, bounding boxes, and profile name.
- Added NFKC Unicode normalization before field filtering.
- Added named OCR profiles for names, integers, level values, percentages, localized stat names/values, and Korean/general localized text.
- Preserved the existing `imageToString()` API as a compatibility wrapper while adding `imageToResult()` for confidence-aware callers.
- Migrated character, weapon, echo-count/stat, and Shell Credit OCR paths to typed profiles.
- Fixed a Korean-specific echo-stat bug where the old `ascii_letters` filter removed all Hangul before matching localized stat names.
- Added dependency-free tests for confidence/bbox preservation, Unicode normalization, row grouping, integer filtering, Korean stat names, malformed backend results, empty results, and partial-token filtering.
- Modernization CI passed on head `7203a2098593f981be724f21201e8e6eb9958600`.


## Item inventory termination hardening

- Removed the legacy `ceil(quantity / 999)` end-of-inventory heuristic; owned quantity is no longer used to infer scrolling state.
- Item detail cards now use SHA-256 fingerprints of the preprocessed information ROI.
- Repeated cards caused by overlapping scroll positions or empty slots retaining the previous selection are committed only once.
- A repeated 24-cell viewport fingerprint sequence marks the end of the scroll range.
- Added a bounded `MAX_VIEWPORTS` guard so unexpected UI/OCR behavior fails closed instead of scrolling indefinitely.
- Failed-recognition screenshots now use a safe fingerprint-based filename rather than raw OCR text.
- Invalid quantity OCR is represented as unknown (`None`) in the manual-review record instead of a fabricated quantity of 1.


## OCR name matching and fail-closed recognition

- Added a dependency-free matching helper with separate cutoffs for resonators, equipped weapons, weapon-inventory entries, items, and echoes so each field can be tuned independently from screenshot fixtures.
- Added unit coverage for exact, fuzzy, rejected, and invalid-threshold matching.
- Unknown resonator and equipped-weapon names no longer leak raw OCR text into otherwise valid character exports.
- Unknown weapon inventory entries and echo names are surfaced as scanner errors instead of being silently skipped.
- Echo stat parsing now rejects name/value count mismatches instead of truncating through `zip()`.
- Incomplete echo level OCR now fails closed.
- Sonata recognition now fails when no known set name is found and restores the scroll position through a `finally` block even on error.
