# WuWa Inventory Kamera - A Wuthering Waves Data Scanner

WuWa Inventory Kamera is a tool designed to scan and manage data for the game Wuthering Waves.  
The data format is specifically designed for [WuWa Tracker](https://wuwatracker.com), facilitating importing data. *(Please note that I am not affiliated with WuWa Tracker.)*

## Modernization status

This fork is being updated for the current Global client without using memory reading, DLL injection, packet interception, or anti-cheat bypasses. The scanner remains screen-capture/OCR based.

The game-data pipeline has been verified against Wuthering Waves Global 3.6.0 / Resource 3.6.6 using the Korean text source. End-to-end scanner compatibility with the current 3.6 UI is **not claimed yet**; real 1920x1080 screenshots and live scans are still part of the release gate.

## Current scanner constraints

- Windows only.
- Windows display scaling must currently be **100%**.
- The Wuthering Waves client area must fill the entire target monitor.
- Live automation is accepted only for explicit ROI profiles:
  - 1920x1080
  - 1680x1050
- 2560x1440 is not currently accepted because this fork has no explicit validated ROI profile for it.
- Korean game-data generation is verified. English is used as a text fallback for missing localized entries. OCR behavior for each in-game language still requires live validation.

## Features

- Scan Characters
- Scan Weapons
- Scan Echoes
- Scan Development Items
- Scan Resources
- Scan Achievements
- Edit/View inventory data

## To-Do List
- [x] Character Scanner (no echo)
- [x] Weapons Scanner
- [x] Echoes Scanner
- [x] Achievements Scanner
- [ ] Auto Updater
- [x] Support for additional in-game languages
- [ ] Support for more software languages
- [x] Improve text recognition accuracy
- [ ] Improve logs
- [x] Optimize releases size
- [ ] Rewrite the code (after all tasks are complete)

## Development / local run

Python 3.12, 3.13, and 3.14 have passed the Windows runtime dependency/import smoke test. The current cx_Freeze build is verified with Python 3.14.

PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m tools.update_game_data --language ko --ref 3.6
python main.py
```

English game data:

```powershell
python -m tools.update_game_data --language en --ref 3.6
```

Offline reuse of the last validated source cache:

```powershell
python -m tools.update_game_data --language ko --ref 3.6 --offline
```

Build the Windows executable:

```powershell
python setup.py build
```

### No-click ROI diagnostics

For current-game calibration, manually open the requested game screen and capture only the scanner regions. The diagnostic command does not click, type, or save a full-screen screenshot.

Examples:

```powershell
python -m tools.capture_diagnostics inventory-weapons
python -m tools.capture_diagnostics inventory-echoes
python -m tools.capture_diagnostics inventory-items
python -m tools.capture_diagnostics resonator-overview
python -m tools.capture_diagnostics resonator-weapon
python -m tools.capture_diagnostics resonator-skills
python -m tools.capture_diagnostics resonator-chain
python -m tools.capture_diagnostics achievements
python -m tools.capture_diagnostics shell-credit
python -m tools.capture_diagnostics main-menu
```

Each run creates a timestamped directory under `logs/diagnostics/` containing only named ROI PNG files plus `manifest.json` with resolution, DPI, bounds, and any layout warning. Review captures before sharing them.

The updater records the exact upstream revision, game/resource versions, file hashes, and generated mapping hashes. Raw upstream game-data files stay in the ignored local cache and are not vendored into this repository.

## OCR troubleshooting

If scanning is rejected before input starts, first check the layout requirements: Windows display scaling must currently be 100%, the game client area must fill the target monitor, and the resolution must have an explicit ROI profile.

If OCR fails or a result is sent to manual review:

1. Confirm the in-game language matches the selected language in Settings.
2. Regenerate the current mapping data, for example `python -m tools.update_game_data --language ko`.
3. Use the no-click diagnostic command for the affected screen and inspect only the generated ROI crops.
4. Check `logs/WuWaInventoryKamera.debug.log` for the field that failed.
5. For item-review failures, inspect the paired PNG and JSON sidecar under `logs/fail/<scan-time>/`; the sidecar records OCR text/confidence and the failure reason.
6. Do not share full-screen captures or any crop containing a UID/account identifier.

OCR failures are intentionally surfaced rather than converted into guessed level, quantity, weapon, Echo, or character values.

## Tutorial

1. **Prepare for Scanning**
   - Ensure you are in the correct menu before clicking on 'Start Scanning'. This is crucial for accurate data capture.  
   ![menu](https://telegra.ph/file/12abde4d5ffdfb68c0142.png)

2. **Complete the Scanning Process**
   - Once scanning is complete, open WuWa Inventory Kamera. You should see something similar to the image below:  
   ![complete](https://telegra.ph/file/a50eba86bcb813e82b919.png)

3. **(Optional) Review Scanned Data**
   - You can optionally check the data that has been scanned to ensure everything is captured correctly:  
   ![review](https://telegra.ph/file/f6c6f2790eb23aa7ce3b5.png)

## Data

Legacy WuWa Tracker-compatible export files keep their existing shapes and filenames. This fork additionally writes:

- `scan_metadata.json`: scanner version, scan time, game/resource version, language, upstream revision, and source identity.
- `validation_report.json`: selected scanners, per-section counts, and whether manual review is still required.
- `account.json`: a single aggregate of metadata plus inventory/characters/weapons/echoes/achievements. It is created only when the scan has no pending manual-review item, so it is never presented as complete while an OCR failure is unresolved.

<details>
  <summary>inventory.json</summary>

  ```json
  {
    "_comment": "itemID: string(int), quantity: int",
    "2": 234
  }
  ```
</details>

<details>
  <summary>characters.json</summary>

  ```json
  {
    "_comment": "resonatorID(1205): string(int), if not the OCR failed and you will see a flatcase name of that",
    "1205": {
      "level": 90,
      "ascension": 6,
      "weapon": {
        "_comment": "weaponID: int, if not the OCR failed and you will see a flatcase name of that",
        "id": 21020064,
        "level": 80,
        "ascension": 5,
        "rank": 1
      },
      "echoes": {},
      "skills": {
        "normal": 10,
        "resonance": 10,
        "forte": 10,
        "liberation": 10,
        "intro": 10,
        "stats0": 2,
        "stats1": 2,
        "inherent": 2,
        "stats3": 2,
        "stats4": 2
      },
      "chain": 0
    }
  }
  ```
</details>

<details>
  <summary>weapons.json</summary>

  ```json
  [
    {
      "_comment": "weaponID(21030016): string(int), if not the OCR failed and you will see a flatcase name of that",
      "21030016": {
        "level": 50,
        "ascension": 2,
        "rank": 1
      }
    }
  ]
  ```
</details>

<details>
  <summary>echoes.json</summary>

  ```json
  [
    {
      "_comment": "monsterID(340000070): string(int), if not the OCR failed and you will see a flatcase name of that",
      "340000070": {
        "_comment": "sonata: is always flatcase",
        "level": 25,
        "tuneLv": 5,
        "sonata": "havoceclipse",
        "rarity": 5,
        "stats": {
          "main": {
            "cr%": 22.0,
            "atk": 150
          },
          "sub": {
            "atk": 40,
            "def": 50,
            "hp": 470,
            "basicAttack%": 8.6
          }
        }
      }
    }
  ]
  ```
  <details>
    <summary>Echo stats</summary>


  ```json
  {
    "_comment": "% will automatically be added to the stats if it is a percentage",
    "hp": "hp",
    "atk": "atk",
    "critrate": "cr",
    "critdmg": "cd",
    "def": "def",
    "energyregen": "er",
    "resonanceskilldmgbonus": "skillDmg",
    "basicattackdmgbonus": "basicAttack",
    "heavyattackdmgbonus": "heavyAttack",
    "resonanceliberationdmgbonus": "liberationDmg",
    "glaciodmgbonus": "glacio",
    "fusiondmgbonus": "fusion",
    "electrodmgbonus": "electro",
    "aerodmgbonus": "aero",
    "spectrodmgbonus": "spectro",
    "havocdmgbonus": "havoc",
    "healingbonus": "healing"
  }
  ```
  </details>
</details>

## Credits
- Highly inspired by [Inventory Kamera](https://github.com/Andrewthe13th/Inventory_Kamera) created by [Andrewthe13th](https://github.com/Andrewthe13th)
- Original updater/data work referenced [Dimbreath](https://github.com/Dimbreath/WutheringData); the modernization pipeline uses [Arikatsu/WutheringWaves_Data](https://github.com/Arikatsu/WutheringWaves_Data) as a local Global-client data input without vendoring its raw data
- Assets sourced from [Stormy Waves](https://github.com/Stormy-Waves/WW_Icon)

## License
This project is licensed under the [GNU General Public License (GPL) v3](https://www.gnu.org/licenses/gpl-3.0.html).  
This means you are free to use, modify, and distribute the project, but you must keep it under the same license and provide proper attribution.

### Third-Party Libraries
This project uses third-party libraries and resources that may be distributed under different licenses. Please check the respective library documentation for details.

## Disclaimer
All rights reserved by © Guangzhou Kuro Technology Co., Ltd. This project is not affiliated with nor endorsed by Kuro Games. Wuthering Waves and other properties are trademarks of their respective owners.
