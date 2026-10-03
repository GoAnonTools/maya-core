import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class ChatEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.main.send_prompt")
    @patch("app.main.create_request_context")
    @patch("app.main.select_model")
    def test_chat_builds_context_before_sending(self, select_model, create_context, send_prompt):
        select_model.return_value = {
            "mode": "online",
            "model": "hermes",
            "provider": "lightning",
            "endpoint": None,
        }
        create_context.return_value = {
            "maya": {"identity": "Maya"},
            "mode": "online",
            "message": "Hello Maya",
        }
        send_prompt.return_value = {
            "status": "unavailable",
            "model": "hermes",
            "message": "No model endpoint is configured; prompt was not sent.",
        }

        response = self.client.post("/chat", json={"message": "Hello Maya"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            {
                "response": body["response"],
                "model": body["model"],
                "mode": body["mode"],
            },
            {
                "response": "No model endpoint is configured; prompt was not sent.",
                "model": "hermes",
                "mode": "online",
            },
        )
        self.assertIsNotNone(datetime.fromisoformat(body["timestamp"]))
        create_context.assert_called_once_with("Hello Maya")
        send_prompt.assert_called_once_with(create_context.return_value, select_model.return_value)

    def test_chat_rejects_empty_message(self):
        response = self.client.post("/chat", json={"message": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "message must not be empty")
