"""Optional UI-asset source descriptor.

Raw Wuthering Waves UI images are external game assets and are never vendored
by this project. This provider only describes where an explicitly requested
asset can be fetched for a local cache.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import quote


class UIAssetProvider:
    owner = "TomyJan"
    repo = "WutheringWaves-UIResources"

    def __init__(self, ref: str = "3.6") -> None:
        if not ref or any(part in ref for part in ("..", "\\", "\x00")):
            raise ValueError("Invalid asset source ref")
        self.ref = ref

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.repo}"

    def revision_url(self) -> str:
        return (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/"
            f"commits/{quote(self.ref, safe='')}"
        )

    def repository_path(self, asset_path: str) -> str:
        normalized = PurePosixPath(asset_path)
        if (
            not asset_path
            or normalized.is_absolute()
            or ".." in normalized.parts
            or "\\" in asset_path
        ):
            raise ValueError("Asset path must be repository-relative")
        return "UIResources/Common/Image/" + "/".join(normalized.parts)

    def raw_url(self, asset_path: str, revision: str | None = None) -> str:
        repository_path = self.repository_path(asset_path)
        selected_ref = revision or self.ref
        encoded_path = "/".join(
            quote(part, safe="") for part in PurePosixPath(repository_path).parts
        )
        return (
            f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/"
            f"{quote(selected_ref, safe='')}/{encoded_path}"
        )
