import unittest

from scraping.export_schema import (
    ExportValidationError,
    normalize_inventory_payload,
)


class ExportSchemaTests(unittest.TestCase):
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
