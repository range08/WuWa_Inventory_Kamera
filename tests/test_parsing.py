import unittest

from scraping.parsing import (
    ScanParseError,
    ascension_from_level_cap,
    parse_level_pair,
    parse_quantity,
)


class ScannerParsingTests(unittest.TestCase):
    def test_quantity_accepts_common_separators(self):
        self.assertEqual(parse_quantity("12,345"), 12345)
        self.assertEqual(parse_quantity("1 234 567"), 1234567)
        self.assertEqual(parse_quantity("Owned: 42"), 42)

    def test_quantity_rejects_text_without_digits(self):
        with self.assertRaises(ScanParseError):
            parse_quantity("unknown")

    def test_level_pair_parses_current_and_cap(self):
        self.assertEqual(parse_level_pair("80/90"), (80, 90))
        self.assertEqual(parse_level_pair(" 20 / 40 "), (20, 40))

    def test_level_pair_rejects_incomplete_or_impossible_values(self):
        for value in ("90", "/90", "90/", "91/90", "abc/90"):
            with self.subTest(value=value):
                with self.assertRaises(ScanParseError):
                    parse_level_pair(value)

    def test_ascension_uses_displayed_level_cap(self):
        caps = [20, 40, 50, 60, 70, 80, 90]
        self.assertEqual(ascension_from_level_cap(20, caps), 0)
        self.assertEqual(ascension_from_level_cap(90, caps), 6)

    def test_unknown_ascension_cap_fails_closed(self):
        with self.assertRaises(ScanParseError):
            ascension_from_level_cap(100, [20, 40, 50, 60, 70, 80, 90])


if __name__ == "__main__":
    unittest.main()
