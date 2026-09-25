import json
import tempfile
import unittest
from pathlib import Path

from scraping.exporter import encode_json, write_json_atomic


class ExporterTests(unittest.TestCase):
    def test_dict_output_is_utf8_and_deterministic(self):
        first = encode_json({"b": 2, "a": "한글"})
        second = encode_json({"a": "한글", "b": 2})

        self.assertEqual(first, second)
        self.assertIn("한글".encode("utf-8"), first)
        self.assertTrue(first.endswith(b"\n"))
        self.assertEqual(json.loads(first.decode("utf-8")), {"a": "한글", "b": 2})

    def test_list_order_is_preserved(self):
        payload = encode_json([{"id": 2}, {"id": 1}])
        self.assertEqual(
            json.loads(payload.decode("utf-8")),
            [{"id": 2}, {"id": 1}],
        )

    def test_atomic_writer_creates_parent_and_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "export.json"
            write_json_atomic(path, {"value": 42})

            self.assertTrue(path.is_file())
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"value": 42},
            )
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
