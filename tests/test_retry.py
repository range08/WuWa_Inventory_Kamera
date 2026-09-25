import unittest

from scraping.retry import retry_call


class RetryTests(unittest.TestCase):
    def test_returns_first_success_without_sleep(self):
        sleeps = []
        result = retry_call(
            lambda: 42,
            attempts=3,
            sleeper=sleeps.append,
        )
        self.assertEqual(result, 42)
        self.assertEqual(sleeps, [])

    def test_retries_then_returns_success(self):
        attempts = {"count": 0}
        sleeps = []

        def operation():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError("transient")
            return 99

        result = retry_call(
            operation,
            attempts=3,
            delay_seconds=0.2,
            sleeper=sleeps.append,
        )
        self.assertEqual(result, 99)
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(sleeps, [0.2, 0.2])

    def test_reraises_last_retryable_error(self):
        errors = iter((ValueError("first"), ValueError("second")))

        with self.assertRaisesRegex(ValueError, "second"):
            retry_call(
                lambda: (_ for _ in ()).throw(next(errors)),
                attempts=2,
                sleeper=lambda _delay: None,
            )

    def test_does_not_swallow_non_retryable_error(self):
        with self.assertRaises(RuntimeError):
            retry_call(
                lambda: (_ for _ in ()).throw(RuntimeError("fatal")),
                retry_on=(ValueError,),
            )

    def test_validates_configuration(self):
        with self.assertRaises(ValueError):
            retry_call(lambda: 1, attempts=0)
        with self.assertRaises(ValueError):
            retry_call(lambda: 1, delay_seconds=-1)
        with self.assertRaises(ValueError):
            retry_call(lambda: 1, retry_on=())


if __name__ == "__main__":
    unittest.main()
