import ast
import unittest
from pathlib import Path

from game.privacy import APPROVED_CAPTURE_WRITERS


ROOT = Path(__file__).resolve().parents[1]


class ScreenshotPrivacyTests(unittest.TestCase):
    def test_captured_pixel_writes_are_confined_to_reviewed_paths(self):
        discovered = set()

        for path in ROOT.rglob("*.py"):
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith((".venv/", "dist/", "build/")):
                continue

            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                if (
                    isinstance(function, ast.Attribute)
                    and function.attr == "imwrite"
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "cv2"
                ):
                    discovered.add(relative)

        self.assertEqual(discovered, set(APPROVED_CAPTURE_WRITERS))

    def test_approved_capture_writers_are_narrowly_scoped(self):
        self.assertNotIn("scraping/utils/common.py", APPROVED_CAPTURE_WRITERS)
        self.assertNotIn("game/foreground.py", APPROVED_CAPTURE_WRITERS)
        self.assertTrue(
            all(
                path.startswith(("scraping/", "tools/"))
                for path in APPROVED_CAPTURE_WRITERS
            )
        )


if __name__ == "__main__":
    unittest.main()
