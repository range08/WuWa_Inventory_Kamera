import unittest
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from game.navigation.state import GameState
from game.navigation.validation_detectors import ValidationStateDetector
from game.gameROI import COORDINATES
from scraping.ocr_engine import OCRResult


class ValidationDetectorEvidenceTests(unittest.TestCase):
    def test_1920_terminal_roi_matches_captured_korean_label_crop(self):
        roi = COORDINATES[(16, 9)][(1920, 1080)]["terminal"]

        self.assertEqual((roi.x, roi.y, roi.w, roi.h), (136, 36, 104, 46))

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

    def test_text_reads_use_detector_language_engine_and_profile(self):
        detector = ValidationStateDetector.__new__(ValidationStateDetector)
        detector.ocr_engine = object()
        from scraping.ocr_engine import KOREAN_TEXT_PROFILE

        detector.localized_text_profile = KOREAN_TEXT_PROFILE
        image_to_result = Mock(return_value=OCRResult("단말기", 0.99, (), "korean-text"))
        fake_utils = SimpleNamespace(imageToResult=image_to_result)

        with patch.dict(sys.modules, {"scraping.utils": fake_utils}):
            result = detector._text_result("terminal-crop")

        self.assertEqual(result.text, "단말기")
        image_to_result.assert_called_once_with(
            "terminal-crop",
            profile=KOREAN_TEXT_PROFILE,
            ocr_engine=detector.ocr_engine,
        )

    def test_main_menu_observation_records_language_profile(self):
        detector = ValidationStateDetector.__new__(ValidationStateDetector)
        detector._crop = lambda _frame, _roi: "terminal-crop"
        detector.ocr_engine = SimpleNamespace(language="ko")
        detector.localized_text_profile = object()
        detector.main_menu = SimpleNamespace(
            inspect_image=Mock(
                return_value={
                    "verified": True,
                    "detector": "terminal-label-ocr",
                    "confidence": 0.99,
                    "reason": None,
                    "ocr_profile": "korean-text",
                }
            )
        )

        observation = detector("frame", GameState.MAIN_MENU)

        self.assertTrue(observation.verified)
        self.assertEqual(observation.confidence, 0.99)
        self.assertEqual(observation.details["ocr_language"], "ko")
        self.assertEqual(observation.details["ocr_profile"], "korean-text")
        detector.main_menu.inspect_image.assert_called_once_with(
            "terminal-crop",
            ocr_engine=detector.ocr_engine,
            profile=detector.localized_text_profile,
        )


if __name__ == "__main__":
    unittest.main()
