import unittest

from scraping.result_protocol import ScraperMessageError, parse_scraper_message


class ScraperResultProtocolTests(unittest.TestCase):
    def test_accepts_inventory_failed_error_and_complete_messages(self):
        self.assertEqual(
            parse_scraper_message({"type": "inventory", "inventory": {"2": 100}}),
            ("inventory", {"2": 100}),
        )
        self.assertEqual(
            parse_scraper_message({"type": "failed", "failed": [{"owned": 1}]}),
            ("failed", [{"owned": 1}]),
        )
        self.assertEqual(
            parse_scraper_message({"type": "error", "error": "boom"}),
            ("error", "boom"),
        )
        self.assertEqual(
            parse_scraper_message({"type": "complete"}),
            ("complete", None),
        )

    def test_rejects_unknown_or_malformed_messages(self):
        invalid = (
            None,
            {},
            {"type": "inventory", "inventory": []},
            {"type": "failed", "failed": {}},
            {"type": "error", "error": ""},
            {"type": "unknown"},
        )
        for message in invalid:
            with self.subTest(message=message):
                with self.assertRaises(ScraperMessageError):
                    parse_scraper_message(message)


if __name__ == "__main__":
    unittest.main()
