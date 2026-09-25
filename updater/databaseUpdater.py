import logging
import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from properties.config import LANGUAGES, basePATH, cfg
from scraping.utils import (
    achievementsID,
    charactersID,
    definedText,
    echoStats,
    echoesID,
    itemsID,
    sonataName,
    weaponsID,
)
from updater.mapping_generator import (
    MappingGenerationError,
    generate_from_cache,
    generated_mappings_current,
    load_json,
)
from updater.providers import ArikatsuDataProvider
from updater.source_cache import SourceCache, SourceCacheError

logger = logging.getLogger("DatabaseManager")


class DataUpdater(QObject):
    """Qt adapter around the versioned Global-client data updater."""

    updateProgress = Signal(int, str)
    updateFailed = Signal(str)
    updateFinished = Signal()

    def __init__(self):
        super().__init__()
        self.lang = LANGUAGES.get(cfg.get(cfg.gameLanguage), "en")
        self.source_ref = os.environ.get("WUWA_DATA_REF", "3.6").strip() or "3.6"
        self.data_dir = Path(basePATH) / "data"

    def run(self):
        try:
            self.updateProgress.emit(5, "Resolving game-data revision")

            provider = ArikatsuDataProvider(self.source_ref)
            cache = SourceCache(self.data_dir / "source")
            manifest_path = cache.sync(provider, self.lang)

            self.updateProgress.emit(85, "Preparing scanner mappings")
            counts = generated_mappings_current(
                manifest_path.parent,
                self.data_dir,
            )
            if counts is None:
                counts = generate_from_cache(manifest_path.parent, self.data_dir)
            else:
                logger.info("Reusing generated scanner mappings for current source revision")

            self._reload_generated_mappings()

            manifest = cache.validate(manifest_path)
            logger.info(
                "Game data updated: version=%s resource=%s revision=%s language=%s generated=%s",
                manifest["source"]["game_version"],
                manifest["source"]["resource_version"],
                manifest["revision"],
                manifest["language"],
                counts,
            )
            self.updateProgress.emit(100, "Game data ready")
        except (SourceCacheError, MappingGenerationError, ValueError, OSError) as exc:
            logger.error("Game-data update failed: %s", exc, exc_info=True)
            self.updateFailed.emit(str(exc))
        finally:
            self.updateFinished.emit()

    def _reload_generated_mappings(self):
        mappings = (
            ("items.json", itemsID),
            ("characters.json", charactersID),
            ("weapons.json", weaponsID),
            ("echoes.json", echoesID),
            ("achievements.json", achievementsID),
            ("echoStats.json", echoStats),
            ("definedText.json", definedText),
        )

        for filename, target in mappings:
            data = load_json(self.data_dir / filename)
            if not isinstance(data, dict):
                raise MappingGenerationError(f"Generated mapping is not an object: {filename}")
            target.clear()
            target.update(data)

        sonata = load_json(self.data_dir / "sonataName.json")
        if not isinstance(sonata, list):
            raise MappingGenerationError("Generated mapping is not a list: sonataName.json")
        sonataName.clear()
        sonataName.extend(sonata)
