import json
import tempfile
import unittest
from pathlib import Path

from scraping.exporter import write_json_atomic
from scraping.review_finalize import (
    ReviewFinalizeError,
    refresh_review_exports,
)


class ReviewFinalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.scan_dir = Path(self.temp_dir.name)
        self.previous_validation = {
            "schema_version": 1,
            "status": "needs_review",
            "selected_scanners": ["resources"],
            "counts": {"manual_review_items": 1},
        }
        write_json_atomic(self.scan_dir / "scan_metadata.json", {
            "schema_version": 1,
            "game_version": "3.6.0",
        })
        write_json_atomic(
            self.scan_dir / "validation_report.json",
            self.previous_validation,
        )
        write_json_atomic(
            self.scan_dir / "characters_wuwainventorykamera.json",
            {},
        )
        write_json_atomic(
            self.scan_dir / "weapons_wuwainventorykamera.json",
            [],
        )
        write_json_atomic(
            self.scan_dir / "echoes_wuwainventorykamera.json",
            [],
        )
        write_json_atomic(
            self.scan_dir / "achievements_wuwainventorykamera.json",
            [],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def finalize(self, remaining_review_items):
        return refresh_review_exports(
            self.scan_dir,
            inventory={"2": 500},
            remaining_review_items=remaining_review_items,
        )

    def read_json(self, name):
        return json.loads((self.scan_dir / name).read_text(encoding="utf-8"))

    def test_pending_review_updates_report_and_removes_stale_account(self):
        write_json_atomic(self.scan_dir / "account.json", {"stale": True})

        report = self.finalize(remaining_review_items=1)

        self.assertEqual(report["status"], "needs_review")
        self.assertEqual(report["counts"]["manual_review_items"], 1)
        self.assertFalse((self.scan_dir / "account.json").exists())
        self.assertEqual(
            self.read_json("validation_report.json"),
            report,
        )

    def test_resolved_review_writes_valid_aggregate_account(self):
        report = self.finalize(remaining_review_items=0)

        account = self.read_json("account.json")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(account["validation"], report)
        self.assertEqual(account["inventory"], {"2": 500})

    def test_invalid_legacy_data_cannot_produce_complete_account(self):
        write_json_atomic(self.scan_dir / "account.json", {"stale": True})
        write_json_atomic(
            self.scan_dir / "weapons_wuwainventorykamera.json",
            [{"21030016": {"level": 0, "ascension": 0, "rank": 1}}],
        )

        with self.assertRaises(ReviewFinalizeError):
            self.finalize(remaining_review_items=0)

        self.assertFalse((self.scan_dir / "account.json").exists())
        self.assertEqual(
            self.read_json("validation_report.json"),
            self.previous_validation,
        )

    def test_credential_fields_cannot_enter_finalized_account(self):
        (self.scan_dir / "scan_metadata.json").write_text(
            json.dumps({
                "schema_version": 1,
                "access_token": "must-not-export",
            }),
            encoding="utf-8",
        )

        with self.assertRaises(ReviewFinalizeError):
            self.finalize(remaining_review_items=0)

        self.assertFalse((self.scan_dir / "account.json").exists())
        self.assertEqual(
            self.read_json("validation_report.json"),
            self.previous_validation,
        )

    def test_review_count_must_be_a_nonnegative_integer(self):
        for value in (-1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ReviewFinalizeError):
                self.finalize(remaining_review_items=value)


if __name__ == "__main__":
    unittest.main()
