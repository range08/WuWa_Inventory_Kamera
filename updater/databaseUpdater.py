import logging
import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from properties.config import LANGUAGES, basePATH, cfg
from scraping.data_store import GameDataStoreError, reload_generated_mappings
from updater.mapping_generator import (
    MappingGenerationError,
    generate_from_cache,
    generated_mappings_current,
)
from updater.providers import ArikatsuDataProvider, DEFAULT_GAME_DATA_REF
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
        self.source_ref = (
            os.environ.get("WUWA_DATA_REF", DEFAULT_GAME_DATA_REF).strip()
            or DEFAULT_GAME_DATA_REF
        )
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
        except (SourceCacheError, MappingGenerationError, GameDataStoreError, ValueError, OSError) as exc:
            logger.error("Game-data update failed: %s", exc, exc_info=True)
            self.updateFailed.emit(str(exc))
        except Exception as exc:
            logger.critical(
                "Unexpected game-data update failure: %s",
                exc,
                exc_info=True,
            )
            self.updateFailed.emit(
                "Unexpected game-data update failure. See the debug log for details."
            )
        finally:
            self.updateFinished.emit()

    def _reload_generated_mappings(self):
        reload_generated_mappings(self.data_dir)
