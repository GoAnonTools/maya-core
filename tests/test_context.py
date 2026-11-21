import unittest
from unittest.mock import patch

from app.context import create_request_context


class RequestContextTests(unittest.TestCase):
    @patch("app.context.load_settings")
    @patch("app.identity.load_identity")
    @patch("app.context.load_identity")
    def test_context_has_stable_hermes_package(
        self, load_identity, identity_load_identity, load_settings
    ):
        identity = {
            "identity": {"name": "Maya"},
            "system_prompt_template": (
                "Current context:\n"
                "- The user's name is {user_name}.\n"
                "- Current mode: {current_mode}.\n"
                "\n"
                "Respond naturally. You are Maya."
            ),
        }
        load_identity.return_value = identity
        identity_load_identity.return_value = identity
        load_settings.return_value = {"maya": {"mode": "online"}}

        context = create_request_context("  hello  ")

        self.assertEqual(
            context,
            {
                "maya": {
                    "identity": "Maya",
                    "system_prompt": (
                        "Current context:\n"
                        "- The user's name is David.\n"
                        "- Current mode: online.\n"
                        "\n"
                        "Respond naturally. You are Maya."
                    ),
                },
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
