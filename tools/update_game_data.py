"""Synchronize external game data and generate local scanner mappings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from updater.mapping_generator import (
    generate_from_cache,
    generated_mappings_current,
)
from updater.providers import ArikatsuDataProvider, DEFAULT_GAME_DATA_REF
from updater.source_cache import SourceCache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download validated Wuthering Waves Global data inputs and generate local scanner mappings."
    )
    parser.add_argument(
        "--ref",
        default=DEFAULT_GAME_DATA_REF,
        help=(
            "Upstream branch/tag/commit to use "
            f"(default: {DEFAULT_GAME_DATA_REF})."
        ),
    )
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
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the newest validated local cache for the selected ref/language without network access.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate scanner mappings even when the generated manifest is current.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    provider = ArikatsuDataProvider(args.ref)
    cache = SourceCache(args.cache_dir)

    if args.offline:
        manifest_path = cache.latest_valid(provider, args.language)
    else:
        manifest_path = cache.sync(provider, args.language)
    counts = None
    regenerated = False
    if not args.force:
        counts = generated_mappings_current(
            manifest_path.parent,
            args.output_dir,
        )

    if counts is None:
        counts = generate_from_cache(manifest_path.parent, args.output_dir)
        regenerated = True

    manifest = cache.validate(manifest_path)

    summary = {
        "manifest": str(manifest_path),
        "revision": manifest["revision"],
        "game_version": manifest["source"]["game_version"],
        "resource_version": manifest["source"]["resource_version"],
        "language": manifest["language"],
        "generated": counts,
        "regenerated": regenerated,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
