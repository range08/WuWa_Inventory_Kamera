"""Local cache for optional Wuthering Waves UI icons."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from updater.asset_provider import UIAssetProvider

Fetcher = Callable[[str], bytes]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class AssetCacheError(RuntimeError):
    pass


def download_asset_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "WuWa-Inventory-Kamera/modernization"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AssetCacheError(f"Failed to download UI asset from {url}") from exc


class AssetCache:
    MANIFEST_NAME = "asset_manifest.json"

    def __init__(
        self,
        root: Path | str = "assets",
        fetcher: Fetcher = download_asset_bytes,
    ) -> None:
        self.root = Path(root)
        self.fetcher = fetcher

    def sync(
        self,
        provider: UIAssetProvider,
        asset_paths: Iterable[str],
    ) -> dict:
        revision = self._fetch_revision(provider)
        unique_paths = tuple(sorted(set(asset_paths)))
        if not unique_paths:
            raise AssetCacheError("No UI assets were requested")

        downloaded = 0
        reused = 0
        files: dict[str, dict[str, int | str]] = {}
        previous_files = self._reusable_manifest_files(provider, revision)

        for asset_path in unique_paths:
            provider.repository_path(asset_path)
            target = self.root / asset_path

            expected = previous_files.get(asset_path)
            if target.is_file() and isinstance(expected, dict):
                payload = target.read_bytes()
                metadata = self._metadata(payload)
                if (
                    self._valid_png(payload)
                    and metadata.get("sha256") == expected.get("sha256")
                    and metadata.get("size") == expected.get("size")
                ):
                    reused += 1
                    files[asset_path] = metadata
                    continue

            payload = self.fetcher(provider.raw_url(asset_path, revision))
            if not self._valid_png(payload):
                raise AssetCacheError(
                    f"Downloaded asset is not a PNG image: {asset_path}"
                )
            self._atomic_write(target, payload)
            files[asset_path] = self._metadata(payload)
            downloaded += 1

        manifest = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "repository": provider.repository,
                "ref": provider.ref,
                "revision": revision,
            },
            "files": files,
        }
        self._atomic_write(
            self.root / self.MANIFEST_NAME,
            (
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8"),
        )

        return {
            "revision": revision,
            "requested": len(unique_paths),
            "downloaded": downloaded,
            "reused": reused,
        }

    def _fetch_revision(self, provider: UIAssetProvider) -> str:
        try:
            payload = self.fetcher(provider.revision_url())
            data = json.loads(payload.decode("utf-8"))
            revision = data["sha"]
        except (
            KeyError,
            TypeError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            raise AssetCacheError("Unable to resolve UI asset revision") from exc

        if (
            not isinstance(revision, str)
            or len(revision) != 40
            or any(ch not in "0123456789abcdefABCDEF" for ch in revision)
        ):
            raise AssetCacheError("UI asset revision is not a valid Git commit SHA")
        return revision.lower()

    @staticmethod
    def _valid_png(payload: bytes) -> bool:
        return payload.startswith(PNG_SIGNATURE)

    @staticmethod
    def _metadata(payload: bytes) -> dict[str, int | str]:
        return {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix="." + path.name + ".",
            suffix=".tmp",
            dir=path.parent,
        )
        try:
            with os.fdopen(fd, "wb") as temp:
                temp.write(payload)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
