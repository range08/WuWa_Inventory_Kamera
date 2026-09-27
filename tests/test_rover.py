import unittest

from scraping.rover import (
    ROVER_ELEMENTS,
    ROVER_GENDERS,
    resolve_rover_id,
)


class RoverVariantTests(unittest.TestCase):
    def test_all_current_variants_have_unique_ids(self):
        ids = {
            resolve_rover_id(gender, element)
            for gender in ROVER_GENDERS
            for element in ROVER_ELEMENTS
        }
        self.assertEqual(len(ids), 8)

    def test_preserves_legacy_default_variant(self):
        self.assertEqual(resolve_rover_id("Female", "Spectro"), "1502")

    def test_known_global_36_variants(self):
        expected = {
            ("Male", "Spectro"): "1501",
            ("Female", "Spectro"): "1502",
            ("Male", "Havoc"): "1605",
            ("Female", "Havoc"): "1604",
            ("Male", "Aero"): "1406",
            ("Female", "Aero"): "1408",
            ("Male", "Electro"): "1309",
            ("Female", "Electro"): "1310",
        }
        for variant, rover_id in expected.items():
            with self.subTest(variant=variant):
                self.assertEqual(resolve_rover_id(*variant), rover_id)

    def test_unknown_variant_fails_closed(self):
        with self.assertRaises(ValueError):
            resolve_rover_id("Unknown", "Spectro")


if __name__ == "__main__":
    unittest.main()
