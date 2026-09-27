import unittest

from scraping.cancellation import (
    ScanCancelled,
    check_cancelled,
    wait_or_cancel,
)


class FakeEvent:
    def __init__(self, value=False):
        self.value = value

    def is_set(self):
        return self.value

    def wait(self, _seconds):
        return self.value


class CancellingWaitEvent(FakeEvent):
    def wait(self, _seconds):
        self.value = True
        return True


class CancellationTests(unittest.TestCase):
    def test_no_event_is_allowed(self):
        check_cancelled(None)

    def test_unset_event_is_allowed(self):
        check_cancelled(FakeEvent(False))

    def test_set_event_raises_scan_cancelled(self):
        with self.assertRaises(ScanCancelled):
            check_cancelled(FakeEvent(True))

    def test_wait_without_event_uses_injected_sleeper(self):
        delays = []

        wait_or_cancel(None, 0.25, sleeper=delays.append)

        self.assertEqual(delays, [0.25])

    def test_wait_returns_when_event_stays_unset(self):
        event = FakeEvent()

        wait_or_cancel(event, 0.25)

        self.assertFalse(event.is_set())

    def test_wait_raises_when_event_is_set_during_delay(self):
        with self.assertRaises(ScanCancelled):
            wait_or_cancel(CancellingWaitEvent(), 0.25)

    def test_zero_delay_does_not_wait_or_raise_for_cancellation(self):
        wait_or_cancel(FakeEvent(True), 0)

    def test_wait_rejects_invalid_delays(self):
        for delay in (-0.1, float("inf"), float("nan"), True, "0.1"):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                wait_or_cancel(None, delay)


if __name__ == "__main__":
    unittest.main()
