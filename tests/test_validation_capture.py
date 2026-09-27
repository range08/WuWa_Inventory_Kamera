import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from game.navigation.manifest import (
    allocate_session_directory,
    build_capture_record,
    build_manifest,
    failed_capture_filename,
    failure_details,
    finalize_manifest,
)
from game.navigation.state import GameState, NavigationResult, StateObservation
from game.navigation.transitions import CAPTURE_PLAN, CaptureSpec


class ValidationCapturePlanTests(unittest.TestCase):
    def test_capture_plan_has_required_order_and_deterministic_names(self):
        self.assertEqual(
            [spec.state_name for spec in CAPTURE_PLAN],
            [
                "main-menu",
                "inventory-weapons",
                "inventory-echoes",
                "inventory-development-items",
                "inventory-resources",
                "resonator-overview",
                "resonator-weapon",
                "resonator-skills",
                "resonator-chain",
                "achievements",
                "shell-credit",
            ],
        )
        self.assertEqual(
            [spec.filename for spec in CAPTURE_PLAN],
            [
                "01-main-menu.png",
                "02-inventory-weapons.png",
                "03-inventory-echoes.png",
                "04-inventory-development-items.png",
                "05-inventory-resources.png",
                "06-resonator-overview.png",
                "07-resonator-weapon.png",
                "08-resonator-skills.png",
                "09-resonator-chain.png",
                "10-achievements.png",
                "11-shell-credit.png",
            ],
        )

    def test_capture_transitions_have_sources_destinations_and_bounded_retries(self):
        all_transitions = [
            transition
            for capture in CAPTURE_PLAN
            for transition in capture.transitions
        ]
        self.assertTrue(all(item.action and item.description for item in all_transitions))
        self.assertTrue(all(1 <= item.verification_attempts <= 3 for item in all_transitions))
        self.assertTrue(
            any(
                item.source == GameState.INVENTORY_ITEMS
                and item.destination == GameState.INVENTORY_ITEMS
                and item.changed_roi == "items.info"
                for item in all_transitions
            )
        )

    def test_manifest_contains_required_metadata_and_status_fields(self):
        manifest = build_manifest(
            game_data_ref="3.6",
            game_version="3.6.0",
            resource_version="3.6.6",
            scanner_version="1.7.1",
            resolution=(1920, 1080),
            dpi_scale=1.0,
            client_bounds=(0, 0, 1920, 1080),
            monitor_bounds=(0, 0, 1920, 1080),
            started_at="2026-09-27T00:00:00+00:00",
        )
        for key in (
            "schema_version",
            "game_data_ref",
            "game_data_language",
            "game_version",
            "resource_version",
            "scanner_version",
            "resolution",
            "dpi_scale",
            "client_bounds",
            "monitor_bounds",
            "started_at",
            "completed_at",
            "status",
            "captures",
            "failed_transition",
        ):
            self.assertIn(key, manifest)
        self.assertEqual(manifest["status"], "running")
        self.assertEqual(manifest["resolution"], [1920, 1080])

    def test_capture_record_includes_transition_timestamp_and_evidence(self):
        spec = CAPTURE_PLAN[1]
        observation = StateObservation(
            GameState.INVENTORY_WEAPONS,
            True,
            "test-weapon-detector",
            0.94,
            "weapons.name",
            {"reason": "recognized"},
        )
        record = build_capture_record(
            spec,
            NavigationResult("frame", observation, attempts=2),
            captured_at="2026-09-27T00:00:02+00:00",
        )
        self.assertEqual(record["state"], "inventory-weapons")
        self.assertEqual(record["filename"], "02-inventory-weapons.png")
        self.assertTrue(record["verified"])
        self.assertEqual(record["verification"]["confidence"], 0.94)
        self.assertIn("open inventory", record["transition"])

    def test_failed_transition_is_explicit_and_never_finalizes_complete(self):
        spec = CAPTURE_PLAN[4]
        self.assertEqual(
            failed_capture_filename(spec),
            "FAILED-05-inventory-resources.png",
        )
        self.assertEqual(
            failed_capture_filename(spec, prefix="CANCELLED"),
            "CANCELLED-05-inventory-resources.png",
        )
        observation = StateObservation(
            GameState.INVENTORY_ITEMS,
            False,
            "item-detector",
            0.3,
            "items.info",
            {"reason": "no change"},
        )
        failure = failure_details(
            source="inventory-items",
            destination="inventory-items",
            action="select_resources",
            reason="transition was not verified",
            attempts=3,
            diagnostic_capture="FAILED-05-inventory-resources.png",
            verification=observation,
        )
        manifest = build_manifest(
            game_data_ref="3.6",
            game_version="3.6.0",
            resource_version="3.6.6",
            scanner_version="1.7.1",
        )
        manifest["failed_transition"] = failure
        with self.assertRaises(ValueError):
            finalize_manifest(manifest, status="complete")
        failed = finalize_manifest(manifest, status="failed")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(
            failed["failed_transition"]["diagnostic_capture"],
            "FAILED-05-inventory-resources.png",
        )

    def test_complete_manifest_requires_all_eleven_successful_captures(self):
        manifest = build_manifest(
            game_data_ref="3.6",
            game_version="3.6.0",
            resource_version="3.6.6",
            scanner_version="1.7.1",
        )
        manifest["captures"] = [{"verified": True}] * 10
        with self.assertRaises(ValueError):
            finalize_manifest(manifest, status="complete")
        manifest["captures"] = [
            {
                "verified": True,
                "state": spec.state_name,
                "filename": spec.filename,
            }
            for spec in CAPTURE_PLAN
        ]
        self.assertEqual(finalize_manifest(manifest, status="complete")["status"], "complete")

    def test_unverified_capture_cannot_be_marked_complete(self):
        manifest = build_manifest(
            game_data_ref="3.6",
            game_version="3.6.0",
            resource_version="3.6.6",
            scanner_version="1.7.1",
        )
        manifest["captures"] = [
            {
                "verified": index != 3,
                "state": spec.state_name,
                "filename": spec.filename,
            }
            for index, spec in enumerate(CAPTURE_PLAN)
        ]
        with self.assertRaisesRegex(ValueError, "unverified captures"):
            finalize_manifest(manifest, status="complete")

    def test_session_directory_never_overwrites_existing_run(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            timestamp = datetime(2026, 9, 27, tzinfo=timezone.utc)
            first = allocate_session_directory(root, started_at=timestamp)
            marker = first / "keep.txt"
            marker.write_text("existing user file", encoding="utf-8")
            second = allocate_session_directory(root, started_at=timestamp)

            self.assertNotEqual(first, second)
            self.assertEqual(marker.read_text(encoding="utf-8"), "existing user file")
            self.assertTrue(second.is_dir())

    def test_capture_spec_rejects_non_plain_filename(self):
        with self.assertRaises(ValueError):
            CaptureSpec(
                12,
                "bad",
                "../overwrite.png",
                GameState.MAIN_MENU,
            )
        with self.assertRaises(ValueError):
            CaptureSpec(
                12,
                "../bad",
                "12-bad.png",
                GameState.MAIN_MENU,
            )


if __name__ == "__main__":
    unittest.main()
