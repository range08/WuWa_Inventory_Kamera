# Game-data source policy

WuWa Inventory Kamera needs current names and IDs for resonators, weapons, echoes, items, achievements, and localized UI text. The original updater was written against an older `Dimbreath/WutheringData` layout.

## Current Global-client source

The modernization branch uses `Arikatsu/WutheringWaves_Data` as the first source profile. At the time this profile was introduced, its `3.6` branch reported:

- Client region: Global
- Game Version: 3.6.0
- Resource Version: 3.6.6
- Changelist: 8499915

The repository does not expose an explicit license file for the upstream game-data dump. Therefore:

- do not vendor the upstream BinData/Textmaps files into this repository;
- do not package those raw files in releases;
- download required files only as local build/update inputs;
- generate the smallest scanner mappings needed locally;
- record source repository, ref/commit, game version, resource version, and changelist;
- keep generated game data out of version control unless its redistribution status is separately established;
- all Wuthering Waves game data and terminology remain property of their respective rights holders.

This policy applies to the data, not to this project's GPL-3.0 source code.

## Relevant 3.6 source layout

```text
README.md
BinData/
  item/iteminfo.json
  weapon/weaponconf.json
  role/roleinfo.json
  monster_Info/monsterinfo.json
  achievement/achievement.json
Textmaps/
  <language>/multi_text/MultiText.json
```

The 3.6 source layout is materially different from the legacy updater's `TextMap/<lang>/MultiText.json` and `ConfigDB/*.json` assumptions. The provider layer must isolate this difference from scanner code.


## Manual update command

From the repository root:

```powershell
python -m tools.update_game_data --language ko --ref 3.6
```

For English:

```powershell
python -m tools.update_game_data --language en --ref 3.6
```

The command:

1. resolves the selected upstream ref to a concrete 40-character Git commit SHA;
2. downloads only the required source inputs into the ignored `data/source/` cache;
3. writes a manifest containing game/resource versions, changelist, revision, sizes, and SHA-256 hashes;
4. validates every cached file against the manifest;
5. generates the legacy-compatible scanner mappings into `data/`.

The raw source cache and generated data remain ignored by git.
