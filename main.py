import logging
import sys
import multiprocessing
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from app import start
from properties.config import basePATH
from properties.logging_utils import RedactingFormatter
from version import __version__

def run_smoke_test() -> int:
	"""Validate that the packaged runtime can import and locate core assets."""
	from scraping.data_store import STORE
	from scraping.ocr_engine import OCREngine
	from ui.mainUI import WuWaInventoryKamera
	from updater.databaseUpdater import DataUpdater

	if not (basePATH / 'assets' / 'icon.ico').is_file():
		raise RuntimeError("Bundled application icon is missing.")

	if not isinstance(__version__, str) or not __version__:
		raise RuntimeError("Application version metadata is invalid.")

	assert STORE is not None
	assert OCREngine is not None
	assert WuWaInventoryKamera is not None
	assert DataUpdater is not None
	return 0


def main():
	configure_logging()
	logger = logging.getLogger('WuWaInventoryKamera')
	logger.info("WuWa Inventory Kamera initialized")

	if '--smoke-test' in sys.argv:
		try:
			run_smoke_test()
		except Exception:
			logger.critical("Packaged runtime smoke test failed", exc_info=True)
			return 1
		logger.info("Packaged runtime smoke test passed")
		return 0

	try:
		start()
	except Exception:
		logger.critical("Main application crashed", exc_info=True)
		return 1

	logger.info("Application closed")
	return 0

def configure_logging():
	Path('logs').mkdir(parents=True, exist_ok=True)

	# Create the formatter
	formatter = RedactingFormatter(
		fmt='%(asctime)s|%(levelname)s|%(name)s|%(message)s'
	)

	# Debug file handler
	debug_file_handler = TimedRotatingFileHandler(
		filename='./logs/WuWaInventoryKamera.debug.log',
		when='midnight',
		interval=1,
		backupCount=4,
		encoding='utf-8'
	)
	debug_file_handler.setFormatter(formatter)
	debug_file_handler.setLevel(logging.DEBUG)

	# General log file handler
	log_file_handler = TimedRotatingFileHandler(
		filename='./logs/WuWaInventoryKamera.log',
		when='midnight',
		interval=1,
		backupCount=4,
		encoding='utf-8'
	)
	log_file_handler.setFormatter(formatter)
	log_file_handler.setLevel(logging.INFO)

	# Console handler
	console_handler = logging.StreamHandler()
	console_handler.setFormatter(formatter)
	console_handler.setLevel(logging.DEBUG)

	# Get the root logger and configure it
	root_logger = logging.getLogger()
	root_logger.setLevel(logging.DEBUG)
	root_logger.addHandler(console_handler)
	root_logger.addHandler(debug_file_handler)
	root_logger.addHandler(log_file_handler)

if __name__ == '__main__':
	multiprocessing.freeze_support()
	raise SystemExit(main())
