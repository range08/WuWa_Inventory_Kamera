import unittest

from scraping.record_collection import append_distinct_copy


class RecordCollectionTests(unittest.TestCase):
    def test_equal_weapon_copies_are_not_collapsed(self):
        records = []
        first = {"21030016": {"level": 90, "ascension": 6, "rank": 1}}
        second = {"21030016": {"level": 90, "ascension": 6, "rank": 1}}

        append_distinct_copy(records, first)
        append_distinct_copy(records, second)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0], records[1])
        self.assertIsNot(records[0], records[1])

    def test_equal_echo_stat_records_are_not_collapsed(self):
        records = []
        first = {
            "340000070": {
                "level": 25,
                "tuneLv": 5,
                "sonata": "freezingfrost",
                "rarity": 5,
                "stats": {"main": {"cr%": 22.0}},
            }
        }
        second = {
            "340000070": {
                "level": 25,
                "tuneLv": 5,
                "sonata": "freezingfrost",
                "rarity": 5,
                "stats": {"main": {"cr%": 22.0}},
            }
        }

        append_distinct_copy(records, first)
        append_distinct_copy(records, second)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0], records[1])


if __name__ == "__main__":
    unittest.main()
