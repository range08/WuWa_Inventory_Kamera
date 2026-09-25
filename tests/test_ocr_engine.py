import unittest

from scraping.ocr_engine import (
    INTEGER_PROFILE,
    NAME_PROFILE,
    OCREngine,
    OCRError,
    OCRProfile,
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


if __name__ == "__main__":
    unittest.main()
