import unittest

from scraping.account_export import (
    build_account_export,
    build_validation_report,
)


class AccountExportTests(unittest.TestCase):
    def make_report(self, failed_count=0):
        return build_validation_report(
            selected_scanners=["characters", "resources"],
            inventory={"2": 100},
            characters={"1205": {"level": 90}},
            weapons=[],
            echoes=[],
            achievements=[],
            failed_count=failed_count,
        )

    def test_validation_report_tracks_counts_and_review_state(self):
        report = self.make_report(failed_count=2)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "needs_review")
        self.assertEqual(report["counts"]["inventory_entries"], 1)
        self.assertEqual(report["counts"]["characters"], 1)
        self.assertEqual(report["counts"]["manual_review_items"], 2)

    def test_account_export_keeps_legacy_data_shapes_nested(self):
        metadata = {"schema_version": 1, "scan_time": "now"}
        validation = self.make_report()
        account = build_account_export(
            metadata=metadata,
            validation=validation,
            inventory={"2": 100},
            characters={"1205": {"level": 90}},
            weapons=[{"21020064": {"level": 90}}],
            echoes=[{"340000070": {"level": 25}}],
            achievements=["1001"],
        )

        self.assertEqual(account["schema_version"], 1)
        self.assertEqual(account["metadata"], metadata)
        self.assertEqual(account["inventory"], {"2": 100})
        self.assertEqual(account["validation"]["status"], "ok")

    def test_account_export_rejects_pending_manual_review(self):
        with self.assertRaisesRegex(ValueError, "pending review"):
            build_account_export(
                metadata={},
                validation=self.make_report(failed_count=1),
                inventory={},
                characters={},
                weapons=[],
                echoes=[],
                achievements=[],
            )


if __name__ == "__main__":
    unittest.main()
