"""Local cache for externally sourced Wuthering Waves game data."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from updater.providers import ArikatsuDataProvider

Fetcher = Callable[[str], bytes]


class SourceCacheError(RuntimeError):
    """Raised when a source cache cannot be synchronized or validated."""


def download_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WuWa-Inventory-Kamera/modernization",
            "Accept": "application/vnd.github+json, application/json, text/plain;q=0.9, */*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SourceCacheError(f"Failed to download source data from {url}") from exc


class SourceCache:
    """Synchronize a provider into an ignored local cache directory.

    Raw upstream data is deliberately stored under data/source, which is ignored
    by this repository. A manifest is written only after all requested inputs
    have been downloaded and hashed successfully.
    """

    MANIFEST_NAME = "manifest.json"

    def __init__(self, root: Path | str = Path("data") / "source", fetcher: Fetcher = download_bytes) -> None:
        self.root = Path(root)
        self.fetcher = fetcher

    def sync(self, provider: ArikatsuDataProvider, language: str) -> Path:
        revision = self._fetch_revision(provider)
        readme_bytes = self.fetcher(provider.metadata_url())
        try:
            readme = readme_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceCacheError("Source README is not valid UTF-8") from exc

        metadata = provider.parse_metadata(readme)
        cache_dir = self.root / provider.owner / provider.repo / revision
        files: dict[str, dict[str, int | str]] = {}

        for source_path in provider.required_paths(language):
            payload = readme_bytes if source_path == "README.md" else self.fetcher(provider.raw_url(source_path))
            target = cache_dir / source_path
            self._atomic_write(target, payload)
            files[source_path] = {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }

        manifest = {
            "schema_version": 1,
            "source": asdict(metadata),
            "revision": revision,
            "language": language,
            "files": dict(sorted(files.items())),
        }
        manifest_path = cache_dir / self.MANIFEST_NAME
        self._atomic_write(
            manifest_path,
            (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )

        self.validate(manifest_path)
        return manifest_path

    def validate(self, manifest_path: Path | str) -> dict:
        manifest_path = Path(manifest_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise SourceCacheError(f"Invalid source manifest: {manifest_path}") from exc

        if manifest.get("schema_version") != 1:
            raise SourceCacheError("Unsupported source-manifest schema")

        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise SourceCacheError("Source manifest contains no files")

        base = manifest_path.parent
        for source_path, expected in files.items():
            target = base / source_path
            try:
                payload = target.read_bytes()
            except OSError as exc:
                raise SourceCacheError(f"Missing cached source file: {source_path}") from exc

            actual_hash = hashlib.sha256(payload).hexdigest()
            if actual_hash != expected.get("sha256") or len(payload) != expected.get("size"):
                raise SourceCacheError(f"Cached source file failed validation: {source_path}")

        return manifest

    def _fetch_revision(self, provider: ArikatsuDataProvider) -> str:
        try:
            payload = self.fetcher(provider.revision_url())
            data = json.loads(payload.decode("utf-8"))
            revision = data["sha"]
        except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SourceCacheError("Unable to resolve source revision") from exc

        if not isinstance(revision, str) or len(revision) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in revision):
            raise SourceCacheError("Source revision is not a valid Git commit SHA")
        return revision.lower()

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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
