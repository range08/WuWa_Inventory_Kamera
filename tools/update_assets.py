"""Download only explicitly requested inventory icons into the local cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from updater.asset_cache import AssetCache
from updater.asset_provider import UIAssetProvider


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Cache optional Wuthering Waves item icons locally. "
            "Raw game assets are not added to the repository."
        )
    )
    parser.add_argument("--ref", default="3.6", help="UI-resource branch/tag/commit.")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("data") / "items.json",
        help="Generated item mapping file.",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path("assets"),
        help="Local ignored asset cache.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--inventory",
        type=Path,
        help="Legacy inventory JSON; only icons for contained item IDs are cached.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Cache every icon referenced by the generated item mapping.",
    )
    return parser


def select_paths(mapping: dict, inventory: dict | None) -> set[str]:
    by_id = {
        str(info.get("id")): info
        for info in mapping.values()
        if isinstance(info, dict) and isinstance(info.get("id"), int)
    }

    if inventory is None:
        selected = by_id.values()
    else:
        if not isinstance(inventory, dict):
            raise ValueError("Inventory JSON must be an object")
        selected = (
            by_id[item_id]
            for item_id in map(str, inventory)
            if item_id in by_id
        )

    paths = {
        info["image"]
        for info in selected
        if isinstance(info.get("image"), str) and info["image"]
    }
    if not paths:
        raise ValueError("No matching item icon paths were found")
    return paths


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mapping = load_json(args.mapping)
    if not isinstance(mapping, dict):
        raise ValueError("Item mapping JSON must be an object")

    inventory = None if args.all else load_json(args.inventory)
    paths = select_paths(mapping, inventory)

    summary = AssetCache(args.assets_dir).sync(
        UIAssetProvider(args.ref),
        paths,
    )
    summary["source"] = "TomyJan/WutheringWaves-UIResources"
    summary["ref"] = args.ref
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
