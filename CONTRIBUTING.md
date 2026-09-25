# Contributing to WuWa Inventory Kamera

This fork modernizes the original GPL-3.0 project while keeping the scanner screen-capture/OCR based.

## Development baseline

- Windows is the runtime target.
- Python 3.12, 3.13, and 3.14 are dependency/import-tested.
- Python 3.14 is the reference build environment.
- The current default game-data source ref is defined by `DEFAULT_GAME_DATA_REF` in `updater/providers.py`.
- Do not claim live game compatibility from data-generation tests alone.

Create an isolated environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Generate Korean Global mappings:

```powershell
python -m tools.update_game_data --language ko
```

Run tests:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
python -m ruff check . --select E9,F63,F7,F82
```

Build:

```powershell
python setup.py build
```

## Safety boundary

Do not add:

- process-memory reading or writing;
- DLL injection;
- packet interception;
- anti-cheat bypasses;
- credential/token extraction;
- launcher authentication persistence;
- hidden background input.

Scanner interaction must remain ordinary user-level screen capture and input automation.

## Game-data inputs

Raw external Wuthering Waves data is a local build/update input and is not vendored into this repository.

The updater must:

- resolve an exact upstream revision;
- hash and validate downloaded inputs;
- generate deterministic scanner mappings;
- fail closed on malformed schema;
- retain validated-cache fallback for temporary network failures;
- keep English fallback text for missing localized entries.

When a new game branch such as 3.7 becomes available, first change the single default data ref, regenerate mappings, run the real-data smoke workflow, and inspect the resulting manifest. Do not change scanner coordinates merely because game data changed.

## Screenshot and privacy rules

Never commit screenshots containing a UID, account identifier, launcher credential, authentication token, chat content, or other unrelated personal information.

Use the no-click diagnostic tool instead of full-screen screenshots:

```powershell
python -m tools.capture_diagnostics inventory-weapons
```

Diagnostic captures must contain only the named scanner ROI. Review every image before sharing or committing it.

Real screenshot fixtures should be stored only after personal/account identifiers are removed. Keep fixtures narrowly cropped to the UI element under test.

## Scanner changes

For input/ROI changes:

1. Reproduce the current behavior first.
2. Prefer fail-closed behavior over guessing.
3. Keep clicks bounded to an explicitly supported layout.
4. Preserve cooperative cancellation and UI cleanup.
5. Add or update unit tests for parsing/state logic.
6. Validate 1920x1080 fullscreen before widening support.
7. Record the exact game/resource version used for live verification.

Unknown or low-confidence OCR should be surfaced for review rather than replaced with a plausible default value.

## Exports

Existing WuWa Tracker-compatible export filenames and data shapes are compatibility surfaces. Do not change them without a versioned migration.

New metadata belongs in separate additive files such as:

- `scan_metadata.json`
- `validation_report.json`
- `account.json`

Do not add credentials, launcher auth material, or unrelated account identifiers to any export.

## Pull requests

Keep changes reviewable and scoped. Include:

- what behavior changed;
- why it changed;
- tests run;
- whether real game UI was tested;
- exact game/resource version for live UI claims;
- any remaining limitations.

Do not auto-publish a release from a modernization PR. Release compatibility requires the release-gate checks in `todo.md`.
