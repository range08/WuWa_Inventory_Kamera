import unittest
from types import SimpleNamespace

from game.roi_debug import overlay_rectangles


class ROIOverlayTests(unittest.TestCase):
    def make_screen(self):
        return SimpleNamespace(
            weapons=SimpleNamespace(
                page=SimpleNamespace(x=10, y=20, w=30, h=40),
                start=SimpleNamespace(x=50, y=60, w=70, h=80),
                name=SimpleNamespace(x=90, y=100, w=110, h=20),
                value=SimpleNamespace(x=90, y=130, w=110, h=20),
                level=SimpleNamespace(x=90, y=160, w=110, h=20),
                rank=SimpleNamespace(x=90, y=190, w=110, h=20),
            )
        )

    def test_returns_named_rectangles_without_image_data(self):
        rectangles = overlay_rectangles(
            self.make_screen(),
            "inventory-weapons",
        )
        self.assertEqual(rectangles[0]["label"], "count")
        self.assertEqual(rectangles[0]["x"], 10)
        self.assertEqual(rectangles[0]["height"], 40)
        self.assertTrue(all("image" not in item for item in rectangles))

    def test_unknown_group_fails_closed(self):
        with self.assertRaises(ValueError):
            overlay_rectangles(self.make_screen(), "not-a-screen")


if __name__ == "__main__":
    unittest.main()
