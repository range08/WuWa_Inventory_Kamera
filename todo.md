# WuWa Inventory Kamera Modernization TODO

Target baseline: Wuthering Waves Global 3.6.x on Windows.
Design goal: avoid hard-coding the project to 3.6 so that 3.7+ updates are mostly data/ROI maintenance rather than rewrites.

## Operating rules

- Preserve the GPL-3.0 license and existing attribution.
- Do not add memory reading, DLL injection, packet interception, anti-cheat bypasses, or process tampering.
- Prefer screen capture/OCR and documented/official launcher data sources only.
- Keep the existing export format compatible unless a schema migration is explicitly versioned.
- Do not silently guess OCR values. Low-confidence or unrecognized results must be reported.
- Never log authentication credentials or other secrets.
- Work from small, reviewable commits.
- Before changing behavior, reproduce and document the current behavior.

## Phase 0 — Establish a reproducible baseline

- [x] Create a modernization branch, suggested name: `modernize/latest`.
- [x] Record the upstream commit SHA used as the baseline: `7b5ecf4eca355d3f4a06fb0d65e8419d1f984883`.
- [ ] Confirm the application starts on a clean Windows 11 environment.
- [x] Record supported Python versions: Windows dependency/import smoke passes on Python 3.12, 3.13, and 3.14; cx_Freeze build smoke passes on Python 3.14.
- [ ] Create a virtual environment and install dependencies from scratch.
- [x] Document exact virtualenv, dependency install, data update, run, offline reuse, and cx_Freeze build commands in README.
- [ ] Run the application with no `data/` directory and record updater behavior.
- [ ] Verify behavior on 1920x1080 fullscreen first.
- [ ] Capture baseline screenshots for:
  - [ ] Inventory — Weapons
  - [ ] Inventory — Echoes
  - [ ] Inventory — Development Items
  - [ ] Inventory — Resources
  - [ ] Resonator — Overview
  - [ ] Resonator — Weapon
  - [ ] Resonator — Forte/Skills
  - [ ] Resonator — Resonance Chain
  - [ ] Achievements
- [ ] Store test fixtures without personal identifiers or UID.

## Phase 1 — Fix known correctness bugs before modernization

- [x] Fix `scraping/charactersScraper.py` cache lookup bug in `scrapeSkills()`:
  - Current code reads `_cache[button]` when `buttonHash` is the cache key.
  - Correct behavior must read `_cache[buttonHash]`.
- [x] Audit cache reads/writes across the six scanner modules for mismatched keys.
- [x] Replace bare `except:` blocks across the Python codebase with explicit exception handling/logging.
- [x] Audit mutable default arguments such as `loadFile(..., default={})`.
- [x] Ensure OCR failure cannot silently become a plausible value such as level 1 or quantity 1 without an error marker.
- [x] Fix queue/error propagation so a scraper subprocess exception is visible to the UI.
- [x] Review item-page termination logic for false duplicate detection; replaced quantity-based duplicate counting with repeated-viewport fingerprint detection.
- [x] Review off-by-one handling on the final weapon/echo/item page. Weapon/Echo use global count boundaries; items now terminate on a repeated viewport instead of a synthetic item count.
- [ ] Confirm every scanner restores the game UI to a predictable state on failure/cancel.
- [x] Add a single structured exception boundary around each scraper.

## Phase 2 — Replace obsolete game-data updater

Current updater is coupled to `Dimbreath/WutheringData` and old paths such as `TextMap`, `ConfigDB/ItemInfo.json`, and `ConfigDB/WeaponConf.json`.

- [x] Introduce a game-data provider abstraction.
- [x] Add a provider for a current Global-client data source.
- [x] Use `Arikatsu/WutheringWaves_Data` as the first supported Global data provider.
- [x] Read the upstream version metadata before importing data.
- [x] Persist source metadata:
  - [x] repository
  - [x] branch/tag/commit
  - [x] game version
  - [x] resource version
  - [x] changelist
  - [x] generated-at timestamp
- [x] Do not compare updates only by file size.
- [x] Use content hashes and resolved commit SHA for update detection/validation.
- [x] Make generated mapping JSON deterministic.
- [x] Generate/update characters, weapons, items, echoes, echo stats, sonata labels, scanner UI text, and achievements mappings where available; validated against real Global 3.6 Korean data.
- [x] Support Korean (`ko`) explicitly in source/provider/config selection.
- [x] Keep English as a fallback when localized text is missing; Korean real-data smoke completed successfully with the dual-textmap pipeline.
- [x] Validate duplicate normalized names.
- [x] Validate missing IDs and malformed records.
- [x] Add `python -m tools.update_game_data` for source sync, validation, and mapping generation.
- [x] Allow selecting/pinning an upstream branch, tag, or commit with `--ref` / `WUWA_DATA_REF`.
- [x] Add an offline mode using the last validated local database, including cache/hash validation and no-regeneration reuse.
- [x] Fail clearly when the remote schema changes.

## Phase 3 — Separate generated game data from scanner logic

- [ ] Move static/generated mappings out of import-time module globals.
- [ ] Add typed data-access functions.
- [ ] Add `schema_version` to generated/exported formats.
- [ ] Add `game_version`, `resource_version`, `language`, and `scan_time` metadata.
- [ ] Maintain an export compatibility layer for existing WuWa Tracker users.
- [ ] Avoid a repository-wide rewrite in one commit.

## Phase 4 — Modernize OCR

- [x] Wrap RapidOCR behind an OCR interface.
- [x] Preserve OCR confidence values.
- [x] Return structured OCR results with text, confidence, bounding box, and preprocessing profile.
- [x] Add separate profiles for names, integer quantities, level current/max, percentages, and Korean text.
- [ ] Add multiple preprocessing candidates.
- [x] Normalize Unicode, spaces, and punctuation.
- [x] Use independently configurable fuzzy-match thresholds for resonators, equipped weapons, weapon inventory entries, items, and echoes.
- [x] Never substitute an unrecognized item with quantity 1 without flagging it.
- [ ] Save failed OCR crops with metadata.
- [ ] Add a review queue for uncertain OCR results.
- [ ] Avoid saving UID/account-identifying screenshot regions unless explicitly needed.

## Phase 5 — Wuthering Waves 3.6 UI/ROI validation

Start with 1920x1080 fullscreen.

- [ ] Recalibrate all 1920x1080 coordinates against current 3.6 Global UI.
- [ ] Validate Inventory: category buttons, first cell, grid spacing, name, quantity, description, weapon level/rank, echo card, echo full stats.
- [ ] Validate Resonator: list, overview, name, level, weapon, echoes, forte/skills, inherent nodes, resonance chain.
- [ ] Validate Achievements controls/status.
- [ ] Validate Shell Credit region.
- [ ] Validate scrolling distances/direction.
- [ ] Validate UI animation timing at 60 FPS and 120 FPS.
- [ ] Add configurable waits/retry-until-stable rather than relying only on fixed sleeps.

## Phase 6 — Resolution/window handling

- [ ] Keep 1920x1080 as the first known-good reference.
- [ ] Verify 2560x1440 with real screenshots.
- [ ] Verify 1680x1050 separately.
- [ ] Detect game client-area bounds rather than assuming monitor origin.
- [ ] Account for Windows DPI scaling.
- [ ] Support borderless-windowed if reliable.
- [ ] Add a calibration/debug ROI overlay.
- [ ] Add screenshot-only diagnostic mode.
- [x] Reject unsupported layouts before scanner input. Current safe policy requires 100% Windows scaling, a client area filling the entire target monitor, and an explicit ROI resolution.

## Phase 7 — Scanner state machine and safety

- [ ] Replace fragile fixed click/sleep sequences with explicit states.
- [ ] Verify expected screen before each action.
- [ ] Verify expected transition after each action.
- [ ] Add bounded retries and safe cancellation.
- [x] Remove the forced Administrator requirement; scanner input remains ordinary user-level Win32 mouse/keyboard automation. Real game interaction still requires manual validation.
- [x] Keep all interaction at ordinary user-input level; no process memory, injection, packet interception, or anti-cheat bypass path is used.
- [ ] Add a dry-run/screenshot mode.

## Phase 8 — Character scanner

- [ ] Verify Korean and English resonator-name recognition.
- [ ] Improve Rover handling.
- [ ] Verify level/ascension.
- [ ] Verify equipped weapon data.
- [ ] Re-enable character echo scan only after standalone echo scan is reliable.
- [ ] Verify all five active skills.
- [ ] Verify inherent/stat nodes.
- [ ] Verify all six resonance-chain nodes.
- [x] Improve resonator end-of-list detection so overlapping scroll viewports do not terminate on the first duplicate.
- [x] Prevent duplicate character processing by resolving cached name cards to IDs and skipping already-scanned resonators.
- [ ] Store OCR confidence/debug metadata outside compatibility export.

## Phase 9 — Weapon scanner

- [ ] Verify 24-slot page assumptions and count/page OCR.
- [ ] Verify equipped/locked states.
- [ ] Verify rarity/level filters.
- [ ] Preserve duplicate weapon copies.
- [ ] Verify max-level ascension mapping.
- [ ] Preserve unknown weapons in review queue.

## Phase 10 — Echo scanner

- [ ] Verify current 3.6 echo card layout.
- [ ] Update current sonata/set names.
- [ ] Verify current main stat combinations and all substat aliases.
- [ ] Verify rarity, tune level, locked/favorited/equipped states.
- [ ] Avoid collapsing distinct identical-stat echoes.
- [ ] Compare robust approaches used by maintained echo OCR tools without copying incompatible code/licenses.

## Phase 11 — Item/resource scanner

- [ ] Verify Development Items and Resources tabs.
- [ ] Verify quantities from 1 to large currency values.
- [ ] Verify duplicate grid behavior.
- [x] Replace `ceil(quantity / 999)` page-termination heuristic with viewport fingerprint detection.
- [x] Add explicit grid/end detection with a repeated-viewport signature and bounded 256-viewport safety limit.
- [ ] Ensure commas/punctuation do not corrupt quantities.
- [ ] Preserve unknown items for manual review.
- [ ] Test newly added materials.

## Phase 12 — Export schema

- [ ] Preserve legacy export filenames.
- [ ] Add optional aggregate `account.json`.
- [ ] Add schema metadata without breaking legacy importers.
- [x] Use deterministic UTF-8 JSON formatting and atomic replacement for scanner exports.
- [ ] Optionally include validation report.
- [ ] Never export launcher auth tokens or credentials.

## Phase 13 — Optional official launcher-data integration

- [ ] Keep launcher integration isolated from screen scanner.
- [ ] Keep auth material local in memory.
- [ ] Never print or persist `oauthCode`.
- [ ] Use only fields actually exposed by launcher endpoints.
- [ ] Keep integration optional and disabled by default until reviewed.

## Phase 14 — Testing

- [ ] Add unit tests for normalization, fuzzy matching, level/quantity/stat parsing, ascension calculation, and data transforms.
- [ ] Add screenshot fixture tests for every scanner.
- [ ] Add Korean and English regression coverage.
- [ ] Add export schema tests.
- [x] Add malformed/partial OCR tests.
- [x] Add offline updater/cache-reuse tests.
- [ ] Ensure tests do not require the game installed.

## Phase 15 — Dependency/build modernization

- [ ] Determine supported Python versions.
- [x] Pin all direct runtime/build dependencies in `requirements.txt`.
- [x] Audit RapidOCR, PySide/qfluentwidgets, pywin32, OpenCV/NumPy, ONNX Runtime, and cx_Freeze compatibility through the Windows 3.12/3.13/3.14 dependency smoke matrix.
- [x] Generate package/build version from the single `version.py` source.
- [x] Stop duplicating version strings in cx_Freeze metadata/output paths.
- [ ] Include generated data in releases or implement safe first-run download.
- [ ] Add checksums for downloaded/generated assets.

## Phase 16 — CI

- [x] Add Windows GitHub Actions for dependency-free syntax/unit tests.
- [x] Do not require the game in CI.
- [ ] Add lint/format checks.
- [x] Add import/compile smoke test.
- [x] Add data-generation validation, including a manual real Global-data smoke workflow.
- [x] Keep the Python 3.14 cx_Freeze build smoke workflow separate from the fast dependency-free PR checks.
- [ ] Do not auto-publish releases until builds are reproducible.

## Phase 17 — Documentation

- [x] Update README with verified Global 3.6 data-source status, current scanner constraints, and explicit no-compatibility-claim wording pending live UI validation.
- [ ] State tested modes/resolutions/languages exactly.
- [ ] Document Korean support status and OCR troubleshooting.
- [ ] Document calibration/debug mode and patch-update workflow.
- [ ] Preserve upstream attribution/GPL obligations.
- [ ] Replace dead tutorial resources where licensing permits.
- [ ] Add `CONTRIBUTING.md`.

## Phase 18 — Release gate

Do not publish a compatibility claim until:

- [ ] Fresh install works.
- [ ] 1920x1080 fullscreen is verified end-to-end.
- [ ] Korean character scan passes.
- [ ] English character scan passes.
- [ ] Weapons, Echoes, Development Items, Resources pass.
- [ ] Export files validate.
- [ ] No secrets appear in logs/export.
- [ ] OCR failures are surfaced instead of silently guessed.
- [ ] GPL-3.0 and attribution are preserved.
- [ ] README lists exact tested game/resource versions.

## After 3.6

Use 3.7 as an architecture validation:
- [ ] Update only the game-data source revision where possible.
- [ ] Regenerate mappings.
- [ ] Run screenshot regressions.
- [ ] Recalibrate only changed ROIs.
- [ ] Produce a compatibility report before scanner-logic changes.
