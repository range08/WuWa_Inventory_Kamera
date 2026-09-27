import unittest

from game.window_discovery import (
    WindowCandidate,
    activate_and_verify,
    select_game_window,
)


class WindowSelectionTests(unittest.TestCase):
    def test_uses_executable_identity_and_area_before_localized_title(self):
        candidates = [
            WindowCandidate(
                10,
                r"C:\Games\Client-Win64-Shipping.exe",
                "Launcher helper",
                True,
                600,
                400,
            ),
            WindowCandidate(
                20,
                "Client-Win64-Shipping.exe",
                "명조:워더링 웨이브",
                True,
                1920,
                1080,
            ),
        ]

        selected = select_game_window(
            candidates,
            process_name="Client-Win64-Shipping.exe",
            title_hint="Wuthering Waves",
        )

        self.assertEqual(selected.hwnd, 20)

    def test_title_hint_only_breaks_equal_area_ties(self):
        candidates = [
            WindowCandidate(1, "Client-Win64-Shipping.exe", "Other", True, 1920, 1080),
            WindowCandidate(
                2,
                "Client-Win64-Shipping.exe",
                "Wuthering Waves",
                True,
                1920,
                1080,
            ),
        ]

        selected = select_game_window(
            candidates,
            process_name="Client-Win64-Shipping.exe",
            title_hint="Wuthering Waves",
        )

        self.assertEqual(selected.hwnd, 2)

    def test_rejects_hidden_owned_tool_and_other_process_windows(self):
        candidates = [
            WindowCandidate(1, "Client-Win64-Shipping.exe", "Hidden", False, 1920, 1080),
            WindowCandidate(
                2,
                "Client-Win64-Shipping.exe",
                "Owned popup",
                True,
                1920,
                1080,
                owned=True,
            ),
            WindowCandidate(
                3,
                "Client-Win64-Shipping.exe",
                "Tool window",
                True,
                1920,
                1080,
                tool_window=True,
            ),
            WindowCandidate(4, "Launcher.exe", "Wuthering Waves", True, 1920, 1080),
            WindowCandidate(5, None, "Unknown process", True, 1920, 1080),
        ]

        selected = select_game_window(
            candidates,
            process_name="Client-Win64-Shipping.exe",
            title_hint="Wuthering Waves",
        )

        self.assertIsNone(selected)

    def test_invalid_process_name_is_rejected(self):
        with self.assertRaises(ValueError):
            select_game_window([], process_name="  ")


class ForegroundActivationTests(unittest.TestCase):
    def test_activates_and_polls_until_foreground_is_confirmed(self):
        activation_calls = []
        checks = iter([False, False, True])
        sleeps = []

        activated, error = activate_and_verify(
            lambda: activation_calls.append("activate"),
            lambda: next(checks),
            attempts=4,
            delay_seconds=0.05,
            sleeper=sleeps.append,
        )

        self.assertTrue(activated)
        self.assertIsNone(error)
        self.assertEqual(activation_calls, ["activate"])
        self.assertEqual(sleeps, [0.05, 0.05])

    def test_reports_failed_activation_when_window_never_becomes_foreground(self):
        sleeps = []

        activated, error = activate_and_verify(
            lambda: None,
            lambda: False,
            attempts=3,
            delay_seconds=0.1,
            sleeper=sleeps.append,
        )

        self.assertFalse(activated)
        self.assertIn("did not become the foreground", error)
        self.assertEqual(sleeps, [0.1, 0.1])

    def test_verifies_foreground_even_if_activation_request_raises(self):
        checks = iter([True])

        activated, error = activate_and_verify(
            lambda: (_ for _ in ()).throw(PermissionError("activation denied")),
            lambda: next(checks),
            attempts=1,
        )

        self.assertTrue(activated)
        self.assertIsNone(error)

    def test_stops_if_foreground_verification_itself_fails(self):
        activated, error = activate_and_verify(
            lambda: None,
            lambda: (_ for _ in ()).throw(OSError("window query failed")),
            attempts=3,
            delay_seconds=0,
        )

        self.assertFalse(activated)
        self.assertIn("Unable to verify foreground window", error)

    def test_rejects_invalid_retry_limits(self):
        with self.assertRaises(ValueError):
            activate_and_verify(lambda: None, lambda: False, attempts=0)
        with self.assertRaises(ValueError):
            activate_and_verify(
                lambda: None,
                lambda: False,
                delay_seconds=float("nan"),
            )


if __name__ == "__main__":
    unittest.main()
