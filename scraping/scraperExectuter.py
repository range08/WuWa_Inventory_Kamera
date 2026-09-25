from properties.config import cfg
from scraping.scraperManager import managerStart


def startScraper():
    scanners = {
        'characters': cfg.get(cfg.scanCharacters),
        'weapons': cfg.get(cfg.scanWeapons),
        'echoes': cfg.get(cfg.scanEchoes),
        'devItems': cfg.get(cfg.scanDevItems),
        'resources': cfg.get(cfg.scanResources),
        'achievements': cfg.get(cfg.scanAchievements),
    }
    enabled = [key for key, value in scanners.items() if value]
    enabled = ['achievements'] if 'achievements' in enabled else enabled

    if enabled:
        return managerStart(enabled)

    return ('warning', 'Warning', 'Select at least one scanner.')
