import json
import tempfile
import unittest
from pathlib import Path

from scraping.scan_metadata import ScanMetadataError, build_scan_metadata
from version import __version__


class ScanMetadataTests(unittest.TestCase):
    def make_manifest(self, root: Path):
        path = root / "mapping_manifest.json"
        path.write_text(
            json.dumps({
                "schema_version": 2,
                "source": {
                    "repository": "Arikatsu/WutheringWaves_Data",
                    "ref": "3.6",
                    "revision": "a" * 40,
                    "game_version": "3.6.0",
                    "resource_version": "3.6.6",
                    "changelist": "8499915",
                    "language": "ko",
                },
            }),
            encoding="utf-8",
        )
        return path

    def test_builds_metadata_without_modifying_legacy_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = build_scan_metadata(
                self.make_manifest(Path(tmp)),
                scan_time="2026-09-25T00:00:00+00:00",
            )

            self.assertEqual(metadata["schema_version"], 1)
            self.assertEqual(metadata["scanner_version"], __version__)
            self.assertEqual(metadata["scan_time"], "2026-09-25T00:00:00+00:00")
            self.assertEqual(metadata["game_data"]["game_version"], "3.6.0")
            self.assertEqual(metadata["game_data"]["language"], "ko")

    def test_missing_source_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_manifest(Path(tmp))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            del manifest["source"]["revision"]
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ScanMetadataError, "revision"):
                build_scan_metadata(path)

    def test_invalid_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mapping_manifest.json"
            path.write_text("not json", encoding="utf-8")

            with self.assertRaises(ScanMetadataError):
                build_scan_metadata(path)


if __name__ == "__main__":
    unittest.main()
