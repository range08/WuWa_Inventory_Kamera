import unittest

from scraping.cancellation import ScanCancelled, check_cancelled


class FakeEvent:
    def __init__(self, value=False):
        self.value = value

    def is_set(self):
        return self.value


class CancellationTests(unittest.TestCase):
    def test_no_event_is_allowed(self):
        check_cancelled(None)

    def test_unset_event_is_allowed(self):
        check_cancelled(FakeEvent(False))

    def test_set_event_raises_scan_cancelled(self):
        with self.assertRaises(ScanCancelled):
            check_cancelled(FakeEvent(True))


if __name__ == "__main__":
    unittest.main()
