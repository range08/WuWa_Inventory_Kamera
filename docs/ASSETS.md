# Optional item icon cache

Item icons are cosmetic and are not required for scanning or exporting account data.

The original project downloaded whole icon folders from `Stormy-Waves/WW_Icon`.
That source is no longer available. The modernization branch therefore does not
block application startup on icon downloads.

## Current optional source

For Wuthering Waves 3.6, the optional local cache uses:

- repository: `TomyJan/WutheringWaves-UIResources`
- source branch: `3.6`
- source content: unpacked Wuthering Waves UI resources

The source repository does not expose an explicit license file. Raw images must
therefore remain local user-side cache inputs. Do not commit them to this
repository or package them in releases.

The project's `.gitignore` already excludes downloaded files under `assets/`
except for the application's own `assets/icon.ico`.

## Cache only icons used by one inventory export

```powershell
python -m tools.update_assets --inventory "export\2026-09-25_12-00-00\inventory_wuwainventorykamera.json" --ref 3.6
```

The command:

1. loads the generated `data/items.json` mapping;
2. selects only item IDs present in the supplied inventory JSON;
3. resolves the UI-resource ref to an exact Git commit SHA;
4. downloads only the referenced PNGs;
5. stores them under the same relative paths expected by the inventory UI;
6. writes `assets/asset_manifest.json` with source revision, size, and SHA-256;
7. reuses a local image only when the manifest revision and file hash match.

## Cache all known item icons

This can download a large number of files and is intentionally opt-in:

```powershell
python -m tools.update_assets --all --ref 3.6
```

Missing icons do not prevent the application from starting. The inventory UI
renders a placeholder when an icon is not available locally.
