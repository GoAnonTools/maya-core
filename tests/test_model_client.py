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
            "model": "NousResearch/Hermes-3-Llama-3.1-8B",
            "provider": "lightning",
            "base_url": None,
            "endpoint": None,
        }

        response = send_prompt(
            self.context,
            settings={
                "services": {
                    "model": {
                        "base_url": None,
                    }
                }
            },
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["model"],
            "NousResearch/Hermes-3-Llama-3.1-8B",
        )
        self.assertIn("not sent", response["message"])

    def test_connects_when_endpoint_is_configured(self):
        class FakeClient:
            def post(self, *args, **kwargs):
                return FakeResponse()

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "Hello from Hermes"
                            }
                        }
                    ]
                }

        response = send_prompt(
            self.context,
            {
                "mode": "online",
                "model": "NousResearch/Hermes-3-Llama-3.1-8B",
                "provider": "lightning",
                "endpoint": "https://model.example",
            },
            client=FakeClient(),
        )

        self.assertEqual(response["status"], "ok")
        self.assertEqual(
            response["model"],
            "NousResearch/Hermes-3-Llama-3.1-8B",
        )
        self.assertEqual(
            response["message"],
            "Hello from Hermes",
        )

    def test_builds_openai_compatible_payload(self):
        payload = build_chat_completion_payload(
            self.context,
            {"model": "NousResearch/Hermes-3-Llama-3.1-8B", "endpoint": None},
        )

        self.assertEqual(
            payload["model"],
            "NousResearch/Hermes-3-Llama-3.1-8B",
        )
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
