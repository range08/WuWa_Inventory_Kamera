"""Local cache for externally sourced Wuthering Waves game data."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
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
        raise SourceCacheError("Failed to download source data from {}".format(url)) from exc


class SourceCache:
    """Synchronize and validate locally cached external game-data inputs.

    Raw upstream data is deliberately stored under data/source, which is ignored
    by this repository. A manifest is written only after all requested inputs
    have been downloaded and hashed successfully.

    A valid cache for the resolved upstream commit is reused without downloading
    the large source files again. If revision lookup is temporarily unavailable,
    sync can fall back to the newest previously validated cache.
    """

    MANIFEST_NAME = "manifest.json"

    def __init__(
        self,
        root: Path | str = Path("data") / "source",
        fetcher: Fetcher = download_bytes,
    ) -> None:
        self.root = Path(root)
        self.fetcher = fetcher

    def sync(
        self,
        provider: ArikatsuDataProvider,
        language: str,
        *,
        allow_cached_fallback: bool = True,
    ) -> Path:
        provider.required_paths(language)

        try:
            revision = self._fetch_revision(provider)
        except SourceCacheError:
            if not allow_cached_fallback:
                raise
            return self.latest_valid(provider, language)

        cache_dir = (
            self.root
            / provider.owner
            / provider.repo
            / revision
            / language
        )
        manifest_path = cache_dir / self.MANIFEST_NAME

        if manifest_path.is_file():
            try:
                manifest = self.validate(manifest_path)
            except SourceCacheError:
                pass
            else:
                if self._manifest_matches(
                    manifest,
                    provider=provider,
                    language=language,
                    revision=revision,
                ):
                    return manifest_path

        readme_bytes = self.fetcher(provider.metadata_url())
        try:
            readme = readme_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceCacheError("Source README is not valid UTF-8") from exc

        metadata = provider.parse_metadata(readme)
        files: dict[str, dict[str, int | str]] = {}

        for source_path in provider.required_paths(language):
            payload = (
                readme_bytes
                if source_path == "README.md"
                else self.fetcher(provider.raw_url(source_path))
            )
            target = cache_dir / source_path
            self._atomic_write(target, payload)
            files[source_path] = {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }

        manifest = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": asdict(metadata),
            "revision": revision,
            "language": language,
            "files": dict(sorted(files.items())),
        }
        self._atomic_write(
            manifest_path,
            (
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8"),
        )

        self.validate(manifest_path)
        return manifest_path

    def latest_valid(
        self,
        provider: ArikatsuDataProvider,
        language: str,
    ) -> Path:
        """Return the newest valid cached manifest for provider/ref/language.

        This method performs no network access and is the explicit offline path.
        """

        provider.required_paths(language)
        source_root = self.root / provider.owner / provider.repo
        if not source_root.is_dir():
            raise SourceCacheError(
                "No cached source data is available for {}".format(provider.repository)
            )

        candidates: list[tuple[str, Path]] = []
        manifest_paths = list(
            source_root.glob("*/*/{}".format(self.MANIFEST_NAME))
        )
        # Read one-level manifests created by early modernization builds too.
        manifest_paths.extend(
            source_root.glob("*/{}".format(self.MANIFEST_NAME))
        )

        for manifest_path in manifest_paths:
            try:
                manifest = self.validate(manifest_path)
            except SourceCacheError:
                continue

            if not self._manifest_matches(
                manifest,
                provider=provider,
                language=language,
                revision=None,
            ):
                continue

            generated_at = manifest.get("generated_at")
            if not isinstance(generated_at, str):
                generated_at = ""
            candidates.append((generated_at, manifest_path))

        if not candidates:
            raise SourceCacheError(
                "No valid cached source data is available for {}@{} ({})".format(
                    provider.repository,
                    provider.ref,
                    language,
                )
            )

        candidates.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
        return candidates[0][1]

    def validate(self, manifest_path: Path | str) -> dict:
        manifest_path = Path(manifest_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise SourceCacheError(
                "Invalid source manifest: {}".format(manifest_path)
            ) from exc

        if manifest.get("schema_version") != 1:
            raise SourceCacheError("Unsupported source-manifest schema")

        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise SourceCacheError("Source manifest contains no files")

        base = manifest_path.parent
        for source_path, expected in files.items():
            if not isinstance(source_path, str) or not isinstance(expected, dict):
                raise SourceCacheError(
                    "Source manifest contains malformed file metadata"
                )

            normalized = PurePosixPath(source_path)
            if (
                not source_path
                or normalized.is_absolute()
                or ".." in normalized.parts
                or "\\" in source_path
                or ":" in source_path
            ):
                raise SourceCacheError(
                    "Source manifest contains unsafe file path: {}".format(
                        source_path
                    )
                )

            target = base / source_path
            try:
                payload = target.read_bytes()
            except OSError as exc:
                raise SourceCacheError(
                    "Missing cached source file: {}".format(source_path)
                ) from exc

            actual_hash = hashlib.sha256(payload).hexdigest()
            if (
                actual_hash != expected.get("sha256")
                or len(payload) != expected.get("size")
            ):
                raise SourceCacheError(
                    "Cached source file failed validation: {}".format(source_path)
                )

        return manifest

    def _fetch_revision(self, provider: ArikatsuDataProvider) -> str:
        try:
            payload = self.fetcher(provider.revision_url())
            data = json.loads(payload.decode("utf-8"))
            revision = data["sha"]
        except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SourceCacheError("Unable to resolve source revision") from exc

        if (
            not isinstance(revision, str)
            or len(revision) != 40
            or any(ch not in "0123456789abcdefABCDEF" for ch in revision)
        ):
            raise SourceCacheError("Source revision is not a valid Git commit SHA")
        return revision.lower()

    @staticmethod
    def _manifest_matches(
        manifest: dict,
        *,
        provider: ArikatsuDataProvider,
        language: str,
        revision: str | None,
    ) -> bool:
        source = manifest.get("source")
        if not isinstance(source, dict):
            return False

        if source.get("repository") != provider.repository:
            return False
        if source.get("ref") != provider.ref:
            return False
        if manifest.get("language") != language:
            return False
        if revision is not None and manifest.get("revision") != revision:
            return False

        files = manifest.get("files")
        if not isinstance(files, dict):
            return False
        required_paths = set(provider.required_paths(language))
        if not required_paths.issubset(files):
            return False

        return True

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
