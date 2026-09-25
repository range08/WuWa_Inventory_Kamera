"""Game-data source definitions for WuWa Inventory Kamera.

This module intentionally contains no downloaded Wuthering Waves game data.
Providers describe where source data lives and how source-version metadata is
parsed. Downloading and transforming data remains a separate responsibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote


@dataclass(frozen=True)
class SourceMetadata:
    repository: str
    ref: str
    game_version: str
    resource_version: str
    changelist: str


class ArikatsuDataProvider:
    """Descriptor for the public Global-client data mirror maintained by Arikatsu.

    Upstream game data is not licensed by this project and must not be vendored
    into this repository. Consumers should download only the files they need and
    generate local scanner mappings.
    """

    owner = "Arikatsu"
    repo = "WutheringWaves_Data"

    _GAME_VERSION_RE = re.compile(r"Game Version:\s*([^<\r\n]+)", re.IGNORECASE)
    _RESOURCE_VERSION_RE = re.compile(r"Resource Version:\s*([^<\r\n]+)", re.IGNORECASE)
    _CHANGELIST_RE = re.compile(r"Changelist:\s*([^<\r\n]+)", re.IGNORECASE)

    def __init__(self, ref: str = "3.6") -> None:
        if not ref or any(part in ref for part in ("..", "\\", "\x00")):
            raise ValueError("Invalid source ref")
        self.ref = ref

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.repo}"

    def raw_url(self, path: str) -> str:
        normalized = PurePosixPath(path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Source path must be repository-relative")
        encoded_path = "/".join(quote(part, safe="") for part in normalized.parts)
        return (
            f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/"
            f"{quote(self.ref, safe='')}/{encoded_path}"
        )

    def metadata_url(self) -> str:
        return self.raw_url("README.md")

    def revision_url(self) -> str:
        return (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/"
            f"commits/{quote(self.ref, safe='')}"
        )

    def required_paths(self, language: str) -> tuple[str, ...]:
        """Return the minimal raw inputs needed by the mapping generator.

        MultiText is intentionally treated as a local build input. Generated
        mappings may be stored locally, but the upstream Textmap itself must not
        be committed or packaged by this project.
        """

        language = language.strip()
        if not language or "/" in language or "\\" in language or ".." in language:
            raise ValueError("Invalid language code")

        paths = [
            "README.md",
            "BinData/item/iteminfo.json",
            "BinData/weapon/weaponconf.json",
            "BinData/role/roleinfo.json",
            "BinData/main_role_change/mainroleconfig.json",
            "BinData/monster_Info/monsterinfo.json",
            "BinData/achievement/achievement.json",
            f"Textmaps/{language}/multi_text/MultiText.json",
        ]
        if language != "en":
            paths.append("Textmaps/en/multi_text/MultiText.json")
        return tuple(paths)

    def parse_metadata(self, readme: str) -> SourceMetadata:
        game = self._extract(self._GAME_VERSION_RE, readme, "game version")
        resource = self._extract(self._RESOURCE_VERSION_RE, readme, "resource version")
        changelist = self._extract(self._CHANGELIST_RE, readme, "changelist")

        return SourceMetadata(
            repository=self.repository,
            ref=self.ref,
            game_version=game,
            resource_version=resource,
            changelist=changelist,
        )

    @staticmethod
    def _extract(pattern: re.Pattern[str], text: str, field: str) -> str:
        match = pattern.search(text)
        if match is None:
            raise ValueError(f"Unable to parse {field} from source README")
        return match.group(1).strip()
