import logging
import unittest

from properties.logging_utils import RedactingFormatter, redact_log_text


class LoggingRedactionTests(unittest.TestCase):
    def test_redacts_assignment_style_secrets(self):
        text = (
            "oauthCode=abc access_token:xyz refresh-token = qwe "
            "password=hunter2 clientSecret=secret"
        )
        redacted = redact_log_text(text)

        for secret in ("abc", "xyz", "qwe", "hunter2", "secret"):
            self.assertNotIn(secret, redacted)
        self.assertGreaterEqual(redacted.count("<redacted>"), 5)

    def test_redacts_bearer_authorization(self):
        self.assertEqual(
            redact_log_text("Authorization: Bearer abc.def.ghi"),
            "Authorization: <redacted> abc.def.ghi",
        )
        self.assertEqual(
            redact_log_text("request Bearer abc.def.ghi failed"),
            "request Bearer <redacted> failed",
        )

    def test_ordinary_log_text_is_unchanged(self):
        text = "Game data updated: version=3.6.0 language=ko"
        self.assertEqual(redact_log_text(text), text)

    def test_formatter_redacts_exception_traceback_text(self):
        formatter = RedactingFormatter("%(levelname)s|%(message)s")
        try:
            raise RuntimeError("access_token=super-secret")
        except RuntimeError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="request failed",
                args=(),
                exc_info=__import__("sys").exc_info(),
            )

        formatted = formatter.format(record)
        self.assertNotIn("super-secret", formatted)
        self.assertIn("access_token=<redacted>", formatted)


if __name__ == "__main__":
    unittest.main()
