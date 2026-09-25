import unittest

from scraping.filters import include_echo, include_weapon


class ScannerFilterTests(unittest.TestCase):
    def test_weapon_thresholds_are_inclusive(self):
        self.assertTrue(
            include_weapon(
                rarity=4,
                level=50,
                min_rarity=4,
                min_level=50,
            )
        )
        self.assertFalse(
            include_weapon(
                rarity=3,
                level=50,
                min_rarity=4,
                min_level=50,
            )
        )
        self.assertFalse(
            include_weapon(
                rarity=4,
                level=49,
                min_rarity=4,
                min_level=50,
            )
        )

    def test_echo_thresholds_are_inclusive(self):
        self.assertTrue(
            include_echo(
                rarity=5,
                level=25,
                min_rarity=5,
                min_level=25,
            )
        )
        self.assertTrue(
            include_echo(
                rarity=1,
                level=0,
                min_rarity=1,
                min_level=0,
            )
        )
        self.assertFalse(
            include_echo(
                rarity=4,
                level=25,
                min_rarity=5,
                min_level=25,
            )
        )

    def test_invalid_values_fail_closed(self):
        cases = [
            lambda: include_weapon(
                rarity=0,
                level=1,
                min_rarity=1,
                min_level=1,
            ),
            lambda: include_weapon(
                rarity=1,
                level=91,
                min_rarity=1,
                min_level=1,
            ),
            lambda: include_echo(
                rarity=True,
                level=0,
                min_rarity=1,
                min_level=0,
            ),
            lambda: include_echo(
                rarity=5,
                level=26,
                min_rarity=1,
                min_level=0,
            ),
        ]
        for operation in cases:
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    operation()


if __name__ == "__main__":
    unittest.main()
