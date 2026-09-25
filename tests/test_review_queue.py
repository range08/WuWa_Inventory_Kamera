import json
import tempfile
import unittest
from pathlib import Path

from scraping.ocr_engine import OCRResult, OCRToken
from scraping.review_queue import write_review_metadata


class ReviewQueueTests(unittest.TestCase):
    def test_writes_ocr_metadata_without_full_screen_or_uid(self):
        result = OCRResult(
            text="unknown item\nowned 123",
            confidence=0.73,
            tokens=(
                OCRToken(
                    bbox=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
                    text="unknown item",
                    confidence=0.73,
                ),
            ),
            profile="legacy",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "item.json"
            write_review_metadata(
                path,
                scanner="items",
                reason="unknown_name",
                fingerprint="a" * 64,
                crop_file="item.png",
                ocr_result=result,
                owned=123,
            )

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["scanner"], "items")
            self.assertEqual(payload["ocr"]["confidence"], 0.73)
            self.assertEqual(payload["owned"], 123)
            self.assertFalse(payload["privacy"]["full_screen_saved"])
            self.assertFalse(
                payload["privacy"]["account_identifier_region_saved"]
            )
            self.assertNotIn("uid", json.dumps(payload).lower())

    def test_rejects_missing_identity_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write_review_metadata(
                    Path(tmp) / "bad.json",
                    scanner="",
                    reason="unknown",
                    fingerprint="x",
                    crop_file="crop.png",
                    ocr_result=OCRResult.empty("legacy"),
                    owned=None,
                )


if __name__ == "__main__":
    unittest.main()
