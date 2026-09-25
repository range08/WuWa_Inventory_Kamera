"""Synchronize external game data and generate local scanner mappings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from updater.mapping_generator import generate_from_cache
from updater.providers import ArikatsuDataProvider
from updater.source_cache import SourceCache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download validated Wuthering Waves Global data inputs and generate local scanner mappings."
    )
    parser.add_argument("--ref", default="3.6", help="Upstream branch/tag/commit to use, for example 3.6.")
    parser.add_argument("--language", default="en", help="Game text language code, for example en or ko.")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data") / "source",
        help="Ignored directory used for raw source inputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Directory for generated scanner mapping JSON files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    provider = ArikatsuDataProvider(args.ref)
    cache = SourceCache(args.cache_dir)

    manifest_path = cache.sync(provider, args.language)
    counts = generate_from_cache(manifest_path.parent, args.output_dir)
    manifest = cache.validate(manifest_path)

    summary = {
        "manifest": str(manifest_path),
        "revision": manifest["revision"],
        "game_version": manifest["source"]["game_version"],
        "resource_version": manifest["source"]["resource_version"],
        "language": manifest["language"],
        "generated": counts,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
