import unittest

from game.navigation.state import GameState
from game.navigation.validation_detectors import ValidationStateDetector
from scraping.ocr_engine import OCRResult


class ValidationDetectorEvidenceTests(unittest.TestCase):
    def make_detector(self, result):
        detector = ValidationStateDetector.__new__(ValidationStateDetector)
        detector._crop = lambda _frame, roi: roi
        detector._text_result = lambda _image, **_kwargs: result
        detector.defined_text = {}
        return detector

    def test_skill_node_state_reports_numeric_confidence(self):
        detector = self.make_detector(
            OCRResult("Upgrade", 0.91, (), "name")
        )

        observation = detector("frame", GameState.RESONATOR_SKILLS_PAGE)

        self.assertTrue(observation.verified)
        self.assertEqual(observation.confidence, 0.91)

    def test_skill_detail_state_reports_numeric_confidence(self):
        detector = self.make_detector(
            OCRResult("8", 0.88, (), "integer")
        )

        observation = detector("frame", GameState.RESONATOR_SKILLS)

        self.assertTrue(observation.verified)
        self.assertEqual(observation.confidence, 0.88)

    def test_chain_state_reports_numeric_confidence(self):
        detector = self.make_detector(
            OCRResult("Activated", 0.86, (), "name")
        )

        observation = detector("frame", GameState.RESONATOR_CHAIN)

        self.assertTrue(observation.verified)
        self.assertEqual(observation.confidence, 0.86)
        self.assertEqual(observation.details["node_status"], "text-visible")

    def test_achievement_state_reports_numeric_confidence(self):
        detector = self.make_detector(
            OCRResult("2/24", 0.93, (), "default")
        )

        observation = detector("frame", GameState.ACHIEVEMENTS)

        self.assertTrue(observation.verified)
        self.assertEqual(observation.confidence, 0.93)
        self.assertTrue(observation.details["progress_visible"])


if __name__ == "__main__":
    unittest.main()
