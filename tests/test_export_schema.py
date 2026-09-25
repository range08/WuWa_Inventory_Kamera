import unittest

from scraping.export_schema import (
    ExportValidationError,
    normalize_inventory_payload,
    validate_scan_sections,
)


class ExportSchemaTests(unittest.TestCase):
    def valid_sections(self):
        return {
            "inventory": {"2": 123456},
            "characters": {
                "1205": {
                    "level": 90,
                    "ascension": 6,
                    "weapon": {
                        "id": 21020064,
                        "level": 90,
                        "ascension": 6,
                        "rank": 5,
                    },
                    "echoes": {},
                    "skills": {
                        "normal": 10,
                        "resonance": 10,
                        "forte": 10,
                        "liberation": 10,
                        "intro": 10,
                        "stats0": 2,
                        "stats1": 2,
                        "inherent": 2,
                        "stats3": 2,
                        "stats4": 2,
                    },
                    "chain": 6,
                }
            },
            "weapons": [
                {
                    "21030016": {
                        "level": 90,
                        "ascension": 6,
                        "rank": 5,
                    }
                }
            ],
            "echoes": [
                {
                    "340000070": {
                        "level": 25,
                        "tuneLv": 5,
                        "sonata": "freezingfrost",
                        "rarity": 5,
                        "stats": {
                            "main": {"cr%": 22.0, "atk": 150},
                            "sub": {"atk": 40, "hp": 470},
                        },
                    }
                }
            ],
            "achievements": ["1001", 1002],
        }

    def test_complete_legacy_export_set_validates(self):
        validate_scan_sections(**self.valid_sections())

    def test_invalid_nested_legacy_values_fail_closed(self):
        cases = []

        bad_character = self.valid_sections()
        bad_character["characters"]["1205"]["weapon"]["rank"] = 6
        cases.append(bad_character)

        bad_weapon = self.valid_sections()
        bad_weapon["weapons"][0]["21030016"]["level"] = 0
        cases.append(bad_weapon)

        bad_echo = self.valid_sections()
        bad_echo["echoes"][0]["340000070"]["rarity"] = 6
        cases.append(bad_echo)

        bad_achievement = self.valid_sections()
        bad_achievement["achievements"] = ["not-an-id"]
        cases.append(bad_achievement)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ExportValidationError):
                    validate_scan_sections(**payload)

    def test_normalizes_numeric_ids_and_preserves_quantities(self):
        self.assertEqual(
            normalize_inventory_payload({2: 123, "43010001": 456}),
            {"2": 123, "43010001": 456},
        )

    def test_ignores_legacy_metadata_keys(self):
        self.assertEqual(
            normalize_inventory_payload({
                "_comment": "legacy documentation metadata",
                "2": 999,
            }),
            {"2": 999},
        )

    def test_rejects_non_object_root(self):
        for payload in ([], "{}", None):
            with self.subTest(payload=payload):
                with self.assertRaises(ExportValidationError):
                    normalize_inventory_payload(payload)

    def test_rejects_invalid_ids(self):
        for item_id in ("not-an-id", -1, True):
            with self.subTest(item_id=item_id):
                with self.assertRaises(ExportValidationError):
                    normalize_inventory_payload({item_id: 1})

    def test_rejects_invalid_quantities(self):
        for quantity in (-1, 1.5, "12", True):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ExportValidationError):
                    normalize_inventory_payload({"2": quantity})


if __name__ == "__main__":
    unittest.main()
