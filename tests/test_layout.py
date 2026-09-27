import unittest

from game.layout import validate_scanner_layout


class ScannerLayoutTests(unittest.TestCase):
    def test_accepts_exact_fullscreen_supported_layout(self):
        self.assertIsNone(
            validate_scanner_layout(
                client_bounds=(0, 0, 1920, 1080),
                monitor_bounds=(0, 0, 1920, 1080),
                dpi_scale=1.0,
                supported_resolutions={(1920, 1080), (1680, 1050)},
            )
        )

    def test_rejects_window_offset_from_monitor_origin(self):
        error = validate_scanner_layout(
            client_bounds=(100, 50, 2020, 1130),
            monitor_bounds=(0, 0, 1920, 1080),
            dpi_scale=1.0,
            supported_resolutions={(1920, 1080)},
        )
        self.assertIn("fill the entire target monitor", error)

    def test_rejects_non_100_percent_dpi(self):
        error = validate_scanner_layout(
            client_bounds=(0, 0, 1920, 1080),
            monitor_bounds=(0, 0, 1920, 1080),
            dpi_scale=1.25,
            supported_resolutions={(1920, 1080)},
        )
        self.assertIn("100%", error)

    def test_rejects_scaled_unprofiled_resolution(self):
        error = validate_scanner_layout(
            client_bounds=(0, 0, 2560, 1440),
            monitor_bounds=(0, 0, 2560, 1440),
            dpi_scale=1.0,
            supported_resolutions={(1920, 1080), (1680, 1050)},
        )
        self.assertIn("Unsupported scanner resolution", error)

    def test_rejects_invalid_dpi(self):
        error = validate_scanner_layout(
            client_bounds=(0, 0, 1920, 1080),
            monitor_bounds=(0, 0, 1920, 1080),
            dpi_scale=0.0,
            supported_resolutions={(1920, 1080)},
        )
        self.assertIn("determine", error)


if __name__ == "__main__":
    unittest.main()
