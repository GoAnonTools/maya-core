import unittest
from datetime import datetime, timezone

from app.schemas import ChatRequest, ChatResponse


class ChatSchemaTests(unittest.TestCase):
    def test_chat_request_contains_message(self):
        request = ChatRequest(message="hello")

        self.assertEqual(request.message, "hello")

    def test_chat_response_contains_timestamp(self):
        timestamp = datetime.now(timezone.utc)
        response = ChatResponse(
            response="placeholder",
            model="hermes",
            mode="online",
            timestamp=timestamp,
        )

        self.assertEqual(response.timestamp, timestamp)
        self.assertEqual(response.model, "hermes")
