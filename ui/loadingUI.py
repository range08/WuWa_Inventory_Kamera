import logging
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QSpacerItem, QSizePolicy

from qfluentwidgets import (
	ProgressRing, BodyLabel, PushButton
)

from properties.config import basePATH
from ui.mainUI import WuWaInventoryKamera
from updater.databaseUpdater import DataUpdater

logger = logging.getLogger('LoadingScreen')

class DataUpdaterThread(QThread):
	updateProgress = Signal(int, str)
	updateFailed = Signal(str)
	updateFinished = Signal()

	def __init__(self):
		super().__init__()
		self.dataUpdater = DataUpdater()
		self.dataUpdater.updateProgress.connect(self.updateProgress.emit)
		self.dataUpdater.updateFailed.connect(self.updateFailed.emit)
		self.dataUpdater.updateFinished.connect(self.updateFinished.emit)
		logger.debug("DataUpdaterThread initialized")

	def run(self):
		logger.info("Starting data update process")
		try:
			self.dataUpdater.run()
			logger.info("Data update process finished")
		except Exception as e:
			logger.error(f"Error during data update: {e}", exc_info=True)

class LoadingScreen(QWidget):
	def __init__(self):
		super().__init__()
		logger.debug("Initializing LoadingScreen")
		self.dataUpdateError = None
		self.initWindow()
		self.setupUI()
		self.startDataUpdate()

	def initWindow(self):
		logger.debug("Setting up window properties")
		self.setFixedSize(1150, 700)
		self.setWindowIcon(QIcon(str(basePATH / 'assets' / 'icon.ico')))
		self.setWindowTitle('WuWa Inventory Kamera')

		desktop = QApplication.primaryScreen().availableGeometry()
		self.move(desktop.width() // 2 - self.width() // 2, desktop.height() // 2 - self.height() // 2)
		logger.info(f"Window positioned at {self.pos().x()}, {self.pos().y()}")

	def setupUI(self):
		logger.debug("Setting up UI components")
		self.vBoxLayout = QVBoxLayout(self)
		self.vBoxLayout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

		self.progress_ring = ProgressRing(self)
		self.progress_ring.setFixedSize(200, 200)
		self.progress_ring.setTextVisible(True)
		self.progress_ring.setValue(0)
		self.vBoxLayout.addWidget(self.progress_ring, 0, Qt.AlignHCenter)

		self.label = BodyLabel("Loading, please wait...", self)
		self.label.setStyleSheet("color: white; font-size: 18px;")
		self.label.setAlignment(Qt.AlignCenter)
		self.vBoxLayout.addWidget(self.label, 0, Qt.AlignHCenter)

		self.file_label = BodyLabel("", self)
		self.file_label.setStyleSheet("color: white; font-size: 14px;")
		self.file_label.setAlignment(Qt.AlignCenter)
		self.vBoxLayout.addWidget(self.file_label, 0, Qt.AlignHCenter)

		self.retry_button = PushButton("Retry game-data update", self)
		self.retry_button.setVisible(False)
		self.retry_button.clicked.connect(self.startDataUpdate)
		self.vBoxLayout.addWidget(self.retry_button, 0, Qt.AlignHCenter)

		self.vBoxLayout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
		logger.info("UI setup completed")

	def startDataUpdate(self):
		logger.info("Initializing and starting data update thread")
		self.dataUpdateError = None
		self.retry_button.setVisible(False)
		self.progress_ring.setValue(0)
		self.label.setText("Loading, please wait...")
		self.file_label.setText("")

		self.dataUpdater_thread = DataUpdaterThread()
		self.dataUpdater_thread.updateProgress.connect(self.updateProgress)
		self.dataUpdater_thread.updateFailed.connect(self.onDataUpdateFailed)
		self.dataUpdater_thread.updateFinished.connect(self.finishDataUpdate)
		self.dataUpdater_thread.start()

	def onDataUpdateFailed(self, message: str):
		self.dataUpdateError = message or "Unknown game-data update error."
		self.label.setText("Game-data update failed.")
		self.file_label.setText(self.dataUpdateError)
		self.retry_button.setVisible(True)

	def finishDataUpdate(self):
		if self.dataUpdateError:
			logger.error(
				"Not starting application because game-data update failed: %s",
				self.dataUpdateError,
			)
			return

		# Item icons are cosmetic. Do not block startup on an external asset
		# repository; the inventory UI provides a missing-icon fallback.
		self.on_updateFinished()

	def updateProgress(self, value, file_name):
		self.progress_ring.setValue(value)
		self.label.setText(f"Downloading {file_name}...")

	def on_updateFinished(self):
		logger.info("Required data update finished, transitioning to main window")
		self.close()
		try:
			self.main_window = WuWaInventoryKamera()
			self.main_window.show()
			logger.info("Main window displayed successfully")
		except Exception as e:
			logger.error(f"Error initializing main window: {e}", exc_info=True)