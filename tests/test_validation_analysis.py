import unittest

from game.navigation.transitions import CAPTURE_PLAN
from tools.analyze_validation_set import (
    annotate_frame,
    build_analysis_report,
    render_markdown_report,
)


class FakeImage:
    def __init__(self, operations=None):
        self.operations = list(operations or [])

    def copy(self):
        return FakeImage(self.operations)


class FakeCV2:
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 1

    def rectangle(self, image, start, end, color, thickness):
        image.operations.append(("rectangle", start, end, color, thickness))

    def putText(self, image, text, origin, font, scale, color, thickness, line):
        image.operations.append(("text", text, origin, font, scale, color, thickness, line))


class ValidationAnalysisTests(unittest.TestCase):
    def make_manifest(self):
        return {
            "schema_version": 1,
            "resolution": [1920, 1080],
            "status": "failed",
            "captures": [
                {
                    "state": spec.state_name,
                    "filename": spec.filename,
                    "verified": True,
                }
                for spec in CAPTURE_PLAN
            ],
        }

    def test_report_associates_each_state_with_current_roi_coordinates(self):
        report = build_analysis_report(self.make_manifest())
        self.assertEqual(len(report["captures"]), 11)
        self.assertFalse(report["roi_coordinates_are_live_validated"])
        self.assertEqual(report["captures"][0]["roi_group"], "main-menu")
        self.assertEqual(report["captures"][3]["roi_group"], "inventory-items")
        weapons = report["captures"][1]
        name_roi = next(item for item in weapons["rois"] if item["roi"] == "weapons.name")
        self.assertEqual(
            (name_roi["x"], name_roi["y"], name_roi["width"], name_roi["height"]),
            (1305, 116, 545, 55),
        )
        self.assertEqual(weapons["annotated_filename"], "annotated/02-inventory-weapons-rois.png")

    def test_report_rejects_unexpected_resolution_or_unsafe_filename(self):
        manifest = self.make_manifest()
        manifest["resolution"] = [2560, 1440]
        with self.assertRaises(ValueError):
            build_analysis_report(manifest)

        manifest = self.make_manifest()
        manifest["captures"][0]["filename"] = "../private.png"
        with self.assertRaises(ValueError):
            build_analysis_report(manifest)

    def test_markdown_report_lists_coordinates_and_nonvalidation_note(self):
        report = build_analysis_report(self.make_manifest())
        markdown = render_markdown_report(report)
        self.assertIn("configured scanner ROIs", markdown)
        self.assertIn("`weapons.name`", markdown)
        self.assertIn("1305", markdown)
        self.assertIn("does not mark live ROI validation complete", markdown)

    def test_annotation_draws_on_a_copy(self):
        image = FakeImage()
        annotated = annotate_frame(
            image,
            [
                {
                    "label": "weapon-name",
                    "roi": "weapons.name",
                    "x": 1305,
                    "y": 116,
                    "width": 545,
                    "height": 55,
                }
            ],
            FakeCV2(),
        )
        self.assertIsNot(annotated, image)
        self.assertEqual(image.operations, [])
        self.assertEqual(annotated.operations[0][0], "rectangle")
        self.assertEqual(annotated.operations[0][1:3], ((1305, 116), (1850, 171)))
        self.assertEqual(annotated.operations[1][0], "text")


if __name__ == "__main__":
    unittest.main()
