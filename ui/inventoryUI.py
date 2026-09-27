import json
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QIntValidator
from PySide6.QtWidgets import (
	QWidget, QFileDialog, QGridLayout,
	QVBoxLayout
)

from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
	SettingCardGroup, ScrollArea, CardWidget,
	StrongBodyLabel, BodyLabel, LineEdit
)

from ui.custom_widgets.widget import MultiplePushSettingCard
from properties.config import cfg, basePATH
from scraping.data_store import (
    find_item_by_display_name,
    find_item_by_id,
    get_item,
)
from scraping.export_schema import ExportValidationError, normalize_inventory_payload
from scraping.exporter import write_json_atomic

logger = logging.getLogger('InventoryInterface')

class ItemCard(CardWidget):
	"""A widget representing an item with an image, name, and quantity input field."""
	
	def __init__(self, image_path, name, quantity, parent=None):
		super().__init__(parent)
		self.itemName = name
		self.quantity = quantity

		self.imageLabel = BodyLabel(self)
		self.nameLabel = StrongBodyLabel(name if len(name) < 19 else name[:16] + '...', self)
		self.quantityLineEdit = LineEdit(self)
		
		self.setupQuantityLineEdit(quantity)
		self.setupImage(image_path)
		self.setupLayout()

	def setupQuantityLineEdit(self, quantity):
		"""Configure the quantity input field."""
		self.quantityLineEdit.setText(str(quantity))
		self.quantityLineEdit.setValidator(QIntValidator(0, 999999999, self))
		self.quantityLineEdit.setAlignment(Qt.AlignCenter)

	def setupImage(self, image_path):
		"""Load the item icon without making it a hard UI dependency."""
		pixmap = QPixmap(image_path)
		self.imageLabel.setFixedSize(64, 64)
		self.imageLabel.setAlignment(Qt.AlignCenter)

		if pixmap.isNull():
			self.imageLabel.setText("—")
			self.imageLabel.setToolTip("Item icon is not cached locally.")
			return

		scaled_pixmap = pixmap.scaled(
			64,
			64,
			Qt.KeepAspectRatio,
			Qt.SmoothTransformation,
		)
		self.imageLabel.setPixmap(scaled_pixmap)

	def setupLayout(self):
		"""Arrange widgets within the layout."""
		vBoxLayout = QVBoxLayout(self)
		vBoxLayout.addWidget(self.imageLabel, alignment=Qt.AlignCenter)
		vBoxLayout.addWidget(self.nameLabel, alignment=Qt.AlignCenter)
		vBoxLayout.addWidget(self.quantityLineEdit, alignment=Qt.AlignCenter)
		vBoxLayout.setSpacing(5)
		vBoxLayout.setContentsMargins(5, 5, 5, 5)
		self.setToolTip(f"{self.itemName}")

	def getItemName(self):
		"""Return the name of the item."""
		return self.itemName

	def getQuantity(self):
		"""Return the quantity from the input field, or 0 if there's an error."""
		try:
			return int(self.quantityLineEdit.text())
		except ValueError:
			return 0

class InventoryInterface(ScrollArea):
	"""A scrollable area displaying and managing an inventory of items."""
	
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.setObjectName("inventoryUI")
		self.setStyleSheet("""
			QScrollArea { background: transparent; }
			QScrollArea > QWidget > QWidget { background: transparent; }
			QScrollArea > QScrollBar { background: transparent; }
		""")

		self.scrollWidget = QWidget()
		self.scrollWidget.setStyleSheet("background: transparent;")
		self.mainLayout = QVBoxLayout(self.scrollWidget)

		self.inventoryGroup = SettingCardGroup(self.tr("Inventory"), self.scrollWidget)
		self.inventoryFileCard = MultiplePushSettingCard(
			[self.tr('Load file'), self.tr('Save file')],
			FIF.DOWNLOAD,
			self.tr("Inventory file"),
			parent=self.inventoryGroup
		)

		self.gridWidget = QWidget(self)
		self.gridLayout = QGridLayout(self.gridWidget)

		self.__initWidget()

	def __initWidget(self):
		"""Initialize the widget and set up layout and signals."""
		self.setWidget(self.scrollWidget)
		self.setWidgetResizable(True)
		self.__initLayout()
		self.__connectSignalToSlot()

	def __initLayout(self):
		"""Set up the layout for the inventory interface."""
		self.inventoryGroup.addSettingCard(self.inventoryFileCard)
		self.mainLayout.setSpacing(28)
		self.mainLayout.setContentsMargins(60, 10, 60, 0)
		self.mainLayout.addWidget(self.inventoryGroup)
		self.mainLayout.addWidget(self.gridWidget)
		self.mainLayout.addStretch(1)
		self.gridLayout.setSpacing(10)

	def __connectSignalToSlot(self):
		"""Connect signals from the file card to the appropriate slot."""
		self.inventoryFileCard.buttonClicked.connect(self.__onInventoryFileCardClicked)

	def __onInventoryFileCardClicked(self, index):
		"""Handle button clicks on the inventory file card."""
		if index == 0:  # Load file
			self.__loadInventoryFile()
		elif index == 1:  # Save file
			self.__saveInventoryFile()

	def __loadInventoryFile(self):
		"""Load inventory data from a JSON file and populate the grid."""
		file_path, _ = QFileDialog.getOpenFileName(
			self,
			self.tr("Choose file to load"),
			cfg.get(cfg.exportFolder),
			"JSON Files (*.json)"
		)

		if file_path:
			self.inventoryFileCard.setContent(file_path)
			try:
				with open(file_path, 'r', encoding='utf-8') as file:
					data = normalize_inventory_payload(json.load(file))
				self.__populateGrid(data)
			except (
				OSError,
				UnicodeDecodeError,
				json.JSONDecodeError,
				ExportValidationError,
			) as exc:
				logger.error(
					"Unable to load inventory file %s: %s",
					file_path,
					exc,
					exc_info=True,
				)

	def __saveInventoryFile(self):
		"""Save current inventory data to a JSON file."""
		file_path = self.inventoryFileCard.getContent()
		if file_path:
			inventory_data = {}
			for i in range(self.gridLayout.count()):
				widget = self.gridLayout.itemAt(i).widget()
				if isinstance(widget, ItemCard):
					item_name = widget.getItemName()
					quantity = widget.getQuantity()
					item_id = self._getItemIDByName(item_name)
					if item_id is not None:
						inventory_data[item_id] = quantity
			
			write_json_atomic(file_path, inventory_data)

	def __populateGrid(self, inventory_file):
		"""Populate the grid layout with ItemCard widgets based on the inventory data."""
		columns = 6
		# Clear existing items from the grid
		for i in reversed(range(self.gridLayout.count())): 
			widget = self.gridLayout.itemAt(i).widget()
			if widget:
				widget.setParent(None)

		display_index = 0
		for item_id, quantity in inventory_file.items():
			item_info = self._getItemInfoByID(item_id)
			if item_info is None:
				logger.warning(
					"Skipping unknown item ID in loaded inventory: %s",
					item_id,
				)
				continue

			image, name = item_info
			card = ItemCard(str(basePATH / 'assets' / image), name, quantity)
			self.gridLayout.addWidget(
				card,
				display_index // columns,
				display_index % columns,
			)
			display_index += 1

	def _getItemIDByName(self, item_name: str):
		"""Resolve a localized display name back to its item ID."""
		normalized = ''.join(item_name.split()).lower()
		info = get_item(normalized) or find_item_by_display_name(item_name)
		return info["id"] if info is not None else None

	def _getItemInfoByID(self, item_id: int):
		"""Retrieve item image and name by its ID."""
		try:
			numeric_id = int(item_id)
		except (TypeError, ValueError):
			return None

		info = find_item_by_id(numeric_id)
		if info is None:
			return None
		return info["image"], info["name"]
