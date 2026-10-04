import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ChatResponse


class ChatEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.main.send_prompt")
    @patch("app.main.create_request_context")
    @patch("app.main.select_model")
    def test_chat_creates_context_before_sending(self, select_model, create_context, send_prompt):
        events = []
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

        def build_context(message):
            events.append("context")
            return create_context.return_value

        def send(context, route):
            events.append("send")
            return {"status": "ok", "model": route["model"], "message": "Hello from Maya."}

        create_context.side_effect = build_context
        send_prompt.side_effect = send

        response = self.client.post("/chat", json={"message": "Hello Maya"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(events, ["context", "send"])
        create_context.assert_called_once_with("Hello Maya")
        send_prompt.assert_called_once_with(create_context.return_value, select_model.return_value)

    @patch("app.main.send_prompt")
    @patch("app.main.create_request_context")
    @patch("app.main.select_model")
    def test_chat_success_returns_response_schema(self, select_model, create_context, send_prompt):
        select_model.return_value = {
            "mode": "online",
            "model": "hermes",
            "provider": "lightning",
            "endpoint": "https://model.example",
        }
        create_context.return_value = {
            "maya": {"identity": "Maya"},
            "mode": "online",
            "message": "Hello Maya",
        }
        send_prompt.return_value = {
            "status": "ok",
            "model": "hermes",
            "message": "Hello from Maya.",
        }

        response = self.client.post("/chat", json={"message": "Hello Maya"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["response"], "Hello from Maya.")
        self.assertEqual(body["model"], "hermes")
        self.assertEqual(body["mode"], "online")
        self.assertIsNotNone(datetime.fromisoformat(body["timestamp"]))
        ChatResponse(**body)

    @patch("app.main.send_prompt")
    @patch("app.main.create_request_context")
    @patch("app.main.select_model")
    def test_chat_returns_model_unavailable_error(self, select_model, create_context, send_prompt):
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

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "MODEL_UNAVAILABLE",
                    "message": "The selected model is unavailable.",
                }
            },
        )

    def test_chat_rejects_empty_message(self):
        response = self.client.post("/chat", json={"message": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "message must not be empty",
                }
            },
        )


    @patch("app.main.stream_prompt")
    @patch("app.main.create_request_context")
    @patch("app.main.select_model")
    def test_chat_stream_returns_streaming_response(
        self,
        select_model,
        create_context,
        stream_prompt,
    ):
        select_model.return_value = {
            "mode": "online",
            "model": "hermes",
            "provider": "lightning",
            "endpoint": "https://model.example",
        }

        create_context.return_value = {
            "maya": {"identity": "Maya"},
            "mode": "online",
            "message": "Hello Maya",
        }

        stream_prompt.return_value = iter(
            [
                "Hello",
                " Maya",
            ]
        )

        response = self.client.post(
            "/chat/stream",
            json={"message": "Hello Maya"},
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.headers["content-type"],
            "text/event-stream; charset=utf-8",
        )

        self.assertIn(
            "data: Hello",
            response.text,
        )

        self.assertIn(
            "data:  Maya",
            response.text,
        )

        self.assertIn(
            "data: [DONE]",
            response.text,
        )

        create_context.assert_called_once_with(
            "Hello Maya"
        )

        stream_prompt.assert_called_once_with(
            create_context.return_value,
            select_model.return_value,
        )

