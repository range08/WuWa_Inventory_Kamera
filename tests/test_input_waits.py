import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from scraping.cancellation import ScanCancelled


class CancellingEvent:
    def __init__(self):
        self.cancelled = False

    def is_set(self):
        return self.cancelled

    def wait(self, _seconds):
        self.cancelled = True
        return True


def load_input_controller():
    win32api = SimpleNamespace(
        MapVirtualKey=lambda scan_code, _mapping: scan_code,
        keybd_event=Mock(),
    )
    win32con = SimpleNamespace(
        VK_SHIFT=0x10,
        KEYEVENTF_SCANCODE=0x01,
        KEYEVENTF_KEYUP=0x02,
        KEYEVENTF_EXTENDEDKEY=0x04,
    )
    mss_module = ModuleType("mss")
    mss_module.mss = Mock()
    stubs = {
        "win32api": win32api,
        "win32con": win32con,
        "mss": mss_module,
    }
    path = (
        Path(__file__).resolve().parents[1]
        / "scraping"
        / "utils"
        / "mouse_keyboard.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_mouse_keyboard_test_subject",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module.WindowsInputController, win32api


class InputWaitTests(unittest.TestCase):
    def test_press_key_classmethod_releases_key_before_cancellation(self):
        controller, win32api = load_input_controller()
        event = CancellingEvent()

        with self.assertRaises(ScanCancelled):
            controller.pressKey("esc", waitTime=0.1, cancel_event=event)

        self.assertEqual(win32api.keybd_event.call_count, 2)
        self.assertTrue(event.is_set())

    def test_hotkey_releases_all_keys_before_cancellation(self):
        controller, win32api = load_input_controller()
        event = CancellingEvent()

        with self.assertRaises(ScanCancelled):
            controller.hotKey(
                "ctrl",
                "v",
                delay=0,
                waitTime=0.1,
                cancel_event=event,
            )

        self.assertEqual(win32api.keybd_event.call_count, 4)
        self.assertTrue(event.is_set())


if __name__ == "__main__":
    unittest.main()
