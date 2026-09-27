import re
import ctypes
import logging
import win32api
import win32gui
import win32con

import pywinctl as pwc
import pymonctl as pmc

from game.gameROI import COORDINATES
from game.layout import validate_scanner_layout
from game.screenInfo import ScreenInfo
from game.window_discovery import (
	WindowCandidate,
	activate_and_verify,
	select_game_window,
)
from properties.config import PROCESS_NAME, WINDOW_NAME

logger = logging.getLogger('WindowManager')

class WindowManager:
	def __init__(self, windowName: str = WINDOW_NAME, preocessName: str = PROCESS_NAME):
		self.user32 = ctypes.WinDLL('user32', use_last_error=True)
		self.windowName = windowName
		self.processName = preocessName
		self.window = self._findWindow()

	def _findWindow(self) -> pwc.Window|None:
		"""Find the largest visible top-level window for the game executable."""
		windows_by_handle = {}
		candidates = []
		tool_window_flag = getattr(win32con, "WS_EX_TOOLWINDOW", 0x80)

		try:
			windows = pwc.getAllWindows()
		except Exception:
			logger.exception("Unable to enumerate top-level windows.")
			return None

		for window in windows:
			hwnd = getattr(window, "_hWnd", None)
			if not hwnd:
				continue
			try:
				if not win32gui.IsWindowVisible(hwnd):
					continue
				owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
				extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
				left, top, right, bottom = win32gui.GetWindowRect(hwnd)
				width, height = right - left, bottom - top
				if width <= 0 or height <= 0:
					continue
				process_name = window.getAppName()
				if not isinstance(process_name, str) or not process_name.strip():
					continue

				candidate = WindowCandidate(
					hwnd=int(hwnd),
					process_name=process_name,
					title=win32gui.GetWindowText(hwnd),
					visible=True,
					width=width,
					height=height,
					owned=bool(owner),
					tool_window=bool(extended_style & tool_window_flag),
				)
			except Exception as exc:
				logger.debug(
					"Skipping window handle %r during game-window discovery: %s",
					hwnd,
					exc,
				)
				continue

			candidates.append(candidate)
			windows_by_handle[candidate.hwnd] = window

		selected = select_game_window(
			candidates,
			process_name=self.processName,
			title_hint=self.windowName,
		)
		if selected is not None:
			window = windows_by_handle[selected.hwnd]
			logger.debug(
				"Selected game window process=%r title=%r bounds=%sx%s.",
				selected.process_name,
				selected.title,
				selected.width,
				selected.height,
			)
			return window

		logger.debug(
			"No visible top-level window matched executable %r (title hint %r).",
			self.processName,
			self.windowName,
		)
		return None

	def setForeground(self) -> tuple:
		"""Request normal activation and confirm the game owns foreground."""
		if self.window:
			hwnd = self.window._hWnd
			activated, error = activate_and_verify(
				self.window.activate,
				lambda: win32gui.GetForegroundWindow() == hwnd,
			)
			if activated:
				logger.debug(
					"Game window activated and verified as foreground (title=%r).",
					win32gui.GetWindowText(hwnd),
				)
				return ("success", "Success", "pass")

			logger.warning("Unable to activate game window: %s", error)
			return ("error", "Unable to focus game window", error or "Activation failed.")
		else:
			logger.debug(
				"Cannot focus game executable %r: no visible game window was found.",
				self.processName,
			)
			return (
				"error",
				"Error",
				f"Cannot focus game process {self.processName}: window not found.",
			)

	def getWindowPosition(self) -> pmc.Point|None:
		"""Return the window's position."""
		if self.window:
			return self.window.position
		else:
			logger.debug("Cannot retrieve window position: window not found.")
			return None
	
	def getWindowSize(self) -> tuple[int, int]|None:
		"""Return the window's size."""
		if self.window:
			return self.window.width, self.window.height
		else:
			logger.debug("Cannot retrieve window size: window not found.")
			return None


	def getClientBounds(self) -> tuple[int, int, int, int]|None:
		"""Return the game client area in physical screen coordinates."""
		if not self.window:
			return None

		left, top = win32gui.ClientToScreen(self.window._hWnd, (0, 0))
		client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(
			self.window._hWnd
		)
		width = client_right - client_left
		height = client_bottom - client_top
		return left, top, left + width, top + height

	def getMonitorBounds(self) -> tuple[int, int, int, int]|None:
		"""Return the target monitor bounds in physical screen coordinates."""
		if not self.window:
			return None

		monitor = win32api.MonitorFromWindow(
			self.window._hWnd,
			win32con.MONITOR_DEFAULTTONEAREST,
		)
		info = win32api.GetMonitorInfo(monitor)
		return tuple(info["Monitor"])

	def getScannerLayoutError(self) -> str|None:
		"""Return why the current layout is unsafe for monitor-relative ROIs."""
		client_bounds = self.getClientBounds()
		monitor_bounds = self.getMonitorBounds()
		if client_bounds is None or monitor_bounds is None:
			return "Unable to determine the Wuthering Waves client/monitor bounds."

		supported_resolutions = {
			resolution
			for ratio_data in COORDINATES.values()
			for resolution in ratio_data
		}
		return validate_scanner_layout(
			client_bounds=client_bounds,
			monitor_bounds=monitor_bounds,
			dpi_scale=self.getDPI(),
			supported_resolutions=supported_resolutions,
		)
	
	def getScreenInfo(self) -> ScreenInfo:
		width, height = self.getWindowSize() or (1920, 1080)

		DPI = self.getDPI()
		monitor = self.window.getDisplay()[0] # ['\\\\.\\DISPLAY1']
		match = re.search(r'\d+', monitor)
		if match: monitor = int(match.group())
		else: monitor = 1
		
		width = int(width / DPI)
		height = int(height / DPI)
		
		return ScreenInfo(width, height, monitor)

	def _getScreen(self) -> pmc.Monitor:
		"""Return the primary screen object."""
		return pmc.getAllMonitors()[0]

	def getScreenSize(self) -> tuple[int, int]:
		"""Retrieves the primary screen size."""
		screen = self._getScreen()
		return screen.size.width, screen.size.height

	def getDPI(self) -> float:
		return self.user32.GetDpiForWindow(self.window._hWnd) / 96.0

	def isForeground(self) -> bool:
		"""Check if the window is still in foreground."""
		if self.window:
			return self.window.isActive
		return False
