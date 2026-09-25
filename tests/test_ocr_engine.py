import unittest

from scraping.ocr_engine import (
    INTEGER_PROFILE,
    NAME_PROFILE,
    OCREngine,
    OCRError,
    OCRConfidenceError,
    OCRProfile,
    OCRResult,
    require_confidence,
    STAT_NAME_PROFILE,
    STAT_VALUE_PROFILE,
)


def token(x, y, text, confidence):
    return (
        [
            [x, y],
            [x + 10, y],
            [x + 10, y + 10],
            [x, y + 10],
        ],
        text,
        confidence,
    )


class OCREngineTests(unittest.TestCase):
    def test_confidence_guard_accepts_threshold_boundary(self):
        result = OCRResult(
            text="Changli",
            confidence=0.75,
            tokens=(),
            profile="name",
        )
        self.assertIs(
            require_confidence(
                result,
                field="resonator-name",
                min_confidence=0.75,
            ),
            result,
        )

    def test_confidence_guard_rejects_low_or_empty_results(self):
        with self.assertRaises(OCRConfidenceError):
            require_confidence(
                OCRResult(
                    text="Changli",
                    confidence=0.74,
                    tokens=(),
                    profile="name",
                ),
                field="resonator-name",
                min_confidence=0.75,
            )
        with self.assertRaises(OCRConfidenceError):
            require_confidence(
                OCRResult.empty("name"),
                field="resonator-name",
            )

    def test_confidence_guard_validates_configuration(self):
        with self.assertRaises(ValueError):
            require_confidence(
                OCRResult.empty("name"),
                field="",
            )
        with self.assertRaises(ValueError):
            require_confidence(
                OCRResult.empty("name"),
                field="name",
                min_confidence=1.1,
            )

    def test_preserves_bbox_confidence_and_groups_rows(self):
        def backend(_image):
            return (
                [
                    token(0, 0, "Ａ B", 0.8),
                    token(20, 0, "C", 0.6),
                    token(0, 30, "D", 1.0),
                ],
                0.01,
            )

        result = OCREngine(backend).recognize(
            object(),
            OCRProfile(name="test", divisor="", banned_chars=" "),
        )

        self.assertEqual(result.text, "ABC\nD")
        self.assertAlmostEqual(result.confidence, 0.8)
        self.assertEqual(result.profile, "test")
        self.assertEqual(len(result.tokens), 3)
        self.assertEqual(result.tokens[0].bbox[0], (0.0, 0.0))
        self.assertAlmostEqual(result.tokens[0].confidence, 0.8)

    def test_integer_profile_filters_non_digits(self):
        result = OCREngine(
            lambda _image: ([token(0, 0, "12,345 credits", 0.95)], 0.01)
        ).recognize(object(), INTEGER_PROFILE)

        self.assertEqual(result.text, "12345")
        self.assertAlmostEqual(result.confidence, 0.95)

    def test_name_profile_normalizes_full_width_unicode(self):
        result = OCREngine(
            lambda _image: ([token(0, 0, "Ｃｈａｎｇｌｉ", 0.9)], 0.01)
        ).recognize(object(), NAME_PROFILE)

        self.assertEqual(result.text, "Changli")

    def test_stat_profiles_preserve_korean_names_and_numeric_values(self):
        name_result = OCREngine(
            lambda _image: ([token(0, 0, "공명 스킬 피해 보너스", 0.93)], 0.01)
        ).recognize(object(), STAT_NAME_PROFILE)
        value_result = OCREngine(
            lambda _image: (
                [
                    token(0, 0, "22.0%", 0.96),
                    token(40, 0, "150", 0.97),
                ],
                0.01,
            )
        ).recognize(object(), STAT_VALUE_PROFILE)

        self.assertEqual(name_result.text, "공명스킬피해보너스")
        self.assertEqual(value_result.text, "22.0% 150")
        self.assertGreater(name_result.confidence, 0.9)
        self.assertGreater(value_result.confidence, 0.9)

    def test_plain_two_token_list_is_not_mistaken_for_result_envelope(self):
        raw_tokens = [
            token(0, 0, "A", 0.9),
            token(20, 0, "B", 0.8),
        ]
        result = OCREngine(lambda _image: raw_tokens).recognize(
            object(),
            OCRProfile(name="plain"),
        )

        self.assertEqual(result.text, "A B")

    def test_partial_filtered_result_keeps_only_valid_tokens(self):
        result = OCREngine(
            lambda _image: (
                [
                    token(0, 0, "not-a-number", 0.4),
                    token(30, 0, "42", 0.97),
                ],
                0.01,
            )
        ).recognize(object(), INTEGER_PROFILE)

        self.assertEqual(result.text, "42")
        self.assertEqual(len(result.tokens), 1)
        self.assertAlmostEqual(result.confidence, 0.97)

    def test_empty_result_has_zero_confidence(self):
        result = OCREngine(lambda _image: (None, 0.01)).recognize(
            object(),
            OCRProfile(name="empty"),
        )

        self.assertEqual(result.text, "")
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.tokens, ())

    def test_malformed_backend_token_fails_closed(self):
        with self.assertRaises(OCRError):
            OCREngine(
                lambda _image: ([["not", "a", "valid", "token"]], 0.01)
            ).recognize(object(), OCRProfile(name="broken"))

    def test_modern_rapidocr_output_is_supported(self):
        class ModernOutput:
            boxes = [
                [[0, 0], [10, 0], [10, 10], [0, 10]],
                [[20, 0], [30, 0], [30, 10], [20, 10]],
            ]
            txts = ("Hello", "World")
            scores = (0.91, 0.93)

        result = OCREngine(lambda _image: ModernOutput()).recognize(
            object(),
            OCRProfile(name="modern"),
        )

        self.assertEqual(result.text, "Hello World")
        self.assertEqual(len(result.tokens), 2)
        self.assertAlmostEqual(result.confidence, 0.92)

    def test_candidate_recognition_uses_first_confident_result(self):
        calls = []

        def backend(image):
            calls.append(image)
            score = {1: 0.40, 2: 0.92, 3: 0.99}[image]
            return [[[[0, 0], [10, 0], [10, 10], [0, 10]], str(image), score]]

        result = OCREngine(backend).recognize_candidates(
            [1, 2, 3],
            OCRProfile(name="candidate"),
            accept_confidence=0.85,
        )

        self.assertEqual(result.text, "2")
        self.assertEqual(calls, [1, 2])

    def test_candidate_recognition_returns_best_low_confidence_result(self):
        def backend(image):
            score = {1: 0.40, 2: 0.70, 3: 0.60}[image]
            return [[[[0, 0], [10, 0], [10, 10], [0, 10]], str(image), score]]

        result = OCREngine(backend).recognize_candidates(
            [1, 2, 3],
            OCRProfile(name="candidate"),
            accept_confidence=0.85,
        )
        self.assertEqual(result.text, "2")
        self.assertAlmostEqual(result.confidence, 0.70)

    def test_candidate_recognition_validates_arguments(self):
        engine = OCREngine(lambda _image: [])
        with self.assertRaises(ValueError):
            engine.recognize_candidates([], OCRProfile(name="candidate"))
        with self.assertRaises(ValueError):
            engine.recognize_candidates(
                [1],
                OCRProfile(name="candidate"),
                accept_confidence=1.1,
            )

    def test_modern_rapidocr_output_rejects_mismatched_fields(self):
        class BrokenModernOutput:
            boxes = [[[0, 0], [10, 0], [10, 10], [0, 10]]]
            txts = ("Hello", "World")
            scores = (0.91,)

        with self.assertRaisesRegex(OCRError, "mismatched lengths"):
            OCREngine(lambda _image: BrokenModernOutput()).recognize(
                object(),
                OCRProfile(name="modern-broken"),
            )

    def test_numpy_like_bbox_is_supported_without_numpy_dependency(self):
        class ArrayLike:
            def __init__(self, value):
                self.value = value

            def tolist(self):
                return self.value

        class ModernOutput:
            boxes = ArrayLike(
                [[[0, 0], [10, 0], [10, 10], [0, 10]]]
            )
            txts = ("42",)
            scores = (0.99,)

        result = OCREngine(lambda _image: ModernOutput()).recognize(
            object(),
            INTEGER_PROFILE,
        )
        self.assertEqual(result.text, "42")


if __name__ == "__main__":
    unittest.main()
