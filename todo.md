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
- [x] Create a clean `.venv` and install all pinned dependencies from scratch; verified by Fresh Install Smoke run 36119576256 on Windows.
- [x] Document exact virtualenv, dependency install, data update, run, offline reuse, and cx_Freeze build commands in README.
- [x] Verify the no-`data/` bootstrap path: imports succeed without generated mappings, real Global 3.6 Korean mappings are generated from empty state, loaded into the data store, and the Qt main window constructs offscreen (Fresh Install Smoke 36119576256).
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

- [x] Move generated mapping file reads out of import-time module globals; scanners now hold stable references to an explicit in-memory data store reloaded only after full validation.
- [x] Add typed generated-data accessors and validate nested item/weapon/ID/text mapping records before mutating live scanner state.
- [x] Add schema versions to generated mapping manifests and to the separate non-breaking `scan_metadata.json` export.
- [x] Add game/resource version, source revision, language, scanner version, and scan time to `scan_metadata.json` without changing legacy export files.
- [x] Maintain existing WuWa Tracker-compatible filenames/data shapes; metadata, validation, and aggregate exports are additive files only.
- [x] Keep modernization changes incremental and reviewable rather than replacing the repository in one rewrite.

## Phase 4 — Modernize OCR

- [x] Wrap RapidOCR behind an OCR interface.
- [x] Preserve OCR confidence values.
- [x] Return structured OCR results with text, confidence, bounding box, and preprocessing profile.
- [x] Add separate profiles for names, integer quantities, level current/max, percentages, and Korean text.
- [x] Add confidence-gated OCR preprocessing fallback using original, thresholded, and inverted candidates.
- [x] Normalize Unicode, spaces, and punctuation.
- [x] Use independently configurable fuzzy-match thresholds for resonators, equipped weapons, weapon inventory entries, items, and echoes.
- [x] Never substitute an unrecognized item with quantity 1 without flagging it.
- [x] Save failed item OCR description crops with paired JSON metadata containing failure reason, OCR text/confidence, fingerprint, and privacy flags.
- [x] Add review handling for uncertain OCR where scanning can safely continue: item, weapon, and Echo inventory entries route unknown/low-confidence results to privacy-minimized review artifacts; critical character state remains fail-closed.
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
- [x] Detect the Win32 client-area and target-monitor bounds before live automation; reject layouts that cannot safely use monitor-relative coordinates.
- [ ] Account for Windows DPI scaling.
- [ ] Support borderless-windowed if reliable.
- [x] Add a privacy-safe calibration/debug ROI overlay that draws click-through named ROIs over the live game without capturing or saving pixels.
- [x] Add no-click screenshot diagnostic mode that saves only named scanner ROIs plus layout metadata, never a full-screen capture.
- [x] Reject unsupported layouts before scanner input. Current safe policy requires 100% Windows scaling, a client area filling the entire target monitor, and an explicit ROI resolution.

## Phase 7 — Scanner state machine and safety

- [ ] Replace fragile fixed click/sleep sequences with explicit states.
- [ ] Verify expected screen before each action.
- [ ] Verify expected transition after each action.
- [x] Add bounded retries and safe cancellation: critical count/Shell OCR reads use bounded 3-attempt retries, and scanner cancellation is cooperative with a 4-second hard-termination fallback.
- [x] Remove the forced Administrator requirement; scanner input remains ordinary user-level Win32 mouse/keyboard automation. Real game interaction still requires manual validation.
- [x] Keep all interaction at ordinary user-input level; no process memory, injection, packet interception, or anti-cheat bypass path is used.
- [x] Add a no-click screenshot diagnostic mode that captures only named scanner ROIs and layout metadata.

## Phase 8 — Character scanner

- [ ] Verify Korean and English resonator-name recognition.
- [x] Improve Rover handling with explicit Gender/Element settings and current 3.6 main-role variant IDs instead of a fixed 1502 ID.
- [ ] Verify level/ascension.
- [ ] Verify equipped weapon data.
- [ ] Re-enable character echo scan only after standalone echo scan is reliable.
- [ ] Verify all five active skills.
- [ ] Verify inherent/stat nodes.
- [ ] Verify all six resonance-chain nodes.
- [x] Improve resonator end-of-list detection so overlapping scroll viewports do not terminate on the first duplicate.
- [x] Prevent duplicate character processing by resolving cached name cards to IDs and skipping already-scanned resonators.
- [ ] Store OCR confidence/debug metadata outside compatibility export. Failed item OCR now records confidence sidecars; broader per-field debug metadata remains pending.

## Phase 9 — Weapon scanner

- [ ] Verify 24-slot page assumptions and count/page OCR.
- [ ] Verify equipped/locked states.
- [ ] Verify rarity/level filters.
- [ ] Preserve duplicate weapon copies.
- [x] Verify max-level ascension mapping with shared level-cap parsing tests, including level cap 90 -> ascension 6.
- [x] Preserve unknown/low-confidence weapon inventory entries as privacy-minimized review crops plus JSON sidecars while continuing the remaining weapon scan.

## Phase 10 — Echo scanner

- [ ] Verify current 3.6 echo card layout.
- [x] Generate current sonata/set names from `PhantomFetter_*_Name` in the selected Global TextMap; verified through the real 3.6 Korean data-generation smoke.
- [ ] Verify current main stat combinations and all substat aliases.
- [ ] Verify rarity, tune level, locked/favorited/equipped states.
- [ ] Avoid collapsing distinct identical-stat echoes.
- [x] Compare maintained Echo OCR approaches in `docs/ECHO_OCR_RESEARCH.md`; retain only high-level design observations and copy no external source/templates/assets.

## Phase 11 — Item/resource scanner

- [ ] Verify Development Items and Resources tabs.
- [ ] Verify quantities from 1 to large currency values.
- [ ] Verify duplicate grid behavior.
- [x] Replace `ceil(quantity / 999)` page-termination heuristic with viewport fingerprint detection.
- [x] Add explicit grid/end detection with a repeated-viewport signature and bounded 256-viewport safety limit.
- [x] Ensure commas/spacing/punctuation do not corrupt quantities through the shared quantity parser and regression tests.
- [x] Preserve unknown/unreadable items for manual review without fabricating a quantity; the review UI now supports an explicit Unknown state.
- [ ] Test newly added materials.

## Phase 12 — Export schema

- [x] Preserve legacy inventory/characters/weapons/echoes/achievements export filenames; new metadata is emitted only as an additional file.
- [x] Add optional `account.json`; it is emitted only when no manual-review item remains at scan completion.
- [x] Add schema/game-data metadata in a separate `scan_metadata.json` file so legacy WuWa Tracker files remain unchanged.
- [x] Use deterministic UTF-8 JSON formatting and atomic replacement for scanner exports.
- [x] Emit `validation_report.json` with selected scanners, section counts, and manual-review status.
- [x] Block credential-like fields such as oauthCode/access-token/refresh-token/password/client-secret recursively in the JSON export writer.

## Phase 13 — Optional official launcher-data integration

- [ ] Keep launcher integration isolated from screen scanner.
- [ ] Keep auth material local in memory.
- [ ] Never print or persist `oauthCode`.
- [ ] Use only fields actually exposed by launcher endpoints.
- [ ] Keep integration optional and disabled by default until reviewed.

## Phase 14 — Testing

- [x] Add unit coverage for normalization, fuzzy matching, level/quantity/stat parsing, ascension calculation, export validation, data-store reloads, and game-data transforms.
- [ ] Add screenshot fixture tests for every scanner.
- [ ] Add Korean and English regression coverage.
- [x] Add legacy inventory export validation tests covering metadata keys, numeric IDs, invalid roots, and invalid quantities.
- [x] Add malformed/partial OCR tests.
- [x] Add offline updater/cache-reuse tests.
- [x] Ensure dependency-free/unit, dependency smoke, build smoke, and fresh-install smoke tests run without Wuthering Waves installed.

## Phase 15 — Dependency/build modernization

- [x] Determine supported Python versions: dependency/import smoke passes on Windows Python 3.12, 3.13, and 3.14; build smoke is verified on 3.14.
- [x] Pin all direct runtime/build dependencies in `requirements.txt`.
- [x] Audit RapidOCR, PySide/qfluentwidgets, pywin32, OpenCV/NumPy, ONNX Runtime, and cx_Freeze compatibility through the Windows 3.12/3.13/3.14 dependency smoke matrix.
- [x] Generate package/build version from the single `version.py` source.
- [x] Stop duplicating version strings in cx_Freeze metadata/output paths.
- [x] Implement safe first-run game-data download/generation with hash validation, atomic writes, retry UI, and validated-cache fallback.
- [x] Add SHA-256/size metadata and reuse validation for downloaded source data, generated mappings, and optional UI assets.

## Phase 16 — CI

- [x] Add Windows GitHub Actions for dependency-free syntax/unit tests.
- [x] Do not require the game in CI.
- [ ] Add lint/format checks. Pinned Ruff correctness lint is active; repository-wide formatting policy/check remains pending.
- [x] Add import/compile smoke test.
- [x] Add data-generation validation, including a manual real Global-data smoke workflow.
- [x] Keep the Python 3.14 cx_Freeze build smoke workflow separate from the fast dependency-free PR checks.
- [x] Do not auto-publish releases; release workflows remain manual and packaged-build/fresh-install verification is separated from fast PR CI.

## Phase 17 — Documentation

- [x] Update README with verified Global 3.6 data-source status, current scanner constraints, and explicit no-compatibility-claim wording pending live UI validation.
- [x] State current tested/accepted modes, explicit ROI resolutions, and Korean data-generation vs live-OCR validation status in README.
- [x] Document Korean data-generation status, live-OCR limitations, diagnostics, logs, failed-OCR sidecars, and privacy guidance.
- [x] Document the no-click ROI diagnostic workflow and the data-provider patch-update commands.
- [x] Preserve GPL-3.0 licensing and upstream/Inventory Kamera attribution in the maintained fork.
- [ ] Replace dead tutorial resources where licensing permits.
- [x] Add `CONTRIBUTING.md` covering the safety boundary, development commands, game-data policy, screenshot privacy, scanner changes, exports, and release discipline.

## Phase 18 — Release gate

Do not publish a compatibility claim until:

- [x] Fresh install works in automated Windows verification: clean `.venv`, no pre-existing `data/`, real 3.6 Korean data bootstrap, offscreen Qt main-window construction, and packaged EXE smoke all pass.
- [ ] 1920x1080 fullscreen is verified end-to-end.
- [ ] Korean character scan passes.
- [ ] English character scan passes.
- [ ] Weapons, Echoes, Development Items, Resources pass.
- [ ] Export files validate.
- [x] No credential-like secrets are allowed in exports, and application logs redact oauthCode/access-refresh tokens/passwords/client secrets/Authorization Bearer values including exception tracebacks.
- [x] OCR failures are surfaced instead of silently guessed; item/weapon uncertainty is queued for review and other invalid scanner fields fail closed.
- [x] GPL-3.0 and upstream/Inventory Kamera attribution are preserved.
- [x] README lists the verified data-source versions: Global 3.6.0 / Resource 3.6.6, while keeping live scanner compatibility claims gated on real UI validation.

## After 3.6

Use 3.7 as an architecture validation:
- [ ] Update only the game-data source revision where possible.
- [ ] Regenerate mappings.
- [ ] Run screenshot regressions.
- [ ] Recalibrate only changed ROIs.
- [ ] Produce a compatibility report before scanner-logic changes.
