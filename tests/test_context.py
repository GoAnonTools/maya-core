import unittest
from unittest.mock import patch

from app.context import create_request_context


class RequestContextTests(unittest.TestCase):
    @patch("app.context.load_settings")
    @patch("app.context.load_identity")
    def test_context_has_stable_hermes_package(self, load_identity, load_settings):
        load_identity.return_value = {"identity": {"name": "Maya"}}
        load_settings.return_value = {"maya": {"mode": "online"}}

        context = create_request_context("  hello  ")

        self.assertEqual(
            context,
            {
                "maya": {"identity": "Maya"},
                "mode": "online",
                "message": "hello",
            },
        )

    def test_context_rejects_empty_message(self):
        with self.assertRaises(ValueError):
            create_request_context("   ")
