import unittest
from unittest.mock import patch

from app.model_client import build_chat_completion_payload, send_prompt


class ModelClientTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "maya": {"identity": "Maya"},
            "mode": "online",
            "message": "Hello Maya",
        }

    @patch("app.model_client.select_model")
    def test_returns_unavailable_when_endpoint_is_missing(self, select_model):
        select_model.return_value = {
            "mode": "online",
            "model": "hermes",
            "provider": "lightning",
            "endpoint": None,
        }

        response = send_prompt(self.context)

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["model"], "hermes")
        self.assertIn("not sent", response["message"])

    def test_does_not_connect_when_endpoint_is_configured(self):
        response = send_prompt(
            self.context,
            {
                "mode": "online",
                "model": "hermes",
                "provider": "lightning",
                "endpoint": "https://model.example",
            },
        )

        self.assertEqual(response["status"], "not_connected")
        self.assertEqual(response["model"], "hermes")
        self.assertIn("not implemented", response["message"])

    def test_builds_openai_compatible_payload(self):
        payload = build_chat_completion_payload(
            self.context,
            {"model": "hermes", "endpoint": None},
        )

        self.assertEqual(payload["model"], "hermes")
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "You are Maya."},
                {"role": "user", "content": "Hello Maya"},
            ],
        )

    def test_rejects_empty_context_message(self):
        with self.assertRaises(ValueError):
            send_prompt(
                {
                    "maya": {"identity": "Maya"},
                    "mode": "online",
                    "message": "   ",
                },
                {"model": "qwen_local", "endpoint": None},
            )
