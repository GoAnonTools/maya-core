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


    @patch("app.context.search_memory")
    @patch("app.context.load_settings")
    @patch("app.context.load_identity")
    def test_context_includes_memory_when_available(
        self,
        load_identity,
        load_settings,
        search_memory,
    ):
        load_identity.return_value = {
            "identity": {
                "name": "Maya",
            }
        }

        load_settings.return_value = {
            "maya": {
                "mode": "online",
            }
        }

        search_memory.return_value = [
            {
                "content": "David prefers local-first AI",
                "importance": 9,
            }
        ]

        context = create_request_context(
            "What AI setup do I prefer?"
        )

        self.assertEqual(
            context["memory"],
            [
                "David prefers local-first AI",
            ],
        )
