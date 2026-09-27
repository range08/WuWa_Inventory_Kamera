import unittest

from scraping.matching import (
    ECHO_NAME_CUTOFF,
    ITEM_NAME_CUTOFF,
    RESONATOR_NAME_CUTOFF,
    WEAPON_INVENTORY_NAME_CUTOFF,
    best_match,
)


class MatchingTests(unittest.TestCase):
    def test_exact_match_is_preserved(self):
        self.assertEqual(
            best_match(
                "blazingbrilliance",
                ("blazingbrilliance", "emeraldofgenesis"),
                cutoff=WEAPON_INVENTORY_NAME_CUTOFF,
            ),
            "blazingbrilliance",
        )

    def test_close_ocr_typo_matches(self):
        self.assertEqual(
            best_match(
                "blazingbrillianc",
                ("blazingbrilliance", "emeraldofgenesis"),
                cutoff=WEAPON_INVENTORY_NAME_CUTOFF,
            ),
            "blazingbrilliance",
        )

    def test_unrelated_text_does_not_match(self):
        self.assertIsNone(
            best_match(
                "completelyunrelated",
                ("yangyang", "chixia", "baizhi"),
                cutoff=RESONATOR_NAME_CUTOFF,
            )
        )

    def test_field_thresholds_are_independently_addressable(self):
        self.assertIsInstance(ITEM_NAME_CUTOFF, float)
        self.assertIsInstance(ECHO_NAME_CUTOFF, float)
        self.assertIsInstance(RESONATOR_NAME_CUTOFF, float)
        self.assertIsInstance(WEAPON_INVENTORY_NAME_CUTOFF, float)

    def test_invalid_cutoff_is_rejected(self):
        with self.assertRaises(ValueError):
            best_match("x", ("x",), cutoff=1.1)


if __name__ == "__main__":
    unittest.main()
