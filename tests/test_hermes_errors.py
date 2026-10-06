import unittest

from app.services.hermes_errors import (
    HermesPartialStreamError,
    HermesTimeoutError,
    HermesUnavailableError,
    user_friendly_message,
)


class HermesErrorMessageTests(unittest.TestCase):
    def test_expected_failures_have_user_friendly_messages(self):
        self.assertIn(
            "unavailable",
            user_friendly_message(HermesUnavailableError("down")).lower(),
        )
        self.assertIn(
            "try again",
            user_friendly_message(HermesTimeoutError("slow")).lower(),
        )
        self.assertIn(
            "disconnected",
            user_friendly_message(
                HermesPartialStreamError("partial")
            ).lower(),
        )


if __name__ == "__main__":
    unittest.main()
